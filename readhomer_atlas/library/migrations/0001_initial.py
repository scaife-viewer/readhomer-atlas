# Generated by Django 2.2.7 on 2019-11-14 22:01

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields.json


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Book",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.IntegerField()),
                ("idx", models.IntegerField(help_text="0-based index")),
            ],
            options={"ordering": ["idx"]},
        ),
        migrations.CreateModel(
            name="Version",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("urn", models.CharField(max_length=255)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "metadata",
                    django_extensions.db.fields.json.JSONField(
                        blank=True, default=dict
                    ),
                ),
            ],
            options={"ordering": ["urn"]},
        ),
        migrations.CreateModel(
            name="Line",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text_content", models.TextField()),
                ("position", models.IntegerField()),
                ("book_position", models.IntegerField()),
                ("idx", models.IntegerField(help_text="0-based index")),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="library.Book",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="library.Version",
                    ),
                ),
            ],
            options={"ordering": ["idx"]},
        ),
        migrations.AddField(
            model_name="book",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="books",
                to="library.Version",
            ),
        ),
    ]
