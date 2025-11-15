"""
Test script for the Position Monitoring System.

This script demonstrates:
1. Position creation and tracking
2. Trailing stop management
3. Portfolio risk management
4. Dump detection
5. Circuit breaker functionality
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from position.models import Position, PositionSide, AssetType, PositionState
from position.monitor import PositionMonitor, create_mock_position
from position.trailing_stop import TrailingStopManager
from position.portfolio_risk_manager import PortfolioRiskManager
from core.simple_events import event_bus, PositionOpened, PositionClosed, OrderSide


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("test_position_monitoring")


async def test_trailing_stops():
    """Test trailing stop functionality."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 1: Trailing Stop Management")
    logger.info("=" * 70)

    # Create trailing stop manager
    tsm = TrailingStopManager()

    # Create mock positions
    positions = [
        create_mock_position(
            symbol="ETHUSDT",
            side=PositionSide.LONG,
            entry_price=3000.0,
            quantity=1.0,
            asset_type=AssetType.CRYPTO_REGULAR
        ),
        create_mock_position(
            symbol="PEPEUSDT",
            side=PositionSide.LONG,
            entry_price=0.00001,
            quantity=1000000.0,
            asset_type=AssetType.CRYPTO_MEME
        ),
    ]

    # Add positions to trailing stop manager
    for pos in positions:
        await tsm.add_position(pos)

    logger.info("\n📊 Initial Positions:")
    stats = tsm.get_stats()
    logger.info(f"  • Total positions: {stats['total_positions']}")
    logger.info(f"  • Symbols: {stats['symbols']}")

    # Simulate price movements for ETH (regular crypto - 0.5% trailing)
    logger.info("\n📈 ETH Price Movement (0.5% trailing stop):")
    eth_prices = [3000, 3010, 3020, 3030, 3025, 3020, 3015, 3010]

    for price in eth_prices:
        await tsm.update_on_tick("ETHUSDT", price)
        eth_pos = tsm.get_positions_for_symbol("ETHUSDT")
        if eth_pos:
            pos = list(eth_pos.values())[0]
            logger.info(
                f"  Price: ${price:,.2f} | "
                f"Highest: ${pos.highest_price:,.2f} | "
                f"Stop: ${pos.trailing_stop_price:,.2f} | "
                f"P&L: {pos.unrealized_pnl_pct:+.2f}%"
            )
        await asyncio.sleep(0.5)

    # Simulate price movements for PEPE (meme coin - 17.5% trailing)
    logger.info("\n📈 PEPE Price Movement (17.5% trailing stop):")
    pepe_prices = [0.00001, 0.000012, 0.000014, 0.000015, 0.000013, 0.000011]

    for price in pepe_prices:
        await tsm.update_on_tick("PEPEUSDT", price)
        pepe_pos = tsm.get_positions_for_symbol("PEPEUSDT")
        if pepe_pos:
            pos = list(pepe_pos.values())[0]
            logger.info(
                f"  Price: ${price:.8f} | "
                f"Highest: ${pos.highest_price:.8f} | "
                f"Stop: ${pos.trailing_stop_price:.8f} | "
                f"P&L: {pos.unrealized_pnl_pct:+.2f}%"
            )
        await asyncio.sleep(0.5)

    # Final stats
    logger.info("\n📊 Final Stats:")
    stats = tsm.get_stats()
    logger.info(f"  • Open positions: {stats['open_positions']}")
    logger.info(f"  • Profitable: {stats['profitable_positions']}")
    logger.info(f"  • Total unrealized P&L: ${stats['total_unrealized_pnl']:+,.2f}")


