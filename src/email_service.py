import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailService:
    def configured(self):
        return all(os.getenv(key) for key in ("SMTP_HOST", "SENDER_EMAIL", "EMAIL_APP_PASSWORD"))

    def send(self, config, photo, stats, duration):
        if not config.parent_mode:
            raise PermissionError("Email consent is disabled")
        if not self.configured():
            raise ValueError("Configure SMTP_HOST, SENDER_EMAIL and EMAIL_APP_PASSWORD in .env")
        message = EmailMessage()
        message["Subject"] = config.email_subject
        message["From"] = os.environ["SENDER_EMAIL"]
        message["To"] = config.parent_email
        message.set_content(config.email_body.format(USER_NAME=config.user_name,
                            PHONE_DURATION=round(duration), FOCUS_TIME=round(stats.focus),
                            PHONE_PICKUPS=stats.pickups, WARNING_COUNT=stats.warnings))
        message.add_attachment(photo, maintype="image", subtype="jpeg", filename="accountability.jpg")
        with smtplib.SMTP_SSL(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "465")),
                              timeout=15, context=ssl.create_default_context()) as smtp:
            smtp.login(os.environ["SENDER_EMAIL"], os.environ["EMAIL_APP_PASSWORD"])
            smtp.send_message(message)
