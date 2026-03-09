from django.views.generic import TemplateView

from wine_cellar.apps.household.mixins import RequireHouseholdMixin
from wine_cellar.apps.user.views import get_active_household
from wine_cellar.apps.wine.models import Wine


class WineMapView(RequireHouseholdMixin, TemplateView):
    template_name = "wine_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        household = get_active_household(self.request.user)
        wines = Wine.objects.filter(
            household=household,
            deleted=False,
            storageitem__isnull=False,
            storageitem__deleted=False,
        ).distinct()

        context.update(
            {
                "wines": wines,
            }
        )
        return context
