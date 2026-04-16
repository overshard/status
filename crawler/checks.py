"""SEO / accessibility / performance / content / security checks.

Every check takes a single `ctx` dict and returns a list of insight dicts.
Insight shape: {url, issue, item, type, severity}
"""
from urllib.parse import urlparse

from .fetcher import same_site


TYPE_SEO = "seo"
TYPE_LINKS = "links"
TYPE_ACCESSIBILITY = "accessibility"
TYPE_CONTENT = "content"
TYPE_PERFORMANCE = "performance"
TYPE_SECURITY = "security"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

REDIRECT_CODES = {301, 302, 303, 307, 308}


def _insight(url, issue, type_, severity, item=""):
    return {
        "url": url,
        "issue": issue,
        "item": item,
        "type": type_,
        "severity": severity,
    }


def _normalize(s):
    return " ".join(s.lower().split()) if s else ""


def _group_by(pages, field):
    seen = {}
    for p in pages:
        val = p.get(field, "")
        if val:
            seen.setdefault(_normalize(val), []).append(p)
    return seen


# ---------- core metadata ----------

def check_title_missing(ctx):
    return [
        _insight(p["url"], "Page has no title", TYPE_SEO, SEVERITY_ERROR)
        for p in ctx["html_pages"]
        if not p.get("title")
    ]


def check_title_length(ctx):
    out = []
    for p in ctx["html_pages"]:
        t = p.get("title", "")
        if t and not (30 <= len(t) <= 60):
            out.append(
                _insight(
                    p["url"],
                    f"Title length is {len(t)} chars (recommended 30-60)",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=t,
                )
            )
    return out


def check_duplicate_titles(ctx):
    out = []
    for _, group in _group_by(ctx["html_pages"], "title").items():
        if len(group) > 1:
            for p in group:
                out.append(
                    _insight(
                        p["url"],
                        "Duplicate title",
                        TYPE_SEO,
                        SEVERITY_WARNING,
                        item=p["title"],
                    )
                )
    return out


def check_description_missing(ctx):
    return [
        _insight(p["url"], "Page has no meta description", TYPE_SEO, SEVERITY_ERROR)
        for p in ctx["html_pages"]
        if not p.get("description")
    ]


def check_description_length(ctx):
    out = []
    for p in ctx["html_pages"]:
        d = p.get("description", "")
        if d and not (70 <= len(d) <= 160):
            out.append(
                _insight(
                    p["url"],
                    f"Description length is {len(d)} chars (recommended 70-160)",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=d,
                )
            )
    return out


def check_duplicate_descriptions(ctx):
    out = []
    for _, group in _group_by(ctx["html_pages"], "description").items():
        if len(group) > 1:
            for p in group:
                out.append(
                    _insight(
                        p["url"],
                        "Duplicate meta description",
                        TYPE_SEO,
                        SEVERITY_WARNING,
                        item=p["description"],
                    )
                )
    return out


def check_h1_missing(ctx):
    return [
        _insight(p["url"], "Page has no h1", TYPE_SEO, SEVERITY_ERROR)
        for p in ctx["html_pages"]
        if not p.get("headings", {}).get("h1")
    ]


def check_h1_multiple(ctx):
    out = []
    for p in ctx["html_pages"]:
        h1s = p.get("headings", {}).get("h1", [])
        if len(h1s) > 1:
            out.append(
                _insight(
                    p["url"],
                    f"Page has {len(h1s)} h1 tags (expected 1)",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=" | ".join(h1s[:3]),
                )
            )
    return out


def check_h1_length(ctx):
    out = []
    for p in ctx["html_pages"]:
        h1s = p.get("headings", {}).get("h1", [])
        if h1s and not (20 <= len(h1s[0]) <= 70):
            out.append(
                _insight(
                    p["url"],
                    f"H1 length is {len(h1s[0])} chars (recommended 20-70)",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=h1s[0],
                )
            )
    return out


def check_duplicate_h1s(ctx):
    out = []
    buckets = {}
    for p in ctx["html_pages"]:
        h1s = p.get("headings", {}).get("h1", [])
        if h1s:
            buckets.setdefault(_normalize(h1s[0]), []).append((p["url"], h1s[0]))
    for _, group in buckets.items():
        if len(group) > 1:
            for url, item in group:
                out.append(_insight(url, "Duplicate h1", TYPE_SEO, SEVERITY_WARNING, item=item))
    return out


