"""
Order executor handler with retry logic and exponential backoff.

Executes orders on exchange with automatic retry on transient failures.
"""

import logging
import asyncio
from typing import Optional
import uuid

from src.execution.handlers.base import (
    ExecutionHandler,
    ExecutionContext,
    ExecutionResult,
    ExecutionResultStatus
)
from src.execution.exchanges.base import (
    ExchangeAdapter,
    ExchangeError,
    RateLimitError,
    InsufficientBalanceError,
    InvalidOrderError
)
from src.execution.exchanges.exchange_factory import get_exchange_factory
from src.core.events import OrderType

logger = logging.getLogger(__name__)


class OrderExecutorHandler(ExecutionHandler):
    """
    Order executor handler with retry logic.

    Features:
    - Automatic retry on transient errors
    - Exponential backoff with jitter
    - Rate limit handling
    - Error classification (retriable vs non-retriable)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        exchange_factory=None,
        **kwargs
    ):
        """
        Initialize order executor.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for first retry
            max_delay: Maximum delay in seconds
            backoff_factor: Exponential backoff multiplier
            jitter: Add random jitter to delays
            exchange_factory: Exchange factory instance
        """
        super().__init__(**kwargs)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.exchange_factory = exchange_factory or get_exchange_factory()

    async def _process(self, context: ExecutionContext) -> ExecutionResult:
        """
        Execute order with retry logic.

        Args:
            context: Execution context

        Returns:
            Execution result
        """
        signal = context.signal
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                # Get exchange adapter
                exchange = await self._get_exchange(
                    exchange_name=signal.exchange,
                    market_type=signal.market_type
                )

                # Generate client order ID if not set
                if 'client_order_id' not in context.metadata:
                    context.metadata['client_order_id'] = f"order_{uuid.uuid4().hex[:16]}"

                # Determine order type
                order_type = context.order_type or OrderType.LIMIT

                # Execute order
                logger.info(
                    f"Executing order (attempt {retry_count + 1}/{self.max_retries + 1}): "
                    f"{signal.symbol} {signal.side.value} {context.quantity} @ {context.price}"
                )

                order_info = await exchange.place_order(
                    symbol=signal.symbol,
                    side=signal.side,
                    order_type=order_type,
                    quantity=context.quantity,
                    price=context.price,
                    stop_price=context.stop_loss_price,
                    client_order_id=context.metadata['client_order_id']
                )

                # Update context with order info
                context.order_id = context.metadata['client_order_id']
                context.exchange_order_id = order_info.order_id
                context.filled_quantity = order_info.filled_quantity
                context.avg_fill_price = order_info.avg_fill_price

                context.metadata.update({
                    'exchange_order_id': order_info.order_id,
                    'order_status': order_info.status.value,
                    'filled_quantity': order_info.filled_quantity,
                    'avg_fill_price': order_info.avg_fill_price,
                    'commission': order_info.commission,
                    'retry_count': retry_count
                })

                logger.info(
                    f"Order executed successfully: {order_info.order_id} "
                    f"(status={order_info.status.value}, filled={order_info.filled_quantity})"
                )

                return ExecutionResult(
                    status=ExecutionResultStatus.SUCCESS,
                    message=f"Order executed: {order_info.order_id}",
                    context=context
                )

            except RateLimitError as e:
                # Rate limit is always retriable
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Max retries exceeded for rate limit: {e}")
                    return ExecutionResult(
                        status=ExecutionResultStatus.FAILURE,
                        message=f"Rate limit exceeded after {retry_count} retries",
                        context=context,
                        error=e
                    )

                # Wait with exponential backoff
                delay = await self._calculate_backoff_delay(retry_count)
                logger.warning(
                    f"Rate limit hit, retrying in {delay:.2f}s "
                    f"(attempt {retry_count}/{self.max_retries})"
                )
                await asyncio.sleep(delay)
                continue

            except InsufficientBalanceError as e:
                # Insufficient balance is not retriable
                logger.error(f"Insufficient balance: {e}")
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Insufficient balance: {str(e)}",
                    context=context,
                    error=e
                )

            except InvalidOrderError as e:
                # Invalid order is not retriable
                logger.error(f"Invalid order parameters: {e}")
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Invalid order: {str(e)}",
                    context=context,
                    error=e
                )

            except ExchangeError as e:
                # Generic exchange error - may be retriable
                retry_count += 1
                if retry_count > self.max_retries:
                    logger.error(f"Max retries exceeded for exchange error: {e}")
                    return ExecutionResult(
                        status=ExecutionResultStatus.FAILURE,
                        message=f"Exchange error after {retry_count} retries: {str(e)}",
                        context=context,
                        error=e
                    )

                # Check if error is retriable
                if not self._is_retriable_error(e):
                    logger.error(f"Non-retriable exchange error: {e}")
                    return ExecutionResult(
                        status=ExecutionResultStatus.FAILURE,
                        message=f"Non-retriable error: {str(e)}",
                        context=context,
                        error=e
                    )

                # Wait with exponential backoff
                delay = await self._calculate_backoff_delay(retry_count)
                logger.warning(
                    f"Exchange error, retrying in {delay:.2f}s "
                    f"(attempt {retry_count}/{self.max_retries}): {e}"
                )
                await asyncio.sleep(delay)
                continue

            except Exception as e:
                # Unexpected error
                logger.error(f"Unexpected error executing order: {e}", exc_info=True)
                return ExecutionResult(
                    status=ExecutionResultStatus.FAILURE,
                    message=f"Unexpected error: {str(e)}",
                    context=context,
                    error=e
                )

        # Should not reach here, but just in case
        return ExecutionResult(
            status=ExecutionResultStatus.FAILURE,
            message="Max retries exceeded",
            context=context
        )

    async def _get_exchange(
        self,
        exchange_name: str,
        market_type: str = "spot"
    ) -> ExchangeAdapter:
        """
        Get or create exchange adapter.

        Args:
            exchange_name: Exchange name
            market_type: Market type

        Returns:
            Exchange adapter
        """
        # Try to get existing instance
        exchange = await self.exchange_factory.get_exchange(
            exchange_name=exchange_name,
            market_type=market_type
        )

        # Create if doesn't exist
        if exchange is None:
            exchange = await self.exchange_factory.create_exchange(
                exchange_name=exchange_name,
                market_type=market_type
            )

        return exchange

    async def _calculate_backoff_delay(self, retry_count: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            retry_count: Current retry count

        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff
        delay = min(
            self.base_delay * (self.backoff_factor ** (retry_count - 1)),
            self.max_delay
        )

        # Add jitter (random ±25%)
        if self.jitter:
            import random
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(delay, 0.1)  # Minimum 0.1s

    def _is_retriable_error(self, error: ExchangeError) -> bool:
        """
        Determine if error is retriable.

        Args:
            error: Exchange error

        Returns:
            True if retriable
        """
        # Check error code/message for known retriable patterns
        error_msg = str(error).lower()

        # Non-retriable patterns
        non_retriable = [
            'insufficient',
            'invalid',
            'unauthorized',
            'forbidden',
            'not found',
            'bad request',
        ]

        for pattern in non_retriable:
            if pattern in error_msg:
                return False

        # Retriable patterns
        retriable = [
            'timeout',
            'connection',
            'network',
            'temporarily',
            'try again',
            'service unavailable',
        ]

        for pattern in retriable:
            if pattern in error_msg:
                return True

        # Default: retriable (conservative approach)
        return True
