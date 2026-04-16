from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0007_add_alert_state_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='last_lighthouse_success_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='last_lighthouse_error',
            field=models.TextField(blank=True, null=True),
        ),
    ]
