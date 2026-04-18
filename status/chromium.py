"""
Headless Chromium wrapper for generating screenshots and PDFs from URLs or HTML.

Shells out to the system chromium binary (no Playwright, no Selenium, no bundled
browser). Works on Alpine, Ubuntu, and macOS as long as a chromium-family binary
is discoverable on PATH.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

from django.core.files import File
from django.core.files.storage import default_storage

DEFAULT_VIEWPORT: Tuple[int, int] = (1280, 720)
DEFAULT_VIRTUAL_TIME_BUDGET_MS = 5_000
DEFAULT_SUBPROCESS_TIMEOUT_S = 60

BASE_FLAGS = (
    "--headless=new",
    "--no-sandbox",
    "--no-zygote",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-software-rasterizer",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-crash-reporter",
    "--disable-logging",
    "--hide-scrollbars",
)


def _find_chromium() -> Optional[str]:
    for binary in ("chromium", "chromium-browser", "google-chrome"):
        path = shutil.which(binary)
        if path:
            return path
    return None


CHROMIUM_BINARY = _find_chromium()


class ChromiumError(RuntimeError):
    pass


@contextmanager
def _tempfile(suffix: str) -> Iterator[Path]:
    fd, raw = tempfile.mkstemp(suffix=suffix, dir="/tmp")
    os.close(fd)
    path = Path(raw)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def _html_tempfile(html: str) -> Iterator[str]:
    fd, raw = tempfile.mkstemp(suffix=".html", dir="/tmp")
    path = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(html)
        yield f"file://{path}"
    finally:
        path.unlink(missing_ok=True)


def _run(args: list[str], timeout: int) -> None:
    if not CHROMIUM_BINARY:
        raise ChromiumError(
            "No chromium binary found on PATH (tried: chromium, "
            "chromium-browser, google-chrome)"
        )
    cmd = [CHROMIUM_BINARY, *BASE_FLAGS, *args]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ChromiumError(f"chromium timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise ChromiumError(
            f"chromium exited {exc.returncode}: {stderr or '(no stderr)'}"
        ) from exc


def _save(source: Path, filename: str) -> str:
    if default_storage.exists(filename):
        default_storage.delete(filename)
    with source.open("rb") as fp:
        default_storage.save(filename, File(fp))
    return default_storage.url(filename)


def generate_screenshot_from_url(
    url: str,
    filename: str,
    *,
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT,
    virtual_time_budget_ms: int = DEFAULT_VIRTUAL_TIME_BUDGET_MS,
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT_S,
) -> str:
    with _tempfile(".png") as out:
        _run(
            [
                f"--screenshot={out}",
                f"--window-size={viewport[0]},{viewport[1]}",
                f"--virtual-time-budget={virtual_time_budget_ms}",
                url,
            ],
            timeout,
        )
        return _save(out, filename)


def generate_screenshot_from_html(
    html: str,
    filename: str,
    *,
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT,
    virtual_time_budget_ms: int = DEFAULT_VIRTUAL_TIME_BUDGET_MS,
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT_S,
) -> str:
    with _html_tempfile(html) as url:
        return generate_screenshot_from_url(
            url,
            filename,
            viewport=viewport,
            virtual_time_budget_ms=virtual_time_budget_ms,
            timeout=timeout,
        )


def generate_pdf_from_url(
    url: str,
    filename: str,
    *,
    virtual_time_budget_ms: int = DEFAULT_VIRTUAL_TIME_BUDGET_MS,
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT_S,
) -> str:
    with _tempfile(".pdf") as out:
        _run(
            [
                f"--print-to-pdf={out}",
                "--no-pdf-header-footer",
                f"--virtual-time-budget={virtual_time_budget_ms}",
                url,
            ],
            timeout,
        )
        return _save(out, filename)


def generate_pdf_from_html(
    html: str,
    filename: str,
    *,
    virtual_time_budget_ms: int = DEFAULT_VIRTUAL_TIME_BUDGET_MS,
    timeout: int = DEFAULT_SUBPROCESS_TIMEOUT_S,
) -> str:
    with _html_tempfile(html) as url:
        return generate_pdf_from_url(
            url,
            filename,
            virtual_time_budget_ms=virtual_time_budget_ms,
            timeout=timeout,
        )
