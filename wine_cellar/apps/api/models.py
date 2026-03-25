import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


class APIKeyScope(models.TextChoices):
    READ = "RE", "Read"
    WRITE = "WR", "Write"
    ADMIN = "AD", "Admin"


SCOPE_HIERARCHY = {
    APIKeyScope.READ: 0,
    APIKeyScope.WRITE: 1,
    APIKeyScope.ADMIN: 2,
}


class APIKey(models.Model):
    name = models.CharField(max_length=100, verbose_name="Key Name")
    prefix = models.CharField(max_length=8, db_index=True, verbose_name="Key Prefix")
    hashed_key = models.CharField(max_length=128, verbose_name="Hashed Key")
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    household = models.ForeignKey(
        "household.Household",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    scope = models.CharField(
        max_length=2,
        choices=APIKeyScope.choices,
        default=APIKeyScope.READ,
    )
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    def has_scope(self, required_scope):
        return SCOPE_HIERARCHY.get(self.scope, 0) >= SCOPE_HIERARCHY.get(
            required_scope, 0
        )

    @property
    def is_expired(self):
        if self.expires is None:
            return False
        return timezone.now() > self.expires

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    @classmethod
    def generate_key(cls):
        """Generate a new API key. Returns (raw_key, prefix, hashed_key)."""
        raw_key = f"wc_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:8]
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, prefix, hashed_key
