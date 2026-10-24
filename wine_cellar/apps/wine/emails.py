from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_drink_by_reminder(user, wines):
    text_content = render_to_string(
        "emails/drink_by_reminder.txt",
        context={"wines": wines, "user": user},
    )

    msg = EmailMultiAlternatives(
        "Reminder to drink your wine(s)", text_content, to=[user.email]
    )
    msg.send()


def send_occasion_date_reminder(user, bottles):
    text_content = render_to_string(
        "emails/occasion_date_reminder.txt",
        context={"bottles": bottles, "user": user},
    )

    msg = EmailMultiAlternatives(
        "Reminder about your wine occasion date(s)", text_content, to=[user.email]
    )
    msg.send()
