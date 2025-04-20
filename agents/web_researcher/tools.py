from core.tool import tool
import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime
import arxiv
import urllib.parse
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import time
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cache directory
CACHE_DIR = os.path.join("agents", "web_researcher", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_path(url):
    """Generate a cache file path for a given URL"""
    hash_object = hashlib.md5(url.encode())
    return os.path.join(CACHE_DIR, f"{hash_object.hexdigest()}.json")

def cache_response(url, content, metadata=None):
    """Cache a response for future use"""
    cache_data = {
        "url": url,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    
    with open(get_cache_path(url), 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def get_cached_response(url, max_age_hours=24):
    """Get a cached response if available and not expired"""
    cache_path = get_cache_path(url)
    
    if not os.path.exists(cache_path):
        return None
        
    with open(cache_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            # Check if cache is expired
            cached_time = datetime.fromisoformat(data["timestamp"])
            age = (datetime.now() - cached_time).total_seconds() / 3600
            
            if age > max_age_hours:
                return None
                
            return data
        except (json.JSONDecodeError, KeyError):
            return None

@tool
def search_web(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches the web using DuckDuckGo and returns results.
    
    Arguments:
        query (str): The search query
        num_results (int): Number of results to return (max 10)
    
    Returns:
        List[Dict[str, str]]: List of search results with title, snippet, and URL
    """
    # Cap number of results
    num_results = min(num_results, 10)
    
    # Check cache first
    cache_key = f"search:{query}:{num_results}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached["content"]
    
    # Try to use selenium if available for a more robust solution
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.chrome import ChromeDriverManager
        import random
        
        browser_available = True
    except ImportError:
        browser_available = False
    
    results = []
    
    if browser_available:
        try:
            # Try Firefox first
            try:
                # Configure Firefox options
                firefox_options = FirefoxOptions()
                firefox_options.add_argument("--headless")
                firefox_options.add_argument("--width=1920")
                firefox_options.add_argument("--height=1080")
                
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
                    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
                ]
                firefox_options.set_preference("general.useragent.override", random.choice(user_agents))
                
                # Initialize the Firefox driver
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=firefox_options)
                print("Using Firefox for web search")
                
            except Exception as firefox_error:
                print(f"Firefox initialization failed: {firefox_error}. Trying Chrome instead.")
                
                # If Firefox fails, fall back to Chrome
                chrome_options = ChromeOptions()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--disable-notifications")
                chrome_options.add_argument("--disable-popup-blocking")
                
                chrome_user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36"
                ]
                chrome_options.add_argument(f"--user-agent={random.choice(chrome_user_agents)}")
                
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print("Using Chrome for web search")
            
            # Navigate to DuckDuckGo
            encoded_query = urllib.parse.quote_plus(query)
            driver.get(f"https://duckduckgo.com/?q={encoded_query}")
            time.sleep(2)  # Allow time for results to load
            
            # Wait for results to load
            try:
                # Find search result elements
                result_elements = driver.find_elements(By.CSS_SELECTOR, "article.result")
                
                # If no results found with that selector, try another common one
                if not result_elements:
                    result_elements = driver.find_elements(By.CSS_SELECTOR, ".result__body")
                
                # If still no results, try a more generic approach
                if not result_elements:
                    result_elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='https']")
                
                # Extract information from each result
                for i, element in enumerate(result_elements):
                    if i >= num_results:
                        break
                        
                    try:
                        # Try to extract structured data
                        title_element = element.find_element(By.CSS_SELECTOR, "h2, h3, .result__title")
                        link_element = element.find_element(By.CSS_SELECTOR, "a[href^='https']")
                        snippet_element = None
                        try:
                            snippet_element = element.find_element(By.CSS_SELECTOR, ".result__snippet, .snippet")
                        except:
                            pass
                        
                        title = title_element.text if title_element else "No title"
                        url = link_element.get_attribute("href") if link_element else ""
                        snippet = snippet_element.text if snippet_element else "No description available"
                        
                        # Add to results if we have at least a URL
                        if url:
                            results.append({
                                "title": title,
                                "snippet": snippet,
                                "url": url
                            })
                    except Exception as e:
                        # If structured extraction fails, try a simpler approach
                        try:
                            url = element.get_attribute("href")
                            text = element.text[:100].replace("\n", " ")
                            if url and "http" in url and len(text) > 10:
                                results.append({
                                    "title": text,
                                    "snippet": "",
                                    "url": url
                                })
                        except:
                            pass
            
            except Exception as e:
                print(f"Error extracting results: {e}")
            
            finally:
                # Take a screenshot for debugging (optional)
                screenshots_dir = os.path.join(CACHE_DIR, "screenshots")
                os.makedirs(screenshots_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshots_dir, f"{hashlib.md5(query.encode()).hexdigest()}.png")
                driver.save_screenshot(screenshot_path)
                
                # Close the driver
                driver.quit()
                
        except Exception as e:
            print(f"Browser automation failed: {e}")
            # Fall back to request-based method
            browser_available = False
    
    # If Selenium approach didn't work or isn't available, fall back to simpler method
    if not browser_available or not results:
        try:
            # Use a simple request to DuckDuckGo HTML
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            }
            
            encoded_query = urllib.parse.quote_plus(query)
            response = requests.get(
                f"https://html.duckduckgo.com/html/?q={encoded_query}", 
                headers=headers
            )
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract search results
            result_elements = soup.select('.result')
            
            for i, result in enumerate(result_elements):
                if i >= num_results:
                    break
                    
                title_element = result.select_one('.result__title')
                link_element = result.select_one('.result__url')
                snippet_element = result.select_one('.result__snippet')
                
                # Get actual URL (DuckDuckGo uses redirects)
                url_element = result.select_one('.result__title a')
                url = ""
                if url_element and 'href' in url_element.attrs:
                    href = url_element['href']
                    if '/redirect/' in href:
                        # Extract the actual URL from DuckDuckGo's redirect
                        parsed_url = urllib.parse.urlparse(href)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        if 'uddg' in query_params:
                            url = query_params['uddg'][0]
                    else:
                        url = href
                
                title = title_element.get_text(strip=True) if title_element else "No title"
                snippet = snippet_element.get_text(strip=True) if snippet_element else "No description available"
                
                if url:
                    results.append({
                        "title": title,
                        "snippet": snippet,
                        "url": url
                    })
        except Exception as e:
            print(f"HTML request failed: {e}")
            # As a last resort, create a fake result to guide the user
            results.append({
                "title": "Search error",
                "snippet": f"Unable to perform search for '{query}'. Try refining your query or using a different search term.",
                "url": f"https://www.google.com/search?q={encoded_query}"
            })
    
    # Cache the results
    cache_response(cache_key, results)
    return results

@tool
def fetch_webpage_content(url: str, extract_text_only: bool = True) -> Dict[str, Any]:
    """
    Fetches and extracts content from a webpage.
    
    Arguments:
        url (str): URL of the webpage to fetch
        extract_text_only (bool): If True, extracts only the meaningful text content
    
    Returns:
        Dict[str, Any]: Dictionary containing title, content, links, and metadata
    """
    # Check cache first
    cached = get_cached_response(url)
    if cached:
        return cached["content"]
    
    # Try to use selenium if available
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import random
        
        browser_available = True
    except ImportError:
        browser_available = False
    
    content = ""
    title = ""
    links = []
    
    if browser_available:
        try:
            # Try Firefox first
            try:
                # Configure Firefox options
                firefox_options = FirefoxOptions()
                firefox_options.add_argument("--headless")
                firefox_options.add_argument("--width=1920")
                firefox_options.add_argument("--height=1080")
                
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
                firefox_options.set_preference("general.useragent.override", user_agent)
                
                # Initialize the Firefox driver
                service = FirefoxService(GeckoDriverManager().install())
                driver = webdriver.Firefox(service=service, options=firefox_options)
                print("Using Firefox for webpage fetching")
                
            except Exception as firefox_error:
                print(f"Firefox initialization failed: {firefox_error}. Trying Chrome instead.")
                
                # If Firefox fails, fall back to Chrome
                chrome_options = ChromeOptions()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
                chrome_options.add_argument(f"--user-agent={user_agent}")
                
                service = ChromeService(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print("Using Chrome for webpage fetching")
            
            # Set page load timeout
            driver.set_page_load_timeout(15)
            
            # Navigate to the URL
            driver.get(url)
            time.sleep(2)  # Allow time for JS to execute
            
            # Get the page source
            page_source = driver.page_source
            
            # Extract the title
            title = driver.title
            
            # Take a screenshot for debugging (optional)
            screenshots_dir = os.path.join(CACHE_DIR, "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            url_hash = hashlib.md5(url.encode()).hexdigest()
            screenshot_path = os.path.join(screenshots_dir, f"{url_hash}.png")
            driver.save_screenshot(screenshot_path)
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract links
            for link_element in driver.find_elements(By.TAG_NAME, "a"):
                try:
                    href = link_element.get_attribute("href")
                    text = link_element.text.strip()
                    if href and text:
                        links.append({"text": text, "href": href})
                except:
                    pass
            
            # Close the driver
            driver.quit()
            
            # Now process with BeautifulSoup
            if extract_text_only:
                # Remove script and style elements
                for script in soup(["script", "style", "header", "footer", "nav"]):
                    script.extract()
                    
                # Get text and clean it up
                text = soup.get_text(separator='\n')
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = '\n'.join(chunk for chunk in chunks if chunk)
            else:
                content = page_source
                
        except Exception as e:
            print(f"Browser automation failed: {e}")
            browser_available = False
    
    # If Selenium approach didn't work or isn't available, fall back to requests
    if not browser_available or not content:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get title
            title = soup.title.string if soup.title else "No title found"
            
            # Extract content based on mode
            if extract_text_only:
                # Remove script and style elements
                for script in soup(["script", "style", "header", "footer", "nav"]):
                    script.extract()
                    
                # Get text and clean it up
                text = soup.get_text(separator='\n')
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = '\n'.join(chunk for chunk in chunks if chunk)
            else:
                content = str(soup)
                
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Convert relative URLs to absolute
                if not bool(urlparse(href).netloc):
                    href = urljoin(url, href)
                link_text = link.get_text().strip()
                if href and link_text:
                    links.append({"text": link_text, "href": href})
                    
        except Exception as e:
            error_result = {
                "title": "Error fetching webpage",
                "content": f"Failed to fetch or parse webpage: {str(e)}",
                "links": [],
                "metadata": {"url": url, "error": str(e)}
            }
            return error_result
    
    # Basic metadata
    metadata = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "word_count": len(content.split()) if content else 0
    }
    
    result = {
        "title": title,
        "content": content[:50000] if len(content) > 50000 else content,  # Limit content size
        "links": links[:100] if len(links) > 100 else links,  # Limit number of links
        "metadata": metadata
    }
    
    # Cache the result
    cache_response(url, result)
    return result

@tool
def fetch_webpage_content(url: str, extract_text_only: bool = True) -> Dict[str, Any]:
    """
    Fetches and extracts content from a webpage.
    
    Arguments:
        url (str): URL of the webpage to fetch
        extract_text_only (bool): If True, extracts only the meaningful text content
    
    Returns:
        Dict[str, Any]: Dictionary containing title, content, links, and metadata
    """
    # Check cache first
    cached = get_cached_response(url)
    if cached:
        return cached["content"]
    
    # If no cache, fetch the webpage
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get title
        title = soup.title.string if soup.title else "No title found"
        
        # Extract content based on mode
        if extract_text_only:
            # Remove script and style elements
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.extract()
                
            # Get text and clean it up
            text = soup.get_text(separator='\n')
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)
        else:
            content = str(soup)
            
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Convert relative URLs to absolute
            if not bool(urlparse(href).netloc):
                href = urljoin(url, href)
            link_text = link.get_text().strip()
            if href and link_text:
                links.append({"text": link_text, "href": href})
        
        # Basic metadata
        metadata = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "content_type": response.headers.get('Content-Type', ''),
            "word_count": len(content.split()) if content else 0
        }
        
        result = {
            "title": title,
            "content": content[:50000] if len(content) > 50000 else content,  # Limit content size
            "links": links[:100] if len(links) > 100 else links,  # Limit number of links
            "metadata": metadata
        }
        
        # Cache the result
        cache_response(url, result)
        return result
        
    except Exception as e:
        error_result = {
            "title": "Error fetching webpage",
            "content": f"Failed to fetch or parse webpage: {str(e)}",
            "links": [],
            "metadata": {"url": url, "error": str(e)}
        }
        return error_result

@tool
def search_arxiv(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Searches arXiv.org for scientific papers.
    
    Arguments:
        query (str): Search query for articles
        max_results (int): Maximum number of results to return (max 20)
    
    Returns:
        List[Dict[str, Any]]: List of paper details
    """
    # Cap number of results
    max_results = min(max_results, 20)
    
    # Check cache
    cache_key = f"arxiv:{query}:{max_results}"
    cached = get_cached_response(cache_key)
    if cached:
        return cached["content"]
    
    try:
        # Search arXiv
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for paper in search.results():
            # Extract and format paper details
            paper_info = {
                "title": paper.title,
                "summary": paper.summary[:500] + "..." if len(paper.summary) > 500 else paper.summary,
                "authors": [author.name for author in paper.authors],
                "published": paper.published.strftime("%Y-%m-%d"),
                "url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "categories": paper.categories
            }
            results.append(paper_info)
        
        # Cache results
        cache_response(cache_key, results)
        return results
        
    except Exception as e:
        return [{"error": f"arXiv search error: {str(e)}"}]

@tool
def download_pdf(url: str, extract_text: bool = True) -> Dict[str, Any]:
    """
    Downloads a PDF and optionally extracts its text content.
    
    Arguments:
        url (str): URL of the PDF to download
        extract_text (bool): Whether to extract text from the PDF
    
    Returns:
        Dict[str, Any]: Dictionary with status, filename, and text content if extracted
    """
    # Check cache
    cached = get_cached_response(url)
    if cached and "content" in cached and "text_content" in cached["content"]:
        return cached["content"]
    
    try:
        # Create directory for PDFs if it doesn't exist
        pdf_dir = os.path.join(CACHE_DIR, "pdfs")
        os.makedirs(pdf_dir, exist_ok=True)
        
        # Generate filename from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        filename = os.path.join(pdf_dir, f"{url_hash}.pdf")
        
        # Download PDF if not already cached
        if not os.path.exists(filename):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        
        result = {
            "status": "success",
            "filename": filename,
            "url": url
        }
        
        # Extract text if requested
        if extract_text:
            try:
                import PyPDF2
                
                with open(filename, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text_content = ""
                    
                    # Extract text from each page
                    for i in range(len(reader.pages)):
                        page = reader.pages[i]
                        text_content += page.extract_text() + "\n\n"
                
                # Truncate if too long
                if len(text_content) > 100000:
                    text_content = text_content[:100000] + "... [Content truncated due to length]"
                    
                result["text_content"] = text_content
                result["page_count"] = len(reader.pages)
                
            except ImportError:
                result["error"] = "PyPDF2 not installed. Cannot extract text."
            except Exception as e:
                result["error"] = f"Error extracting text: {str(e)}"
        
        # Cache the result
        cache_response(url, result)
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "url": url,
            "error": f"Failed to download PDF: {str(e)}"
        }

@tool
def summarize_text(text: str, max_length: int = 1000) -> str:
    """
    Summarizes long text using the core inference system.
    
    Arguments:
        text (str): Text to summarize
        max_length (int): Maximum length of the summary
    
    Returns:
        str: Summarized text
    """
    # Generate a unique cache key from the text
    text_hash = hashlib.md5(text.encode()).hexdigest()
    cache_key = f"summary:{text_hash}:{max_length}"
    
    # Check cache
    cached = get_cached_response(cache_key)
    if cached:
        return cached["content"]

    try:
        from core.inference import get_inference
        prompt = f"""You are a helpful assistant that summarizes text concisely.
        Please summarize the following text in no more than {max_length} characters. Focus on key points and important details:
        TEXT TO SUMMARIZE:

        {text}
        
        Your summary should be clear, accurate, and highlight the most important information from the text."""
        
        # Use the core inference function
        summary = get_inference(prompt)
        
        # Cache the summary
        cache_response(cache_key, summary)
        return summary
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"