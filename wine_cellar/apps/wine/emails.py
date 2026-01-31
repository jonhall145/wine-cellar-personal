from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _


def send_drink_by_reminder(user, wines):
    text_content = render_to_string(
        "emails/drink_by_reminder.txt",
        context={"wines": wines, "user": user},
    )

    msg = EmailMultiAlternatives(
        _("Reminder to drink your wine(s)"), text_content, to=[user.email]
    )
    msg.send()


def send_sale_alert(user, deals):
    """Send sale alert email to user about price drops.

    Args:
        user: User to notify
        deals: List of dicts with keys: wine, source, current_price, previous_price
    """
    text_content = render_to_string(
        "emails/sale_alert.txt",
        context={"deals": deals, "user": user},
    )

    msg = EmailMultiAlternatives(
        _("Wine Sale Alert: Price drops detected!"),
        text_content,
        to=[user.email],
    )
    msg.send()
