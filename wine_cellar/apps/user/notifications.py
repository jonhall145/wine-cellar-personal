import datetime
from dataclasses import dataclass

from django.conf import settings
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from wine_cellar.apps.household.models import HouseholdInvitation, InvitationStatus
from wine_cellar.apps.user.models import InAppNotificationStatus


@dataclass(slots=True)
class NotificationItem:
    key: str
    notification_type: str
    section: str
    title: str
    body: str
    severity: str
    icon: str
    url: str
    url_label: str
    sort_order: int
    is_read: bool = False
    invitation_token: str | None = None


def get_notification_summary(request):
    if hasattr(request, "_notification_summary"):
        return request._notification_summary

    notifications = []
    if request.user.is_authenticated:
        notifications = build_in_app_notifications(request.user)

    sections = {}
    for notification in notifications:
        sections.setdefault(notification.section, []).append(notification)

    request._notification_summary = {
        "notifications": notifications,
        "notification_sections": sections,
        "notification_unread_count": sum(
            1 for notification in notifications if not notification.is_read
        ),
    }
    return request._notification_summary


def build_in_app_notifications(user):
    from wine_cellar.apps.user.views import get_active_household, get_user_settings

    user_settings = get_user_settings(user)
    household = get_active_household(user)
    notifications = []

    if household and user_settings.allows_in_app_notifications("drink_window"):
        notifications.extend(_build_drink_window_notifications(user, household))
    if household and user_settings.allows_in_app_notifications("low_stock"):
        notifications.extend(_build_low_stock_notifications(user, household))
    if (
        user.email
        and user_settings.allows_in_app_notifications("household_invitation")
        and user_settings.notifications
    ):
        notifications.extend(_build_household_invitation_notifications(user))

    statuses = {
        status.notification_key: status
        for status in InAppNotificationStatus.objects.filter(
            user=user,
            notification_key__in=[notification.key for notification in notifications],
        )
    }

    visible_notifications = []
    for notification in sorted(
        notifications, key=lambda item: (item.sort_order, item.title.lower())
    ):
        status = statuses.get(notification.key)
        if status and status.dismissed_at:
            continue
        notification.is_read = bool(status and status.is_read)
        visible_notifications.append(notification)

    return visible_notifications


def _build_drink_window_notifications(user, household):
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    if app_type == "whisky":
        return _build_whisky_drink_window_notifications(household)
    return _build_wine_drink_window_notifications(user, household)


def _build_wine_drink_window_notifications(user, household):
    from wine_cellar.apps.user.views import get_user_settings
    from wine_cellar.apps.wine.models import Wine

    user_settings = get_user_settings(user)
    current_year = timezone.now().year
    stock_filter = Q(storageitem__deleted=False)
    notifications = []

    overdue_wines = (
        Wine.objects.filter(
            household=household,
            deleted=False,
            drink_to__isnull=False,
            drink_to__gt=0,
            drink_to__lt=current_year,
        )
        .annotate(notification_stock_count=Count("storageitem", filter=stock_filter))
        .filter(notification_stock_count__gt=0)
        .distinct()
    )
    for wine in overdue_wines:
        notifications.append(
            NotificationItem(
                key=(
                    "drink-window:wine:"
                    f"{wine.pk}:overdue:{wine.notification_stock_count}"
                ),
                notification_type="drink_window",
                section="Drink window",
                title=wine.name,
                body=(
                    f"Past drink-by year {wine.drink_to}. "
                    f"{wine.notification_stock_count} bottle(s) still in stock."
                ),
                severity="danger",
                icon="clock",
                url=reverse("wine-detail", args=[wine.pk]),
                url_label="View wine",
                sort_order=10,
            )
        )

    if user_settings.reminder_enabled:
        max_drink_to = current_year + user_settings.reminder_years_before
        upcoming_wines = (
            Wine.objects.filter(
                household=household,
                deleted=False,
                drink_to__isnull=False,
                drink_to__gt=0,
                drink_to__gte=current_year,
                drink_to__lte=max_drink_to,
            )
            .annotate(
                notification_stock_count=Count("storageitem", filter=stock_filter)
            )
            .filter(notification_stock_count__gt=0)
            .distinct()
        )
        for wine in upcoming_wines:
            notifications.append(
                NotificationItem(
                    key=(
                        "drink-window:wine:"
                        f"{wine.pk}:upcoming:{wine.notification_stock_count}"
                    ),
                    notification_type="drink_window",
                    section="Drink window",
                    title=wine.name,
                    body=(
                        f"Drink-by year {wine.drink_to} is approaching. "
                        f"{wine.notification_stock_count} bottle(s) in stock."
                    ),
                    severity="warning",
                    icon="wine-bottle",
                    url=reverse("wine-detail", args=[wine.pk]),
                    url_label="View wine",
                    sort_order=20,
                )
            )

    return notifications


