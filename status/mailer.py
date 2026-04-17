import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor

import dns.resolver
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mailer")


def _deliver(message):
    try:
        by_domain = {}
        for rcpt in message.to + message.cc + message.bcc:
            by_domain.setdefault(rcpt.rsplit("@", 1)[1], []).append(rcpt)

        payload = message.message().as_bytes()
        sender = message.from_email

        for domain, rcpts in by_domain.items():
            mxs = sorted(
                dns.resolver.resolve(domain, "MX"),
                key=lambda r: r.preference,
            )
            for mx in mxs:
                host = str(mx.exchange).rstrip(".")
                try:
                    with smtplib.SMTP(
                        host, 25, local_hostname="bythewood.me", timeout=30
                    ) as smtp:
                        smtp.ehlo()
                        try:
                            smtp.starttls()
                            smtp.ehlo()
                        except smtplib.SMTPNotSupportedError:
                            pass
                        smtp.sendmail(sender, rcpts, payload)
                    break
                except Exception as exc:
                    log.warning("MX %s failed for %s: %s", host, domain, exc)
            else:
                log.error("all MX hosts failed for %s", domain)
    except Exception:
        log.exception("mail delivery failed")


class DirectMXBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        for message in email_messages:
            _POOL.submit(_deliver, message)
        return len(email_messages)
