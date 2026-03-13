"""Web Push notification utilities for PWA."""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def send_push_notification(subscription, title, body, url="/"):
    """Send a push notification to a single subscription.

    Returns True on success, False on failure (including expired subscriptions).
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.debug("VAPID keys not configured, skipping push notification")
        return False

    try:
        from pywebpush import WebPushException, webpush

        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "url": url,
                "icon": "/static/images/pwa-icon-192.png",
            }
        )

        webpush(
            subscription_info=subscription.to_webpush_dict(),
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
        )
        return True
    except WebPushException as e:
        if e.response and e.response.status_code in (404, 410):
            # Subscription expired or invalid — clean it up
            logger.info("Removing expired push subscription %s", subscription.pk)
            subscription.delete()
        else:
            logger.warning("Push notification failed: %s", e)
        return False
    except Exception:
        logger.exception("Unexpected error sending push notification")
        return False


def send_push_to_user(user, title, body, url="/"):
    """Send a push notification to all of a user's subscriptions.

    Returns the number of successful sends.
    """
    from wine_cellar.apps.user.models import PushSubscription

    subscriptions = PushSubscription.objects.filter(user=user)
    sent = 0
    for sub in subscriptions:
        if send_push_notification(sub, title, body, url):
            sent += 1
    return sent
