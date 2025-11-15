"""
Unit tests for DatabaseManager - Per-pair isolation testing.

Tests:
1. Per-pair database isolation (separate DB files)
2. Concurrent writes across multiple pairs
3. Schema creation
4. Data cleanup
5. Connection management
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import threading
import time

from src.market_data.storage import (
    DatabaseManager,
    insert_tick_query,
    get_recent_ticks_query,
    execute_query,
    execute_insert,
)


@pytest.fixture
def temp_db_dir():
    """Create temporary directory for test databases."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def db_manager(temp_db_dir):
    """Create DatabaseManager with temporary directory."""
    manager = DatabaseManager(base_dir=temp_db_dir)
    yield manager
    manager.close_all()


def test_per_pair_database_isolation(db_manager, temp_db_dir):
    """Test that each trading pair gets its own database file."""
    # Create connections for different pairs
    conn_btc = db_manager.get_connection("binance", "spot", "BTCUSDT")
    conn_eth = db_manager.get_connection("binance", "spot", "ETHUSDT")
    conn_sol = db_manager.get_connection("binance", "futures", "SOLUSDT")

    # Verify separate database files exist
    btc_path = Path(temp_db_dir) / "binance" / "spot" / "BTCUSDT" / "trading.duckdb"
    eth_path = Path(temp_db_dir) / "binance" / "spot" / "ETHUSDT" / "trading.duckdb"
    sol_path = Path(temp_db_dir) / "binance" / "futures" / "SOLUSDT" / "trading.duckdb"

    assert btc_path.exists(), "BTCUSDT database should exist"
    assert eth_path.exists(), "ETHUSDT database should exist"
    assert sol_path.exists(), "SOLUSDT database should exist"

    # Verify they are different files
    assert btc_path != eth_path
    assert btc_path != sol_path
    assert eth_path != sol_path

    # Verify connections are different
    assert conn_btc is not conn_eth
    assert conn_btc is not conn_sol


def test_concurrent_writes_no_contention(db_manager):
    """Test concurrent writes to different pairs (should have zero contention)."""
    results = []

    def write_ticks(exchange, market, symbol, num_ticks):
        """Write ticks to a specific pair."""
        try:
            conn = db_manager.get_connection(exchange, market, symbol)
            query = insert_tick_query()

            for i in range(num_ticks):
                execute_insert(conn, query, [
                    datetime.now(),
                    50000.0 + i,
                    1.5,
                    'BUY',
                    f'trade_{i}'
                ])

            results.append((symbol, num_ticks, "SUCCESS"))
        except Exception as e:
            results.append((symbol, 0, f"ERROR: {e}"))

    # Create 5 threads writing to different pairs simultaneously
    threads = [
        threading.Thread(target=write_ticks, args=("binance", "spot", "BTCUSDT", 10)),
        threading.Thread(target=write_ticks, args=("binance", "spot", "ETHUSDT", 10)),
        threading.Thread(target=write_ticks, args=("binance", "spot", "SOLUSDT", 10)),
        threading.Thread(target=write_ticks, args=("binance", "futures", "BTCUSDT", 10)),
        threading.Thread(target=write_ticks, args=("bybit", "spot", "BTCUSDT", 10)),
    ]

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Verify all writes succeeded
    assert len(results) == 5
    for symbol, count, status in results:
        assert status == "SUCCESS", f"{symbol} failed: {status}"
        assert count == 10


