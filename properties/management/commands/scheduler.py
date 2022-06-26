import threading
import time

from django import db
from django.core.management.base import BaseCommand
from django.utils import timezone

from properties.models import Property


class Command(BaseCommand):
    def thread_target(self, property_id):
        property = Property.objects.get(id=property_id)
        property.process_check()

        self.stdout.write("[Scheduler] Checked {}".format(property.url))

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        while True:
            properties = [p for p in Property.objects.all() if p.should_check()]
            for p in properties:
                p.next_run_at = p.get_next_run_at()
                p.last_run_at = timezone.now()
                p.save()

            properties = [p.id for p in properties]
            db.connections.close_all()
            for p_id in properties:
                threading.Thread(target=self.thread_target, args=(p_id,)).start()

            self.stdout.write("[Scheduler] Sleeping scheduler for 30 seconds...")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
