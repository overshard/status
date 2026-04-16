"""
A wrapper around the lighthouse node CLI.

Raises LighthouseError with a descriptive message on failure so callers can
log/persist the reason instead of silently dropping the result.
"""
import json
import logging
import shutil
import subprocess

from django.conf import settings


logger = logging.getLogger(__name__)


# Lighthouse's chrome-launcher searches for a browser on its own; we only
# pin CHROME_PATH when we can resolve a known name, for determinism in
# production (Alpine ships `chromium`). If nothing is found, fall through
# and let chrome-launcher do its own lookup.
CHROMIUM_BINARY = (
    shutil.which("chromium")
    or shutil.which("chromium-browser")
    or shutil.which("google-chrome")
)

CHROME_FLAGS = "--headless --no-sandbox --disable-dev-shm-usage --disable-gpu"

# Lighthouse itself can take 60-90s on a slow site; the outer timeout is a
# backstop against Chromium hangs that would otherwise wedge the scheduler.
SUBPROCESS_TIMEOUT_SECONDS = 180


class LighthouseError(Exception):
    pass


def fetch_lighthouse_results(url):
    command = [
        f"{settings.BASE_DIR}/node_modules/.bin/lighthouse",
        url,
        f"--chrome-flags={CHROME_FLAGS}",
        "--output=json",
        "--output-path=stdout",
        "--quiet",
    ]
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin"}
    if CHROMIUM_BINARY:
        env["CHROME_PATH"] = CHROMIUM_BINARY

    try:
        process = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise LighthouseError(f"lighthouse timed out after {SUBPROCESS_TIMEOUT_SECONDS}s")
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        raise LighthouseError(f"lighthouse exited {e.returncode}: {stderr[-500:]}")
    except FileNotFoundError as e:
        raise LighthouseError(f"lighthouse binary missing: {e}")

    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as e:
        raise LighthouseError(f"could not parse lighthouse output: {e}")


def parse_lighthouse_results(results):
    try:
        scores = {
            "Performance": results["categories"]["performance"]["score"],
            "Accessibility": results["categories"]["accessibility"]["score"],
            "Best practices": results["categories"]["best-practices"]["score"],
            "SEO": results["categories"]["seo"]["score"],
        }
    except KeyError as e:
        raise LighthouseError(f"missing category in lighthouse output: {e}")

    if any(v is None for v in scores.values()):
        missing = [k for k, v in scores.items() if v is None]
        raise LighthouseError(f"null score(s) returned by lighthouse: {missing}")

    return {k: round(v * 100) for k, v in scores.items()}
