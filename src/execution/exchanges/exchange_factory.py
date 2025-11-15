"""
Exchange factory for creating exchange adapter instances.

Implements the factory pattern for exchange creation with
configuration management and caching.
"""

import logging
from typing import Optional, Dict, Any

from src.execution.exchanges.base import ExchangeAdapter, ExchangeError
from src.execution.exchanges.binance_ccxt import BinanceCCXTAdapter

logger = logging.getLogger(__name__)


class ExchangeFactory:
    """
    Factory for creating exchange adapter instances.

    Features:
    - Supports multiple exchanges (Binance, Bybit, etc.)
    - Configuration-driven creation
    - Instance caching to reuse connections
    - Automatic cleanup on shutdown
    """

    # Registry of supported exchanges
    _EXCHANGE_REGISTRY = {
        'binance': BinanceCCXTAdapter,
        # Add more exchanges here:
        # 'bybit': BybitCCXTAdapter,
        # 'okx': OKXCCXTAdapter,
    }

    def __init__(self):
        """Initialize exchange factory."""
        self._instances: Dict[str, ExchangeAdapter] = {}
        self._configs: Dict[str, Dict[str, Any]] = {}

    def register_exchange(self, name: str, adapter_class: type):
        """
        Register a new exchange adapter.

        Args:
            name: Exchange name (lowercase)
            adapter_class: Adapter class
        """
        self._EXCHANGE_REGISTRY[name] = adapter_class
        logger.info(f"Registered exchange adapter: {name}")

    def configure_exchange(self, name: str, config: Dict[str, Any]):
        """
        Configure an exchange.

        Args:
            name: Exchange name
            config: Exchange configuration
        """
        self._configs[name] = config
        logger.info(f"Configured exchange: {name}")

    async def create_exchange(
        self,
        exchange_name: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
        market_type: str = "spot",
        **kwargs
    ) -> ExchangeAdapter:
        """
        Create or retrieve an exchange adapter instance.

        Args:
            exchange_name: Exchange name (e.g., 'binance')
            api_key: API key (overrides config)
            api_secret: API secret (overrides config)
            testnet: Use testnet
            market_type: Market type ('spot' or 'futures')
            **kwargs: Additional parameters

        Returns:
            Exchange adapter instance

        Raises:
            ExchangeError: If exchange not supported or creation fails
        """
        exchange_name = exchange_name.lower()

        # Check if exchange is supported
        if exchange_name not in self._EXCHANGE_REGISTRY:
            raise ExchangeError(
                f"Unsupported exchange: {exchange_name}. "
                f"Supported: {list(self._EXCHANGE_REGISTRY.keys())}"
            )

        # Create cache key
        cache_key = f"{exchange_name}_{market_type}_{'testnet' if testnet else 'mainnet'}"

        # Return cached instance if exists
        if cache_key in self._instances:
            logger.debug(f"Returning cached exchange instance: {cache_key}")
            return self._instances[cache_key]

        # Get configuration
        config = self._configs.get(exchange_name, {})

        # Override with provided credentials
        if api_key:
            config['api_key'] = api_key
        if api_secret:
            config['api_secret'] = api_secret

        # Merge kwargs
        config.update(kwargs)
        config['testnet'] = testnet
        config['market_type'] = market_type

        # Create adapter instance
        try:
            adapter_class = self._EXCHANGE_REGISTRY[exchange_name]
            adapter = adapter_class(**config)

            # Connect to exchange
            await adapter.connect()

            # Cache instance
            self._instances[cache_key] = adapter

            logger.info(
                f"Created exchange adapter: {cache_key} "
                f"(class={adapter_class.__name__})"
            )

            return adapter

        except Exception as e:
            logger.error(f"Failed to create exchange adapter {exchange_name}: {e}")
            raise ExchangeError(f"Exchange creation failed: {str(e)}")

    async def get_exchange(
        self,
        exchange_name: str,
        market_type: str = "spot",
        testnet: bool = False
    ) -> Optional[ExchangeAdapter]:
        """
        Get existing exchange instance without creating.

        Args:
            exchange_name: Exchange name
            market_type: Market type
            testnet: Testnet flag

        Returns:
            Exchange adapter or None if not exists
        """
        cache_key = f"{exchange_name}_{market_type}_{'testnet' if testnet else 'mainnet'}"
        return self._instances.get(cache_key)

    async def close_all(self):
        """Close all exchange connections."""
        for name, instance in self._instances.items():
            try:
                await instance.disconnect()
                logger.info(f"Closed exchange: {name}")
            except Exception as e:
                logger.error(f"Error closing exchange {name}: {e}")

        self._instances.clear()

    def get_supported_exchanges(self) -> list:
        """Get list of supported exchange names."""
        return list(self._EXCHANGE_REGISTRY.keys())


# Global factory instance (can be replaced with DI container)
_global_factory: Optional[ExchangeFactory] = None


def get_exchange_factory() -> ExchangeFactory:
    """
    Get global exchange factory instance.

    Returns:
        Exchange factory
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = ExchangeFactory()
    return _global_factory


def set_exchange_factory(factory: ExchangeFactory):
    """
    Set global exchange factory instance.

    Args:
        factory: Exchange factory
    """
    global _global_factory
    _global_factory = factory
