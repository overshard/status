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
        '--chrome-flags="--headless --no-sandbox"',
        '--output="json"',
        '--output-path="stdout"',
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
            "performance": results["categories"]["performance"]["score"],
            "accessibility": results["categories"]["accessibility"]["score"],
            "best-practices": results["categories"]["best-practices"]["score"],
            "seo": results["categories"]["seo"]["score"],
        }
    except KeyError:
        return None
    scores = {k: round(v * 100) for k, v in scores.items()}
    return scores
