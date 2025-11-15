"""
Configuration dataclasses using Pydantic for type-safe validation.

This module defines all configuration models for the trading engine:
- ExchangeConfig: Exchange API keys, rate limits
- StrategyConfig: Strategy parameters
- RiskConfig: Position sizing, max drawdown
- NotificationConfig: SendGrid settings
- SystemConfig: Log level, data directory
- DEXConfig: DEX aggregator settings
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator, SecretStr
from enum import Enum
from pathlib import Path


# ============================================================================
# Enums for Configuration
# ============================================================================

class Environment(str, Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging level."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MarketType(str, Enum):
    """Market type."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"


class OrderType(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class TimeInForce(str, Enum):
    """Time in force."""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


# ============================================================================
# System Configuration
# ============================================================================

class SystemConfig(BaseModel):
    """System-wide settings."""

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment"
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )

    data_dir: Path = Field(
        default=Path("/data"),
        description="Data storage directory"
    )

    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )

    api_port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="API server port"
    )

    class Config:
        use_enum_values = True


# ============================================================================
# Exchange Configuration
# ============================================================================

class ExchangeSpotConfig(BaseModel):
    """Spot market configuration for an exchange."""

    api_key_env: str = Field(
        description="Environment variable name for API key"
    )

    api_secret_env: str = Field(
        description="Environment variable name for API secret"
    )

    rate_limit_per_minute: int = Field(
        default=1200,
        gt=0,
        description="Rate limit per minute"
    )

    order_type: OrderType = Field(
        default=OrderType.LIMIT,
        description="Default order type"
    )

    time_in_force: TimeInForce = Field(
        default=TimeInForce.IOC,
        description="Default time in force"
    )

    class Config:
        use_enum_values = True


class ExchangeFuturesConfig(BaseModel):
    """Futures market configuration for an exchange."""

    api_key_env: str = Field(
        description="Environment variable name for API key"
    )

    api_secret_env: str = Field(
        description="Environment variable name for API secret"
    )

    rate_limit_per_minute: int = Field(
        default=2400,
        gt=0,
        description="Rate limit per minute"
    )

    leverage: int = Field(
        default=1,
        ge=1,
        le=125,
        description="Default leverage"
    )

    order_type: OrderType = Field(
        default=OrderType.LIMIT,
        description="Default order type"
    )

    time_in_force: TimeInForce = Field(
        default=TimeInForce.IOC,
        description="Default time in force"
    )

    class Config:
        use_enum_values = True


class ExchangeConfig(BaseModel):
    """Exchange configuration."""

    default_exchange: str = Field(
        default="binance",
        description="Default exchange to use"
    )

    default_market: MarketType = Field(
        default=MarketType.SPOT,
        description="Default market type"
    )

    binance_spot: Optional[ExchangeSpotConfig] = None
    binance_futures: Optional[ExchangeFuturesConfig] = None
    bybit_spot: Optional[ExchangeSpotConfig] = None
    bybit_futures: Optional[ExchangeFuturesConfig] = None

    class Config:
        use_enum_values = True


# ============================================================================
# DEX Aggregator Configuration
# ============================================================================

class AggregatorConfig(BaseModel):
    """DEX aggregator configuration."""

    api_url: str = Field(
        description="API endpoint URL"
    )

    api_key: Optional[str] = Field(
        default=None,
        description="API key (if required)"
    )

    slippage_bps: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Default slippage in basis points (0.5% = 50 bps)"
    )

    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Request timeout in seconds"
    )


class ChainAggregatorConfig(BaseModel):
    """Chain-specific aggregator configuration."""

    primary: str = Field(
        description="Primary aggregator name"
    )

    backup: Optional[str] = Field(
        default=None,
        description="Backup aggregator name"
    )

    aggregators: Dict[str, AggregatorConfig] = Field(
        default_factory=dict,
        description="Aggregator configurations by name"
    )


class DEXConfig(BaseModel):
    """DEX aggregator configurations for all chains."""

    solana: Optional[ChainAggregatorConfig] = None
    ethereum: Optional[ChainAggregatorConfig] = None
    base: Optional[ChainAggregatorConfig] = None
    arbitrum: Optional[ChainAggregatorConfig] = None
    polygon: Optional[ChainAggregatorConfig] = None


