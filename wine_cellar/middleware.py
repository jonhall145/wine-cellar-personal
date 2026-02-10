class CacheControlMiddleware:
    """Set Cache-Control on page responses.

    Prevents Cloudflare from caching authenticated HTML pages.
    Skips responses that already have Cache-Control set (e.g. by
    WhiteNoise for static files, or the media view).
    Allows browser caching on public pages like login.
    """

    # Paths that can be cached by the browser (public, no user data)
    CACHEABLE_PREFIXES = ("/accounts/login/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Override cache headers for cacheable public pages (e.g. login)
        if (
            request.method == "GET"
            and response.status_code == 200
            and any(request.path.startswith(p) for p in self.CACHEABLE_PREFIXES)
        ):
            del response["Expires"]
            response["Cache-Control"] = "private, max-age=86400"
            return response

        if response.has_header("Cache-Control"):
            return response

        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return response

        response["Cache-Control"] = "private, no-store"
        return response
