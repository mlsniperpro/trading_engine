"""
SQL query templates for DuckDB analytics.

All queries are optimized for per-pair databases (no symbol filtering needed).
"""

import logging
from typing import Optional, List, Dict, Any
import duckdb

logger = logging.getLogger(__name__)


def calculate_cvd_query(lookback_minutes: int = 15) -> str:
    """
    Calculate Cumulative Volume Delta (CVD) from ticks.

    CVD = SUM(buy_volume) - SUM(sell_volume)

    Args:
        lookback_minutes: Time window in minutes

    Returns:
        SQL query string
    """
    return f"""
        SELECT
            timestamp,
            SUM(CASE WHEN side = 'BUY' THEN volume ELSE -volume END)
                OVER (ORDER BY timestamp) as cvd
        FROM ticks
        WHERE timestamp >= NOW() - INTERVAL '{lookback_minutes} minutes'
        ORDER BY timestamp DESC
        LIMIT 1
    """


def calculate_order_flow_imbalance_query(window_seconds: int = 60) -> str:
    """
    Calculate order flow imbalance (buy/sell ratio).

    Imbalance = buy_volume / sell_volume

    Args:
        window_seconds: Time window in seconds

    Returns:
        SQL query string
    """
    return f"""
        WITH volume_aggregation AS (
            SELECT
                SUM(CASE WHEN side = 'BUY' THEN volume ELSE 0 END) as buy_volume,
                SUM(CASE WHEN side = 'SELL' THEN volume ELSE 0 END) as sell_volume
            FROM ticks
            WHERE timestamp >= NOW() - INTERVAL '{window_seconds} seconds'
        )
        SELECT
            buy_volume,
            sell_volume,
            CASE
                WHEN sell_volume > 0 THEN buy_volume / sell_volume
                ELSE 0
            END as imbalance_ratio,
            buy_volume - sell_volume as net_volume
        FROM volume_aggregation
    """


def calculate_market_profile_query(session_hours: int = 4) -> str:
    """
    Calculate market profile (POC, Value Area High/Low) from ticks.

    POC (Point of Control) = Price level with highest volume
    Value Area = Range containing 70% of total volume

    Args:
        session_hours: Session length in hours

    Returns:
        SQL query string
    """
    return f"""
        WITH price_volume AS (
            SELECT
                ROUND(price, 2) as price_level,
                SUM(volume) as total_volume
            FROM ticks
            WHERE timestamp >= NOW() - INTERVAL '{session_hours} hours'
            GROUP BY price_level
        ),
        total_vol AS (
            SELECT SUM(total_volume) as total FROM price_volume
        ),
        cumulative_vol AS (
            SELECT
                price_level,
                total_volume,
                SUM(total_volume) OVER (ORDER BY price_level) as cumulative_volume
            FROM price_volume
        ),
        value_area AS (
            SELECT
                MIN(CASE WHEN cumulative_volume >= (SELECT total * 0.15 FROM total_vol)
                    THEN price_level END) as value_area_low,
                MAX(CASE WHEN cumulative_volume <= (SELECT total * 0.85 FROM total_vol)
                    THEN price_level END) as value_area_high
            FROM cumulative_vol
        ),
        poc AS (
            SELECT price_level as poc_price
            FROM price_volume
            ORDER BY total_volume DESC
            LIMIT 1
        )
        SELECT
            poc.poc_price,
            value_area.value_area_high,
            value_area.value_area_low
        FROM poc, value_area
    """


