import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Property(models.Model):
    """
    A site that we attach all our status hits to and connect up to a user.
    """

    RUN_INTERVAL_CHOICES = (
        (60, "Every 1 minute"),
        (180, "Every 3 minutes"),
        (300, "Every 5 minutes"),
        (900, "Every 15 minutes"),
        (1800, "Every 30 minutes"),
        (3600, "Every hour"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="properties")

    url = models.CharField(max_length=255)

    is_public = models.BooleanField(default=False)

    run_interval = models.IntegerField(choices=RUN_INTERVAL_CHOICES, default=180)
    last_run_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"

    def __str__(self):
        return self.url

    @property
    def name(self):
        return self.url.split("/")[2].replace("www.", "")

    def should_check(self):
        now = timezone.now()
        if self.last_run_at is None:
            return True
        if self.next_run_at is None:
            return True
        return self.next_run_at <= now

    def get_next_run_at(self):
        """
        Returns the next run datetime. Should be in whole increments of the interval.
        """
        now = timezone.now()
        if self.run_interval == 60:
            return now.replace(
                minute=(now.minute // 1) * 1, second=0, microsecond=0
            ) + timezone.timedelta(minutes=1)
        elif self.run_interval == 180:
            return now.replace(
                minute=(now.minute // 3) * 3, second=0, microsecond=0
            ) + timezone.timedelta(minutes=3)
        elif self.run_interval == 300:
            return now.replace(
                minute=(now.minute // 5) * 5, second=0, microsecond=0
            ) + timezone.timedelta(minutes=5)
        elif self.run_interval == 900:
            return now.replace(
                minute=(now.minute // 15) * 15, second=0, microsecond=0
            ) + timezone.timedelta(minutes=15)
        elif self.run_interval == 1800:
            return now.replace(
                minute=(now.minute // 30) * 30, second=0, microsecond=0
            ) + timezone.timedelta(minutes=30)
        elif self.run_interval == 3600:
            today = now.replace(minute=0, second=0, microsecond=0)
            return today + timezone.timedelta(hours=1)
        else:
            raise ValueError("Invalid run interval")

    @property
    def total_checks(self):
        return self.statuses.count()

    @property
    def current_status(self):
        return self.statuses.latest("created_at").status_code

    @property
    def avg_response_time(self):
        try:
            return int(
                self.statuses.all()[:31].aggregate(models.Avg("response_time"))[
                    "response_time__avg"
                ]
            )
        except TypeError:
            return 0

    @property
    def latest_headers(self):
        try:
            # return all headers lowercase to make them easier to use
            return {
                k.lower(): v.lower() for k, v in self.statuses.latest().headers.items()
            }
        except Check.DoesNotExist:
            return {}

    @property
    def invalid_cert(self):
        return self.statuses.latest("created_at").status_code == 526

    @property
    def is_https(self):
        return self.url.startswith("https://")

    @property
    def has_mime_type(self):
        return self.latest_headers.get("content-type", None) is not None

    @property
    def has_content_sniffing_protection(self):
        return self.latest_headers.get("x-content-type-options", None) == "nosniff"

    @property
    def has_xss_protection(self):
        return self.latest_headers.get("x-xss-protection", None) == "1; mode=block"

    @property
    def has_clickjack_protection(self):
        return self.latest_headers.get("x-frame-options", None) in [
            "deny",
            "sameorigin",
            "allow-from",
        ]

    @property
    def hides_server_version(self):
        if (
            self.latest_headers.get("server", None) is None
            and self.latest_headers.get("x-server", None) is None
            and self.latest_headers.get("powered-by", None) is None
            and self.latest_headers.get("x-powered-by", None) is None
        ):
            return True
        return False

    @property
    def has_security_issue(self):
        if not self.is_https:
            return True
        if not self.has_mime_type:
            return True
        if not self.has_content_sniffing_protection:
            return True
        if not self.has_xss_protection:
            return True
        if not self.has_clickjack_protection:
            return True
        if not self.hides_server_version:
            return True
        return False


class Check(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="statuses", editable=False
    )

    status_code = models.IntegerField()
    response_time = models.IntegerField(default=0)
    headers = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        verbose_name = "Check"
        verbose_name_plural = "Checks"
        indexes = [
            models.Index(fields=["created_at"]),
        ]
        get_latest_by = "created_at"

    def __str__(self):
        return f"{self.property.url} - {self.created_at} - {self.status_code}"
