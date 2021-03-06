# Generated by Django 4.0.6 on 2022-07-15 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='last_lighthouse_run_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='lighthouse_scores',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='next_lighthouse_run_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
