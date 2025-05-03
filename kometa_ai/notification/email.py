import logging
import smtplib
import ssl
from typing import List, Dict, Any, Optional, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from kometa_ai.config import Config

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Email notification system for sending summary emails about processed collections."""

    def __init__(self):
        """Initialize the email notifier with configuration from environment variables."""
        # Required SMTP settings
        self.smtp_server = Config.get('SMTP_SERVER')
        self.smtp_port = Config.get_int('SMTP_PORT', 25)
        self.recipients = Config.get_list('NOTIFICATION_RECIPIENTS')

        # Optional SMTP authentication settings
        self.smtp_username = Config.get('SMTP_USERNAME', '')
        self.smtp_password = Config.get('SMTP_PASSWORD', '')
        self.use_ssl = Config.get_bool('SMTP_USE_SSL', False)
        self.use_tls = Config.get_bool('SMTP_USE_TLS', False)

        # Email metadata settings
        self.from_address = Config.get('NOTIFICATION_FROM', 'kometa-ai@localhost')
        self.reply_to = Config.get('NOTIFICATION_REPLY_TO', self.from_address)

        # Notification control settings
        self.send_on_no_changes = Config.get_bool('NOTIFY_ON_NO_CHANGES', False)
        self.send_on_errors_only = Config.get_bool('NOTIFY_ON_ERRORS_ONLY', True)

        # Log warning messages if critical configs are missing
        if not self.smtp_server:
            logger.warning("SMTP server not configured, email notifications disabled")

        if not self.recipients:
            logger.warning("No notification recipients configured, email notifications disabled")

        # Validate SSL/TLS configuration
        if self.use_ssl and self.use_tls:
            logger.warning("Both SMTP_USE_SSL and SMTP_USE_TLS are enabled. Using TLS only.")
            self.use_ssl = False

        logger.debug(f"Email notifier configured: server={self.smtp_server}:{self.smtp_port}, "
                    f"ssl={self.use_ssl}, tls={self.use_tls}, "
                    f"auth={'enabled' if self.smtp_username else 'disabled'}")

    def can_send(self) -> bool:
        """Check if email notifications can be sent.

        Returns:
            True if email notifications can be sent, False otherwise
        """
        return bool(self.smtp_server and self.recipients)

    def should_send(self, has_changes: bool, has_errors: bool) -> bool:
        """Determine if a notification should be sent based on configuration.

        Args:
            has_changes: Whether there are any changes to report
            has_errors: Whether there are any errors to report

        Returns:
            True if a notification should be sent, False otherwise
        """
        if has_errors and self.send_on_errors_only:
            return True

        if has_changes:
            return True

        return self.send_on_no_changes

    def send_notification(self, subject: str, message: str) -> bool:
        """Send an email notification.

        Args:
            subject: Email subject
            message: Email message (supports Markdown formatting)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.can_send():
            logger.warning("Email notifications disabled, not sending")
            return False

        try:
            # Create a multipart email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_address
            msg['Reply-To'] = self.reply_to
            msg['To'] = ', '.join(self.recipients)
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')

            # Add plain text and HTML parts
            # For simplicity, we're using the same content for both
            # In a production system, we might want to convert Markdown to HTML
            text_part = MIMEText(message, 'plain')
            msg.attach(text_part)

            # Connect to SMTP server
            # Type note: We use Union[SMTP, SMTP_SSL] for server variable
            # but mypy doesn't track this through the conditional
            if self.use_ssl:
                context = ssl.create_default_context()
                server: Union[smtplib.SMTP, smtplib.SMTP_SSL] = smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)

                # Start TLS if requested
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)

            # Log in if credentials are provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)

            # Send email
            server.sendmail(self.from_address, self.recipients, msg.as_string())
            server.quit()

            logger.info(f"Email sent: Subject='{subject}', To={self.recipients}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_summary(self,
                    subject: str,
                    message: str,
                    has_changes: bool = False,
                    has_errors: bool = False) -> bool:
        """Send a summary email if conditions are met.

        Args:
            subject: Email subject
            message: Email message
            has_changes: Whether there are any changes to report
            has_errors: Whether there are any errors to report

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.should_send(has_changes, has_errors):
            logger.info("No changes or errors to report, skipping notification")
            return False

        return self.send_notification(subject, message)