def _build_whisky_drink_window_notifications(household):
    from wine_cellar.apps.whisky.models import WhiskyStorageItem

    today = datetime.date.today()
    warning_cutoff = today - datetime.timedelta(days=335)
    expired_cutoff = today - datetime.timedelta(days=365)
    notifications = []

    dreg_expired = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        fill_level="DR",
        dreg_date__lte=expired_cutoff,
    ).select_related("whisky", "storage")
    for item in dreg_expired:
        notifications.append(
            NotificationItem(
                key=f"drink-window:whisky:{item.pk}:expired",
                notification_type="drink_window",
                section="Drink window",
                title=item.whisky.name,
                body=(
                    f"Dreg bottle has been open since {item.dreg_date} "
                    f"in {item.storage}."
                ),
                severity="danger",
                icon="whiskey-glass",
                url=reverse("whisky-detail", args=[item.whisky.pk]),
                url_label="View whisky",
                sort_order=10,
            )
        )

    dreg_warning = WhiskyStorageItem.objects.filter(
        household=household,
        deleted=False,
        fill_level="DR",
        dreg_date__lte=warning_cutoff,
        dreg_date__gt=expired_cutoff,
    ).select_related("whisky", "storage")
    for item in dreg_warning:
        notifications.append(
            NotificationItem(
                key=f"drink-window:whisky:{item.pk}:warning",
                notification_type="drink_window",
                section="Drink window",
                title=item.whisky.name,
                body=f"Dreg bottle is nearing one year open in {item.storage}.",
                severity="warning",
                icon="clock",
                url=reverse("whisky-detail", args=[item.whisky.pk]),
                url_label="View whisky",
                sort_order=20,
            )
        )

    return notifications


def _build_low_stock_notifications(user, household):
    app_type = getattr(settings, "CELLAR_APP_TYPE", "wine")
    if app_type == "whisky":
        from wine_cellar.apps.whisky.models import WhiskyReorderReminder

        reminders = (
            WhiskyReorderReminder.objects.filter(household=household, is_active=True)
            .select_related("whisky")
            .annotate(
                current_stock=Count(
                    "whisky__whiskystorageitem",
                    filter=Q(whisky__whiskystorageitem__deleted=False),
                )
            )
        )
        return [
            NotificationItem(
                key=f"low-stock:whisky:{reminder.pk}:{reminder.current_stock}",
                notification_type="low_stock",
                section="Low stock",
                title=reminder.whisky.name,
                body=(
                    f"Only {reminder.current_stock} bottle(s) left. "
                    f"Minimum stock is {reminder.min_stock}."
                ),
                severity="warning",
                icon="arrow-down",
                url=reverse("whisky-detail", args=[reminder.whisky.pk]),
                url_label="View whisky",
                sort_order=30,
            )
            for reminder in reminders
            if reminder.current_stock <= reminder.min_stock
        ]

    from wine_cellar.apps.wine.models import ReorderReminder

    reminders = (
        ReorderReminder.objects.filter(household=household, is_active=True)
        .select_related("wine")
        .annotate(
            current_stock=Count(
                "wine__storageitem",
                filter=Q(wine__storageitem__deleted=False),
            )
        )
    )
    return [
        NotificationItem(
            key=f"low-stock:wine:{reminder.pk}:{reminder.current_stock}",
            notification_type="low_stock",
            section="Low stock",
            title=reminder.wine.name,
            body=(
                f"Only {reminder.current_stock} bottle(s) left. "
                f"Minimum stock is {reminder.min_stock}."
            ),
            severity="warning",
            icon="arrow-down",
            url=reverse("wine-detail", args=[reminder.wine.pk]),
            url_label="View wine",
            sort_order=30,
        )
        for reminder in reminders
        if reminder.current_stock <= reminder.min_stock
    ]


def _build_household_invitation_notifications(user):
    notifications = []
    invitations = HouseholdInvitation.objects.filter(
        email=user.email,
        status=InvitationStatus.PENDING,
    ).select_related("household", "invited_by")
    for invitation in invitations:
        inviter = (
            invitation.invited_by.username
            if invitation.invited_by
            else "another member"
        )
        notifications.append(
            NotificationItem(
                key=f"household-invitation:{invitation.pk}",
                notification_type="household_invitation",
                section="Household invitations",
                title=invitation.household.name,
                body=f"Invited by {inviter} as {invitation.get_role_display()}.",
                severity="info",
                icon="user-group",
                url=reverse("household-list"),
                url_label="Manage households",
                sort_order=40,
                invitation_token=invitation.token,
            )
        )
    return notifications
