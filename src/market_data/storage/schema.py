"""
DuckDB schema definitions for market data storage.

Per-pair database isolation means:
- NO symbol column needed (implied by database path)
- Simpler indexes (timestamp only)
- Better query performance
"""

import duckdb
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Table creation SQL templates
TICKS_TABLE = """
CREATE TABLE IF NOT EXISTS ticks (
    timestamp TIMESTAMP NOT NULL,
    price DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL,
    side VARCHAR(4) NOT NULL,  -- 'BUY' or 'SELL'
    trade_id VARCHAR(64),
    PRIMARY KEY (timestamp, trade_id)
);
"""

TICKS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ticks_timestamp ON ticks(timestamp);
"""

# Candle tables (1m, 5m, 15m)
CANDLES_1M_TABLE = """
CREATE TABLE IF NOT EXISTS candles_1m (
    timestamp TIMESTAMP NOT NULL PRIMARY KEY,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL,
    buy_volume DECIMAL(18, 8),
    sell_volume DECIMAL(18, 8),
    num_trades INTEGER
);
"""

CANDLES_1M_INDEX = """
CREATE INDEX IF NOT EXISTS idx_candles_1m_timestamp ON candles_1m(timestamp);
"""

CANDLES_5M_TABLE = """
CREATE TABLE IF NOT EXISTS candles_5m (
    timestamp TIMESTAMP NOT NULL PRIMARY KEY,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL,
    buy_volume DECIMAL(18, 8),
    sell_volume DECIMAL(18, 8),
    num_trades INTEGER
);
"""

CANDLES_5M_INDEX = """
CREATE INDEX IF NOT EXISTS idx_candles_5m_timestamp ON candles_5m(timestamp);
"""

CANDLES_15M_TABLE = """
CREATE TABLE IF NOT EXISTS candles_15m (
    timestamp TIMESTAMP NOT NULL PRIMARY KEY,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL,
    buy_volume DECIMAL(18, 8),
    sell_volume DECIMAL(18, 8),
    num_trades INTEGER
);
"""

CANDLES_15M_INDEX = """
CREATE INDEX IF NOT EXISTS idx_candles_15m_timestamp ON candles_15m(timestamp);
"""

# Order flow metrics
ORDER_FLOW_TABLE = """
CREATE TABLE IF NOT EXISTS order_flow (
    timestamp TIMESTAMP NOT NULL PRIMARY KEY,
    cvd DECIMAL(18, 8) NOT NULL,  -- Cumulative Volume Delta
    imbalance_ratio DECIMAL(10, 4),  -- Buy/Sell ratio
    buy_volume DECIMAL(18, 8),
    sell_volume DECIMAL(18, 8),
    net_volume DECIMAL(18, 8)
);
"""

ORDER_FLOW_INDEX = """
CREATE INDEX IF NOT EXISTS idx_order_flow_timestamp ON order_flow(timestamp);
"""

# Market profile data
MARKET_PROFILE_TABLE = """
CREATE TABLE IF NOT EXISTS market_profile (
    timestamp TIMESTAMP NOT NULL PRIMARY KEY,
    poc DECIMAL(18, 8) NOT NULL,  -- Point of Control
    value_area_high DECIMAL(18, 8) NOT NULL,
    value_area_low DECIMAL(18, 8) NOT NULL,
    session_high DECIMAL(18, 8),
    session_low DECIMAL(18, 8),
    timeframe VARCHAR(10) NOT NULL  -- '1h', '4h', '1d'
);
"""

MARKET_PROFILE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_market_profile_timestamp ON market_profile(timestamp);
"""

# Supply/demand zones
SUPPLY_DEMAND_ZONES_TABLE = """
CREATE TABLE IF NOT EXISTS supply_demand_zones (
    id INTEGER PRIMARY KEY,
    zone_type VARCHAR(10) NOT NULL,  -- 'SUPPLY' or 'DEMAND'
    price_high DECIMAL(18, 8) NOT NULL,
    price_low DECIMAL(18, 8) NOT NULL,
    strength INTEGER NOT NULL,  -- 0-100
    status VARCHAR(10) NOT NULL,  -- 'FRESH', 'TESTED', 'BROKEN'
    created_at TIMESTAMP NOT NULL,
    tested_count INTEGER DEFAULT 0,
    last_tested_at TIMESTAMP
);
"""

SUPPLY_DEMAND_ZONES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_supply_demand_zones_status ON supply_demand_zones(status);
CREATE INDEX IF NOT EXISTS idx_supply_demand_zones_created ON supply_demand_zones(created_at);
"""

# Fair value gaps
FAIR_VALUE_GAPS_TABLE = """
CREATE TABLE IF NOT EXISTS fair_value_gaps (
    id INTEGER PRIMARY KEY,
    gap_type VARCHAR(10) NOT NULL,  -- 'BULLISH' or 'BEARISH'
    price_high DECIMAL(18, 8) NOT NULL,
    price_low DECIMAL(18, 8) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    filled_pct DECIMAL(5, 2) DEFAULT 0.0,
    status VARCHAR(10) NOT NULL,  -- 'UNFILLED', 'PARTIAL', 'FILLED'
    filled_at TIMESTAMP
);
"""

FAIR_VALUE_GAPS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_fvg_status ON fair_value_gaps(status);
CREATE INDEX IF NOT EXISTS idx_fvg_created ON fair_value_gaps(created_at);
"""


