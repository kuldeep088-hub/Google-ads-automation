import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    def send(self, subject: str, body_html: str, recipients: list[str]) -> bool:
        if not recipients:
            return False
        if settings.EMAIL_BACKEND == "sendgrid":
            return self._send_sendgrid(subject, body_html, recipients)
        return self._send_smtp(subject, body_html, recipients)

    def _send_smtp(self, subject: str, body_html: str, recipients: list[str]) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.ALERT_EMAIL_FROM
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.ALERT_EMAIL_FROM, recipients, msg.as_string())
            logger.info("Email sent to %s", recipients)
            return True
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False

    def _send_sendgrid(self, subject: str, body_html: str, recipients: list[str]) -> bool:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, To

            message = Mail(
                from_email=settings.ALERT_EMAIL_FROM,
                to_emails=[To(r) for r in recipients],
                subject=subject,
                html_content=body_html,
            )
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info("SendGrid response: %d", response.status_code)
            return response.status_code in (200, 202)
        except Exception as e:
            logger.error("SendGrid send failed: %s", e)
            return False
