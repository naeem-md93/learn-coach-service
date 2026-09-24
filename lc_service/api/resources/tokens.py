"""Signed, resource-scoped tokens for the unauthenticated file-fetch URL.

FastAPI has no user/session and can't hold a JWT, but `GET /.../file/` still
shouldn't be a fully open, guessable-URL file server (PDFs may contain
material the user doesn't want publicly reachable). Django's own
`itsdangerous`-equivalent (`django.core.signing`) gives a simple, dependency
-free way to mint a token that:

- is scoped to exactly one resource id (can't be reused for other files),
- expires after a short window (just long enough for FastAPI to fetch it
  once, right after Django calls it),
- requires no shared secret beyond Django's own SECRET_KEY, and no extra
  moving parts (no DB-stored tokens to clean up).

This is intentionally MVP-simple: no per-download revocation, no rate
limiting. Good enough because the token is never exposed to the browser or
any third party — it only ever appears in the URL Django itself constructs
and sends directly to the logic service.
"""

from django.core import signing

SALT = "resources.file-access"

# Only needs to survive one synchronous request/response cycle between
# Django and FastAPI (title extraction, page rendering, etc.), so a short
# TTL limits the blast radius if a URL ever leaked (e.g. into logs).
MAX_AGE_SECONDS = 5 * 60


def make_file_access_token(resource_id) -> str:
    return signing.dumps({"resource_id": str(resource_id)}, salt=SALT)


def verify_file_access_token(token: str, resource_id) -> bool:
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:
        return False
    return data.get("resource_id") == str(resource_id)
