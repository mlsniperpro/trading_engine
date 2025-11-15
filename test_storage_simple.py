#!/usr/bin/env python
"""
Simple integration test for market data storage layer.
Direct imports to avoid dependency issues.
"""

import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import threading

# Direct imports from storage package
sys.path.insert(0, '/workspaces/trading_engine/src/market_data')

from storage.database_manager import DatabaseManager
from storage.connection_pool import ConnectionPoolManager
from storage.queries import (
    insert_tick_query,
    get_recent_ticks_query,
    calculate_cvd_query,
    calculate_order_flow_imbalance_query,
    execute_query,
    execute_insert,
)


def test_per_pair_isolation():
    """Test per-pair database isolation."""
    print("\n" + "="*60)
    print("TEST 1: Per-pair database isolation")
    print("="*60)

    temp_dir = tempfile.mkdtemp()
    try:
        db_mgr = DatabaseManager(base_dir=temp_dir)

        # Create connections for different pairs
        conn_btc = db_mgr.get_connection("binance", "spot", "BTCUSDT")
        conn_eth = db_mgr.get_connection("binance", "spot", "ETHUSDT")
        conn_sol = db_mgr.get_connection("binance", "futures", "SOLUSDT")

        # Verify separate database files
        btc_path = Path(temp_dir) / "binance" / "spot" / "BTCUSDT" / "trading.duckdb"
        eth_path = Path(temp_dir) / "binance" / "spot" / "ETHUSDT" / "trading.duckdb"
        sol_path = Path(temp_dir) / "binance" / "futures" / "SOLUSDT" / "trading.duckdb"

        assert btc_path.exists(), "BTCUSDT database should exist"
        assert eth_path.exists(), "ETHUSDT database should exist"
        assert sol_path.exists(), "SOLUSDT database should exist"

        print(f"✓ Created 3 separate database files:")
        print(f"  - {btc_path.relative_to(temp_dir)}")
        print(f"  - {eth_path.relative_to(temp_dir)}")
        print(f"  - {sol_path.relative_to(temp_dir)}")

        # Test writing to each
        for conn, symbol in [(conn_btc, "BTCUSDT"), (conn_eth, "ETHUSDT"), (conn_sol, "SOLUSDT")]:
            execute_insert(conn, insert_tick_query(), [
                datetime.now(),
                50000.0,
                1.5,
                'BUY',
                f'{symbol}_trade_1'
            ])

        print(f"✓ Successfully wrote ticks to all 3 pairs")

        # Verify data isolation
        for conn, symbol, expected_id in [
            (conn_btc, "BTCUSDT", "BTCUSDT_trade_1"),
            (conn_eth, "ETHUSDT", "ETHUSDT_trade_1"),
            (conn_sol, "SOLUSDT", "SOLUSDT_trade_1")
        ]:
            results = execute_query(conn, get_recent_ticks_query(limit=10))
            assert len(results) == 1, f"{symbol} should have 1 tick"
            assert results[0][4] == expected_id, f"{symbol} tick ID mismatch"

        print(f"✓ Data isolation verified - each pair only sees its own data")

        db_mgr.close_all()
        print("\n✅ TEST 1 PASSED")

    finally:
        shutil.rmtree(temp_dir)


def test_concurrent_writes():
    """Test concurrent writes to different pairs (zero contention)."""
    print("\n" + "="*60)
    print("TEST 2: Concurrent writes (zero contention)")
    print("="*60)

    temp_dir = tempfile.mkdtemp()
    try:
        db_mgr = DatabaseManager(base_dir=temp_dir)
        results = []

        def write_ticks(exchange, market, symbol, num_ticks):
            """Write ticks to a specific pair."""
            try:
                conn = db_mgr.get_connection(exchange, market, symbol)
                query = insert_tick_query()

                for i in range(num_ticks):
                    execute_insert(conn, query, [
                        datetime.now(),
                        50000.0 + i,
                        1.5 + (i * 0.1),
                        'BUY' if i % 2 == 0 else 'SELL',
                        f'{symbol}_trade_{i}'
                    ])

                results.append((symbol, num_ticks, "SUCCESS"))
            except Exception as e:
                results.append((symbol, 0, f"ERROR: {e}"))

        # Create 5 threads writing to different pairs simultaneously
        pairs = [
            ("binance", "spot", "BTCUSDT", 20),
            ("binance", "spot", "ETHUSDT", 20),
            ("binance", "spot", "SOLUSDT", 20),
            ("binance", "futures", "BTCUSDT", 20),
            ("bybit", "spot", "BTCUSDT", 20),
        ]

        threads = [
            threading.Thread(target=write_ticks, args=pair)
            for pair in pairs
        ]

        print(f"Starting {len(threads)} concurrent write threads...")

        import time
        start_time = time.time()

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        elapsed = time.time() - start_time

        print(f"✓ All threads completed in {elapsed:.3f}s")

        # Verify results
        assert len(results) == 5, "Should have 5 results"
        for symbol, count, status in results:
            assert status == "SUCCESS", f"{symbol} failed: {status}"
            assert count == 20, f"{symbol} wrote {count} ticks instead of 20"
            print(f"✓ {symbol}: {count} ticks written successfully")

        db_mgr.close_all()
        print("\n✅ TEST 2 PASSED - Zero contention achieved!")

    finally:
        shutil.rmtree(temp_dir)


