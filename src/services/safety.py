"""Input safety: prompt-injection detection and PII redaction.

Runs BEFORE any LLM call and before any database write, mirroring the
capstone-3 safety posture.
"""
from __future__ import annotations

import re

# 26 prompt-injection / jailbreak patterns (curated, same family as agent 3)
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior)\s+instructions",
    r"override\s+(your\s+)?(system|prior)\s+(prompt|instructions)",
    r"system\s+prompt",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(if\s+you\s+were\s+)?(a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"roleplay\s+as",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"developer\s+mode",
    r"unrestricted\s+mode",
    r"bypass\s+(your\s+)?(safety|filter|guardrail)",
    r"disable\s+(your\s+)?(safety|filter|guardrail)",
    r"reveal\s+(your\s+)?(system|hidden)\s+(prompt|instructions)",
    r"print\s+(your\s+)?(system|hidden)\s+(prompt|instructions)",
    r"output\s+(your\s+)?(system|hidden)\s+(prompt|instructions)",
    r"exfiltrate",
    r"base64\s+decode",
    r"exec\s*\(",
    r"eval\s*\(",
    r"<script",
    r"drop\s+table",
    r";\s*--",
    r"union\s+select",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("PHONE", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]


def detect_injection(text: str) -> tuple[bool, list[str]]:
    """Return (is_injection, matched_pattern_names)."""
    matched = [p for p, rx in zip(_INJECTION_PATTERNS, _COMPILED) if rx.search(text)]
    return bool(matched), matched


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, redaction_kinds_applied)."""
    kinds: list[str] = []
    for kind, rx in _PII_PATTERNS:
        if rx.search(text):
            kinds.append(kind)
            text = rx.sub(f"[REDACTED_{kind}]", text)
    return text, kinds
