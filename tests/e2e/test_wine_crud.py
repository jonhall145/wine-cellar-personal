"""E2E tests for wine CRUD operations."""

import pytest


@pytest.mark.django_db(transaction=True)
class TestWineCrud:
    def test_create_wine(self, authenticated_page, live_server):
        """Create a wine through the form."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wine/add/")
        page.wait_for_load_state("networkidle")
        assert "/wine/add" in page.url

        # Fill minimum required fields
        page.fill("input[name='name']", "E2E Test Merlot")
        # Select wine type if it's a dropdown
        wine_type = page.locator("select[name='wine_type']")
        if wine_type.count() > 0:
            wine_type.select_option(index=1)

        # Submit the form
        page.locator("button[type='submit'][name='save']").click()
        page.wait_for_load_state("networkidle")

        # Should redirect away from the add page
        assert "/wine/add" not in page.url

    def test_edit_wine(self, authenticated_page, live_server):
        """Edit an existing wine."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        page = authenticated_page

        # Create a wine via ORM
        membership = HouseholdMembership.objects.first()
        wine = Wine.objects.create(
            name="Wine To Edit",
            household=membership.household,
            user=membership.user,
            country="FR",
            wine_type="RED",
        )

        page.goto(f"{live_server.url}/wine/edit/{wine.pk}/")
        page.wait_for_load_state("networkidle")
        page.fill("input[name='name']", "Edited Wine Name")
        page.locator("button[type='submit'][name='save']").click()
        page.wait_for_load_state("networkidle")

        wine.refresh_from_db()
        assert wine.name == "Edited Wine Name"

    def test_delete_wine(self, authenticated_page, live_server):
        """Delete a wine via the confirm delete page."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        page = authenticated_page
        membership = HouseholdMembership.objects.first()
        wine = Wine.objects.create(
            name="Wine To Delete",
            household=membership.household,
            user=membership.user,
            country="IT",
            wine_type="RED",
        )

        page.goto(f"{live_server.url}/wine/delete/{wine.pk}/")
        page.wait_for_load_state("networkidle")
        # Use the specific delete button (name="save") to avoid matching nav buttons
        page.locator("button[type='submit'][name='save']").click()
        page.wait_for_load_state("networkidle")

        assert not Wine.objects.filter(pk=wine.pk).exists()
