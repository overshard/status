from django.db import migrations


def create_superuser(apps, schema_editor):
    """
    Makes the initial admin superuser with the username admin and the password
    admin.
    """
    User = apps.get_model('accounts', 'User')
    User.objects.create_superuser(username='admin', password='admin')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]
