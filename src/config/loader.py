"""
Configuration loader with YAML + environment variable support.

Loads and validates configuration files from the config/ directory.
Supports:
- Loading from YAML files
- Environment variable overrides
- Pydantic validation
- Hot reload capability
- Caching for performance
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache
from dotenv import load_dotenv
import logging

from .settings import (
    AppConfig,
    SystemConfig,
    ExchangeConfig,
    DEXConfig,
    StrategyConfig,
    RiskConfig,
    NotificationConfig,
    DecisionConfig,
    TradingConfig,
)


# Configure logging
logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables from .env file
load_dotenv(PROJECT_ROOT / ".env")


# ============================================================================
# ConfigLoader - Main Configuration Loader
# ============================================================================

class ConfigLoader:
    """
    Configuration loader with YAML + environment variable support.

    Features:
    - Loads configuration from YAML files
    - Overrides with environment variables
    - Validates using Pydantic models
    - Supports hot reload
    - Caches loaded configurations
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_dir: Configuration directory (defaults to PROJECT_ROOT/config)
        """
        self.config_dir = config_dir or (PROJECT_ROOT / "config")
        self._cache: Dict[str, Any] = {}
        logger.info(f"ConfigLoader initialized with config_dir: {self.config_dir}")

    def load_yaml(self, config_name: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file.

        Args:
            config_name: Name of the config file (without .yaml extension)

        Returns:
            Dictionary containing configuration data

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        config_path = self.config_dir / f"{config_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        logger.debug(f"Loading YAML config from: {config_path}")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Replace environment variable placeholders
        config = self._replace_env_vars(config)

        return config

    def _replace_env_vars(self, config: Any) -> Any:
        """
        Recursively replace environment variable placeholders in config.

        Placeholders format: ${ENV_VAR_NAME} or ${ENV_VAR_NAME:default_value}

        Args:
            config: Configuration dictionary or value

        Returns:
            Configuration with environment variables replaced
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Check for ${VAR} or ${VAR:default} pattern
            if config.startswith("${") and config.endswith("}"):
                env_expr = config[2:-1]  # Remove ${ and }

                # Check for default value
                if ":" in env_expr:
                    var_name, default_value = env_expr.split(":", 1)
                    return os.getenv(var_name.strip(), default_value.strip())
                else:
                    var_name = env_expr.strip()
                    value = os.getenv(var_name)
                    if value is None:
                        logger.warning(f"Environment variable {var_name} not set, using empty string")
                        return ""
                    return value

        return config

    def load_app_config(self, use_cache: bool = True) -> AppConfig:
        """
        Load complete application configuration.

        Args:
            use_cache: Use cached config if available

        Returns:
            Validated AppConfig instance
        """
        cache_key = "app_config"

        if use_cache and cache_key in self._cache:
            logger.debug("Returning cached app config")
            return self._cache[cache_key]

        logger.info("Loading complete application configuration")

        # Load main config file
        config_data = {}

        # Try to load main config.yaml
        try:
            main_config = self.load_yaml("config")
            config_data.update(main_config)
        except FileNotFoundError:
            logger.warning("config.yaml not found, using defaults")

        # Try to load risk.yaml
        try:
            risk_config = self.load_yaml("risk")
            config_data["risk"] = risk_config
        except FileNotFoundError:
            logger.warning("risk.yaml not found, using defaults")

        # Try to load strategies.yaml
        try:
            strategy_config = self.load_yaml("strategies")
            config_data["strategy"] = strategy_config
        except FileNotFoundError:
            logger.warning("strategies.yaml not found, using defaults")

        # Try to load aggregators.yaml for DEX config
        try:
            dex_config = self.load_yaml("aggregators")
            config_data["dex"] = dex_config.get("aggregators", {})
        except FileNotFoundError:
            logger.warning("aggregators.yaml not found, using defaults")

        # Try to load notifications.yaml
        try:
            notification_config = self.load_yaml("notifications")
            config_data["notification"] = notification_config
        except FileNotFoundError:
            logger.warning("notifications.yaml not found, using defaults")

        # Override with environment variables
        config_data = self._apply_env_overrides(config_data)

        # Validate with Pydantic
        try:
            app_config = AppConfig(**config_data)
            logger.info("Application configuration loaded and validated successfully")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        # Cache the config
        if use_cache:
            self._cache[cache_key] = app_config

        return app_config

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration.

        Environment variables format: SECTION_SUBSECTION_KEY
        Example: SYSTEM_LOG_LEVEL=DEBUG

        Args:
            config: Configuration dictionary

        Returns:
            Configuration with environment overrides applied
        """
        # System overrides
        if "system" not in config:
            config["system"] = {}

        if env_val := os.getenv("ENVIRONMENT"):
            config["system"]["environment"] = env_val

        if env_val := os.getenv("LOG_LEVEL"):
            config["system"]["log_level"] = env_val

        if env_val := os.getenv("DATA_DIR"):
            config["system"]["data_dir"] = env_val

        if env_val := os.getenv("API_HOST"):
            config["system"]["api_host"] = env_val

        if env_val := os.getenv("API_PORT"):
            config["system"]["api_port"] = int(env_val)

        # Exchange overrides
        if "exchange" not in config:
            config["exchange"] = {}

        # Add more environment overrides as needed

        return config

    def reload(self) -> AppConfig:
        """
        Reload configuration from disk (hot reload).

        Returns:
            Fresh AppConfig instance
        """
        logger.info("Reloading configuration from disk")
        self._cache.clear()
        return self.load_app_config(use_cache=False)

    def clear_cache(self):
        """Clear the configuration cache."""
        logger.info("Clearing configuration cache")
        self._cache.clear()


# ============================================================================
# Legacy Functions (for backward compatibility)
# ============================================================================

@lru_cache(maxsize=32)
def load_config(config_name: str) -> Dict[str, Any]:
    """
    Load a configuration file from config/ directory.

    Args:
        config_name: Name of the config file (without .yaml extension)

    Returns:
        Dictionary containing configuration data

    Example:
        >>> dex_config = load_config('dex')
        >>> pools = dex_config['uniswap_v3']['pools']
    """
    loader = ConfigLoader()
    return loader.load_yaml(config_name)


# ============================================================================
# DEX Configuration Loaders
# ============================================================================

def get_dex_config() -> Dict[str, Any]:
    """
    Get complete DEX configuration for all supported DEXs.

    Returns:
        Dictionary with all DEX configurations (Uniswap, Curve, SushiSwap, Balancer)
    """
    return load_config('dex')


def get_uniswap_config() -> Dict[str, Any]:
    """
    Get Uniswap V3 configuration.

    Returns:
        Dictionary with pools, routers, and ABI configurations
    """
    dex_config = get_dex_config()
    return dex_config['uniswap_v3']


def get_curve_config() -> Dict[str, Any]:
    """
    Get Curve Finance configuration.

    Returns:
        Dictionary with Curve pools and router
    """
    dex_config = get_dex_config()
    return dex_config['curve']


def get_sushiswap_config() -> Dict[str, Any]:
    """
    Get SushiSwap configuration.

    Returns:
        Dictionary with SushiSwap pairs and router
    """
    dex_config = get_dex_config()
    return dex_config['sushiswap']


def get_balancer_config() -> Dict[str, Any]:
    """
    Get Balancer V2 configuration.

    Returns:
        Dictionary with Balancer pools and vault
    """
    dex_config = get_dex_config()
    return dex_config['balancer']


# ============================================================================
# Uniswap-specific Helpers (backward compatibility)
# ============================================================================

def get_pool_config(pool_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific Uniswap pool.

    Args:
        pool_name: Pool identifier (e.g., 'ETH-USDC-0.3%')

    Returns:
        Pool configuration dictionary

    Raises:
        KeyError: If pool not found in configuration
    """
    config = get_uniswap_config()
    return config['pools'][pool_name]


