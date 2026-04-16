"""HTTP fetching, robots.txt, and sitemap loading."""
import logging
import urllib.robotparser
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

USER_AGENT = "status (+https://status.bythewood.me)"
PAGE_CAP = 500
CONCURRENCY = 4
REQUEST_TIMEOUT = (5, 15)
EXTERNAL_LINK_TIMEOUT = (3, 8)
# Hard deadline for a single site crawl. Scheduler JOIN_TIMEOUT must exceed this.
CRAWL_DEADLINE_SECONDS = 540


@dataclass
class FetchResult:
    url: str
    requested_url: str
    status: int
    headers: dict
    body: bytes
    content_type: str
    elapsed_ms: int
    redirect_chain: list = field(default_factory=list)
    error: str = ""


def make_session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch(session, url):
    """GET a URL and return a FetchResult. Body is only captured for HTML."""
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        chain = [(h.status_code, h.url) for h in r.history]
        chain.append((r.status_code, r.url))
        content_type = r.headers.get("content-type", "").lower()
        body = r.content if "text/html" in content_type else b""
        return FetchResult(
            url=r.url,
            requested_url=url,
            status=r.status_code,
            headers=dict(r.headers),
            body=body,
            content_type=content_type,
            elapsed_ms=int(r.elapsed.total_seconds() * 1000),
            redirect_chain=chain,
        )
    except requests.RequestException as e:
        return FetchResult(
            url=url,
            requested_url=url,
            status=0,
            headers={},
            body=b"",
            content_type="",
            elapsed_ms=0,
            error=str(e),
        )


def head_status(session, url):
    """Cheap check for external links. Returns the status code (0 on error)."""
    try:
        r = session.head(url, timeout=EXTERNAL_LINK_TIMEOUT, allow_redirects=True)
        # Some servers reject HEAD with 405/403 but accept GET.
        if r.status_code in (403, 405, 501):
            r = session.get(
                url, timeout=EXTERNAL_LINK_TIMEOUT, allow_redirects=True, stream=True
            )
            r.close()
        return r.status_code
    except requests.RequestException:
        return 0


def load_robots(session, base_origin):
    """Fetch robots.txt. Returns (RobotFileParser, robots_url, raw_text_or_None)."""
    robots_url = f"{base_origin}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    text = None
    try:
        r = session.get(robots_url, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            text = r.text
            rp.parse(text.splitlines())
    except requests.RequestException:
        pass
    return rp, robots_url, text


def _parse_sitemap_xml(body):
    """Return all <loc> values. Distinguishing index vs urlset is handled upstream."""
    soup = BeautifulSoup(body, "xml")
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]


def load_sitemap(session, base_origin, robots_text):
    """Return list of URLs from sitemap(s). Follows sitemap indexes one level.

    Checks Sitemap: entries in robots.txt first, falls back to /sitemap.xml.
    """
    candidates = []
    if robots_text:
        for line in robots_text.splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    if not candidates:
        candidates.append(f"{base_origin}/sitemap.xml")

    seen = set()
    urls = []
    to_fetch = list(candidates)
    while to_fetch and len(seen) < 20:
        smurl = to_fetch.pop()
        if smurl in seen:
            continue
        seen.add(smurl)
        try:
            r = session.get(smurl, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue
            for loc in _parse_sitemap_xml(r.content):
                # Sub-sitemaps end in .xml; everything else is a page URL.
                if loc.lower().endswith(".xml") or "sitemap" in loc.lower():
                    to_fetch.append(loc)
                else:
                    urls.append(loc)
        except requests.RequestException:
            continue
    return urls


def same_site(url, host):
    """True if `url` is on `host` or its www./apex counterpart."""
    u = urlparse(url).netloc.lower()
    h = host.lower()
    if not u:
        return False
    if u == h:
        return True
    if u == "www." + h or h == "www." + u:
        return True
    return False
