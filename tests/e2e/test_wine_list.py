"""E2E tests for wine list page: listing, filtering, pagination."""

import pytest


@pytest.mark.django_db(transaction=True)
class TestWineList:
    @pytest.fixture(autouse=True)
    def _setup_wines(self, e2e_user):
        """Create test wines for list tests."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        membership = HouseholdMembership.objects.filter(user=e2e_user).first()
        self.household = membership.household
        self.user = e2e_user

        self.wines = []
        for i in range(15):
            wine = Wine.objects.create(
                name=f"Test Wine {i:02d}",
                household=self.household,
                user=self.user,
                country="FR" if i % 2 == 0 else "IT",
                wine_type="RE" if i % 3 == 0 else "WH",
                vintage=2020 + (i % 5),
            )
            self.wines.append(wine)

    def test_wine_list_loads(self, authenticated_page, live_server):
        """Wine list page loads and shows wines."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/")
        page.wait_for_load_state("networkidle")
        assert page.locator(".wine-card").count() > 0

    def test_wine_list_pagination(self, authenticated_page, live_server):
        """Wine list paginates with default 10 per page."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/")
        page.wait_for_load_state("networkidle")
        # Should have pagination since we have 15 wines
        pagination = page.locator("ul.pagination")
        assert pagination.count() > 0 or "page=2" in page.content()

    def test_wine_list_name_filter(self, authenticated_page, live_server):
        """Filtering by name narrows results."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/?name=Test+Wine+01")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "Test Wine 01" in content

    def test_wine_list_per_page(self, authenticated_page, live_server):
        """Changing per_page shows more results."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/?per_page=25")
        page.wait_for_load_state("networkidle")
        # All 15 wines should fit on one page with per_page=25
        cards = page.locator(".wine-card")
        assert cards.count() >= 15

    def test_per_page_selector_preserves_path(self, authenticated_page, live_server):
        """Changing per_page must stay on /wines/, not redirect to site root.

        Regression: JS used new URL(value, window.location.origin) which
        resolved ?per_page=50 against the origin, losing the /wines/ path.
        """
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/")
        page.wait_for_load_state("networkidle")

        # Selecting a per_page option triggers a full page navigation via JS
        with page.expect_navigation():
            page.locator("#per-page").select_option(label="25")

        # Must still be on /wines/, not /
        assert (
            "/wines/" in page.url
        ), f"Per-page selector navigated away from /wines/: {page.url}"
        assert (
            "per_page=25" in page.url
        ), f"Per-page selector did not set per_page=25: {page.url}"
