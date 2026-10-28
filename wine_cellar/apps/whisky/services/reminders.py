from django.db.models import Count, F, Q

from wine_cellar.apps.whisky.models import WhiskyReorderReminder


class WhiskyReminderService:
    @staticmethod
    def get_reorder_reminders(household):
        return (
            WhiskyReorderReminder.objects.filter(household=household, is_active=True)
            .select_related("whisky")
            .annotate(
                current_stock=Count(
                    "whisky__whiskystorageitem",
                    filter=Q(whisky__whiskystorageitem__deleted=False),
                )
            )
        )

    @classmethod
    def get_reorder_context(cls, household):
        reminders = cls.get_reorder_reminders(household)
        needs_reorder = [
            {
                "whisky": reminder.whisky,
                "current_stock": reminder.current_stock,
                "min_stock": reminder.min_stock,
                "reminder": reminder,
            }
            for reminder in reminders
            if reminder.current_stock <= reminder.min_stock
        ]
        return reminders, needs_reorder

    @classmethod
    def count_low_stock_reminders(cls, household):
        return (
            cls.get_reorder_reminders(household)
            .filter(current_stock__lte=F("min_stock"))
            .count()
        )

    @staticmethod
    def save_reorder_reminder(*, whisky, user, household, min_stock):
        return WhiskyReorderReminder.objects.update_or_create(
            whisky=whisky,
            user=user,
            household=household,
            defaults={"min_stock": min_stock, "is_active": True},
        )
