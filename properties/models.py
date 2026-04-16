import re
import uuid
import logging

import requests
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property
from crawler.runner import run_seo_spider

from status.lighthouse import (
    LighthouseError,
    fetch_lighthouse_results,
    parse_lighthouse_results,
)


logger = logging.getLogger(__name__)


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

    def send_down_email(self):
        subject = f"Status: {self.name} is down!"
        message = render_to_string("emails/property_down.html", {"property": self})
        from_email = "noreply@bythewood.me"
        to_emails = [self.user.email]
        email = EmailMessage(subject, message, from_email, to_emails)
        email.content_subtype = "html"
        try:
            email.send()
        except Exception:
            logger.exception("Failed to send down email for %s", self.url)

    def send_recovery_email(self):
        subject = f"Status: {self.name} is back up!"
        message = render_to_string("emails/property_recovery.html", {"property": self})
        from_email = "noreply@bythewood.me"
        to_emails = [self.user.email]
        email = EmailMessage(subject, message, from_email, to_emails)
        email.content_subtype = "html"
        try:
            email.send()
        except Exception:
            logger.exception("Failed to send recovery email for %s", self.url)

    def send_down_discord_message(self):
        if self.user.discord_webhook_url:
            payload = {
                "username": "Status",
                "embeds": [
                    {
                        "title": "Status Alert",
                        "description": f"{self.url} is down!",
                        "color": 16711680,  # Red
                        "timestamp": timezone.now().isoformat(),
                    }
                ],
            }
            try:
                requests.post(self.user.discord_webhook_url, json=payload, timeout=5)
            except requests.RequestException:
                logger.exception("Discord down webhook failed for %s", self.url)

    def send_recovery_discord_message(self):
        if self.user.discord_webhook_url:
            payload = {
                "username": "Status",
                "embeds": [
                    {
                        "title": "Status Recovery",
                        "description": f"{self.url} is back up!",
                        "color": 65280,  # Green
                        "timestamp": timezone.now().isoformat(),
                    }
                ],
            }
            try:
                requests.post(self.user.discord_webhook_url, json=payload, timeout=5)
            except requests.RequestException:
                logger.exception("Discord recovery webhook failed for %s", self.url)

    def send_alerts(self, current_status_code):
        """
        Send alerts based on state transitions:
        - Send 'down' alert when site goes from UP to DOWN
        - Send 'recovery' alert when site goes from DOWN to UP
        - No alerts for consecutive failures or consecutive successes
        """
        is_currently_up = current_status_code == 200

        # Lock the property row so concurrent checks can't both observe the
        # same alert_state and double-fire transitions.
        with transaction.atomic():
            locked = Property.objects.select_for_update().get(pk=self.pk)

            if is_currently_up and locked.alert_state == 'down':
                self.send_recovery_email()
                self.send_recovery_discord_message()
                locked.alert_state = 'up'
                locked.last_alert_sent = timezone.now()
                locked.save(update_fields=['alert_state', 'last_alert_sent'])
                self.alert_state = locked.alert_state
                self.last_alert_sent = locked.last_alert_sent
            elif not is_currently_up and locked.alert_state == 'up':
                # Require at least 2 consecutive failures to avoid false positives.
                checks = self.statuses.order_by("-created_at")[:2]
                if len(checks) >= 2 and checks[0].status_code != 200 and checks[1].status_code != 200:
                    self.send_down_email()
                    self.send_down_discord_message()
                    locked.alert_state = 'down'
                    locked.last_alert_sent = timezone.now()
                    locked.save(update_fields=['alert_state', 'last_alert_sent'])
                    self.alert_state = locked.alert_state
                    self.last_alert_sent = locked.last_alert_sent


class CrawlerMixin:
    def get_next_run_at_crawl(self):
        """Weekly crawl by default; users can trigger a recrawl anytime."""
        return timezone.now() + timezone.timedelta(days=7)

    def should_check_crawl(self):
        now = timezone.now()
        if self.last_run_at_crawler is None:
            return True
        if self.next_run_at_crawler is None:
            return True
        return self.next_run_at_crawler <= now

    def crawl_site(self):
        insights = run_seo_spider(self.url)
        self.crawler_insights = insights
        self.save(update_fields=["crawler_insights"])


class Property(CrawlerMixin, AlertsMixin, SecurityMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="properties")

    url = models.CharField(max_length=255)

    is_public = models.BooleanField(default=False)

    last_run_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)

    last_run_at_crawler = models.DateTimeField(blank=True, null=True)
    next_run_at_crawler = models.DateTimeField(blank=True, null=True)
    crawler_insights = models.JSONField(blank=True, null=True)

    lighthouse_scores = models.JSONField(blank=True, null=True)
    last_lighthouse_run_at = models.DateTimeField(blank=True, null=True)
    last_lighthouse_success_at = models.DateTimeField(blank=True, null=True)
    last_lighthouse_error = models.TextField(blank=True, null=True)
    next_lighthouse_run_at = models.DateTimeField(blank=True, null=True)

    # Alert state tracking
    last_alert_sent = models.DateTimeField(blank=True, null=True)
    alert_state = models.CharField(
        max_length=10,
        choices=[('up', 'Up'), ('down', 'Down')],
        default='up'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"

        indexes = [
            models.Index(fields=["url"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return self.url

    @property
    def name(self):
        return self.url.split("/")[2].replace("www.", "")

    def get_next_run_at(self):
        now = timezone.now()
        return now.replace(
            minute=(now.minute // 3) * 3, second=0, microsecond=0
        ) + timezone.timedelta(minutes=3)

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
            response = requests.get(self.url, timeout=(3, 10), headers=headers)
            response_time = response.elapsed.total_seconds() * 1000
            status_code = response.status_code
            headers = response.headers
        except (requests.exceptions.SSLError):
            response_time = 10000
            status_code = 526
            headers = {}
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            response_time = 10000
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
        # Always check for state changes, regardless of current status
        self.send_alerts(check.status_code)

    def get_next_run_at_lighthouse(self):
        """
        Should check daily.
        """
        return timezone.now() + timezone.timedelta(days=1)

    def should_check_lighthouse(self):
        now = timezone.now()
        if self.last_lighthouse_run_at is None:
            return True
        if self.next_lighthouse_run_at is None:
            return True
        return self.next_lighthouse_run_at <= now

    def process_check_lighthouse(self):
        self.run_check_lighthouse()

    def run_check_lighthouse(self):
        try:
            results = fetch_lighthouse_results(self.url)
            scores = parse_lighthouse_results(results)
        except LighthouseError as e:
            logger.warning("Lighthouse failed for %s: %s", self.url, e)
            self.last_lighthouse_error = str(e)
            self.save(update_fields=["last_lighthouse_error"])
            return
        except Exception as e:
            logger.exception("Unexpected lighthouse error for %s", self.url)
            self.last_lighthouse_error = f"{type(e).__name__}: {e}"
            self.save(update_fields=["last_lighthouse_error"])
            return

        self.lighthouse_scores = scores
        self.last_lighthouse_success_at = timezone.now()
        self.last_lighthouse_error = None
        self.save(
            update_fields=[
                "lighthouse_scores",
                "last_lighthouse_success_at",
                "last_lighthouse_error",
            ]
        )

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

    @cached_property
    def avg_lighthouse_score(self):
        if self.lighthouse_scores:
            scores = [score for score in self.lighthouse_scores.values()]
            return round(sum(scores) / len(scores))


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
            models.Index(fields=["property", "-created_at"]),
        ]
        get_latest_by = "created_at"

    def __str__(self):
        return f"{self.property.url} - {self.created_at} - {self.status_code}"
