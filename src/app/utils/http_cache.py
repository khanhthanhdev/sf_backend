"""
Lightweight HTTP caching helpers (ETag/Cache-Control) without Redis.

Use these helpers to set strong client-side caching headers so
frontends (e.g., React Query) can cache effectively.
"""

import hashlib
import json
from typing import Any

from fastapi import Request, Response


def compute_etag(payload: Any) -> str:
    """Compute a deterministic ETag for a JSON-serializable payload."""
    try:
        data = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()
    except Exception:
        # Fallback to string representation
        data = str(payload).encode()
    return 'W/"' + hashlib.md5(data).hexdigest() + '"'


def set_cache_headers(response: Response, etag: str, max_age: int = 60, private: bool = True) -> None:
    """Set Cache-Control and ETag headers on the response."""
    cache_scope = "private" if private else "public"
    response.headers["Cache-Control"] = f"{cache_scope}, max-age={max_age}"
    response.headers["ETag"] = etag


def not_modified(request: Request, etag: str) -> bool:
    """Check If-None-Match header against provided ETag."""
    inm = request.headers.get("if-none-match")
    return inm == etag if inm else False

