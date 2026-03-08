"""E2E test fixtures using Playwright with pytest-django live_server."""

import os

import pytest

# Skip all e2e tests if Playwright browsers are not installed
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        if not os.path.exists(p.chromium.executable_path):
            raise FileNotFoundError(p.chromium.executable_path)
    _playwright_available = True
except Exception:
    _playwright_available = False

if not _playwright_available:
    pytest.skip(
        "Playwright browsers not installed (run: playwright install chromium)",
        allow_module_level=True,
    )

# Playwright runs in an async context; allow Django ORM calls in test fixtures
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# Mobile-first viewport (iPhone 14 equivalent)
MOBILE_VIEWPORT = {"width": 390, "height": 844}

TEST_USERNAME = "e2e_testuser"
TEST_PASSWORD = "e2e_testpass123"


@pytest.fixture(scope="session")
def browser_context_args():
    """Default browser context: mobile-first viewport."""
    return {
        "viewport": MOBILE_VIEWPORT,
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 "
            "Safari/604.1"
        ),
    }


@pytest.fixture()
def e2e_user(db):
    """Create a test user with a household and active_household set."""
    from django.contrib.auth import get_user_model

    from wine_cellar.apps.household.models import Household, HouseholdMembership
    from wine_cellar.apps.user.models import UserSettings

    User = get_user_model()
    user = User.objects.create_user(
        username=TEST_USERNAME,
        password=TEST_PASSWORD,
        email="e2e@test.com",
    )
    household = Household.objects.create(name="E2E Household")
    HouseholdMembership.objects.create(user=user, household=household, role="OW")
    # Set active household so views don't redirect to /household/
    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    user_settings.active_household = household
    user_settings.save()
    return user


def _login(page, live_server, username=TEST_USERNAME, password=TEST_PASSWORD):
    """Helper: log in via the login page."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='login']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    page.wait_for_url(f"{live_server.url}/**")


@pytest.fixture()
def authenticated_page(page, live_server, e2e_user):
    """A Playwright page already logged in as the test user."""
    _login(page, live_server)
    return page
