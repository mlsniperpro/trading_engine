"""
Integrated Trading Engine - Main Entry Point

This is the NEW integrated main.py that wires all components together:
- Event Bus (THE HEART - runs 24/7)
- DI Container (dependency injection)
- Market Data Streams (existing MarketDataManager)
- Storage Layer (DatabaseManager)
- Analytics Engine (24/7)
- Decision Engine (reactive)
- Execution Engine (reactive)
- Position Monitor (24/7)
- Notification System (reactive)
- FastAPI server (monitoring & control)

Architecture: Event-driven with always-on and reactive components
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
import uvicorn

# Core components
from src.core.event_bus import EventBus
from src.core.di_container import DependencyContainer
from src.core.events import (
    TradingSignalGenerated,
    PositionOpened,
    PositionClosed,
    OrderPlaced,
    OrderFilled,
    OrderFailed,
    SystemError as SystemErrorEvent,
)

# Market data
from src.market_data.stream.manager import MarketDataManager
from src.market_data.storage.database_manager import DatabaseManager

# Analytics
from src.analytics.engine import AnalyticsEngine

# Decision engine
from src.decision.engine import DecisionEngine, create_default_decision_engine

# Execution engine
from src.execution.engine import ExecutionEngine
from src.execution.pipeline import ExecutionPipeline
from src.execution.order_manager import OrderManager
from src.execution.exchanges.exchange_factory import ExchangeFactory

# Position monitoring
from src.position.monitor import PositionMonitor
from src.position.trailing_stop import TrailingStopManager
from src.position.portfolio_risk_manager import PortfolioRiskManager

# Notifications
from src.notifications.service import NotificationSystem
from src.notifications.sendgrid_client import SendGridNotificationService
from src.notifications.priority import PriorityHandler

# Logging
from src.log_buffer import setup_log_buffer, log_buffer

# ============================================================================
# Configuration
# ============================================================================

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Setup log buffer for API access
setup_log_buffer()

logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Integrated Trading Engine",
    version="2.0.0",
    description="Event-driven algorithmic trading engine with full component integration"
)

# Global references
event_bus: Optional[EventBus] = None
di_container: Optional[DependencyContainer] = None
market_manager: Optional[MarketDataManager] = None
analytics_engine: Optional[AnalyticsEngine] = None
decision_engine: Optional[DecisionEngine] = None
execution_engine: Optional[ExecutionEngine] = None
position_monitor: Optional[PositionMonitor] = None
notification_system: Optional[NotificationSystem] = None


# ============================================================================
# Setup Functions
# ============================================================================

def setup_di_container() -> DependencyContainer:
    """
    Setup Dependency Injection Container with all services.

    This registers all components in the DI container for
    dependency resolution and proper initialization order.
    """
    container = DependencyContainer()

    logger.info("=" * 70)
    logger.info("Setting up DI Container...")
    logger.info("=" * 70)

    # Core services
    event_bus_instance = EventBus(max_queue_size=10000)
    container.register_singleton("EventBus", event_bus_instance)
    logger.info("✓ Registered EventBus")

    # Database Manager
    db_manager = DatabaseManager(base_dir="/workspaces/trading_engine/data")
    container.register_singleton("DatabaseManager", db_manager)
    logger.info("✓ Registered DatabaseManager")

    # Analytics Engine
    analytics = AnalyticsEngine(
        event_bus=event_bus_instance,
        db_manager=db_manager,
        update_interval=2.0
    )
    container.register_singleton("AnalyticsEngine", analytics)
    logger.info("✓ Registered AnalyticsEngine")

    # Decision Engine (with default analyzers/filters)
    decision = create_default_decision_engine(min_confluence=3.0)
    container.register_singleton("DecisionEngine", decision)
    logger.info("✓ Registered DecisionEngine")

    # Execution Engine
    pipeline = ExecutionPipeline()
    order_manager = OrderManager()
    exchange_factory = ExchangeFactory()

    execution = ExecutionEngine(
        pipeline=pipeline,
        order_manager=order_manager,
        exchange_factory=exchange_factory,
        event_bus=event_bus_instance
    )
    container.register_singleton("ExecutionEngine", execution)
    logger.info("✓ Registered ExecutionEngine")

    # Position Monitor
    position_config = {
        'portfolio_risk': {
            'dump_detection': {},
            'correlation': {},
            'health': {},
            'circuit_breaker': {},
            'hold_time': {},
        }
    }
    pos_monitor = PositionMonitor(config=position_config)
    container.register_singleton("PositionMonitor", pos_monitor)
    logger.info("✓ Registered PositionMonitor")

    # Notification System (if SendGrid configured)
    sendgrid_key = os.getenv('SENDGRID_API_KEY')
    if sendgrid_key:
        sendgrid_service = SendGridNotificationService(
            api_key=sendgrid_key,
            from_email=os.getenv('ALERT_FROM_EMAIL', 'algo-engine@trading.com'),
            to_emails=[os.getenv('ALERT_EMAIL', 'trader@trading.com')]
        )
        priority_handler = PriorityHandler()
        notification_sys = NotificationSystem(
            event_bus=event_bus_instance,
            sendgrid_service=sendgrid_service,
            priority_handler=priority_handler
        )
        container.register_singleton("NotificationSystem", notification_sys)
        logger.info("✓ Registered NotificationSystem (SendGrid enabled)")
    else:
        logger.warning("⚠ SendGrid not configured - notifications disabled")

    logger.info("=" * 70)
    logger.info(f"DI Container setup complete: {len(container.get_all_services())} services")
    logger.info("=" * 70)

    return container


def setup_event_subscriptions(bus: EventBus, container: DependencyContainer):
    """
    Wire up event subscriptions between components.

    This connects components via the event bus:
    - Analytics → Decision Engine
    - Decision Engine → Execution Engine
    - Execution Engine → Position Monitor
    - All → Notification System
    """
    logger.info("=" * 70)
    logger.info("Setting up event subscriptions...")
    logger.info("=" * 70)

    # Get components from DI container
    analytics = container.resolve("AnalyticsEngine")
    decision = container.resolve("DecisionEngine")
    execution = container.resolve("ExecutionEngine")
    position = container.resolve("PositionMonitor")

    # Analytics → Decision Engine
    # (Decision engine subscribes to analytics events)
    # NOTE: This would be implemented when analytics emits proper events
    logger.info("✓ Analytics → Decision (to be wired when analytics emits events)")

    # Decision Engine → Execution Engine
    async def on_trading_signal(event: TradingSignalGenerated):
        """Forward trading signals to execution engine."""
        await execution.on_trading_signal(event)

    bus.subscribe(TradingSignalGenerated, on_trading_signal)
    logger.info("✓ Decision → Execution (TradingSignalGenerated)")

    # Execution Engine → Position Monitor
    async def on_position_opened(event: PositionOpened):
        """Forward position opened events to monitor."""
        await position.on_position_opened(event)

    bus.subscribe(PositionOpened, on_position_opened)
    logger.info("✓ Execution → Position Monitor (PositionOpened)")

    # Notification System (if available)
    notification = container.resolve_optional("NotificationSystem")
    if notification:
        # Already subscribed in NotificationSystem.start()
        logger.info("✓ All components → Notifications (via NotificationSystem)")

    logger.info("=" * 70)
    logger.info("Event subscriptions complete")
    logger.info("=" * 70)


async def start_always_on_components(container: DependencyContainer):
    """
    Start all always-on (24/7) components.

    Always-on components:
    1. Event Bus - THE HEART
    2. Analytics Engine - continuous analytics
    3. Position Monitor - continuous monitoring
    4. Notification System - event processing
    """
    logger.info("=" * 70)
    logger.info("Starting Always-On Components (24/7)...")
    logger.info("=" * 70)

    # 1. Event Bus (THE HEART)
    event_bus = container.resolve("EventBus")
    await event_bus.start()
    logger.info("✓ Event Bus started - THE HEART is beating")

    # 2. Analytics Engine
    analytics = container.resolve("AnalyticsEngine")
    await analytics.start()
    logger.info("✓ Analytics Engine started")

    # 3. Position Monitor
    position = container.resolve("PositionMonitor")
    await position.start()
    logger.info("✓ Position Monitor started")

    # 4. Execution Engine (reactive but needs to be ready)
    execution = container.resolve("ExecutionEngine")
    await execution.start()
    logger.info("✓ Execution Engine started")

    # 5. Notification System (if available)
    notification = container.resolve_optional("NotificationSystem")
    if notification:
        await notification.start()
        logger.info("✓ Notification System started")

    logger.info("=" * 70)
    logger.info("All Always-On Components Running")
    logger.info("=" * 70)


async def stop_all_components(container: DependencyContainer):
    """
    Gracefully stop all components.

    Stops in reverse dependency order:
    1. Market Data Manager (stop new data)
    2. Notification System
    3. Position Monitor
    4. Execution Engine
    5. Decision Engine
    6. Analytics Engine
    7. Event Bus (stop last - the heart)
    """
    logger.info("=" * 70)
    logger.info("Stopping all components...")
    logger.info("=" * 70)

    # Stop market data manager
    global market_manager
    if market_manager:
        logger.info("Stopping Market Data Manager...")
        await market_manager.stop()
        logger.info("✓ Market Data Manager stopped")

    # Stop notification system
    notification = container.resolve_optional("NotificationSystem")
    if notification:
        logger.info("Stopping Notification System...")
        await notification.stop()
        logger.info("✓ Notification System stopped")

    # Stop position monitor
    position = container.resolve("PositionMonitor")
    logger.info("Stopping Position Monitor...")
    await position.stop()
    logger.info("✓ Position Monitor stopped")

    # Stop execution engine
    execution = container.resolve("ExecutionEngine")
    logger.info("Stopping Execution Engine...")
    await execution.stop()
    logger.info("✓ Execution Engine stopped")

    # Stop analytics engine
    analytics = container.resolve("AnalyticsEngine")
    logger.info("Stopping Analytics Engine...")
    await analytics.stop()
    logger.info("✓ Analytics Engine stopped")

    # Stop event bus (last - the heart)
    event_bus = container.resolve("EventBus")
    logger.info("Stopping Event Bus...")
    await event_bus.stop()
    logger.info("✓ Event Bus stopped - The heart has stopped")

    logger.info("=" * 70)
    logger.info("All components stopped gracefully")
    logger.info("=" * 70)


# ============================================================================
# FastAPI Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - system status."""
    global di_container, market_manager

    components = {
        "event_bus": "active" if event_bus and event_bus.is_running else "inactive",
        "market_data": "active" if market_manager else "inactive",
        "analytics": "active" if analytics_engine and analytics_engine.running else "inactive",
        "decision": "registered" if decision_engine else "inactive",
        "execution": "active" if execution_engine and execution_engine._running else "inactive",
        "position_monitor": "active" if position_monitor and position_monitor.is_running else "inactive",
        "notifications": "active" if notification_system and notification_system.is_running else "inactive",
    }

    return {
        "name": "Integrated Trading Engine",
        "version": "2.0.0",
        "status": "running",
        "architecture": "event-driven",
        "components": components,
        "event_bus_stats": event_bus.get_stats() if event_bus else {},
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    global event_bus, di_container

    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Check each component
    if event_bus:
        health["components"]["event_bus"] = {
            "status": "running" if event_bus.is_running else "stopped",
            "queue_size": event_bus.queue_size,
            "events_processed": event_bus.get_stats().get("events_processed", 0)
        }

    if analytics_engine:
        health["components"]["analytics"] = {
            "status": "running" if analytics_engine.running else "stopped",
            "total_updates": analytics_engine.total_updates
        }

    if position_monitor:
        health["components"]["position_monitor"] = {
            "status": "running" if position_monitor.is_running else "stopped",
            "open_positions": len(position_monitor.get_open_positions())
        }

    return health


@app.get("/stats")
async def get_stats():
    """Get detailed statistics from all components."""
    global di_container

    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    if di_container:
        # Event Bus stats
        if event_bus:
            stats["components"]["event_bus"] = event_bus.get_stats()

        # Analytics stats
        if analytics_engine:
            stats["components"]["analytics"] = analytics_engine.get_statistics()

        # Decision Engine stats
        if decision_engine:
            stats["components"]["decision"] = decision_engine.get_stats()

        # Execution Engine stats
        if execution_engine:
            stats["components"]["execution"] = execution_engine.get_stats()

        # Position Monitor stats
        if position_monitor:
            stats["components"]["position_monitor"] = position_monitor.get_stats()

        # Notification stats
        if notification_system:
            stats["components"]["notifications"] = notification_system.get_stats()

    return stats


@app.get("/prices")
async def get_prices():
    """Get current prices from market data manager."""
    global market_manager

    if not market_manager:
        return {"error": "Market data manager not initialized"}

    prices = market_manager.get_current_prices()
    return {
        "dex": {k: float(v) for k, v in prices['dex'].items()},
        "cex": {k: float(v) for k, v in prices['cex'].items()},
    }


@app.get("/positions")
async def get_positions():
    """Get all open positions."""
    global position_monitor

    if not position_monitor:
        return {"error": "Position monitor not initialized"}

    open_positions = position_monitor.get_open_positions()

    return {
        "count": len(open_positions),
        "positions": [
            {
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "side": pos.side.value,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
                "state": pos.state.value,
            }
            for pos in open_positions.values()
        ]
    }


@app.get("/logs")
async def get_logs(
    lines: int = 100,
    level: str = None,
    search: str = None
):
    """
    Get application logs via API.

    Args:
        lines: Number of log lines to return (default: 100, max: 1000)
        level: Filter by log level (ERROR, WARNING, INFO, DEBUG)
        search: Search for specific text in logs
    """
    lines = min(lines, 1000)

    try:
        logs = log_buffer.get_logs(lines=lines, level=level, search=search)

        return {
            "timestamp": datetime.now().isoformat(),
            "lines_requested": lines,
            "lines_returned": len(logs),
            "filters": {
                "level": level,
                "search": search
            },
            "logs": logs
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/logs/stats")
async def get_log_stats():
    """Get log statistics."""
    try:
        stats = log_buffer.get_stats()

        # Add market data info if available
        if market_manager:
            prices = market_manager.get_current_prices()
            stats["market_data"] = {
                "dex_pools_monitored": len(prices['dex']),
                "cex_symbols_monitored": len(prices['cex']),
                "active": True
            }

        stats["timestamp"] = datetime.now().isoformat()

        return stats
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# FastAPI Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Start the integrated trading engine on FastAPI startup."""
    global event_bus, di_container, market_manager, analytics_engine
    global decision_engine, execution_engine, position_monitor, notification_system

    logger.info("=" * 70)
    logger.info("🚀 Starting Integrated Trading Engine v2.0")
    logger.info("=" * 70)

    try:
        # Step 1: Setup DI Container
        di_container = setup_di_container()

        # Step 2: Get component references
        event_bus = di_container.resolve("EventBus")
        analytics_engine = di_container.resolve("AnalyticsEngine")
        decision_engine = di_container.resolve("DecisionEngine")
        execution_engine = di_container.resolve("ExecutionEngine")
        position_monitor = di_container.resolve("PositionMonitor")
        notification_system = di_container.resolve_optional("NotificationSystem")

        # Step 3: Setup event subscriptions
        setup_event_subscriptions(event_bus, di_container)

        # Step 4: Start always-on components
        await start_always_on_components(di_container)

        # Step 5: Initialize market data manager (keep existing functionality)
        logger.info("=" * 70)
        logger.info("Initializing Market Data Manager...")
        logger.info("=" * 70)

        market_manager = MarketDataManager(
            # Ethereum DEX streams
            enable_uniswap_v3=True,
            enable_curve=True,
            enable_sushiswap=True,
            enable_balancer=True,
            uniswap_pools=[
                "ETH-USDC-0.3%",
                "ETH-USDT-0.3%",
                "ETH-USDC-0.05%",
                "ETH-USDT-0.05%",
            ],
            curve_pools=["stETH", "frxETH"],
            sushiswap_pairs=["ETH-USDC", "ETH-USDT"],
            balancer_pools=["BAL-WETH"],
            # Solana DEX streams
            enable_pump_fun=True,
            enable_raydium=True,
            enable_jupiter=True,
            enable_orca=True,
            enable_meteora=True,
            pump_fun_min_mcap=1000,
            raydium_pools=["SOL-USDC"],
            orca_pools=["SOL-USDC"],
            meteora_pools=["SOL-USDC"],
            # CEX streams
            enable_binance=True,
            binance_symbols=["ETH-USDT"],
            # Settings
            arbitrage_threshold_pct=0.3,
        )

        # Register arbitrage callback
        async def handle_arbitrage(data):
            logger.warning(
                f"🚨 ARBITRAGE: {data['price_diff_pct']:.2f}% | "
                f"DEX: ${data['dex_price']:.2f} | CEX: ${data['cex_price']:.2f} | "
                f"Action: {data['direction']}"
            )

        market_manager.on_arbitrage(handle_arbitrage)

        # Start market data streams in background
        logger.info("Starting market data streams...")

        async def start_streams_with_error_handling():
            """Wrapper to handle errors in background streams."""
            try:
                await market_manager.start()
            except Exception as e:
                logger.error(f"❌ Market data streams crashed: {e}")
                logger.exception("Full traceback:")

        asyncio.create_task(start_streams_with_error_handling())
        logger.info("✓ Market data streams task created")

        # All done!
        logger.info("=" * 70)
        logger.info("✅ INTEGRATED TRADING ENGINE STARTED")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Components Running:")
        logger.info("  ✓ Event Bus (THE HEART) - 24/7")
        logger.info("  ✓ Market Data Streams - 24/7")
        logger.info("  ✓ Analytics Engine - 24/7")
        logger.info("  ✓ Decision Engine - Reactive")
        logger.info("  ✓ Execution Engine - Reactive")
        logger.info("  ✓ Position Monitor - 24/7")
        if notification_system:
            logger.info("  ✓ Notification System - Reactive")
        logger.info("")
        logger.info("Event Flow:")
        logger.info("  Market Data → Analytics → Decision → Execution → Position Monitor")
        logger.info("  All events → Notification System")
        logger.info("")
        logger.info("API Endpoints:")
        logger.info("  • GET /          - System status")
        logger.info("  • GET /health    - Health check")
        logger.info("  • GET /stats     - Component statistics")
        logger.info("  • GET /prices    - Current prices")
        logger.info("  • GET /positions - Open positions")
        logger.info("  • GET /logs      - Application logs")
        logger.info("  • GET /docs      - API documentation")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"❌ Failed to start trading engine: {e}")
        logger.exception("Full traceback:")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Stop all components on shutdown."""
    global di_container

    logger.info("=" * 70)
    logger.info("Shutting down Integrated Trading Engine...")
    logger.info("=" * 70)

    if di_container:
        await stop_all_components(di_container)

    logger.info("✓ Trading engine shut down gracefully")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Entry point for the application."""
    print("\n" + "=" * 70)
    print("🚀 Integrated Trading Engine v2.0 - Starting")
    print("=" * 70)
    print("\nArchitecture: Event-Driven")
    print("\nComponents:")
    print("  • Event Bus (THE HEART) - 24/7 event processing")
    print("  • DI Container - Dependency injection")
    print("  • Market Data - Ethereum DEX, Solana DEX, CEX streams")
    print("  • Analytics Engine - Order flow, market profile, indicators")
    print("  • Decision Engine - Signal generation with confluence")
    print("  • Execution Engine - Order execution pipeline")
    print("  • Position Monitor - Trailing stops, portfolio risk")
    print("  • Notification System - Email alerts via SendGrid")
    print("\nAPI Server:")
    print("  • FastAPI server on http://0.0.0.0:8000")
    print("  • Swagger docs at http://0.0.0.0:8000/docs")
    print("\nPress Ctrl+C to stop...")
    print("=" * 70 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()
