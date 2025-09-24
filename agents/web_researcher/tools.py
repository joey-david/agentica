from __future__ import annotations

import atexit
import hashlib
import json
import os
import sys
import time
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from core.tool import tool
from core.inference import get_inference

try:  # Optional dependency
    import arxiv
    ARXIV_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    ARXIV_AVAILABLE = False

# Optional Selenium imports ----------------------------------------------------
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:  # pragma: no cover - handled gracefully at runtime
    WebDriverException = Exception  # type: ignore
    SELENIUM_AVAILABLE = False


# ----------------------------------------------------------------------------
# Cache helpers
# ----------------------------------------------------------------------------
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
DATA_CACHE_DIR = CACHE_ROOT / "data"
PDF_CACHE_DIR = CACHE_ROOT / "pdfs"
SCREENSHOT_DIR = CACHE_ROOT / "screenshots"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
for directory in (DATA_CACHE_DIR, PDF_CACHE_DIR, SCREENSHOT_DIR, REPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}


def _with_telemetry(payload: Dict[str, Any], *, cache_hit: bool | None, success: bool = True, info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    result = dict(payload)
    result["_telemetry"] = {
        "cache_hit": cache_hit,
        "success": success,
        "info": info or {},
    }
    return result


class CacheManager:
    """Simple JSON-based cache with expiry support."""

    def __init__(self, base_dir: Path, max_age_hours: int = 24) -> None:
        self.base_dir = base_dir
        self.max_age = timedelta(hours=max_age_hours)

    def _path_for(self, key: str) -> Path:
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.base_dir / f"{digest}.json"

    def load(self, key: str) -> Optional[Any]:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            timestamp = datetime.fromisoformat(payload.get("timestamp"))
            if datetime.utcnow() - timestamp > self.max_age:
                return None
            return payload.get("payload")
        except Exception:
            return None

    def store(self, key: str, payload: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        path = self._path_for(key)
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
            "metadata": metadata or {},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


data_cache = CacheManager(DATA_CACHE_DIR)


# ----------------------------------------------------------------------------
# Browser manager
# ----------------------------------------------------------------------------
class BrowserManager:
    """Lazy Selenium browser manager that keeps a visible window alive."""

    def __init__(self) -> None:
        self.driver = None
        self.backend = None

    def _prepare_desktop_environment(self) -> None:
        """Ensure Selenium starts with a GUI-capable environment."""
        os.environ.pop("MOZ_HEADLESS", None)

        if sys.platform.startswith("linux"):
            # Prefer Wayland when available, otherwise fall back to X11 displays.
            if os.environ.get("WAYLAND_DISPLAY"):
                os.environ.setdefault("MOZ_ENABLE_WAYLAND", "1")

            if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                for candidate in (":0", ":1", ":2"):
                    socket_path = Path(f"/tmp/.X11-unix/X{candidate.lstrip(':')}")
                    if socket_path.exists():
                        os.environ["DISPLAY"] = candidate
                        break

    def get_driver(self) -> "webdriver.Remote":
        if not SELENIUM_AVAILABLE:
            raise RuntimeError(
                "Selenium is not installed. Install 'selenium' and 'webdriver-manager' to enable browser tools."
            )

        if self.driver is not None:
            try:
                _ = self.driver.current_url  # Health check
                self._ensure_window_visible(self.driver)
                return self.driver
            except WebDriverException:
                self.shutdown()

        self.driver = self._launch_driver()
        self._ensure_window_visible(self.driver)
        return self.driver

    def _launch_driver(self) -> "webdriver.Remote":
        errors: List[str] = []
        for backend in ("chrome", "firefox"):
            try:
                driver = self._start_backend(backend)
                self.backend = backend
                driver.set_page_load_timeout(25)
                return driver
            except Exception as exc:  # pragma: no cover - hardware dependent
                errors.append(f"{backend}: {exc}")
        raise RuntimeError("Unable to start a visible browser window (" + "; ".join(errors) + ")")

    def _start_backend(self, backend: str) -> "webdriver.Remote":  # pragma: no cover - runtime only
        self._prepare_desktop_environment()

        if backend == "chrome":
            options = ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.headless = False
            options.add_experimental_option("detach", True)  # keep window open while driver lives
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)

        if backend == "firefox":
            options = FirefoxOptions()
            options.set_preference("dom.disable_beforeunload", True)
            options.set_preference("browser.tabs.warnOnClose", False)
            options.headless = False
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
            driver.maximize_window()
            return driver

        raise ValueError(f"Unsupported backend: {backend}")

    def _ensure_window_visible(self, driver: "webdriver.Remote") -> None:
        """Try to bring the browser window to the foreground for the user.

        Behaviour / configuration:
        - Respects optional env vars to control position & size:
          * AGENTICA_BROWSER_X, AGENTICA_BROWSER_Y (default auto WMs choice)
          * AGENTICA_BROWSER_W, AGENTICA_BROWSER_H (if unset -> maximize)
        - If AGENTICA_BROWSER_FORCE_FRONT=1 and the platform is Linux, will
          attempt to use 'wmctrl' or 'xdotool' if available to raise window.
        - Falls back silently if any step fails (never crashes the tool call).
        """
        try:
            handle = driver.current_window_handle
            driver.switch_to.window(handle)

            # Custom geometry if provided; otherwise maximize
            try:
                w = int(os.environ.get("AGENTICA_BROWSER_W", "0"))
                h = int(os.environ.get("AGENTICA_BROWSER_H", "0"))
                x = int(os.environ.get("AGENTICA_BROWSER_X", "-1"))
                y = int(os.environ.get("AGENTICA_BROWSER_Y", "-1"))
            except ValueError:
                w = h = x = y = 0

            if w > 200 and h > 200:
                try:
                    driver.set_window_size(w, h)
                except Exception:
                    pass
                if x >= 0 and y >= 0:
                    try:
                        driver.set_window_position(x, y)
                    except Exception:
                        pass
            else:  # maximize fallback
                try:
                    driver.maximize_window()
                except Exception:
                    pass

            # JS focus attempt
            try:
                driver.execute_script("window.focus();")
            except Exception:
                pass

            # Optional external raise on Linux
            if (
                os.name == "posix"
                and os.environ.get("AGENTICA_BROWSER_FORCE_FRONT") == "1"
            ):
                self._try_external_focus()
        except Exception:
            pass

    def _try_external_focus(self) -> None:
        """Use wmctrl / xdotool if present to raise the most recent browser window.
        This is a best-effort helper for some tiling / strict WMs.
        """
        try:
            # Choose a generic pattern; we don't store window id portably.
            patterns = [
                "Firefox",  # firefox
                "Mozilla Firefox",
                "Chrome",  # chrome
                "Chromium",
            ]
            used_tool = None
            if shutil.which("wmctrl"):
                used_tool = "wmctrl"
                for pat in patterns:
                    subprocess.run(["wmctrl", "-a", pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif shutil.which("xdotool"):
                used_tool = "xdotool"
                for pat in patterns:
                    # search returns window ids; activate first if any
                    res = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", pat], capture_output=True, text=True)
                    if res.returncode == 0 and res.stdout.strip():
                        wid = res.stdout.strip().splitlines()[0]
                        subprocess.run(["xdotool", "windowactivate", wid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        break
            if used_tool:
                return
        except Exception:
            pass

    def bring_to_front(self) -> None:
        """Public helper so tools can explicitly nudge the window each call."""
        if self.driver is None:
            return
        self._ensure_window_visible(self.driver)

    def shutdown(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
                self.backend = None


browser_manager = BrowserManager()
atexit.register(browser_manager.shutdown)


def wait_for_page(driver: "webdriver.Remote", timeout: int = 12) -> None:
    """Block until the browser reports the page finished loading."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def take_screenshot(driver: "webdriver.Remote", name: str) -> Optional[str]:
    try:
        filename = hashlib.md5(name.encode("utf-8")).hexdigest() + ".png"
        path = SCREENSHOT_DIR / filename
        driver.save_screenshot(str(path))
        return str(path)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------------
def clean_text(text: str) -> str:
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def extract_page_metadata(soup: BeautifulSoup, fallback_url: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "url": fallback_url,
        "title": soup.title.string.strip() if soup.title else "",
        "description": "",
        "author": "",
        "published": "",
        "updated": "",
        "site_name": "",
    }

    def grab(names: List[str]) -> str:
        for name in names:
            element = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
            if element and element.get("content"):
                return element["content"].strip()
        return ""

    meta["description"] = grab(["description", "og:description", "twitter:description"])
    meta["author"] = grab(["author", "article:author", "og:author", "dc.creator"])
    meta["published"] = grab(["article:published_time", "og:published_time", "date", "dc.date", "dc.date.issued"])
    meta["updated"] = grab(["article:modified_time", "og:updated_time", "last-modified"])
    meta["site_name"] = grab(["og:site_name", "twitter:site"])

    return meta


def build_citation(entry: Dict[str, Any]) -> Dict[str, Any]:
    citation = {
        "title": entry.get("title") or entry.get("url") or "Untitled",
        "url": entry.get("url"),
        "author": entry.get("author"),
        "published": entry.get("published"),
        "retrieved": datetime.utcnow().isoformat(),
        "summary": entry.get("snippet") or entry.get("description"),
    }
    return {k: v for k, v in citation.items() if v}


def extract_links(soup: BeautifulSoup, base_url: str, limit: int = 120) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for link in soup.find_all("a", href=True):
        href = link.get("href")
        text = clean_text(link.get_text() or "")
        if not href or not text:
            continue
        absolute = urljoin(base_url, href)
        links.append({"text": text, "href": absolute})
        if len(links) >= limit:
            break
    return links


def fallback_duckduckgo_html(query: str, num_results: int) -> List[Dict[str, str]]:
    url = "https://html.duckduckgo.com/html/"
    response = requests.get(url, params={"q": query}, headers=DEFAULT_HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    results: List[Dict[str, str]] = []
    for element in soup.select(".result"):
        if len(results) >= num_results:
            break
        title_element = element.select_one(".result__title")
        snippet_element = element.select_one(".result__snippet")
        link_element = element.select_one(".result__url")

        title = clean_text(title_element.get_text()) if title_element else "Untitled result"
        snippet = clean_text(snippet_element.get_text()) if snippet_element else ""

        url_element = element.select_one('.result__title a')
        target_url = ""
        if url_element and url_element.has_attr("href"):
            href = url_element["href"]
            if "/redirect/" in href:
                parsed = urlparse(href)
                params = parse_qs(parsed.query)
                target_url = params.get("uddg", [""])[0]
            else:
                target_url = href

        if not target_url and link_element:
            target_url = link_element.get_text()

        if target_url:
            results.append({"title": title, "snippet": snippet, "url": target_url})
    return results


# ----------------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------------
@tool
def search_web(query: str, num_results: int = 6) -> List[Dict[str, str]]:
    """Perform a web search, showing a visible browser window when possible."""
    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty.")

    num_results = max(1, min(num_results, 10))
    cache_key = f"search::{query}::{num_results}"
    cached = data_cache.load(cache_key)
    if cached:
        cached_payload = dict(cached)
        return _with_telemetry(cached_payload, cache_hit=True)

    results: List[Dict[str, str]] = []
    screenshot_path: Optional[str] = None
    browser_error: Optional[str] = None
    browser_used = False

    if not SELENIUM_AVAILABLE:
        browser_error = "Selenium not available; install 'selenium' and 'webdriver-manager' for a live browser."
    else:
        try:
            driver = browser_manager.get_driver()
            browser_manager.bring_to_front()
            driver.get("https://duckduckgo.com/")
            wait_for_page(driver)

            search_box = WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.ID, "search_form_input_homepage"))
            )
            search_box.clear()
            search_box.send_keys(query)
            search_box.send_keys(Keys.RETURN)

            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.result, .results--main"))
            )
            time.sleep(1.0)

            entries = driver.find_elements(By.CSS_SELECTOR, "article.result")
            if not entries:
                entries = driver.find_elements(By.CSS_SELECTOR, ".result__body")

            for element in entries:
                if len(results) >= num_results:
                    break
                try:
                    title_element = element.find_element(By.CSS_SELECTOR, "h2, h3, .result__title")
                    link_element = element.find_element(By.CSS_SELECTOR, "a.result__a, a[href^='http']")
                except Exception:
                    continue

                snippet = ""
                try:
                    snippet_element = element.find_element(By.CSS_SELECTOR, ".result__snippet, .snippet")
                    snippet = clean_text(snippet_element.text)
                except Exception:
                    pass

                title = clean_text(title_element.text)
                url = link_element.get_attribute("href") or ""
                if url:
                    results.append({
                        "title": title or url,
                        "snippet": snippet,
                        "url": url,
                    })

            screenshot_path = take_screenshot(driver, f"search::{query}")
            browser_used = True
        except Exception as exc:
            results = []
            browser_error = str(exc)
            print(f"[web_researcher] Browser search fallback: {browser_error}")

    if not results:
        results = fallback_duckduckgo_html(query, num_results)

    sources = []
    for rank, entry in enumerate(results, start=1):
        entry["rank"] = rank
        entry["retrieved_at"] = datetime.utcnow().isoformat()
        sources.append(build_citation({
            "title": entry.get("title"),
            "url": entry.get("url"),
            "snippet": entry.get("snippet"),
        }))

    payload = {
        "query": query,
        "results": results,
        "sources": sources,
        "metadata": {
            "screenshot": screenshot_path,
            "results": len(results),
            "browser": {
                "backend": browser_manager.backend,
                "used": browser_used,
                "error": browser_error,
            },
        },
    }
    data_cache.store(cache_key, payload, metadata={"results": len(results)})
    return _with_telemetry(payload, cache_hit=False)


@tool
def fetch_webpage_content(url: str, extract_text_only: bool = True) -> Dict[str, Any]:
    """Fetch the contents of a webpage, preferring the live browser view."""
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty.")

    cache_key = f"page::{url}::{extract_text_only}"
    cached = data_cache.load(cache_key)
    if cached:
        cached_payload = dict(cached)
        return _with_telemetry(cached_payload, cache_hit=True)

    title = ""
    content = ""
    links: List[Dict[str, str]] = []
    screenshot_path: Optional[str] = None
    browser_error: Optional[str] = None
    browser_used = False

    if not SELENIUM_AVAILABLE:
        browser_error = "Selenium not available; install 'selenium' and 'webdriver-manager' for a live browser."
    else:
        try:
            driver = browser_manager.get_driver()
            browser_manager.bring_to_front()
            driver.get(url)
            wait_for_page(driver, timeout=20)
            time.sleep(1.2)
            page_source = driver.page_source
            title = driver.title
            screenshot_path = take_screenshot(driver, f"page::{url}")

            soup = BeautifulSoup(page_source, "html.parser")
            meta = extract_page_metadata(soup, url)
            if extract_text_only:
                for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    tag.decompose()
                content = clean_text(soup.get_text(separator="\n"))
            else:
                content = str(soup)
            links = extract_links(soup, url)
            browser_used = True
        except Exception as exc:
            content = ""
            meta = {
                "url": url,
                "title": title,
            }
            browser_error = str(exc)
            print(f"[web_researcher] Browser page fallback: {browser_error}")

    if not content:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.title.string.strip() if soup.title else ""
        meta = extract_page_metadata(soup, url)
        if extract_text_only:
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                tag.decompose()
            content = clean_text(soup.get_text(separator="\n"))
        else:
            content = soup.prettify()
        links = extract_links(soup, url)

    citation = build_citation({
        "title": title or meta.get("title"),
        "url": url,
        "author": meta.get("author"),
        "published": meta.get("published"),
        "description": meta.get("description"),
    })

    result = {
        "title": title or url,
        "content": content[:60000],
        "links": links,
        "metadata": {
            "url": url,
            "timestamp": datetime.utcnow().isoformat(),
            "word_count": len(content.split()),
            "screenshot": screenshot_path,
            "page_meta": meta,
            "browser": {
                "backend": browser_manager.backend,
                "used": browser_used,
                "error": browser_error,
            },
        }
    }
    if citation:
        result["citation"] = citation
    data_cache.store(cache_key, result)
    return _with_telemetry(result, cache_hit=False)


@tool
def search_arxiv(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search arXiv for academic papers matching the query."""
    query = query.strip()
    if not query:
        raise ValueError("Query cannot be empty.")

    max_results = max(1, min(max_results, 20))
    if not ARXIV_AVAILABLE:
        raise RuntimeError("The 'arxiv' package is not installed. Run 'pip install arxiv' to enable this tool.")
    cache_key = f"arxiv::{query}::{max_results}"
    cached = data_cache.load(cache_key)
    if cached:
        cached_payload = dict(cached)
        return _with_telemetry(cached_payload, cache_hit=True)

    search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)
    results: List[Dict[str, Any]] = []
    for paper in search.results():
        results.append({
            "title": paper.title,
            "summary": paper.summary,
            "published": paper.published.isoformat() if paper.published else None,
            "updated": paper.updated.isoformat() if paper.updated else None,
            "primary_category": paper.primary_category,
            "pdf_url": paper.pdf_url,
            "entry_id": paper.entry_id,
        })

    citations = []
    for paper in results:
        citations.append({
            "title": paper.get("title"),
            "url": paper.get("pdf_url") or paper.get("entry_id"),
            "published": paper.get("published"),
            "summary": (paper.get("summary") or "")[:280],
        })

    payload = {
        "query": query,
        "results": results,
        "citations": citations,
        "metadata": {"results": len(results)},
    }
    data_cache.store(cache_key, payload, metadata={"results": len(results)})
    return _with_telemetry(payload, cache_hit=False)


@tool
def download_pdf(url: str, extract_text: bool = True) -> Dict[str, Any]:
    """Download a PDF and optionally extract its text content."""
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty.")

    pdf_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    pdf_path = PDF_CACHE_DIR / f"{pdf_hash}.pdf"
    cache_key = f"pdf::{pdf_hash}::{extract_text}"
    cached = data_cache.load(cache_key)
    if cached:
        cached_payload = dict(cached)
        return _with_telemetry(cached_payload, cache_hit=True)

    if not pdf_path.exists():
        with requests.get(url, headers=DEFAULT_HEADERS, stream=True, timeout=40) as response:
            response.raise_for_status()
            with open(pdf_path, "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file_handle.write(chunk)

    result: Dict[str, Any] = {
        "status": "success",
        "filename": str(pdf_path),
        "url": url,
    }

    if extract_text:
        try:
            import PyPDF2

            with open(pdf_path, "rb") as file_handle:
                reader = PyPDF2.PdfReader(file_handle)
                text = []
                for page in reader.pages:
                    try:
                        text.append(page.extract_text() or "")
                    except Exception:
                        continue
            content = "\n\n".join(segment for segment in text if segment)
            result["text_content"] = content[:120000]
            result["page_count"] = len(reader.pages)
        except ImportError:
            result["error"] = "PyPDF2 is not installed; run 'pip install PyPDF2'."
        except Exception as exc:
            result["error"] = f"Error extracting text: {exc}"

    data_cache.store(cache_key, result)
    return _with_telemetry(result, cache_hit=False)


@tool
def summarize_text(text: str, max_length: int = 900) -> str:
    """Summarise long text using the configured LLM backend."""
    text = text.strip()
    if not text:
        payload = {
            "summary": "",
            "metadata": {"warning": "Empty text provided."},
        }
        return _with_telemetry(payload, cache_hit=None, success=True)

    cache_key = f"summary::{hashlib.md5(text.encode('utf-8')).hexdigest()}::{max_length}"
    cached = data_cache.load(cache_key)
    if cached:
        cached_payload = dict(cached)
        return _with_telemetry(cached_payload, cache_hit=True)

    max_length = max(100, min(max_length, 2000))
    prompt = (
        "You are a meticulous research assistant. Summarise the given text in no more "
        f"than {max_length} characters, focusing on key facts, figures, and takeaways.\n\n"
        "Text:\n" + text
    )

    summary = get_inference(prompt)
    payload = {
        "summary": summary,
        "metadata": {
            "max_length": max_length,
            "characters": len(summary),
        },
    }
    data_cache.store(cache_key, payload)
    return _with_telemetry(payload, cache_hit=False)


def _slugify(value: str) -> str:
    value = value.strip().lower()
    safe = [c if c.isalnum() else "-" for c in value]
    slug = "".join(safe)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    return slug or "research-notes"


@tool
def persist_research(
    session_title: str,
    timeline: str,
    knowledge_digest: str,
    citations: Optional[List[str]] = None,
    destination: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist the current research timeline and knowledge digest to a Markdown report."""

    session_title = session_title.strip() or "Untitled Research Session"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(session_title)
    report_path = Path(destination).expanduser() if destination else REPORT_DIR / f"{timestamp}-{slug}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    citation_block = ""
    if citations:
        formatted = "\n".join(f"- {item}" for item in citations if item)
        if formatted.strip():
            citation_block = f"\n\n## Citations\n{formatted}\n"

    content = (
        f"# {session_title}\n\n"
        f"_Exported: {datetime.utcnow().isoformat()}Z_\n\n"
        f"## Timeline\n{timeline.strip()}\n\n"
        f"## Knowledge Digest\n{knowledge_digest.strip()}\n"
        f"{citation_block}"
    )
    report_path.write_text(content, encoding="utf-8")

    payload = {
        "status": "saved",
        "path": str(report_path),
        "bytes": len(content.encode("utf-8")),
    }
    return _with_telemetry(payload, cache_hit=None)


__all__ = [
    "search_web",
    "fetch_webpage_content",
    "search_arxiv",
    "download_pdf",
    "summarize_text",
    "persist_research",
]
