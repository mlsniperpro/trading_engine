"""
Database Manager - Per-pair DuckDB database isolation.

Critical design: Separate database file per trading pair to prevent race conditions
and enable true parallel analytics across 100+ pairs.

Database path pattern: data/{exchange}/{market_type}/{symbol}/trading.duckdb
Example: data/binance/spot/BTCUSDT/trading.duckdb
"""

import duckdb
import logging
from pathlib import Path
from typing import Optional, Dict
import threading

from .schema import create_all_tables, cleanup_old_data

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages per-pair DuckDB database connections.

    Key design principles:
    1. ONE database file per trading pair (exchange/market/symbol)
    2. ZERO write contention - each pair has its own DB file
    3. NO symbol column needed - implied by database path
    4. Independent scaling - add/remove pairs dynamically

    Example:
        db_mgr = DatabaseManager(base_dir="/workspaces/trading_engine/data")
        conn = db_mgr.get_connection("binance", "spot", "BTCUSDT")
        conn.execute("INSERT INTO ticks VALUES (NOW(), 50000.0, 1.5, 'BUY', '12345')")
    """

    def __init__(self, base_dir: str = "/workspaces/trading_engine/data"):
        """
        Initialize DatabaseManager.

        Args:
            base_dir: Base directory for all database files
        """
        self.base_dir = Path(base_dir)
        self.connections: Dict[str, duckdb.DuckDBPyConnection] = {}
        self._lock = threading.Lock()
        logger.info(f"DatabaseManager initialized with base_dir: {self.base_dir}")

    def _get_db_path(self, exchange: str, market_type: str, symbol: str) -> Path:
        """
        Get database file path for a specific trading pair.

        Args:
            exchange: Exchange name (e.g., 'binance', 'bybit')
            market_type: Market type (e.g., 'spot', 'futures')
            symbol: Trading symbol (e.g., 'BTCUSDT', 'ETHUSDT')

        Returns:
            Path to the database file
        """
        # Create directory structure: data/binance/spot/BTCUSDT/
        db_dir = self.base_dir / exchange.lower() / market_type.lower() / symbol.upper()
        db_dir.mkdir(parents=True, exist_ok=True)

        # Return path to database file
        return db_dir / "trading.duckdb"

    def _get_connection_key(self, exchange: str, market_type: str, symbol: str) -> str:
        """
        Generate unique key for connection cache.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol

        Returns:
            Unique connection key
        """
        return f"{exchange.lower()}:{market_type.lower()}:{symbol.upper()}"

    def get_connection(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        read_only: bool = False
    ) -> duckdb.DuckDBPyConnection:
        """
        Get or create DuckDB connection for a specific trading pair.

        This method is thread-safe and will reuse existing connections.

        Args:
            exchange: Exchange name (e.g., 'binance', 'bybit')
            market_type: Market type (e.g., 'spot', 'futures')
            symbol: Trading symbol (e.g., 'BTCUSDT')
            read_only: Open in read-only mode (prevents write conflicts)

        Returns:
            DuckDB connection for the specific trading pair
        """
        conn_key = self._get_connection_key(exchange, market_type, symbol)

        # Check if connection already exists
        with self._lock:
            if conn_key in self.connections:
                return self.connections[conn_key]

            # Create new connection
            db_path = self._get_db_path(exchange, market_type, symbol)

            try:
                # Connect to per-pair database
                conn = duckdb.connect(
                    str(db_path),
                    read_only=read_only
                )

                # Initialize schema if not read-only
                if not read_only:
                    create_all_tables(conn)

                # Cache connection
                self.connections[conn_key] = conn

                logger.info(
                    f"Created DuckDB connection for {exchange}/{market_type}/{symbol} "
                    f"(read_only={read_only})"
                )

                return conn

            except Exception as e:
                logger.error(
                    f"Error creating connection for {exchange}/{market_type}/{symbol}: {e}"
                )
                raise

    def create_tables(self, exchange: str, market_type: str, symbol: str) -> None:
        """
        Explicitly create tables for a trading pair.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol
        """
        conn = self.get_connection(exchange, market_type, symbol, read_only=False)
        create_all_tables(conn)
        logger.info(f"Tables created for {exchange}/{market_type}/{symbol}")

    def cleanup_old_data(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        retention_minutes: int = 15
    ) -> None:
        """
        Clean up old data for a specific trading pair.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol
            retention_minutes: Data retention in minutes (default: 15)
        """
        conn = self.get_connection(exchange, market_type, symbol, read_only=False)
        cleanup_old_data(conn, retention_minutes)
        logger.debug(
            f"Cleaned up old data for {exchange}/{market_type}/{symbol} "
            f"(retention: {retention_minutes} min)"
        )

    def cleanup_all_pairs(self, retention_minutes: int = 15) -> None:
        """
        Clean up old data for all active trading pairs.

        Args:
            retention_minutes: Data retention in minutes (default: 15)
        """
        with self._lock:
            for conn_key, conn in self.connections.items():
                try:
                    cleanup_old_data(conn, retention_minutes)
                except Exception as e:
                    logger.error(f"Error cleaning up {conn_key}: {e}")

        logger.info(f"Cleaned up all pairs (retention: {retention_minutes} min)")

    def close_connection(self, exchange: str, market_type: str, symbol: str) -> None:
        """
        Close connection for a specific trading pair.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol
        """
        conn_key = self._get_connection_key(exchange, market_type, symbol)

        with self._lock:
            if conn_key in self.connections:
                try:
                    self.connections[conn_key].close()
                    del self.connections[conn_key]
                    logger.info(f"Closed connection for {conn_key}")
                except Exception as e:
                    logger.error(f"Error closing connection for {conn_key}: {e}")

    def close_all(self) -> None:
        """
        Close all database connections.

        Call this during graceful shutdown.
        """
        with self._lock:
            for conn_key, conn in list(self.connections.items()):
                try:
                    conn.close()
                    logger.debug(f"Closed connection: {conn_key}")
                except Exception as e:
                    logger.error(f"Error closing {conn_key}: {e}")

            self.connections.clear()
            logger.info("All database connections closed")

    def get_active_pairs(self) -> list:
        """
        Get list of active trading pairs with open connections.

        Returns:
            List of (exchange, market_type, symbol) tuples
        """
        with self._lock:
            pairs = []
            for conn_key in self.connections.keys():
                parts = conn_key.split(':')
                if len(parts) == 3:
                    pairs.append((parts[0], parts[1], parts[2]))
            return pairs

    def get_db_stats(self, exchange: str, market_type: str, symbol: str) -> dict:
        """
        Get statistics about database for a specific pair.

        Args:
            exchange: Exchange name
            market_type: Market type
            symbol: Trading symbol

        Returns:
            Dict with database statistics
        """
        from .schema import get_table_stats

        conn = self.get_connection(exchange, market_type, symbol, read_only=True)
        stats = get_table_stats(conn)

        # Add database file size
        db_path = self._get_db_path(exchange, market_type, symbol)
        if db_path.exists():
            stats['file_size_mb'] = db_path.stat().st_size / (1024 * 1024)

        return stats

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close all connections."""
        self.close_all()
