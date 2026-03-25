from rest_framework.permissions import SAFE_METHODS, BasePermission

from wine_cellar.apps.api.models import APIKeyScope


class HasReadScope(BasePermission):
    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        return api_key.has_scope(APIKeyScope.READ)


class HasWriteScope(BasePermission):
    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        return api_key.has_scope(APIKeyScope.WRITE)


class HasAdminScope(BasePermission):
    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        return api_key.has_scope(APIKeyScope.ADMIN)


class ScopeBasedPermission(BasePermission):
    """Maps HTTP methods to required scopes:
    GET/HEAD/OPTIONS -> Read, POST/PUT/PATCH/DELETE -> Write.
    """

    def has_permission(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return False
        if request.method in SAFE_METHODS:
            return api_key.has_scope(APIKeyScope.READ)
        return api_key.has_scope(APIKeyScope.WRITE)
