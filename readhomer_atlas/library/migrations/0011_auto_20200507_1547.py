# Generated by Django 2.2.10 on 2020-05-07 15:47

from django.db import migrations, models
import django_extensions.db.fields.json


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0010_auto_20200507_1433"),
    ]

    operations = [
        migrations.AddField(
            model_name="textalignmentchunk",
            name="idx",
            field=models.IntegerField(default=0, help_text="0-based index"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="textalignmentchunk",
            name="items",
            field=django_extensions.db.fields.json.JSONField(blank=True, default=list),
        ),
    ]
