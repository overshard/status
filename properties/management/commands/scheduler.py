import threading
import time
import queue

from django import db
from django.core.management.base import BaseCommand
from django.utils import timezone

from properties.models import Property, Check


q = queue.Queue()


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

    def queue_add(self, property_id, lighthouse=False):
        q.put((property_id, lighthouse))

    def queue_process(self):
        while True:
            """
            Use 2 threads to process each item in the queue. If lighthouse == False
            then use thread_target in the thread_target function. If lighthouse == True
            then use thread_target_lighthouse in the thread_target_lighthouse function.
            """
            if not q.empty():
                threads = []
                for i in range(2):
                    q_data = q.get()
                    if q_data[1]:
                        t = threading.Thread(target=self.thread_target_lighthouse, args=(q_data[0],))
                    else:
                        t = threading.Thread(target=self.thread_target, args=(q_data[0],))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                    q.task_done()
            time.sleep(1)

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        # Start queue_process thread
        t = threading.Thread(target=self.queue_process)
        t.daemon = True
        t.start()

        # Start our loop to check properties every 30 seconds
        while True:
            # Do our standard checks
            # Only run 10 at a time
            properties = [p for p in Property.objects.all() if p.should_check()]
            for p in properties:
                p.next_run_at = p.get_next_run_at()
                p.last_run_at = timezone.now()
                p.save(update_fields=["next_run_at", "last_run_at"])

            properties = [p.id for p in properties]
            db.connections.close_all()
            for p_id in properties:
                self.queue_add(p_id)

            self.clean_checks()

            # Do our daily lighthouse checks
            # Only run 1 of these checks per loop to avoid overloading the server
            properties = [p for p in Property.objects.all() if p.should_check_lighthouse()]
            for p in properties:
                p.next_lighthouse_run_at = p.get_next_run_at_lighthouse()
                p.last_lighthouse_run_at = timezone.now()
                p.save(update_fields=["next_lighthouse_run_at", "last_lighthouse_run_at"])

            properties = [p.id for p in properties]
            db.connections.close_all()
            for p_id in properties:
                self.queue_add(p_id, True)

            self.stdout.write("[Scheduler] Sleeping scheduler for 30 seconds...")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
