"""Helpers to keep sensitive data out of logs.

Used by `RequestLoggingMiddleware` (request/response body + header logging)
and by `resources.services` (logging the signed file-access token/URL sent
to FastAPI). Kept as a single shared module so "what counts as sensitive"
is defined in exactly one place.
"""

import re

# Header names that must never be logged, even partially. Matched
# case-insensitively. Covers auth headers and any custom secret headers we
# might add later.
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrftoken",
}

# JSON body field names that must be masked wherever they appear (top level
# or nested), matched case-insensitively. Covers auth payloads (login,
# register, refresh/access tokens) and generic "password"/"token" fields
# any future endpoint might add.
SENSITIVE_BODY_FIELDS = {
    "password",
    "password1",
    "password2",
    "old_password",
    "new_password",
    "token",
    "access",
    "refresh",
    "authorization",
}

MASK = "***"


def mask_headers(headers: dict) -> dict:
    """Return a copy of `headers` with sensitive values replaced by a mask."""
    return {
        key: (MASK if key.lower() in SENSITIVE_HEADER_NAMES else value)
        for key, value in headers.items()
    }


def mask_body(data):
    """Recursively mask sensitive fields in a parsed JSON-like structure.

    Non-dict/list values (or anything that isn't JSON-shaped) are returned
    unchanged — callers should only pass already-parsed JSON bodies, never
    raw file bytes.
    """
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_BODY_FIELDS:
                masked[key] = MASK
            else:
                masked[key] = mask_body(value)
        return masked
    if isinstance(data, list):
        return [mask_body(item) for item in data]
    return data


_TOKEN_QUERY_PARAM_RE = re.compile(r"([?&]token=)[^&\s]+", re.IGNORECASE)


def mask_url_token(url: str) -> str:
    """Mask a `?token=...`/`&token=...` query param value in a URL.

    Used for the signed internal file-access URL Django builds for FastAPI
    (see `resources.tokens`) — the token itself must never appear in full
    in logs, but the rest of the URL (host/path) is useful for debugging.
    """
    return _TOKEN_QUERY_PARAM_RE.sub(rf"\1{MASK}", url)
