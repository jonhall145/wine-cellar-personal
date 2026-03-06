from wine_cellar.apps.core.views import (
    BaseWishlistCreateView,
    BaseWishlistDeleteView,
    BaseWishlistListView,
    BaseWishlistPurchasedView,
)
from wine_cellar.apps.wine.models import Wishlist


class WishlistListView(BaseWishlistListView):
    template_name = "core/wishlist_list.html"
    wishlist_model = Wishlist
    wishlist_columns_header = "includes/wishlist_columns_header.html"
    wishlist_columns_row = "includes/wishlist_columns_row.html"


class WishlistCreateView(BaseWishlistCreateView):
    template_name = "core/wishlist_create.html"
    wishlist_model = Wishlist

    def get_form_class(self):
        from wine_cellar.apps.wine.forms import WishlistForm

        return WishlistForm

    def get_extra_create_kwargs(self, form):
        return {
            "wine_type": form.cleaned_data.get("wine_type") or None,
            "country": form.cleaned_data.get("country") or None,
            "subregion": form.cleaned_data.get("subregion"),
            "vintage": form.cleaned_data.get("vintage"),
        }


class WishlistDeleteView(BaseWishlistDeleteView):
    model = Wishlist
    template_name = "wishlist_confirm_delete.html"


class WishlistPurchasedView(BaseWishlistPurchasedView):
    wishlist_model = Wishlist
