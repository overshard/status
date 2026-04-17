#!/usr/bin/env python
import os
import signal
import subprocess
import sys

procs = [
    subprocess.Popen(["python", "manage.py", "scheduler"]),
    subprocess.Popen(
        [
            "gunicorn",
            "status.asgi:application",
            "--workers",
            "2",
            "--max-requests",
            "256",
            "--timeout",
            "30",
            "--bind",
            f":{os.environ['PORT']}",
            "--worker-class",
            "uvicorn.workers.UvicornWorker",
            "--error-logfile",
            "-",
            "--access-logfile",
            "-",
        ]
    ),
]


def shutdown(signum, frame):
    for p in procs:
        p.terminate()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

pid, status = os.wait()
for p in procs:
    if p.pid != pid:
        p.terminate()
for p in procs:
    p.wait()

sys.exit(os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1)
