import logging
import re
import secrets
import time

from django.conf import settings

logger = logging.getLogger("fetchuccini.requests")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


class RequestObservabilityMiddleware:
    """Attach request IDs/timing and emit compact slow/error request logs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = (request.headers.get("X-Request-ID") or "").strip()
        request_id = incoming if _REQUEST_ID_RE.fullmatch(incoming) else secrets.token_hex(8)
        request.fetchuccini_request_id = request_id
        started = time.perf_counter()

        response = self.get_response(request)

        elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
        response["X-Request-ID"] = request_id
        response["X-Fetchuccini-Version"] = str(getattr(settings, "FETCHUCCINI_VERSION", "unknown"))
        response["Server-Timing"] = f"app;dur={elapsed_ms}"

        # Avoid noisy logs for every asset/health request. Searches that are
        # slow or unsuccessful remain easy to correlate through request_id.
        if response.status_code >= 400 or (request.path.startswith("/api/") and elapsed_ms >= 1500):
            logger.info(
                "request id=%s method=%s path=%s status=%s elapsed_ms=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
            )
        return response


class ResponseSecurityHeadersMiddleware:
    """Small defense-in-depth header layer for the public Fetchuccini UI/API."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _set_default(response, name: str, value: str) -> None:
        if not response.has_header(name):
            response[name] = value

    def __call__(self, request):
        response = self.get_response(request)
        self._set_default(response, "Referrer-Policy", "strict-origin-when-cross-origin")
        self._set_default(
            response,
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        self._set_default(response, "X-Permitted-Cross-Domain-Policies", "none")
        self._set_default(
            response,
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'",
        )
        return response
