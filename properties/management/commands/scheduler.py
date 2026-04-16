import threading
import time
import queue

from django import db
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from properties.models import Property, Check


q = queue.Queue()
q_status = queue.Queue()


class Command(BaseCommand):
    def clean_checks(self):
        """
        Clean checks older than 3 days.
        """
        self.stdout.write("[Scheduler] Cleaning checks older than 3 days...")
        Check.objects.filter(created_at__lt=timezone.now() - timezone.timedelta(days=3)).delete()
        self.stdout.write("[Scheduler] Cleaned checks older than 3 days.")

    def reset_wedged_states(self):
        """Flip stale running/queued states back to idle.

        Runs on startup (catches states left over from a crashed scheduler)
        and each cycle (catches threads that overran JOIN_TIMEOUT).
        """
        now = timezone.now()
        crawl_cutoff = now - timezone.timedelta(seconds=900)
        lh_cutoff = now - timezone.timedelta(seconds=300)

        Property.objects.filter(
            crawl_state__in=["queued", "running"],
        ).filter(
            Q(crawl_started_at__isnull=True) | Q(crawl_started_at__lt=crawl_cutoff)
        ).update(
            crawl_state="idle",
            last_crawl_error="Crawl timed out or was interrupted",
        )

        Property.objects.filter(
            lighthouse_state__in=["queued", "running"],
        ).filter(
            Q(lighthouse_started_at__isnull=True) | Q(lighthouse_started_at__lt=lh_cutoff)
        ).update(
            lighthouse_state="idle",
            last_lighthouse_error="Lighthouse run timed out or was interrupted",
        )

    def thread_target(self, property_id):
        property = Property.objects.get(id=property_id)
        self.stdout.write("[Scheduler] Checking status {}".format(property.url))
        property.process_check()

    def thread_target_lighthouse(self, property_id):
        property = Property.objects.get(id=property_id)
        self.stdout.write("[Scheduler] Checking lighthouse {}".format(property.url))
        property.process_check_lighthouse()

    def thread_target_crawler(self, property_id):
        property = Property.objects.get(id=property_id)
        self.stdout.write("[Scheduler] Checking crawler {}".format(property.url))
        property.crawl_site()

    def queue_add(self, property_id, property_type):
        q.put((property_id, property_type))

    def queue_add_status(self, property_id, property_type):
        q_status.put((property_id, property_type))

    def queue_process(self):
        # Cap on join() so a wedged lighthouse/crawler can't freeze the queue
        # indefinitely. Must exceed both status.lighthouse.SUBPROCESS_TIMEOUT_SECONDS
        # (180s) and crawler.fetcher.CRAWL_DEADLINE_SECONDS (540s) so a normal
        # slow run still completes inside the window.
        JOIN_TIMEOUT = 900
        while True:
            if not q.empty():
                threads = []
                for i in range(2):
                    if q.empty():
                        break
                    q_data = q.get()
                    if q_data[1] == "lighthouse":
                        t = threading.Thread(target=self.thread_target_lighthouse, args=(q_data[0],))
                    elif q_data[1] == "crawler":
                        t = threading.Thread(target=self.thread_target_crawler, args=(q_data[0],))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join(timeout=JOIN_TIMEOUT)
                    if t.is_alive():
                        self.stdout.write(
                            "[Scheduler] Thread still running after {}s, abandoning".format(JOIN_TIMEOUT)
                        )
                    q.task_done()
            time.sleep(1)

    def queue_process_status(self):
        while True:
            if not q_status.empty():
                threads = []
                for i in range(2):
                    if q_status.empty():
                        break
                    q_data = q_status.get()
                    if q_data[1] != "status":
                        q_status.task_done()
                        continue
                    t = threading.Thread(target=self.thread_target, args=(q_data[0],))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                    q_status.task_done()
            time.sleep(1)

    def queue_check_status(self):
        now = timezone.now()
        due = Property.objects.filter(
            Q(last_run_at__isnull=True) | Q(next_run_at__isnull=True) | Q(next_run_at__lte=now)
        )
        properties = list(due)
        for p in properties:
            p.next_run_at = p.get_next_run_at()
            p.last_run_at = timezone.now()
            p.save(update_fields=["next_run_at", "last_run_at"])

        properties = [p.id for p in properties]
        db.connections.close_all()
        for p_id in properties:
            self.queue_add_status(p_id, "status")

    def queue_check_lighthouse(self):
        now = timezone.now()
        due = Property.objects.filter(
            Q(last_lighthouse_run_at__isnull=True)
            | Q(next_lighthouse_run_at__isnull=True)
            | Q(next_lighthouse_run_at__lte=now)
        ).exclude(lighthouse_state__in=["queued", "running"])
        properties = list(due)
        for p in properties:
            p.next_lighthouse_run_at = p.get_next_run_at_lighthouse()
            p.last_lighthouse_run_at = timezone.now()
            p.lighthouse_state = "queued"
            p.save(update_fields=[
                "next_lighthouse_run_at",
                "last_lighthouse_run_at",
                "lighthouse_state",
            ])

        properties = [p.id for p in properties]
        db.connections.close_all()
        for p_id in properties:
            self.queue_add(p_id, "lighthouse")

    def queue_check_crawler(self):
        now = timezone.now()
        due = Property.objects.filter(
            Q(last_run_at_crawler__isnull=True)
            | Q(next_run_at_crawler__isnull=True)
            | Q(next_run_at_crawler__lte=now)
        ).exclude(crawl_state__in=["queued", "running"])
        properties = list(due)
        for p in properties:
            p.next_run_at_crawler = p.get_next_run_at_crawl()
            p.last_run_at_crawler = timezone.now()
            p.crawl_state = "queued"
            p.save(update_fields=[
                "next_run_at_crawler",
                "last_run_at_crawler",
                "crawl_state",
            ])

        properties = [p.id for p in properties]
        db.connections.close_all()
        for p_id in properties:
            self.queue_add(p_id, "crawler")

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        # Clear any running/queued states left over from a prior crash so
        # that rows don't sit stuck and block new runs.
        Property.objects.filter(crawl_state__in=["queued", "running"]).update(
            crawl_state="idle"
        )
        Property.objects.filter(lighthouse_state__in=["queued", "running"]).update(
            lighthouse_state="idle"
        )

        # Start queue_process thread
        t = threading.Thread(target=self.queue_process)
        t.daemon = True
        t.start()

        # Start queue_process thread
        t = threading.Thread(target=self.queue_process_status)
        t.daemon = True
        t.start()

        # Start our loop to check properties every 30 seconds
        while True:
            self.queue_check_status()
            self.queue_check_lighthouse()
            self.queue_check_crawler()
            self.reset_wedged_states()
            self.clean_checks()

            self.stdout.write("[Scheduler] Sleeping scheduler for 30 seconds...")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                self.stdout.write("[Scheduler] Stopping scheduler...")
                break
