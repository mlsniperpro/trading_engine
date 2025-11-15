"""
Execution engine orchestrator.

Main execution component that:
- Subscribes to TradingSignalGenerated events
- Triggers execution pipeline
- Emits OrderPlaced, OrderFilled, OrderFailed events
"""

import logging
import asyncio
import uuid
from typing import Optional, Callable, Dict, Any

from src.execution.pipeline import ExecutionPipeline
from src.execution.order_manager import OrderManager
from src.execution.handlers.base import ExecutionResultStatus
from src.execution.exchanges.exchange_factory import ExchangeFactory, get_exchange_factory
from src.core.events import (
    TradingSignalGenerated,
    OrderPlaced,
    OrderFilled,
    OrderFailed,
    PositionOpened,
    OrderSide,
    OrderType,
    OrderStatus
)

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Main execution engine orchestrator.

    Features:
    - Event-driven execution (reactive to signals)
    - Pipeline-based order processing
    - Order state management
    - Event emission for order lifecycle
    - Integration with event bus
    """

    def __init__(
        self,
        pipeline: Optional[ExecutionPipeline] = None,
        order_manager: Optional[OrderManager] = None,
        exchange_factory: Optional[ExchangeFactory] = None,
        event_bus=None
    ):
        """
        Initialize execution engine.

        Args:
            pipeline: Execution pipeline
            order_manager: Order manager
            exchange_factory: Exchange factory
            event_bus: Event bus for publishing events
        """
        self.pipeline = pipeline or ExecutionPipeline()
        self.order_manager = order_manager or OrderManager()
        self.exchange_factory = exchange_factory or get_exchange_factory()
        self.event_bus = event_bus

        # Running state
        self._running = False

        # Providers for risk manager
        self._setup_providers()

        logger.info("Execution engine initialized")

    def _setup_providers(self):
        """Setup providers for pipeline handlers."""
        # Set balance provider
        self.pipeline.set_balance_provider(self._get_account_balance)

        # Set positions provider
        self.pipeline.set_positions_provider(self._get_current_positions)

    async def start(self):
        """Start the execution engine."""
        self._running = True
        logger.info("Execution engine started")

    async def stop(self):
        """Stop the execution engine."""
        self._running = False

        # Close all exchange connections
        await self.exchange_factory.close_all()

        logger.info("Execution engine stopped")

    def subscribe_to_events(self, event_bus):
        """
        Subscribe to events from event bus.

        Args:
            event_bus: Event bus instance
        """
        self.event_bus = event_bus

        # Subscribe to TradingSignalGenerated events
        event_bus.subscribe("TradingSignalGenerated", self.on_trading_signal)

        logger.info("Subscribed to TradingSignalGenerated events")

    async def on_trading_signal(self, signal: TradingSignalGenerated):
        """
        Handle trading signal event.

        Args:
            signal: Trading signal
        """
        if not self._running:
            logger.warning("Execution engine not running, ignoring signal")
            return

        logger.info(
            f"Received trading signal: {signal.symbol} {signal.side.value} "
            f"(confluence={signal.confluence_score})"
        )

        # Execute signal
        await self.execute_signal(signal)

    async def execute_signal(self, signal: TradingSignalGenerated) -> bool:
        """
        Execute a trading signal through the pipeline.

        Args:
            signal: Trading signal to execute

        Returns:
            True if execution succeeded
        """
        # Generate client order ID
        client_order_id = f"order_{uuid.uuid4().hex[:16]}"

        # Create order in manager
        order = self.order_manager.create_order(
            client_order_id=client_order_id,
            symbol=signal.symbol,
            side=signal.side,
            order_type=OrderType.LIMIT,  # Default to limit orders
            quantity=0.0,  # Will be calculated by risk manager
            price=signal.entry_price,
            exchange=signal.exchange,
            market_type=signal.market_type,
            signal_id=str(uuid.uuid4()),
            signal_strength=signal.signal_strength,
            confluence_score=signal.confluence_score
        )

        try:
            # Execute pipeline
            result = await self.pipeline.execute(signal)

            if result.is_success:
                # Update order manager
                self.order_manager.update_order_submitted(
                    client_order_id=client_order_id,
                    exchange_order_id=result.context.exchange_order_id
                )

                # Emit OrderPlaced event
                await self._emit_order_placed(result.context, client_order_id)

                # Check if order is filled
                if result.context.filled_quantity and result.context.filled_quantity > 0:
                    self.order_manager.update_order_filled(
                        client_order_id=client_order_id,
                        filled_quantity=result.context.filled_quantity,
                        avg_fill_price=result.context.avg_fill_price,
                        is_partial=result.context.filled_quantity < result.context.quantity
                    )

                    # Emit OrderFilled event
                    await self._emit_order_filled(result.context, client_order_id)

                    # Emit PositionOpened event
                    await self._emit_position_opened(result.context, client_order_id)

                return True

            else:
                # Execution failed
                self.order_manager.update_order_failed(
                    client_order_id=client_order_id,
                    error=result.message,
                    is_rejected=True
                )

                # Emit OrderFailed event
                await self._emit_order_failed(
                    signal=signal,
                    client_order_id=client_order_id,
                    error=result.message
                )

                return False

        except Exception as e:
            logger.error(f"Unexpected error executing signal: {e}", exc_info=True)

            # Update order manager
            self.order_manager.update_order_failed(
                client_order_id=client_order_id,
                error=str(e)
            )

            # Emit OrderFailed event
            await self._emit_order_failed(
                signal=signal,
                client_order_id=client_order_id,
                error=str(e)
            )

            return False

    async def _emit_order_placed(self, context, client_order_id: str):
        """Emit OrderPlaced event."""
        if self.event_bus is None:
            return

        event = OrderPlaced(
            order_id=client_order_id,
            exchange_order_id=context.exchange_order_id,
            symbol=context.signal.symbol,
            side=context.signal.side,
            order_type=context.order_type or OrderType.LIMIT,
            quantity=context.quantity,
            price=context.price,
            exchange=context.signal.exchange,
            status=OrderStatus.PLACED
        )

        await self.event_bus.publish(event)
        logger.info(f"Emitted OrderPlaced event: {client_order_id}")

    async def _emit_order_filled(self, context, client_order_id: str):
        """Emit OrderFilled event."""
        if self.event_bus is None:
            return

        event = OrderFilled(
            order_id=client_order_id,
            exchange_order_id=context.exchange_order_id,
            symbol=context.signal.symbol,
            side=context.signal.side,
            quantity=context.quantity,
            filled_quantity=context.filled_quantity,
            avg_fill_price=context.avg_fill_price,
            exchange=context.signal.exchange,
            status=OrderStatus.FILLED,
            commission=context.metadata.get('commission', 0.0),
            commission_asset=context.metadata.get('commission_asset', 'USDT')
        )

        await self.event_bus.publish(event)
        logger.info(f"Emitted OrderFilled event: {client_order_id}")

    async def _emit_order_failed(self, signal: TradingSignalGenerated, client_order_id: str, error: str):
        """Emit OrderFailed event."""
        if self.event_bus is None:
            return

        event = OrderFailed(
            order_id=client_order_id,
            symbol=signal.symbol,
            side=signal.side,
            error_code=None,
            error_message=error,
            exchange=signal.exchange,
            retry_count=0,
            is_retriable=False
        )

        await self.event_bus.publish(event)
        logger.error(f"Emitted OrderFailed event: {client_order_id} - {error}")

    async def _emit_position_opened(self, context, client_order_id: str):
        """Emit PositionOpened event."""
        if self.event_bus is None:
            return

        event = PositionOpened(
            position_id=f"pos_{uuid.uuid4().hex[:16]}",
            symbol=context.signal.symbol,
            side=context.signal.side,
            entry_price=context.avg_fill_price or context.price,
            quantity=context.filled_quantity,
            exchange=context.signal.exchange,
            market_type=context.signal.market_type,
            stop_loss=context.stop_loss_price,
            take_profit=context.take_profit_price,
            order_id=client_order_id
        )

        await self.event_bus.publish(event)
        logger.info(f"Emitted PositionOpened event: {event.position_id}")

    async def _get_account_balance(self, exchange: str) -> float:
        """
        Get account balance from exchange.

        Args:
            exchange: Exchange name

        Returns:
            Account balance in USDT
        """
        try:
            exchange_adapter = await self.exchange_factory.get_exchange(exchange)
            if exchange_adapter is None:
                logger.warning(f"Exchange adapter not found: {exchange}, using default balance")
                return 10000.0

            balances = await exchange_adapter.get_balance(asset="USDT")
            usdt_balance = balances.get("USDT")

            if usdt_balance:
                return usdt_balance.total

            return 10000.0

        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 10000.0

    async def _get_current_positions(self) -> list:
        """
        Get current open positions.

        Returns:
            List of open positions
        """
        # In a real implementation, this would query from position monitor
        # For now, return active orders from order manager
        active_orders = self.order_manager.get_active_orders()
        return active_orders

    def get_stats(self) -> Dict[str, Any]:
        """
        Get execution engine statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "running": self._running,
            "order_stats": self.order_manager.get_stats(),
            "pipeline": self.pipeline.get_handler_chain(),
            "exchange_factory": self.exchange_factory.get_supported_exchanges()
        }
