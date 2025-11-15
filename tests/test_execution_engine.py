"""
Test suite for execution engine.

Tests the complete execution pipeline with a mock exchange adapter.
"""

import asyncio
import pytest
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.core.events import (
    TradingSignalGenerated,
    OrderSide,
    OrderType,
    OrderStatus
)
from src.execution import (
    ExecutionEngine,
    ExecutionPipeline,
    OrderManager,
    ExchangeAdapter,
    Balance,
    Position,
    OrderInfo,
    ExchangeFactory
)


class MockExchangeAdapter(ExchangeAdapter):
    """Mock exchange adapter for testing."""

    def __init__(self, **kwargs):
        # Extract and ignore additional kwargs like market_type
        api_key = kwargs.get('api_key')
        api_secret = kwargs.get('api_secret')
        testnet = kwargs.get('testnet', False)
        super().__init__(api_key=api_key, api_secret=api_secret, testnet=testnet)
        self._orders = {}
        self._balance = Balance(
            asset="USDT",
            free=10000.0,
            locked=0.0,
            total=10000.0
        )

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        client_order_id: Optional[str] = None,
        time_in_force: str = "GTC",
        **kwargs
    ) -> OrderInfo:
        """Place a mock order."""
        order_id = f"mock_order_{len(self._orders) + 1}"

        order_info = OrderInfo(
            order_id=order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=OrderStatus.FILLED,  # Immediately fill for testing
            price=price,
            quantity=quantity,
            filled_quantity=quantity,
            avg_fill_price=price or 50000.0,
            commission=quantity * 0.001,  # 0.1% fee
            commission_asset="USDT",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            raw_data={}
        )

        self._orders[order_id] = order_info
        return order_info

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> bool:
        return True

    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> OrderInfo:
        return self._orders.get(order_id)

    async def get_balance(self, asset: Optional[str] = None) -> Dict[str, Balance]:
        return {"USDT": self._balance}

    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        return []

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return {
            "bid": 50000.0,
            "ask": 50001.0,
            "last": 50000.5,
        }

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "min_qty": 0.001,
            "price_precision": 2,
        }

    def get_exchange_name(self) -> str:
        return "mock_exchange"


class MockEventBus:
    """Mock event bus for testing."""

    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)

    def subscribe(self, event_type, handler):
        pass


@pytest.mark.asyncio
async def test_execution_engine_with_mock_exchange():
    """Test execution engine with mock exchange adapter."""

    # Create mock exchange
    mock_exchange = MockExchangeAdapter()
    await mock_exchange.connect()

    # Create exchange factory and register mock
    factory = ExchangeFactory()
    factory.register_exchange("mock_exchange", MockExchangeAdapter)
    factory._instances["mock_exchange_spot_mainnet"] = mock_exchange

    # Create mock event bus
    event_bus = MockEventBus()

    # Create execution engine with custom pipeline that allows mock_exchange
    from src.execution.handlers import ValidationHandler, RiskManagementHandler, OrderExecutorHandler, ReconciliationHandler
    from src.execution import ExecutionPipeline

    validator = ValidationHandler(valid_exchanges=["mock_exchange", "binance", "bybit"])
    pipeline = ExecutionPipeline(validator=validator)

    engine = ExecutionEngine(pipeline=pipeline, exchange_factory=factory, event_bus=event_bus)
    await engine.start()

    # Create test signal
    signal = TradingSignalGenerated(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        signal_strength=0.8,
        confluence_score=7.5,
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        position_size_pct=2.0,
        exchange="mock_exchange",
        market_type="spot"
    )

    # Execute signal
    success = await engine.execute_signal(signal)

    # Verify execution
    assert success is True, "Execution should succeed"

    # Check order manager
    stats = engine.order_manager.get_stats()
    assert stats["total_orders"] > 0, "Should have created orders"

    # Check emitted events
    assert len(event_bus.events) > 0, "Should have emitted events"

    # Verify event types
    event_types = [type(e).__name__ for e in event_bus.events]
    assert "OrderPlaced" in event_types, "Should emit OrderPlaced"
    assert "OrderFilled" in event_types, "Should emit OrderFilled"
    assert "PositionOpened" in event_types, "Should emit PositionOpened"

    # Stop engine
    await engine.stop()

    print("✓ Test passed: Execution engine with mock exchange")


@pytest.mark.asyncio
async def test_validation_failure():
    """Test execution pipeline validation failure."""

    # Create mock exchange
    factory = ExchangeFactory()
    factory.register_exchange("mock_exchange", MockExchangeAdapter)

    # Create execution engine
    engine = ExecutionEngine(exchange_factory=factory)
    await engine.start()

    # Create invalid signal (low confluence score)
    signal = TradingSignalGenerated(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        signal_strength=0.5,
        confluence_score=1.0,  # Below minimum threshold
        entry_price=50000.0,
        exchange="mock_exchange"
    )

    # Execute signal
    success = await engine.execute_signal(signal)

    # Should fail validation
    assert success is False, "Execution should fail validation"

    await engine.stop()

    print("✓ Test passed: Validation failure")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_execution_engine_with_mock_exchange())
    asyncio.run(test_validation_failure())
