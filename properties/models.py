import re
import uuid
import os
import json
import logging

import requests
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.functional import cached_property
from django.conf import settings
from crawler.runner import run_seo_spider

from status.lighthouse import fetch_lighthouse_results, parse_lighthouse_results


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


class CrawlerMixin:
    @cached_property
    def get_crawl_output(self):
        """
        This will fetch crawler output in the JSON format from the folders:

        - DEBUG == True: crawler_output/
        - DEBUG == False: /data/crawler_output/

        The filename in the folder is the site URL `self.url.split("/")[2] + ".json"`.

        Need to parse every line individually to get the data.
        """
        if settings.DEBUG:
            path = "crawler_output/"
        else:
            path = "/data/crawler_output/"

        try:
            with open(os.path.join(path, self.url.split("/")[2] + ".json")) as f:
                data = []
                for line in f:
                    data.append(json.loads(line))
                return data
        except FileNotFoundError:
            return []

    def get_next_run_at_crawl(self):
        """
        Should check daily.
        """
        return timezone.now() + timezone.timedelta(days=1)

    def should_check_crawl(self):
        now = timezone.now()
        if self.last_run_at_crawler is None:
            return True
        if self.next_run_at_crawler is None:
            return True
        return self.next_run_at_crawler <= now

    def parse_page(self, page):
        insights = []

        # Make sure the content type is text/html else skip
        if "text/html" not in page.get("content_type", ""):
            return insights

        # Make sure all pages have a title
        if page['title'] == '':
            logger.warning(f"Page {page['url']} has no title")
            insights.append({
                'url': page['url'],
                'issue': 'Page has no title',
                'type': 'seo',
            })

        # Make sure pages have a title between 30 and 60 characters
        if len(page['title']) < 30 or len(page['title']) > 60:
            logger.warning(f"Page {page['url']} has title of length {len(page['title'])}")
            insights.append({
                'url': page['url'],
                'item': page['title'],
                'issue': 'Page title is not between 30 and 60 characters',
                'type': 'seo',
            })

        # Make sure pages have a unique title
        if page['title'] in [p['title'] for p in self.get_crawl_output if p['url'] != page['url']]:
            logger.warning(f"Page {page['url']} has duplicate title")
            insights.append({
                'url': page['url'],
                'item': page['title'],
                'issue': 'Page has duplicate title',
                'type': 'seo',
            })

        # Make sure pages have a description
        if page['description'] == '':
            logger.warning(f"Page {page['url']} has no description")
            insights.append({
                'url': page['url'],
                'issue': 'Page has no description',
                'type': 'seo',
            })

        # Make sure pages have a description between 70 and 160 characters
        if len(page['description']) < 70 or len(page['description']) > 160:
            logger.warning(f"Page {page['url']} has description of length {len(page['description'])}")
            insights.append({
                'url': page['url'],
                'item': page['description'],
                'issue': 'Page description is not between 70 and 160 characters',
                'type': 'seo',
            })

        # Make sure pages have a unique description
        if page['description'] in [p['description'] for p in self.get_crawl_output if p['url'] != page['url']]:
            logger.warning(f"Page {page['url']} has duplicate description")
            insights.append({
                'url': page['url'],
                'item': page['description'],
                'issue': 'Page has duplicate description',
                'type': 'seo',
            })

        # Make sure pages have an h1
        if page['h1'] == '':
            logger.warning(f"Page {page['url']} has no h1")
            insights.append({
                'url': page['url'],
                'issue': 'Page has no h1',
                'type': 'seo',
            })

        # Make sure pages have an h1 between 20 and 70 characters
        if len(page['h1']) < 20 or len(page['h1']) > 70:
            logger.warning(f"Page {page['url']} has h1 of length {len(page['h1'])}")
            insights.append({
                'url': page['url'],
                'item': page['h1'],
                'issue': 'Page h1 is not between 20 and 70 characters',
                'type': 'seo',
            })

        # Make sure pages have a unique h1
        if page['h1'] in [p['h1'] for p in self.get_crawl_output if p['url'] != page['url']]:
            logger.warning(f"Page {page['url']} has duplicate h1")
            insights.append({
                'url': page['url'],
                'item': page['h1'],
                'issue': 'Page has duplicate h1',
                'type': 'seo',
            })

        # Make sure pages have a canonical url
        if page['canonical'] == '':
            logger.warning(f"Page {page['url']} has no canonical url")
            insights.append({
                'url': page['url'],
                'issue': 'Page has no canonical url',
                'type': 'seo',
            })

        return insights

    def parse_crawl(self):
        insights = []
        for page in self.get_crawl_output:
            insights.extend(self.parse_page(page))
        self.crawler_insights = insights
        self.save(update_fields=['crawler_insights'])

    def crawl_site(self):
        run_seo_spider(self.url)
        self.parse_crawl()


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
    next_lighthouse_run_at = models.DateTimeField(blank=True, null=True)

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
            if scores:
                self.lighthouse_scores = scores
                self.save(update_fields=["lighthouse_scores"])
        except Exception:
            pass

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
        ]
        get_latest_by = "created_at"

    def __str__(self):
        return f"{self.property.url} - {self.created_at} - {self.status_code}"