def check_heading_hierarchy(ctx):
    out = []
    for p in ctx["html_pages"]:
        h = p.get("headings", {})
        levels = [lvl for lvl in range(1, 7) if h.get(f"h{lvl}")]
        for i in range(1, len(levels)):
            if levels[i] - levels[i - 1] > 1:
                out.append(
                    _insight(
                        p["url"],
                        f"Heading hierarchy skips from h{levels[i - 1]} to h{levels[i]}",
                        TYPE_SEO,
                        SEVERITY_INFO,
                    )
                )
                break
    return out


def check_canonical_missing(ctx):
    return [
        _insight(p["url"], "Page has no canonical URL", TYPE_SEO, SEVERITY_WARNING)
        for p in ctx["html_pages"]
        if not p.get("canonical")
    ]


def check_canonical_offdomain(ctx):
    out = []
    host = ctx["host"]
    for p in ctx["html_pages"]:
        c = p.get("canonical", "")
        if c and not same_site(c, host):
            out.append(
                _insight(
                    p["url"],
                    "Canonical URL points off-domain",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=c,
                )
            )
    return out


def check_canonical_broken(ctx):
    out = []
    status_map = ctx["status_map"]
    for p in ctx["html_pages"]:
        c = p.get("canonical", "")
        if c and c in status_map and status_map[c] != 200:
            out.append(
                _insight(
                    p["url"],
                    f"Canonical URL returns {status_map[c]}",
                    TYPE_SEO,
                    SEVERITY_ERROR,
                    item=c,
                )
            )
    return out


def check_robots_meta_noindex(ctx):
    out = []
    for p in ctx["html_pages"]:
        rm = (p.get("robots_meta") or "").lower()
        if "noindex" in rm:
            out.append(
                _insight(
                    p["url"],
                    "Page has noindex in meta robots tag",
                    TYPE_SEO,
                    SEVERITY_WARNING,
                    item=p.get("robots_meta", ""),
                )
            )
    return out


def check_lang_missing(ctx):
    return [
        _insight(p["url"], "HTML lang attribute missing", TYPE_SEO, SEVERITY_WARNING)
        for p in ctx["html_pages"]
        if not p.get("lang")
    ]


def check_viewport_missing(ctx):
    return [
        _insight(p["url"], "Viewport meta tag missing (mobile)", TYPE_SEO, SEVERITY_WARNING)
        for p in ctx["html_pages"]
        if not p.get("viewport")
    ]


def check_og_incomplete(ctx):
    out = []
    for p in ctx["html_pages"]:
        og = p.get("og") or {}
        missing = [k for k in ("title", "description", "image", "url") if not og.get(k)]
        if missing:
            out.append(
                _insight(
                    p["url"],
                    f"Open Graph tags missing: {', '.join('og:' + m for m in missing)}",
                    TYPE_SEO,
                    SEVERITY_INFO,
                )
            )
    return out


def check_twitter_card(ctx):
    return [
        _insight(p["url"], "Twitter card meta tag missing", TYPE_SEO, SEVERITY_INFO)
        for p in ctx["html_pages"]
        if not (p.get("twitter") or {}).get("card")
    ]


def check_favicon(ctx):
    return [
        _insight(p["url"], "Favicon link missing", TYPE_SEO, SEVERITY_INFO)
        for p in ctx["html_pages"]
        if not p.get("favicon")
    ]


def check_json_ld_parse_error(ctx):
    out = []
    for p in ctx["html_pages"]:
        for item in p.get("json_ld", []):
            if item is None:
                out.append(
                    _insight(
                        p["url"],
                        "JSON-LD structured data failed to parse",
                        TYPE_SEO,
                        SEVERITY_WARNING,
                    )
                )
                break
    return out


# ---------- links ----------

def check_broken_internal_links(ctx):
    out = []
    reported = set()
    status_map = ctx["status_map"]
    host = ctx["host"]
    for p in ctx["html_pages"]:
        for link in p.get("links", []):
            lu = link["url"]
            if not same_site(lu, host):
                continue
            status = status_map.get(lu)
            if status is None:
                continue
            if status != 200 and status not in REDIRECT_CODES:
                key = (p["url"], lu)
                if key in reported:
                    continue
                reported.add(key)
                label = f"status {status}" if status else "unreachable"
                out.append(
                    _insight(
                        p["url"],
                        f"Broken internal link ({label})",
                        TYPE_LINKS,
                        SEVERITY_ERROR,
                        item=lu,
                    )
                )
    return out


