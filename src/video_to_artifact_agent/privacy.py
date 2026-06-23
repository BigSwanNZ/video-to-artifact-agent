from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def redact_url(value: str) -> str:
    """Remove query and fragment material from URLs before logging."""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        return value
    suffix = "?<redacted>" if parsed.query or parsed.fragment else ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")) + suffix


def redact_text(text: str) -> str:
    return _URL_RE.sub(lambda match: redact_url(match.group(0)), text)