def create_all_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Create all tables and indexes for a per-pair database.

    Args:
        conn: DuckDB connection to the per-pair database
    """
    try:
        # Create ticks table
        conn.execute(TICKS_TABLE)
        conn.execute(TICKS_INDEX)
        logger.debug("Created ticks table and index")

        # Create candle tables
        conn.execute(CANDLES_1M_TABLE)
        conn.execute(CANDLES_1M_INDEX)
        conn.execute(CANDLES_5M_TABLE)
        conn.execute(CANDLES_5M_INDEX)
        conn.execute(CANDLES_15M_TABLE)
        conn.execute(CANDLES_15M_INDEX)
        logger.debug("Created candle tables and indexes")

        # Create order flow table
        conn.execute(ORDER_FLOW_TABLE)
        conn.execute(ORDER_FLOW_INDEX)
        logger.debug("Created order_flow table and index")

        # Create market profile table
        conn.execute(MARKET_PROFILE_TABLE)
        conn.execute(MARKET_PROFILE_INDEX)
        logger.debug("Created market_profile table and index")

        # Create supply/demand zones table
        conn.execute(SUPPLY_DEMAND_ZONES_TABLE)
        conn.execute(SUPPLY_DEMAND_ZONES_INDEX)
        logger.debug("Created supply_demand_zones table and indexes")

        # Create fair value gaps table
        conn.execute(FAIR_VALUE_GAPS_TABLE)
        conn.execute(FAIR_VALUE_GAPS_INDEX)
        logger.debug("Created fair_value_gaps table and indexes")

        conn.commit()
        logger.info("All tables created successfully")

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


def cleanup_old_data(conn: duckdb.DuckDBPyConnection, retention_minutes: int = 15) -> None:
    """
    Clean up old data based on retention policy (15-minute default).

    Args:
        conn: DuckDB connection
        retention_minutes: Data retention in minutes
    """
    try:
        # Delete old ticks (15 minutes)
        conn.execute(f"""
            DELETE FROM ticks
            WHERE timestamp < NOW() - INTERVAL '{retention_minutes} minutes'
        """)

        # Delete old 1m candles (15 minutes)
        conn.execute(f"""
            DELETE FROM candles_1m
            WHERE timestamp < NOW() - INTERVAL '{retention_minutes} minutes'
        """)

        # Delete old 5m candles (1 hour)
        conn.execute(f"""
            DELETE FROM candles_5m
            WHERE timestamp < NOW() - INTERVAL '60 minutes'
        """)

        # Delete old 15m candles (1 hour)
        conn.execute(f"""
            DELETE FROM candles_15m
            WHERE timestamp < NOW() - INTERVAL '60 minutes'
        """)

        # Delete old order flow data (15 minutes)
        conn.execute(f"""
            DELETE FROM order_flow
            WHERE timestamp < NOW() - INTERVAL '{retention_minutes} minutes'
        """)

        # Delete old market profile data (15 minutes)
        conn.execute(f"""
            DELETE FROM market_profile
            WHERE timestamp < NOW() - INTERVAL '{retention_minutes} minutes'
        """)

        # Clean up filled FVGs older than 24 hours
        conn.execute("""
            DELETE FROM fair_value_gaps
            WHERE status = 'FILLED' AND filled_at < NOW() - INTERVAL '24 hours'
        """)

        # Keep only top 50 supply/demand zones (by strength)
        conn.execute("""
            DELETE FROM supply_demand_zones
            WHERE id NOT IN (
                SELECT id FROM supply_demand_zones
                WHERE status != 'BROKEN'
                ORDER BY strength DESC
                LIMIT 50
            )
        """)

        conn.commit()
        logger.debug(f"Cleaned up old data (retention: {retention_minutes} minutes)")

    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        raise


def get_table_stats(conn: duckdb.DuckDBPyConnection) -> dict:
    """
    Get statistics about table sizes.

    Args:
        conn: DuckDB connection

    Returns:
        Dict with table row counts
    """
    try:
        stats = {}

        tables = [
            'ticks', 'candles_1m', 'candles_5m', 'candles_15m',
            'order_flow', 'market_profile', 'supply_demand_zones', 'fair_value_gaps'
        ]

        for table in tables:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            stats[table] = result[0] if result else 0

        return stats

    except Exception as e:
        logger.error(f"Error getting table stats: {e}")
        return {}
