"""
Main entry point for the trading engine.

This starts the market data streams and the FastAPI server.
"""

import asyncio
import logging
import os
from datetime import datetime

from fastapi import FastAPI

# Imports for market data and logging
from market_data.stream import MarketDataManager
from log_buffer import setup_log_buffer, log_buffer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Setup log buffer for API access
setup_log_buffer()

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Trading Engine API", version="0.1.0")

# Global market data manager
market_manager: MarketDataManager = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Trading Engine",
        "version": "0.1.0",
        "status": "running",
        "components": {
            "market_data": "active" if market_manager else "inactive",
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/prices")
async def get_prices():
    """Get current prices from all sources."""
    if not market_manager:
        return {"error": "Market data manager not initialized"}

    prices = market_manager.get_current_prices()
    return {
        "dex": {k: float(v) for k, v in prices['dex'].items()},
        "cex": {k: float(v) for k, v in prices['cex'].items()},
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

    Examples:
        /logs?lines=50
        /logs?level=ERROR
        /logs?search=ARBITRAGE
        /logs?lines=200&level=WARNING
    """
    # Limit lines to prevent abuse
    lines = min(lines, 1000)

    try:
        # Get logs from in-memory buffer
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


@app.get("/logs/recent")
async def get_recent_logs(lines: int = 100):
    """Get recent log lines."""
    lines = min(lines, 1000)

    try:
        logs = log_buffer.get_logs(lines=lines)

        return {
            "timestamp": datetime.now().isoformat(),
            "lines_requested": lines,
            "lines_returned": len(logs),
            "logs": logs
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/logs/errors")
async def get_error_logs(lines: int = 100):
    """Get recent error logs only."""
    lines = min(lines, 1000)

    try:
        # Get only ERROR level logs
        logs = log_buffer.get_logs(lines=lines, level="ERROR")

        return {
            "timestamp": datetime.now().isoformat(),
            "lines_requested": lines,
            "lines_returned": len(logs),
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


@app.on_event("startup")
async def startup_event():
    """Start market data streams on startup."""
    global market_manager

    logger.info("=" * 70)
    logger.info("🚀 Starting Trading Engine")
    logger.info("=" * 70)

    try:
        # Initialize market data manager
        logger.info("Initializing market data manager...")
        market_manager = MarketDataManager(
            enable_uniswap_v3=True,
            enable_binance=True,
            uniswap_pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"],
            binance_symbols=["ETH-USDT"],
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
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"❌ Failed to start market data streams: {e}")
        logger.error(f"Continuing with API server only (market data disabled)")
        logger.error("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Stop market data streams on shutdown."""
    global market_manager

    logger.info("Shutting down trading engine...")

    if market_manager:
        await market_manager.stop()

    logger.info("✓ Trading engine stopped")


def main():
    """Entry point for the application."""
    import uvicorn

    print("\n" + "=" * 70)
    print("🚀 Trading Engine - Starting")
    print("=" * 70)
    print("\nComponents:")
    print("  • FastAPI server on http://0.0.0.0:8000")
    print("  • DEX stream (Uniswap V3)")
    print("  • CEX stream (Binance)")
    print("  • Arbitrage detection")
    print("\nEndpoints:")
    print("  • GET /          - System status")
    print("  • GET /health    - Health check")
    print("  • GET /prices    - Current prices")
    print("  • GET /docs      - API documentation")
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
