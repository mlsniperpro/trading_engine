"""
Notification Service - Main Orchestrator

This module provides the main NotificationSystem that subscribes to important
events from the trading engine and routes them to appropriate notification
handlers based on priority.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.event_bus import EventBus
from ..core.events import (
    Event,
    TradingSignalGenerated,
    PositionOpened,
    PositionClosed,
    OrderFailed,
    SystemError,
    MarketDataConnectionLost,
    CircuitBreakerTriggered,
    DumpDetected,
    PortfolioHealthDegraded,
    CorrelatedDumpDetected,
    MaxHoldTimeExceeded,
    ForceExitRequired,
    DataQualityIssue,
    TrailingStopHit,
    OrderFilled,
    NotificationSent,
    NotificationFailed,
)

from .priority import PriorityHandler, NotificationPriority
from .sendgrid_client import SendGridNotificationService

logger = logging.getLogger(__name__)


class NotificationSystem:
    """
    Main notification orchestrator.

    This service:
    - Subscribes to important events from the event bus
    - Routes events to appropriate handlers based on priority
    - Manages batching for non-critical notifications
    - Tracks notification statistics
    """

    def __init__(
        self,
        event_bus: EventBus,
        sendgrid_service: SendGridNotificationService,
        priority_handler: Optional[PriorityHandler] = None,
    ):
        """
        Initialize notification system.

        Args:
            event_bus: Event bus instance
            sendgrid_service: SendGrid email service
            priority_handler: Optional priority handler (uses default if not provided)
        """
        self.event_bus = event_bus
        self.sendgrid = sendgrid_service
        self.priority_handler = priority_handler or PriorityHandler()

        self.is_running = False
        self.batch_processor_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "notifications_sent": 0,
            "notifications_failed": 0,
            "critical_sent": 0,
            "warning_batched": 0,
            "info_batched": 0,
            "started_at": None,
        }

        logger.info("NotificationSystem initialized")

    async def start(self):
        """
        Start the notification system.

        This subscribes to important events and starts the batch processor.
        """
        if self.is_running:
            logger.warning("NotificationSystem already running")
            return

        logger.info("Starting NotificationSystem...")

        # Subscribe to CRITICAL events
        self.event_bus.subscribe(OrderFailed, self._handle_order_failed)
        self.event_bus.subscribe(SystemError, self._handle_system_error)
        self.event_bus.subscribe(MarketDataConnectionLost, self._handle_connection_lost)
        self.event_bus.subscribe(CircuitBreakerTriggered, self._handle_circuit_breaker)
        self.event_bus.subscribe(ForceExitRequired, self._handle_force_exit)

        # Subscribe to WARNING events
        self.event_bus.subscribe(DataQualityIssue, self._handle_data_quality_issue)
        self.event_bus.subscribe(PortfolioHealthDegraded, self._handle_portfolio_health)
        self.event_bus.subscribe(DumpDetected, self._handle_dump_detected)
        self.event_bus.subscribe(CorrelatedDumpDetected, self._handle_correlated_dump)
        self.event_bus.subscribe(MaxHoldTimeExceeded, self._handle_max_hold_time)

        # Subscribe to INFO events
        self.event_bus.subscribe(TradingSignalGenerated, self._handle_trading_signal)
        self.event_bus.subscribe(PositionOpened, self._handle_position_opened)
        self.event_bus.subscribe(PositionClosed, self._handle_position_closed)
        self.event_bus.subscribe(OrderFilled, self._handle_order_filled)
        self.event_bus.subscribe(TrailingStopHit, self._handle_trailing_stop)

        # Start batch processor
        self.batch_processor_task = asyncio.create_task(
            self.priority_handler.start_batch_processor(self._send_batch_notifications)
        )

        self.is_running = True
        self.stats["started_at"] = datetime.utcnow()
        logger.info("NotificationSystem started successfully")

    async def stop(self):
        """Stop the notification system."""
        if not self.is_running:
            logger.warning("NotificationSystem not running")
            return

        logger.info("Stopping NotificationSystem...")

        # Stop batch processor
        self.priority_handler.stop()
        if self.batch_processor_task:
            self.batch_processor_task.cancel()
            try:
                await self.batch_processor_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from all events
        self.event_bus.unsubscribe_all(self._handle_order_failed)
        self.event_bus.unsubscribe_all(self._handle_system_error)
        # ... unsubscribe other handlers

        self.is_running = False
        logger.info("NotificationSystem stopped")

    # ========================================================================
    # CRITICAL Event Handlers (send immediately)
    # ========================================================================

    async def _handle_order_failed(self, event: OrderFailed):
        """Handle order failed event (CRITICAL)."""
        logger.warning(f"Order failed: {event.symbol} - {event.error_message}")

        # Check rate limiting
        if self.priority_handler.is_rate_limited("order_failed", max_per_hour=5):
            logger.warning("Rate limit reached for order_failed notifications")
            return

        # Prepare notification data
        order_data = {
            "symbol": event.symbol,
            "direction": event.side.value.upper() if hasattr(event.side, 'value') else str(event.side).upper(),
            "order_type": "UNKNOWN",
            "quantity": 0.0,
            "price": 0.0,
            "error_message": event.error_message,
            "exchange": event.exchange,
        }

        # Send immediately
        success = await self.sendgrid.notify_order_failed(order_data)

        if success:
            self.stats["notifications_sent"] += 1
            self.stats["critical_sent"] += 1
            await self._emit_notification_sent(event, "order_failed", NotificationPriority.CRITICAL)
        else:
            self.stats["notifications_failed"] += 1
            await self._emit_notification_failed(event, "order_failed", "SendGrid error")

    async def _handle_system_error(self, event: SystemError):
        """Handle system error event (CRITICAL)."""
        logger.error(f"System error: {event.component} - {event.error_message}")

        # Check rate limiting
        if self.priority_handler.is_rate_limited("system_error", max_per_hour=10):
            logger.warning("Rate limit reached for system_error notifications")
            return

        # Prepare notification data
        error_data = {
            "error_type": event.error_type,
            "message": event.error_message,
            "component": event.component,
            "timestamp": event.timestamp.isoformat(),
            "stack_trace": event.traceback or "",
        }

        # Send immediately
        success = await self.sendgrid.notify_critical_error(error_data)

        if success:
            self.stats["notifications_sent"] += 1
            self.stats["critical_sent"] += 1
            await self._emit_notification_sent(event, "system_error", NotificationPriority.CRITICAL)
        else:
            self.stats["notifications_failed"] += 1
            await self._emit_notification_failed(event, "system_error", "SendGrid error")

    async def _handle_connection_lost(self, event: MarketDataConnectionLost):
        """Handle connection lost event (CRITICAL)."""
        logger.critical(f"Connection lost: {event.exchange} {event.market_type}")

        # Check rate limiting
        if self.priority_handler.is_rate_limited("connection_lost", max_per_hour=3):
            logger.warning("Rate limit reached for connection_lost notifications")
            return

        # Prepare notification data
        connection_data = {
            "exchange": event.exchange,
            "market_type": event.market_type,
            "symbols": event.symbols,
            "last_heartbeat": event.timestamp.isoformat(),
            "reconnect_attempts": event.retry_attempt,
        }

        # Send immediately
        success = await self.sendgrid.notify_connection_lost(connection_data)

        if success:
            self.stats["notifications_sent"] += 1
            self.stats["critical_sent"] += 1
            await self._emit_notification_sent(event, "connection_lost", NotificationPriority.CRITICAL)
        else:
            self.stats["notifications_failed"] += 1
            await self._emit_notification_failed(event, "connection_lost", "SendGrid error")

    async def _handle_circuit_breaker(self, event: CircuitBreakerTriggered):
        """Handle circuit breaker event (CRITICAL)."""
        logger.critical(f"Circuit breaker triggered: {event.drawdown_pct}% drawdown")

        error_data = {
            "error_type": "Circuit Breaker Triggered",
            "message": f"Daily drawdown limit reached: {event.drawdown_pct}% (threshold: {event.threshold_pct}%)",
            "component": "PortfolioRiskManager",
            "timestamp": event.timestamp.isoformat(),
            "stack_trace": f"Action: {event.action_taken}\nPositions closed: {len(event.positions_closed)}\nTotal P&L: ${event.total_realized_pnl:,.2f}",
        }

        success = await self.sendgrid.notify_critical_error(error_data)

        if success:
            self.stats["notifications_sent"] += 1
            self.stats["critical_sent"] += 1
            await self._emit_notification_sent(event, "circuit_breaker", NotificationPriority.CRITICAL)
        else:
            self.stats["notifications_failed"] += 1

    async def _handle_force_exit(self, event: ForceExitRequired):
        """Handle force exit required event (CRITICAL)."""
        logger.critical(f"Force exit required: {event.reason}")

        error_data = {
            "error_type": "Force Exit Required",
            "message": event.reason,
            "component": "PortfolioRiskManager",
            "timestamp": event.timestamp.isoformat(),
            "stack_trace": f"Urgency: {event.urgency}\nPositions: {len(event.position_ids)}",
        }

        success = await self.sendgrid.notify_critical_error(error_data)

        if success:
            self.stats["notifications_sent"] += 1
            self.stats["critical_sent"] += 1

    # ========================================================================
    # WARNING Event Handlers (batched)
    # ========================================================================

    async def _handle_data_quality_issue(self, event: DataQualityIssue):
        """Handle data quality issue event (WARNING)."""
        logger.warning(f"Data quality issue: {event.exchange} {event.symbol} - {event.description}")

        notification = {
            "type": "DataQualityIssue",
            "message": f"{event.exchange} {event.symbol}: {event.description}",
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity,
        }

        self.priority_handler.add_to_batch(NotificationPriority.WARNING, notification)
        self.stats["warning_batched"] += 1

    async def _handle_portfolio_health(self, event: PortfolioHealthDegraded):
        """Handle portfolio health degraded event (WARNING)."""
        logger.warning(f"Portfolio health degraded: score={event.health_score}")

        notification = {
            "type": "PortfolioHealthDegraded",
            "message": f"Health score: {event.health_score:.1f}, Action: {event.action_taken}",
            "timestamp": event.timestamp.isoformat(),
            "positions_affected": len(event.positions_affected),
        }

        self.priority_handler.add_to_batch(NotificationPriority.WARNING, notification)
        self.stats["warning_batched"] += 1

    async def _handle_dump_detected(self, event: DumpDetected):
        """Handle dump detected event (WARNING)."""
        logger.warning(f"Dump detected: {event.symbol} - {event.price_drop_pct}%")

        notification = {
            "type": "DumpDetected",
            "message": f"{event.symbol}: {event.price_drop_pct}% drop, Action: {event.action_taken}",
            "timestamp": event.timestamp.isoformat(),
            "signals": event.detection_signals,
        }

        self.priority_handler.add_to_batch(NotificationPriority.WARNING, notification)
        self.stats["warning_batched"] += 1

    async def _handle_correlated_dump(self, event: CorrelatedDumpDetected):
        """Handle correlated dump detected event (WARNING)."""
        logger.warning(f"Correlated dump: {event.leader_symbol} - {event.dump_pct}%")

        notification = {
            "type": "CorrelatedDumpDetected",
            "message": f"{event.leader_symbol} dumped {event.dump_pct}%, {len(event.correlated_positions)} positions affected",
            "timestamp": event.timestamp.isoformat(),
            "action": event.action_taken,
        }

        self.priority_handler.add_to_batch(NotificationPriority.WARNING, notification)
        self.stats["warning_batched"] += 1

    async def _handle_max_hold_time(self, event: MaxHoldTimeExceeded):
        """Handle max hold time exceeded event (WARNING)."""
        logger.warning(f"Max hold time exceeded: {event.symbol}")

        notification = {
            "type": "MaxHoldTimeExceeded",
            "message": f"{event.symbol}: held {event.hold_time_seconds/60:.1f}min (max: {event.max_hold_time_seconds/60:.1f}min)",
            "timestamp": event.timestamp.isoformat(),
            "strategy": event.strategy,
        }

        self.priority_handler.add_to_batch(NotificationPriority.WARNING, notification)
        self.stats["warning_batched"] += 1

    # ========================================================================
    # INFO Event Handlers (batched)
    # ========================================================================

    async def _handle_trading_signal(self, event: TradingSignalGenerated):
        """Handle trading signal event (INFO)."""
        logger.info(f"Trading signal: {event.side.value.upper()} {event.symbol}")

        notification = {
            "type": "TradingSignalGenerated",
            "message": f"{event.side.value.upper()} {event.symbol} @ ${event.entry_price or 0:,.4f} (score: {event.confluence_score:.2f})",
            "timestamp": event.timestamp.isoformat(),
        }

        self.priority_handler.add_to_batch(NotificationPriority.INFO, notification)
        self.stats["info_batched"] += 1

    async def _handle_position_opened(self, event: PositionOpened):
        """Handle position opened event (INFO)."""
        logger.info(f"Position opened: {event.side.value.upper()} {event.symbol}")

        notification = {
            "type": "PositionOpened",
            "message": f"{event.side.value.upper()} {event.symbol} @ ${event.entry_price:,.4f} (qty: {event.quantity:.6f})",
            "timestamp": event.timestamp.isoformat(),
        }

        self.priority_handler.add_to_batch(NotificationPriority.INFO, notification)
        self.stats["info_batched"] += 1

    async def _handle_position_closed(self, event: PositionClosed):
        """Handle position closed event (INFO)."""
        pnl_emoji = "+" if event.realized_pnl >= 0 else ""
        logger.info(f"Position closed: {event.symbol} P&L: {pnl_emoji}${event.realized_pnl:,.2f}")

        notification = {
            "type": "PositionClosed",
            "message": f"{event.symbol}: P&L {pnl_emoji}${event.realized_pnl:,.2f} ({pnl_emoji}{event.realized_pnl_pct:.2f}%) - {event.exit_reason}",
            "timestamp": event.timestamp.isoformat(),
        }

        self.priority_handler.add_to_batch(NotificationPriority.INFO, notification)
        self.stats["info_batched"] += 1

    async def _handle_order_filled(self, event: OrderFilled):
        """Handle order filled event (INFO)."""
        logger.info(f"Order filled: {event.side.value.upper()} {event.symbol} @ ${event.avg_fill_price:,.4f}")

        notification = {
            "type": "OrderFilled",
            "message": f"{event.side.value.upper()} {event.symbol}: {event.filled_quantity:.6f} @ ${event.avg_fill_price:,.4f}",
            "timestamp": event.timestamp.isoformat(),
        }

        self.priority_handler.add_to_batch(NotificationPriority.INFO, notification)
        self.stats["info_batched"] += 1

    async def _handle_trailing_stop(self, event: TrailingStopHit):
        """Handle trailing stop hit event (INFO)."""
        logger.info(f"Trailing stop hit: {event.symbol}")

        notification = {
            "type": "TrailingStopHit",
            "message": f"{event.symbol}: Stop triggered @ ${event.trigger_price:,.4f}",
            "timestamp": event.timestamp.isoformat(),
        }

        self.priority_handler.add_to_batch(NotificationPriority.INFO, notification)
        self.stats["info_batched"] += 1

    # ========================================================================
    # Batch Notifications
    # ========================================================================

    async def _send_batch_notifications(self, priority: NotificationPriority, notifications: list):
        """
        Send batched notifications summary.

        Args:
            priority: Priority level of the batch
            notifications: List of notification dictionaries
        """
        logger.info(f"Sending {priority.value} batch: {len(notifications)} notifications")

        success = await self.sendgrid.notify_batch_summary(priority, notifications)

        if success:
            self.stats["notifications_sent"] += 1
            logger.info(f"Batch notification sent: {priority.value} ({len(notifications)} events)")
        else:
            self.stats["notifications_failed"] += 1
            logger.error(f"Failed to send batch notification: {priority.value}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _emit_notification_sent(
        self, original_event: Event, notification_type: str, priority: NotificationPriority
    ):
        """Emit NotificationSent event."""
        notification_event = NotificationSent(
            notification_type=notification_type,
            priority=priority.value,
            subject=f"{notification_type} notification",
            recipient=", ".join(self.sendgrid.to_emails),
            original_event_id=str(id(original_event)),
        )
        await self.event_bus.publish(notification_event)

    async def _emit_notification_failed(
        self, original_event: Event, notification_type: str, error_message: str
    ):
        """Emit NotificationFailed event."""
        notification_event = NotificationFailed(
            notification_type=notification_type,
            error_message=error_message,
            retry_count=0,
            original_event_id=str(id(original_event)),
        )
        await self.event_bus.publish(notification_event)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get notification system statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            **self.stats,
            "priority_handler": self.priority_handler.get_stats(),
        }
