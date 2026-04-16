"""Entry point for the SEO crawler.

Crawls a site, runs checks, writes per-page debug output, and returns
a list of insights. Designed to run in-process; no subprocess required.
"""
import json
import logging
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from django.conf import settings

from . import checks
from .fetcher import (
    CONCURRENCY,
    CRAWL_DEADLINE_SECONDS,
    PAGE_CAP,
    fetch,
    head_status,
    load_robots,
    load_sitemap,
    make_session,
    same_site,
)
from .parser import parse_html


logger = logging.getLogger(__name__)


def _output_path(host):
    base = "crawler_output" if settings.DEBUG else "/data/crawler_output"
    return os.path.join(base, f"{host}.json")


def _normalize_url(url):
    # Drop fragments; keep query strings since they often distinguish pages.
    p = urlparse(url)
    cleaned = p._replace(fragment="").geturl()
    return cleaned.rstrip("/") or cleaned


def crawl(start_url):
    """Fetch up to PAGE_CAP pages from the same host and collect metadata."""
    session = make_session()

    parsed = urlparse(start_url)
    host = parsed.netloc
    base_origin = f"{parsed.scheme}://{parsed.netloc}"

    rp, robots_url, robots_text = load_robots(session, base_origin)
    sitemap_urls = load_sitemap(session, base_origin, robots_text)

    seen = set()
    queue = deque()
    pages = []
    fetched = set()
    deadline = time.time() + CRAWL_DEADLINE_SECONDS

    def enqueue(url):
        n = _normalize_url(url)
        if n in seen:
            return
        seen.add(n)
        queue.append(url)

    enqueue(start_url)
    # Seed with sitemap URLs so sitemap-only pages get crawled too.
    for url in sitemap_urls[:PAGE_CAP]:
        if same_site(url, host):
            enqueue(url)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        while queue and len(pages) < PAGE_CAP and time.time() < deadline:
            batch = []
            while queue and len(batch) < CONCURRENCY and len(pages) + len(batch) < PAGE_CAP:
                url = queue.popleft()
                if not rp.can_fetch("*", url):
                    continue
                batch.append(url)
            if not batch:
                break

            futures = [ex.submit(fetch, session, u) for u in batch]
            for f in as_completed(futures):
                r = f.result()
                # Different requested URLs can collapse to the same final URL
                # after redirects. Drop duplicates so checks don't double-flag.
                final_key = _normalize_url(r.url)
                if final_key in fetched:
                    seen.add(final_key)
                    continue
                fetched.add(final_key)
                is_html = r.status == 200 and "text/html" in r.content_type
                page = {
                    "url": r.url,
                    "requested_url": r.requested_url,
                    "status": r.status,
                    "content_type": r.content_type,
                    "elapsed_ms": r.elapsed_ms,
                    "bytes": len(r.body),
                    "headers": r.headers,
                    "redirect_chain": r.redirect_chain,
                    "error": r.error,
                    "is_html": is_html,
                }
                if is_html:
                    try:
                        page.update(parse_html(r.body, r.url))
                    except Exception:
                        logger.exception("[crawler] parse failed for %s", r.url)
                        page["is_html"] = False
                    else:
                        for link in page.get("links", []):
                            lu = link["url"]
                            if same_site(lu, host):
                                enqueue(lu)
                # Ensure the final redirected URL is considered "seen" too, so
                # we don't refetch it on another pass.
                seen.add(_normalize_url(r.url))
                pages.append(page)

    if time.time() >= deadline:
        logger.warning(
            "[crawler] hit deadline for %s after %d pages",
            start_url,
            len(pages),
        )

    # External link HEAD check. Only checks same unique URL once.
    external_links = set()
    for p in pages:
        if not p.get("is_html"):
            continue
        for link in p.get("links", []):
            if not same_site(link["url"], host):
                external_links.add(link["url"])

    external_link_status = {}
    if external_links and time.time() < deadline:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            futures = {ex.submit(head_status, session, u): u for u in external_links}
            for f in as_completed(futures):
                url = futures[f]
                try:
                    external_link_status[url] = f.result()
                except Exception:
                    external_link_status[url] = 0

    return {
        "start_url": start_url,
        "host": host,
        "pages": pages,
        "external_link_status": external_link_status,
        "sitemap_urls": sitemap_urls,
        "robots": {
            "url": robots_url,
            "exists": robots_text is not None,
            "raw": robots_text,
            "references_sitemap": bool(
                robots_text
                and any(
                    line.lower().startswith("sitemap:")
                    for line in robots_text.splitlines()
                )
            ),
        },
    }


def run_checks(crawl_result):
    """Build a ctx dict and run every check. Returns the flat insight list."""
    ctx = {
        "start_url": crawl_result["start_url"],
        "host": crawl_result["host"],
        "pages": crawl_result["pages"],
        "html_pages": [p for p in crawl_result["pages"] if p.get("is_html")],
        "status_map": {p["url"]: p["status"] for p in crawl_result["pages"]},
        "external_link_status": crawl_result["external_link_status"],
        "sitemap_urls": crawl_result["sitemap_urls"],
        "robots": crawl_result["robots"],
    }

    insights = []
    for fn in checks.ALL_CHECKS:
        try:
            insights.extend(fn(ctx))
        except Exception:
            logger.exception("[crawler] check %s failed", fn.__name__)
    return insights


def _write_debug_output(crawl_result):
    host = crawl_result["host"]
    path = _output_path(host)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            for p in crawl_result["pages"]:
                # Strip bulky fields from the debug file.
                snapshot = {k: v for k, v in p.items() if k != "headers"}
                f.write(json.dumps(snapshot, default=str) + "\n")
    except OSError:
        logger.exception("[crawler] failed writing debug output to %s", path)


def run_seo_spider(url):
    """Crawl `url`, write debug output, return list of insight dicts."""
    start = time.time()
    logger.info("[crawler] starting %s", url)
    result = crawl(url)
    insights = run_checks(result)
    _write_debug_output(result)
    logger.info(
        "[crawler] done %s - %d pages, %d insights, %.1fs",
        url,
        len(result["pages"]),
        len(insights),
        time.time() - start,
    )
    return insights