def check_broken_external_links(ctx):
    out = []
    reported = set()
    host = ctx["host"]
    ext = ctx["external_link_status"]
    for p in ctx["html_pages"]:
        for link in p.get("links", []):
            lu = link["url"]
            if same_site(lu, host):
                continue
            if lu not in ext:
                continue
            status = ext[lu]
            if status == 0 or status >= 400:
                key = (p["url"], lu)
                if key in reported:
                    continue
                reported.add(key)
                label = f"status {status}" if status else "unreachable"
                out.append(
                    _insight(
                        p["url"],
                        f"Broken external link ({label})",
                        TYPE_LINKS,
                        SEVERITY_WARNING,
                        item=lu,
                    )
                )
    return out


def check_redirect_chains(ctx):
    out = []
    for p in ctx["pages"]:
        chain = p.get("redirect_chain") or []
        if len(chain) > 2:  # initial + final is fine; more means multiple hops
            hops = len(chain) - 1
            out.append(
                _insight(
                    p["url"],
                    f"Redirect chain has {hops} hops",
                    TYPE_LINKS,
                    SEVERITY_INFO,
                    item=" -> ".join(str(code) for code, _ in chain),
                )
            )
    return out


def check_nofollow_internal_links(ctx):
    out = []
    reported = set()
    host = ctx["host"]
    for p in ctx["html_pages"]:
        for link in p.get("links", []):
            lu = link["url"]
            if not same_site(lu, host):
                continue
            if "nofollow" in (link.get("rel") or []):
                key = (p["url"], lu)
                if key in reported:
                    continue
                reported.add(key)
                out.append(
                    _insight(
                        p["url"],
                        "Internal link has rel=nofollow",
                        TYPE_LINKS,
                        SEVERITY_INFO,
                        item=lu,
                    )
                )
    return out


# ---------- robots / sitemap ----------

def check_robots_missing(ctx):
    if not ctx["robots"]["exists"]:
        return [
            _insight(
                ctx["start_url"],
                "robots.txt missing",
                TYPE_SEO,
                SEVERITY_WARNING,
                item=ctx["robots"]["url"],
            )
        ]
    return []


def check_sitemap_missing(ctx):
    if not ctx["sitemap_urls"]:
        return [
            _insight(
                ctx["start_url"],
                "sitemap.xml missing or empty",
                TYPE_SEO,
                SEVERITY_WARNING,
            )
        ]
    return []


def check_sitemap_not_in_robots(ctx):
    if (
        ctx["robots"]["exists"]
        and ctx["sitemap_urls"]
        and not ctx["robots"].get("references_sitemap")
    ):
        return [
            _insight(
                ctx["start_url"],
                "robots.txt does not reference a sitemap",
                TYPE_SEO,
                SEVERITY_INFO,
            )
        ]
    return []


def check_sitemap_broken_urls(ctx):
    out = []
    status_map = ctx["status_map"]
    for url in ctx["sitemap_urls"]:
        s = status_map.get(url)
        if s is not None and s != 200 and s not in REDIRECT_CODES:
            out.append(
                _insight(
                    url,
                    f"URL listed in sitemap returns {s}",
                    TYPE_SEO,
                    SEVERITY_ERROR,
                )
            )
    return out


def check_pages_missing_from_sitemap(ctx):
    if not ctx["sitemap_urls"]:
        return []
    sitemap_set = set(ctx["sitemap_urls"])
    out = []
    for p in ctx["html_pages"]:
        if p["url"] in sitemap_set:
            continue
        # Ignore pages excluded by meta robots
        if "noindex" in (p.get("robots_meta") or "").lower():
            continue
        out.append(
            _insight(
                p["url"],
                "Page not listed in sitemap",
                TYPE_SEO,
                SEVERITY_INFO,
            )
        )
    return out


# ---------- accessibility ----------

def check_images_missing_alt(ctx):
    out = []
    for p in ctx["html_pages"]:
        missing = [img for img in p.get("images", []) if img.get("alt") is None]
        if missing:
            out.append(
                _insight(
                    p["url"],
                    f"{len(missing)} image(s) missing alt attribute",
                    TYPE_ACCESSIBILITY,
                    SEVERITY_WARNING,
                    item=missing[0].get("src", "")[:160],
                )
            )
    return out


def check_empty_anchor_text(ctx):
    out = []
    for p in ctx["html_pages"]:
        empty = [link for link in p.get("links", []) if not link.get("text")]
        if empty:
            out.append(
                _insight(
                    p["url"],
                    f"{len(empty)} link(s) have no visible text",
                    TYPE_ACCESSIBILITY,
                    SEVERITY_INFO,
                    item=empty[0].get("url", "")[:160],
                )
            )
    return out


