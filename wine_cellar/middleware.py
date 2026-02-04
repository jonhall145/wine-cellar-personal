class CacheControlMiddleware:
    """Set Cache-Control: private, no-store on page responses.

    Prevents Cloudflare from caching authenticated HTML pages.
    Skips responses that already have Cache-Control set (e.g. by
    WhiteNoise for static files, or the media view).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.has_header("Cache-Control"):
            return response

        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return response

        response["Cache-Control"] = "private, no-store"
        return response
