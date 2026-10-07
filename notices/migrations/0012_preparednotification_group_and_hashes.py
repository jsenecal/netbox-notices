import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import MD5, Cast, Coalesce, Concat


def _text(field):
    return Coalesce(field, models.Value(""), output_field=models.TextField())


# Inlined rather than imported so later model changes cannot rewrite this migration's history.
CONTENT_HASH = MD5(
    Concat(
        _text(Cast("headers", models.TextField())),
        *(
            part
            for name in ("subject", "body_text", "body_html", "css", "ical_content")
            for part in (models.Value("\x1f"), _text(name))
        ),
        output_field=models.TextField(),
    )
)


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
                expression=CONTENT_HASH,
                output_field=models.CharField(max_length=32),
            ),
        ),
    ]
