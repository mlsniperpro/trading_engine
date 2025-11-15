"""
Priority Handling System for Notifications

This module defines the priority levels and routing logic for notifications.
Different event types are mapped to different priority levels, which determine
how and when notifications are sent.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Priority levels for notifications"""
    CRITICAL = "critical"  # Immediate email (order failures, connection loss)
    WARNING = "warning"    # Batched email (data quality issues)
    INFO = "info"         # Optional email (signals, fills)


@dataclass
class PriorityConfig:
    """Configuration for a priority level"""
    send_immediately: bool
    batch_interval_seconds: int
    retry_on_failure: bool
    max_retries: int


class PriorityHandler:
    """
    Handles priority-based routing and batching of notifications.

    Features:
    - CRITICAL: Sent immediately with retries
    - WARNING: Batched every 5 minutes
    - INFO: Batched every 10 minutes
    - Rate limiting to avoid spam
    """

    # Default priority configurations
    DEFAULT_CONFIGS: Dict[NotificationPriority, PriorityConfig] = {
        NotificationPriority.CRITICAL: PriorityConfig(
            send_immediately=True,
            batch_interval_seconds=0,
            retry_on_failure=True,
            max_retries=3
        ),
        NotificationPriority.WARNING: PriorityConfig(
            send_immediately=False,
            batch_interval_seconds=300,  # 5 minutes
            retry_on_failure=True,
            max_retries=2
        ),
        NotificationPriority.INFO: PriorityConfig(
            send_immediately=False,
            batch_interval_seconds=600,  # 10 minutes
            retry_on_failure=False,
            max_retries=0
        )
    }

    # Event type to priority mapping
    EVENT_PRIORITY_MAP: Dict[str, NotificationPriority] = {
        # CRITICAL events - immediate notification
        "OrderFailed": NotificationPriority.CRITICAL,
        "MarketDataConnectionLost": NotificationPriority.CRITICAL,
        "SystemError": NotificationPriority.CRITICAL,
        "CircuitBreakerTriggered": NotificationPriority.CRITICAL,
        "ForceExitRequired": NotificationPriority.CRITICAL,

        # WARNING events - batched notification
        "DataQualityIssue": NotificationPriority.WARNING,
        "PortfolioHealthDegraded": NotificationPriority.WARNING,
        "DumpDetected": NotificationPriority.WARNING,
        "CorrelatedDumpDetected": NotificationPriority.WARNING,
        "MaxHoldTimeExceeded": NotificationPriority.WARNING,

        # INFO events - optional notification
        "TradingSignalGenerated": NotificationPriority.INFO,
        "PositionOpened": NotificationPriority.INFO,
        "PositionClosed": NotificationPriority.INFO,
        "OrderFilled": NotificationPriority.INFO,
        "TrailingStopHit": NotificationPriority.INFO,
    }

    def __init__(self, configs: Optional[Dict[NotificationPriority, PriorityConfig]] = None):
        """
        Initialize priority handler.

        Args:
            configs: Optional custom priority configurations
        """
        self.configs = configs or self.DEFAULT_CONFIGS
        self.batched_notifications: Dict[NotificationPriority, List[dict]] = {
            NotificationPriority.WARNING: [],
            NotificationPriority.INFO: []
        }
        self.last_batch_send: Dict[NotificationPriority, datetime] = {
            NotificationPriority.WARNING: datetime.utcnow(),
            NotificationPriority.INFO: datetime.utcnow()
        }
        self.rate_limit_tracker: Dict[str, List[datetime]] = {}
        self.is_running = False

    def get_priority(self, event_type: str) -> NotificationPriority:
        """
        Get priority level for an event type.

        Args:
            event_type: The event type name

        Returns:
            NotificationPriority for the event
        """
        return self.EVENT_PRIORITY_MAP.get(event_type, NotificationPriority.INFO)

    def should_send_immediately(self, priority: NotificationPriority) -> bool:
        """
        Check if notification should be sent immediately.

        Args:
            priority: The notification priority

        Returns:
            True if should send immediately, False if should batch
        """
        config = self.configs[priority]
        return config.send_immediately

    def add_to_batch(self, priority: NotificationPriority, notification: dict):
        """
        Add notification to batch queue.

        Args:
            priority: The notification priority
            notification: The notification data
        """
        if priority not in self.batched_notifications:
            logger.warning(f"Cannot batch {priority} priority notifications")
            return

        self.batched_notifications[priority].append(notification)
        logger.debug(f"Added notification to {priority} batch. Queue size: {len(self.batched_notifications[priority])}")

    def should_send_batch(self, priority: NotificationPriority) -> bool:
        """
        Check if batch should be sent based on time interval.

        Args:
            priority: The notification priority

        Returns:
            True if batch should be sent
        """
        if priority not in self.batched_notifications:
            return False

        if not self.batched_notifications[priority]:
            return False

        config = self.configs[priority]
        last_send = self.last_batch_send[priority]
        time_since_last = (datetime.utcnow() - last_send).total_seconds()

        return time_since_last >= config.batch_interval_seconds

    def get_batch(self, priority: NotificationPriority) -> List[dict]:
        """
        Get and clear the batch for a priority level.

        Args:
            priority: The notification priority

        Returns:
            List of notifications in the batch
        """
        if priority not in self.batched_notifications:
            return []

        batch = self.batched_notifications[priority].copy()
        self.batched_notifications[priority].clear()
        self.last_batch_send[priority] = datetime.utcnow()

        logger.info(f"Retrieved {len(batch)} notifications from {priority} batch")
        return batch

    def is_rate_limited(self, notification_type: str, max_per_hour: int = 10) -> bool:
        """
        Check if notification type is rate limited.

        Args:
            notification_type: Type of notification
            max_per_hour: Maximum notifications per hour

        Returns:
            True if rate limited
        """
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)

        # Initialize tracker if needed
        if notification_type not in self.rate_limit_tracker:
            self.rate_limit_tracker[notification_type] = []

        # Clean old entries
        self.rate_limit_tracker[notification_type] = [
            ts for ts in self.rate_limit_tracker[notification_type]
            if ts > one_hour_ago
        ]

        # Check limit
        if len(self.rate_limit_tracker[notification_type]) >= max_per_hour:
            logger.warning(f"Rate limit exceeded for {notification_type}: {len(self.rate_limit_tracker[notification_type])}/{max_per_hour} per hour")
            return True

        # Add current timestamp
        self.rate_limit_tracker[notification_type].append(now)
        return False

    def get_retry_config(self, priority: NotificationPriority) -> tuple[bool, int]:
        """
        Get retry configuration for a priority level.

        Args:
            priority: The notification priority

        Returns:
            Tuple of (should_retry, max_retries)
        """
        config = self.configs[priority]
        return config.retry_on_failure, config.max_retries

    async def start_batch_processor(self, send_callback):
        """
        Start the batch processor loop.

        This runs continuously and checks if batches should be sent.

        Args:
            send_callback: Async function to call to send batched notifications
        """
        self.is_running = True
        logger.info("Started notification batch processor")

        try:
            while self.is_running:
                # Check WARNING batch
                if self.should_send_batch(NotificationPriority.WARNING):
                    batch = self.get_batch(NotificationPriority.WARNING)
                    if batch:
                        try:
                            await send_callback(NotificationPriority.WARNING, batch)
                        except Exception as e:
                            logger.error(f"Failed to send WARNING batch: {e}")

                # Check INFO batch
                if self.should_send_batch(NotificationPriority.INFO):
                    batch = self.get_batch(NotificationPriority.INFO)
                    if batch:
                        try:
                            await send_callback(NotificationPriority.INFO, batch)
                        except Exception as e:
                            logger.error(f"Failed to send INFO batch: {e}")

                # Sleep for a short interval
                await asyncio.sleep(10)

        except asyncio.CancelledError:
            logger.info("Batch processor cancelled")
        finally:
            self.is_running = False

    def stop(self):
        """Stop the batch processor"""
        self.is_running = False
        logger.info("Stopped notification batch processor")

    def get_stats(self) -> dict:
        """
        Get statistics about the priority handler.

        Returns:
            Dictionary with handler statistics
        """
        return {
            "batched_counts": {
                priority.value: len(notifications)
                for priority, notifications in self.batched_notifications.items()
            },
            "last_batch_send": {
                priority.value: timestamp.isoformat()
                for priority, timestamp in self.last_batch_send.items()
            },
            "rate_limit_tracker": {
                notification_type: len(timestamps)
                for notification_type, timestamps in self.rate_limit_tracker.items()
            }
        }
