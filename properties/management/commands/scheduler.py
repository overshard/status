import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from django import db
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from properties.models import Check, Property

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    # Two pools so slow lighthouse/crawler work can't starve quick HTTP pings.
    SLOW_WORKERS = 2
    FAST_WORKERS = 2
    CYCLE_SECONDS = 30
    CLEANUP_INTERVAL_SECONDS = 86400

    def __init__(self):
        super().__init__()
        self._stop = threading.Event()
        self._last_cleanup = None

    def handle(self, *args, **options):
        self.stdout.write("[Scheduler] Starting scheduler...")

        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

        # Clear any running/queued states left over from a prior crash so
        # rows don't sit stuck and block new runs.
        Property.objects.filter(crawl_state__in=["queued", "running"]).update(
            crawl_state="idle"
        )
        Property.objects.filter(lighthouse_state__in=["queued", "running"]).update(
            lighthouse_state="idle"
        )

        slow = ThreadPoolExecutor(
            max_workers=self.SLOW_WORKERS, thread_name_prefix="slow"
        )
        fast = ThreadPoolExecutor(
            max_workers=self.FAST_WORKERS, thread_name_prefix="fast"
        )

        try:
            while not self._stop.is_set():
                try:
                    self._enqueue_status(fast)
                    self._enqueue_lighthouse(slow)
                    self._enqueue_crawler(slow)
                    self.reset_wedged_states()
                    self._maybe_cleanup()
                except Exception:
                    logger.exception("[Scheduler] cycle error")

                self.stdout.write(
                    f"[Scheduler] Sleeping scheduler for {self.CYCLE_SECONDS} seconds..."
                )
                self._stop.wait(self.CYCLE_SECONDS)
        finally:
            self.stdout.write("[Scheduler] Stopping scheduler...")
            slow.shutdown(wait=False, cancel_futures=True)
            fast.shutdown(wait=False, cancel_futures=True)

    def _on_signal(self, signum, frame):
        self.stdout.write(f"[Scheduler] Received signal {signum}, shutting down...")
        self._stop.set()

    def reset_wedged_states(self):
        """Flip running rows back to idle once they've overrun their deadline.

        Only "running" rows count as wedged. "queued" rows are waiting their
        turn in the thread pool and will be picked up when a worker frees up;
        flipping them here would mark healthy backlog as failed whenever the
        user fans out manual re-triggers.

        The startup path in handle() also wipes any leftover queued/running
        state unconditionally to cover crashes.
        """
        now = timezone.now()
        crawl_cutoff = now - timezone.timedelta(seconds=900)
        lh_cutoff = now - timezone.timedelta(seconds=300)

        Property.objects.filter(
            crawl_state="running",
            crawl_started_at__lt=crawl_cutoff,
        ).update(
            crawl_state="idle",
            last_crawl_error="Crawl timed out or was interrupted",
        )

        Property.objects.filter(
            lighthouse_state="running",
            lighthouse_started_at__lt=lh_cutoff,
        ).update(
            lighthouse_state="idle",
            last_lighthouse_error="Lighthouse run timed out or was interrupted",
        )

    def _maybe_cleanup(self):
        now = timezone.now()
        if (
            self._last_cleanup
            and (now - self._last_cleanup).total_seconds()
            < self.CLEANUP_INTERVAL_SECONDS
        ):
            return
        self.stdout.write("[Scheduler] Cleaning checks older than 3 days...")
        Check.objects.filter(
            created_at__lt=now - timezone.timedelta(days=3)
        ).delete()
        self._last_cleanup = now

    def _enqueue_status(self, pool):
        now = timezone.now()
        due = list(
            Property.objects.filter(
                Q(last_run_at__isnull=True)
                | Q(next_run_at__isnull=True)
                | Q(next_run_at__lte=now)
            )
        )
        for p in due:
            p.next_run_at = p.get_next_run_at()
            p.last_run_at = timezone.now()
            p.save(update_fields=["next_run_at", "last_run_at"])
            pool.submit(self._run_status, p.id)
        db.connections.close_all()

    def _enqueue_lighthouse(self, pool):
        now = timezone.now()
        due = list(
            Property.objects.filter(
                Q(last_lighthouse_run_at__isnull=True)
                | Q(next_lighthouse_run_at__isnull=True)
                | Q(next_lighthouse_run_at__lte=now)
            ).exclude(lighthouse_state__in=["queued", "running"])
        )
        for p in due:
            p.next_lighthouse_run_at = p.get_next_run_at_lighthouse()
            p.last_lighthouse_run_at = timezone.now()
            p.lighthouse_state = "queued"
            p.save(
                update_fields=[
                    "next_lighthouse_run_at",
                    "last_lighthouse_run_at",
                    "lighthouse_state",
                ]
            )
            pool.submit(self._run_lighthouse, p.id)
        db.connections.close_all()

    def _enqueue_crawler(self, pool):
        now = timezone.now()
        due = list(
            Property.objects.filter(
                Q(last_run_at_crawler__isnull=True)
                | Q(next_run_at_crawler__isnull=True)
                | Q(next_run_at_crawler__lte=now)
            ).exclude(crawl_state__in=["queued", "running"])
        )
        for p in due:
            p.next_run_at_crawler = p.get_next_run_at_crawl()
            p.last_run_at_crawler = timezone.now()
            p.crawl_state = "queued"
            p.save(
                update_fields=[
                    "next_run_at_crawler",
                    "last_run_at_crawler",
                    "crawl_state",
                ]
            )
            pool.submit(self._run_crawler, p.id)
        db.connections.close_all()

    def _run_status(self, property_id):
        try:
            prop = Property.objects.get(id=property_id)
            self.stdout.write(f"[Scheduler] Checking status {prop.url}")
            prop.process_check()
        except Exception:
            logger.exception("[Scheduler] status check failed for %s", property_id)
        finally:
            db.close_old_connections()

    def _run_lighthouse(self, property_id):
        try:
            prop = Property.objects.get(id=property_id)
            self.stdout.write(f"[Scheduler] Checking lighthouse {prop.url}")
            prop.process_check_lighthouse()
        except Exception:
            logger.exception("[Scheduler] lighthouse failed for %s", property_id)
        finally:
            db.close_old_connections()

    def _run_crawler(self, property_id):
        try:
            prop = Property.objects.get(id=property_id)
            self.stdout.write(f"[Scheduler] Checking crawler {prop.url}")
            prop.crawl_site()
        except Exception:
            logger.exception("[Scheduler] crawler failed for %s", property_id)
        finally:
            db.close_old_connections()
