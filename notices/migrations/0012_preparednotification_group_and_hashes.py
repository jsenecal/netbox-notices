import django.db.models.deletion
from django.db import migrations, models

import notices.models.messaging


class Migration(migrations.Migration):
    dependencies = [
        ("notices", "0011_alter_preparednotification_headers_and_more"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="preparednotification",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="impact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="notices.impact",
            ),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="rendered_hash",
            field=models.CharField(blank=True, default="", editable=False, max_length=32),
        ),
        migrations.AddField(
            model_name="preparednotification",
            name="content_hash",
            field=models.GeneratedField(
                db_persist=True,
                expression=notices.models.messaging._content_hash_expression(),
                output_field=models.CharField(max_length=32),
            ),
        ),
    ]
