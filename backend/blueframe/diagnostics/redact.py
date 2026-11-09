from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_SECRET = re.compile(r"(?i)(token|authorization|password|secret|cookie|api[_-]?key|credential)")
_PRIVATE = re.compile(r"(?i)(path|transcript|subtitle|caption|media|payload|content|text|name|email|phone|user)")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET.search(str(key)) or _PRIVATE.search(str(key)):
                result[str(key)] = "[redacted]"
            elif str(key).lower().endswith("url") and isinstance(item, str):
                result[str(key)] = _safe_url(item)
            else:
                result[str(key)] = redact(item)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def _safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))
    except ValueError:
        return "[redacted]"
