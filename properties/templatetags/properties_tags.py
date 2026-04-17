from django import template

register = template.Library()


@register.filter
def url_path(value):
    """
    Returns everything after the domain and possibly port in a URL. As an
    example:

    https://example.com:443/path/to/page.html?query=string#fragment -> /path/to/page.html?query=string#fragment
    """

    return "/" + value.split("/", 3)[-1]


@register.filter
def lh_score_class(score):
    """Bootstrap contextual class for a Lighthouse score (0-1)."""
    if score is None:
        return "secondary"
    if score >= 0.9:
        return "success"
    if score >= 0.5:
        return "warning"
    return "danger"


@register.filter
def format_ms_savings(ms):
    """Render an ms value as '1.2 s' / '420 ms', or '' for zero/None."""
    if not ms:
        return ""
    if ms >= 1000:
        return f"{ms / 1000:.1f} s"
    return f"{int(round(ms))} ms"
