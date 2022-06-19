"""
Template tags for social media and sharing in general.
"""
import hashlib
import io
import threading

from django import template
from django.core.files.storage import default_storage
from django.utils.html import format_html
from django.utils import timezone

from status.chromium import generate_screenshot_from_url

register = template.Library()


@register.simple_tag
def og_image(url):
    filename = hashlib.md5(url.encode("utf-8")).hexdigest()
    filename = f"opengraph/{filename}.png"

    if not default_storage.exists(filename):
        # save a quick file to prevent infinite loop
        default_storage.save(filename, io.BytesIO())
        generate_screenshot_from_url(url, filename)
    else:
        # if the file exists, check it's timestamp, if it's older than a day
        # regenerate it with threading since the old one is okay for now
        one_day_ago = timezone.now() - timezone.timedelta(days=1)
        if default_storage.get_modified_time(filename) < one_day_ago:
            threading.Thread(
                target=generate_screenshot_from_url, args=(url, filename)
            ).start()

    # get full url including domain
    url = default_storage.url(filename)
    return format_html('<meta property="og:image" content="{}">', url)
