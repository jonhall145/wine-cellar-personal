import hashlib

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from wine_cellar.apps.api.models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        raw_key = auth_header[len(self.keyword) + 1 :].strip()
        if len(raw_key) < 8:
            raise AuthenticationFailed("Invalid API key")

        prefix = raw_key[:8]
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()

        try:
            api_key = APIKey.objects.select_related("user", "household").get(
                prefix=prefix, hashed_key=hashed
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key")

        if not api_key.is_valid:
            if api_key.is_expired:
                raise AuthenticationFailed("API key has expired")
            raise AuthenticationFailed("API key is inactive")

        # Rate-limit last_used updates to avoid a write on every request
        now = timezone.now()
        if not api_key.last_used or (now - api_key.last_used).total_seconds() > 300:
            APIKey.objects.filter(pk=api_key.pk).update(last_used=now)

        request.api_key = api_key
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return self.keyword
