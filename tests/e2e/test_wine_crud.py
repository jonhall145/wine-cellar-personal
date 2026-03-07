"""E2E tests for wine CRUD operations."""

import pytest


@pytest.mark.django_db(transaction=True)
class TestWineCrud:
    def test_create_wine(self, authenticated_page, live_server):
        """Create a wine through the form."""
        page = authenticated_page
        page.goto(f"{live_server.url}/wine/add/")
        page.wait_for_load_state("networkidle")

        form = page.locator("form.wine-form")
        form.wait_for(state="visible")
        form.locator("input[name='name']").fill("E2E Test Merlot")
        wine_type = form.locator("select[name='wine_type']")
        if wine_type.count() > 0:
            wine_type.select_option(index=1)

        form.locator("button[name='save_finish']").click()
        page.wait_for_load_state("networkidle")
        assert "/wine/add" not in page.url

    def test_edit_wine(self, authenticated_page, live_server):
        """Edit an existing wine."""
        from wine_cellar.apps.household.models import HouseholdMembership
        from wine_cellar.apps.wine.models import Wine

        page = authenticated_page
        membership = HouseholdMembership.objects.first()
        wine = Wine.objects.create(
            name="Wine To Edit",
            household=membership.household,
            user=membership.user,
            country="FR",
            wine_type="RE",
        )

        page.goto(f"{live_server.url}/wine/edit/{wine.pk}/")
        page.wait_for_load_state("networkidle")

        form = page.locator("form.wine-form")
        form.wait_for(state="visible")
        form.locator("input[name='name']").fill("Edited Wine Name")
        form.locator("button[type='submit']").click()
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
            wine_type="RE",
        )

        page.goto(f"{live_server.url}/wine/delete/{wine.pk}/")
        page.wait_for_load_state("networkidle")
        page.locator("main button[type='submit'][name='save']").click()
        page.wait_for_load_state("networkidle")

        assert not Wine.objects.filter(pk=wine.pk).exists()