async def test_portfolio_risk_management():
    """Test portfolio risk management."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Portfolio Risk Management")
    logger.info("=" * 70)

    # Create configuration
    config = {
        'portfolio_risk': {
            'dump_detection': {
                'volume_reversal_candles': 3,
                'order_flow_flip_ratio': 2.5,
            },
            'correlation': {
                'dump_threshold_pct': 1.5,
                'dump_timeframe_minutes': 5,
                'correlation_threshold': 0.7,
            },
            'health': {},
            'circuit_breaker': {
                'level_1_pct': 3.0,
                'level_2_pct': 4.0,
                'level_3_pct': 5.0,
            },
            'hold_time': {
                'max_hold_scalping': 30,
                'max_hold_meme': 1440,
            },
        }
    }

    # Create trailing stop manager
    tsm = TrailingStopManager()

    # Create portfolio risk manager
    prm = PortfolioRiskManager(config['portfolio_risk'])

    # Create mock positions
    positions = [
        create_mock_position("ETHUSDT", PositionSide.LONG, 3000.0, 1.0),
        create_mock_position("BTCUSDT", PositionSide.LONG, 50000.0, 0.1),
        create_mock_position("SOLUSDT", PositionSide.LONG, 100.0, 10.0),
    ]

    # Add positions
    for pos in positions:
        await tsm.add_position(pos)
        pos.update_price(pos.entry_price * 1.01)  # All up 1%

    # Start portfolio risk manager
    await prm.start(tsm)

    logger.info("\n📊 Portfolio Health Check:")
    health = await prm.health_monitor.calculate_health(tsm.get_all_positions())
    logger.info(f"  • Total positions: {health.total_positions}")
    logger.info(f"  • Total unrealized P&L: ${health.total_unrealized_pnl:+,.2f}")
    logger.info(f"  • Health score: {health.health_score:.1f}/100")

    # Test circuit breaker
    logger.info("\n🔥 Testing Circuit Breaker:")
    prm.circuit_breaker.set_session_start_balance(10000.0)

    # Simulate losses
    losses = [
        (-250, "2.5% drawdown - No action"),
        (-300, "3.0% drawdown - Level 1: Close worst 50%"),
        (-400, "4.0% drawdown - Level 2: Close ALL positions"),
        (-500, "5.0% drawdown - Level 3: Close all + STOP TRADING"),
    ]

    for loss, description in losses:
        prm.circuit_breaker.update_daily_pnl(loss)
        drawdown_pct = prm.circuit_breaker.get_drawdown_pct()
        level = prm.circuit_breaker.should_trigger()

        logger.info(
            f"  • Loss: ${loss:+,} | "
            f"Drawdown: {abs(drawdown_pct):.2f}% | "
            f"Level: {level if level else 'None'} | "
            f"{description}"
        )

    # Stop portfolio risk manager
    await prm.stop()


async def test_position_monitor_integration():
    """Test full position monitor integration."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Position Monitor Integration")
    logger.info("=" * 70)

    # Create configuration
    config = {
        'portfolio_risk': {
            'dump_detection': {},
            'correlation': {},
            'health': {},
            'circuit_breaker': {},
            'hold_time': {},
        }
    }

    # Create position monitor
    monitor = PositionMonitor(config)

    # Subscribe to PositionClosed events
    closed_positions = []

    async def on_position_closed(event):
        closed_positions.append(event)
        logger.info(
            f"\n🔔 POSITION CLOSED EVENT RECEIVED: {event.symbol} | "
            f"P&L: {event.realized_pnl_pct:+.2f}%"
        )

    await event_bus.subscribe("position_closed", on_position_closed)

    # Start monitor
    await monitor.start()

    # Create and open positions
    logger.info("\n📈 Opening Positions:")

    positions_data = [
        ("ETHUSDT", PositionSide.LONG, 3000.0, 1.0, AssetType.CRYPTO_REGULAR),
        ("BTCUSDT", PositionSide.LONG, 50000.0, 0.1, AssetType.CRYPTO_MAJOR),
    ]

    for symbol, side, entry_price, quantity, asset_type in positions_data:
        position = create_mock_position(symbol, side, entry_price, quantity, asset_type)

        # Emit PositionOpened event
        event = PositionOpened(
            position_id=position.position_id,
            symbol=position.symbol,
            side=OrderSide(position.side.value),
            entry_price=position.entry_price,
            quantity=position.quantity,
            exchange=position.exchange,
            market_type=position.market_type,
            trailing_stop_distance_pct=position.trailing_stop_distance_pct,
            timestamp=datetime.utcnow(),
            metadata={}
        )

        await monitor.on_position_opened(event)
        logger.info(f"  ✓ Opened {symbol} {side.value} @ ${entry_price:,.2f}")

    # Get stats
    logger.info("\n📊 Position Monitor Stats:")
    stats = monitor.get_stats()
    logger.info(f"  • Total positions: {stats['total_positions']}")
    logger.info(f"  • Open positions: {stats['open_positions']}")
    logger.info(f"  • Symbols: {stats['symbols']}")

    # Simulate price updates
    logger.info("\n📈 Simulating Price Updates:")

    price_sequence = [
        (3010, 50500),  # +0.33%, +1%
        (3020, 51000),  # +0.67%, +2%
        (3030, 51500),  # +1.00%, +3%
        (3025, 51000),  # +0.83%, +2%
        (3015, 50000),  # +0.50%, 0%
        (2995, 49000),  # -0.17%, -2% (should trigger stops)
    ]

    for eth_price, btc_price in price_sequence:
        await monitor.update_price("ETHUSDT", eth_price)
        await monitor.update_price("BTCUSDT", btc_price)

        logger.info(f"  • ETH: ${eth_price:,} | BTC: ${btc_price:,}")
        await asyncio.sleep(1)

    # Final stats
    logger.info("\n📊 Final Stats:")
    stats = monitor.get_stats()
    logger.info(f"  • Open positions: {stats['open_positions']}")
    logger.info(f"  • Closed positions: {len(closed_positions)}")

    # Stop monitor
    await monitor.stop()


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("POSITION MONITORING SYSTEM - TEST SUITE")
    logger.info("=" * 70)

    try:
        # Test 1: Trailing stops
        await test_trailing_stops()
        await asyncio.sleep(2)

        # Test 2: Portfolio risk management
        await test_portfolio_risk_management()
        await asyncio.sleep(2)

        # Test 3: Full integration
        await test_position_monitor_integration()

        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
