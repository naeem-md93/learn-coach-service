"""Request/response logging middleware.

Logs one line per HTTP request/response, at a level derived from the
response status code (INFO for 2xx/3xx, WARNING for 4xx, ERROR for 5xx),
including method, path, status, duration in ms, and the authenticated
user id if any. Optionally logs a redacted request/response JSON body at
DEBUG level for local troubleshooting — never raw file uploads, never
sensitive headers/fields (see `log_safety.py`).

Deliberately a plain Django middleware (per the task's own preference)
rather than a third-party logging package — this keeps full control over
what gets logged and how secrets are masked, with no new dependency.
"""

import json
import logging
import time

from .log_safety import mask_body, mask_headers, mask_url_token

logger = logging.getLogger("lc_service.request")

# Multipart bodies (PDF uploads) are never JSON — skip body logging for
# them entirely rather than trying to parse/redact binary content.
JSON_CONTENT_TYPE_PREFIX = "application/json"

# Cap on how much of a body we ever attempt to log, to avoid flooding logs
# with huge payloads even for legitimate JSON responses (e.g. a long
# resource list).
MAX_BODY_LOG_CHARS = 2000


class RequestLoggingMiddleware:
    """Logs method/path/status/duration/user for every request.

    Placed near the top of MIDDLEWARE (right after security/whitenoise) so
    it wraps as much of the request lifecycle as possible, including
    exceptions raised deeper in the stack (Django converts those to a 500
    response before this middleware's post-`get_response` code runs).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()

        request_body_log = self._safe_request_body(request)

        response = self.get_response(request)

        duration_ms = (time.monotonic() - start) * 1000
        user = getattr(request, "user", None)
        user_id = user.id if user is not None and getattr(user, "is_authenticated", False) else None

        status_code = response.status_code
        # `?token=` is the signed, resource-scoped file-access token minted
        # for FastAPI (see resources.tokens) — mask it here too, since the
        # UI/FastAPI's actual GET request path (not just the value Django
        # constructs in services.py) also carries it verbatim.
        safe_path = mask_url_token(request.get_full_path())
        message = "%s %s -> %s (%.1fms) user=%s" % (
            request.method,
            safe_path,
            status_code,
            duration_ms,
            user_id,
        )

        level = self._level_for_status(status_code)
        logger.log(level, message)

        # Bodies are only ever logged at DEBUG, in addition to the always-on
        # INFO/WARNING/ERROR summary line above — keeps default (INFO) log
        # volume low while still allowing verbose local troubleshooting via
        # DJANGO_LOG_LEVEL=DEBUG.
        if logger.isEnabledFor(logging.DEBUG):
            if request_body_log is not None:
                logger.debug("%s %s request body: %s", request.method, request.path, request_body_log)
            response_body_log = self._safe_response_body(response)
            if response_body_log is not None:
                logger.debug("%s %s response body: %s", request.method, request.path, response_body_log)
            logger.debug(
                "%s %s request headers: %s",
                request.method,
                request.path,
                mask_headers(self._request_headers(request)),
            )

        return response

    @staticmethod
    def _level_for_status(status_code: int) -> int:
        if status_code >= 500:
            return logging.ERROR
        if status_code >= 400:
            return logging.WARNING
        return logging.INFO

    @staticmethod
    def _request_headers(request) -> dict:
        headers = {}
        for key, value in request.headers.items():
            headers[key] = value
        return headers

    def _safe_request_body(self, request):
        """Return a masked, truncated string of the request JSON body, or
        None if the body isn't JSON (e.g. multipart file upload) or can't
        be parsed."""
        content_type = request.content_type or ""
        if not content_type.startswith(JSON_CONTENT_TYPE_PREFIX):
            return None
        try:
            raw = request.body
        except Exception:
            # Body already consumed by something upstream, or unavailable.
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return self._dump_masked(data)

    def _safe_response_body(self, response):
        content_type = response.get("Content-Type", "") or ""
        if not content_type.startswith(JSON_CONTENT_TYPE_PREFIX):
            return None
        # Streaming responses (e.g. FileResponse for PDFs) must not be read
        # here — doing so would consume the stream before it reaches the
        # client. Only ever true for plain, already-rendered responses.
        if getattr(response, "streaming", False):
            return None
        try:
            content = response.content
        except Exception:
            return None
        if not content:
            return None
        try:
            data = json.loads(content.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return self._dump_masked(data)

    @staticmethod
    def _dump_masked(data) -> str:
        masked = mask_body(data)
        dumped = json.dumps(masked, ensure_ascii=False, default=str)
        if len(dumped) > MAX_BODY_LOG_CHARS:
            return dumped[:MAX_BODY_LOG_CHARS] + "...(truncated)"
        return dumped
