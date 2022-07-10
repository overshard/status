import re
import uuid

import requests
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property

User = get_user_model()


class SecurityMixin:

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
    def has_hsts(self):
        # hsts has at least one year set
        hsts = self.latest_headers.get("strict-transport-security", None)
        if hsts is None:
            return False
        # use re to get the max-age value
        max_age = re.search(r"max-age=(\d+)", hsts)
        if max_age is None:
            return False
        # convert to int and compare
        max_age = int(max_age.group(1))
        return max_age >= 31536000

    @property
    def has_hsts_preload(self):
        hsts = self.latest_headers.get("strict-transport-security", None)
        if hsts is None:
            return False
        return "preload" in hsts.lower()

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
        if not self.has_hsts:
            return True
        if not self.has_hsts_preload:
            return True
        return False


class AlertsMixin:

    def send_email(self):
        subject = f"Status: {self.name} is down!"
        message = render_to_string("emails/property_down.html", {"property": self})
        from_email = "noreply@bythewood.me"
        to_emails = [self.user.email]
        email = EmailMessage(subject, message, from_email, to_emails)
        email.content_subtype = "html"
        email.send()

    def send_discord_message(self):
        if self.user.discord_webhook_url:
            payload = {
                "username": "Status",
                "embeds": [
                    {
                        "title": "Status",
                        "description": f"{property.url} is down!",
                        "color": 16711680,
                        "timestamp": timezone.now().isoformat(),
                    }
                ],
            }
            requests.post(self.user.discord_webhook_url, json=payload)

    def send_alerts(self):
        # if the past two checks were != 200 send alerts
        checks = self.statuses.order_by("-created_at")[:2]
        if checks[0].status_code != 200 and checks[1].status_code != 200:
            self.send_email()
            self.send_discord_message()


class Property(AlertsMixin, SecurityMixin, models.Model):
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

    def should_check(self):
        now = timezone.now()
        if self.last_run_at is None:
            return True
        if self.next_run_at is None:
            return True
        return self.next_run_at <= now

    def run_check(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 Safari/537.36 Status/1.0.0"
            }
            response = requests.get(self.url, timeout=5, headers=headers)
            response_time = response.elapsed.total_seconds() * 1000
            status_code = response.status_code
            headers = response.headers
        except (requests.exceptions.SSLError):
            response_time = 5000
            status_code = 526
            headers = {}
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            response_time = 5000
            status_code = 408
            headers = {}
        return Check.objects.create(
            property=self,
            status_code=status_code,
            response_time=response_time,
            headers=dict(headers),
        )

    def process_check(self):
        check = self.run_check()
        if check.status_code != 200:
            self.send_alerts()

    @property
    def total_checks(self):
        return self.statuses.count()

    @cached_property
    def current_status(self):
        try:
            return self.statuses.latest("created_at").status_code
        except Check.DoesNotExist:
            return 200

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

    @cached_property
    def latest_headers(self):
        try:
            # return all headers lowercase to make them easier to use
            return {
                k.lower(): v.lower() for k, v in self.statuses.latest().headers.items()
            }
        except Check.DoesNotExist:
            return {}


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