def test_schema_creation(db_manager):
    """Test that all tables are created correctly."""
    conn = db_manager.get_connection("binance", "spot", "BTCUSDT")

    # Check all expected tables exist
    tables = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """).fetchall()

    table_names = [t[0] for t in tables]

    expected_tables = [
        'ticks',
        'candles_1m',
        'candles_5m',
        'candles_15m',
        'order_flow',
        'market_profile',
        'supply_demand_zones',
        'fair_value_gaps'
    ]

    for expected in expected_tables:
        assert expected in table_names, f"Table {expected} not found"


def test_insert_and_query_ticks(db_manager):
    """Test inserting and querying ticks."""
    conn = db_manager.get_connection("binance", "spot", "BTCUSDT")

    # Insert test ticks
    insert_query = insert_tick_query()
    test_ticks = [
        (datetime.now(), 50000.0, 1.5, 'BUY', 'trade_1'),
        (datetime.now(), 50001.0, 2.0, 'SELL', 'trade_2'),
        (datetime.now(), 50002.0, 1.0, 'BUY', 'trade_3'),
    ]

    for tick in test_ticks:
        execute_insert(conn, insert_query, tick)

    # Query ticks
    query = get_recent_ticks_query(limit=10)
    results = execute_query(conn, query)

    assert len(results) == 3, "Should have 3 ticks"

    # Verify data (most recent first)
    assert results[0][1] == 50002.0  # price
    assert results[0][3] == 'BUY'  # side
    assert results[1][1] == 50001.0
    assert results[1][3] == 'SELL'


def test_data_cleanup(db_manager):
    """Test data cleanup based on retention policy."""
    conn = db_manager.get_connection("binance", "spot", "BTCUSDT")

    # Insert old ticks (beyond retention period)
    insert_query = insert_tick_query()
    old_timestamp = datetime.now() - timedelta(minutes=20)

    execute_insert(conn, insert_query, [
        old_timestamp,
        50000.0,
        1.5,
        'BUY',
        'old_trade'
    ])

    # Insert recent ticks
    execute_insert(conn, insert_query, [
        datetime.now(),
        50001.0,
        2.0,
        'BUY',
        'recent_trade'
    ])

    # Run cleanup (15-minute retention)
    db_manager.cleanup_old_data("binance", "spot", "BTCUSDT", retention_minutes=15)

    # Query remaining ticks
    query = get_recent_ticks_query(limit=10)
    results = execute_query(conn, query)

    # Should only have recent tick
    assert len(results) == 1, "Old ticks should be cleaned up"
    assert results[0][4] == 'recent_trade'  # trade_id


def test_connection_reuse(db_manager):
    """Test that connections are reused for same pair."""
    conn1 = db_manager.get_connection("binance", "spot", "BTCUSDT")
    conn2 = db_manager.get_connection("binance", "spot", "BTCUSDT")

    # Should be the same connection object
    assert conn1 is conn2, "Connections should be reused"


def test_close_connection(db_manager):
    """Test closing individual connections."""
    conn = db_manager.get_connection("binance", "spot", "BTCUSDT")
    assert conn is not None

    # Close connection
    db_manager.close_connection("binance", "spot", "BTCUSDT")

    # Get new connection (should be different)
    new_conn = db_manager.get_connection("binance", "spot", "BTCUSDT")
    assert new_conn is not conn


def test_close_all_connections(db_manager):
    """Test closing all connections."""
    # Create multiple connections
    db_manager.get_connection("binance", "spot", "BTCUSDT")
    db_manager.get_connection("binance", "spot", "ETHUSDT")
    db_manager.get_connection("binance", "futures", "SOLUSDT")

    # Verify connections exist
    assert len(db_manager.connections) == 3

    # Close all
    db_manager.close_all()

    # Verify all connections closed
    assert len(db_manager.connections) == 0


def test_get_active_pairs(db_manager):
    """Test getting list of active pairs."""
    # Create connections
    db_manager.get_connection("binance", "spot", "BTCUSDT")
    db_manager.get_connection("binance", "spot", "ETHUSDT")
    db_manager.get_connection("bybit", "futures", "SOLUSDT")

    # Get active pairs
    pairs = db_manager.get_active_pairs()

    assert len(pairs) == 3
    assert ("binance", "spot", "BTCUSDT") in pairs
    assert ("binance", "spot", "ETHUSDT") in pairs
    assert ("bybit", "futures", "SOLUSDT") in pairs


def test_get_db_stats(db_manager):
    """Test getting database statistics."""
    conn = db_manager.get_connection("binance", "spot", "BTCUSDT")

    # Insert some test data
    insert_query = insert_tick_query()
    for i in range(5):
        execute_insert(conn, insert_query, [
            datetime.now(),
            50000.0 + i,
            1.5,
            'BUY',
            f'trade_{i}'
        ])

    # Get stats
    stats = db_manager.get_db_stats("binance", "spot", "BTCUSDT")

    assert 'ticks' in stats
    assert stats['ticks'] == 5
    assert 'file_size_mb' in stats
    assert stats['file_size_mb'] > 0


def test_context_manager(temp_db_dir):
    """Test DatabaseManager as context manager."""
    with DatabaseManager(base_dir=temp_db_dir) as manager:
        conn = manager.get_connection("binance", "spot", "BTCUSDT")
        assert conn is not None

    # Connections should be closed after exiting context
    assert len(manager.connections) == 0


def test_read_only_connection(db_manager):
    """Test opening connection in read-only mode."""
    # First create database with write connection
    write_conn = db_manager.get_connection("binance", "spot", "BTCUSDT", read_only=False)

    # Insert test data
    execute_insert(write_conn, insert_tick_query(), [
        datetime.now(),
        50000.0,
        1.5,
        'BUY',
        'trade_1'
    ])

    # Close and reopen in read-only mode
    db_manager.close_connection("binance", "spot", "BTCUSDT")
    read_conn = db_manager.get_connection("binance", "spot", "BTCUSDT", read_only=True)

    # Should be able to read
    results = execute_query(read_conn, get_recent_ticks_query(limit=10))
    assert len(results) == 1

    # Should NOT be able to write
    with pytest.raises(Exception):
        execute_insert(read_conn, insert_tick_query(), [
            datetime.now(),
            50001.0,
            2.0,
            'BUY',
            'trade_2'
        ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
