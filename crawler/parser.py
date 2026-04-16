"""HTML parsing: raw body -> structured page dict."""
import hashlib
import json
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


def parse_html(body, url):
    """Extract everything the checks need from one HTML page.

    Returns a dict with title, meta, headings, links, images, resources,
    forms, json_ld, word count, text hash, favicon, lang, viewport, robots.
    """
    soup = BeautifulSoup(body, "lxml")

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    def meta_name(name):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    def meta_property(prop):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    description = meta_name("description")
    robots_meta = meta_name("robots")
    viewport = meta_name("viewport")

    canonical_tag = soup.find("link", rel="canonical")
    canonical = ""
    if canonical_tag and canonical_tag.get("href"):
        canonical = urljoin(url, canonical_tag["href"].strip())

    og = {
        "title": meta_property("og:title"),
        "description": meta_property("og:description"),
        "image": meta_property("og:image"),
        "url": meta_property("og:url"),
    }

    twitter = {
        "card": meta_name("twitter:card"),
        "title": meta_name("twitter:title"),
        "description": meta_name("twitter:description"),
    }

    html_tag = soup.find("html")
    lang = html_tag.get("lang", "").strip() if html_tag else ""

    headings = {f"h{i}": [] for i in range(1, 7)}
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            headings[f"h{level}"].append(h.get_text(" ", strip=True))

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        rel = a.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        links.append(
            {
                "url": urljoin(url, href),
                "text": a.get_text(" ", strip=True),
                "rel": list(rel),
            }
        )

    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        alt = img.get("alt")  # None = missing attribute, "" = explicitly empty
        images.append(
            {
                "src": urljoin(url, src) if src else "",
                "alt": alt,
            }
        )

    resources = []
    for tag in soup.find_all(["script", "link", "img", "iframe", "source"]):
        src = tag.get("src") or tag.get("href")
        if src and src.strip():
            resources.append(urljoin(url, src.strip()))

    json_ld = []
    for s in soup.find_all("script", type="application/ld+json"):
        raw = s.string or s.get_text() or ""
        if not raw.strip():
            continue
        try:
            json_ld.append(json.loads(raw))
        except (ValueError, TypeError):
            json_ld.append(None)  # parse error

    favicon = ""
    for link in soup.find_all("link", rel=True):
        rels = link.get("rel", [])
        if isinstance(rels, str):
            rels = rels.split()
        if any("icon" in r.lower() for r in rels):
            href = link.get("href", "").strip()
            if href:
                favicon = urljoin(url, href)
                break

    forms = []
    for form in soup.find_all("form"):
        inputs = []
        for i in form.find_all(["input", "textarea", "select"]):
            inputs.append(
                {
                    "type": i.get("type", "text"),
                    "name": i.get("name"),
                    "id": i.get("id"),
                    "aria_label": i.get("aria-label"),
                }
            )
        label_fors = {lb.get("for") for lb in form.find_all("label") if lb.get("for")}
        forms.append(
            {
                "action": urljoin(url, form.get("action", "")) if form.get("action") else url,
                "inputs": inputs,
                "label_fors": list(label_fors),
            }
        )

    # Visible text for word count + duplicate detection.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    word_count = len(text.split())
    text_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "robots_meta": robots_meta,
        "viewport": viewport,
        "lang": lang,
        "og": og,
        "twitter": twitter,
        "headings": headings,
        "links": links,
        "images": images,
        "resources": resources,
        "json_ld": json_ld,
        "favicon": favicon,
        "forms": forms,
        "word_count": word_count,
        "text_hash": text_hash,
    }
