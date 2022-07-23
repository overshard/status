import subprocess
import os

from django.conf import settings


def run_seo_spider(url):
    """
    Run the SEO spider on the given URL.

    I'm using the command line runner instead of the python runner because the
    python runner doesn't play well with threads and I can run multiple spiders
    with the command line runner.
    """
    filename = url.split('/')[2] + '.json'
    if settings.DEBUG:
        filename = 'crawler_output/' + filename
    else:
        filename = '/data/crawler_output/' + filename

    # remove the file if it exists before running the spider
    if os.path.exists(filename):
        os.remove(filename)

    # use the jsonlines format to store the results
    subprocess.run([
        'pipenv',
        'run',
        'scrapy',
        'crawl',
        'seo_spider',
        '-a',
        'url=' + url,
        '-t',
        'jsonlines',
        '-o',
        filename,
    ])
