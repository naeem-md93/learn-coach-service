"""HTTP integration with learn-coach-logic (FastAPI) for Resource processing.

Per CONTEXT.md, Django never sends raw PDF bytes to FastAPI in the request
body. Instead it sends a single HTTP-fetchable URL that FastAPI calls back
to download the file. This module builds that URL and calls the
`POST /extract-title` contract.
"""

import logging

import requests
from django.urls import reverse

from lc_service.settings.project import LOGIC_SETTINGS

from .tokens import make_file_access_token

logger = logging.getLogger(__name__)

# Title extraction can involve OCR/vision on the first page(s) of a PDF,
# which is slow — generous timeout per CONTEXT.md's "OCR/vision is slow"
# guidance, but still bounded so an upload request can't hang forever.
EXTRACT_TITLE_TIMEOUT_SECONDS = 45


def build_internal_file_url(resource) -> str:
    """Build the URL FastAPI will fetch to download this resource's PDF.

    Uses LOGIC_SETTINGS.DJANGO_INTERNAL_BASE_URL — the address at which
    *this* Django instance is reachable from the FastAPI service/container
    (e.g. `http://django:8000` on a shared Docker network, as opposed to
    the public/browser-facing host). Falls back to localhost for local dev
    where both processes run on the host directly.

    The path carries a signed, resource-scoped token (see `tokens.py`) so
    the endpoint can stay unauthenticated (FastAPI has no user/JWT) without
    being a fully public/guessable file server.
    """
    token = make_file_access_token(resource.id)
    path = reverse("resources:resource-file", kwargs={"pk": resource.id})
    base = LOGIC_SETTINGS.DJANGO_INTERNAL_BASE_URL.rstrip("/")
    return f"{base}{path}?token={token}"


def extract_title(resource) -> str | None:
    """Call FastAPI's POST /extract-title with this resource's file URL.

    Returns the extracted title string, or None if the call failed for any
    reason (network error, timeout, non-2xx, unexpected body shape). Never
    raises — upload must still succeed with a fallback title when the logic
    service is unreachable, per CONTEXT.md's sync-but-non-blocking upload
    step.
    """
    file_url = build_internal_file_url(resource)
    endpoint = f"{LOGIC_SETTINGS.BASE_URL.rstrip('/')}/extract-title"

    try:
        response = requests.post(
            endpoint,
            json={"file_url": file_url},
            timeout=EXTRACT_TITLE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        logger.warning("extract-title returned no usable title: %r", data)
        return None
    except requests.RequestException:
        logger.exception("Failed to reach logic service for title extraction")
        return None
    except ValueError:
        logger.exception("Logic service returned non-JSON response for title extraction")
        return None
