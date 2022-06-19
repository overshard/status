import time
from multiprocessing import Process

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import Check, Property


class Command(BaseCommand):
    def run_check(self, property):
        try:
            response = requests.get(property.url, timeout=5)
            response_time = response.elapsed.total_seconds() * 1000
            status_code = response.status_code
            headers = response.headers
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            response_time = 5000
            status_code = 0
            headers = {}
        Check.objects.create(
            property=property,
            status_code=status_code,
            response_time=response_time,
            headers=dict(headers),
        )
        if property.user.discord_webhook_url and status_code != 200:
            payload = {
                "username": "Status Check",
                "content": f"{property.url} is down!",
                "embeds": [
                    {
                        "title": "Status Check",
                        "description": f"{property.url} is down!",
                        "color": 16711680,
                        "timestamp": timezone.now().isoformat(),
                        "footer": {"text": "Status Check"},
                    }
                ],
            }
            requests.post(property.user.discord_webhook_url, json=payload)

        self.stdout.write("[Scheduler] Checked {}".format(property.url))

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        while True:
            """
            Get all properties and find which ones we "should_check". From there
            use multiprocessing to run multiple checks at the same time.
            """
            properties = [p for p in Property.objects.all() if p.should_check()]
            properties = []
            for p in Property.objects.all():
                if p.should_check():
                    properties.append(p)
                    p.last_run_at = timezone.now()
                    p.next_run_at = p.get_next_run_at()
                    p.save()
            if properties:
                self.stdout.write(
                    "[Scheduler] Running {} checks...".format(len(properties))
                )
                processes = [
                    Process(target=self.run_check, args=(p,)) for p in properties
                ]
                for p in processes:
                    p.daemon = True
                    p.start()

            self.stdout.write("[Scheduler] Sleeping scheduler for 30 seconds...")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
