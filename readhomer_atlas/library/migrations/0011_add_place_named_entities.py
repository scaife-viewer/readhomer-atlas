# Generated by Django 2.2.10 on 2020-04-30 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0010_metricalannotation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="namedentity",
            name="kind",
            field=models.CharField(
                choices=[("person", "Person"), ("person", "Place")], max_length=6
            ),
        ),
    ]
