from django import template


register = template.Library()


@register.filter
def url_path(value):
    """
    Returns everything after the domain and possibly port in a URL. As an
    example:

    https://example.com:443/path/to/page.html?query=string#fragment -> /path/to/page.html?query=string#fragment
    """

    return "/" + value.split('/', 3)[-1]
