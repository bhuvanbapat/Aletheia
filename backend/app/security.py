"""Security utilities: secret redaction and untrusted-content labeling.

Telemetry is untrusted data. It must never:
  - be treated as instructions for the agent
  - carry secret values into LLM prompts or logs
"""
from __future__ import annotations

import re

# Patterns that indicate secret material in telemetry payloads.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?i)\b(api[-_]?key)\b")),
    ("password", re.compile(r"(?i)\b(password|passwd|pwd)\b")),
    ("token", re.compile(r"(?i)\b(access[-_]?token|auth[-_]?token|secret|bearer)\b")),
    ("private_key", re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential", re.compile(r"(?i)\b(credential|client[-_]?secret)\b")),
]

# Values that look like literal secrets.
_SECRET_VALUE_RE = re.compile(
    r"(?i)(sk-[a-z0-9]{16,}|ghp_[a-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{10,})"
)

_REDACTED = "[REDACTED]"


def redact_text(text: str) -> tuple[str, list[str]]:
    """Redact secret-looking values from free text. Returns (clean, redaction_kinds)."""
    kinds: list[str] = []
    if not text:
        return text, kinds
    clean = text
    if _SECRET_VALUE_RE.search(clean):
        clean = _SECRET_VALUE_RE.sub(_REDACTED, clean)
        kinds.append("value_pattern")
    return clean, kinds


def redact_mapping(obj: dict) -> tuple[dict, list[str]]:
    """Redact secret-looking keys/values in a mapping. Returns (clean, redaction_kinds)."""
    kinds: list[str] = []
    clean: dict = {}
    for key, value in obj.items():
        key_s = str(key)
        matched = False
        for kind, pattern in _SECRET_PATTERNS:
            if pattern.search(key_s):
                clean[key_s] = _REDACTED
                kinds.append(kind)
                matched = True
                break
        if matched:
            continue
        if isinstance(value, str):
            v, vk = redact_text(value)
            clean[key_s] = v
            kinds.extend(vk)
        elif isinstance(value, dict):
            v, vk = redact_mapping(value)
            clean[key_s] = v
            kinds.extend(vk)
        else:
            clean[key_s] = value
    return clean, kinds


INJECTION_MARKERS = [
    "ignore previous instructions",
    "disregard the above",
    "you are now",
    "system prompt",
    "shut down payments",
    "new instructions:",
]


def contains_injection_markers(text: str) -> bool:
    """Heuristic detection of prompt-injection attempts inside untrusted telemetry."""
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def quarantine_explanation(flagged: bool) -> str | None:
    """Standard explanation attached to flagged telemetry."""
    if flagged:
        return (
            "Telemetry content matched prompt-injection heuristics. It is stored and displayed "
            "as DATA only and is never passed to the AI investigator as instructions."
        )
    return None
