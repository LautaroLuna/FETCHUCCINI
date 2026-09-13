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