def detect_fvg_query(min_gap_pct: float = 0.5) -> str:
    """
    Detect Fair Value Gaps (FVG) from 1m candles.

    FVG = 3-candle pattern where candle[1] leaves a gap between
    candle[0].high and candle[2].low (bullish) or
    candle[0].low and candle[2].high (bearish)

    Args:
        min_gap_pct: Minimum gap size as % of price

    Returns:
        SQL query string
    """
    return f"""
        WITH candle_gaps AS (
            SELECT
                c2.timestamp as gap_timestamp,
                c2.close as current_price,
                CASE
                    -- Bullish FVG: gap between c0.high and c2.low
                    WHEN c2.low > c0.high
                    THEN 'BULLISH'
                    -- Bearish FVG: gap between c0.low and c2.high
                    WHEN c2.high < c0.low
                    THEN 'BEARISH'
                    ELSE NULL
                END as gap_type,
                CASE
                    WHEN c2.low > c0.high THEN c0.high
                    WHEN c2.high < c0.low THEN c2.high
                    ELSE NULL
                END as gap_low,
                CASE
                    WHEN c2.low > c0.high THEN c2.low
                    WHEN c2.high < c0.low THEN c0.low
                    ELSE NULL
                END as gap_high,
                CASE
                    WHEN c2.low > c0.high THEN (c2.low - c0.high) / c2.close * 100
                    WHEN c2.high < c0.low THEN (c0.low - c2.high) / c2.close * 100
                    ELSE 0
                END as gap_pct
            FROM candles_1m c0
            JOIN candles_1m c1 ON c1.timestamp = c0.timestamp + INTERVAL '1 minute'
            JOIN candles_1m c2 ON c2.timestamp = c1.timestamp + INTERVAL '1 minute'
            WHERE c2.timestamp >= NOW() - INTERVAL '15 minutes'
        )
        SELECT
            gap_timestamp,
            gap_type,
            gap_low,
            gap_high,
            gap_pct,
            current_price
        FROM candle_gaps
        WHERE gap_type IS NOT NULL
          AND gap_pct >= {min_gap_pct}
        ORDER BY gap_timestamp DESC
    """


def get_recent_ticks_query(limit: int = 100) -> str:
    """
    Get recent ticks.

    Args:
        limit: Number of ticks to retrieve

    Returns:
        SQL query string
    """
    return f"""
        SELECT timestamp, price, volume, side, trade_id
        FROM ticks
        ORDER BY timestamp DESC
        LIMIT {limit}
    """


def get_candles_query(timeframe: str, limit: int = 100) -> str:
    """
    Get recent candles for a specific timeframe.

    Args:
        timeframe: Candle timeframe ('1m', '5m', '15m')
        limit: Number of candles to retrieve

    Returns:
        SQL query string
    """
    table_name = f"candles_{timeframe}"

    return f"""
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            buy_volume,
            sell_volume,
            num_trades
        FROM {table_name}
        ORDER BY timestamp DESC
        LIMIT {limit}
    """


def get_active_supply_zones_query() -> str:
    """
    Get active supply zones (FRESH or TESTED, not BROKEN).

    Returns:
        SQL query string
    """
    return """
        SELECT
            id,
            price_high,
            price_low,
            strength,
            status,
            created_at,
            tested_count
        FROM supply_demand_zones
        WHERE zone_type = 'SUPPLY'
          AND status != 'BROKEN'
        ORDER BY strength DESC, created_at DESC
        LIMIT 10
    """


def get_active_demand_zones_query() -> str:
    """
    Get active demand zones (FRESH or TESTED, not BROKEN).

    Returns:
        SQL query string
    """
    return """
        SELECT
            id,
            price_high,
            price_low,
            strength,
            status,
            created_at,
            tested_count
        FROM supply_demand_zones
        WHERE zone_type = 'DEMAND'
          AND status != 'BROKEN'
        ORDER BY strength DESC, created_at DESC
        LIMIT 10
    """


def get_unfilled_fvgs_query() -> str:
    """
    Get unfilled or partially filled Fair Value Gaps.

    Returns:
        SQL query string
    """
    return """
        SELECT
            id,
            gap_type,
            price_high,
            price_low,
            filled_pct,
            created_at
        FROM fair_value_gaps
        WHERE status IN ('UNFILLED', 'PARTIAL')
          AND created_at >= NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
    """


