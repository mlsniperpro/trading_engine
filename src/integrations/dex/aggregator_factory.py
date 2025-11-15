"""
DEX Aggregator Factory.

Factory for creating and managing aggregator instances based on chain.
Supports:
- Chain-based aggregator selection
- Fallback aggregator support
- Instance caching
- Configuration-driven setup
"""

from typing import Dict, Optional
from .aggregator_adapter import DEXAggregator, Chain, UnsupportedChainError
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Aggregator Factory
# ============================================================================

class AggregatorFactory:
    """
    Factory for creating DEX aggregator instances.

    Features:
    - Automatic aggregator selection based on chain
    - Fallback aggregator support
    - Instance caching for performance
    - Configuration-driven setup
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize aggregator factory.

        Args:
            config: DEX configuration dictionary (from config.dex)
        """
        self.config = config or {}
        self._aggregator_cache: Dict[str, DEXAggregator] = {}
        logger.info("AggregatorFactory initialized")

    def get_aggregator(
        self,
        chain: Chain,
        use_cache: bool = True
    ) -> DEXAggregator:
        """
        Get aggregator instance for a specific chain.

        Args:
            chain: Blockchain network
            use_cache: Use cached instance if available

        Returns:
            DEXAggregator instance

        Raises:
            UnsupportedChainError: If chain is not supported
        """
        cache_key = f"{chain.value}"

        # Check cache
        if use_cache and cache_key in self._aggregator_cache:
            logger.debug(f"Returning cached aggregator for {chain}")
            return self._aggregator_cache[cache_key]

        # Get chain config
        chain_config = self.config.get(chain.value)
        if not chain_config:
            raise UnsupportedChainError(f"Chain {chain} not configured")

        # Get primary aggregator name
        primary_aggregator_name = chain_config.get("primary")
        if not primary_aggregator_name:
            raise UnsupportedChainError(f"No primary aggregator configured for {chain}")

        # Create aggregator instance
        aggregator = self._create_aggregator(
            chain=chain,
            aggregator_name=primary_aggregator_name,
            chain_config=chain_config
        )

        # Cache the instance
        if use_cache:
            self._aggregator_cache[cache_key] = aggregator

        logger.info(f"Created {primary_aggregator_name} aggregator for {chain}")
        return aggregator

    def get_fallback_aggregator(
        self,
        chain: Chain,
        use_cache: bool = True
    ) -> Optional[DEXAggregator]:
        """
        Get fallback aggregator for a chain.

        Args:
            chain: Blockchain network
            use_cache: Use cached instance if available

        Returns:
            DEXAggregator instance or None if no fallback configured
        """
        cache_key = f"{chain.value}_fallback"

        # Check cache
        if use_cache and cache_key in self._aggregator_cache:
            logger.debug(f"Returning cached fallback aggregator for {chain}")
            return self._aggregator_cache[cache_key]

        # Get chain config
        chain_config = self.config.get(chain.value)
        if not chain_config:
            return None

        # Get backup aggregator name
        backup_aggregator_name = chain_config.get("backup")
        if not backup_aggregator_name:
            logger.debug(f"No fallback aggregator configured for {chain}")
            return None

        # Create aggregator instance
        aggregator = self._create_aggregator(
            chain=chain,
            aggregator_name=backup_aggregator_name,
            chain_config=chain_config
        )

        # Cache the instance
        if use_cache:
            self._aggregator_cache[cache_key] = aggregator

        logger.info(f"Created {backup_aggregator_name} fallback aggregator for {chain}")
        return aggregator

    def _create_aggregator(
        self,
        chain: Chain,
        aggregator_name: str,
        chain_config: Dict
    ) -> DEXAggregator:
        """
        Create aggregator instance.

        Args:
            chain: Blockchain network
            aggregator_name: Name of aggregator
            chain_config: Chain configuration

        Returns:
            DEXAggregator instance

        Raises:
            ValueError: If aggregator not found or config invalid
        """
        # Get aggregator-specific config
        aggregators_config = chain_config.get("aggregators", {})
        aggregator_config = aggregators_config.get(aggregator_name)

        if not aggregator_config:
            raise ValueError(f"Aggregator {aggregator_name} not configured for {chain}")

        # Import and instantiate appropriate aggregator
        if aggregator_name == "jupiter":
            from .jupiter_adapter import JupiterAggregator
            return JupiterAggregator(
                api_url=aggregator_config.get("api_url"),
                api_key=aggregator_config.get("api_key"),
                timeout_seconds=aggregator_config.get("timeout_seconds", 10)
            )

        elif aggregator_name == "1inch":
            from .oneinch_adapter import OneInchAggregator
            return OneInchAggregator(
                api_url=aggregator_config.get("api_url"),
                api_key=aggregator_config.get("api_key"),
                timeout_seconds=aggregator_config.get("timeout_seconds", 10),
                chain=chain
            )

        elif aggregator_name == "matcha":
            from .matcha_adapter import MatchaAggregator
            return MatchaAggregator(
                api_url=aggregator_config.get("api_url"),
                api_key=aggregator_config.get("api_key"),
                timeout_seconds=aggregator_config.get("timeout_seconds", 10),
                chain=chain
            )

        elif aggregator_name == "paraswap":
            from .paraswap_adapter import ParaSwapAggregator
            return ParaSwapAggregator(
                api_url=aggregator_config.get("api_url"),
                api_key=aggregator_config.get("api_key"),
                timeout_seconds=aggregator_config.get("timeout_seconds", 10),
                chain=chain
            )

        else:
            raise ValueError(f"Unknown aggregator: {aggregator_name}")

    def clear_cache(self):
        """Clear aggregator instance cache."""
        logger.info("Clearing aggregator cache")
        self._aggregator_cache.clear()

    def get_all_aggregators_for_chain(self, chain: Chain) -> Dict[str, DEXAggregator]:
        """
        Get all configured aggregators for a chain.

        Args:
            chain: Blockchain network

        Returns:
            Dictionary mapping aggregator names to instances
        """
        result = {}

        # Get primary
        try:
            primary = self.get_aggregator(chain)
            result["primary"] = primary
        except Exception as e:
            logger.warning(f"Failed to get primary aggregator for {chain}: {e}")

        # Get fallback
        try:
            fallback = self.get_fallback_aggregator(chain)
            if fallback:
                result["fallback"] = fallback
        except Exception as e:
            logger.warning(f"Failed to get fallback aggregator for {chain}: {e}")

        return result

    def __repr__(self) -> str:
        """String representation of factory."""
        chains = list(self.config.keys())
        return f"AggregatorFactory(chains={chains})"


# ============================================================================
# Global Factory Instance
# ============================================================================

_global_factory: Optional[AggregatorFactory] = None


def get_aggregator_factory(config: Optional[Dict] = None) -> AggregatorFactory:
    """
    Get or create global AggregatorFactory instance.

    Args:
        config: DEX configuration (if creating new instance)

    Returns:
        AggregatorFactory instance
    """
    global _global_factory

    if _global_factory is None:
        if config is None:
            # Try to load from config
            try:
                from src.config.loader import get_app_config
                app_config = get_app_config()
                config = app_config.dex.dict() if app_config.dex else {}
            except Exception as e:
                logger.warning(f"Failed to load DEX config: {e}, using empty config")
                config = {}

        _global_factory = AggregatorFactory(config)

    return _global_factory


def get_aggregator_for_chain(chain: Chain) -> DEXAggregator:
    """
    Convenience function to get aggregator for a chain.

    Args:
        chain: Blockchain network

    Returns:
        DEXAggregator instance
    """
    factory = get_aggregator_factory()
    return factory.get_aggregator(chain)
