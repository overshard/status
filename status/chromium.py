"""
A simple library for working with the chromium browser in headless mode for
generating things like screenshots.
"""
import os
import shutil
import subprocess
import uuid

from django.core.files.storage import default_storage


# Chromium/Chrome binary discovery — distro names vary (Alpine: chromium,
# Debian/Ubuntu: chromium-browser, the webdev container ships google-chrome).
chromium = None
for binary in ("chromium", "chromium-browser", "google-chrome"):
    if shutil.which(binary):
        chromium = binary
        break


base_command = [
    chromium,
    "--headless",
    "--no-sandbox",
    "--use-gl=swiftshader",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-dev-shm-usage",
    "--disable-crash-reporter",
    "--disable-extensions",
    "--disable-in-process-stack-traces",
    "--disable-logging",
    "--window-size=1280,720",
    "--hide-scrollbars",
] if chromium else []


def save_tempfile_to_storage(tempfilename, filename):
    """
    Saves the given tempfile to django default_storage.

    :param tempfilename: The tempfile we want to save
    :param filename: The storage location to save the file to
    """
    if default_storage.exists(filename):
        default_storage.delete(filename)
    default_storage.save(filename, open(tempfilename, "rb"))
    os.remove(tempfilename)


def run_chromium_command(command):
    """
    Runs the given chromium command and returns the stdout.

    :param command: The command to run
    """
    if not chromium:
        raise Exception("Could not find chromium")
    command = command.split()
    command = base_command + command
    subprocess.run(
        command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def generate_screenshot_from_url(url, filename):
    """
    Generates a screenshot of the given url and saves it to the given output
    file.

    :param url: The url to screenshot
    :param filename: The output file to save the screenshot to
    """
    tempfilename = f"{uuid.uuid4()}.png"
    run_chromium_command(f"--screenshot={tempfilename} {url}")
    save_tempfile_to_storage(tempfilename, filename)
    return default_storage.url(filename)


def generate_screenshot_from_html(html, filename):
    """
    Generates a screenshot of the given html and saves it to the given output
    file.

    :param html: The html to screenshot
    :param filename: The output file to save the screenshot to
    """
    tempfilename = f"{uuid.uuid4()}.html"
    with open(tempfilename, "w") as f:
        f.write(html)
    tempfilename_path = "file://" + os.path.join(os.getcwd(), tempfilename)
    run_chromium_command(f"--screenshot={tempfilename} {tempfilename_path}")
    save_tempfile_to_storage(tempfilename, filename)
    return default_storage.url(filename)


def generate_pdf_from_url(url, filename):
    """
    Generates a pdf of the given url and saves it to the given output file.

    :param url: The url to screenshot
    :param filename: The output file to save the screenshot to
    """
    tempfilename = f"{uuid.uuid4()}.pdf"
    run_chromium_command(f"--print-to-pdf-no-header --print-to-pdf={tempfilename} {url}")
    save_tempfile_to_storage(tempfilename, filename)
    return default_storage.url(filename)


def generate_pdf_from_html(html, filename):
    """
    Generates a pdf of the given html and saves it to the given output file.

    :param url: The url to screenshot
    :param filename: The output file to save the screenshot to
    """
    tempfilename = f"{uuid.uuid4()}.html"
    with open(tempfilename, "w") as f:
        f.write(html)
    tempfilename_path = "file://" + os.path.join(os.getcwd(), tempfilename)
    run_chromium_command(f"--print-to-pdf-no-header --print-to-pdf={tempfilename} {tempfilename_path}")
    save_tempfile_to_storage(tempfilename, filename)
    return default_storage.url(filename)