# ============================================================================
# Strategy Configuration
# ============================================================================

class OrderFlowScalpingConfig(BaseModel):
    """Order flow scalping strategy configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable this strategy"
    )

    imbalance_threshold: float = Field(
        default=2.5,
        gt=1.0,
        le=10.0,
        description="Buy/sell imbalance threshold ratio"
    )

    lookback_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Lookback window in seconds"
    )

    min_trades_in_window: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Minimum trades required in window"
    )


class SupplyDemandBounceConfig(BaseModel):
    """Supply/demand bounce strategy configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable this strategy"
    )

    zone_strength_min: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Minimum zone strength (0-100)"
    )

    use_fresh_zones_only: bool = Field(
        default=True,
        description="Only trade fresh (untested) zones"
    )


class StrategyConfig(BaseModel):
    """Trading strategy parameters."""

    enabled_strategies: List[str] = Field(
        default=["order_flow_scalping", "supply_demand_bounce"],
        description="List of enabled strategy names"
    )

    order_flow_scalping: Optional[OrderFlowScalpingConfig] = None
    supply_demand_bounce: Optional[SupplyDemandBounceConfig] = None


# ============================================================================
# Risk Management Configuration
# ============================================================================

class PositionSizingConfig(BaseModel):
    """Position sizing configuration."""

    default_pct: float = Field(
        default=2.0,
        gt=0.0,
        le=100.0,
        description="Default position size as % of portfolio"
    )

    max_pct: float = Field(
        default=5.0,
        gt=0.0,
        le=100.0,
        description="Maximum position size as % of portfolio"
    )

    @validator('max_pct')
    def max_pct_greater_than_default(cls, v, values):
        """Validate that max_pct >= default_pct."""
        if 'default_pct' in values and v < values['default_pct']:
            raise ValueError('max_pct must be >= default_pct')
        return v


class LimitsConfig(BaseModel):
    """Trading limits configuration."""

    max_concurrent_positions: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Maximum concurrent positions"
    )

    max_daily_trades: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum trades per day"
    )

    max_daily_loss_pct: float = Field(
        default=5.0,
        gt=0.0,
        le=50.0,
        description="Maximum daily loss as % of portfolio"
    )

    max_position_hold_time_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,  # 24 hours
        description="Maximum position hold time in minutes"
    )


class TrailingStopConfig(BaseModel):
    """Trailing stop-loss configuration."""

    regular_distance_pct: float = Field(
        default=0.5,
        gt=0.0,
        le=10.0,
        description="Trailing stop distance for regular assets (%)"
    )

    meme_distance_pct: float = Field(
        default=17.5,
        gt=0.0,
        le=50.0,
        description="Trailing stop distance for meme coins (%)"
    )

    activate_immediately: bool = Field(
        default=True,
        description="Activate trailing stop immediately on entry"
    )


class StopLossConfig(BaseModel):
    """Stop-loss configuration."""

    initial_distance_pct: float = Field(
        default=0.5,
        gt=0.0,
        le=10.0,
        description="Initial stop-loss distance (%)"
    )

    max_distance_pct: float = Field(
        default=2.0,
        gt=0.0,
        le=20.0,
        description="Maximum stop-loss distance (%)"
    )

    @validator('max_distance_pct')
    def max_distance_greater_than_initial(cls, v, values):
        """Validate that max_distance_pct >= initial_distance_pct."""
        if 'initial_distance_pct' in values and v < values['initial_distance_pct']:
            raise ValueError('max_distance_pct must be >= initial_distance_pct')
        return v


class RiskConfig(BaseModel):
    """Risk management rules."""

    position_sizing: PositionSizingConfig = Field(
        default_factory=PositionSizingConfig,
        description="Position sizing rules"
    )

    limits: LimitsConfig = Field(
        default_factory=LimitsConfig,
        description="Trading limits"
    )

    trailing_stop: TrailingStopConfig = Field(
        default_factory=TrailingStopConfig,
        description="Trailing stop configuration"
    )

    stop_loss: StopLossConfig = Field(
        default_factory=StopLossConfig,
        description="Stop-loss configuration"
    )


