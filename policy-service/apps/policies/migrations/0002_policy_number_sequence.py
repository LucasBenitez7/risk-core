from django.db import migrations


def create_sequence(apps, schema_editor):
    """PostgreSQL only. SQLite (used in tests) keeps the legacy lock-based path."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE SEQUENCE IF NOT EXISTS policy_number_seq")
        # Sync sequence to existing max policy number to avoid duplicates
        schema_editor.execute(
            "SELECT setval('policy_number_seq', "
            "(SELECT COALESCE(MAX(CAST(SPLIT_PART(policy_number, '-', 3) AS INTEGER)), 0) "
            "FROM policies_policy))"
        )


def drop_sequence(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP SEQUENCE IF EXISTS policy_number_seq")


class Migration(migrations.Migration):
    dependencies = [
        ("policies", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_sequence, drop_sequence),
    ]
