from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.notifications.models import Notification


class NotificationMetricsService:
    def get_metrics(self) -> dict:
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)

        sent_today = Notification.objects.filter(
            status=Notification.Status.SENT,
            sent_at__date=today,
        ).count()

        failed_today = Notification.objects.filter(
            status=Notification.Status.FAILED,
            created_at__date=today,
        ).count()

        pending = Notification.objects.filter(
            status=Notification.Status.PENDING
        ).count()

        week_agg = (
            Notification.objects.filter(
                created_at__date__gte=seven_days_ago,
                status__in=[Notification.Status.SENT, Notification.Status.FAILED],
            )
            .values("status")
            .annotate(count=Count("id"))
        )

        sent_7d = 0
        failed_7d = 0
        for row in week_agg:
            if row["status"] == Notification.Status.SENT:
                sent_7d = row["count"]
            elif row["status"] == Notification.Status.FAILED:
                failed_7d = row["count"]

        total_7d = sent_7d + failed_7d
        success_rate_7d = (
            round((sent_7d / total_7d) * 100, 1) if total_7d > 0 else 100.0
        )

        return {
            "sent_today": sent_today,
            "failed_today": failed_today,
            "pending": pending,
            "success_rate_7d": success_rate_7d,
        }
