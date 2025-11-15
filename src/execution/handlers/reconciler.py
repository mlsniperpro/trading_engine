"""
Reconciliation handler for order verification.

Verifies order execution and updates position state.
"""

import logging
import asyncio
from typing import Optional

from src.execution.handlers.base import (
    ExecutionHandler,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultStatus
)
from src.execution.exchanges.base import ExchangeAdapter, ExchangeError, OrderStatus as ExchangeOrderStatus
from src.execution.exchanges.exchange_factory import get_exchange_factory
from src.core.events import OrderStatus

logger = logging.getLogger(__name__)


class ReconciliationHandler(ExecutionHandler):
    """
    Reconciliation handler for order verification.

    Responsibilities:
    - Verify order fill status
    - Check actual fill price vs expected
    - Validate filled quantity
    - Update position state
    - Detect execution anomalies
    """

    def __init__(
        self,
        verify_fill: bool = True,
        max_price_slippage_pct: float = 1.0,
        poll_interval: float = 0.5,
        max_wait_time: float = 10.0,
        exchange_factory=None,
        **kwargs
    ):
        """
        Initialize reconciliation handler.

        Args:
            verify_fill: Whether to verify order fill
            max_price_slippage_pct: Maximum acceptable price slippage %
            poll_interval: Interval to poll order status (seconds)
            max_wait_time: Maximum time to wait for fill (seconds)
            exchange_factory: Exchange factory instance
        """
        super().__init__(**kwargs)
        self.verify_fill = verify_fill
        self.max_price_slippage_pct = max_price_slippage_pct
        self.poll_interval = poll_interval
        self.max_wait_time = max_wait_time
        self.exchange_factory = exchange_factory or get_exchange_factory()

    async def _process(self, context: ExecutionContext) -> ExecutionResult:
        """
        Reconcile order execution.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        # Skip if no order was placed
        if context.exchange_order_id is None:
            logger.warning("No order ID to reconcile")
            return ExecutionResult(
                status=ExecutionResultStatus.FAILURE,
                message="No order ID to reconcile",
                context=context
            )

        # Verify order fill if enabled
        if self.verify_fill:
            fill_verified = await self._verify_order_fill(context)
            if not fill_verified:
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message="Order fill verification failed",
                    context=context
                )

        # Check price slippage
        if context.avg_fill_price and context.price:
            slippage_pct = abs(context.avg_fill_price - context.price) / context.price * 100

            if slippage_pct > self.max_price_slippage_pct:
                logger.warning(
                    f"High price slippage detected: {slippage_pct:.2f}% "
                    f"(expected={context.price}, filled={context.avg_fill_price})"
                )
                context.metadata['high_slippage'] = True
                context.metadata['slippage_pct'] = slippage_pct

        # Validate filled quantity
        if context.filled_quantity and context.quantity:
            fill_ratio = context.filled_quantity / context.quantity

            if fill_ratio < 0.95:  # Less than 95% filled
                logger.warning(
                    f"Partial fill detected: {fill_ratio * 100:.1f}% "
                    f"(requested={context.quantity}, filled={context.filled_quantity})"
                )
                context.metadata['partial_fill'] = True
                context.metadata['fill_ratio'] = fill_ratio

        # Update reconciliation metadata
        context.metadata['reconciliation_completed'] = True
        context.metadata['avg_fill_price'] = context.avg_fill_price
        context.metadata['total_filled'] = context.filled_quantity

        logger.info(
            f"Reconciliation completed: order={context.exchange_order_id}, "
            f"filled={context.filled_quantity}/{context.quantity} @ {context.avg_fill_price}"
        )

        return ExecutionResult(
            status=ExecutionResultStatus.SUCCESS,
            message="Reconciliation successful",
            context=context
        )

    async def _verify_order_fill(self, context: ExecutionContext) -> bool:
        """
        Verify order fill by polling exchange.

        Args:
            context: Execution context

        Returns:
            True if order is filled
        """
        signal = context.signal

        try:
            # Get exchange adapter
            exchange = await self._get_exchange(
                exchange_name=signal.exchange,
                market_type=signal.market_type
            )

            # Poll for order status
            elapsed = 0.0
            while elapsed < self.max_wait_time:
                # Fetch order status
                order_info = await exchange.get_order(
                    symbol=signal.symbol,
                    order_id=context.exchange_order_id
                )

                logger.debug(
                    f"Order status: {order_info.status.value} "
                    f"(filled={order_info.filled_quantity}/{order_info.quantity})"
                )

                # Check if filled
                if order_info.status == ExchangeOrderStatus.FILLED:
                    # Update context with actual fill data
                    context.filled_quantity = order_info.filled_quantity
                    context.avg_fill_price = order_info.avg_fill_price

                    logger.info(
                        f"Order filled: {context.exchange_order_id} "
                        f"({order_info.filled_quantity} @ {order_info.avg_fill_price})"
                    )
                    return True

                # Check if rejected or cancelled
                if order_info.status in [
                    ExchangeOrderStatus.REJECTED,
                    ExchangeOrderStatus.CANCELLED,
                    ExchangeOrderStatus.FAILED
                ]:
                    logger.error(f"Order failed: status={order_info.status.value}")
                    return False

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                elapsed += self.poll_interval

            # Timeout - order not filled in time
            logger.warning(
                f"Order fill verification timeout after {elapsed:.1f}s: "
                f"{context.exchange_order_id}"
            )

            # For market orders, this is unusual
            # For limit orders, this might be expected
            return False

        except ExchangeError as e:
            logger.error(f"Error verifying order fill: {e}")
            return False

    async def _get_exchange(
        self,
        exchange_name: str,
        market_type: str = "spot"
    ) -> ExchangeAdapter:
        """
        Get exchange adapter.

        Args:
            exchange_name: Exchange name
            market_type: Market type

        Returns:
            Exchange adapter
        """
        exchange = await self.exchange_factory.get_exchange(
            exchange_name=exchange_name,
            market_type=market_type
        )

        if exchange is None:
            exchange = await self.exchange_factory.create_exchange(
                exchange_name=exchange_name,
                market_type=market_type
            )

        return exchange
