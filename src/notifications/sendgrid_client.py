"""
SendGrid Email Notification Service

This module provides the SendGrid integration for sending email notifications
from the trading engine. It supports priority-based sending, rate limiting,
and retry logic.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Header
from python_http_client.exceptions import HTTPError

from .priority import NotificationPriority
from . import templates

logger = logging.getLogger(__name__)


class MockSendGridClient:
    """
    Mock SendGrid client for testing without sending real emails.

    Logs all email attempts instead of actually sending them.
    """

    def __init__(self):
        self.sent_emails: List[Dict[str, Any]] = []
        logger.info("Initialized MockSendGridClient (no real emails will be sent)")

    def send(self, message: Mail) -> Dict[str, Any]:
        """
        Mock send method that logs the email instead of sending.

        Args:
            message: SendGrid Mail object

        Returns:
            Mock response
        """
        email_data = {
            'to': str(message.to[0].email) if message.to else 'unknown',
            'from': str(message.from_email.email) if message.from_email else 'unknown',
            'subject': message.subject.subject if message.subject else 'No Subject',
            'timestamp': datetime.utcnow().isoformat(),
        }

        self.sent_emails.append(email_data)

        logger.info(f"[MOCK EMAIL] To: {email_data['to']}, Subject: {email_data['subject']}")

        # Return mock successful response
        return {
            'status_code': 202,
            'body': 'Mock email accepted',
            'headers': {}
        }

    def get_sent_emails(self) -> List[Dict[str, Any]]:
        """Get list of all mock sent emails"""
        return self.sent_emails.copy()

    def clear_history(self):
        """Clear sent email history"""
        self.sent_emails.clear()


class SendGridNotificationService:
    """
    SendGrid-based email notification service.

    Features:
    - Priority-based email sending
    - Rate limiting and retry logic
    - HTML email templates
    - Mock mode for testing
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        to_emails: Optional[List[str]] = None,
        mock_mode: bool = False
    ):
        """
        Initialize SendGrid notification service.

        Args:
            api_key: SendGrid API key (defaults to SENDGRID_API_KEY env var)
            from_email: Sender email address (defaults to ALERT_FROM_EMAIL env var)
            to_emails: List of recipient emails (defaults to ALERT_EMAIL env var)
            mock_mode: If True, use mock client instead of real SendGrid
        """
        self.mock_mode = mock_mode

        if mock_mode:
            self.client = MockSendGridClient()
            logger.info("SendGrid service initialized in MOCK mode")
        else:
            self.api_key = api_key or os.getenv('SENDGRID_API_KEY')
            if not self.api_key:
                raise ValueError("SendGrid API key not provided and SENDGRID_API_KEY env var not set")

            self.client = SendGridAPIClient(self.api_key)
            logger.info("SendGrid service initialized in PRODUCTION mode")

        self.from_email = from_email or os.getenv('ALERT_FROM_EMAIL', 'algo-engine@trading.com')

        # Parse to_emails from env or parameter
        if to_emails:
            self.to_emails = to_emails
        else:
            alert_emails = os.getenv('ALERT_EMAIL', '')
            self.to_emails = [email.strip() for email in alert_emails.split(',') if email.strip()]

        if not self.to_emails:
            logger.warning("No recipient emails configured!")

        logger.info(f"Configured to send from: {self.from_email} to: {', '.join(self.to_emails)}")

    async def send_email(
        self,
        subject: str,
        html_body: str,
        priority: NotificationPriority = NotificationPriority.INFO,
        to_emails: Optional[List[str]] = None,
        max_retries: int = 3
    ) -> bool:
        """
        Send an email with retry logic.

        Args:
            subject: Email subject
            html_body: HTML email body
            priority: Email priority level
            to_emails: Optional override for recipient emails
            max_retries: Maximum retry attempts

        Returns:
            True if email sent successfully, False otherwise
        """
        recipients = to_emails or self.to_emails

        if not recipients:
            logger.error("Cannot send email: no recipients configured")
            return False

        # Create email message
        message = Mail(
            from_email=Email(self.from_email),
            to_emails=[To(email) for email in recipients],
            subject=subject,
            html_content=Content("text/html", html_body)
        )

        # Add priority headers
        self._add_priority_headers(message, priority)

        # Attempt to send with retries
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(self.client.send, message)

                if self.mock_mode:
                    logger.info(f"Mock email sent: {subject}")
                    return True

                # Check response status
                if response.status_code in [200, 202]:
                    logger.info(f"Email sent successfully: {subject} (status: {response.status_code})")
                    return True
                else:
                    logger.warning(f"Unexpected status code {response.status_code} for email: {subject}")

            except HTTPError as e:
                logger.error(f"SendGrid HTTP error (attempt {attempt + 1}/{max_retries}): {e}")

                # Check if rate limited
                if e.status_code == 429:
                    retry_after = int(e.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds before retry...")
                    await asyncio.sleep(retry_after)
                    continue

                # Don't retry on client errors (4xx except 429)
                if 400 <= e.status_code < 500:
                    logger.error(f"Client error {e.status_code}, not retrying")
                    return False

            except Exception as e:
                logger.error(f"Error sending email (attempt {attempt + 1}/{max_retries}): {e}")

            # Exponential backoff for retries
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, etc.
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        logger.error(f"Failed to send email after {max_retries} attempts: {subject}")
        return False

    def _add_priority_headers(self, message: Mail, priority: NotificationPriority):
        """
        Add priority headers to email message.

        Args:
            message: SendGrid Mail object
            priority: Notification priority
        """
        if priority == NotificationPriority.CRITICAL:
            # High priority headers
            message.header = Header("Priority", "Urgent")
            message.header = Header("Importance", "high")
            message.header = Header("X-Priority", "1")
        elif priority == NotificationPriority.WARNING:
            # Medium priority
            message.header = Header("Priority", "Normal")
            message.header = Header("Importance", "normal")
            message.header = Header("X-Priority", "3")
        else:
            # Low priority
            message.header = Header("Priority", "Low")
            message.header = Header("Importance", "low")
            message.header = Header("X-Priority", "5")

    async def notify_trade_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Send notification for trading signal generated.

        Args:
            signal: Signal data dictionary

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_signal_email(signal)
        return await self.send_email(
            subject,
            html_body,
            priority=NotificationPriority.INFO
        )

    async def notify_position_opened(self, position: Dict[str, Any]) -> bool:
        """
        Send notification for position opened.

        Args:
            position: Position data dictionary

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_position_opened_email(position)
        return await self.send_email(
            subject,
            html_body,
            priority=NotificationPriority.INFO
        )

    async def notify_position_closed(self, position: Dict[str, Any]) -> bool:
        """
        Send notification for position closed.

        Args:
            position: Position data with P&L

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_position_closed_email(position)

        # Use WARNING priority for losses
        priority = NotificationPriority.WARNING if position.get('pnl_usd', 0) < 0 else NotificationPriority.INFO

        return await self.send_email(
            subject,
            html_body,
            priority=priority
        )

    async def notify_critical_error(self, error: Dict[str, Any]) -> bool:
        """
        Send notification for critical system error.

        Args:
            error: Error data dictionary

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_critical_error_email(error)
        return await self.send_email(
            subject,
            html_body,
            priority=NotificationPriority.CRITICAL,
            max_retries=5  # More retries for critical errors
        )

    async def notify_order_failed(self, order: Dict[str, Any]) -> bool:
        """
        Send notification for order failure.

        Args:
            order: Order data dictionary with error details

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_order_failed_email(order)
        return await self.send_email(
            subject,
            html_body,
            priority=NotificationPriority.CRITICAL,
            max_retries=5
        )

    async def notify_connection_lost(self, connection_info: Dict[str, Any]) -> bool:
        """
        Send notification for market data connection loss.

        Args:
            connection_info: Connection information dictionary

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_connection_lost_email(connection_info)
        return await self.send_email(
            subject,
            html_body,
            priority=NotificationPriority.CRITICAL,
            max_retries=5
        )

    async def notify_batch_summary(self, priority: NotificationPriority, notifications: List[Dict[str, Any]]) -> bool:
        """
        Send batched notification summary.

        Args:
            priority: Priority level of the batch
            notifications: List of notification dictionaries

        Returns:
            True if notification sent successfully
        """
        subject, html_body = templates.render_batch_summary_email(priority.value, notifications)
        return await self.send_email(
            subject,
            html_body,
            priority=priority
        )

    def get_mock_history(self) -> List[Dict[str, Any]]:
        """
        Get mock email history (only works in mock mode).

        Returns:
            List of sent emails
        """
        if isinstance(self.client, MockSendGridClient):
            return self.client.get_sent_emails()
        return []

    def clear_mock_history(self):
        """Clear mock email history (only works in mock mode)"""
        if isinstance(self.client, MockSendGridClient):
            self.client.clear_history()
