from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, Iterable, List, Optional


def _truncate(value: Any, max_chars: int = 280) -> str:
    """Utility to turn arbitrary values into a trimmed string."""
    text = "" if value is None else str(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


@dataclass
class TimelineEntry:
    """Structured record of an event the agent should remember."""

    kind: str
    detail: str
    step: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def format(self) -> str:
        parts: List[str] = []
        if self.step is not None:
            parts.append(f"Step {self.step}")
        ts = self.timestamp.strftime("%H:%M:%S")
        parts.append(ts)
        header = " | ".join(parts) if parts else ts

        suffix = ""
        if self.metadata:
            meta_bits = []
            for key, value in self.metadata.items():
                if value is None:
                    continue
                meta_bits.append(f"{key}={_truncate(value, 60)}")
            if meta_bits:
                suffix = " (" + ", ".join(meta_bits) + ")"

        return f"{header} · {self.kind}: {_truncate(self.detail, 240)}{suffix}"


class Memory:
    """Structured agent memory that balances short- and long-horizon needs."""

    def __init__(
        self,
        history_length: int = 10,
        timeline_length: int = 50,
    ) -> None:
        self.summaries: Deque[str] = deque(maxlen=history_length)
        self.state: str = ""
        self.facts_and_results: Dict[str, Any] = {}
        self.action_results: Dict[str, Any] = {}
        self.timeline: Deque[TimelineEntry] = deque(maxlen=timeline_length)
        self.long_term_notes: Deque[str] = deque(maxlen=max(history_length * 2, 20))
        self.tool_stats: Dict[str, Counter] = {}
        self.tool_events: Deque[Dict[str, Any]] = deque(maxlen=200)

    # ------------------------------------------------------------------
    # High level snapshots
    # ------------------------------------------------------------------
    def add_summary(self, sentence: str, *, step: Optional[int] = None) -> None:
        sentence = (sentence or "").strip()
        if sentence:
            self.summaries.append(sentence)
            self.add_structured_entry("Summary", sentence, step=step)

    def get_summaries(self) -> str:
        if not self.summaries:
            return ""
        lines = []
        for idx, summary in enumerate(reversed(self.summaries), 1):
            prefix = "Previous step" if idx == 1 else f"Step-{idx}"
            lines.append(f"{prefix}: {summary}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # State tracking
    # ------------------------------------------------------------------
    def set_state(self, text: str, *, step: Optional[int] = None) -> None:
        self.state = (text or "").strip()
        if self.state:
            self.add_structured_entry("State", self.state, step=step)

    def get_state(self) -> str:
        return self.state

    # ------------------------------------------------------------------
    # Tool action bookkeeping
    # ------------------------------------------------------------------
    def set_action_results(self, results: Dict[str, Any]) -> None:
        if not isinstance(results, dict):
            raise ValueError("Action results must be a dictionary.")
        self.action_results = results
        if results:
            self.add_structured_entry(
                "Tool Results",
                "; ".join(f"{k}={_truncate(v)}" for k, v in results.items()),
                metadata={"result_count": len(results)}
            )

    def get_action_results(self) -> str:
        if not self.action_results:
            return "No action results available."
        lines = [f"{key}: {value}" for key, value in self.action_results.items()]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Persistent facts and key-value store
    # ------------------------------------------------------------------
    def store_result(self, key: str, value: Any) -> None:
        key = key.strip()
        if not key:
            raise ValueError("Key must be a non-empty string.")
        self.facts_and_results[key] = value
        self.add_structured_entry(
            "StoreResult",
            f"Stored key '{key}'",
            metadata={"key": key, "size": len(str(value))}
        )

    def get_stored_result(self, key: str) -> Any:
        return self.facts_and_results.get(key)

    def clear_stored_result(self, key: str) -> None:
        if key in self.facts_and_results:
            del self.facts_and_results[key]
            self.add_structured_entry("DeleteResult", f"Deleted key '{key}'", metadata={"key": key})

    def get_stored_results_keys(self) -> List[str]:
        return list(self.facts_and_results.keys())

    # ------------------------------------------------------------------
    # Timeline helpers for long-horizon recall
    # ------------------------------------------------------------------
    def add_structured_entry(
        self,
        kind: str,
        detail: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        step: Optional[int] = None
    ) -> None:
        entry = TimelineEntry(kind=kind, detail=detail, metadata=metadata or {}, step=step)
        self.timeline.append(entry)

    def remember_step(
        self,
        step: int,
        *,
        thought: str = "",
        summary: str = "",
        state: str = "",
        actions: Optional[Iterable[Any]] = None,
        results: Optional[Dict[str, Any]] = None,
    ) -> None:
        if thought:
            self.add_structured_entry("Thought", thought, step=step)
        if summary:
            self.add_structured_entry("Summary", summary, step=step)
        if state:
            self.add_structured_entry("State", state, step=step)
        if actions:
            actions_list = list(actions)
            self.add_structured_entry(
                "Actions",
                "; ".join(_truncate(action, 180) for action in actions_list),
                step=step,
                metadata={"count": len(actions_list)}
            )
        if results:
            preview = "; ".join(f"{k}={_truncate(v)}" for k, v in results.items())
            self.add_structured_entry(
                "Results",
                preview,
                step=step,
                metadata={"result_count": len(results)}
            )

    def render_recent_events(self, limit: int = 5) -> str:
        if not self.timeline:
            return "No timeline entries yet."
        entries = list(self.timeline)[-limit:]
        return "\n".join(entry.format() for entry in entries)

    def add_long_term_note(self, note: str) -> None:
        note = (note or "").strip()
        if not note:
            return
        self.long_term_notes.appendleft(note)
        self.add_structured_entry("Note", note)

    def render_long_term_notes(self, limit: int = 5) -> str:
        if not self.long_term_notes:
            return "No long-term notes yet."
        return "\n".join(_truncate(note, 240) for note in list(self.long_term_notes)[:limit])

    # ------------------------------------------------------------------
    # Aggregated snapshot utilities
    # ------------------------------------------------------------------
    def get_all(self) -> str:
        sections = [
            "Summaries:\n" + (self.get_summaries() or "None"),
            "State:\n" + (self.get_state() or "None"),
            "Stored Results:\n" + (", ".join(self.get_stored_results_keys()) or "None"),
            "Recent Timeline:\n" + self.render_recent_events(limit=10),
            "Long-Term Notes:\n" + self.render_long_term_notes(limit=10),
            "Knowledge Digest:\n" + self.render_knowledge_digest(),
            "Tool Telemetry:\n" + self.render_tool_metrics(),
        ]
        return "\n\n".join(sections)

    def snapshot_for_prompt(self) -> Dict[str, str]:
        """Return reusable blocks consumed by prompting templates."""
        return {
            "summaries_block": self.get_summaries() or "None yet.",
            "state_block": self.get_state() or "None yet.",
            "stored_results_keys": ", ".join(self.get_stored_results_keys()) or "No results stored yet.",
            "recent_timeline_block": self.render_recent_events(),
            "long_term_notes_block": self.render_long_term_notes(),
            "knowledge_digest_block": self.render_knowledge_digest(),
            "telemetry_block": self.render_tool_metrics(),
        }

    # ------------------------------------------------------------------
    # Tool telemetry helpers
    # ------------------------------------------------------------------
    def record_tool_event(
        self,
        tool_name: str,
        *,
        success: bool,
        cache_hit: bool | None = None,
        info: Optional[Dict[str, Any]] = None,
    ) -> None:
        stats = self.tool_stats.setdefault(tool_name, Counter())
        stats["calls"] += 1
        stats["success" if success else "failure"] += 1
        if cache_hit:
            stats["cache_hits"] += 1
        if info and info.get("error"):
            stats["errors"] += 1

        event = {
            "tool": tool_name,
            "success": success,
            "cache_hit": cache_hit,
            "info": info or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.tool_events.append(event)
        status = "success" if success else "failure"
        detail = f"{tool_name} -> {status}"
        if cache_hit is True:
            detail += " (cache hit)"
        elif cache_hit is False:
            detail += " (cache miss)"
        self.add_structured_entry("ToolEvent", detail, metadata={"tool": tool_name, "status": status})

    def render_tool_metrics(self, limit: int = 5) -> str:
        if not self.tool_stats:
            return "No tool telemetry yet."

        lines: List[str] = []
        for tool_name, stats in sorted(self.tool_stats.items()):
            calls = stats.get("calls", 0)
            if not calls:
                continue
            success = stats.get("success", 0)
            failure = stats.get("failure", 0)
            cache_hits = stats.get("cache_hits", 0)
            success_rate = (success / calls) * 100 if calls else 0
            cache_rate = (cache_hits / calls) * 100 if calls else 0
            lines.append(
                f"{tool_name}: {calls} calls | {success_rate:.0f}% success | {cache_rate:.0f}% cache hit"
            )

        if not lines:
            return "Tool telemetry collected but empty."

        recent_events = list(self.tool_events)[-limit:]
        if recent_events:
            lines.append("Recent events:")
            for event in recent_events:
                status = "✅" if event["success"] else "⚠️"
                cache_note = " (cache)" if event.get("cache_hit") else ""
                lines.append(f"  {status} {event['tool']}{cache_note} @ {event['timestamp']}")

        return "\n".join(lines)

    def startup_report(self) -> str:
        stored_count = len(self.get_stored_results_keys())
        notes_count = len(self.long_term_notes)
        timeline_count = len(self.timeline)
        telemetry = "No tool calls yet."
        if self.tool_stats:
            telemetry = ", ".join(
                f"{tool}: {stats.get('calls', 0)} calls" for tool, stats in self.tool_stats.items()
            )
        return (
            f"Stored results: {stored_count}; long-term notes: {notes_count}; "
            f"timeline entries: {timeline_count}; telemetry: {telemetry}"
        )

    # ------------------------------------------------------------------
    # Overridable knowledge summary hook
    # ------------------------------------------------------------------
    def render_knowledge_digest(self, limit: int = 5) -> str:
        return "Knowledge memory not enabled."


if __name__ == "__main__":
    memory = Memory(history_length=5)
    memory.add_summary("First summary")
    memory.add_summary("Second summary")
    memory.set_state("Current state of the agent")
    memory.store_result("example", {"value": 42})
    memory.add_long_term_note("Remember to review the quarterly report.")
    memory.remember_step(
        1,
        thought="We should gather requirements.",
        summary="Outlined the initial question.",
        actions=["search_web"],
        results={"search_web": "Found 3 promising sources."},
    )
    print(memory.get_all())
