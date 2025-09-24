from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from collections import Counter

from core.memory import Memory, _truncate


@dataclass
class KnowledgeItem:
    """Container for long-term knowledge entries."""

    text: str
    tags: List[str] = field(default_factory=list)
    added_at: datetime = field(default_factory=datetime.utcnow)
    step: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tags": self.tags,
            "added_at": self.added_at.isoformat(),
            "step": self.step,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "KnowledgeItem":
        added_at = datetime.fromisoformat(payload.get("added_at")) if payload.get("added_at") else datetime.utcnow()
        return cls(
            text=payload.get("text", ""),
            tags=payload.get("tags", []),
            added_at=added_at,
            step=payload.get("step"),
        )


class EnhancedMemory(Memory):
    """Extended memory with tagged knowledge base and persistence."""

    def __init__(
        self,
        history_length: int = 25,
        timeline_length: int = 80,
        max_kb_items: int = 150,
        storage_path: Optional[str | Path] = None,
    ) -> None:
        super().__init__(history_length=history_length, timeline_length=timeline_length)
        self.max_kb_items = max_kb_items
        self.storage_path = Path(storage_path) if storage_path else None
        self.knowledge_base: Dict[str, KnowledgeItem] = {}

        if self.storage_path:
            self._load_from_disk()
            self._prune_stale_knowledge()

    # ------------------------------------------------------------------
    # Knowledge base helpers
    # ------------------------------------------------------------------
    def store_knowledge(
        self,
        key: str,
        value: Any,
        *,
        tags: Optional[Iterable[str]] = None,
        step: Optional[int] = None,
    ) -> None:
        key = key.strip()
        if not key:
            raise ValueError("Knowledge key must be a non-empty string.")

        text_value = self._normalise_value(value)
        if len(text_value) > 4000:
            text_value = text_value[:4000] + " …"
        tag_list = sorted({tag.strip().lower() for tag in (tags or []) if tag})

        if len(self.knowledge_base) >= self.max_kb_items and key not in self.knowledge_base:
            self._prune_oldest()

        item = KnowledgeItem(text=text_value, tags=tag_list, step=step)
        self.knowledge_base[key] = item

        note = f"{key}: {text_value[:160]}" if text_value else key
        self.add_long_term_note(note)
        self.add_structured_entry(
            "KnowledgeStore",
            f"Stored knowledge '{key}'",
            metadata={"tags": ", ".join(tag_list) or None},
            step=step,
        )
        self._persist()
        self._prune_stale_knowledge()

    def retrieve_by_key(self, key: str) -> Optional[str]:
        item = self.knowledge_base.get(key)
        return item.text if item else None

    def retrieve_by_tags(self, tags: Iterable[str], require_all: bool = False) -> Dict[str, str]:
        query_tags = {tag.strip().lower() for tag in tags if tag}
        if not query_tags:
            return {}

        matches: Dict[str, str] = {}
        for key, item in self.knowledge_base.items():
            item_tags = set(item.tags)
            if require_all and not query_tags.issubset(item_tags):
                continue
            if not require_all and not query_tags.intersection(item_tags):
                continue
            matches[key] = item.text
        return matches

    def retrieve_related(self, query: str, limit: int = 5) -> Dict[str, str]:
        query_terms = {token.lower() for token in query.split() if token}
        if not query_terms:
            return {}

        scored: List[tuple[str, float]] = []
        for key, item in self.knowledge_base.items():
            text = item.text.lower()
            score = 0.0
            for term in query_terms:
                if term in text:
                    score += 2
                if term in key.lower():
                    score += 3
                if term in item.tags:
                    score += 1.5
            if score:
                scored.append((key, score))

        scored.sort(key=lambda kv: kv[1], reverse=True)
        return {key: self.knowledge_base[key].text for key, _ in scored[:limit]}

    def remove_knowledge(self, key: str) -> None:
        if key in self.knowledge_base:
            del self.knowledge_base[key]
            self.add_structured_entry("KnowledgeDelete", f"Removed knowledge '{key}'")
            self._persist()

    # ------------------------------------------------------------------
    # Rendering hooks
    # ------------------------------------------------------------------
    def render_knowledge_digest(self, limit: int = 8) -> str:
        if not self.knowledge_base:
            return "Knowledge base is empty."
        latest = sorted(
            self.knowledge_base.items(),
            key=lambda kv: kv[1].added_at,
            reverse=True,
        )[:limit]
        lines = []
        metrics = self._knowledge_metrics()
        lines.append(
            f"Total items: {metrics['count']} | Newest tag: {metrics['top_tag']} | Oldest entry age: {metrics['oldest_age']} days"
        )
        for key, item in latest:
            tags = f" [{', '.join(item.tags)}]" if item.tags else ""
            lines.append(f"{key}{tags}: {_truncate(item.text, 200)}")
        return "\n".join(lines)

    def snapshot_for_prompt(self) -> Dict[str, str]:
        data = super().snapshot_for_prompt()
        data["knowledge_digest_block"] = self.render_knowledge_digest()
        return data

    def add_long_term_note(self, note: str) -> None:
        super().add_long_term_note(note)
        self._persist()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _persist(self) -> None:
        if not self.storage_path:
            return
        payload = {
            "knowledge_base": {key: item.to_payload() for key, item in self.knowledge_base.items()},
            "long_term_notes": list(self.long_term_notes),
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_from_disk(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return

        kb_payload = payload.get("knowledge_base", {})
        for key, item_payload in kb_payload.items():
            try:
                self.knowledge_base[key] = KnowledgeItem.from_payload(item_payload)
            except Exception:
                continue

        notes = payload.get("long_term_notes", [])
        if notes:
            self.long_term_notes.clear()
            for note in notes:
                if isinstance(note, str):
                    self.long_term_notes.append(note)

    def _prune_oldest(self) -> None:
        if not self.knowledge_base:
            return
        oldest_key = min(self.knowledge_base.items(), key=lambda kv: kv[1].added_at)[0]
        del self.knowledge_base[oldest_key]

    def _prune_stale_knowledge(self, max_age_days: int = 30) -> None:
        if not self.knowledge_base:
            return
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        stale = [key for key, item in self.knowledge_base.items() if item.added_at < cutoff]
        for key in stale:
            del self.knowledge_base[key]
        if stale:
            self.add_structured_entry(
                "KnowledgePrune",
                f"Removed {len(stale)} stale knowledge items",
                metadata={"max_age_days": max_age_days}
            )
            self._persist()

    def _knowledge_metrics(self) -> Dict[str, Any]:
        count = len(self.knowledge_base)
        if not self.knowledge_base:
            return {"count": 0, "oldest_age": "-", "top_tag": "-"}

        oldest = min(self.knowledge_base.values(), key=lambda item: item.added_at)
        age_days = max((datetime.utcnow() - oldest.added_at).days, 0)
        tag_counter: Counter = Counter()
        for item in self.knowledge_base.values():
            tag_counter.update(item.tags)
        top_tag = tag_counter.most_common(1)[0][0] if tag_counter else "-"

        return {"count": count, "oldest_age": age_days, "top_tag": top_tag}

    @staticmethod
    def _normalise_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        try:
            return json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            return str(value)
