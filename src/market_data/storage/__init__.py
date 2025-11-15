"""
Market data storage layer - Per-pair DuckDB isolation.

This module provides:
- DatabaseManager: Per-pair database isolation (zero race conditions)
- ConnectionPoolManager: LRU-based connection pooling (max 200 connections)
- Schema: Table definitions and retention policies
- Queries: Optimized SQL templates for analytics

Architecture:
- ONE database file per trading pair (exchange/market/symbol)
- ZERO write contention across 100+ pairs
- NO symbol columns (implied by database path)
- 15-minute data retention (aggressive cleanup)

Example:
    from market_data.storage import DatabaseManager, get_pool

    # Option 1: Direct database access
    db_mgr = DatabaseManager()
    conn = db_mgr.get_connection("binance", "spot", "BTCUSDT")
    conn.execute("INSERT INTO ticks VALUES (NOW(), 50000.0, 1.5, 'BUY', '12345')")

    # Option 2: Connection pooling (recommended for production)
    pool = get_pool(max_connections=200)
    conn = pool.acquire("binance", "spot", "BTCUSDT")
    # Use connection
    pool.release(conn)
"""

from .database_manager import DatabaseManager
from .connection_pool import ConnectionPoolManager, get_pool
from .schema import (
    create_all_tables,
    cleanup_old_data,
    get_table_stats,
)
from .queries import (
    # Analytics queries
    calculate_cvd_query,
    calculate_order_flow_imbalance_query,
    calculate_market_profile_query,
    detect_fvg_query,
    # Read queries
    get_recent_ticks_query,
    get_candles_query,
    get_active_supply_zones_query,
    get_active_demand_zones_query,
    get_unfilled_fvgs_query,
    # Insert queries
    insert_tick_query,
    insert_candle_query,
    insert_order_flow_query,
    insert_market_profile_query,
    insert_supply_demand_zone_query,
    insert_fvg_query,
    # Update queries
    update_fvg_fill_query,
    update_zone_status_query,
    # Helper functions
    execute_query,
    execute_insert,
    execute_update,
)

__all__ = [
    # Core managers
    "DatabaseManager",
    "ConnectionPoolManager",
    "get_pool",
    # Schema functions
    "create_all_tables",
    "cleanup_old_data",
    "get_table_stats",
    # Analytics queries
    "calculate_cvd_query",
    "calculate_order_flow_imbalance_query",
    "calculate_market_profile_query",
    "detect_fvg_query",
    # Read queries
    "get_recent_ticks_query",
    "get_candles_query",
    "get_active_supply_zones_query",
    "get_active_demand_zones_query",
    "get_unfilled_fvgs_query",
    # Insert queries
    "insert_tick_query",
    "insert_candle_query",
    "insert_order_flow_query",
    "insert_market_profile_query",
    "insert_supply_demand_zone_query",
    "insert_fvg_query",
    # Update queries
    "update_fvg_fill_query",
    "update_zone_status_query",
    # Helper functions
    "execute_query",
    "execute_insert",
    "execute_update",
]