def get_all_pool_addresses() -> Dict[str, str]:
    """
    Get all Uniswap pool addresses from configuration.

    Returns:
        Dictionary mapping pool names to addresses
    """
    config = get_uniswap_config()
    return {
        name: pool['address']
        for name, pool in config['pools'].items()
    }


def get_pool_abi() -> list:
    """
    Get Uniswap V3 pool ABI from configuration.

    Returns:
        List of ABI definitions for pool contract
    """
    config = get_uniswap_config()
    return config['pool_abi']


# ============================================================================
# Token Configuration
# ============================================================================

def get_token_addresses() -> Dict[str, str]:
    """
    Get all token addresses from DEX configuration.

    Returns:
        Dictionary mapping token symbols to addresses
    """
    dex_config = get_dex_config()
    return dex_config.get('tokens', {})


def get_token_address(symbol: str) -> str:
    """
    Get address for a specific token.

    Args:
        symbol: Token symbol (e.g., 'WETH', 'USDC')

    Returns:
        Token contract address

    Raises:
        KeyError: If token not found
    """
    tokens = get_token_addresses()
    return tokens[symbol]


# ============================================================================
# Arbitrage Configuration
# ============================================================================

def get_arbitrage_config() -> Dict[str, Any]:
    """
    Get arbitrage monitoring configuration.

    Returns:
        Dictionary with arbitrage settings (threshold, gas limits, etc.)
    """
    dex_config = get_dex_config()
    return dex_config.get('arbitrage', {})


# ============================================================================
# Global ConfigLoader Instance
# ============================================================================

# Global instance for convenience
_global_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """
    Get or create global ConfigLoader instance.

    Returns:
        Global ConfigLoader instance
    """
    global _global_loader
    if _global_loader is None:
        _global_loader = ConfigLoader()
    return _global_loader


def get_app_config(use_cache: bool = True) -> AppConfig:
    """
    Get complete application configuration.

    Args:
        use_cache: Use cached config if available

    Returns:
        Validated AppConfig instance
    """
    loader = get_config_loader()
    return loader.load_app_config(use_cache=use_cache)


def reload_config() -> AppConfig:
    """
    Reload configuration from disk (hot reload).

    Returns:
        Fresh AppConfig instance
    """
    loader = get_config_loader()
    return loader.reload()
