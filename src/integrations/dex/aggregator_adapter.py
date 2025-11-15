"""
DEX Aggregator Adapter - Abstract Base Class and Quote Model.

This module defines the standard interface for all DEX aggregators:
- AggregatorQuote: Standard quote format across all aggregators
- DEXAggregator: Abstract base class for aggregator implementations

Supported aggregators:
- Jupiter (Solana)
- 1inch (EVM chains)
- Matcha/0x (EVM chains)
- ParaSwap (EVM chains)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


# ============================================================================
# Chain Enumeration
# ============================================================================

class Chain(str, Enum):
    """Supported blockchain networks."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BASE = "base"
    ARBITRUM = "arbitrum"
    POLYGON = "polygon"
    BSC = "bsc"
    AVALANCHE = "avalanche"
    OPTIMISM = "optimism"


# ============================================================================
# Aggregator Quote Model
# ============================================================================

@dataclass
class AggregatorQuote:
    """
    Standard quote format for DEX aggregators.

    This standardized format allows the trading engine to work with
    any aggregator without changes.
    """

    # Quote identification
    quote_id: str
    aggregator: str  # Name of aggregator (jupiter, 1inch, matcha, etc.)
    chain: Chain

    # Tokens
    input_token: str  # Token address or symbol
    output_token: str  # Token address or symbol

    # Amounts
    input_amount: Decimal  # Amount of input token (in token units)
    output_amount: Decimal  # Expected output token amount (in token units)
    input_amount_usd: Optional[Decimal] = None  # USD value of input
    output_amount_usd: Optional[Decimal] = None  # USD value of output

    # Price information
    price: Decimal = None  # Price (output/input)
    price_impact_pct: Optional[Decimal] = None  # Price impact percentage

    # Slippage
    slippage_bps: int = 50  # Slippage tolerance in basis points (0.5% = 50)
    minimum_output: Optional[Decimal] = None  # Minimum output after slippage

    # Gas/fees
    estimated_gas: Optional[int] = None  # Estimated gas units
    gas_price: Optional[Decimal] = None  # Gas price (Gwei for EVM, lamports for Solana)
    network_fee_usd: Optional[Decimal] = None  # Network fee in USD

    # Route information
    route: Optional[List[str]] = None  # Token route (e.g., [USDC, WETH, SOL])
    dexes: Optional[List[str]] = None  # DEXs used in route
    num_splits: int = 1  # Number of route splits

    # Timing
    valid_until: Optional[int] = None  # Unix timestamp when quote expires

    # Raw data from aggregator (for debugging/advanced use)
    raw_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.price is None and self.input_amount and self.output_amount:
            self.price = self.output_amount / self.input_amount

        if self.minimum_output is None and self.output_amount:
            # Calculate minimum output based on slippage
            slippage_multiplier = Decimal(1) - (Decimal(self.slippage_bps) / Decimal(10000))
            self.minimum_output = self.output_amount * slippage_multiplier

    @property
    def is_valid(self) -> bool:
        """Check if quote is still valid based on expiration time."""
        if self.valid_until is None:
            return True

        import time
        return time.time() < self.valid_until

    @property
    def effective_price_with_slippage(self) -> Decimal:
        """Get the effective price accounting for slippage."""
        if self.minimum_output and self.input_amount:
            return self.minimum_output / self.input_amount
        return self.price

    def __repr__(self) -> str:
        """String representation of quote."""
        return (
            f"AggregatorQuote("
            f"{self.input_token} -> {self.output_token}, "
            f"in={self.input_amount}, out={self.output_amount}, "
            f"price={self.price:.6f}, "
            f"aggregator={self.aggregator}, "
            f"chain={self.chain}"
            f")"
        )


# ============================================================================
# DEX Aggregator Abstract Base Class
# ============================================================================

class DEXAggregator(ABC):
    """
    Abstract base class for DEX aggregators.

    All aggregator implementations must inherit from this class and
    implement the required methods.
    """

    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        timeout_seconds: int = 10
    ):
        """
        Initialize aggregator adapter.

        Args:
            api_url: API endpoint URL
            api_key: API key (if required)
            timeout_seconds: Request timeout in seconds
        """
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: Decimal,
        slippage_bps: int = 50,
        **kwargs
    ) -> AggregatorQuote:
        """
        Get a swap quote from the aggregator.

        Args:
            input_token: Input token address or symbol
            output_token: Output token address or symbol
            amount: Amount of input token (in token units)
            slippage_bps: Slippage tolerance in basis points (0.5% = 50)
            **kwargs: Additional aggregator-specific parameters

        Returns:
            AggregatorQuote with swap details

        Raises:
            Exception: If quote fails or aggregator error
        """
        pass

    @abstractmethod
    async def execute_swap(
        self,
        quote: AggregatorQuote,
        wallet_address: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a swap based on a quote.

        Args:
            quote: AggregatorQuote from get_quote()
            wallet_address: Wallet address to execute swap from
            **kwargs: Additional execution parameters (private key, etc.)

        Returns:
            Dictionary with transaction details:
            {
                'tx_hash': str,
                'status': str,  # 'pending', 'confirmed', 'failed'
                'block_number': int (optional),
                'gas_used': int (optional),
                ...
            }

        Raises:
            Exception: If swap execution fails
        """
        pass

    @abstractmethod
    def get_supported_chains(self) -> List[Chain]:
        """
        Get list of supported blockchain networks.

        Returns:
            List of Chain enum values
        """
        pass

    @abstractmethod
    def get_supported_tokens(self, chain: Chain) -> List[str]:
        """
        Get list of supported tokens for a chain.

        Args:
            chain: Blockchain network

        Returns:
            List of token addresses or symbols
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if aggregator API is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Default implementation - subclasses can override
            return True
        except Exception:
            return False

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get aggregator name.

        Returns:
            Aggregator name (e.g., 'jupiter', '1inch', 'matcha')
        """
        pass

    def __repr__(self) -> str:
        """String representation of aggregator."""
        return f"{self.__class__.__name__}(name={self.name}, api_url={self.api_url})"


# ============================================================================
# Exception Classes
# ============================================================================

class AggregatorError(Exception):
    """Base exception for aggregator errors."""
    pass


class QuoteError(AggregatorError):
    """Exception raised when getting quote fails."""
    pass


class ExecutionError(AggregatorError):
    """Exception raised when swap execution fails."""
    pass


class InsufficientLiquidityError(AggregatorError):
    """Exception raised when there's insufficient liquidity for swap."""
    pass


class UnsupportedTokenError(AggregatorError):
    """Exception raised when token is not supported."""
    pass


class UnsupportedChainError(AggregatorError):
    """Exception raised when chain is not supported."""
    pass