# ============================================================================
# Notification Configuration
# ============================================================================

class SendGridConfig(BaseModel):
    """SendGrid email configuration."""

    api_key_env: str = Field(
        default="SENDGRID_API_KEY",
        description="Environment variable for SendGrid API key"
    )

    from_email: str = Field(
        description="From email address"
    )

    to_emails: List[str] = Field(
        default_factory=list,
        description="List of recipient email addresses"
    )


class PriorityRuleConfig(BaseModel):
    """Notification priority rule configuration."""

    send_immediately: bool = Field(
        default=True,
        description="Send notification immediately"
    )

    batch_interval_seconds: Optional[int] = Field(
        default=None,
        ge=1,
        le=3600,
        description="Batch interval in seconds (if not immediate)"
    )

    retry_on_failure: bool = Field(
        default=False,
        description="Retry on failure"
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts"
    )

    events: List[str] = Field(
        default_factory=list,
        description="Event names for this priority"
    )


class PriorityRulesConfig(BaseModel):
    """Notification priority rules."""

    critical: PriorityRuleConfig = Field(
        default_factory=lambda: PriorityRuleConfig(
            send_immediately=True,
            retry_on_failure=True,
            max_retries=3,
            events=["OrderFailed", "MarketDataConnectionLost", "SystemError"]
        ),
        description="Critical priority rules"
    )

    warning: PriorityRuleConfig = Field(
        default_factory=lambda: PriorityRuleConfig(
            send_immediately=False,
            batch_interval_seconds=300,
            events=[]
        ),
        description="Warning priority rules"
    )

    info: PriorityRuleConfig = Field(
        default_factory=lambda: PriorityRuleConfig(
            send_immediately=False,
            batch_interval_seconds=600,
            events=[]
        ),
        description="Info priority rules"
    )


class NotificationConfig(BaseModel):
    """Notification system configuration."""

    sendgrid: SendGridConfig
    priority_rules: PriorityRulesConfig = Field(
        default_factory=PriorityRulesConfig,
        description="Priority-based notification rules"
    )


# ============================================================================
# Decision Engine Configuration
# ============================================================================

class DecisionConfig(BaseModel):
    """Decision engine configuration."""

    min_confluence_score: float = Field(
        default=3.0,
        ge=0.0,
        le=10.0,
        description="Minimum confluence score to generate signal"
    )

    enabled_strategies: List[str] = Field(
        default=["order_flow_scalping", "supply_demand_bounce"],
        description="List of enabled strategy names"
    )


# ============================================================================
# Trading Configuration
# ============================================================================

class TradingConfig(BaseModel):
    """Trading configuration."""

    symbols: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        description="Trading symbols/pairs"
    )

    timeframes: Dict[str, Any] = Field(
        default={
            "primary": "1m",
            "confirmation": ["5m", "15m"]
        },
        description="Trading timeframes"
    )


# ============================================================================
# Complete Application Configuration
# ============================================================================

class AppConfig(BaseModel):
    """Complete application configuration."""

    system: SystemConfig = Field(
        default_factory=SystemConfig,
        description="System configuration"
    )

    exchange: ExchangeConfig = Field(
        default_factory=ExchangeConfig,
        description="Exchange configuration"
    )

    dex: Optional[DEXConfig] = Field(
        default=None,
        description="DEX aggregator configuration"
    )

    strategy: StrategyConfig = Field(
        default_factory=StrategyConfig,
        description="Strategy configuration"
    )

    risk: RiskConfig = Field(
        default_factory=RiskConfig,
        description="Risk management configuration"
    )

    notification: Optional[NotificationConfig] = Field(
        default=None,
        description="Notification configuration"
    )

    decision: DecisionConfig = Field(
        default_factory=DecisionConfig,
        description="Decision engine configuration"
    )

    trading: TradingConfig = Field(
        default_factory=TradingConfig,
        description="Trading configuration"
    )

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True
