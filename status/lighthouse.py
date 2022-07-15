"""
A basic wrapper around the lighthouse node module.
"""
import json
import subprocess

from django.conf import settings


def fetch_lighthouse_results(url):
    command = [
        f"{settings.BASE_DIR}/node_modules/.bin/lighthouse",
        url,
        '--chrome-flags="--headless --no-sandbox --disable-dev-shm-usage"',
        '--output="json"',
        '--output-path="stdout"',
        '--max-wait-for-load=5000',
        "--quiet",
    ]
    try:
        process = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return None
    return json.loads(process.stdout)


def parse_lighthouse_results(results):
    try:
        scores = {
            "Performance": results["categories"]["performance"]["score"],
            "Accessibility": results["categories"]["accessibility"]["score"],
            "Best practices": results["categories"]["best-practices"]["score"],
            "SEO": results["categories"]["seo"]["score"],
        }
    except KeyError:
        return None
    scores = {k: round(v * 100) for k, v in scores.items()}
    return scores