def check_form_inputs_unlabeled(ctx):
    out = []
    ignore_types = {"hidden", "submit", "button", "reset", "image"}
    for p in ctx["html_pages"]:
        for form in p.get("forms", []):
            label_fors = set(form.get("label_fors", []))
            unlabeled = 0
            for i in form.get("inputs", []):
                if (i.get("type") or "text").lower() in ignore_types:
                    continue
                if i.get("aria_label"):
                    continue
                if i.get("id") and i.get("id") in label_fors:
                    continue
                unlabeled += 1
            if unlabeled:
                out.append(
                    _insight(
                        p["url"],
                        f"{unlabeled} form input(s) without associated label",
                        TYPE_ACCESSIBILITY,
                        SEVERITY_WARNING,
                        item=form.get("action", ""),
                    )
                )
                break  # one insight per page
    return out


# ---------- content ----------

def check_thin_content(ctx):
    out = []
    for p in ctx["html_pages"]:
        wc = p.get("word_count", 0)
        if wc < 300:
            out.append(
                _insight(
                    p["url"],
                    f"Thin content ({wc} words)",
                    TYPE_CONTENT,
                    SEVERITY_WARNING,
                )
            )
    return out


def check_duplicate_content(ctx):
    out = []
    buckets = {}
    for p in ctx["html_pages"]:
        th = p.get("text_hash")
        if th:
            buckets.setdefault(th, []).append(p["url"])
    for urls in buckets.values():
        if len(urls) > 1:
            for u in urls:
                other = next((x for x in urls if x != u), urls[0])
                out.append(
                    _insight(
                        u,
                        "Page has duplicate visible content with another page",
                        TYPE_CONTENT,
                        SEVERITY_WARNING,
                        item=other,
                    )
                )
    return out


# ---------- performance ----------

def check_slow_pages(ctx):
    out = []
    for p in ctx["pages"]:
        if not p.get("is_html"):
            continue
        ms = p.get("elapsed_ms", 0)
        if ms > 1000:
            out.append(
                _insight(
                    p["url"],
                    f"Slow response ({ms} ms)",
                    TYPE_PERFORMANCE,
                    SEVERITY_WARNING,
                )
            )
    return out


def check_missing_compression(ctx):
    out = []
    for p in ctx["html_pages"]:
        headers = p.get("headers") or {}
        enc = ""
        for k, v in headers.items():
            if k.lower() == "content-encoding":
                enc = (v or "").lower()
                break
        if not enc:
            out.append(
                _insight(
                    p["url"],
                    "Response not compressed (no Content-Encoding header)",
                    TYPE_PERFORMANCE,
                    SEVERITY_INFO,
                )
            )
    return out


def check_oversized_pages(ctx):
    out = []
    for p in ctx["pages"]:
        size = p.get("bytes", 0)
        if size > 500_000:
            out.append(
                _insight(
                    p["url"],
                    f"Oversized page ({size // 1024} KB)",
                    TYPE_PERFORMANCE,
                    SEVERITY_WARNING,
                )
            )
    return out


# ---------- security (per-page; SecurityMixin covers site-level) ----------

def check_mixed_content(ctx):
    out = []
    for p in ctx["html_pages"]:
        if not p["url"].startswith("https://"):
            continue
        http_resources = [r for r in p.get("resources", []) if r.startswith("http://")]
        if http_resources:
            out.append(
                _insight(
                    p["url"],
                    f"Mixed content: {len(http_resources)} http:// resource(s) on https:// page",
                    TYPE_SECURITY,
                    SEVERITY_WARNING,
                    item=http_resources[0],
                )
            )
    return out


ALL_CHECKS = [
    # Core metadata
    check_title_missing,
    check_title_length,
    check_duplicate_titles,
    check_description_missing,
    check_description_length,
    check_duplicate_descriptions,
    check_h1_missing,
    check_h1_multiple,
    check_h1_length,
    check_duplicate_h1s,
    check_heading_hierarchy,
    check_canonical_missing,
    check_canonical_offdomain,
    check_canonical_broken,
    check_robots_meta_noindex,
    check_lang_missing,
    check_viewport_missing,
    check_og_incomplete,
    check_twitter_card,
    check_favicon,
    check_json_ld_parse_error,
    # Links
    check_broken_internal_links,
    check_broken_external_links,
    check_redirect_chains,
    check_nofollow_internal_links,
    # Robots / sitemap
    check_robots_missing,
    check_sitemap_missing,
    check_sitemap_not_in_robots,
    check_sitemap_broken_urls,
    check_pages_missing_from_sitemap,
    # Accessibility
    check_images_missing_alt,
    check_empty_anchor_text,
    check_form_inputs_unlabeled,
    # Content
    check_thin_content,
    check_duplicate_content,
    # Performance
    check_slow_pages,
    check_missing_compression,
    check_oversized_pages,
    # Security
    check_mixed_content,
]
