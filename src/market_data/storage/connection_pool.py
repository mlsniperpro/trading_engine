"""
Connection Pool Manager - LRU-based connection pooling for DuckDB.

Manages a shared pool of 200 connections across ALL trading pairs with
LRU (Least Recently Used) eviction for inactive pairs.

Design:
- Max 200 connections globally (not per-pair)
- LRU eviction when pool is full
- Active pairs stay cached, inactive pairs get evicted
- Thread-safe operations
"""

import duckdb
import logging
import threading
from collections import OrderedDict
from typing import Optional, Tuple
from datetime import datetime

from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """
    Manages a shared LRU connection pool across all trading pairs.

    Key features:
    1. Max 200 connections globally
    2. LRU eviction for inactive pairs
    3. Thread-safe acquire/release
    4. Automatic connection reuse

    Example:
        pool = ConnectionPoolManager(max_connections=200)
        conn = pool.acquire("binance", "spot", "BTCUSDT")
        # Use connection
        pool.release(conn)
    """

    def __init__(
        self,
        max_connections: int = 200,
        base_dir: str = "/workspaces/trading_engine/data"
    ):
        """
        Initialize ConnectionPoolManager.

        Args:
            max_connections: Maximum number of connections in pool
            base_dir: Base directory for database files
        """
        self.max_connections = max_connections
        self.db_manager = DatabaseManager(base_dir=base_dir)

        # LRU cache: key -> (connection, last_used_timestamp)
        self._pool: OrderedDict[str, Tuple[duckdb.DuckDBPyConnection, datetime]] = OrderedDict()

        # Lock for thread-safe operations
        self._lock = threading.Lock()

        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'acquisitions': 0,
            'releases': 0
        }

        logger.info(
            f"ConnectionPoolManager initialized (max_connections={max_connections})"
        )

    def _get_connection_key(self, exchange: str, market_type: str, symbol: str) -> str:
        """Generate unique key for connection."""
        return f"{exchange.lower()}:{market_type.lower()}:{symbol.upper()}"

    def _evict_lru(self) -> None:
        """
        Evict least recently used connection.

        This is called when pool is full and we need to add a new connection.
        """
        if not self._pool:
            return

        # Get LRU connection (first item in OrderedDict)
        lru_key, (conn, last_used) = self._pool.popitem(last=False)

        try:
            conn.close()
            self._stats['evictions'] += 1
            logger.debug(
                f"Evicted LRU connection: {lru_key} "
                f"(last used: {last_used.strftime('%H:%M:%S')})"
            )
        except Exception as e:
            logger.error(f"Error evicting connection {lru_key}: {e}")

    def acquire(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        read_only: bool = False
    ) -> duckdb.DuckDBPyConnection:
        """
        Acquire connection from pool (or create new one).

        Thread-safe. If connection exists in pool, reuse it.
        If pool is full, evict LRU connection.

        Args:
            exchange: Exchange name (e.g., 'binance')
            market_type: Market type (e.g., 'spot', 'futures')
            symbol: Trading symbol (e.g., 'BTCUSDT')
            read_only: Open in read-only mode

        Returns:
            DuckDB connection for the trading pair
        """
        conn_key = self._get_connection_key(exchange, market_type, symbol)

        with self._lock:
            self._stats['acquisitions'] += 1

            # Check if connection exists in pool
            if conn_key in self._pool:
                # Move to end (mark as recently used)
                conn, _ = self._pool.pop(conn_key)
                self._pool[conn_key] = (conn, datetime.now())
                self._stats['hits'] += 1

                logger.debug(f"Cache HIT: {conn_key}")
                return conn

            # Cache miss - need to create new connection
            self._stats['misses'] += 1
            logger.debug(f"Cache MISS: {conn_key}")

            # Check if pool is full
            if len(self._pool) >= self.max_connections:
                self._evict_lru()

            # Create new connection via DatabaseManager
            conn = self.db_manager.get_connection(
                exchange, market_type, symbol, read_only=read_only
            )

            # Add to pool
            self._pool[conn_key] = (conn, datetime.now())

            logger.info(
                f"Acquired new connection: {conn_key} "
                f"(pool size: {len(self._pool)}/{self.max_connections})"
            )

            return conn

    def release(self, conn: duckdb.DuckDBPyConnection) -> None:
        """
        Release connection back to pool.

        Note: Connection is NOT closed, just marked as available for reuse.

        Args:
            conn: DuckDB connection to release
        """
        with self._lock:
            self._stats['releases'] += 1

            # Find connection in pool and update last_used timestamp
            for key, (cached_conn, _) in self._pool.items():
                if cached_conn is conn:
                    # Move to end (mark as recently used)
                    self._pool.pop(key)
                    self._pool[key] = (conn, datetime.now())
                    logger.debug(f"Released connection: {key}")
                    return

            # Connection not in pool - this is unexpected
            logger.warning("Released connection not found in pool")

    def get_connection_for_pair(
        self,
        exchange: str,
        market_type: str,
        symbol: str
    ) -> Optional[duckdb.DuckDBPyConnection]:
        """
        Get connection if it exists in pool (without acquiring).

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol

        Returns:
            Connection if exists in pool, None otherwise
        """
        conn_key = self._get_connection_key(exchange, market_type, symbol)

        with self._lock:
            if conn_key in self._pool:
                conn, _ = self._pool[conn_key]
                return conn
            return None

    def evict(self, exchange: str, market_type: str, symbol: str) -> None:
        """
        Manually evict a specific connection from pool.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol
        """
        conn_key = self._get_connection_key(exchange, market_type, symbol)

        with self._lock:
            if conn_key in self._pool:
                conn, _ = self._pool.pop(conn_key)
                try:
                    conn.close()
                    self._stats['evictions'] += 1
                    logger.info(f"Manually evicted connection: {conn_key}")
                except Exception as e:
                    logger.error(f"Error evicting {conn_key}: {e}")

    def clear_pool(self) -> None:
        """
        Clear entire pool (close all connections).

        Call this during graceful shutdown.
        """
        with self._lock:
            for key, (conn, _) in list(self._pool.items()):
                try:
                    conn.close()
                    logger.debug(f"Closed connection: {key}")
                except Exception as e:
                    logger.error(f"Error closing {key}: {e}")

            self._pool.clear()
            logger.info("Connection pool cleared")

    def get_pool_stats(self) -> dict:
        """
        Get connection pool statistics.

        Returns:
            Dict with pool stats (size, hits, misses, etc.)
        """
        with self._lock:
            hit_rate = (
                self._stats['hits'] / max(1, self._stats['acquisitions'])
            ) * 100

            return {
                'pool_size': len(self._pool),
                'max_connections': self.max_connections,
                'utilization_pct': (len(self._pool) / self.max_connections) * 100,
                'acquisitions': self._stats['acquisitions'],
                'releases': self._stats['releases'],
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'hit_rate_pct': hit_rate,
                'active_pairs': list(self._pool.keys())
            }

    def get_active_pairs(self) -> list:
        """
        Get list of active pairs in pool.

        Returns:
            List of (exchange, market_type, symbol) tuples
        """
        with self._lock:
            pairs = []
            for key in self._pool.keys():
                parts = key.split(':')
                if len(parts) == 3:
                    pairs.append((parts[0], parts[1], parts[2]))
            return pairs

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clear pool."""
        self.clear_pool()


# Singleton instance
_pool_instance: Optional[ConnectionPoolManager] = None
_pool_lock = threading.Lock()


def get_pool(
    max_connections: int = 200,
    base_dir: str = "/workspaces/trading_engine/data"
) -> ConnectionPoolManager:
    """
    Get singleton ConnectionPoolManager instance.

    Args:
        max_connections: Maximum connections in pool
        base_dir: Base directory for database files

    Returns:
        Singleton ConnectionPoolManager instance
    """
    global _pool_instance

    if _pool_instance is None:
        with _pool_lock:
            if _pool_instance is None:
                _pool_instance = ConnectionPoolManager(
                    max_connections=max_connections,
                    base_dir=base_dir
                )
                logger.info("Created singleton ConnectionPoolManager")

    return _pool_instance
