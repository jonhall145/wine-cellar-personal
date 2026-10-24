from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from wine_cellar.apps.api.authentication import APIKeyAuthentication
from wine_cellar.apps.api.pagination import StandardPagination
from wine_cellar.apps.api.permissions import ScopeBasedPermission


class HouseholdScopedViewSetMixin:
    """Base mixin for API viewsets that scope data to the API key's household."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [ScopeBasedPermission]
    pagination_class = StandardPagination

    def get_household(self):
        return self.request.api_key.household

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(household=self.get_household())

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user,
            household=self.get_household(),
        )

    def perform_destroy(self, instance):
        if hasattr(instance, "deleted"):
            update_fields = ["deleted"]
            instance.deleted = True
            # Match UI behavior: also set finished_date for storage items
            if hasattr(instance, "finished_date") and not instance.finished_date:
                from django.utils import timezone

                instance.finished_date = timezone.now().date()
                update_fields.append("finished_date")
            instance.save_with_modified(update_fields=update_fields)
        else:
            instance.delete()

    @classmethod
    def as_view(cls, actions=None, **initkwargs):
        view = super().as_view(actions=actions, **initkwargs)
        view.login_not_required = True
        return view


class HouseholdScopedModelViewSet(HouseholdScopedViewSetMixin, ModelViewSet):
    pass


class HouseholdScopedReadOnlyViewSet(HouseholdScopedViewSetMixin, ReadOnlyModelViewSet):
    pass


class GlobalReferenceViewSet(ReadOnlyModelViewSet):
    """Read-only viewset for global reference data (no household scoping)."""

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [ScopeBasedPermission]
    pagination_class = StandardPagination

    @classmethod
    def as_view(cls, actions=None, **initkwargs):
        view = super().as_view(actions=actions, **initkwargs)
        view.login_not_required = True
        return view