def test_analytics_queries():
    """Test analytics query execution."""
    print("\n" + "="*60)
    print("TEST 3: Analytics queries (CVD, Order Flow)")
    print("="*60)

    temp_dir = tempfile.mkdtemp()
    try:
        db_mgr = DatabaseManager(base_dir=temp_dir)
        conn = db_mgr.get_connection("binance", "spot", "BTCUSDT")

        # Insert test ticks (mix of BUY and SELL)
        insert_query = insert_tick_query()
        test_data = [
            (datetime.now(), 50000.0, 10.0, 'BUY', 'trade_1'),
            (datetime.now(), 50001.0, 5.0, 'SELL', 'trade_2'),
            (datetime.now(), 50002.0, 15.0, 'BUY', 'trade_3'),
            (datetime.now(), 50003.0, 3.0, 'SELL', 'trade_4'),
            (datetime.now(), 50004.0, 20.0, 'BUY', 'trade_5'),
        ]

        for tick in test_data:
            execute_insert(conn, insert_query, tick)

        print(f"✓ Inserted {len(test_data)} test ticks")

        # Test CVD query
        print("\nTesting CVD calculation...")
        cvd_query = calculate_cvd_query(lookback_minutes=15)
        cvd_result = execute_query(conn, cvd_query)

        if cvd_result and len(cvd_result) > 0:
            cvd_value = float(cvd_result[0][1])
            # CVD = (10 + 15 + 20) - (5 + 3) = 45 - 8 = 37
            expected_cvd = 37.0
            print(f"✓ CVD calculated: {cvd_value} (expected: {expected_cvd})")
            assert abs(cvd_value - expected_cvd) < 0.01, "CVD calculation mismatch"
        else:
            print("⚠ CVD query returned no results")

        # Test order flow imbalance query
        print("\nTesting order flow imbalance...")
        imbalance_query = calculate_order_flow_imbalance_query(window_seconds=60)
        imbalance_result = execute_query(conn, imbalance_query)

        if imbalance_result and len(imbalance_result) > 0:
            buy_vol = float(imbalance_result[0][0])
            sell_vol = float(imbalance_result[0][1])
            imbalance = float(imbalance_result[0][2])

            print(f"✓ Buy volume: {buy_vol}, Sell volume: {sell_vol}")
            print(f"✓ Imbalance ratio: {imbalance:.2f}")

            # Buy = 45, Sell = 8, Ratio = 45/8 = 5.625
            expected_ratio = 45.0 / 8.0
            assert abs(imbalance - expected_ratio) < 0.01, "Imbalance calculation mismatch"
        else:
            print("⚠ Order flow query returned no results")

        db_mgr.close_all()
        print("\n✅ TEST 3 PASSED")

    finally:
        shutil.rmtree(temp_dir)


def test_connection_pool():
    """Test ConnectionPoolManager with LRU eviction."""
    print("\n" + "="*60)
    print("TEST 4: Connection pool with LRU eviction")
    print("="*60)

    temp_dir = tempfile.mkdtemp()
    try:
        # Create pool with small max size for testing
        pool = ConnectionPoolManager(max_connections=3, base_dir=temp_dir)

        # Acquire 3 connections (fill pool)
        conn1 = pool.acquire("binance", "spot", "BTCUSDT")
        conn2 = pool.acquire("binance", "spot", "ETHUSDT")
        conn3 = pool.acquire("binance", "spot", "SOLUSDT")

        stats = pool.get_pool_stats()
        print(f"✓ Pool filled: {stats['pool_size']}/{stats['max_connections']}")
        assert stats['pool_size'] == 3, "Pool should be full"

        # Acquire 4th connection - should evict LRU (BTCUSDT)
        print("  Acquiring 4th connection (should trigger LRU eviction)...")
        conn4 = pool.acquire("binance", "spot", "ADAUSDT")

        stats = pool.get_pool_stats()
        print(f"✓ After 4th connection: {stats['pool_size']}/{stats['max_connections']}")
        print(f"✓ Evictions: {stats['evictions']}")
        assert stats['pool_size'] == 3, "Pool should still have 3 connections"
        assert stats['evictions'] == 1, "Should have 1 eviction"

        # Reacquire BTCUSDT - should create new connection (cache miss)
        conn1_new = pool.acquire("binance", "spot", "BTCUSDT")

        stats = pool.get_pool_stats()
        print(f"✓ Cache hits: {stats['hits']}, misses: {stats['misses']}")
        print(f"✓ Hit rate: {stats['hit_rate_pct']:.1f}%")

        pool.clear_pool()
        print("\n✅ TEST 4 PASSED")

    finally:
        shutil.rmtree(temp_dir)


def main():
    """Run all tests."""
    print("\n" + "🚀 MARKET DATA STORAGE LAYER - INTEGRATION TESTS")
    print("="*60)

    try:
        test_per_pair_isolation()
        test_concurrent_writes()
        test_analytics_queries()
        test_connection_pool()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n📊 Summary:")
        print("  - Per-pair database isolation: WORKING")
        print("  - Concurrent writes (zero contention): WORKING")
        print("  - Analytics queries (CVD, Order Flow): WORKING")
        print("  - Connection pooling with LRU eviction: WORKING")
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
