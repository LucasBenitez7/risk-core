import structlog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

logger = structlog.get_logger()
User = get_user_model()


class Command(BaseCommand):
    help = "Create admin/admin test user. Only runs when DEBUG=True."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            logger.info("seed_test_user_skipped", reason="DEBUG is False")
            return

        if User.objects.filter(username="admin").exists():
            logger.info("seed_test_user_skipped", reason="user already exists")
            return

        User.objects.create_superuser(
            username="admin",
            password="admin",  # pragma: allowlist secret
            email="admin@riskcore.local",
        )
        logger.info("seed_test_user_created", username="admin")