def insert_tick_query() -> str:
    """
    Insert a tick into the ticks table.

    Returns:
        SQL query string for prepared statement
    """
    return """
        INSERT INTO ticks (timestamp, price, volume, side, trade_id)
        VALUES (?, ?, ?, ?, ?)
    """


def insert_candle_query(timeframe: str) -> str:
    """
    Insert or update a candle.

    Args:
        timeframe: Candle timeframe ('1m', '5m', '15m')

    Returns:
        SQL query string
    """
    table_name = f"candles_{timeframe}"

    return f"""
        INSERT OR REPLACE INTO {table_name}
        (timestamp, open, high, low, close, volume, buy_volume, sell_volume, num_trades)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


def insert_order_flow_query() -> str:
    """
    Insert order flow metrics.

    Returns:
        SQL query string
    """
    return """
        INSERT OR REPLACE INTO order_flow
        (timestamp, cvd, imbalance_ratio, buy_volume, sell_volume, net_volume)
        VALUES (?, ?, ?, ?, ?, ?)
    """


def insert_market_profile_query() -> str:
    """
    Insert market profile data.

    Returns:
        SQL query string
    """
    return """
        INSERT OR REPLACE INTO market_profile
        (timestamp, poc, value_area_high, value_area_low, session_high, session_low, timeframe)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """


def insert_supply_demand_zone_query() -> str:
    """
    Insert supply/demand zone.

    Returns:
        SQL query string
    """
    return """
        INSERT INTO supply_demand_zones
        (zone_type, price_high, price_low, strength, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """


def insert_fvg_query() -> str:
    """
    Insert Fair Value Gap.

    Returns:
        SQL query string
    """
    return """
        INSERT INTO fair_value_gaps
        (gap_type, price_high, price_low, created_at, filled_pct, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """


def update_fvg_fill_query() -> str:
    """
    Update FVG fill percentage.

    Returns:
        SQL query string
    """
    return """
        UPDATE fair_value_gaps
        SET filled_pct = ?,
            status = CASE
                WHEN ? >= 100 THEN 'FILLED'
                WHEN ? > 0 THEN 'PARTIAL'
                ELSE 'UNFILLED'
            END,
            filled_at = CASE WHEN ? >= 100 THEN NOW() ELSE filled_at END
        WHERE id = ?
    """


def update_zone_status_query() -> str:
    """
    Update supply/demand zone status.

    Returns:
        SQL query string
    """
    return """
        UPDATE supply_demand_zones
        SET status = ?,
            tested_count = tested_count + 1,
            last_tested_at = NOW()
        WHERE id = ?
    """


# Helper functions to execute queries

def execute_query(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: Optional[List[Any]] = None
) -> Optional[List[tuple]]:
    """
    Execute a SQL query and return results.

    Args:
        conn: DuckDB connection
        query: SQL query string
        params: Optional query parameters

    Returns:
        Query results as list of tuples
    """
    try:
        if params:
            result = conn.execute(query, params).fetchall()
        else:
            result = conn.execute(query).fetchall()
        return result
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        logger.debug(f"Query: {query}")
        raise


def execute_insert(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: List[Any]
) -> None:
    """
    Execute an INSERT query.

    Args:
        conn: DuckDB connection
        query: SQL INSERT statement
        params: Query parameters
    """
    try:
        conn.execute(query, params)
        conn.commit()
    except Exception as e:
        logger.error(f"Error executing insert: {e}")
        logger.debug(f"Query: {query}, Params: {params}")
        raise


def execute_update(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: List[Any]
) -> None:
    """
    Execute an UPDATE query.

    Args:
        conn: DuckDB connection
        query: SQL UPDATE statement
        params: Query parameters
    """
    try:
        conn.execute(query, params)
        conn.commit()
    except Exception as e:
        logger.error(f"Error executing update: {e}")
        logger.debug(f"Query: {query}, Params: {params}")
        raise
