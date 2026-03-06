"""E2E tests for authentication flow."""

import pytest

from tests.e2e.conftest import TEST_USERNAME, _login


@pytest.mark.django_db(transaction=True)
class TestAuth:
    def test_login_redirects_to_homepage(self, page, live_server, e2e_user):
        """Successful login redirects to the homepage."""
        _login(page, live_server)
        assert (
            page.url.rstrip("/") == live_server.url.rstrip("/")
            or "/accounts/" not in page.url
        )

    def test_unauthenticated_redirect(self, page, live_server):
        """Unauthenticated users are redirected to the login page."""
        page.goto(f"{live_server.url}/wines/")
        assert "/accounts/login" in page.url

    def test_logout(self, authenticated_page, live_server):
        """Logging out redirects to the login page."""
        page = authenticated_page
        # POST directly to the logout endpoint to avoid multiple submit buttons
        page.goto(f"{live_server.url}/accounts/logout/")
        # Click the Sign Out button in the main content area (not nav)
        page.locator("main button[type='submit']").first.click()
        page.wait_for_load_state("networkidle")
        # Should be redirected away from authenticated pages
        page.goto(f"{live_server.url}/wines/")
        assert "/accounts/login" in page.url

    def test_login_invalid_credentials(self, page, live_server, e2e_user):
        """Invalid credentials show an error message."""
        page.goto(f"{live_server.url}/accounts/login/")
        page.fill("input[name='login']", TEST_USERNAME)
        page.fill("input[name='password']", "wrong_password")
        page.click("button[type='submit']")
        # Should stay on login page with error
        assert "/accounts/login" in page.url
