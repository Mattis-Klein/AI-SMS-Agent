"""Verification policy helpers for assistant factual-answer behavior."""

from __future__ import annotations

from typing import Any


class VerificationPolicy:
    DYNAMIC_FACT_TERMS = (
        "election", "officeholder", "president", "vice president", "senator", "governor", "mayor",
        "congress", "parliament", "prime minister", "won", "winner", "results", "poll", "latest",
        "breaking", "today", "this week", "this month", "this year", "current", "as of", "now",
        "schedule", "calendar", "deadline", "law", "bill", "statute", "court", "ruling",
        "price", "cost", "stock", "market", "inflation", "gdp", "population", "statistics", "stats",
    )

    LOCAL_CONTEXT_TERMS = (
        "mashbak", "this app", "this system", "my computer", "desktop", "inbox", "outbox",
        "file", "folder", "path", "cpu", "disk", "network", "uptime", "process", "email",
    )

    @staticmethod
    def is_time_or_date_query(message: str) -> bool:
        lower = str(message or "").strip().lower()
        if not lower:
            return False
        date_time_tokens = (
            "what time", "current time", "time is it", "date today", "today's date",
            "what date", "what day is", "today",
        )
        return any(token in lower for token in date_time_tokens)

    def is_time_sensitive_fact_query(self, message: str, parsed: dict[str, Any]) -> bool:
        lower = str(message or "").strip().lower()
        if not lower:
            return False

        if any(token in lower for token in self.LOCAL_CONTEXT_TERMS):
            return False

        if parsed.get("tool"):
            return False

        factual_cues = (
            "who", "what", "when", "which", "did", "won", "winner", "result", "latest",
            "current", "as of", "now", "price", "cost", "how much", "schedule", "law", "stat",
        )
        if not any(token in lower for token in factual_cues) and "?" not in lower:
            return False

        return any(token in lower for token in self.DYNAMIC_FACT_TERMS)
