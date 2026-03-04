"""E2E tests for wine CRUD operations."""

import pytest


@pytest.mark.django_db(transaction=True)
class TestWineCrud:
    def test_create_wine(self, authenticated_page, live_server):
        """Create a wine through the form."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wines/add/")
        assert page.url.endswith("/wines/add/") or "add" in page.url

        # Fill minimum required fields
        page.fill("input[name='name']", "E2E Test Merlot")
        # Select wine type if it's a dropdown
        wine_type = page.locator("select[name='wine_type']")
        if wine_type.count() > 0:
            wine_type.select_option(index=1)

        # Submit the form
        page.click("button[type='submit'], input[type='submit']")
        page.wait_for_load_state("networkidle")

        # Should redirect to the wine detail page
        assert "/wines/add/" not in page.url

    def test_edit_wine(self, authenticated_page, live_server):
        """Edit an existing wine."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        page = authenticated_page

        # Create a wine via ORM
        user = HouseholdMembership.objects.first().user
        household = HouseholdMembership.objects.first().household
        wine = Wine.objects.create(
            name="Wine To Edit",
            household=household,
            user=user,
            country="FR",
            wine_type="RED",
        )

        page.goto(f"{live_server.url}/wines/{wine.pk}/edit/")
        page.fill("input[name='name']", "Edited Wine Name")
        page.click("button[type='submit'], input[type='submit']")
        page.wait_for_load_state("networkidle")

        wine.refresh_from_db()
        assert wine.name == "Edited Wine Name"

    def test_delete_wine(self, authenticated_page, live_server):
        """Delete a wine via the confirm delete page."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        page = authenticated_page
        user = HouseholdMembership.objects.first().user
        household = HouseholdMembership.objects.first().household
        wine = Wine.objects.create(
            name="Wine To Delete",
            household=household,
            user=user,
            country="IT",
            wine_type="RED",
        )

        page.goto(f"{live_server.url}/wines/{wine.pk}/delete/")
        page.click("button[type='submit'], input[type='submit']")
        page.wait_for_load_state("networkidle")

        assert not Wine.objects.filter(pk=wine.pk).exists()
