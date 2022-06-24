import threading
import time

import requests
from django import db
from django.core.management.base import BaseCommand
from django.utils import timezone

from properties.models import Check, Property


class Command(BaseCommand):
    def run_check(self, property_id):
        property = Property.objects.get(id=property_id)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.115 Safari/537.36 Status/1.0.0"
            }
            response = requests.get(property.url, timeout=5, headers=headers)
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
        Check.objects.create(
            property=property,
            status_code=status_code,
            response_time=response_time,
            headers=dict(headers),
        )
        if property.user.discord_webhook_url and status_code != 200:
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
            requests.post(property.user.discord_webhook_url, json=payload)

        self.stdout.write("[Scheduler] Checked {}".format(property.url))

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        while True:
            properties = [p.id for p in Property.objects.all() if p.should_check()]
            db.connections.close_all()
            for property in properties:
                threading.Thread(target=self.run_check, args=(property,)).start()
                property.next_run_at = property.get_next_run_at()
                property.last_run_at = timezone.now()
                property.save()

            self.stdout.write("[Scheduler] Sleeping scheduler for 30 seconds...")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
