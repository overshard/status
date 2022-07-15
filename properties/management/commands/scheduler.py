import threading
import time

from django import db
from django.core.management.base import BaseCommand
from django.utils import timezone

from properties.models import Property, Check


class Command(BaseCommand):
    def clean_checks(self):
        """
        Clean checks older than 3 days.
        """
        self.stdout.write("[Scheduler] Cleaning checks older than 3 days...")
        Check.objects.filter(created_at__lt=timezone.now() - timezone.timedelta(days=3)).delete()
        self.stdout.write("[Scheduler] Cleaned checks older than 3 days.")

    def thread_target(self, property_id):
        property = Property.objects.get(id=property_id)
        self.stdout.write("[Scheduler] Checking status {}".format(property.url))
        property.process_check()

    def thread_target_lighthouse(self, property_id):
        property = Property.objects.get(id=property_id)
        self.stdout.write("[Scheduler] Checking lighthouse {}".format(property.url))
        property.process_check_lighthouse()

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        while True:
            # Do our standard checks
            # Only run 10 at a time
            properties = [p for p in Property.objects.all() if p.should_check()]
            properties = properties[:10]
            for p in properties:
                p.next_run_at = p.get_next_run_at()
                p.last_run_at = timezone.now()
                p.save(update_fields=["next_run_at", "last_run_at"])

            properties = [p.id for p in properties]
            db.connections.close_all()
            for p_id in properties:
                t = threading.Thread(target=self.thread_target, args=(p_id,))
                t.daemon = True
                t.start()

            self.clean_checks()

            # # Do our daily lighthouse checks
            # # Only run 1 of these checks per loop to avoid overloading the server
            # properties = [p for p in Property.objects.all() if p.should_check_lighthouse()]
            # properties = properties[:1]
            # for p in properties:
            #     p.next_lighthouse_run_at = p.get_next_run_at_lighthouse()
            #     p.last_lighthouse_run_at = timezone.now()
            #     p.save(update_fields=["next_lighthouse_run_at", "last_lighthouse_run_at"])

            # properties = [p.id for p in properties]
            # db.connections.close_all()
            # for p_id in properties:
            #     t = threading.Thread(target=self.thread_target_lighthouse, args=(p_id,))
            #     t.daemon = True
            #     t.start()

            self.stdout.write("[Scheduler] Sleeping scheduler for 10 seconds...")
            try:
                time.sleep(10)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
