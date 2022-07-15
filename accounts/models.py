import uuid

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    discord_webhook_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.username

    @property
    def total_properties(self):
        return self.properties.count()

    @property
    def total_checks(self):
        total_checks = 0
        for property in self.properties.all():
            total_checks += property.total_checks
        return total_checks

    @property
    def total_properties_down(self):
        total_properties_down = 0
        for property in self.properties.all():
            total_properties_down += property.current_status != 200
        return total_properties_down
