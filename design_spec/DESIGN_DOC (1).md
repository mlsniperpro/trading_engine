# Algorithmic Trading Engine - Design Document

## 1. Executive Summary

### 1.1 Project Overview
The Algorithmic Trading Engine is a sophisticated, profit-oriented trading system designed to execute multiple trading strategies across crypto and forex markets. The engine supports:
- **Crypto Markets**: Centralized exchanges (Binance Global), decentralized exchanges (DEXes), meme coin trading, and flashloan arbitrage
- **Forex Markets**: MetaTrader 5 (MT5), cTrader, TradeLocker, MatchTrader for FX pairs and commodities (Gold, Silver, Oil)

### 1.2 Core Objectives
- **Profit Generation**: Primary focus on market-making through bid-ask bounce and spread capture
- **Multi-Strategy Support**: Enable diverse trading strategies including market-making, arbitrage, and meme coin trading
- **High Performance**: Ultra-fast data processing and decision-making capabilities
- **Scalability**: Support for multiple markets, exchanges, and trading pairs simultaneously
- **Risk Management**: Built-in safeguards and position management
- **Real-time Monitoring**: Comprehensive notification and alerting system

### 1.3 Technology Stack
- **Primary Language**: Python 3.12+
- **Market Data**:
  - Crypto: Cryptofeed (WebSocket connections for real-time data)
  - Forex: MT5 Python API, cTrader API, TradeLocker REST API, MatchTrader API
- **Order Execution**:
  - Crypto: CCXT (unified exchange API) + Direct Binance API
  - Forex: MT5 Python package, cTrader FIX API, TradeLocker REST API, MatchTrader API
- **Data Storage**: DuckDB (ultra-fast analytical queries), Firestore (persistent data)
- **File Storage**: Firebase Storage (logs, reports, historical data)
- **Notifications**: API-based notification system
- **Supported Platforms**:
  - **Crypto**: Binance Global, DEXes (Uniswap, PancakeSwap, Raydium)
  - **Forex**: MetaTrader 5 (Priority #1), cTrader (Priority #2), TradeLocker (Priority #3), MatchTrader (Priority #3)

### 1.4 Supported Markets & Instruments

**Crypto Markets**:
- **Spot Trading**: BTC, ETH, altcoins on Binance and other CEXes
- **Perpetual Futures**: Leverage trading on crypto derivatives
- **Meme Coins**: High-volatility emerging tokens
- **DEX Trading**: Uniswap, PancakeSwap, and other decentralized exchanges

**Forex & Commodities Markets**:
- **Major Pairs**: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, NZD/USD
- **Minor Pairs**: EUR/GBP, EUR/JPY, GBP/JPY, etc.
- **Exotic Pairs**: USD/TRY, USD/ZAR, etc. (broker-dependent)
- **Precious Metals**: Gold (XAU/USD), Silver (XAG/USD)
- **Commodities**: Oil (WTI, Brent), Natural Gas (broker-dependent)
- **Indices**: US30, US100, SPX500, GER40 (broker-dependent)

**Trading Sessions**:
- **Crypto**: 24/7 continuous trading
- **Forex**: 24/5 trading (Monday 00:00 GMT - Friday 23:59 GMT)
  - London Session: 08:00-16:00 GMT
  - New York Session: 13:00-21:00 GMT
  - Tokyo Session: 00:00-09:00 GMT

### 1.5 Primary Trading Strategy Overview

**Strategy: Ultra-Short Scalping**

The engine employs a **hierarchical multi-timeframe scalping strategy** optimized for speed and high-frequency execution:

**Timeframe Hierarchy (1M / 5M / 15M)**:
- **15M (LONGEST)**: Trend & Regime Detection + Market Profile Zones
  - Filters out ranging markets immediately (short-circuit)
  - Identifies supply/demand zones for surveillance
  - Determines overall market bias (trending vs ranging)

- **5M (MIDDLE)**: Order Flow Cascade Confirmation
  - Validates institutional buying/selling pressure
  - Confirms trend acceleration or deceleration
  - Provides confluence with longer timeframe bias

- **1M (FASTEST)**: Entry Timing & Final Trigger
  - Precise entry signals from order flow imbalance
  - Bid-ask bounce detection
  - Real-time execution decisions (updated every 2 seconds)

**Core Philosophy**:
- **Zones as Surveillance Areas**: Supply/demand zones are NOT trade signals - they're areas to WATCH for order flow confirmation
- **Order Flow Confirmation Required**: Never trade zones alone - wait for aggressive buying/selling confirmation
- **Cascade Detection**: Order flow must ACCELERATE across timeframes (e.g., 3.5 → 2.8 → 1.8 imbalance ratio = bullish cascade)
- **Quick In, Quick Out**: Target hold times of 30 seconds to 5 minutes
- **Capital Preservation**: 0.5% trailing stop maximum, exit immediately if wrong

**Trading Targets**:
- 5-20 trades per hour per pair
- 0.5-1.0% profit per trade
- 1:1.5 to 1:2 risk-reward ratio
- Best for: High volatility periods, trending markets ONLY (ranging markets filtered out at Level 1)

**Why These Timeframes?**
- **Speed Optimized**: 15M is fast enough for trend detection without lag
- **Data Efficiency**: Only 15 minutes tick retention needed (matches longest timeframe)
- **High Frequency**: Enables scanning 100+ pairs simultaneously
- **VM Friendly**: Minimal computational overhead, low memory footprint

---

## 2. System Architecture

### 2.1 Event-Driven Architecture (Core Design)

**The Heart of the System:**
At the core, this is an **event-driven system** where:
- 🔄 **Data Streaming & Analytics run 24/7** - Continuously processing market data
- ⚡ **Event Bus at the center** - All components communicate via events
- 🎯 **Everything else reacts to events** - Decision, Execution, Notifications triggered by events

```
┌──────────────────────────────────────────────────────────────────────┐
│                        EVENT BUS (THE HEART)                         │
│                     Central Message Broker (24/7)                    │
│                                                                       │
│  Events: TradeReceived, AnalyticsUpdated, SignalGenerated,          │
│          OrderFilled, PositionClosed, ConnectionLost, etc.           │
└──────────────────────────────────────────────────────────────────────┘
         ▲                    │                    │                ▲
         │ Emit               │ Subscribe          │ Subscribe     │ Emit
         │ Events             │ & React            │ & React       │ Events
         │                    │                    │               │
┌────────┴────────┐    ┌──────▼────────┐   ┌──────▼───────┐   ┌──┴──────────┐
│                 │    │               │   │              │   │             │
│ DATA STREAMING  │    │   DECISION    │   │  EXECUTION   │   │ POSITION    │
│   (ALWAYS ON)   │    │    ENGINE     │   │   ENGINE     │   │  MONITOR    │
│                 │    │  (REACTIVE)   │   │  (REACTIVE)  │   │ (ALWAYS ON) │
│ - WebSocket     │    │               │   │              │   │             │
│ - Trade Ticks   │    │ Waits for:    │   │ Waits for:   │   │ - Monitors  │
│ - Candles       │    │ • Analytics   │   │ • Signals    │   │ - Trailing  │
│                 │    │   Updates     │   │              │   │   Stops     │
│ Emits:          │    │               │   │ Emits:       │   │             │
│ • TradeReceived │    │ Emits:        │   │ • OrderFilled│   │ Emits:      │
│ • CandleComplete│    │ • SignalGen   │   │ • PosOpened  │   │ • StopHit   │
│ • ConnLost 🔴   │    │ • SignalRej   │   │ • OrderFail🔴│   │ • PosClosed │
│                 │    │               │   │              │   │             │
└────────┬────────┘    └───────────────┘   └──────────────┘   └─────────────┘
         │
         ▼
┌─────────────────┐                                         ┌─────────────────┐
│                 │                                         │                 │
│    ANALYTICS    │                                         │  NOTIFICATION   │
│     ENGINE      │                                         │     SYSTEM      │
│  (ALWAYS ON)    │                                         │   (REACTIVE)    │
│                 │                                         │                 │
│ Listens:        │                                         │ Listens:        │
│ • TradeReceived │                                         │ • SignalGen ✉️  │
│ • CandleComp    │                                         │ • OrderFilled✉️ │
│                 │                                         │ • OrderFail 🔴✉️│
│ Emits:          │                                         │ • ConnLost 🔴✉️ │
│ • AnalyticsUpd  │                                         │ • PosClosed ✉️  │
│ • ImbalanceDet  │                                         │                 │
│ • PatternDet    │                                         │ Uses:           │
│ • DataQuality⚠️ │                                         │ • SendGrid API  │
│                 │                                         │                 │
└─────────────────┘                                         └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          STORAGE LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │   DuckDB     │  │  Firestore   │  │  Firebase Storage    │     │
│  │ (Per-Symbol) │  │ (State Sync) │  │  (Logs & Reports)    │     │
│  └──────────────┘  └──────────────┘  └──────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

**What Runs 24/7 (Always-On Components):**
1. ✅ **Event Bus** - Processes events continuously
2. ✅ **Data Streaming** - Ingests market data continuously
3. ✅ **Analytics Engine** - Calculates metrics continuously
4. ✅ **Position Monitor** - Monitors open positions continuously
5. ✅ **API Server** - Listens for commands continuously

**What Reacts to Events (Triggered Components):**
1. ⚡ **Decision Engine** - Triggers on analytics events
2. ⚡ **Execution Engine** - Triggers on trading signals
3. ⚡ **Notification System** - Triggers on important events (SendGrid emails)

---

### 2.2 Component Overview

#### 2.2.0 Service Management & Dependency Injection ⭐

**Dependency Injection Container**:
The system uses a lightweight DI container to manage service lifecycle and automatically resolve dependencies. This is **critical** for testability, decoupling, and proper initialization order.

**Container Responsibilities**:
1. **Service Registration**: Register services as singletons, factories, or types
2. **Dependency Resolution**: Automatically inject dependencies based on type hints
3. **Lifecycle Management**: Initialize services in correct order (topological sort)
4. **Testing Support**: Easy dependency mocking for unit tests

**Implementation**:
```python
# src/core/di_container.py
from typing import Dict, Any, Callable, Type
import inspect

class DependencyContainer:
    """
    Dependency Injection container for managing service lifecycle
    and resolving dependencies automatically.
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}

    def register_singleton(self, name: str, instance: Any):
        """Register a singleton instance"""
        self._singletons[name] = instance

    def register_factory(self, name: str, factory: Callable):
        """Register a factory function for creating instances"""
        self._factories[name] = factory

    def register_type(self, interface: Type, implementation: Type):
        """Register a type with automatic dependency resolution"""
        self._services[interface.__name__] = implementation

    def resolve(self, service_name: str) -> Any:
        """Resolve a service by name, creating it if necessary"""
        # Check singletons first
        if service_name in self._singletons:
            return self._singletons[service_name]

        # Check factories
        if service_name in self._factories:
            factory = self._factories[service_name]
            dependencies = self._resolve_dependencies(factory)
            return factory(**dependencies)

        # Check registered types
        if service_name in self._services:
            service_type = self._services[service_name]
            dependencies = self._resolve_dependencies(service_type.__init__)
            instance = service_type(**dependencies)
            return instance

        raise ValueError(f"Service '{service_name}' not registered")

    def _resolve_dependencies(self, func: Callable) -> Dict[str, Any]:
        """Automatically resolve function/constructor dependencies"""
        sig = inspect.signature(func)
        dependencies = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # Get type hint
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                continue

            # Resolve dependency by type name
            type_name = param_type.__name__
            dependencies[param_name] = self.resolve(type_name)

        return dependencies
```

**Service Registration Example**:
```python
# main.py
from src.core.di_container import DependencyContainer

def setup_application():
    container = DependencyContainer()

    # Register storage layer
    container.register_singleton(
        "ConnectionPoolManager",
        ConnectionPoolManager(max_connections=200)
    )

    # Register data services (auto-inject connection pool)
    container.register_factory(
        "MarketDataService",
        lambda pool: MarketDataService(connection_pool=pool)
    )

    # Register analytics with auto-dependency resolution
    container.register_type(OrderFlowAnalyzer, OrderFlowAnalyzerImpl)
    container.register_type(MicrostructureAnalyzer, MicrostructureAnalyzerImpl)

    # Register decision engine (dependencies auto-injected)
    container.register_factory(
        "DecisionEngine",
        lambda order_flow, microstructure: DecisionEngine(
            primary_analyzers=[order_flow, microstructure]
        )
    )

    # Register execution layer
    container.register_type(ExecutionPipeline, ExecutionPipelineImpl)

    # Resolve main application
    app = container.resolve("TradingEngine")
    return app, container
```

**Service with Auto-Injected Dependencies**:
```python
# src/decision/engine.py
class DecisionEngine:
    def __init__(
        self,
        order_flow_analyzer: OrderFlowAnalyzer,      # Auto-resolved
        microstructure_analyzer: MicrostructureAnalyzer,  # Auto-resolved
        market_data_service: MarketDataService,      # Auto-resolved
        config: Config                               # Auto-resolved
    ):
        self.order_flow = order_flow_analyzer
        self.microstructure = microstructure_analyzer
        self.market_data = market_data_service
        self.config = config
```

**Testing with DI**:
```python
# tests/test_decision_engine.py
def test_decision_engine():
    # Create test container with mocks
    container = DependencyContainer()

    # Register mocks
    mock_order_flow = Mock(spec=OrderFlowAnalyzer)
    mock_microstructure = Mock(spec=MicrostructureAnalyzer)
    mock_market_data = Mock(spec=MarketDataService)

    container.register_singleton("OrderFlowAnalyzer", mock_order_flow)
    container.register_singleton("MicrostructureAnalyzer", mock_microstructure)
    container.register_singleton("MarketDataService", mock_market_data)

    # Resolve service with mocked dependencies
    engine = container.resolve("DecisionEngine")

    # Test with controlled mock behavior
    mock_order_flow.analyze.return_value = SignalResult(strength=0.8)
    assert engine.evaluate() == expected_result
```

**Benefits**:
- **No Global State**: All services properly initialized through container
- **Clear Dependencies**: Type hints show what each service needs
- **Easy Testing**: Mock any dependency without touching production code
- **Flexible Configuration**: Swap implementations based on environment (dev/staging/prod)
- **Initialization Order**: Container ensures services initialized in correct order
- **Decoupling**: Services don't create their own dependencies

---

#### 2.2.0.0.1 Adapter Pattern for Swappable Components ⭐⭐⭐

**Critical for Maintainability & Swappability**: Use abstract interfaces for all external integrations (aggregators, exchanges, platforms) to enable swapping implementations without code changes.

**DEX Aggregator Adapter Interface**:
```python
# src/integrations/dex/aggregator_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class AggregatorQuote:
    """Standard quote format from any aggregator"""
    input_token: str
    output_token: str
    input_amount: float
    output_amount: float
    estimated_slippage: float
    estimated_gas: float
    route_data: Dict[str, Any]  # Aggregator-specific route info
    aggregator: str  # 'jupiter', '1inch', 'matcha', 'paraswap'

class DEXAggregator(ABC):
    """Base interface for all DEX aggregators"""

    @abstractmethod
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: float,
        slippage_bps: int = 50
    ) -> AggregatorQuote:
        """Get swap quote from aggregator"""
        pass

    @abstractmethod
    async def execute_swap(
        self,
        quote: AggregatorQuote,
        wallet_address: str
    ) -> str:
        """Execute swap, return transaction hash"""
        pass

    @abstractmethod
    def get_supported_chains(self) -> list[str]:
        """Return list of supported chains"""
        pass
```

**Concrete Implementations**:
```python
# src/integrations/dex/jupiter_adapter.py
from jupiter_py import Jupiter  # Hypothetical Jupiter SDK

class JupiterAggregator(DEXAggregator):
    """Jupiter adapter for Solana"""

    def __init__(self, rpc_url: str, private_key: str):
        self.client = Jupiter(rpc_url, private_key)

    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: float,
        slippage_bps: int = 50
    ) -> AggregatorQuote:
        # Call Jupiter API
        jupiter_quote = await self.client.quote(
            input_mint=input_token,
            output_mint=output_token,
            amount=int(amount * 1_000000),
            slippage_bps=slippage_bps
        )

        # Convert to standard format
        return AggregatorQuote(
            input_token=input_token,
            output_token=output_token,
            input_amount=amount,
            output_amount=jupiter_quote['outAmount'] / 1_000000,
            estimated_slippage=jupiter_quote['slippageBps'] / 10000,
            estimated_gas=0.00025,  # Solana gas is tiny
            route_data=jupiter_quote,
            aggregator='jupiter'
        )

    async def execute_swap(
        self,
        quote: AggregatorQuote,
        wallet_address: str
    ) -> str:
        tx_hash = await self.client.swap(quote.route_data)
        return tx_hash

    def get_supported_chains(self) -> list[str]:
        return ['solana']


# src/integrations/dex/oneinch_adapter.py
from oneinch_py import OneInchClient  # Hypothetical 1inch SDK

class OneInchAggregator(DEXAggregator):
    """1inch adapter for EVM chains"""

    def __init__(self, chain_id: int, api_key: str):
        self.client = OneInchClient(chain_id, api_key)
        self.chain_id = chain_id

    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: float,
        slippage_bps: int = 50
    ) -> AggregatorQuote:
        # Call 1inch API
        oneinch_quote = await self.client.get_quote(
            src=input_token,
            dst=output_token,
            amount=int(amount * 1e18),  # Assuming 18 decimals
            slippage=slippage_bps / 10000
        )

        # Convert to standard format
        return AggregatorQuote(
            input_token=input_token,
            output_token=output_token,
            input_amount=amount,
            output_amount=oneinch_quote['toTokenAmount'] / 1e18,
            estimated_slippage=slippage_bps / 10000,
            estimated_gas=oneinch_quote['estimatedGas'],
            route_data=oneinch_quote,
            aggregator='1inch'
        )

    async def execute_swap(
        self,
        quote: AggregatorQuote,
        wallet_address: str
    ) -> str:
        tx = await self.client.swap(quote.route_data, wallet_address)
        return tx['hash']

    def get_supported_chains(self) -> list[str]:
        # Chain ID to name mapping
        chains = {1: 'ethereum', 56: 'bsc', 8453: 'base', 42161: 'arbitrum'}
        return [chains.get(self.chain_id, 'unknown')]
```

**Factory for Aggregator Selection**:
```python
# src/integrations/dex/aggregator_factory.py
from typing import Dict
from src.config import Config

class AggregatorFactory:
    """Factory to create appropriate aggregator based on chain"""

    def __init__(self, config: Config):
        self.config = config
        self._aggregators: Dict[str, DEXAggregator] = {}

    def get_aggregator(self, chain: str) -> DEXAggregator:
        """Get best aggregator for given chain"""

        # Check cache first
        if chain in self._aggregators:
            return self._aggregators[chain]

        # Create appropriate aggregator based on config
        aggregator_config = self.config.aggregators.get(chain)

        if chain == 'solana':
            aggregator = JupiterAggregator(
                rpc_url=self.config.solana_rpc,
                private_key=self.config.solana_private_key
            )
        elif chain in ['ethereum', 'base', 'arbitrum', 'polygon', 'bsc']:
            chain_id = {'ethereum': 1, 'bsc': 56, 'base': 8453,
                        'arbitrum': 42161, 'polygon': 137}[chain]
            aggregator = OneInchAggregator(
                chain_id=chain_id,
                api_key=self.config.oneinch_api_key
            )
        else:
            raise ValueError(f"No aggregator configured for chain: {chain}")

        # Cache it
        self._aggregators[chain] = aggregator
        return aggregator
```

**Usage in Trading Code (Now Swappable)**:
```python
# src/trading/dex_executor.py
class DEXExecutor:
    def __init__(self, aggregator_factory: AggregatorFactory):
        self.aggregator_factory = aggregator_factory

    async def buy_token(self, chain: str, token_in: str, token_out: str, amount: float):
        """Buy token using best aggregator for chain"""

        # Get appropriate aggregator (Jupiter for Solana, 1inch for EVM)
        aggregator = self.aggregator_factory.get_aggregator(chain)

        # Get quote (works with ANY aggregator)
        quote = await aggregator.get_quote(
            input_token=token_in,
            output_token=token_out,
            amount=amount,
            slippage_bps=50
        )

        # Execute swap
        tx_hash = await aggregator.execute_swap(quote, self.wallet_address)

        logger.info(f"Executed swap via {quote.aggregator}: {tx_hash}")
        return tx_hash
```

**Configuration-Driven Selection**:
```yaml
# config/aggregators.yaml
aggregators:
  solana:
    primary: jupiter
    fallback: raydium_sdk
  ethereum:
    primary: 1inch
    fallback: matcha
  base:
    primary: 1inch
    fallback: uniswap_sdk
  arbitrum:
    primary: 1inch
    fallback: paraswap
```

**Benefits of Adapter Pattern**:
- ✅ **Swappable**: Switch from Jupiter to Raydium SDK with zero code changes (just config)
- ✅ **Testable**: Mock DEXAggregator interface for unit tests
- ✅ **Extensible**: Add new aggregators (Matcha, ParaSwap) by implementing interface
- ✅ **Maintainable**: Single place to change aggregator logic
- ✅ **Fallback Support**: If Jupiter is down, automatically use fallback aggregator

**Exchange Adapter Interface (CEX)**:
```python
# src/integrations/cex/exchange_adapter.py
from abc import ABC, abstractmethod
from typing import Optional, List

class ExchangeAdapter(ABC):
    """Base interface for all centralized exchanges"""

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get current price ticker"""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None
    ) -> str:
        """Place order, return order ID"""
        pass

    @abstractmethod
    async def get_balance(self, asset: str) -> float:
        """Get balance for asset"""
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel order"""
        pass

# Implementation examples:
class BinanceAdapter(ExchangeAdapter):
    """Binance implementation"""
    # ... implement all methods using ccxt or binance SDK

class BybitAdapter(ExchangeAdapter):
    """Bybit implementation"""
    # ... implement all methods

class ExchangeFactory:
    """Factory to create appropriate exchange adapter"""

    def get_exchange(self, exchange_name: str) -> ExchangeAdapter:
        if exchange_name == 'binance':
            return BinanceAdapter(api_key, api_secret)
        elif exchange_name == 'bybit':
            return BybitAdapter(api_key, api_secret)
        # ... etc
```

**Result**:
- Swap Binance for Bybit → change 1 line in config
- Add new exchange → implement ExchangeAdapter interface
- Test with mock exchange → inject MockExchangeAdapter

---

#### 2.2.0.1 Event Bus System (THE HEART) ⭐⭐⭐

**Central Event Bus**:
The event bus is the **core communication mechanism** of the entire system. ALL components communicate through events - no direct coupling.

**Purpose**:
- Decouple all system components
- Enable reactive, event-driven architecture
- Allow components to run independently (always-on vs reactive)
- Provide audit trail of all system events

**Implementation**:
```python
# src/core/event_bus.py
class EventBus:
    """
    Central event bus for system-wide event communication.
    Runs 24/7 as the heart of the system.
    """

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_queue = asyncio.Queue(maxsize=10000)
        self.running = False

    def subscribe(self, event_type: str, handler: Callable):
        """Register event handler"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        """Publish event to queue"""
        await self.event_queue.put(event)

    async def process_events(self):
        """
        Main event processing loop - runs 24/7.
        This is THE HEART of the system.
        """
        self.running = True
        logger.info("Event Bus started - THE HEART is beating")

        while self.running:
            try:
                # Get next event from queue
                event = await self.event_queue.get()
                event_type = event.__class__.__name__

                # Dispatch to all subscribers
                if event_type in self.subscribers:
                    for handler in self.subscribers[event_type]:
                        try:
                            await handler(event)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")
                            # Emit system error event
                            await self.publish(SystemError(
                                component=handler.__name__,
                                error=str(e)
                            ))

            except Exception as e:
                logger.critical(f"Event bus error: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
```

**Event Types**:
```python
# src/core/events.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Event:
    """Base event class"""
    timestamp: float

# Market Data Events
@dataclass
class TradeTickReceived(Event):
    symbol: str
    price: float
    volume: float
    side: str  # "buy" or "sell" aggressor

@dataclass
class CandleCompleted(Event):
    symbol: str
    timeframe: str  # "1m", "5m", "15m"
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class MarketDataConnectionLost(Event):
    exchange: str
    market_type: str
    reason: str

# Analytics Events
@dataclass
class AnalyticsUpdated(Event):
    symbol: str
    timeframe: str
    order_flow_ratio: float
    cvd: float
    vwap: float

@dataclass
class OrderFlowImbalanceDetected(Event):
    symbol: str
    ratio: float
    direction: str  # "bullish" or "bearish"
    strength: float

# Trading Events
@dataclass
class TradingSignalGenerated(Event):
    symbol: str
    side: str
    confluence_score: float
    entry_price: float
    stop_loss: float
    take_profit: float

@dataclass
class OrderPlaced(Event):
    order_id: str
    symbol: str
    side: str
    quantity: float

@dataclass
class OrderFilled(Event):
    order_id: str
    symbol: str
    fill_price: float
    quantity: float

@dataclass
class OrderFailed(Event):
    order_id: str
    symbol: str
    reason: str

# Position Events
@dataclass
class PositionOpened(Event):
    position_id: str
    symbol: str
    side: str
    entry_price: float
    quantity: float

@dataclass
class PositionClosed(Event):
    position_id: str
    symbol: str
    entry_price: float
    exit_price: float
    pnl_percent: float
    reason: str

# System Events
@dataclass
class SystemError(Event):
    component: str
    error: str
    critical: bool = False
```

**Event Subscription Setup**:
```python
# main.py - Setup all event subscribers
async def setup_event_subscribers(event_bus, container):
    """Wire up all event subscriptions"""

    # Get services from DI container
    decision_engine = container.resolve("DecisionEngine")
    execution_engine = container.resolve("ExecutionEngine")
    position_monitor = container.resolve("PositionMonitor")
    notification_system = container.resolve("NotificationSystem")

    # Decision Engine listens to analytics
    event_bus.subscribe(
        "OrderFlowImbalanceDetected",
        decision_engine.on_order_flow_imbalance
    )
    event_bus.subscribe(
        "MicrostructurePatternDetected",
        decision_engine.on_microstructure_pattern
    )

    # Execution Engine listens to signals
    event_bus.subscribe(
        "TradingSignalGenerated",
        execution_engine.on_trading_signal
    )

    # Position Monitor listens to position events
    event_bus.subscribe(
        "PositionOpened",
        position_monitor.on_position_opened
    )

    # Notification System listens to everything important
    # Critical events (🔴 immediate email)
    event_bus.subscribe("OrderFailed", notification_system.on_critical_event)
    event_bus.subscribe("MarketDataConnectionLost", notification_system.on_critical_event)
    event_bus.subscribe("SystemError", notification_system.on_critical_event)

    # Info events (✉️ optional email)
    event_bus.subscribe("TradingSignalGenerated", notification_system.on_info_event)
    event_bus.subscribe("OrderFilled", notification_system.on_info_event)
    event_bus.subscribe("PositionClosed", notification_system.on_info_event)
```

**Benefits**:
- **Fully Decoupled**: Components don't know about each other
- **Easy to Extend**: Add new event listeners without modifying emitters
- **Audit Trail**: All events logged automatically
- **Testable**: Mock event bus for testing
- **Reliable**: Queue ensures events aren't lost

---

#### 2.2.0.2 Notification System

**Responsibility**: Send real-time alerts for trading events via external notification services

**Notification Channels** (External Services):
- **Email**: SendGrid API for critical alerts and trade confirmations
- **Telegram**: Bot API for real-time mobile notifications
- **Discord**: Webhook integration for community/team alerts

**Event-Driven Integration**:
- Listens to Event Bus for important events (order failures, position updates, system errors)
- Priority-based routing: Critical events → immediate alerts, Info events → batched digests
- Fully decoupled from core trading logic (external service calls)

**Alert Types**:
- 🔴 Critical: Order failures, connection loss, system errors
- 🟡 Warning: Data quality issues, validation failures
- 🟢 Info: Trade signals, position updates, P&L reports

---

#### 2.2.1 Data Ingestion Layer
**Responsibility**: Collect and normalize market data from multiple sources via real-time WebSocket connections

**Sub-components**:
- **Market Data Collectors (Cryptofeed)**
  - **Binance WebSocket streams (TRADES ONLY)**
    - Individual trade stream (tick data with actual executed prices)
    - Candle streams (1M, 5M, 15M OHLCV aggregation)
    - **NO orderbook streaming** - orderbooks are heavily manipulated
  - Multiple concurrent connections for different trading pairs
  - Automatic reconnection and error handling
  - DEX blockchain listeners (Uniswap, PancakeSwap, etc.)
  - Price aggregators for meme coins

- **Real-Time Data Pipeline**
  - **Tick-by-tick trade data ingestion** (THE SOURCE OF TRUTH)
    - Each trade contains: timestamp, price, volume, side (buy/sell aggressor)
    - This is actual executed trades - cannot be manipulated
    - Trades show real market behavior and price action
  - OHLCV candle aggregation (1M, 5M, 15M timeframes)
  - Volume profile calculation from actual trades
  - Timestamp synchronization across feeds

- **Data Normalizer**
  - Standardize data formats across different exchanges
  - Handle timestamp synchronization
  - Validate data integrity and handle outliers
  - Convert between different price/volume formats

- **Price & Volume Behavior Analyzer**
  - Calculate spread from actual trade prices (high-low in period)
  - Measure true trading volume (not fake orderbook depth)
  - Assess actual slippage from executed trades
  - Monitor buy vs. sell aggressor pressure (order flow)
  - Detect abnormal price movements and volume spikes

**Why NO Orderbook?**
- Orderbooks show fake liquidity (spoofing, fake walls)
- Large orders get pulled before execution
- Whales manipulate sentiment with fake orders
- **TRADES = TRUTH**: Only executed trades show real supply/demand

**Output**: Clean, normalized, real-time trade data and price behavior flowing into analytics engine

#### 2.2.2 Core Decision Engine
**Responsibility**: Analyze market conditions in real-time using hierarchical signal system, generate high-probability trading signals

**Analysis Hierarchy**:

**PRIMARY SIGNALS** (Entry Trigger - Must Have):
1. **Order Flow Imbalance**
   - Real-time buy vs sell aggressor volume
   - Detects aggressive buying/selling pressure
   - Threshold: >2:1 ratio for signal generation
   - Calculated from actual trade data (not orderbook)

2. **Microstructure Analysis**
   - Price behavior at key levels
   - Rejection patterns (wicks, pin bars)
   - Absorption vs breakout behavior
   - Speed of price movement

**SECONDARY FILTERS** (Confirmation - Increase Probability):
3. **Market Profile**
   - Value Area High/Low (70% volume zone)
   - Point of Control (POC - highest volume price)
   - Trading at extremes vs inside value area
   - Profile shape (balanced vs trending)

4. **Mean Reversion**
   - Price deviation from moving average
   - Overbought/oversold conditions
   - Extreme deviations likely to revert
   - Works best in ranging markets

5. **Autocorrelation**
   - Price momentum persistence
   - Trend continuation probability
   - Recent candle correlation analysis
   - Helps identify true trends vs noise

6. **Demand Zones (Support)**
   - Price levels with historical strong buying
   - Fresh zones (untested) vs tested zones
   - Volume-confirmed support areas
   - Entry opportunities on retest

7. **Supply Zones (Resistance)**
   - Price levels with historical strong selling
   - Fresh zones (untested) vs tested zones
   - Volume-confirmed resistance areas
   - Short entry or exit targets

8. **Fair Value Gaps (FVG)**
   - Imbalances in price action (3-candle pattern)
   - Gaps often get filled (mean reversion)
   - High-probability reversal zones
   - Confluence with supply/demand zones

**Signal Generation Logic**:

**PRIMARY SIGNALS (Both Must Be TRUE)**:
1. Order Flow Imbalance: Ratio exceeds threshold
2. Microstructure: Rejection pattern confirmed

**SECONDARY FILTERS (Weighted Scoring System)**:

3. **Market Profile** (Weight: 1.5 points):
   - At Value Area extremes (VAH/VAL): +1.5 points
   - Inside Value Area: +0.5 points
   - Wrong side of POC: 0 points

4. **Mean Reversion** (Weight: 1.5 points):
   - Price beyond 2σ from recent price mean (last 15 min): +1.5 points
   - Price beyond 1σ from mean: +0.75 points
   - Price inside 1σ: 0 points

5. **Autocorrelation** (Weight: 1.0 point):
   - High correlation (r>0.6) OR Low (|r|<0.3): +1.0 point
   - Medium correlation: +0.5 points

6. **Demand Zone** (Weight: 2.0 points):
   - Fresh demand zone (untested): +2.0 points
   - Tested demand zone (1-2 touches): +1.0 point
   - No relevant demand zone: 0 points

7. **Supply Zone** (Weight: 0.5 points):
   - Supply zone as target: +0.5 points
   - No relevant supply zone: 0 points

8. **Fair Value Gap** (Weight: 1.5 points):
   - FVG in trade direction: +1.5 points
   - No relevant FVG: 0 points

**TOTAL POSSIBLE CONFLUENCE SCORE**: 10.0 points

**ENTRY DECISION THRESHOLDS**:
- Score ≥ 3.0: Consider entry (low probability) - PRIMARY + 2 secondary filters minimum
- Score ≥ 5.0: Strong entry signal (medium probability)
- Score ≥ 7.0: Very strong entry (high probability)
- Score < 3.0: NO TRADE (insufficient confluence)

**Example - Real-Time Signal Generation**:
```
Tick arrives: BTCUSDT at $50,245

PRIMARY ANALYSIS:
✅ Order Flow Imbalance: 3.2:1 buy/sell ratio (>2.5:1 threshold) → BUY SIGNAL
✅ Microstructure: Strong rejection wick at $50,200, close near high → BULLISH

SECONDARY FILTERS (Weighted Scoring):
✅ Market Profile: Trading at Value Area Low ($50,250) → +1.5 points
✅ Mean Reversion: Price -1.8σ below 15-min mean price ($50,400) → +1.5 points
✅ Autocorrelation: Low (r=0.2) → Range-bound, mean reversion expected → +1.0 point
✅ Demand Zone: Fresh zone at $50,200-50,250 (untested) → +2.0 points
❌ Supply Zone: None nearby as target → 0 points
✅ Fair Value Gap: Bullish FVG at $50,300 (unfilled) → +1.5 points

CONFLUENCE SCORE: 7.5/10.0 points (VERY STRONG)

DECISION: ✅ ENTER LONG
- Primary signals: Both confirmed ✅
- Confluence: 7.5/10.0 (HIGH PROBABILITY)
- Entry: $50,245
- Stop: $50,120 (0.5% trailing)
- Target: $50,500 (FVG fill at $50,300 + extension to supply)
```

---

**Composition-Based Signal Generation Pipeline** ⭐:

The decision engine uses **composition** to combine multiple analyzers and filters, following a clear two-stage hierarchy. This replaces monolithic if-else decision logic with modular, testable components.

**Architecture**:
```python
# src/decision/signal_pipeline.py
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class SignalResult:
    """Result from a signal analyzer"""
    passed: bool
    strength: float  # 0.0 to 1.0
    reason: str
    metadata: dict


class SignalAnalyzer(ABC):
    """Base class for primary signal analyzers"""

    @abstractmethod
    async def analyze(self, market_data: MarketData) -> SignalResult:
        pass


class SignalFilter(ABC):
    """Base class for secondary signal filters"""

    def __init__(self, weight: float):
        self.weight = weight

    @abstractmethod
    async def evaluate(self, market_data: MarketData) -> float:
        """Return score from 0.0 to weight (max contribution)"""
        pass


# PRIMARY ANALYZERS (must all pass)
class OrderFlowAnalyzer(SignalAnalyzer):
    """PRIMARY SIGNAL #1: Order flow imbalance detection"""

    def __init__(self, threshold: float = 2.5):
        self.threshold = threshold

    async def analyze(self, market_data: MarketData) -> SignalResult:
        buy_volume = market_data.buy_volume_30s
        sell_volume = market_data.sell_volume_30s

        ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
        passed = ratio > self.threshold
        strength = min(ratio / 5.0, 1.0)

        return SignalResult(
            passed=passed,
            strength=strength,
            reason=f"Order flow ratio: {ratio:.2f} (threshold: {self.threshold})",
            metadata={"ratio": ratio, "buy_volume": buy_volume, "sell_volume": sell_volume}
        )


class MicrostructureAnalyzer(SignalAnalyzer):
    """PRIMARY SIGNAL #2: Price rejection pattern detection"""

    async def analyze(self, market_data: MarketData) -> SignalResult:
        candle = market_data.latest_candle_1m

        body_size = abs(candle.close - candle.open)
        upper_wick = candle.high - max(candle.close, candle.open)
        lower_wick = min(candle.close, candle.open) - candle.low

        # Bullish rejection
        bullish_rejection = (
            lower_wick > body_size * 2 and
            candle.close > candle.open and
            (candle.close - candle.low) / (candle.high - candle.low) > 0.8
        )

        # Bearish rejection
        bearish_rejection = (
            upper_wick > body_size * 2 and
            candle.close < candle.open and
            (candle.high - candle.close) / (candle.high - candle.low) > 0.8
        )

        passed = bullish_rejection or bearish_rejection
        strength = 0.8 if passed else 0.0

        return SignalResult(
            passed=passed,
            strength=strength,
            reason=f"Rejection: {'Bullish' if bullish_rejection else 'Bearish' if bearish_rejection else 'None'}",
            metadata={"body_size": body_size, "upper_wick": upper_wick, "lower_wick": lower_wick}
        )


# SECONDARY FILTERS (weighted scoring)
class MarketProfileFilter(SignalFilter):
    """FILTER #1: Market profile analysis (weight: 1.5)"""

    def __init__(self, weight: float = 1.5):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        profile = market_data.market_profile_15m
        current_price = market_data.current_price

        at_val = abs(current_price - profile.value_area_low) < profile.value_area_low * 0.001
        at_vah = abs(current_price - profile.value_area_high) < profile.value_area_high * 0.001

        if at_val or at_vah:
            return self.weight  # Full points
        elif profile.value_area_low < current_price < profile.value_area_high:
            return self.weight * 0.5  # Inside value area
        else:
            return 0.0


class MeanReversionFilter(SignalFilter):
    """FILTER #2: Mean reversion from recent price mean (weight: 1.5)"""

    def __init__(self, weight: float = 1.5):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        # Calculate mean price from last 15 minutes of ticks
        recent_mean = market_data.price_mean_15m
        current_price = market_data.current_price
        std_dev = market_data.price_std_dev_15m

        deviation_sigma = abs(current_price - recent_mean) / std_dev

        if deviation_sigma >= 2.0:
            return self.weight  # Beyond 2σ - extreme deviation
        elif deviation_sigma >= 1.0:
            return self.weight * 0.5  # Beyond 1σ
        else:
            return 0.0


class AutocorrelationFilter(SignalFilter):
    """FILTER #3: Autocorrelation analysis (weight: 1.0)"""

    def __init__(self, weight: float = 1.0):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        correlation = market_data.price_autocorrelation

        if abs(correlation) > 0.6 or abs(correlation) < 0.3:
            return self.weight
        else:
            return self.weight * 0.5


class DemandZoneFilter(SignalFilter):
    """FILTER #4: Demand zone proximity (weight: 2.0)"""

    def __init__(self, weight: float = 2.0):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        demand_zones = market_data.demand_zones
        current_price = market_data.current_price

        # Check for fresh demand zones
        for zone in demand_zones:
            if zone.is_fresh and zone.price_low <= current_price <= zone.price_high:
                return self.weight
            elif zone.test_count <= 2 and zone.price_low <= current_price <= zone.price_high:
                return self.weight * 0.5

        return 0.0


class SupplyZoneFilter(SignalFilter):
    """FILTER #5: Supply zone as target (weight: 0.5)"""

    def __init__(self, weight: float = 0.5):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        supply_zones = market_data.supply_zones
        current_price = market_data.current_price

        # Check if supply zone exists as target
        for zone in supply_zones:
            if zone.price_low > current_price:  # Zone above current price
                return self.weight

        return 0.0


class FairValueGapFilter(SignalFilter):
    """FILTER #6: Fair value gap detection (weight: 1.5)"""

    def __init__(self, weight: float = 1.5):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        fvgs = market_data.fair_value_gaps
        current_price = market_data.current_price

        # Check for unfilled FVGs in trade direction
        for fvg in fvgs:
            if not fvg.is_filled and fvg.gap_low <= current_price <= fvg.gap_high:
                return self.weight

        return 0.0


# DECISION ENGINE (orchestrates evaluation)
class DecisionEngine:
    """
    Orchestrates signal generation using composition.
    Primary analyzers must ALL pass, then secondary filters add confluence.
    """

    def __init__(
        self,
        primary_analyzers: List[SignalAnalyzer],
        secondary_filters: List[SignalFilter],
        min_confluence_score: float = 3.0
    ):
        self.primary_analyzers = primary_analyzers
        self.secondary_filters = secondary_filters
        self.min_confluence_score = min_confluence_score

    async def evaluate(self, market_data: MarketData) -> Optional[TradeSignal]:
        """
        Evaluate market data and generate trade signal if conditions met.

        Logic:
        1. ALL primary analyzers must pass (AND logic)
        2. Calculate confluence score from secondary filters (sum)
        3. Generate trade signal if confluence >= threshold
        """

        # Step 1: Check primary signals (ALL must pass)
        primary_results = []
        for analyzer in self.primary_analyzers:
            result = await analyzer.analyze(market_data)
            primary_results.append(result)

            if not result.passed:
                logger.debug(
                    f"Primary signal failed: {analyzer.__class__.__name__} - {result.reason}"
                )
                return None  # Early exit

        logger.info("✅ All primary signals passed")

        # Step 2: Calculate confluence score
        confluence_score = 0.0
        filter_contributions = {}

        for filter_obj in self.secondary_filters:
            contribution = await filter_obj.evaluate(market_data)
            confluence_score += contribution
            filter_contributions[filter_obj.__class__.__name__] = contribution

        logger.info(f"Confluence score: {confluence_score:.1f}/10.0")
        logger.debug(f"Filter contributions: {filter_contributions}")

        # Step 3: Check threshold
        if confluence_score < self.min_confluence_score:
            logger.debug(
                f"Insufficient confluence: {confluence_score:.1f} < {self.min_confluence_score}"
            )
            return None

        # Step 4: Generate trade signal
        return TradeSignal(
            symbol=market_data.symbol,
            side=self._determine_side(primary_results, market_data),
            confluence_score=confluence_score,
            primary_signals=primary_results,
            filter_scores=filter_contributions,
            timestamp=market_data.timestamp
        )

    def _determine_side(self, primary_results: List[SignalResult], market_data: MarketData) -> str:
        """Determine trade direction from primary signals"""
        # Analyze order flow direction, rejection pattern
        return "long"  # or "short"
```

**Factory Function to Create Pipeline**:
```python
# Setup in main.py
def create_decision_engine():
    """Factory function to create decision engine with all analyzers"""

    # Primary analyzers (both must pass)
    primary_analyzers = [
        OrderFlowAnalyzer(threshold=2.5),
        MicrostructureAnalyzer()
    ]

    # Secondary filters (weighted scoring)
    secondary_filters = [
        MarketProfileFilter(weight=1.5),
        MeanReversionFilter(weight=1.5),
        AutocorrelationFilter(weight=1.0),
        DemandZoneFilter(weight=2.0),
        SupplyZoneFilter(weight=0.5),
        FairValueGapFilter(weight=1.5)
    ]

    return DecisionEngine(
        primary_analyzers=primary_analyzers,
        secondary_filters=secondary_filters,
        min_confluence_score=3.0
    )
```

**Evaluation Flow**:
```
Market Data Input
        ↓
┌───────────────────────────┐
│   PRIMARY ANALYZERS       │
│   (ALL must pass)         │
├───────────────────────────┤
│ OrderFlowAnalyzer         │ → Pass? ✅
│ MicrostructureAnalyzer    │ → Pass? ✅
└───────────────────────────┘
        ↓ (All passed)
┌───────────────────────────┐
│   SECONDARY FILTERS       │
│   (Weighted scoring)      │
├───────────────────────────┤
│ MarketProfileFilter       │ → +1.5 points
│ MeanReversionFilter       │ → +1.5 points
│ AutocorrelationFilter     │ → +1.0 point
│ DemandZoneFilter          │ → +2.0 points
│ SupplyZoneFilter          │ → +0.0 points
│ FairValueGapFilter        │ → +1.5 points
└───────────────────────────┘
        ↓
Confluence Score: 7.5/10.0
        ↓
Score >= 3.0? ✅ YES
        ↓
GENERATE TRADE SIGNAL
```

**Adding New Analyzers/Filters**:
```python
# Create new filter class
class LiquidityFilter(SignalFilter):
    def __init__(self, weight: float = 1.0):
        super().__init__(weight)

    async def evaluate(self, market_data: MarketData) -> float:
        if market_data.liquidity_score > 0.8:
            return self.weight
        return 0.0

# Add to secondary filters list
secondary_filters.append(LiquidityFilter(weight=1.0))
```

**Benefits**:
- **Modular**: Each analyzer is independent class
- **Extensible**: Add new analyzers without modifying existing code
- **Testable**: Test each component in isolation
- **Transparent**: See exactly which filters contributed points
- **Configurable**: Adjust weights via configuration file
- **Maintainable**: No monolithic if-else decision logic
- **Clear Hierarchy**: Primary (must pass) vs Secondary (scoring) is explicit

---

**Trading Timeframe Configurations**:

**Configuration 1: Ultra-Short Scalping (1M / 5M / 15M)**
- **Use Case**: High-frequency scalping with 30-second to 5-minute hold times
- **Timeframe Hierarchy**:
  - **15M (LONGEST)**: Trend & Regime Detection + Market Profile Zones
  - **5M (MIDDLE)**: Order Flow Cascade Confirmation
  - **1M (FASTEST)**: Entry Timing & Final Trigger
- **Target**: 5-20 trades per hour per pair
- **Hold Duration**: 30 seconds - 5 minutes
- **Target R:R**: 1:1.5 to 1:2
- **Best For**: High volatility periods, trending markets ONLY

---

## 2.3 🚨 CRITICAL: Hierarchical Multi-Timeframe Decision Flow

**Why This Matters**:
With 100+ trading pairs, we CANNOT waste computational resources analyzing ranging/choppy markets. The system uses a **SHORT-CIRCUIT filter** at each level - if a condition fails, we immediately STOP and move to the next pair.

### 2.3.1 Level 1: Trend & Regime Detection (LONGEST TIMEFRAME) ⚡ SHORT-CIRCUIT FILTER

**Purpose**: Filter out ranging markets IMMEDIATELY - only trending markets proceed.

**For Ultra-Short Scalping (15M longest timeframe)**:

```python
# STEP 1: Detect market regime (LONGEST TIMEFRAME ONLY)
trend_direction = detect_trend(longest_timeframe)

if trend_direction == "RANGING":
    # 🚫 SHORT-CIRCUIT: Skip this pair entirely
    # Do NOT proceed to further analysis
    # Move to next trading pair immediately
    return None  # No trade consideration

elif trend_direction == "UPTREND":
    # ✅ ONLY consider LONG setups
    allowed_direction = "LONG"

elif trend_direction == "DOWNTREND":
    # ✅ ONLY consider SHORT setups
    allowed_direction = "SHORT"
```

**Trend Detection Criteria** (Pure Price Action):
- **Directional Structure**: Last 3 candles on 15M making higher highs/higher lows (clear trend)
- **ADX**: >25 (trending), <20 (ranging - REJECT)
- **Directional Persistence**: >0.55 (price movements continue in same direction)
- **Mean Reversion Strength**: <0.6 (price doesn't snap back too quickly)
- **Volume Trend**: Increasing volume in trend direction

**RANGING Market Detection (REJECT IMMEDIATELY)**:
- No clear higher highs or lower lows on 15M (last 3 candles)
- ADX < 20 (weak trend strength)
- Directional persistence < 0.55 (random/choppy price action)
- Mean reversion strength > 0.6 (price snaps back too fast)
- Price chopping between same levels
- Low volatility (ATR below threshold)

**Additional Filter Metrics**:

**Directional Persistence (Hurst Exponent)**:
- **Measures**: Tendency for price movements to continue in same direction vs flip randomly
- **Range**: 0.0 to 1.0
  - **> 0.6**: Strong trending (price keeps going same direction) ✅ TRADE
  - **0.45-0.55**: Random walk (unpredictable flipping) ❌ SKIP
  - **< 0.45**: Mean reverting noise (constant bouncing) ❌ SKIP
- **Calculation**: Analyze last 50-100 candles on longest timeframe
- **Why it matters**: Avoids undecided/choppy markets where price randomly flips direction

**Mean Reversion Strength**:
- **Measures**: How quickly price returns to average after displacement
- **Range**: 0.0 to 1.0
  - **< 0.5**: Weak reversion (trending market - price drifts) ✅ TRADE
  - **0.5-0.7**: Moderate reversion (questionable) ⚠️ CAUTION
  - **> 0.7**: Strong reversion (ranging - price snaps back fast) ❌ SKIP
- **Calculation**: Measure speed of return to recent price mean after 2σ deviation
- **Why it matters**: Avoids ranging markets where price gets pulled back quickly

**Combined Filter Logic**:
```python
# ALL conditions must pass for trending market
if (
    adx > 25                           # Trend strength
    and directional_persistence > 0.55 # Movements persist
    and mean_reversion_strength < 0.6  # Doesn't snap back too fast
    and ema_alignment_valid            # EMAs in order
    and atr_sufficient                 # Enough volatility
):
    # ✅ Strong trending market - proceed to Level 2
    pass
else:
    # ❌ Ranging/choppy/risky market - SKIP
    return None
```

**Benefits of Enhanced Filter**:
1. **Avoids undecided markets** (low directional persistence)
2. **Avoids high-risk choppy markets** (strong mean reversion)
3. **Avoids low-lucrativity ranging markets** (where price goes nowhere)
4. **Only trades strongest trending opportunities** (all metrics aligned)

**Result**:
- ❌ **RANGING** → Stop processing, skip pair (save CPU resources)
- ✅ **TRENDING** → Continue to Level 2

---

### 2.3.2 Level 2: Market Profile Zone Analysis (LONGEST TIMEFRAME)

**Purpose**: Identify WHERE to look for trades - these are surveillance areas, NOT trade signals.

**Only Executed If**: Pair passed Level 1 (trending market confirmed)

**For Ultra-Short Scalping (15M longest timeframe)**:

```python
# STEP 2: Identify zones on LONGEST timeframe ONLY
zones = identify_market_profile_zones(longest_timeframe)

if allowed_direction == "LONG":
    # Look for DEMAND ZONES (support levels)
    target_zones = zones.demand_zones

elif allowed_direction == "SHORT":
    # Look for SUPPLY ZONES (resistance levels)
    target_zones = zones.supply_zones

# Wait for price to reach one of these zones
# No zone = no trade
if not price_near_zone(current_price, target_zones):
    return None  # Not at a zone, keep monitoring
```

**⚠️ CRITICAL: Zones Are NOT Trade Signals**

These zones are **surveillance areas** - places where day traders BELIEVE something will happen:
- **Support/Resistance** (aka Demand/Supply Zones): Historical levels where price reversed
- **Fair Value Gaps**: Price areas that were "skipped" during fast moves (day traders believe price will return to "fill the gap")

**We do NOT trade these zones by themselves!**

They simply tell us **WHERE TO WATCH** for actual order flow confirmation.

**Zone Identification**:

1. **Demand Zones (Support)** - Same thing, different names:
   - Historical price levels where buyers stepped in aggressively
   - Volume spike at the level
   - Strong rejection wicks (long lower wicks)
   - Price bounced up from this area

2. **Supply Zones (Resistance)** - Same thing, different names:
   - Historical price levels where sellers stepped in aggressively
   - Volume spike at the level
   - Strong rejection wicks (long upper wicks)
   - Price bounced down from this area

3. **Fair Value Gaps (FVG)** - Mathematically identified:
   ```python
   # 3-Candle Pattern
   candle_1_high = $100
   candle_2 = (fast move - the "gap")
   candle_3_low = $105

   if candle_3_low > candle_1_high:
       # BULLISH FVG: Price never traded between $100-$105
       # Day traders believe price will come back to "fill" this gap
       fvg_zone = ($100, $105)
   ```

**Zone Strength Scoring**:
- Fresh zone (untested) = 100 points (strongest belief)
- Tested 1-2 times = 70 points (still respected)
- Tested 3+ times = 40 points (weakening - belief fading)
- Volume at zone creation (higher = stronger belief)

**What These Zones Really Are**:
- **Psychological levels** where many day traders have placed orders
- **Areas of interest** where institutional activity historically occurred
- **NOT predictive** - just historical observations
- **NOT trade signals** - just surveillance cameras

**Our Approach**:
We monitor these zones and ONLY trade if **order flow and bid-ask bounce CONFIRM** that what day traders believe is actually happening. If the confirmation doesn't come, we don't trade.

---

### 2.3.3 Level 3: Order Flow Cascade Detection (ALL TIMEFRAMES)

**Purpose**: **THIS IS THE REAL SIGNAL** - Confirm what day traders believe is actually happening.

**Only Executed If**:
- Level 1 passed (trending market)
- Level 2 passed (price at demand/supply zone - surveillance area)

**What We're Testing**:
Day traders believe price will bounce at support/resistance or fill fair value gaps. We test if **institutional money is actually confirming this belief** by checking if order flow is accelerating in the expected direction.

**Cascade Logic**:

```python
# STEP 3: Check order flow imbalance CASCADE
# Measure imbalance on all timeframes

imbalance_1m = calculate_imbalance("1m")    # Fastest
imbalance_middle = calculate_imbalance(middle_tf)  # 5m
imbalance_longest = calculate_imbalance(longest_tf)  # 15m (longest TF)

# FOR LONG ENTRY (at demand zone in uptrend):
if allowed_direction == "LONG":
    cascade_valid = (
        imbalance_1m > imbalance_middle > imbalance_longest
        and imbalance_1m > 2.0  # At least 2:1 buy pressure
    )

# FOR SHORT ENTRY (at supply zone in downtrend):
elif allowed_direction == "SHORT":
    cascade_valid = (
        imbalance_1m < imbalance_middle < imbalance_longest
        and imbalance_1m < 0.5  # At least 2:1 sell pressure
    )

if not cascade_valid:
    return None  # Cascade not confirmed, wait
```

**Example CASCADE for LONG**:
```
1-minute imbalance: 3.5  (3.5x more buy volume than sell)
15-minute imbalance: 2.8  (still bullish but less aggressive)
1-hour imbalance: 1.8  (mild bullish bias)

✅ CASCADE CONFIRMED: 3.5 > 2.8 > 1.8
This shows ACCELERATION of buying at smaller timeframes = institutions getting aggressive
```

**Imbalance Calculation**:
```python
buy_volume = sum(trades where side == "buy")
sell_volume = sum(trades where side == "sell")
imbalance = buy_volume / sell_volume

# > 1.0 = more buying (bullish)
# < 1.0 = more selling (bearish)
# > 2.0 = strong buying pressure
# < 0.5 = strong selling pressure
```

---

### 2.3.4 Level 4: Bid-Ask Bounce + Volume Confirmation (1M TIMEFRAME)

**Purpose**: **FINAL CONFIRMATION** - Verify price is actually bouncing with volume, not just touching the zone.

**Only Executed If**:
- Level 1 passed (trending market)
- Level 2 passed (at surveillance zone)
- Level 3 passed (order flow cascade confirmed - institutions are active)

**What We're Testing**:
Now that we know institutions are buying/selling aggressively (Level 3), we verify the **price action itself** shows a bounce with volume spike. This confirms the zone is being respected RIGHT NOW, not just historically.

```python
# STEP 4: Final trigger - bid-ask bounce × volume
bounce_strength = detect_bid_ask_bounce("1m")
volume_spike = current_volume / avg_volume_20periods

# FOR LONG: Price bouncing OFF demand zone
if allowed_direction == "LONG":
    bounce_valid = (
        bounce_strength > 0.7  # Strong rejection of demand zone
        and volume_spike > 1.5  # 50% more volume than average
        and price_action == "BOUNCING_UP"  # Price moving away from zone
    )

# FOR SHORT: Price bouncing OFF supply zone
elif allowed_direction == "SHORT":
    bounce_valid = (
        bounce_strength > 0.7  # Strong rejection of supply zone
        and volume_spike > 1.5
        and price_action == "BOUNCING_DOWN"
    )

if bounce_valid:
    # ✅ EXECUTE TRADE
    entry_score = bounce_strength * imbalance_1m
    execute_trade(allowed_direction, entry_score)
```

**Bid-Ask Bounce Detection**:
- **Wick Analysis**: Long lower wick at demand = rejection (bullish)
- **Close Position**: Candle closes near high (strong buyers)
- **Volume**: Spike on bounce candle
- **Speed**: Quick rejection vs slow grind

---

---

## 2.4 🎯 Critical Strategy Philosophy

**What We're Really Doing**:

We are **NOT** trading based on chart patterns, support/resistance, or fair value gaps. These are not statistically proven and often fail.

**Instead, we:**
1. Use zones as **surveillance cameras** - areas to watch
2. Monitor **actual order flow** at these zones
3. Only trade when **institutions confirm** with aggressive buying/selling
4. Verify with **price action + volume spike**

**The Logic**:
```
Day traders believe: "Price will bounce at support"
                     ↓
We monitor support zone as surveillance area
                     ↓
If order flow shows institutions ARE buying aggressively (cascade)
                     ↓
AND price actually bounces with volume spike
                     ↓
Then the belief is being CONFIRMED by real money
                     ↓
ONLY THEN do we trade
```

**If No Confirmation**:
- Zone touched but no order flow acceleration? → ❌ Don't trade
- Zone touched but price breaks through? → ❌ Don't trade
- Order flow present but no bounce? → ❌ Don't trade
- Everything aligns but weak volume? → ❌ Don't trade

**We need ALL 4 levels to pass:**
1. ✅ Trending market (not ranging)
2. ✅ At surveillance zone (support/resistance/FVG)
3. ✅ Order flow cascade (institutional confirmation)
4. ✅ Bid-ask bounce + volume (price action confirmation)

**This is NOT technical analysis. This is order flow analysis with zone-based surveillance.**

---

## 2.5 🛡️ Risk Management Philosophy

**Core Principle**: **Capital Preservation > Being Right**

We are aware of zones, but we **trade the order flow confirmation** of those zones. Our risk management reflects this reality:

### Maximum Risk Per Trade: 0.5-1% Trailing Stop

**Default Configuration**:
- **All Markets (Crypto/Forex/Meme Coins)**: 0.5% trailing stop distance
- **Exit Trigger**: Trailing stop hit OR dump detected (order flow flip + volume reversal)
- **No time-based exits**: Hold as long as price moves in our favor
- **Stop activates IMMEDIATELY** on entry (no "wait for profit" delay)
- **Stop only moves in favorable direction** (never widens)

### Why 0.5-1% Maximum?

**Philosophy**: Better to exit and re-enter multiple times than risk more capital.

```
Scenario 1: Hold through drawdown
Entry: $50,000
Drawdown: -3% ($1,500 loss)
Outcome: Hope it comes back (risky)

Scenario 2: Exit at 0.5% stop, re-enter on new signal
Entry: $50,000
Stop hit: -0.5% ($250 loss)
New signal: Re-enter at $49,800
Stop hit again: -0.5% ($249 loss)
Third entry: Works, +2% profit ($1,000 gain)

Total: -$250 -$249 +$1,000 = +$501 profit
```

**Result**: Multiple small controlled losses + one winner = profitable.

**vs Holding**: One large uncontrolled loss = account damage.

### Trailing Stop Behavior

**On Entry**:
```python
entry_price = $50,000
trailing_stop = $50,000 * (1 - 0.005) = $49,750  # 0.5% below

# Stop is ACTIVE immediately
```

**As Price Moves Favorably**:
```python
# Price moves to $50,500
new_stop = $50,500 * (1 - 0.005) = $50,247.50

# Price moves to $51,000
new_stop = $51,000 * (1 - 0.005) = $50,745

# Price drops to $50,745
# STOP TRIGGERED - Exit with +1.49% profit
```

**If Price Reverses Before Profit**:
```python
entry_price = $50,000
stop = $49,750

# Price drops to $49,750 immediately
# STOP TRIGGERED - Exit with -0.5% loss

# No emotion, no hoping, no "waiting for it to come back"
# Capital preserved, ready for next signal
```

### Better to Exit and Re-Enter

**Scenario**: Wrong timing, order flow fades:
```
1. Enter at demand zone on order flow confirmation
2. Stop at 0.5% below entry
3. Price chops, hits stop (-0.5%)
4. Exit cleanly, capital preserved
5. Wait for next order flow confirmation
6. Re-enter on stronger signal
7. Win the trade (+2%)

Net: -0.5% + 2% = +1.5% profitable
```

**Alternative (no stop)**:
```
1. Enter at demand zone
2. No stop (or wide stop at 3%)
3. Price chops against you
4. Hope it comes back
5. Eventually stops out at -3%

Net: -3% loss (6x worse than controlled exit)
```

### Mental Model

**We don't "know" if the zone will hold.**
- We have awareness of the zone ✅
- We have order flow confirmation ✅
- But we DON'T KNOW if it will continue ❌

**Therefore**:
- Place stop immediately at 0.5-1%
- Let the market prove us right (trailing stop follows)
- If wrong, exit cleanly and wait for next signal
- **Multiple small losses < One large loss**

### Exit Scenarios

**Good Exit** (Trailing Stop Hit After Profit):
```
Entry: $50,000
Peak: $51,500 (+3%)
Exit: $51,257 (trailing stop hit)
Profit: +2.51% ✅
```

**Acceptable Exit** (Small Loss):
```
Entry: $50,000
Exit: $49,750 (stop hit immediately)
Loss: -0.5% ✅ (Capital preserved)
```

**Bad Exit** (Should Never Happen):
```
Entry: $50,000
No stop or wide stop
Exit: $48,500 (panic sell)
Loss: -3% ❌ (Account damage)
```

### Configuration Values

**Ultra-Short Scalping Stop Loss**:
- Initial stop: 0.2-0.3% (at demand/supply zone boundary)
- Trailing stop: 0.5% distance
- Target: 0.5-1.0% profit
- Philosophy: Quick in, quick out

**Core Principles**:
- **0.5% trailing stop** (maximum risk tolerance)
- **Exit quickly if wrong** (preserve capital)
- **Re-enter on new signal** (multiple attempts OK)
- **Capital preservation > being right** (ego-free trading)

---

## 2.6 🎯 Dynamic Exit Strategy (No Fixed Take Profit)

**Philosophy**: We entered on order flow confirmation. We exit when order flow reverses.

### 2.6.1 NO Default Take Profit Target

**Traditional (Bad) Approach**:
```
Enter at $50,000
Fixed take profit: +2% ($51,000)
Price hits $51,000 → Exit

Problem: What if order flow is still bullish?
Price continues to $52,000 → Missed $1,000
```

**Our Approach (Dynamic)**:
```
Enter at $50,000 on bullish cascade
Monitor every 15 seconds for reversal signals
Price at $51,500 → Still bullish cascade → HOLD
Price at $52,200 → Cascade reverses → EXIT

Result: Captured +4.4% instead of +2%
```

### Real-Time Exit Monitoring (Every 2 Seconds)

**Check Frequency**: Every 2 seconds (extremely responsive)
**Lookback Window**: 15 seconds (rolling window for analysis)
**Max Detection Time**: 6 seconds (3 consecutive drops × 2-second checks)

**Monitor 3 Reversal Signals**:

#### 1. **Order Flow Cascade Reversal** 🚨 **SMOKING GUN** (Priority #1)

**This is the PRIMARY exit signal** - most reliable.

**Entry Cascade** (Long):
```
1m buy imbalance: 3.5 (heavy buying)
5m buy imbalance: 2.8 (moderate buying)
15m buy imbalance: 1.8 (mild buying)

Cascade: 3.5 > 2.8 > 1.8 ✅ (accelerating buyers - ENTER)
```

**Monitor for Reversal** (every 2 seconds, 15-second rolling window):
```python
# Recalculate imbalances continuously
current_1m = calculate_imbalance("1m", lookback=15)
current_5m = calculate_imbalance("5m", lookback=15)
current_15m = calculate_imbalance("15m", lookback=15)

if position_side == "LONG":
    # Check if cascade REVERSED (now selling accelerating)
    if (
        current_1m < 0.5              # Heavy selling (< 0.5 = 2:1 sell)
        and current_1m < current_5m   # 1m worse than 5m
        and current_5m < current_15m  # 5m worse than 15m
    ):
        # 🚨 CASCADE REVERSED - Institutions selling aggressively
        exit_position("Order flow cascade reversed - SMOKING GUN")
```

**Example**:
```
Entry Cascade (Long):
1m: 3.5, 5m: 2.8, 15m: 1.8 → ENTER at $50,000

+10 seconds: 1m: 3.2, 5m: 2.7, 15m: 1.9 → HOLD (still bullish)
+20 seconds: 1m: 2.8, 5m: 2.5, 15m: 1.8 → HOLD (still bullish)
+30 seconds: 1m: 0.4, 5m: 0.6, 15m: 0.9 → EXIT IMMEDIATELY
Cascade reversed: 0.4 < 0.6 < 0.9 (accelerating sellers)

Exit at $51,800 → +3.6% profit
Detection time: 30 seconds from entry
```

---

### 2.6.2 Consecutive Price Drops (Priority #2)

**CRITICAL**: We monitor **price direction**, NOT trade sides (buy/sell).

**Why This Matters**:
```
Wrong Approach (Trade Sides):
Tick 1: SELL at $50,300
Tick 2: SELL at $50,305  ← Price going UP
Tick 3: SELL at $50,310  ← Price still going UP

3 consecutive SELL ticks, but price RISING!
❌ Wrong signal - should NOT exit

Correct Approach (Price Drops):
Tick 1: $50,300
Tick 2: $50,295  ← Price DROPPED
Tick 3: $50,290  ← Price DROPPED again
Tick 4: $50,285  ← Price DROPPED again

3 consecutive price drops = momentum reversing
✅ Correct signal - EXIT NOW
```

**Implementation**:
```python
async def count_consecutive_price_drops(position: Position) -> int:
    """
    Count consecutive price moves AGAINST our position
    Checked every 2 seconds, 15-second rolling window
    """

    # Get recent ticks (15-second window)
    ticks = await get_recent_ticks(symbol, lookback_seconds=15)

    consecutive = 0

    # Check from most recent backwards
    for i in range(len(ticks) - 1):
        current = ticks[-(i+1)]      # Most recent
        previous = ticks[-(i+2)]     # One before

        if position.side == "LONG":
            # For LONG: check if price is DROPPING
            if current.price < previous.price:
                consecutive += 1
            else:
                break  # Streak broken

        else:  # SHORT
            # For SHORT: check if price is RISING
            if current.price > previous.price:
                consecutive += 1
            else:
                break  # Streak broken

    return consecutive

# Exit logic
consecutive_drops = await count_consecutive_price_drops(position)
threshold = get_threshold_by_profit(position.profit_pct)

if consecutive_drops >= threshold:
    exit_position(f"{consecutive_drops} consecutive price drops")
```

**Profit-Based Thresholds**:
```python
def get_threshold_by_profit(profit_pct: float) -> int:
    """
    More profit = more aggressive exit protection
    """

    if profit_pct < 0.3:
        return 5  # Be patient - small/no profit yet
    elif profit_pct < 1.0:
        return 3  # Moderate - decent profit, protect it
    elif profit_pct < 2.0:
        return 2  # Aggressive - good profit, exit quickly
    else:
        return 1  # Very aggressive - excellent profit, take it NOW
```

**Visual Example** (LONG Position):
```
Time    Price     Change      Consecutive    Profit%   Threshold   Action
---------------------------------------------------------------------------
+0s     $50,000   (entry)            0        0.00%       5        ENTER
+2s     $50,020   +$20               0        0.04%       5        HOLD
+4s     $50,080   +$60               0        0.16%       5        HOLD
+6s     $50,150   +$70               0        0.30%       3        HOLD (threshold now 3)
+8s     $50,180   +$30               0        0.36%       3        HOLD
+10s    $50,200   +$20               0        0.40%       3        HOLD
+12s    $50,195   -$5                1        0.39%       3        HOLD (1 drop, need 3)
+14s    $50,190   -$5                2        0.38%       3        HOLD (2 drops, need 3)
+16s    $50,185   -$5                3        0.37%       3        EXIT ✅

Exit: $50,185 (+0.37% profit)
Detection time: 6 seconds (3 drops × 2-second checks)
Reason: "3 consecutive price drops (threshold=3)"
```

**Why This is Superior**:
```
Scenario: Price at $50,500, profit +1.0%

Using SELL TICKS (Wrong):
+0s: SELL at $50,500
+2s: SELL at $50,510 (price going UP)
+4s: SELL at $50,520 (price going UP)
❌ 3 SELL ticks would exit at $50,520
But price continues to $50,800!

Using PRICE DROPS (Correct):
+0s: $50,500
+2s: $50,510 (UP - no drop)
+4s: $50,520 (UP - no drop)
+6s: $50,800 (UP - no drop)
+8s: $50,795 (drop #1)
+10s: $50,785 (drop #2)
✅ 2 drops, threshold=2 at +1.5% profit
Exit at $50,785 (+1.57% profit)

Captured full move, exited on real reversal
```

**Response Time**: **2-6 Seconds**
```
Check frequency: Every 2 seconds
Need: 1-5 consecutive drops (profit-based)
Max detection: 5 drops × 2 seconds = 10 seconds
Typical detection: 3 drops × 2 seconds = 6 seconds

vs Human trader:
- Notice reversal: 2-3 seconds
- Decide to exit: 1-2 seconds
- Click button: 0.5 seconds
- Order fills: 0.5-1 second
Total: 4-7 seconds (inconsistent, emotional)

Our system:
✅ Consistent 2-6 seconds
✅ No emotion
✅ No hesitation
✅ Perfect execution
```

### 2.6.3 Exit Priority (Which Signal to Act On First)

**Priority Order**:
1. 🚨 **Order Flow Cascade Reversal** (SMOKING GUN) → Exit immediately
2. ⚠️ **Consecutive Price Drops** → Exit immediately (profit-based threshold)
3. 🛡️ **Trailing Stop Hit** → Backup exit (if we miss reversal signals)

**All monitored every 2 seconds** with **15-second rolling window** for analysis.

### 2.6.4 Implementation Logic

```python
class DynamicExitMonitor:
    """
    Monitor open positions for exit signals
    Runs every 2 seconds with 15-second rolling window
    """

    def __init__(self):
        self.check_interval = 2  # seconds
        self.lookback_window = 15  # seconds

    async def monitor_position(self, position: Position):
        """
        Monitor position for exit signals
        Called every 2 seconds
        """

        while position.is_open:
            await asyncio.sleep(self.check_interval)

            # --- PRIORITY 1: Order Flow Cascade Reversal (SMOKING GUN) ---
            cascade_reversed = await self.check_cascade_reversal(position)
            if cascade_reversed:
                await self.exit_position(
                    position,
                    reason="Order flow cascade reversed (15-sec window)",
                    priority="CRITICAL"
                )
                return

            # --- PRIORITY 2: Consecutive Price Drops ---
            consecutive_drops = await self.count_consecutive_price_drops(position)
            profit_pct = position.calculate_profit_pct()
            threshold = self.get_threshold_by_profit(profit_pct)

            if consecutive_drops >= threshold:
                await self.exit_position(
                    position,
                    reason=f"{consecutive_drops} consecutive price drops (threshold={threshold})",
                    priority="HIGH"
                )
                return

            # --- PRIORITY 3: Trailing Stop (Backup) ---
            # Handled by PositionMonitor separately

    async def check_cascade_reversal(self, position: Position) -> bool:
        """
        Check if order flow cascade has reversed
        15-second rolling window
        THIS IS THE SMOKING GUN
        """
        imbalance_1m = await calculate_imbalance("1m", lookback=15)
        imbalance_5m = await calculate_imbalance("5m", lookback=15)
        imbalance_15m = await calculate_imbalance("15m", lookback=15)

        if position.side == "LONG":
            # Check if selling is now accelerating
            reversed = (
                imbalance_1m < 0.5  # Heavy selling
                and imbalance_1m < imbalance_5m
                and imbalance_5m < imbalance_15m
            )
        else:  # SHORT
            # Check if buying is now accelerating
            reversed = (
                imbalance_1m > 2.0  # Heavy buying
                and imbalance_1m > imbalance_5m
                and imbalance_5m > imbalance_15m
            )

        return reversed

    async def count_consecutive_price_drops(self, position: Position) -> int:
        """
        Count consecutive price moves AGAINST our position
        Uses PRICE DIRECTION, not trade sides
        15-second rolling window
        """

        # Get recent ticks (15-second window)
        ticks = await self.get_recent_ticks(
            symbol=position.symbol,
            lookback_seconds=self.lookback_window
        )

        if len(ticks) < 2:
            return 0

        consecutive = 0

        # Check from most recent backwards
        for i in range(len(ticks) - 1):
            current = ticks[-(i+1)]      # Most recent
            previous = ticks[-(i+2)]     # One before

            # Check if price moved against us
            adverse_move = False

            if position.side == "LONG":
                # For LONG: price DROPPING
                adverse_move = (current.price < previous.price)
            else:  # SHORT
                # For SHORT: price RISING
                adverse_move = (current.price > previous.price)

            if adverse_move:
                consecutive += 1
            else:
                break  # Streak broken

        return consecutive

    def get_threshold_by_profit(self, profit_pct: float) -> int:
        """
        Profit-based exit threshold
        More profit = more aggressive protection
        """

        if profit_pct < 0.3:
            return 5  # Be patient - small/no profit
        elif profit_pct < 1.0:
            return 3  # Moderate - decent profit
        elif profit_pct < 2.0:
            return 2  # Aggressive - good profit
        else:
            return 1  # Very aggressive - excellent profit
```

### Why This is Superior

**Fixed Take Profit (Bad)**:
```
Entry: $50,000
Target: +2% = $51,000
Exit: $51,000

Max profit: +2% (capped)
Missed: Potential +5% run
```

**Dynamic Exit (Good)**:
```
Entry: $50,000
Monitor: Every 15 seconds for reversal
Cascade still bullish at $51,500 → HOLD
Cascade reverses at $52,300 → EXIT

Profit: +4.6% (captured the entire move)
Protected: Exited before reversal completed
```

### Trailing Stop as Backup

**Trailing stop is still active** as a backup safety net:
- If we miss reversal signals (system glitch)
- If sudden price crash (no time for 15-sec check)
- If gap down/up (overnight moves)

**But primary exit = reversal signals**, not trailing stop.

### Exit Timing Comparison

**Scenario**: BTC long from $50,000

| Exit Method | Exit Price | Profit | Detection Time | Notes |
|-------------|-----------|--------|----------------|-------|
| Fixed TP (+2%) | $51,000 | +2% | Instant | Missed rest of move |
| Trailing Stop (0.5%) | $51,257 | +2.51% | Variable | Good, but gave back some |
| **Price Drops (3 consecutive)** | **$51,200** | **+2.4%** | **6 seconds** | **Fast exit on pullback** |
| **Cascade Reversal** | **$52,300** | **+4.6%** | **2-30 seconds** | **Optimal - full move captured** |
| Too Late (panic) | $51,500 | +3% | 10+ seconds | Emotional, gave back $800 |

**Best Strategy**:
- **Cascade reversal** = Optimal exit (captures full institutional move)
- **Price drops** = Fast exit on pullbacks (can re-enter on next signal)
- Both monitored every 2 seconds with 15-second rolling window

---

## 2.7 Complete Strategy & Market Flow Diagrams

### 2.7.1 🎯 PRIMARY STRATEGY: Order Flow Scalping (CEX & Forex)

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│  SCANNER: Monitor 100+ Trading Pairs (CEX Spot/Futures, DEX, Perp DEX, Forex)    │
│  Data: Realtime WebSocket → Ticks → DuckDB → Analytics (15min)                   │
└────────────────────────────┬──────────────────────────────────────────────────────┘
                             │
         ┌───────────────────┼────────────────────────┐
         │                   │                        │
    ┌────▼─────┐        ┌────▼─────┐           ┌─────▼──────┐
    │ CEX      │        │ DEX      │           │ FOREX      │
    │ Spot &   │        │ Spot &   │           │ Spot &     │
    │ Futures  │        │ Perps    │           │ Futures    │
    └────┬─────┘        └────┬─────┘           └─────┬──────┘
         │                   │                        │
    ┌────┴─────┐        ┌────┴─────┐           ┌─────┴──────┐
    │          │        │          │           │            │
  ┌─▼─┐      ┌─▼─┐    ┌─▼─┐      ┌─▼─┐       ┌─▼─┐      ┌─▼─┐
  │BIN│      │BIN│    │Uni│      │Hyp│       │MT5│      │MT5│
  │NCE│      │NCE│    │swp│      │Liq│       │FX │      │FX │
  │SPT│      │FUT│    │Ray│      │GMX│       │SPT│      │FUT│
  └─┬─┘      └─┬─┘    │dim│      │dYdX│      └─┬─┘      └─┬─┘
    │          │      └─┬─┘      │Aster│       │          │
    │          │        │        └─┬─┘         │          │
    │          │        │   (Pre-filtered:     │          │
    │          │        │   Vol spike + Rug)   │          │
    └──────────┴────────┴──────────┴───────────┴──────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ LEVEL 1: TREND       │ ⚡ SHORT-CIRCUIT #1
                  │ ✓ Higher highs/lows? │ (Rejects ~60% of pairs)
                  │ ✓ ADX > 25?          │
                  │ ✓ Dir persist >0.55? │
                  │ ✓ Mean revert <0.6?  │
                  └──────────┬───────────┘
                             │
                      ┌──────┴──────┐
                      │             │
                 RANGING 📉     TRENDING 📈
                      │             │
                      ▼             ▼
                   ❌ SKIP      ✅ CONTINUE
                   (Next)       │
                                ▼
                     ┌─────────────────────┐
                     │ Direction Filter:   │
                     │ • UP → LONG only    │
                     │ • DOWN → SHORT only │
                     │ (No counter-trend)  │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌──────────────────────────┐
                     │ LEVEL 2: ZONE CHECK      │ ⚡ SHORT-CIRCUIT #2
                     │ • Market Profile (15min) │ (Rejects ~25% more)
                     │ • At VAH/VAL?            │
                     │ • Supply/Demand zone?    │
                     │ • Fresh zone preferred   │
                     └──────────┬───────────────┘
                                │
                        ┌───────┴────────┐
                        │                │
                   NOT AT ZONE       AT ZONE ✅
                        │                │
                        ▼                ▼
                     ❌ WAIT         ✅ CONTINUE
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │ LEVEL 3: CASCADE     │ ⚡ SHORT-CIRCUIT #3
                              │ Order Flow Alignment │ (Rejects ~10% more)
                              │ • 1M imbalance >2.5? │
                              │ • 5M imbalance >2.5? │
                              │ • 15M imbalance >2.5?│
                              │ ALL must agree! ✓✓✓  │
                              └──────────┬───────────┘
                                         │
                                 ┌───────┴────────┐
                                 │                │
                          NO CASCADE        CASCADE OK ✅
                                 │                │
                                 ▼                ▼
                              ❌ WAIT         ✅ CONTINUE
                                                  │
                                                  ▼
                                       ┌─────────────────────┐
                                       │ LEVEL 4: TRIGGER    │ ⚡ ENTRY SIGNAL
                                       │ Microstructure:     │ (Final 5%)
                                       │ • Rejection wick?   │
                                       │ • Bid-ask bounce?   │
                                       │ • Volume spike 2x?  │
                                       │ • Close near high?  │
                                       └──────────┬──────────┘
                                                  │
                                          ┌───────┴────────┐
                                          │                │
                                    NO TRIGGER      TRIGGER + VOL ✅
                                          │                │
                                          ▼                ▼
                                       ❌ WAIT       ✅ EXECUTE
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │ POSITION ENTERED     │
                                              │ • 0.5% trail stop    │
                                              │ • Hold til trend     │
                                              │ • No fixed TP        │
                                              │ • DEX liq watch 💎   │
                                              │   (Meme coins only)  │
                                              └────────┬─────────────┘
                                                       │
                                                       ▼
                                              ┌──────────────────────┐
                                              │ EXIT MONITORS        │
                                              │                      │
                                              │ 1. Trailing Stop Hit │
                                              │    (0.5% all markets)│
                                              │                      │
                                              │ 2. Dump Detected     │
                                              │    • Order flow flip │
                                              │    • Volume reversal │
                                              │    • Lower highs     │
                                              │                      │
                                              │ 3. DEX Liq Drop 💎   │
                                              │    • -30% liquidity  │
                                              │    (Meme coins only) │
                                              │                      │
                                              │ 4. Session Close ⏰  │
                                              │    (Forex only)      │
                                              └──────────────────────┘
```

**Filtering Efficiency**:
- Level 1 (Trend): ~60% rejected → 40 pairs remain
- Level 2 (Zones): ~25% rejected → 30 pairs remain
- Level 3 (Cascade): ~10% rejected → 27 pairs remain
- Level 4 (Trigger): Final ~5% execute → **1-3 trades/hour**

**Key Benefits**:
1. ⚡ **Fast**: Most pairs rejected in <1ms at Level 1
2. 🎯 **Precise**: Only 1-3% of scans result in trades (high quality)
3. 📊 **Data-Driven**: Pure order flow + price action (no lagging indicators)
4. 🔄 **Real-Time**: WebSocket ticks → DuckDB → Analytics (sub-second)

---

### 2.7.1.1 📊 Futures Markets Integration

The algo engine supports **ALL types of futures markets** using the SAME decision engine:

#### **1. CEX Perpetual Futures (Centralized)**

**Binance Futures (Primary)**:
- **USDT-Margined Perpetuals**: BTC/USDT, ETH/USDT, SOL/USDT, etc.
- **Leverage**: Up to 125x (we use max 5-10x for risk management)
- **Funding Rate**: 8-hour settlements (±2% cap)
- **Fees**: Maker 0.02%, Taker 0.04%
- **Volume**: $60B+ daily (highest liquidity)
- **API**: WebSocket for realtime ticks, REST for orders
- **Why**: Highest liquidity, tightest spreads, best for scalping

**Bybit Futures (Secondary)**:
- **USDT Perpetuals**: Similar to Binance
- **Leverage**: Up to 100x
- **Fees**: Maker 0.01%, Taker 0.06%
- **Volume**: $15B+ daily
- **Why**: Backup exchange, arbitrage opportunities

**Key Advantages**:
- ✅ Deep liquidity (large orders don't move price)
- ✅ Tight spreads (0.01-0.05%)
- ✅ Fast execution (<50ms)
- ✅ Funding rate arbitrage opportunities
- ⚠️ Centralized (custody risk)

#### **2. Decentralized Perpetual Futures (On-Chain)**

**Hyperliquid** (Leader - 55% market share):
- **Network**: L1 blockchain (custom)
- **Leverage**: Up to 50x
- **Liquidity**: $100M+ daily volume
- **Fees**: 0.02% taker, 0% maker (negative rebates)
- **Settlement**: On-chain, instant
- **Why**: Best decentralized liquidity, lowest fees, no custody risk
- **2024 Growth**: 25.3x volume increase

**GMX** (Arbitrum/Avalanche):
- **Network**: Arbitrum (Layer 2)
- **Leverage**: Up to 50x
- **Model**: GLP pool (traders vs. liquidity pool)
- **Fees**: 0.1% open/close
- **Volume**: $100M+ daily
- **Why**: Real-yield for LPs, established protocol

**dYdX** (v4 - Cosmos Chain):
- **Network**: dYdX Chain (Cosmos app-chain)
- **Leverage**: Up to 20x
- **Liquidity**: $500B+ total 2024 volume
- **Fees**: 0.02% maker, 0.05% taker
- **Why**: Most institutional, highest TVL historically
- **Issue**: Lost market share in 2024 (73% → 7%)

**Aster DEX** (Trust Wallet Integration):
- **Networks**: BSC, Ethereum, Arbitrum, Solana
- **Leverage**: Up to 100x
- **Integration**: Built into Trust Wallet
- **Why**: Self-custody, multi-chain
- **Launch**: Late 2024
- **Geographic**: Restricted in US/UK

**Key Advantages**:
- ✅ Non-custodial (you own the keys)
- ✅ No KYC required
- ✅ Censorship-resistant
- ✅ Transparent on-chain settlement
- ⚠️ Lower liquidity than CEX
- ⚠️ Higher slippage on large orders
- ⚠️ Gas fees (L1) or bridge costs

#### **3. Forex Futures (Currency Futures)**

**MetaTrader 5 Futures**:
- **Instruments**: EUR/USD, GBP/USD, USD/JPY futures
- **Leverage**: Up to 500x (we use max 50x)
- **Settlement**: Monthly or quarterly expiry
- **Volume**: Lower than spot forex
- **Fees**: Spread + overnight swap
- **Why**: Access to institutional forex futures markets

**CME Currency Futures** (via MT5 brokers):
- **Contracts**: E-mini EUR, GBP, JPY, etc.
- **Leverage**: Regulated (typically 50:1)
- **Settlement**: Physical or cash-settled
- **Why**: Institutional-grade, regulated

**Key Advantages**:
- ✅ Regulated markets
- ✅ High leverage (use cautiously)
- ✅ Tight spreads on majors
- ⚠️ Expiry dates (must roll positions)
- ⚠️ Weekend gaps

#### **4. Futures Strategy Comparison**

| Feature | CEX Perps | Decentralized Perps | Forex Futures |
|---------|-----------|---------------------|---------------|
| **Custody** | Centralized | Self-custody | Centralized |
| **Liquidity** | Highest | Medium | High |
| **Leverage** | 125x | 50-100x | 500x |
| **Fees** | 0.02-0.04% | 0.02-0.1% | Spread |
| **KYC** | Required | Optional | Required |
| **Expiry** | None (perpetual) | None | Monthly/Quarterly |
| **24/7 Trading** | Yes | Yes | No (weekends closed) |
| **Slippage** | Low | Medium | Low |
| **Our Use** | Primary | Meme coins + arb | Forex pairs |

#### **5. Futures-Specific Considerations**

**Funding Rate Management**:
```python
# Monitor funding rates for arbitrage
if binance_funding_rate > 0.05%:  # Paying longs expensive
    # Consider shorting on Binance, longing on dYdX
    execute_funding_arbitrage()
```

**Leverage Strategy**:
- **Regular Trading**: 3-5x leverage (conservative)
- **High Conviction**: 10x leverage (rare)
- **Never**: >10x leverage (our hard limit)
- **Reason**: 0.5% trailing stop + leverage = manageable risk

**Position Sizing with Leverage**:
```python
# Example: 2% account risk, 5x leverage
account_size = $10,000
risk_per_trade = 2% = $200
leverage = 5x
position_size = $200 / (0.005 * 5) = $8,000 notional
# If stop hit: $8,000 * 0.005 * 5 = $200 loss ✓
```

**Liquidation Prevention**:
- Always maintain 50%+ margin buffer
- If margin < 30%, reduce position size
- Never hold through high volatility events with leverage

#### **6. Market Selection Logic**

**When to Use Each Market**:

```python
# CEX Futures (Binance/Bybit)
if (
    pair in ["BTC/USDT", "ETH/USDT", "SOL/USDT"] and  # Major pairs
    required_liquidity > $100k and                     # Large orders
    need_tight_spread and                              # Low slippage
    okay_with_centralized                              # Accept custody risk
):
    use_binance_futures()

# Decentralized Perps (Hyperliquid/GMX/dYdX)
if (
    want_self_custody and                              # No custody risk
    okay_with_higher_fees and                          # 0.05-0.1% fees
    pair_has_liquidity_on_dex and                      # Check TVL
    (trading_meme_coin or avoiding_kyc)                # Use cases
):
    use_hyperliquid() or use_gmx()

# Forex Futures (MT5)
if (
    pair in ["EUR/USD", "GBP/USD", "USD/JPY"] and     # Currency pairs
    trading_during_session and                         # No weekend risk
    need_high_leverage and                             # 50-100x
    regulated_market_preferred                         # Compliance
):
    use_mt5_futures()
```

**Integration in Scanner**:
- All futures markets feed into SAME 4-level decision engine
- Pre-filtering happens at data ingestion (filter by liquidity, spread)
- Analytics work identically (order flow, market profile, zones)
- Exit logic: Same 0.5% trailing stop + dump detection
- Special handling: Funding rate monitoring (CEX), gas cost management (DEX), session close (Forex)

---

---

### 2.7.2 💎 MEME COIN STRATEGY: Same Engine + Pre-Filters + Special Exit

```
┌─────────────────────────────────────────────────────────────────┐
│  SCANNER: Monitor DEX Pairs (Raydium, Uniswap, PancakeSwap)    │
│  Data: On-Chain → Mempool Monitor → Volume Spike Detector      │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
    ┌────▼────┐                            ┌────▼────┐
    │ SOLANA  │                            │   EVM   │
    │ (Raydium│                            │(Uniswap)│
    └────┬────┘                            └────┬────┘
         │                                       │
         └───────────────────┬───────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ PRE-FILTER 1: VOLUME SPIKE   │ 🔍 MEME-SPECIFIC
              │ • 5x avg volume?             │ (Rejects ~80%)
              │ • New DEX listing?           │
              │ • Social buzz (Twitter)?     │
              └──────────┬───────────────────┘
                         │
                  ┌──────┴──────┐
                  │             │
              NO SPIKE      SPIKE ✅
                  │             │
                  ▼             ▼
               ❌ SKIP      ✅ CONTINUE
                                │
                                ▼
                     ┌──────────────────────┐
                     │ PRE-FILTER 2: RUG    │ 🔍 MEME-SPECIFIC
                     │ • Liquidity locked?  │ (Rejects ~50% more)
                     │ • Contract verified? │
                     │ • Honeypot test OK?  │
                     │ • Whale <5%?         │
                     └──────────┬───────────┘
                                │
                        ┌───────┴────────┐
                        │                │
                  FAILED RUG      PASSED ✅
                        │                │
                        ▼                ▼
                     ❌ SKIP         ✅ CONTINUE
                                         │
                                         ▼
            ┌────────────────────────────────────────────────┐
            │ NOW ENTERS SAME 4-LEVEL DECISION ENGINE        │
            │ (Identical to regular CEX/Forex trading)       │
            └────────────────────────┬───────────────────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ LEVEL 1: TREND       │ ⚡ SHORT-CIRCUIT #1
                          │ ✓ Higher highs/lows? │ (Same as CEX)
                          │ ✓ ADX > 25?          │
                          │ ✓ Dir persist >0.55? │
                          └──────────┬───────────┘
                                     │
                              ┌──────┴──────┐
                              │             │
                         RANGING 📉     TRENDING 📈
                              │             │
                              ▼             ▼
                           ❌ SKIP      ✅ CONTINUE
                                            │
                                            ▼
                                 ┌──────────────────────────┐
                                 │ LEVEL 2: ZONE CHECK      │ ⚡ SHORT-CIRCUIT #2
                                 │ • Market Profile (15min) │ (Same as CEX)
                                 │ • At VAH/VAL?            │
                                 │ • Supply/Demand zone?    │
                                 └──────────┬───────────────┘
                                            │
                                    ┌───────┴────────┐
                                    │                │
                               NOT AT ZONE       AT ZONE ✅
                                    │                │
                                    ▼                ▼
                                 ❌ WAIT         ✅ CONTINUE
                                                     │
                                                     ▼
                                          ┌──────────────────────┐
                                          │ LEVEL 3: CASCADE     │ ⚡ SHORT-CIRCUIT #3
                                          │ Order Flow Alignment │ (Same as CEX)
                                          │ • 1M imbalance >2.5? │
                                          │ • 5M imbalance >2.5? │
                                          │ • 15M imbalance >2.5?│
                                          └──────────┬───────────┘
                                                     │
                                             ┌───────┴────────┐
                                             │                │
                                      NO CASCADE        CASCADE OK ✅
                                             │                │
                                             ▼                ▼
                                          ❌ WAIT         ✅ CONTINUE
                                                              │
                                                              ▼
                                                   ┌─────────────────────┐
                                                   │ LEVEL 4: TRIGGER    │ ⚡ ENTRY SIGNAL
                                                   │ Microstructure:     │ (Same as CEX)
                                                   │ • Rejection wick?   │
                                                   │ • Bid-ask bounce?   │
                                                   │ • Volume spike 2x?  │
                                                   └──────────┬──────────┘
                                                              │
                                                      ┌───────┴────────┐
                                                      │                │
                                                NO TRIGGER      TRIGGER ✅
                                                      │                │
                                                      ▼                ▼
                                                   ❌ WAIT       ✅ EXECUTE
                                                                     │
                                                                     ▼
                                                          ┌──────────────────┐
                                                          │ POSITION ENTERED │
                                                          │ • 0.5% trail     │ SAME as CEX
                                                          │ • Hold til trend │ NO time limit
                                                          │ • No fixed TP    │
                                                          └────────┬─────────┘
                                                                   │
                                                                   ▼
                                                          ┌──────────────────┐
                                                          │ LIQUIDITY WATCH  │ 🔍 MEME-SPECIFIC
                                                          │ • DEX liq -30%?  │ (Rug detection)
                                                          │ → EXIT IMMEDIATE │
                                                          └────────┬─────────┘
                                                                   │
                                                                   ▼
                                                          ┌──────────────────┐
                                                          │ DUMP DETECTOR    │ (Same as CEX)
                                                          │ Portfolio Monitor│
                                                          │ • Order flow flip│
                                                          │ • Volume reversal│
                                                          └──────────────────┘
```

**Meme Coin Strategy = Same Engine + Special Handling**:

**🔍 PRE-FILTERS (Before Decision Engine)**:
1. Volume spike detection (5x avg volume, new listing, social buzz)
2. Rug check (liquidity locked, contract verified, honeypot test, whale <5%)

**✅ DECISION ENGINE (Identical to CEX/Forex)**:
- Level 1: Trend Filter (higher highs/lows, ADX >25, directional persistence)
- Level 2: Zone Check (market profile, supply/demand zones)
- Level 3: Cascade (order flow imbalance across all timeframes)
- Level 4: Trigger (microstructure, rejection wick, volume spike)

**⚠️ POST-ENTRY (Meme-Specific Handling)**:
- **Same 0.5% Trailing Stop**: Meme coins trend hard → reverse = exit immediately (catching knife)
- **No Time Limit**: Hold as long as trend continues (same as all strategies)
- **Liquidity Monitor**: Exit if DEX liquidity drops >30% (rug pull early warning)
- **Same Dump Detector**: Order flow flip + volume reversal (like all positions)

**Why 0.5% for Meme Coins Too?**
- Meme coins trend in ONE direction when momentum is strong
- If reversing → you're catching a falling knife → exit IMMEDIATELY
- Wide stops (15-20%) would let winners turn into losers
- Our edge = order flow + momentum, not "hope it comes back"

---

### 2.7.3 ⚡ ARBITRAGE STRATEGY: Cross-Exchange Price Differences

```
┌──────────────────────────────────────────────────────────────────┐
│  PRICE MONITOR: Compare BTC/ETH/SOL across 3+ exchanges         │
│  Binance | Bybit | Hyperliquid | Jupiter | 1inch                │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
                  ┌──────────────────────────┐
                  │ LEVEL 1: PRICE GAP       │
                  │ Exchange A vs Exchange B │
                  │ • Gap > 0.5% (fees)?     │
                  │ • Same asset pair?       │
                  │ • Both liquid?           │
                  └──────────┬───────────────┘
                             │
                      ┌──────┴──────┐
                      │             │
                  GAP <0.5%     GAP >=0.5% ✅
                      │             │
                      ▼             ▼
                   ❌ SKIP      ✅ CONTINUE
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ LEVEL 2: FEASIBILITY │
                         │ • Withdraw available?│
                         │ • Bridge time <30min?│
                         │ • Gas fees viable?   │
                         │ • Net profit >1%?    │
                         └──────────┬───────────┘
                                    │
                            ┌───────┴────────┐
                            │                │
                      NOT FEASIBLE      FEASIBLE ✅
                            │                │
                            ▼                ▼
                         ❌ SKIP         ✅ CONTINUE
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ LEVEL 3: EXECUTION   │
                                  │ Simultaneous:        │
                                  │ 1. BUY on Exchange A │
                                  │ 2. SELL on Exchange B│
                                  │ (Lock in spread)     │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ LEVEL 4: SETTLEMENT  │
                                  │ • Transfer funds     │
                                  │ • Rebalance accounts │
                                  │ • Net profit calc    │
                                  └──────────────────────┘
```

**Arbitrage Types**:
1. **CEX ↔ CEX**: Binance → Bybit (fast, low fees)
2. **DEX ↔ CEX**: Uniswap → Binance (bridge time 2-30 min)
3. **DEX ↔ DEX**: Ethereum DEX → Solana DEX (cross-chain)
4. **Flashloan Arb**: Borrow → Buy → Sell → Repay (single TX, no capital)

---

### 2.7.4 🌍 COMPLETE SYSTEM: All Strategies & Markets

```
┌──────────────────────────────────────────────────────────────────┐
│                   ALGO ENGINE - MASTER CONTROLLER                │
│          Event Bus (24/7) → All Strategies Subscribe             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ CEX MARKETS     │ │ DEX MARKETS     │ │ FOREX MARKETS   │
│                 │ │                 │ │                 │
│ • Binance Spot  │ │ • Ethereum      │ │ • MT5 (IC Mkts) │
│ • Binance Fut   │ │ • Solana        │ │ • cTrader       │
│ • Bybit Spot    │ │ • BSC           │ │ • TradeLocker   │
│ • Hyperliquid   │ │ • Polygon       │ │ • MatchTrader   │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ STRATEGY 1:     │ │ STRATEGY 2:     │ │ STRATEGY 3:     │
│ Order Flow      │ │ Meme Coin       │ │ Arbitrage       │
│ Scalping        │ │ Hunter          │ │ Cross-Exchange  │
│                 │ │                 │ │                 │
│ Markets:        │ │ Markets:        │ │ Markets:        │
│ • CEX (all)     │ │ • DEX (all)     │ │ • CEX + DEX     │
│ • Forex (all)   │ │ • CEX (new)     │ │ • Cross-chain   │
│                 │ │                 │ │                 │
│ Exit: 0.5% stop │ │ Exit: 0.5% stop │ │ Hold: Instant   │
│ Hold: Til trend │ │ + Liq monitor   │ │ Stop: N/A       │
└─────────────────┘ └─────────────────┘ └─────────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                  ┌──────────────────────────┐
                  │ PORTFOLIO RISK MANAGER   │
                  │ (Monitors ALL positions) │
                  │                          │
                  │ • Dump Detector          │
                  │ • Correlation Monitor    │
                  │ • Health Score           │
                  │ • Circuit Breaker        │
                  │ • Max Hold Enforcer      │
                  └──────────┬───────────────┘
                             │
                             ▼
                  ┌──────────────────────────┐
                  │ NOTIFICATION SYSTEM      │
                  │ SendGrid Email Alerts    │
                  │                          │
                  │ 🔴 Critical: Immediate   │
                  │ 🟡 Warning: Batched      │
                  │ 🟢 Info: Daily digest    │
                  └──────────────────────────┘
```

**System Capabilities**:
- 🌐 **Multi-Market**: CEX, DEX, Forex, Commodities
- 🎯 **Multi-Strategy**: Scalping, Meme Coins, Arbitrage
- ⚡ **Real-Time**: WebSocket → DuckDB → Decision (<1s)
- 🛡️ **Risk Management**: Portfolio-wide monitoring
- 📧 **Notifications**: Critical alerts via email

---

**Key Design Principles**:
1. ⚡ **Speed**: Short-circuit filtering rejects 95% of pairs in <1ms
2. 🎯 **Quality**: Only highest-probability setups executed
3. 📊 **Data-Driven**: Order flow + price action (no EMAs)
4. 🔄 **Adaptive**: Different stops/holds per strategy
5. 🛡️ **Protected**: Portfolio-wide dump detection

**Real-Time Analytics Components**:

**PRIMARY ANALYZERS** (Generate Entry Signals):

1. **Order Flow Analyzer** ⭐ (PRIMARY SIGNAL #1)
   - **Lookback Window**: Last **30 seconds** of trades
   - **Calculation Frequency**: Every 5 seconds (real-time)
   - **Buy/Sell Imbalance Ratio**: `buy_volume / sell_volume` from aggressor side
   - **Threshold**: >2.5:1 ratio (stricter for ultra-short timeframe)
   - **Minimum Volume**: At least 5 trades in window (prevent false signals on low volume)
   - **Cumulative Volume Delta (CVD)**: Running sum over last **15 minutes**
   - **Large Trade Detection**: Trades >10x average size in last 5 minutes
   - **Exhaustion Detection**: When aggressive volume suddenly drops <50% of 5-min average
   - **Signal**: Imbalance ratio exceeds threshold = entry trigger

2. **Microstructure Analyzer** ⭐ (PRIMARY SIGNAL #2)
   - **Price Rejection Patterns**: Large wicks, pin bars at key levels
   - **Absorption Analysis**: Does price bounce or breakthrough?
   - **Speed of Movement**: Rapid moves vs slow grinding
   - **Candle Close Strength**: Close near high/low indicates conviction
   - **Signal**: Strong rejection + volume confirmation = entry trigger

**SECONDARY ANALYZERS** (Confirmation Filters):

3. **Market Profile Analyzer** (FILTER #1)
   - **Lookback Window**: Last **15 minutes** of tick data
   - **Recalculation Frequency**: Every 5 minutes
   - **Value Area High/Low**: Price levels containing 70% of volume traded in window
   - **Point of Control (POC)**: Highest volume price level (acts as magnet)
   - **Trading Location**:
     - At Value Area Low = support expected (bullish)
     - At Value Area High = resistance expected (bearish)
     - Inside Value Area = neutral
   - **Filter**: Trading at value area extremes = higher probability trades

4. **Mean Reversion Calculator** (FILTER #2)
   - **Distance from Recent Mean**: Current price vs mean price from last 15 minutes of ticks
     - Calculation: `mean = avg(last 15 min tick prices)`
     - Deviation: `deviation = (current_price - mean) / std_dev`
   - **Standard Deviation Bands**: 2σ bands calculated on same 15-min window
     - Beyond +2σ = overbought (potential short/exit)
     - Beyond -2σ = oversold (potential long/entry)
   - **RSI**: 14-period RSI on 1M timeframe
     - RSI > 70 = overbought
     - RSI < 30 = oversold
   - **Filter**: Price beyond ±2σ from recent mean triggers mean reversion signal

5. **Autocorrelation Detector** (FILTER #3)
   - **Metric**: Pearson correlation of log-returns
   - **Timeframe & Lookback**: Last 10 candles on **1M timeframe** (10 minutes)
   - **Calculation**: Correlation coefficient (r) of price returns
   - **Thresholds**:
     - High autocorrelation (r > 0.6): Strong trend, continuation likely
     - Low autocorrelation (-0.3 < r < 0.3): Range-bound, mean reversion
     - Negative autocorrelation (r < -0.3): Reversal pattern
   - **Filter**: High r (>0.6) = add to confluence if trend trade, Low r = add if reversion trade

6. **Supply/Demand Zone Mapper** (FILTER #4 & #5)
   - **Zone Identification**: Historical price rejection areas
   - **Fresh vs Tested**: Untested zones = stronger
   - **Volume Confirmation**: High volume at zone creation
   - **Zone Strength Score**: 0-100 based on multiple factors
   - **Filter**: Price at fresh zone + order flow agreement = strong entry

7. **Fair Value Gap Detector** (FILTER #6)
   - **3-Candle Pattern**: Gap between candle 1 and candle 3
   - **Gap Size**: Minimum 0.2% gap for significance
   - **Fill Probability**: Historical 80%+ gaps get filled
   - **Confluence**: FVG + Supply/Demand zone = high probability
   - **Filter**: Price approaching unfilled FVG = reversal likely

8. **Multi-Timeframe Synchronizer**
   - **Timeframe Alignment**: Check 1M, 5M, 15M all agree
   - **Trend Direction**: Higher TF determines bias, lower TF for entry
   - **Divergence Detection**: Conflicting timeframes = avoid trade
   - **Weight Scoring**: More timeframes aligned = higher score

**Strategy Modules** (Pluggable Architecture):
1. **Order Flow Scalping (Primary Strategy)**
   - Exploit order flow imbalances and CVD divergences
   - Enter on aggressive buying/selling exhaustion
   - Target fair value gaps and liquidity zones

2. **Supply/Demand Zone Bounce**
   - Enter at fresh demand zones with order flow confirmation
   - Exit at supply zones or target FVGs
   - Multi-timeframe zone validation

3. **Bid-Ask Bounce (Market Making)**
   - High-frequency market-making within spread
   - Use order flow to predict short-term price movement

4. **Market Quality-Based Trading**
   - Only trade high-quality markets with tight spreads
   - Adjust position sizes based on liquidity depth

5. **Meme Coin Hunter** 
   - Detect emerging meme coins with volume spikes
   - Social sentiment integration

6. **Flashloan Arbitrage** 
   - DEX arbitrage with flashloans
   - Cross-exchange opportunities

#### 2.2.3 Risk Management Module
**Responsibility**: Protect capital and enforce trading limits

**Key Functions**:
- **Position Size Calculator**
  - Dynamic position sizing based on volatility
  - Portfolio heat limits

- **Exposure Monitor**
  - Track total exposure across all positions
  - Correlation analysis between positions

- **Trailing Stop-Loss Engine** ⭐ (PRIMARY PROTECTION)

  **For Regular Trading (Binance Spot/Futures, Forex)**:
  - **Universal 0.5% trailing distance** on ALL positions
  - Activates immediately on position entry
  - Trails price as position moves into profit
  - Never moves backward (only follows favorable direction)
  - Calculated continuously (every tick update)
  - **Long Position**: Stop trails 0.5% below highest price reached
  - **Short Position**: Stop trails 0.5% above lowest price reached
  - Overrides initial stop-loss once position is 0.5% in profit
  - Automatically executed when price hits trailing stop

  **For All Markets (Including Meme Coins)**:
  - **Same 0.5% trailing distance** (meme coins trend hard → reverse = exit immediately)
  - If reversing, you're catching a falling knife → exit NOW
  - Risk managed via position sizing (max 2% per position)

- **Additional Stop-Loss Rules**
  - Initial stop-loss: Based on entry signal (support/demand zone, FVG)
  - Portfolio-level circuit breakers (max 5% daily drawdown)
  - Time-based position exits (max hold time per config)
  - Correlation stops (close correlated positions if one hits stop)

- **Sanity Checks**
  - Validate order prices (prevent fat-finger errors)
  - Check available balance before trading
  - Prevent duplicate orders
  - Verify stop-loss is never worse than 0.5% from entry

#### 2.2.4 Order Execution Layer
**Responsibility**: Execute trading decisions efficiently with minimal latency

**Execution Pipeline (Chain of Responsibility Pattern)** ⭐:

The system uses a chain of responsibility pattern for trade execution, where each handler performs a specific validation or action before passing to the next handler. This ensures **fail-fast** behavior and **modular validation**.

**Handler Chain (in order)**:
1. **ExistingPositionHandler**: Reject if position already exists for symbol
2. **ReversalDetectionHandler**: Close existing position if signal direction opposes it
3. **PositionLimitHandler**: Enforce max open positions limit
4. **ExposureCheckHandler**: Ensure total exposure within limits
5. **OrderPlacementHandler**: Execute the actual order on exchange
6. **PositionMonitoringHandler**: Activate trailing stop monitoring

**Flow Diagram**:
```
Trade Signal Generated
         ↓
[ExistingPositionHandler] → Already has position? → REJECT
         ↓ Pass
[ReversalDetectionHandler] → Signal opposes position? → Close position first
         ↓ Pass
[PositionLimitHandler] → Max positions reached? → REJECT
         ↓ Pass
[ExposureCheckHandler] → Exposure limit exceeded? → REJECT
         ↓ Pass
[OrderPlacementHandler] → Place order on exchange → Fill received
         ↓ Pass
[PositionMonitoringHandler] → Activate trailing stop → COMPLETE
```

**Handler Interface**:
```python
# src/trading/execution_handlers.py
from abc import ABC, abstractmethod
from typing import Optional

class ExecutionHandler(ABC):
    """Base class for execution handlers in chain of responsibility"""

    def __init__(self):
        self._next_handler: Optional[ExecutionHandler] = None

    def set_next(self, handler: 'ExecutionHandler') -> 'ExecutionHandler':
        """Set the next handler in the chain"""
        self._next_handler = handler
        return handler

    @abstractmethod
    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        """Handle the trade signal"""
        pass

    def _pass_to_next(self, trade_signal: TradeSignal) -> ExecutionResult:
        """Pass to next handler in chain"""
        if self._next_handler:
            return self._next_handler.handle(trade_signal)
        return ExecutionResult(success=True)


class ExistingPositionHandler(ExecutionHandler):
    """Check if position already exists for this symbol"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        existing_position = self.position_manager.get_position(
            trade_signal.symbol
        )

        if existing_position:
            return ExecutionResult(
                success=False,
                reason="Position already exists for this symbol"
            )

        return self._pass_to_next(trade_signal)


class ReversalDetectionHandler(ExecutionHandler):
    """Detect if signal contradicts current position"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        existing_position = self.position_manager.get_position(
            trade_signal.symbol
        )

        if existing_position:
            # Check if signal direction opposes position
            if (existing_position.side == "long" and trade_signal.side == "short") or \
               (existing_position.side == "short" and trade_signal.side == "long"):
                # Exit existing position first
                self.close_position(existing_position)

        return self._pass_to_next(trade_signal)


class PositionLimitHandler(ExecutionHandler):
    """Enforce maximum open positions limit"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        open_positions = self.position_manager.get_open_positions()

        if len(open_positions) >= self.config.max_open_positions:
            return ExecutionResult(
                success=False,
                reason=f"Max positions limit reached: {self.config.max_open_positions}"
            )

        return self._pass_to_next(trade_signal)


class ExposureCheckHandler(ExecutionHandler):
    """Ensure total exposure stays within limits"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        total_exposure = self.position_manager.get_total_exposure()
        new_exposure = total_exposure + trade_signal.position_size_usd

        if new_exposure > self.config.max_exposure_usd:
            return ExecutionResult(
                success=False,
                reason=f"Exposure limit would be exceeded: {new_exposure}"
            )

        return self._pass_to_next(trade_signal)


class OrderPlacementHandler(ExecutionHandler):
    """Place the actual order on exchange"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        try:
            order = self.exchange_client.place_order(
                symbol=trade_signal.symbol,
                side=trade_signal.side,
                quantity=trade_signal.quantity,
                order_type="market"
            )

            return ExecutionResult(
                success=True,
                order_id=order.id,
                fill_price=order.avg_price
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                reason=f"Order placement failed: {str(e)}"
            )


class PositionMonitoringHandler(ExecutionHandler):
    """Activate trailing stop monitoring after order fills"""

    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        # This is the last handler - execute order first
        result = self._pass_to_next(trade_signal)

        if result.success:
            # Activate trailing stop for new position
            self.position_monitor.activate_trailing_stop(
                symbol=trade_signal.symbol,
                entry_price=result.fill_price,
                side=trade_signal.side,
                trailing_percent=0.005  # 0.5%
            )

        return result
```

**Pipeline Setup**:
```python
# Create execution pipeline
def create_execution_pipeline():
    """Create the full execution handler chain"""

    # Create handlers
    existing_position = ExistingPositionHandler()
    reversal_detection = ReversalDetectionHandler()
    position_limit = PositionLimitHandler()
    exposure_check = ExposureCheckHandler()
    order_placement = OrderPlacementHandler()
    position_monitoring = PositionMonitoringHandler()

    # Chain them together
    existing_position.set_next(reversal_detection) \
                     .set_next(position_limit) \
                     .set_next(exposure_check) \
                     .set_next(order_placement) \
                     .set_next(position_monitoring)

    return existing_position  # Return first handler in chain


# Usage
execution_pipeline = create_execution_pipeline()

def execute_trade(trade_signal: TradeSignal):
    result = execution_pipeline.handle(trade_signal)

    if not result.success:
        logger.warning(f"Trade rejected: {result.reason}")
    else:
        logger.info(f"Trade executed: {result.order_id}")
```

**Example Rejection Scenarios**:
```
Scenario 1: Position Already Exists
Trade Signal: BUY BTCUSDT @ $50,000
         ↓
[ExistingPositionHandler] → REJECT: "Position already exists for BTCUSDT"
(Chain stops here - remaining handlers not executed)

Scenario 2: Exposure Limit
Trade Signal: BUY ETHUSDT @ $3,000
         ↓
[ExistingPositionHandler] → ✅ Pass (no position)
         ↓
[ReversalDetectionHandler] → ✅ Pass (no reversal)
         ↓
[PositionLimitHandler] → ✅ Pass (4/5 positions)
         ↓
[ExposureCheckHandler] → REJECT: "Exposure limit would be exceeded: $1,050 > $1,000"
(Chain stops here)

Scenario 3: Successful Execution
Trade Signal: BUY SOLUSDT @ $100
         ↓
[ExistingPositionHandler] → ✅ Pass
         ↓
[ReversalDetectionHandler] → ✅ Pass
         ↓
[PositionLimitHandler] → ✅ Pass
         ↓
[ExposureCheckHandler] → ✅ Pass
         ↓
[OrderPlacementHandler] → ✅ Order filled at $100.05
         ↓
[PositionMonitoringHandler] → ✅ Trailing stop activated at $99.55 (-0.5%)
(Execution complete)
```

**Benefits**:
- **Modular**: Add/remove checks without modifying other handlers
- **Clear Order**: Visual chain shows exact execution sequence
- **Fail-Fast**: Stop at first validation failure (save API calls)
- **Testable**: Test each handler in isolation
- **Auditable**: Log each handler's decision for debugging
- **Single Responsibility**: Each handler does ONE thing

---

**Other Components**:

- **Order Manager**
  - Route orders to appropriate exchanges
  - Handle order lifecycle (create, modify, cancel)
  - Track order status and fills in real-time
  - Maintain order state in Firestore

- **Exchange Connectors**
  - **CCXT**: Unified API for order execution across multiple exchanges
  - **Direct Binance API**: Fallback for Binance-specific features and lower latency
  - **WebSocket Order Updates**: Real-time order fill notifications via Cryptofeed
  - DEX smart contract interfaces (Web3)
  - Flashloan protocol integrations (Aave, dYdX)

- **Execution Optimizer**
  - Smart order routing (CCXT vs. direct API)
  - Post-only orders for maker fee rebates
  - IOC (Immediate-or-Cancel) for aggressive fills
  - TWAP/VWAP execution for large orders
  - Minimize slippage and fees

#### 2.2.5 Portfolio Risk Manager ⭐⭐⭐

**Responsibility**: Monitor ALL open positions simultaneously and execute portfolio-level exit decisions BEFORE individual trailing stops hit

**Why Critical**: Individual trailing stops protect each position, but portfolio-level dump detection protects the ENTIRE account from correlated losses and cascade failures.

**Core Philosophy**:
- **Proactive Exit**: Don't wait for trailing stops - detect dumps early and exit
- **Correlation Protection**: If BTC dumps, exit all correlated positions immediately
- **Portfolio Health**: Monitor aggregate unrealized P&L and position quality
- **Liquidity Monitoring**: Exit meme coins if DEX liquidity evaporates (rug pull early warning)
- **Circuit Breaker**: Force close all positions if daily drawdown hits limit

---

**Key Components**:

**1. Dump Detection Engine**

Detects positions showing dump signals BEFORE trailing stop hits:

```python
class DumpDetector:
    """Detect early warning signs of position dumps"""

    async def detect_position_dump(self, position) -> bool:
        """
        Early warning signals (any trigger = EXIT IMMEDIATELY):

        1. Volume Reversal (CRITICAL):
           - Sell volume > Buy volume for 3 consecutive 1M candles
           - Volume spike (3x average) with price drop >0.3%
           - Aggressive selling detected on order flow cascade

        2. Order Flow Flip (CRITICAL):
           - Order flow imbalance flips from 2.5:1 BUY to 2.5:1 SELL
           - Cascade reversal: bullish cascade → bearish cascade
           - Institutional exit pattern (large sells)

        3. Liquidity Evaporation (MEME COINS ONLY):
           - DEX liquidity drops >30% in 10 minutes
           - Aggregator quote shows >10% slippage (can't exit cleanly)
           - No bids available on current position size

        4. Momentum Breakdown:
           - Lower highs + lower lows pattern forming on 1M (3+ candles)
           - Price breaks below recent swing low with volume
           - Support zone broken with volume

        5. Resistance Rejection:
           - Price hits supply zone and gets rejected (wick >0.5%)
           - Multiple failed attempts to break resistance
           - Volume declining on each bounce attempt

        Action: EXIT ENTIRE POSITION IMMEDIATELY, don't wait for 0.5% trailing stop
        """
```

**Example - Dump Detection in Action**:
```
Position: LONG ETH @ $3,000, currently $3,020 (+0.67%)
Trailing Stop: $3,004.90 (-0.5% from highest price $3,020)

Dump Signals Detected at $3,018:
- ❌ Sell volume > Buy volume (3 consecutive 1M candles)
- ❌ Order flow flipped: 2.8:1 BUY → 2.3:1 SELL
- ❌ Lower highs forming (momentum breakdown)

Action: EXIT IMMEDIATELY at $3,018 = +0.6% profit
(Instead of waiting for trailing stop at $3,004.90 = +0.16% profit)
```

---

**2. Correlation-Based Exit System**

Monitors market leaders (BTC, ETH) and closes correlated positions on dumps:

```python
class CorrelationMonitor:
    """Monitor market leader dumps and exit correlated positions"""

    async def monitor_market_leaders(self):
        """
        Market Leaders: BTC (crypto), DXY (forex), SPY (stocks)

        BTC Dump Detection:
        - BTC drops >1.5% in 5 minutes
        - Check all open LONG positions
        - Calculate rolling 24h correlation with BTC
        - Exit positions with correlation >0.7 IMMEDIATELY

        Example:
        BTC: $50,000 → $49,250 (-1.5% in 5 min)

        Open Positions:
        - ETH LONG (correlation: 0.85) → EXIT IMMEDIATELY
        - SOL LONG (correlation: 0.72) → EXIT IMMEDIATELY
        - PEPE LONG (correlation: 0.45) → Keep (low correlation)
        - BTC SHORT (inverse exposure) → Keep (profiting from dump)
        """

    async def calculate_position_correlation(self, position, leader='BTC'):
        """
        Calculate rolling correlation:
        - Use last 1440 1M candles (24 hours)
        - Pearson correlation coefficient
        - Update every 5 minutes

        Correlation thresholds:
        - >0.7 = High correlation (exit on leader dump)
        - 0.4-0.7 = Moderate (tighten stops)
        - <0.4 = Low correlation (independent movement)
        """
```

---

**3. Portfolio Health Scoring**

Calculates real-time portfolio health score (0-100) and takes action:

```python
class PortfolioHealthMonitor:
    """Calculate portfolio health and take protective action"""

    def calculate_health_score(self) -> float:
        """
        Score: 0-100 (100 = perfect health, 0 = critical)

        Factors:
        1. Unrealized P&L (-30%):
           - Total unrealized P&L as % of account
           - -5% or worse = 0 points
           - +5% or better = 30 points

        2. Position Quality (-25%):
           - Average of individual position health
           - Volume trending up = good
           - Order flow positive = good
           - Liquidity stable = good

        3. Concentration Risk (-20%):
           - Too many positions in one sector = bad
           - Max 3 correlated positions (>0.7) = penalty
           - Diversification bonus

        4. Hold Time Distribution (-15%):
           - Positions held >30 min (scalping) = penalty
           - Meme coins held >24h = major penalty
           - Fresh positions (<5 min) = good

        5. Market Conditions (-10%):
           - VIX equivalent for crypto
           - High volatility during open positions = penalty

        Actions Based on Score:
        - Score < 30 (CRITICAL): Close worst 2 positions immediately
        - Score < 50 (WARNING): Tighten all trailing stops to 0.3%
        - Score < 70 (CAUTION): Stop opening new positions
        - Score >= 70 (HEALTHY): Normal operations
        """
```

**Example - Health Score Triggers**:
```
Portfolio State:
- 5 open positions
- Total unrealized P&L: -2.5% (BTC dumping)
- 4 positions correlated with BTC (>0.7)
- Average hold time: 18 minutes

Health Score Calculation:
- Unrealized P&L: -2.5% → 15/30 points
- Position Quality: Declining → 10/25 points
- Concentration: 4 correlated → 5/20 points
- Hold Time: 18 min avg → 12/15 points
- Market Conditions: High volatility → 5/10 points

Total Score: 47/100 (WARNING)

Action Taken: Tighten all trailing stops from 0.5% to 0.3%
```

---

**4. Daily Drawdown Circuit Breaker**

Monitors total daily P&L and triggers emergency stops:

```python
class DrawdownCircuitBreaker:
    """Prevent catastrophic daily losses"""

    async def monitor_daily_drawdown(self):
        """
        Track total P&L from session start (midnight UTC reset):

        Drawdown Levels:
        - 0-2%: Normal operations
        - 2-3%: ALERT - Log warning, notify user
        - 3-4%: WARNING - Close worst 50% of positions
        - 4-5%: CRITICAL - Close ALL positions
        - 5%+: CIRCUIT BREAKER - Close all + STOP TRADING

        Example:
        Starting Capital: $100,000
        Current Total P&L: -$4,200 (-4.2%)

        Action:
        1. Close ALL open positions immediately
        2. Emit CircuitBreakerTriggered event
        3. Notify user via email/SMS
        4. Block new position entries for rest of day
        5. Reset at midnight UTC
        """
```

---

**5. Session-Based Position Management (Forex Only)**

Forex-specific session handling:

```python
class ForexSessionManager:
    """Manage forex positions based on trading sessions"""

    async def monitor_forex_sessions(self):
        """
        Forex session rules:

        1. Close All Forex Before Session End:
           - No overnight forex positions (swap fees + weekend gaps)
           - Force close 30 min before session end (Friday 23:30 GMT)

        2. No Time Limits for Crypto/DEX:
           - Hold as long as trailing stop not hit
           - Crypto markets are 24/7 (no session closures)
           - Exit only on: trailing stop OR dump detection

        3. Arbitrage: Until convergence
           - Monitor for stuck positions
           - If >4 hours without convergence, re-evaluate

        Action: Force market close only for session-based exits (Forex Friday close)
        """
```

---

**Event-Driven Integration**:

```python
# Portfolio Risk Manager subscribes to:
event_bus.subscribe("TradeTickReceived", portfolio_risk.check_dumps)
event_bus.subscribe("CandleCompleted", portfolio_risk.update_correlations)
event_bus.subscribe("PositionOpened", portfolio_risk.add_to_monitoring)
event_bus.subscribe("PositionClosed", portfolio_risk.remove_from_monitoring)

# Portfolio Risk Manager emits:
event_bus.publish("DumpDetected")  # Position showing dump signals
event_bus.publish("PortfolioHealthDegraded")  # Health score dropped
event_bus.publish("ForceExitRequired")  # Immediate exit needed
event_bus.publish("CorrelatedDumpDetected")  # Market leader dumped
event_bus.publish("CircuitBreakerTriggered")  # Daily loss limit hit
event_bus.publish("MaxHoldTimeExceeded")  # Position held too long
```

---

**DuckDB Schema Additions**:

```sql
-- Track portfolio health over time
CREATE TABLE portfolio_health_snapshots (
    timestamp TIMESTAMP,
    total_positions INTEGER,
    total_unrealized_pnl DECIMAL(30, 6),
    health_score FLOAT,  -- 0-100
    btc_correlation_avg FLOAT,
    daily_drawdown_pct FLOAT,
    action_taken VARCHAR,  -- 'none', 'tighten_stops', 'close_worst', 'circuit_breaker'
    worst_position VARCHAR,  -- Symbol of worst performing position
    best_position VARCHAR    -- Symbol of best performing position
);

-- Track correlation matrix (updated every 5 minutes)
CREATE TABLE position_correlations (
    timestamp TIMESTAMP,
    position_symbol VARCHAR,
    leader_symbol VARCHAR,  -- 'BTC', 'ETH', 'DXY'
    correlation FLOAT,  -- -1.0 to 1.0
    rolling_window VARCHAR,  -- '24h', '7d'
    PRIMARY KEY (timestamp, position_symbol, leader_symbol)
);

-- Track dump events
CREATE TABLE dump_detections (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    dump_type VARCHAR,  -- 'volume_reversal', 'order_flow_flip', 'liquidity_evaporation', 'momentum_break'
    severity VARCHAR,  -- 'warning', 'critical'
    price_at_detection DECIMAL(30, 10),
    action_taken VARCHAR,  -- 'exit_immediate', 'tighten_stop', 'monitor'
    exit_price DECIMAL(30, 10),
    pnl DECIMAL(30, 6)
);
```

---

**Configuration** (`config/portfolio_risk.yaml`):

```yaml
portfolio_risk:
  enabled: true
  check_interval_seconds: 10  # Check portfolio health every 10 seconds

  # Daily drawdown circuit breaker
  max_daily_drawdown_pct: 5.0
  drawdown_levels:
    alert_pct: 2.0
    warning_pct: 3.0
    critical_pct: 4.0
    circuit_breaker_pct: 5.0

  # Correlation-based exits
  correlation_exit:
    enabled: true
    leaders: ['BTC', 'ETH']  # Monitor these as market leaders
    btc_dump_threshold_pct: 1.5  # Exit if BTC dumps >1.5% in 5 min
    min_correlation: 0.7  # Exit positions with >0.7 correlation
    rolling_window_hours: 24

  # Dump detection
  dump_detection:
    enabled: true
    volume_reversal:
      consecutive_candles: 3
      sell_buy_ratio: 1.5  # Sell volume > 1.5x Buy volume
    order_flow_flip:
      imbalance_threshold: 2.5  # Flip from 2.5:1 buy to 2.5:1 sell
    liquidity_drop:
      threshold_pct: 30  # DEX liquidity drops >30%
      window_minutes: 10
    momentum_break:
      lower_highs_count: 3  # 3 consecutive lower highs on 1M
      swing_low_break: true # Price breaks recent swing low

  # Portfolio health scoring
  health_score:
    enabled: true
    weights:
      unrealized_pnl: 0.30
      position_quality: 0.25
      concentration_risk: 0.20
      hold_time_distribution: 0.15
      market_conditions: 0.10
    actions:
      score_30_action: close_worst_2
      score_50_action: tighten_stops_to_0.3pct
      score_70_action: stop_new_entries

  # Maximum hold times
  max_hold_times:
    scalping_minutes: 30
    meme_coins_hours: 24
    arbitrage_hours: 4
    forex_session_based: true  # Close before session end
```

---

**Benefits**:
- ✅ **Proactive Protection**: Exit before trailing stops (preserve more profit)
- ✅ **Correlation Safety**: Don't hold 5 longs when BTC dumps -3%
- ✅ **Meme Coin Protection**: Exit if liquidity evaporates (rug pull early warning)
- ✅ **Account Protection**: Circuit breaker prevents catastrophic losses
- ✅ **Strategy Enforcement**: Force close positions held too long

**Maps to**:
- PROJECT_STRUCTURE.md: `src/position/portfolio_risk_manager.py`
- TECHNICAL_ARCHITECTURE.md: Section 8.2 (new)
- Event Bus integration: Section 2.2.0.1

---

#### 2.2.6 Mempool Monitor (Blockchain Chains Only) ⭐

**Responsibility**: Monitor pending transactions on chains with mempools for MEV protection, slippage prediction, and transaction tracking

**Why Critical**: For DEX trading on EVM chains, the mempool reveals pending large transactions BEFORE execution, allowing us to:
- **Avoid frontrunning/sandwich attacks** (MEV protection)
- **Predict slippage** from large pending orders
- **Detect rug pulls** (dev wallet dumping before announcement)
- **Monitor our own transactions** (pending → confirmed)
- **Optimize gas prices** based on mempool congestion

**Chains with Mempool Support**:
- ✅ **Ethereum** - Full mempool access via eth_subscribe
- ✅ **Base** - EVM-compatible mempool monitoring
- ✅ **Arbitrum** - L2 sequencer mempool (limited visibility)
- ✅ **Polygon** - Full mempool access
- ✅ **BSC** - Full mempool access
- ❌ **Solana** - No traditional mempool (uses leader schedule, different approach)
- ❌ **Hyperliquid** - No mempool (centralized orderbook)

---

**Core Components**:

**1. Mempool Stream Monitor**

Monitors pending transactions in real-time:

```python
class MempoolMonitor:
    """
    Monitor blockchain mempool for pending transactions
    EVM chains only (Ethereum, Base, Arbitrum, Polygon, BSC)
    """

    def __init__(
        self,
        web3_provider: Web3,
        event_bus: EventBus,
        config: Dict
    ):
        self.w3 = web3_provider
        self.event_bus = event_bus
        self.config = config['mempool']

        # Track our own pending transactions
        self.our_pending_txs: Dict[str, Dict] = {}

        # Large pending swaps (>$100k) to monitor
        self.large_pending_swaps: List[Dict] = []

    async def start(self):
        """Start mempool monitoring (runs 24/7 for EVM chains)"""

        # Subscribe to pending transactions
        async for tx_hash in self.w3.eth.subscribe('pendingTransactions'):
            # Fetch full transaction details
            tx = await self.w3.eth.get_transaction(tx_hash)

            if tx:
                await self.process_pending_transaction(tx)

    async def process_pending_transaction(self, tx: Dict):
        """Process each pending transaction"""

        # 1. Check if it's our own transaction
        if tx['from'].lower() in self.our_wallet_addresses:
            await self.track_our_transaction(tx)

        # 2. Decode DEX swap transactions
        if self.is_dex_swap(tx):
            swap_data = await self.decode_swap(tx)

            # Large swap detected (>$100k)
            if swap_data['usd_value'] > 100_000:
                await self.handle_large_pending_swap(swap_data, tx)

        # 3. Check for MEV opportunities/threats
        if self.config['mev_detection_enabled']:
            await self.detect_mev_activity(tx)

    async def track_our_transaction(self, tx: Dict):
        """Track our own pending transactions"""
        tx_hash = tx['hash'].hex()

        self.our_pending_txs[tx_hash] = {
            'timestamp': datetime.utcnow(),
            'to': tx['to'],
            'value': tx['value'],
            'gas_price': tx['gasPrice'],
            'nonce': tx['nonce'],
            'data': tx['input'],
            'status': 'pending'
        }

        print(f"[Mempool] Our TX pending: {tx_hash[:10]}... Gas: {tx['gasPrice']/1e9:.2f} Gwei")

        # Emit event
        self.event_bus.publish(OurTransactionPending(
            tx_hash=tx_hash,
            gas_price=tx['gasPrice']
        ))

    async def handle_large_pending_swap(self, swap_data: Dict, tx: Dict):
        """
        Handle large pending swap detected in mempool

        Example: Someone swapping $500k ETH → USDC
        - This will impact price WHEN it executes
        - We might want to avoid trading same pair
        - Or front-run if profitable (legal MEV)
        """

        print(f"[Mempool] Large swap pending: {swap_data['token_in']} → {swap_data['token_out']}")
        print(f"  Amount: ${swap_data['usd_value']:,.0f}")
        print(f"  DEX: {swap_data['dex']}")
        print(f"  Expected slippage: {swap_data['expected_slippage']:.2f}%")

        # Emit event for decision engine
        self.event_bus.publish(LargePendingSwap(
            swap_data=swap_data,
            tx_hash=tx['hash'].hex()
        ))

        # Store for tracking
        self.large_pending_swaps.append({
            **swap_data,
            'tx_hash': tx['hash'].hex(),
            'timestamp': datetime.utcnow(),
            'confirmed': False
        })

    def is_dex_swap(self, tx: Dict) -> bool:
        """Check if transaction is a DEX swap"""

        # Check if 'to' address is a known DEX router
        known_dex_routers = [
            '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',  # Uniswap V2 Router
            '0xE592427A0AEce92De3Edee1F18E0157C05861564',  # Uniswap V3 Router
            '0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F',  # SushiSwap Router
            '0x1111111254EEB25477B68fb85Ed929f73A960582',  # 1inch V5 Router
            # ... more routers
        ]

        return tx['to'] and tx['to'].lower() in [r.lower() for r in known_dex_routers]

    async def decode_swap(self, tx: Dict) -> Dict:
        """
        Decode DEX swap transaction data

        Returns:
        - token_in, token_out
        - amount_in, expected_amount_out
        - dex name
        - usd_value
        - expected_slippage
        """

        # Decode function call (e.g., swapExactTokensForTokens)
        function_signature = tx['input'][:10]

        # Use web3.py contract ABI to decode parameters
        decoded = self.decode_function_input(tx)

        # Estimate USD value and slippage
        token_in = decoded['path'][0]
        token_out = decoded['path'][-1]
        amount_in = decoded['amountIn']

        # Get token prices
        token_in_price = await self.get_token_price(token_in)
        usd_value = (amount_in / 1e18) * token_in_price

        return {
            'token_in': token_in,
            'token_out': token_out,
            'amount_in': amount_in,
            'expected_amount_out': decoded.get('amountOutMin', 0),
            'dex': self.identify_dex(tx['to']),
            'usd_value': usd_value,
            'expected_slippage': self.calculate_slippage(decoded),
            'deadline': decoded.get('deadline', 0)
        }

    async def detect_mev_activity(self, tx: Dict):
        """
        Detect potential MEV bots (frontrunning/sandwich attacks)

        Sandwich attack pattern:
        1. Bot TX#1: Buy token (frontrun)
        2. Victim TX: Original swap
        3. Bot TX#2: Sell token (backrun)

        Detection:
        - Same 'from' address with multiple pending txs
        - Opposite directions (buy then sell)
        - Similar gas price (racing for block inclusion)
        """

        # Check for known MEV bot addresses
        known_mev_bots = [
            # List of known MEV bot addresses
        ]

        if tx['from'].lower() in known_mev_bots:
            print(f"[Mempool] MEV bot detected: {tx['from']}")

            # Emit warning event
            self.event_bus.publish(MEVBotDetected(
                bot_address=tx['from'],
                tx_hash=tx['hash'].hex()
            ))
```

---

**2. Transaction Confirmation Tracker**

Tracks our transactions from pending → confirmed:

```python
class TransactionConfirmationTracker:
    """
    Track our DEX transactions through mempool → confirmation
    """

    async def monitor_confirmation(self, tx_hash: str, max_wait_seconds: int = 300):
        """
        Monitor transaction until confirmed or timeout

        Returns:
        - 'confirmed': Transaction included in block
        - 'failed': Transaction reverted
        - 'timeout': Not confirmed within max_wait_seconds
        - 'replaced': Transaction replaced (higher gas price)
        """

        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).seconds < max_wait_seconds:
            # Check transaction receipt
            receipt = await self.w3.eth.get_transaction_receipt(tx_hash)

            if receipt:
                # Transaction confirmed
                if receipt['status'] == 1:
                    print(f"[Mempool] TX confirmed: {tx_hash[:10]}... Block: {receipt['blockNumber']}")

                    self.event_bus.publish(OurTransactionConfirmed(
                        tx_hash=tx_hash,
                        block_number=receipt['blockNumber'],
                        gas_used=receipt['gasUsed']
                    ))

                    return 'confirmed'

                else:
                    # Transaction failed/reverted
                    print(f"[Mempool] TX FAILED: {tx_hash[:10]}...")

                    self.event_bus.publish(OurTransactionFailed(
                        tx_hash=tx_hash,
                        reason='Transaction reverted'
                    ))

                    return 'failed'

            # Still pending
            await asyncio.sleep(2)  # Check every 2 seconds

        # Timeout
        print(f"[Mempool] TX timeout: {tx_hash[:10]}... (not confirmed after {max_wait_seconds}s)")

        self.event_bus.publish(OurTransactionTimeout(
            tx_hash=tx_hash
        ))

        return 'timeout'
```

---

**3. Gas Price Oracle**

Monitors mempool congestion for optimal gas pricing:

```python
class GasPriceOracle:
    """
    Monitor mempool to determine optimal gas prices
    """

    async def get_optimal_gas_price(self, urgency: str = 'normal') -> int:
        """
        Get optimal gas price based on mempool congestion

        urgency:
        - 'low': Next 10 blocks (~2 min)
        - 'normal': Next 3 blocks (~36 sec)
        - 'high': Next block (~12 sec)
        - 'urgent': Top 10% gas price (immediate)
        """

        # Get pending transactions from mempool
        pending_txs = await self.w3.eth.get_block('pending', full_transactions=True)

        # Extract gas prices
        gas_prices = [tx['gasPrice'] for tx in pending_txs['transactions']]
        gas_prices.sort()

        # Calculate percentiles
        if urgency == 'low':
            # 25th percentile (slower, cheaper)
            return gas_prices[len(gas_prices) // 4]

        elif urgency == 'normal':
            # 50th percentile (median)
            return gas_prices[len(gas_prices) // 2]

        elif urgency == 'high':
            # 75th percentile (faster)
            return gas_prices[3 * len(gas_prices) // 4]

        elif urgency == 'urgent':
            # 90th percentile (very fast)
            return gas_prices[9 * len(gas_prices) // 10]
```

---

**4. MEV Protection Strategies**

```python
class MEVProtectionStrategy:
    """
    Protect against frontrunning and sandwich attacks
    """

    async def use_private_mempool(self, tx: Dict) -> str:
        """
        Send transaction via private relay (Flashbots, Eden, etc.)
        Avoids public mempool exposure

        Use for:
        - Large DEX swaps (>$50k)
        - Meme coin buys (prevent frontrunning)
        - Arbitrage transactions (protect alpha)
        """

        # Send to Flashbots Relay
        flashbots_rpc = "https://relay.flashbots.net"

        response = await self.send_private_transaction(
            tx,
            relay_url=flashbots_rpc
        )

        return response['tx_hash']

    async def use_limit_orders(self, token_in: str, token_out: str, amount: float, limit_price: float):
        """
        Use limit orders instead of market swaps
        Eliminates MEV vulnerability

        Use protocols:
        - Cowswap (batch auctions, MEV protection)
        - 1inch Limit Orders
        - Uniswap X
        """

    async def split_large_orders(self, total_amount: float, num_splits: int = 5):
        """
        Split large orders into smaller chunks
        Reduces price impact and MEV profit opportunity

        Example: $500k swap → 5x $100k swaps over 30 seconds
        """
```

---

**Event-Driven Integration**:

```python
# Mempool Monitor emits:
event_bus.publish("OurTransactionPending")      # Our TX entered mempool
event_bus.publish("OurTransactionConfirmed")    # Our TX confirmed
event_bus.publish("OurTransactionFailed")       # Our TX failed/reverted
event_bus.publish("OurTransactionTimeout")      # Our TX not confirmed in time
event_bus.publish("LargePendingSwap")           # Large swap detected (>$100k)
event_bus.publish("MEVBotDetected")             # Known MEV bot activity
event_bus.publish("MempoolCongestionHigh")      # Gas prices >100 Gwei

# Decision Engine subscribes to:
event_bus.subscribe("LargePendingSwap", decision_engine.on_large_pending_swap)
# Action: Avoid trading same pair until large swap confirms

# Execution Engine subscribes to:
event_bus.subscribe("OurTransactionPending", execution_engine.track_pending)
event_bus.subscribe("OurTransactionConfirmed", execution_engine.on_confirmed)
event_bus.subscribe("OurTransactionFailed", execution_engine.on_failed)
```

---

**DuckDB Schema Additions**:

```sql
-- Track mempool activity
CREATE TABLE mempool_large_swaps (
    timestamp TIMESTAMP,
    tx_hash VARCHAR,
    chain VARCHAR,
    dex VARCHAR,
    token_in VARCHAR,
    token_out VARCHAR,
    amount_in DECIMAL(30, 6),
    usd_value DECIMAL(30, 2),
    expected_slippage FLOAT,
    confirmed BOOLEAN,
    block_number INTEGER,
    actual_slippage FLOAT
);

-- Track our transaction lifecycle
CREATE TABLE our_transactions (
    tx_hash VARCHAR PRIMARY KEY,
    chain VARCHAR,
    status VARCHAR,  -- 'pending', 'confirmed', 'failed', 'timeout'
    submitted_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    gas_price BIGINT,
    gas_used INTEGER,
    block_number INTEGER,
    revert_reason VARCHAR
);

-- MEV activity log
CREATE TABLE mev_activity (
    timestamp TIMESTAMP,
    tx_hash VARCHAR,
    mev_type VARCHAR,  -- 'frontrun', 'sandwich', 'backrun'
    bot_address VARCHAR,
    target_tx VARCHAR,  -- Transaction being MEV'd
    estimated_profit DECIMAL(30, 6)
);
```

---

**Configuration** (`config/mempool.yaml`):

```yaml
mempool:
  enabled: true  # Enable for EVM chains only

  # Which chains to monitor
  monitored_chains:
    - ethereum
    - base
    - polygon
    - bsc
    # - arbitrum  # Limited mempool visibility on L2

  # Large swap detection
  large_swap_threshold_usd: 100000  # Alert on swaps >$100k

  # MEV protection
  mev_detection_enabled: true
  use_private_mempool_threshold_usd: 50000  # Use Flashbots for swaps >$50k

  # Gas price monitoring
  gas_price_monitoring:
    enabled: true
    check_interval_seconds: 10
    high_congestion_threshold_gwei: 100

  # Transaction confirmation
  max_confirmation_wait_seconds: 300  # 5 minutes
  check_interval_seconds: 2
```

---

**Benefits**:
- ✅ **MEV Protection**: Detect and avoid frontrunning/sandwich attacks
- ✅ **Slippage Prediction**: See large pending swaps before execution
- ✅ **Transaction Tracking**: Monitor our DEX transactions (pending → confirmed)
- ✅ **Gas Optimization**: Set optimal gas prices based on mempool congestion
- ✅ **Rug Pull Detection**: Dev wallets dumping detected early
- ✅ **Alpha Protection**: Use private mempools for sensitive trades

**Chains Supported**:
- ✅ Ethereum, Base, Polygon, BSC (full mempool access)
- ⚠️ Arbitrum (limited L2 sequencer visibility)
- ❌ Solana (no mempool, use leader schedule monitoring instead)
- ❌ Hyperliquid (centralized, no mempool)

**Maps to**:
- PROJECT_STRUCTURE.md: `src/market_data/mempool/mempool_monitor.py`
- TECHNICAL_ARCHITECTURE.md: Section 3.X (new)
- Event Bus integration: Section 2.2.0.1

---

#### 2.2.7 Data Storage Layer
**Responsibility**: Store and retrieve data efficiently with multi-timeframe support

**Data Organization Strategy - Per-Symbol Isolation** ⭐:
- **Per-Symbol Database Isolation**: Each trading pair gets its own isolated DuckDB database files
- **Directory Structure**: `/data/{exchange}/{market_type}/{symbol}/`
- **Example Structure**:
  ```
  data/
  ├── binance/
  │   ├── spot/
  │   │   ├── BTCUSDT/
  │   │   │   └── trading.duckdb        # All data: market data, analytics, decisions, trades
  │   │   ├── ETHUSDT/
  │   │   │   └── trading.duckdb
  │   │   └── SOLUSDT/
  │   │       └── trading.duckdb
  │   └── futures/
  │       ├── BTCUSDT/
  │       │   └── trading.duckdb
  │       └── ETHUSDT/
  │           └── trading.duckdb
  └── bybit/
      └── futures/
          └── BTCUSDT/
              └── trading.duckdb
  ```

**Why Per-Symbol Isolation is Critical**:
- **Zero Lock Contention**: 100 symbols = 100 independent databases = no write blocking
- **Parallel Processing**: All symbols can write simultaneously without waiting
- **Independent Scaling**: High-frequency pairs (BTC) don't impact low-frequency pairs (altcoins)
- **Clean Data Isolation**: Bug in one symbol doesn't corrupt others
- **Easy Management**: Add/remove symbols by creating/deleting directories
- **Debugging**: Clear data boundaries - if BTC trading fails, check `BTCUSDT/trading.duckdb` only
- **Performance**: No table-level locks across symbols, each DB can be optimized independently

**Connection Pooling & Management** ⭐:
```python
class ConnectionPoolManager:
    """
    Manages DuckDB connections with LRU eviction.
    Maximum 200 concurrent connections cached.
    """
    def __init__(self, max_connections: int = 200):
        self.pool: Dict[str, duckdb.DuckDBPyConnection] = {}
        self.access_times: Dict[str, float] = {}
        self.max_connections = max_connections
        self.lock = threading.Lock()

    def get_connection(self, exchange: str, market_type: str, symbol: str):
        """Get or create connection for specific symbol"""
        key = f"{exchange}_{market_type}_{symbol}"

        with self.lock:
            # Update access time
            self.access_times[key] = time.time()

            # Return cached connection
            if key in self.pool:
                return self.pool[key]

            # Evict LRU if pool is full
            if len(self.pool) >= self.max_connections:
                lru_key = min(self.access_times, key=self.access_times.get)
                self.pool[lru_key].close()
                del self.pool[lru_key]
                del self.access_times[lru_key]

            # Create new connection to symbol-specific database
            db_path = f"data/{exchange}/{market_type}/{symbol}/trading.duckdb"
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = duckdb.connect(db_path)
            self.pool[key] = conn

            return conn
```

**Performance Characteristics**:
- **Cached Connection Query**: 0.5-2ms (database already open)
- **New Connection Query**: 50-150ms (opening database overhead)
- **Cache Hit Rate**: >95% for active symbols
- **Memory Usage**: ~500MB for 200 cached connections
- **Throughput**: 100+ symbols writing simultaneously without blocking

**DuckDB** (Primary Analytics Database - Ultra-Fast Queries):
**Schema Design for Multi-Timeframe Analysis** (replicated per trading pair):

**Table: ticks** (THE SOURCE OF TRUTH)
- Raw tick data (trade-by-trade actual executions)
- Columns: timestamp, price, volume, side (buy/sell aggressor), exchange
- **No symbol column** - implied by database path (data/{exchange}/{market}/{symbol}/trading.duckdb)
- This contains ONLY real executed trades - no fake orderbook data
- **Retention: 15 MINUTES rolling window** (matches longest timeframe)
- High-frequency inserts (thousands per second during volatility)
- **Cleanup: Every 5 minutes, delete ticks older than 15 minutes**

**Table: candles_1m, candles_5m, candles_15m**
- OHLCV data for each timeframe (aggregated from ticks)
- Columns: timestamp, open, high, low, close, volume, buy_volume, sell_volume, num_trades, num_buy_trades, num_sell_trades
- **No symbol column** - implied by database path
- Buy/sell volume split provides order flow insight
- Indexed by (timestamp) only - simpler, faster queries
- **Retention Policy** (minimal for pattern detection):
  - **1M candles**: 15 minutes (15 candles for short-term patterns, RSI)
  - **5M candles**: 1 hour (12 candles for medium-term patterns)
  - **15M candles**: 1 hour (4 candles for trend detection)
- **Cleanup: Every 15 minutes, delete candles beyond retention window**
- **Rationale**: No EMAs needed - just recent candles for pattern detection (higher highs/lower lows, RSI)

**Table: order_flow** (Calculated from Trades Only)
- Cumulative volume delta and order flow metrics from actual trades
- Columns: timestamp, cvd, buy_volume, sell_volume, imbalance_ratio, delta, avg_buy_size, avg_sell_size
- **No symbol column** - implied by database path
- Timeframe: 1-minute aggregation
- All metrics derived from real executed trades (no orderbook)
- **Retention: 15 MINUTES rolling window**
- **Cleanup: Every 5 minutes, delete rows older than 15 minutes**

**Table: market_profile**
- Volume profile and POC data per timeframe
- Columns: timestamp, timeframe, poc_price, value_area_high, value_area_low, profile_data (JSON)
- **No symbol column** - implied by database path
- **Retention: 15 MINUTES rolling window** (recalculated on-the-fly from recent ticks)
- **Cleanup: Every 5 minutes, delete rows older than 15 minutes**

**Table: supply_demand_zones**
- Identified support/resistance zones
- Columns: zone_id, timeframe, zone_type (supply/demand), price_low, price_high, strength_score, first_seen, last_tested, status (fresh/tested)
- **No symbol column** - implied by database path
- **Retention: PERMANENT** (small data, only active zones kept)
- Zones marked as 'broken' are deleted immediately
- Max 50 zones per pair (oldest broken zones deleted first)

**Table: fair_value_gaps**
- Detected FVG patterns
- Columns: fvg_id, timeframe, fvg_type (bullish/bearish), gap_low, gap_high, created_at, filled_at, fill_percentage
- **No symbol column** - implied by database path
- **Retention: Until filled or 24 hours max**
- **Cleanup: Delete filled FVGs immediately, delete unfilled FVGs after 24 hours**

**Table: trade_executions**
- All executed trades (for current session only)
- Columns: trade_id, timestamp, side, entry_price, exit_price, quantity, pnl, fees, strategy, config_type
- **No symbol column** - implied by database path
- **Retention: Moved to Firestore immediately after trade completes**
- **Cleanup: Delete from DuckDB after syncing to Firestore (within 1 minute)**
- DuckDB only keeps active/open positions, completed trades go to Firestore

**Table: strategy_performance**
- Per-strategy performance metrics (in-memory calculations)
- Columns: timestamp, strategy, config_type, win_rate, avg_pnl, sharpe_ratio, max_drawdown, num_trades
- **No symbol column** - implied by database path
- **Retention: Current session only** (recalculated from Firestore trade_history on demand)
- **Cleanup: Cleared on system restart**

**Query Optimization**:
- Indexed on timestamp columns for fast cleanup
- In-memory caching for active trading pairs
- Minimal disk usage (15-minute rolling window for ticks/analytics)

**Data Cleanup Strategy** (Aggressive - VM Resource Management):

**Background Job: DuckDB Cleanup Service** (runs every 5 minutes):
- Deletes ticks older than 15 minutes
- Deletes all candles (1M, 5M, 15M) older than retention window
- Deletes order flow metrics older than 15 minutes
- Deletes market profile data older than 15 minutes
- Deletes filled FVGs immediately, unfilled FVGs after 24 hours
- Deletes broken supply/demand zones, keeps max 50 active zones per symbol
- Moves completed trades to Firestore and removes from DuckDB
- Runs VACUUM to reclaim disk space

**Implementation**: See TECHNICAL_ARCHITECTURE.md for detailed cleanup queries and code

**Why 15-Minute Rolling Window for Tick Data?**
- Ultra-short scalping strategy uses 15M as longest timeframe (1M/5M/15M)
- Market profile lookback matches longest timeframe (15 minutes)
- Order flow and CVD calculated from last 15 minutes maximum
- Perfect consistency across all analytics (everything aligned to 15m max)
- Keeps DuckDB database size ultra-minimal (< 50MB even with 100 symbols)
- VM-friendly: Low memory, low CPU, low disk usage
- Speed optimized for high-frequency scanning

**Data Retention Summary**:
| Data Type | Retention | Cleanup Frequency | Reason |
|-----------|-----------|-------------------|---------|
| Ticks | 15 minutes | Every 5 minutes | Raw trade data, matches longest TF |
| 1M Candles | 15 minutes | Every 15 minutes | Short-term patterns, RSI only |
| 5M Candles | 1 hour | Every 15 minutes | Medium-term patterns |
| 15M Candles | 1 hour | Every 15 minutes | Trend detection (3-4 candles) |
| Order Flow | 15 minutes | Every 5 minutes | Matches tick retention |
| Market Profile | 15 minutes | Every 5 minutes | Matches longest TF for consistency |
| Supply/Demand Zones | Permanent (max 50/symbol) | On zone break | Small data, need for context |
| Fair Value Gaps | Until filled or 24hrs | On fill or daily | Active gaps only |
| Trade Executions | Immediate to Firestore | Every 5 minutes | DuckDB not for storage |
| Watchlist Manual | 24 hours | Daily at 00:00 UTC | User-added pairs expire |
| Watchlist Top 15 | Permanent | Updated daily | Auto-selected liquid pairs |

**Expected DuckDB Size** (per exchange/market):
- 100 symbols × 15 minutes of tick data + ultra-minimal candles = ~30-50 MB per database file
- Total across all exchanges: ~200-300MB max (binance spot + futures, bybit, etc.)
- **70% reduction** from EMA-based approach (was ~1GB)
- Firestore handles all historical data and trade logs

**Firestore** (Persistent State):

**Collection: `watchlists`** (Symbol Selection & Management):
- **Top 15 Liquid Pairs** (permanent, auto-updated daily)
  - Ranked by 24h volume, trades, and spread
  - Always monitored (e.g., BTCUSDT, ETHUSDT, SOLUSDT)
- **Manual Watchlist** (24-hour expiry)
  - Added via API endpoints
  - Auto-deleted after 24 hours
  - Can be renewed before expiry
- Schema: `{symbol, added_at, expires_at, added_by, priority, enabled}`

**Collection: `market_configs`**:
- **Binance Spot**: fee_maker: 0.1%, fee_taker: 0.1%, leverage: 1x
- **Binance Futures**: fee_maker: 0.02%, fee_taker: 0.04%, max_leverage: 125x
- **Bybit Futures**: (future expansion)

**Collection: `active_positions`**:
- Real-time position tracking per exchange/market
- Schema: `{exchange, market_type, symbol, side, entry_price, quantity, pnl}`

**Collection: `strategy_configs`**:
- Ultra-Short Scalping configuration settings per exchange/market
- Risk limits and thresholds
- Trading pair settings (enabled/disabled, position sizes)

**Collection: `trade_history`**:
- Historical trade logs (summary, references to DuckDB)
- Account balances and margin usage per exchange
- System state and metadata

**Firebase Storage** (File Storage):
- Daily/weekly performance reports (CSV/JSON)
- System logs and error traces
- Backtest results with charts
- Market profile visualizations
- Order flow heatmaps

---

## 3. Trading Strategies

### 3.1 Bid-Ask Bounce Strategy

**Concept**: Capture profits from the natural oscillation of prices within the bid-ask spread.

**Market Conditions**:
- Tight spreads (< 0.1% for crypto)
- High liquidity (order book depth)
- Low volatility (stable range-bound markets)

**Entry Logic**:
- Place buy orders at or near bid price
- Place sell orders at or near ask price
- Adjust orders based on order book dynamics

**Exit Logic**:
- Take profit when spread is captured
- Cancel stale orders (not filled within time limit)
- Exit if volatility spike detected

**Risk Controls**:
- Maximum position size per pair
- Inventory management (avoid accumulating directional exposure)

### 3.2 Market Quality Trading

**Concept**: Only trade in high-quality markets to minimize adverse selection.

**Quality Metrics**:
- Bid-ask spread (tighter is better)
- Order book depth (higher is better)
- Volume (higher is better)
- Price stability (lower volatility is better for market-making)

**Implementation**:
- Calculate quality score for each market
- Only enable strategies on markets exceeding quality threshold
- Dynamically adjust position sizes based on quality

### 3.3 Meme Coin Trading

**Concept**: Identify and trade emerging meme coins with high volatility.

**Entry Signals**:
- Sudden volume increase (10x+ normal)
- New token listings on DEXes
- Social media buzz indicators (future integration)
- Liquidity pool creation events

**Risk Management**:
- Small position sizes (high risk)
- Tight stop-losses (10-20%)
- Time-based exits (avoid holding overnight)
- Rug pull detection (liquidity removal alerts)

### 3.4 Flashloan Arbitrage

**Concept**: Execute risk-free arbitrage using flashloans on DeFi protocols.

**Opportunity Detection**:
- Monitor price differences across DEXes
- Calculate profitable routes (token A → token B → token C → token A)
- Account for gas fees and flashloan fees

**Execution Flow**:
1. Detect arbitrage opportunity
2. Simulate flashloan transaction
3. Execute atomic transaction if profitable
4. Return flashloan + fee
5. Keep profit

**Challenges**:
- High gas costs on Ethereum (consider L2s)
- MEV competition (bots frontrunning)
- Slippage on low-liquidity pools

---

## 4. Data Flow

### 4.1 Real-Time Trading Flow

```
1. Market Data Arrives (WebSocket/Blockchain Events)
          ↓
2. Data Ingestion Layer (normalize, validate)
          ↓
3. DuckDB Storage (insert tick data)
          ↓
4. Core Decision Engine (analyze, generate signals)
          ↓
5. Risk Management Module (validate trade)
          ↓
6. Order Execution Layer (send order to exchange)
          ↓
7. Firestore (update positions, orders)
          ↓
8. Notification System (alert if needed)
```

### 4.2 Historical Analysis Flow

```
1. Load historical data from DuckDB
          ↓
2. Run backtest on strategy
          ↓
3. Generate performance metrics
          ↓
4. Store results in Firebase Storage
          ↓
5. Update strategy parameters in Firestore
```

---

## 5. Integration Points

### 5.1 Exchange Integrations

**Binance**:
- **Spot Market**:
  - REST API for account management
  - WebSocket for real-time trade data
  - Order placement and management APIs
  - No leverage, actual token ownership
- **Futures Market** (USDT-M Perpetual):
  - Separate WebSocket feed for futures trades
  - Perpetual contracts (no expiry)
  - Up to 125x leverage support
  - Funding rates every 8 hours
  - Lower fees (0.02% maker, 0.04% taker)

**Bybit**:
- Spot and Futures market support
- Similar structure to Binance integration

**DEX Integrations**:
- Uniswap V2/V3 (Ethereum, L2s)
- PancakeSwap (BSC)
- Raydium (Solana)
- Web3 wallet integration for transaction signing

### 5.2 Firebase Integration

**Firestore**:
- Store trading configurations
- Persist position and order state
- Save strategy performance logs
- User authentication and access control 

**Firebase Storage**:
- Upload daily performance reports (CSV/JSON)
- Store system logs for debugging
- Archive backtest results
- Store snapshots for disaster recovery

### 5.3 Watchlist Management API

**Base URL**: `/api/v1/watchlist`

**Endpoints**:
- `POST /api/v1/watchlist/add` - Add symbol to manual watchlist (24hr default expiry)
- `DELETE /api/v1/watchlist/remove` - Remove symbol from watchlist
- `POST /api/v1/watchlist/renew` - Extend watchlist entry by 24 hours
- `GET /api/v1/watchlist` - Get active watchlist for exchange/market
- `GET /api/v1/watchlist/top-liquid` - Get top 15 most liquid pairs

**Example - Add Symbol**:
```json
POST /api/v1/watchlist/add
{
  "exchange": "binance",
  "market_type": "futures",
  "symbol": "PEPEUSDT",
  "duration_hours": 24,
  "priority": 3
}
```

**Background Jobs**:
- Watchlist Cleaner (every 24 hours at 00:00 UTC): Check and remove expired 24hr entries
- Top Liquid Updater (daily at 00:00 UTC): Update top 15 pairs based on 24h volume

### 5.4 Notification API

**Webhook Integration**:
- POST requests to configurable endpoints
- JSON payload with event details
- Retry logic for failed deliveries
- Rate limiting to prevent spam

**Event Types**:
- `trade_executed`: Trade details and P&L
- `watchlist_expiring`: Symbol expiring in 1 hour
- `risk_breach`: Risk limit violations
- `system_error`: Critical failures
- `daily_summary`: End-of-day performance

---

## 6. Non-Functional Requirements

### 6.1 Performance
- **Latency**: <100ms from signal generation to order placement
- **Throughput**: Support 1000+ market data updates per second
- **Query Speed**: DuckDB queries complete in <10ms for recent data

### 6.2 Reliability
- **Uptime**: 99.9% availability target
- **Data Integrity**: Zero data loss for trade executions
- **Fault Tolerance**: Automatic reconnection to exchanges
- **State Recovery**: Resume operations after crashes

### 6.3 Security
- **API Key Management**: Encrypted storage of credentials
- **Network Security**: HTTPS/WSS only
- **Access Control**: Authentication for admin operations
- **Audit Logging**: Track all system actions

### 6.4 Scalability
- **Horizontal Scaling**: Support multiple trading pairs on separate instances
- **Vertical Scaling**: Efficient CPU/memory usage
- **Storage Growth**: Handle years of tick data in DuckDB

---

## 7. Key Design Decisions Pending

### 7.1 Core Decision Engine Architecture
**Status**: TO BE DESIGNED

**Questions to Address**:
- Event-driven vs. polling architecture?
- Strategy prioritization mechanism?
- State management across strategies?
- Backtesting integration approach?
- Configuration management (YAML vs. database)?

### 8.2 DEX Transaction Management
- Which blockchain(s) to prioritize?
- Gas optimization strategies?
- MEV protection mechanisms?
- Wallet key management approach?

### 8.3 Monitoring and Observability
- Metrics collection framework (Prometheus, custom)?
- Real-time dashboard requirements?
- Alerting rules and thresholds?

---

## 8. Success Metrics

### 9.1 Financial Performance
- **Profitability**: Positive returns after fees
- **Sharpe Ratio**: >1.5 (risk-adjusted returns)
- **Win Rate**: >55% for market-making strategies
- **Maximum Drawdown**: <10% of capital

### 9.2 Operational Metrics
- **System Uptime**: >99.5%
- **Order Fill Rate**: >90%
- **Average Latency**: <50ms (signal to order)
- **Data Accuracy**: >99.99%

### 9.3 Risk Metrics
- **Risk Limit Breaches**: <5 per month
- **Failed Trades**: <1% of total
- **Unexpected Losses**: <0.5% of capital per month

---

## 9. DEX Trading System

### 9.1 Overview
The DEX trading system enables multi-chain decentralized exchange trading using **DEX aggregators** for optimal routing, meme coin detection, and cross-exchange arbitrage.

**Core Principle**: Don't build custom routing - use proven aggregators that already optimize across multiple DEXes for best price and lowest fees.

**Aggregators Used**:
- **Solana**: Jupiter Aggregator (routes across Raydium, Orca, Phoenix for best price)
- **Ethereum/EVM**: 1inch, Matcha (0x), ParaSwap (routes across Uniswap, SushiSwap, Curve, etc.)
- **Base**: 1inch, Uniswap Router
- **BSC**: 1inch, PancakeSwap Router

**Why Aggregators?**
- ✅ Already optimized routing algorithms (Dijkstra, A* pathfinding)
- ✅ Real-time liquidity monitoring across all DEXes
- ✅ Automatic split orders across multiple pools for best price
- ✅ Built-in slippage protection and MEV mitigation
- ✅ No need to maintain complex routing logic

### 9.2 Supported Chains & DEXes (Prioritized by Tier)

**Strategy**: Start with high-liquidity chains first, then expand to emerging chains with growth potential.

---

#### **TIER 1: Priority Chains**
*Highest liquidity, proven infrastructure, essential for profitability*

**Ethereum Mainnet** (EVM)
- **DEXes**: Uniswap V2/V3, SushiSwap, Curve Finance, Balancer V2, 0x Protocol
- **Why Priority**: Deepest liquidity, highest meme coin activity, flashloan support
- **Challenges**: High gas costs (use during low-gas periods)
- **Meme Coin Hotspot**: ✓ Primary meme coin launch platform

**Base** (EVM - Ethereum L2)
- **DEXes**: Uniswap V3, Aerodrome, BaseSwap
- **Why Priority**: Fast-growing ecosystem, low fees, Coinbase backing, meme coin explosion
- **Gas Costs**: Very low (~$0.01-0.05 per transaction)
- **Meme Coin Hotspot**: ✓✓ Extremely active for new meme coins

**Solana** (Non-EVM)
- **DEXes**: Raydium, Orca, Jupiter Aggregator, Phoenix
- **Why Priority**: Ultra-low fees, massive meme coin activity, high-speed execution
- **Gas Costs**: ~$0.00025 per transaction
- **Meme Coin Hotspot**: ✓✓✓ #1 platform for meme coin launches

**Binance Smart Chain (BSC)** (EVM)
- **DEXes**: PancakeSwap V2/V3, BiSwap, ApeSwap, THENA
- **Why Priority**: High volume, low fees, strong meme coin community
- **Gas Costs**: Very low (~$0.10-0.30 per transaction)
- **Meme Coin Hotspot**: ✓✓ Very active meme coin trading

**Hyperliquid L1** (Non-EVM - Custom Chain) ⭐⭐⭐
- **Type**: Native perpetual DEX with own L1 blockchain + growing spot markets
- **DEXes**: Hyperliquid DEX (native orderbook + AMM hybrid)
- **Why TIER 1 Priority**:
  - **Perpetual-Spot Arbitrage**: Trade perps against spot on other chains (MASSIVE opportunity)
  - **Funding Rate Arbitrage**: Earn funding rates while hedging on spot DEXes
  - **Ultra-low latency**: <10ms execution, institutional-grade
  - **Extremely low fees**: ~$0.001 per trade (no gas, just exchange fees)
  - **High leverage**: Up to 50x on perpetuals (for arbitrage hedging)
  - **Growing spot markets**: New meme coins launching on HyperEVM spot
- **Arbitrage Examples**:
  - Long BTC spot on Uniswap, short BTC perp on Hyperliquid → collect funding
  - Spot-perp spread capture (perps often trade at premium/discount)
  - Cross-exchange perp arbitrage (Hyperliquid vs Binance futures)
- **Challenges**: Custom API (not standard Web3), requires specific SDK
- **Meme Coin Activity**: Growing rapidly (HyperEVM spot launch)
- **Priority**: CRITICAL FOR ARBITRAGE ⭐⭐⭐

**HyperEVM Integration Note**: HyperEVM (Hyperliquid's EVM layer) is launching spot markets. Start with Hyperliquid L1 perps immediately, then add HyperEVM spot when available for complete arbitrage coverage.

---

#### **TIER 2: High-Value L2s**
*Lower fees than Ethereum, high liquidity, growing ecosystems*

**Arbitrum** (EVM - Ethereum L2)
- **DEXes**: Uniswap V3, SushiSwap, Camelot, GMX (perps)
- **Why Important**: Second-largest L2 by TVL, strong DeFi ecosystem
- **Gas Costs**: Low (~$0.10-0.50 per transaction)
- **Meme Coin Activity**: Moderate (growing)

**Polygon** (EVM - Ethereum Sidechain)
- **DEXes**: QuickSwap, Uniswap V3, SushiSwap, Balancer
- **Why Important**: Large user base, low fees, established ecosystem
- **Gas Costs**: Very low (~$0.01-0.05 per transaction)
- **Meme Coin Activity**: Moderate

**Avalanche C-Chain** (EVM)
- **DEXes**: Trader Joe, Pangolin, Pharaoh
- **Why Important**: Fast finality, Subnet ecosystem, DeFi focus
- **Gas Costs**: Low (~$0.50-2.00 per transaction)
- **Meme Coin Activity**: Moderate

---

#### **TIER 3: Emerging High-Performance Chains**
*Newer chains with unique features, growing liquidity*

**Sui** (Non-EVM - Move Language)
- **DEXes**: Cetus, Turbos Finance, Aftermath Finance
- **Why Important**: High throughput, Move VM security, growing ecosystem
- **Gas Costs**: Very low (~$0.001-0.01 per transaction)
- **Meme Coin Activity**: Emerging (watch for growth)

**Aptos** (Non-EVM - Move Language)
- **DEXes**: PancakeSwap, LiquidSwap, Thala
- **Why Important**: Move VM, parallel execution, strong backers
- **Gas Costs**: Very low (~$0.001-0.01 per transaction)
- **Meme Coin Activity**: Emerging

**Berachain** (EVM) ⭐
- **DEXes**: BEX (native), Kodiak, Infrared
- **Why Important**:
  - Proof-of-Liquidity consensus (unique incentives)
  - Growing meme coin community
  - Strong DeFi focus
- **Gas Costs**: Low (estimated ~$0.05-0.20)
- **Meme Coin Activity**: ✓ High potential (new chain hype)
- **Status**: Recently launched - HIGH GROWTH POTENTIAL

---

#### **TIER 4: Additional EVM L2s**
*Good for completeness, lower priority*

**Optimism** (EVM - Ethereum L2)
- **DEXes**: Uniswap V3, Velodrome
- **Gas Costs**: Low (~$0.10-0.50 per transaction)

**Linea** (EVM - zkEVM L2)
- **DEXes**: SyncSwap, Velocore, EchoDEX
- **Why Include**: zkEVM technology, Consensys backing

**Mantle** (EVM - Ethereum L2)
- **DEXes**: Agni Finance, FusionX, Merchant Moe
- **Why Include**: High TVL, BitDAO backing

**Blast** (EVM - Ethereum L2)
- **DEXes**: Thruster, Blaster Swap
- **Why Include**: Native yield on ETH/stablecoins

---

#### **TIER 5: Special Purpose / Lower Priority**

**Tron** (Non-EVM)
- **DEXes**: SunSwap, JustLend
- **Why Include**: High stablecoin volume (USDT), Asian markets
- **Meme Coin Activity**: Moderate (primarily in Asia)

**Cronos** (EVM)
- **DEXes**: VVS Finance, MM Finance
- **Why Include**: Crypto.com ecosystem

**Bitcoin L2s** (Emerging)
- **Chains**: Stacks, RSK, Liquid Network
- **Status**: Watch for DeFi growth
- **Priority**: LOW (limited DEX activity currently)

---

#### **EXCLUDED / NOT RECOMMENDED**

**Plasma**:
- Status: Deprecated technology (old Ethereum scaling solution)
- Recommendation: ❌ DO NOT include

**Vaulta**:
- Status: Unknown/very low volume
- Recommendation: ❌ SKIP unless specific use case

**Katana (Ronin DEX)**:
- Limited to Ronin ecosystem (gaming-focused)
- Recommendation: ⚠️ LOW PRIORITY (niche use case)

---

#### **SPECIAL CONSIDERATION: HyperEVM**

**HyperEVM** (Hyperliquid's EVM Layer)
- **Status**: In development / early stage
- **Purpose**: EVM compatibility on top of Hyperliquid L1
- **Strategy**:
  - Start with native Hyperliquid L1 perpetuals first
  - Add HyperEVM when it launches and has liquidity
  - Will enable standard Web3 integration
- **Timeline**: Monitor for launch (2025 likely)
- **Recommendation**: ✓ Add when launched with sufficient liquidity

---

### 9.2.1 Final Recommended Priority Order

**TIER 1 - CRITICAL FOR ARBITRAGE**:
1. Ethereum Mainnet (spot DEX + flashloans)
2. Solana ⭐⭐⭐ (Best for meme coins + spot trading)
3. Base ⭐⭐ (Fast-growing, low fees)
4. BSC (High volume spot trading)
5. **Hyperliquid L1** ⭐⭐⭐ (Perpetuals - MUST HAVE for perp-spot arbitrage)

**TIER 2**:
6. Arbitrum
7. Polygon
8. Avalanche

**TIER 3**:
9. Berachain ⭐ (New chain hype)
10. Sui
11. HyperEVM ⭐ (When launched - Hyperliquid spot markets)

**TIER 4**:
11. Aptos
12. Optimism
13. Linea
14. Mantle

**TIER 5+**:
15. Tron (if Asian market focus)
16. Cronos
17. HyperEVM (when launched)
18. Additional chains as they gain traction

---

### 9.2.2 Chain Selection Criteria

When evaluating new chains, consider:

1. **Liquidity Depth**: TVL > $100M for meaningful trading
2. **Meme Coin Activity**: New token launches per week
3. **Gas Costs**: Must not eat into arbitrage profits
4. **Technical Maturity**: Stable RPC endpoints, good documentation
5. **DEX Availability**: Multiple DEXes for arbitrage opportunities
6. **Community Size**: Active traders and developers
7. **Bridge Availability**: Easy cross-chain capital movement

**Auto-Include Threshold**: Any chain that consistently has >$500M TVL in DEXes

---

**Cross-Chain Bridges** (for arbitrage):
- Wormhole (multi-chain)
- Stargate Finance (LayerZero-based)
- Synapse Protocol
- Across Protocol
- Celer cBridge
- Multichain (RIP - use alternatives)

### 9.3 Architecture: DEX Aggregator Integration

```
┌──────────────────────────────────────────────────────────────────┐
│                    DEX Trading Architecture                       │
│                  (Using External Aggregators)                     │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Price Monitoring Layer                        │
│  Monitor aggregator quotes for best execution prices             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Jupiter   │  │ 1inch    │  │ Matcha   │  │ ParaSwap │       │
│  │(Solana)  │  │(EVM)     │  │ (0x)     │  │ (EVM)    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                   ┌──────────────────────┐
                   │ Arbitrage Detector   │
                   │ - CEX-DEX spread     │
                   │ - Aggregator quotes  │
                   │ - Cross-chain arb    │
                   └──────────────────────┘
                                │
                                ▼
                   ┌─────────────────────────────────┐
                   │  Aggregator Execution Engine    │
                   │                                  │
                   │  Solana:                         │
                   │  └─ Jupiter API (best route)    │
                   │                                  │
                   │  Ethereum/Base/L2s:              │
                   │  └─ 1inch API (best route)      │
                   │  └─ Matcha API (0x limit orders)│
                   │                                  │
                   │  ✅ Aggregators handle:         │
                   │     - Route optimization        │
                   │     - Slippage protection       │
                   │     - MEV protection            │
                   │     - Gas optimization          │
                   └─────────────────────────────────┘
```

**Example: Buying SOL with USDT on Solana**
```python
# Use aggregator factory to get appropriate aggregator
aggregator = aggregator_factory.get_aggregator('solana')  # Returns JupiterAggregator

# Get quote using adapter interface
quote = await aggregator.get_quote(
    input_token="USDT",
    output_token="SOL",
    amount=1000,  # 1000 USDT
    slippage_bps=50  # 0.5% slippage
)

# Aggregator (Jupiter) returns the best route across:
# - Raydium
# - Orca
# - Phoenix
# - Multiple pools
# - Split orders for best price

# Execute swap using adapter interface
tx_hash = await aggregator.execute_swap(quote, wallet_address)
logger.info(f"Swap executed via {quote.aggregator}: {tx_hash}")
```

**Example: Selling SOL for USDT**
```python
# Same adapter interface works for selling
aggregator = aggregator_factory.get_aggregator('solana')

quote = await aggregator.get_quote(
    input_token="SOL",
    output_token="USDT",
    amount=10,  # 10 SOL
    slippage_bps=50
)

# Aggregator finds path with:
# - Highest output price
# - Lowest fees
# - Best liquidity

# Execute swap
tx_hash = await aggregator.execute_swap(quote, wallet_address)
```

### 9.4 Aggregator Performance Analysis

**Purpose**: Monitor and compare aggregator performance to select the best aggregator per chain/token.

**Analysis Components**:

**Aggregator Quote Comparison**:
```python
# Compare multiple aggregators for same swap (if available on chain)
aggregators = [
    aggregator_factory.get_aggregator('solana'),  # Jupiter
    # Could add alternative Solana aggregators if configured
]

quotes = []
for aggregator in aggregators:
    quote = await aggregator.get_quote("SOL", "USDT", 10)
    quotes.append(quote)

# Pick best aggregator based on:
# - Output amount (highest)
# - Estimated fees (lowest)
# - Success rate (historical)
# - Execution speed

best_quote = max(quotes, key=lambda q: q.output_amount)
logger.info(f"Best aggregator: {best_quote.aggregator}")
```

**Meme Coin Liquidity Analysis**:
```python
# For new meme coins, check:
1. Which aggregator has best route?
2. What's the exit liquidity?
3. Slippage tolerance needed?
4. Is there enough volume to sell?
```

**Gas Cost Optimization**:
```python
# Monitor gas costs across chains:
- Ethereum: High gas, use during low-gas periods
- Base/Arbitrum: Low gas, execute anytime
- Solana: Ultra-low fees, always optimal
```

**No Custom Routing**:
- ❌ Don't build graph algorithms
- ❌ Don't maintain pool liquidity databases
- ✅ Use aggregator APIs (they do this for us)
- ✅ Monitor aggregator performance
- ✅ Switch aggregators if one performs better

---

### 9.5 Meme Coin Detection & Trading

**Purpose**: Detect new meme coin launches and evaluate trading opportunities using aggregator quotes.

**Detection Strategy**:
```python
class MemeCoinDetector:
    def monitor_new_pools(self):
        """
        Monitor pool creation events across all DEXes:
        - Uniswap V2/V3 PoolCreated events
        - Raydium pool initialization
        - PancakeSwap pair creation

        Filter for:
        - Tokens paired with WETH, USDC, SOL, BNB
        - Initial liquidity > $10k
        - Contract deployed < 24 hours ago
        """

    def screen_meme_coin(self, token_address, chain):
        """
        Initial screening checks:
        1. Contract verification (is it a honeypot?)
        2. Liquidity lock status (is LP locked?)
        3. Holder distribution (is it concentrated?)
        4. Token permissions (can owner mint/pause?)
        5. Social signals (Twitter mentions, Telegram activity)

        Return risk score: 0-100
        """

    def get_aggregator_quote(self, token_address, chain, amount_in):
        """
        Use aggregators to check exit liquidity:

        Solana:
        - Jupiter quote for selling X SOL worth of token

        Ethereum/Base/L2s:
        - 1inch quote for selling X WETH worth of token

        This tells us if we can actually EXIT the position!
        """
        # Get appropriate aggregator via factory (swappable!)
        aggregator = self.aggregator_factory.get_aggregator(chain)

        # Determine output token based on chain
        output_token = "SOL" if chain == 'solana' else "WETH"

        # Get quote using adapter interface
        quote = await aggregator.get_quote(
            input_token=token_address,
            output_token=output_token,
            amount=amount_in,
            slippage_bps=1000  # 10% for meme coins
        )

        # Check slippage - if >10%, liquidity too thin
        if quote.estimated_slippage > 0.10:
            logger.warning(f"High slippage for {token_address}: {quote.estimated_slippage}")

        return {'quote': quote, 'slippage': quote.estimated_slippage}
```

**Entry Strategy**:
```python
def evaluate_meme_coin_entry(token, chain):
    """
    Entry criteria:
    - Risk score > 60 (not likely honeypot)
    - Liquidity > $50k and locked
    - Exit quote shows <5% slippage for target position size
    - Volume trending up (10x spike in last hour)
    - Social buzz score > threshold

    Position sizing:
    - Max 1% of portfolio per meme coin
    - Max 5% total in meme coins
    """
```

**Exit Strategy**:
```python
def execute_meme_coin_exit(token, chain, position_size):
    """
    Use aggregator for best exit price:

    1. Get quote from aggregator
    2. Check slippage tolerance
    3. Execute if profitable
    4. Monitor for failed transactions (honeypot detection)

    Exit triggers:
    - 0.5% trailing stop hit (same as all markets)
    - Dump detected (order flow flip + volume reversal + lower highs)
    - Liquidity dropping >30% (rug pull risk)
    - Catching falling knife (if reversing, exit immediately)
    """
```

**Risk Management**:
- Never trade without checking aggregator exit quote FIRST
- Aggregators show real liquidity depth
- If aggregator can't route, DON'T trade
- Use 0.5% trailing stop (same as all markets)
- Monitor for honeypot characteristics after entry

### 9.6 Multi-Chain DEX Data Ingestion

**Ethereum & L2s** (via Web3.py + WebSockets):
```python
# Monitor Uniswap V3 pool events
from web3 import Web3

# Subscribe to events:
- Swap events (real-time trades)
- Mint/Burn events (liquidity changes)
- Pool creation events (new trading pairs)

# Data normalized to standard format:
{
    'chain': 'ethereum',
    'dex': 'uniswap_v3',
    'pool_address': '0x...',
    'token0': 'WETH',
    'token1': 'USDC',
    'price': 2000.5,
    'liquidity': 10000000,
    'volume_24h': 50000000,
    'fee_tier': 0.3  # 0.3%
}
```

**Solana** (via Solana Web3.js + WebSocket):
```python
# Monitor Raydium/Orca pools
from solana.rpc.websocket_api import connect

# Subscribe to:
- accountSubscribe (pool account changes)
- logsSubscribe (transaction logs)

# Parse Raydium AMM events
# Normalize to common format
```

**BSC** (via Web3.py):
```python
# PancakeSwap monitoring (same as Ethereum, different RPC)
```

### 9.7 Meme Coin Detection & Trading System

**Real-Time Detection Pipeline**:
```
1. Pool Creation Monitoring
   - Listen for new pair creation on all DEXes
   - Filter for tokens paired with WETH/USDC/BNB
   - Ignore known scam contracts

2. Initial Screening
   - Check contract for honeypot characteristics
   - Verify liquidity lock status
   - Analyze token holder distribution
   - Check for unlimited minting capabilities

3. Signal Scoring
   - Liquidity score (min $50k)
   - Holder distribution score (not 90% in one wallet)
   - Contract security score (audit results)
   - Social buzz score (Twitter mentions)

4. Trade Decision
   - If score > threshold: prepare entry
   - Calculate position size (max 1% of portfolio)
   - Set tight stop-loss (15%)
   - Plan exit strategy (target 2x-5x)
```

**Meme Coin Trading Strategy**:
```python
class MemeCoinStrategy:
    def evaluate_entry(self, token):
        """
        PRE-FILTERS (before decision engine):
        - Liquidity > $50k and locked
        - Volume spike > 10x baseline
        - No honeypot indicators
        - Rug check passed

        Then enters SAME 4-level decision engine:
        - Level 1: Trend (higher highs/lows, ADX >25)
        - Level 2: Zone (market profile, POC)
        - Level 3: Cascade (order flow imbalance >2.5:1)
        - Level 4: Trigger (wick rejection, bid-ask bounce)
        """

    def execute_trade(self, token, amount):
        """
        Execution:
        - Use optimal route (usually direct WETH → Token)
        - Set slippage to 5-10% (high volatility)
        - Monitor for rug pull indicators
        - Set 0.5% trailing stop (SAME as all markets)
        """

    def exit_strategy(self, position):
        """
        Exit triggers (SAME as all markets):
        - 0.5% trailing stop hit
        - Dump detected (order flow flip + volume reversal)
        - Liquidity drops >30% (meme-specific)
        - If reversing = catching falling knife = exit NOW

        NO time-based exits - hold as long as trend continues
        Meme coins trend in ONE direction when momentum strong
        """
```

### 9.8 Hyperliquid Perpetual-Spot Arbitrage System

**Why Hyperliquid is Critical for Arbitrage**:

Hyperliquid offers unique arbitrage opportunities that don't exist on traditional DEXes:
1. **Perp-Spot Basis Trading**: Perpetual contracts often trade at premium/discount to spot
2. **Funding Rate Arbitrage**: Earn 0.01-0.1% per 8 hours while market-neutral
3. **Cross-Venue Perp Arbitrage**: Price differences between Hyperliquid and Binance/Bybit futures
4. **Meme Coin Perp Launch**: Trade perps of meme coins with high leverage while managing spot risk

---

#### **Strategy 1: Funding Rate Arbitrage (Delta-Neutral)**

**Concept**: Earn funding rates by holding perpetual positions while hedging with spot.

**Example Setup**:
```
Scenario: ETH perpetual on Hyperliquid has +0.05% funding rate (8h)

Position:
1. LONG 10 ETH spot on Uniswap @ $3,000 = $30,000
2. SHORT 10 ETH perp on Hyperliquid @ $3,000 = $30,000

Result:
- Delta-neutral (price movement doesn't matter)
- Earn 0.05% × $30,000 = $15 every 8 hours
- = $45/day = $16,425/year on $30k (54% APY)

Costs:
- Hyperliquid fees: ~$0.001 per trade ($0.03 to open)
- Uniswap gas: ~$5-20 (one-time)
- Bridge fees to move capital

Profit: $45/day - minimal fees = $43/day net
```

**Risk Management**:
- Monitor funding rate changes (can flip negative)
- Set auto-close if funding rate drops below threshold (e.g., 0.01%)
- Account for bridge time and costs
- Keep collateral buffer on Hyperliquid (avoid liquidation)

---

#### **Strategy 2: Perpetual-Spot Basis Trading**

**Concept**: Exploit price differences between perpetual and spot markets.

**Example Opportunity**:
```
Situation: PEPE meme coin during high volatility

Spot DEX (Raydium): $0.001000
Hyperliquid Perp: $0.001100 (10% premium - overleveraged longs)

Execution:
1. BUY PEPE spot on Raydium for $10,000 @ $0.001000
2. SHORT PEPE perp on Hyperliquid for $10,000 @ $0.001100
3. Wait for basis to converge (usually happens within hours/days)
4. Close both positions

Scenario A - Basis Converges (both at $0.001050):
- Spot P&L: +$500 (went from $0.001000 to $0.001050)
- Perp P&L: -$500 (went from $0.001100 to $0.001050)
- Basis Capture: $1,000 (the 10% premium)
- Net Profit: $1,000 - fees ≈ $995

Scenario B - Price Moves Up 50%:
- Spot @ $0.001500 → Profit: $5,000
- Perp @ $0.001650 → Loss: $5,500
- Basis still captured: $1,000
- Net: ~$500 profit (basis - increased perp premium)
```

**When to Use**:
- Perp trading at >5% premium or discount to spot
- High volatility meme coins (often get overleveraged)
- Before major news events (perps overshoot)

---

#### **Strategy 3: Cross-Venue Perpetual Arbitrage**

**Concept**: Price differences between Hyperliquid and other perpetual exchanges.

**Example**:
```
BTC/USDT Perpetual Prices:
- Hyperliquid: $69,500
- Binance Futures: $69,800

Execution:
1. LONG BTC perp on Hyperliquid @ $69,500
2. SHORT BTC perp on Binance @ $69,800
3. $300 spread per BTC captured

Position Size: 1 BTC
Profit: $300 per BTC (0.43% return)

On $100k capital (20x leverage):
- Trade 2.88 BTC
- Profit: $864 per convergence
- If 2-3 opportunities per day: $1,700-2,500/day
```

**Requirements**:
- Capital on both Hyperliquid and Binance
- Fast execution (spreads close quickly)
- Monitor both order books in real-time
- Account for funding rate differences

---

#### **Strategy 4: Hyperliquid + DEX Meme Coin Arbitrage**

**Concept**: New meme coins often launch perps on Hyperliquid before/after spot DEX listings.

**Scenario A - Perp Launches First**:
```
1. PEPE2 perp launches on Hyperliquid at $0.0001
2. Speculation drives perp to $0.00015 (50% premium)
3. Spot launches on Raydium at $0.0001
4. Arbitrage: Buy spot @ $0.0001, Short perp @ $0.00015
5. Wait for convergence (usually 1-24 hours)
6. Profit: 50% spread capture
```

**Scenario B - Spot Launches First**:
```
1. DOGE2 launches on pump.fun (Solana) at $0.001
2. Price pumps to $0.005 in first hour
3. Hyperliquid lists perp at $0.006 (20% premium due to hype)
4. Arbitrage: Buy spot @ $0.005, Short perp @ $0.006
5. Capture 20% spread
```

---

#### **Strategy 5: Liquidation Cascade Arbitrage**

**Concept**: During high volatility, mass liquidations create temporary mispricings.

**Example**:
```
Market Event: BTC dumps 10% in 5 minutes

What Happens:
1. Overleveraged longs get liquidated on Hyperliquid
2. Liquidation engine dumps at market → price overshoots down
3. Spot DEXes react slower (less leverage, less panic)
4. Temporary spread: Hyperliquid $62,000 vs Uniswap $63,500

Execution (FAST - 30 seconds window):
1. BUY BTC perp on Hyperliquid @ $62,000
2. SELL BTC on Uniswap @ $63,500
3. $1,500 spread capture per BTC

Risk: Must execute VERY fast (spread closes in 30-60 seconds)
```

---

### 9.8.1 Hyperliquid Technical Integration Requirements

**API Integration**:
```python
# Hyperliquid Python SDK
from hyperliquid.api import HyperliquidAPI
from hyperliquid.utils import sign_message

class HyperliquidArbitrageEngine:
    def __init__(self, private_key):
        self.api = HyperliquidAPI(private_key)
        self.websocket = self.api.connect_websocket()

    def get_perpetual_price(self, symbol):
        """Get current perpetual contract price"""
        return self.api.get_mark_price(symbol)

    def get_funding_rate(self, symbol):
        """Get current funding rate (updated every 8h)"""
        return self.api.get_funding_rate(symbol)

    def open_short_position(self, symbol, size, leverage):
        """Open short perpetual position"""
        order = self.api.market_order(
            symbol=symbol,
            side='sell',
            size=size,
            leverage=leverage,
            reduce_only=False
        )
        return order

    def monitor_basis_spread(self, symbol, spot_price):
        """Calculate perp-spot basis"""
        perp_price = self.get_perpetual_price(symbol)
        basis = (perp_price - spot_price) / spot_price * 100
        return basis  # Return as percentage

    def execute_funding_arbitrage(self, symbol, size):
        """
        Full funding rate arbitrage execution:
        1. Check funding rate > threshold
        2. Open perp position
        3. Hedge with spot on DEX
        4. Monitor and close when unprofitable
        """
        funding_rate = self.get_funding_rate(symbol)

        if funding_rate > 0.01:  # 0.01% threshold
            # Long perp (receive funding if positive)
            perp_order = self.api.market_order(
                symbol=symbol,
                side='buy',
                size=size,
                leverage=1  # Delta-neutral, no leverage needed
            )

            # Execute spot hedge on DEX to remain delta-neutral
            # NOTE: Spot hedge implementation uses DEX aggregator (1inch/Jupiter)
            # See integrations/dex/aggregator_adapter.py for implementation
            # aggregator = AggregatorFactory.get_aggregator(chain='ethereum')
            # quote = await aggregator.get_quote(input_token, output_token, size, slippage_bps=50)
            # await aggregator.execute_swap(quote, wallet_address)

            return {'status': 'opened', 'funding_rate': funding_rate}
```

**Real-Time Monitoring**:
```python
# WebSocket for real-time price updates
def monitor_arbitrage_opportunities():
    """Monitor perp-spot spreads in real-time"""

    # Connect to Hyperliquid WebSocket
    hl_ws = hyperliquid_websocket.connect()

    # Connect to DEX price feeds
    uniswap_ws = uniswap_price_feed.connect()
    raydium_ws = raydium_price_feed.connect()

    while True:
        # Get prices
        btc_perp_price = hl_ws.get_price('BTC')
        btc_spot_price = uniswap_ws.get_price('WBTC/USDC')

        # Calculate spread
        spread_percent = (btc_perp_price - btc_spot_price) / btc_spot_price * 100

        # Alert if opportunity
        if abs(spread_percent) > 2.0:  # 2% threshold
            execute_arbitrage('BTC', btc_perp_price, btc_spot_price, spread_percent)
```

**Database Schema for Hyperliquid**:
```sql
-- Track perpetual positions
CREATE TABLE hyperliquid_positions (
    position_id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    side VARCHAR,  -- 'long' or 'short'
    size DECIMAL(30, 6),
    entry_price DECIMAL(30, 10),
    leverage INTEGER,
    liquidation_price DECIMAL(30, 10),
    unrealized_pnl DECIMAL(30, 6),
    hedged_with VARCHAR,  -- 'uniswap', 'raydium', etc.
    hedge_tx_hash VARCHAR,
    funding_earned DECIMAL(30, 6),
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    status VARCHAR  -- 'open', 'closed', 'liquidated'
);

-- Track funding rate history
CREATE TABLE hyperliquid_funding_rates (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    funding_rate FLOAT,  -- Percentage per 8 hours
    predicted_rate FLOAT,
    annualized_apy FLOAT,  -- (funding_rate * 3 * 365)
    PRIMARY KEY (timestamp, symbol)
);

-- Track basis spreads
CREATE TABLE perp_spot_basis (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    perp_price DECIMAL(30, 10),
    spot_price DECIMAL(30, 10),
    basis_percent FLOAT,
    venue VARCHAR,  -- Which DEX for spot
    opportunity_score FLOAT,  -- Basis - fees - slippage
    PRIMARY KEY (timestamp, symbol, venue)
);
```

---

### 9.9 Cross-Exchange Arbitrage System (Traditional)

**CEX-DEX Arbitrage**:
```
Opportunity: BTC is $50,000 on Binance, $50,500 on Uniswap

Execution:
1. Buy BTC on Binance (CEX)
2. Transfer to Ethereum wallet
3. Swap BTC → WETH on Uniswap (DEX)
4. Transfer WETH back or keep for next trade

Considerations:
- Withdrawal time from CEX (minutes to hours)
- Gas costs on Ethereum
- Bridge fees if using wrapped BTC
- Slippage on DEX
```

**DEX-DEX Arbitrage (Same Chain)**:
```
Opportunity: PEPE is $0.001000 on Uniswap, $0.001050 on SushiSwap

Execution:
1. Buy PEPE on Uniswap
2. Sell PEPE on SushiSwap
3. Profit = (0.001050 - 0.001000) * amount - gas - fees

Optimization:
- Use flashloan to avoid needing capital
- Execute atomically (no risk)
```

**Cross-Chain Arbitrage**:
```
Opportunity: SOL is $100 on Solana DEXes, $102 on BSC DEXes

Execution:
1. Buy SOL on Raydium (Solana)
2. Bridge SOL to BSC via Wormhole
3. Sell wrapped SOL on PancakeSwap (BSC)
4. Bridge USDC back to Solana

Considerations:
- Bridge time (2-30 minutes)
- Bridge fees (0.1-0.3%)
- Price movement during bridge
- Gas on multiple chains
```

### 9.9 DuckDB Schema Extensions for DEX Trading

**New Tables**:

**Table: dex_pools**
```sql
CREATE TABLE dex_pools (
    pool_id VARCHAR PRIMARY KEY,
    chain VARCHAR,  -- 'ethereum', 'solana', 'bsc', 'arbitrum', etc.
    dex VARCHAR,    -- 'uniswap_v3', 'raydium', 'pancakeswap', etc.
    pool_address VARCHAR,
    token0 VARCHAR,
    token1 VARCHAR,
    fee_tier FLOAT,
    liquidity DECIMAL(30, 6),
    volume_24h DECIMAL(30, 6),
    price_token0 DECIMAL(30, 10),
    price_token1 DECIMAL(30, 10),
    last_updated TIMESTAMP
);
CREATE INDEX idx_dex_pools_chain ON dex_pools(chain, dex);
CREATE INDEX idx_dex_pools_tokens ON dex_pools(token0, token1);
```

**Table: aggregator_quotes**
```sql
CREATE TABLE aggregator_quotes (
    quote_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    chain VARCHAR,
    aggregator VARCHAR,  -- 'jupiter', '1inch', 'matcha', 'paraswap'
    token_in VARCHAR,
    token_out VARCHAR,
    amount_in DECIMAL(30, 6),
    amount_out DECIMAL(30, 6),
    estimated_slippage FLOAT,
    estimated_gas DECIMAL(18, 6),
    quote_data JSON,  -- Full quote response from aggregator
    executed BOOLEAN,
    execution_tx VARCHAR,
    actual_amount_out DECIMAL(30, 6),
    actual_slippage FLOAT
);
CREATE INDEX idx_quotes_chain ON aggregator_quotes(chain, timestamp);
CREATE INDEX idx_quotes_tokens ON aggregator_quotes(token_in, token_out);
```

**Table: arbitrage_opportunities**
```sql
CREATE TABLE arbitrage_opportunities (
    opportunity_id VARCHAR PRIMARY KEY,
    detected_at TIMESTAMP,
    arb_type VARCHAR,  -- 'cex_dex', 'dex_dex', 'cross_chain'
    token VARCHAR,
    buy_exchange VARCHAR,
    sell_exchange VARCHAR,
    buy_price DECIMAL(30, 10),
    sell_price DECIMAL(30, 10),
    spread_percent FLOAT,
    estimated_profit DECIMAL(30, 6),
    gas_cost DECIMAL(30, 6),
    net_profit DECIMAL(30, 6),
    executed BOOLEAN,
    execution_time TIMESTAMP,
    actual_profit DECIMAL(30, 6)
);
CREATE INDEX idx_arb_detected ON arbitrage_opportunities(detected_at);
CREATE INDEX idx_arb_executed ON arbitrage_opportunities(executed, net_profit);
```

**Table: meme_coin_tracker**
```sql
CREATE TABLE meme_coin_tracker (
    token_address VARCHAR PRIMARY KEY,
    token_symbol VARCHAR,
    chain VARCHAR,
    first_seen TIMESTAMP,
    pool_address VARCHAR,
    initial_liquidity DECIMAL(30, 6),
    current_liquidity DECIMAL(30, 6),
    liquidity_locked BOOLEAN,
    holder_count INTEGER,
    top_10_holders_percent FLOAT,
    contract_verified BOOLEAN,
    honeypot_risk FLOAT,  -- 0.0 to 1.0
    social_score FLOAT,
    volume_24h DECIMAL(30, 6),
    price_change_24h FLOAT,
    our_position DECIMAL(30, 6),
    our_entry_price DECIMAL(30, 10),
    status VARCHAR  -- 'monitoring', 'entered', 'exited', 'scam'
);
CREATE INDEX idx_meme_status ON meme_coin_tracker(status);
CREATE INDEX idx_meme_first_seen ON meme_coin_tracker(first_seen);
```

**Table: gas_prices**
```sql
CREATE TABLE gas_prices (
    timestamp TIMESTAMP,
    chain VARCHAR,
    gas_price_gwei FLOAT,
    base_fee FLOAT,  -- EIP-1559
    priority_fee FLOAT,  -- EIP-1559
    fast_gas FLOAT,
    average_gas FLOAT,
    slow_gas FLOAT,
    PRIMARY KEY (timestamp, chain)
);
CREATE INDEX idx_gas_chain_time ON gas_prices(chain, timestamp);
```

### 9.10 Execution Engine Components

**Web3 Integration Module**:
```python
class MultiChainExecutor:
    def __init__(self):
        self.eth_web3 = Web3(Web3.HTTPProvider(ETH_RPC))
        self.bsc_web3 = Web3(Web3.HTTPProvider(BSC_RPC))
        self.polygon_web3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
        self.solana_client = SolanaClient(SOLANA_RPC)

    def execute_aggregator_swap(self, chain, aggregator, quote, slippage):
        """
        Execute swap using aggregator quote
        - Get quote from aggregator (Jupiter, 1inch, etc.)
        - Build transaction from aggregator's swap data
        - Estimate gas
        - Sign with private key
        - Broadcast transaction
        - Monitor for confirmation
        """

    def execute_flashloan_arbitrage(self, aggregator_quote, amount):
        """
        Execute atomic arbitrage using flashloan
        - Borrow from Aave/dYdX
        - Execute swap sequence using aggregator
        - Repay loan + fee
        - Keep profit
        - All in single transaction (reverts if not profitable)
        """
```

**MEV Protection**:
```python
class MEVProtection:
    """
    Protect against front-running and sandwich attacks
    """
    def use_private_mempool(self, transaction):
        # Send via Flashbots or other private relay
        # Prevents public mempool exposure

    def use_limit_orders(self, order):
        # Use 1inch Limit Order Protocol
        # Execute only at specified price

    def split_large_trades(self, trade):
        # Break into smaller transactions
        # Reduce price impact and MEV profit opportunity
```

### 9.11 Risk Management for DEX Trading

**DEX-Specific Risks**:
```python
class DEXRiskManager:
    def check_liquidity(self, pool, trade_amount):
        """
        Ensure sufficient liquidity to prevent excessive slippage
        - Trade size < 1% of pool liquidity
        - Pool must have > $100k liquidity
        """

    def check_contract_risk(self, token_address):
        """
        Verify token contract safety
        - Check for honeypot characteristics
        - Verify no unlimited mint function
        - Check for transfer restrictions
        - Verify liquidity lock
        """

    def gas_limit_check(self, estimated_gas):
        """
        Ensure gas cost doesn't exceed profit
        - Gas cost < 30% of expected profit
        - Abort if gas > threshold
        """

    def bridge_risk_assessment(self, chain_from, chain_to, amount):
        """
        Assess cross-chain bridge risks
        - Bridge reliability score
        - Historical bridge failure rate
        - Amount limits
        - Time exposure during bridge
        """
```

**Position Limits for Meme Coins**:
- Max 1% of portfolio per meme coin
- Max 5% total allocation to meme coins
- No time-based exits (hold as long as trailing stop not hit)
- 0.5% trailing stop (same as all markets)

### 9.12 Monitoring & Alerting for DEX Operations

**Critical Alerts**:
- Arbitrage opportunity detected (>2% profit)
- Meme coin entry signal (score >80/100)
- Rug pull detected (liquidity removed)
- Failed transaction (revert)
- Gas price spike (>200 gwei)
- Bridge delay (>expected time)
- Slippage exceeded limit
- Contract interaction failed

**Dashboard Metrics**:
- DEX pools monitored: 500+
- Active arbitrage opportunities: 50+
- Meme coins tracked: 100+
- 24h arbitrage profit
- Average slippage
- Gas costs by chain
- Bridge success rate

### 9.13 Expected Performance Metrics

**DEX Trading Performance**:
- Aggregator quote fetch: <50ms per quote
- Arbitrage detection: <100ms per opportunity
- Transaction execution: 15-30 seconds (depends on chain)
- Meme coin detection latency: <5 seconds after pool creation
- Cost savings: Aggregators automatically optimize for best price and fees

**Profitability Targets**:
- DEX arbitrage: 2-5% per profitable trade
- Meme coin trading: 50-200% per winning trade (high variance)
- CEX-DEX arbitrage: 0.5-2% per trade
- Cross-chain arbitrage: 1-3% per trade

**Risk Metrics**:
- Meme coin win rate target: 40-50%
- Maximum loss per meme coin: 0.5% (trailing stop, same as all markets)
- Arbitrage success rate: >85%
- Failed transaction rate: <5%

---

## 10. Forex Trading Integration

### 9.1 Overview

The Forex trading module extends the algo-engine to traditional forex markets (EUR/USD, GBP/USD, XAU/USD, etc.) through integration with multiple forex trading platforms. This runs **separately** from crypto trading but uses the same core decision engine, risk management, and analytics infrastructure.

**Key Separation**:
- **Crypto Trading**: Binance (spot/futures) + DEXes (Ethereum, Solana, Base, etc.)
- **Forex Trading**: MT5, MatchTrader, TradeLocker, cTrader
- **Shared Components**: Core decision engine, risk management, DuckDB analytics, notifications

---

### 9.2 Broker & Prop Firm Configuration System

**CRITICAL**: Each MT5/TradeLocker/MatchTrader/cTrader connection requires specific **broker server details** and **account credentials**. The algo-engine must support multiple broker/prop firm accounts simultaneously.

---

### 9.3 Supported Forex Platforms

#### **MetaTrader 5 (MT5)** ⭐⭐⭐ - Priority #1
- **Why Priority**: Most widely used, institutional-grade, extensive broker support
- **Integration**: Python via `MetaTrader5` package or REST/WebSocket API bridges
- **Features**:
  - Real-time tick data for all major pairs
  - Multi-timeframe analysis (M1, M5, M15 for ultra-short scalping)
  - Expert Advisors (EA) support for custom strategies
  - Built-in technical indicators
  - Market depth (Level II data)
  - One-click trading and pending orders
- **Connection Methods**:
  - **Direct Python API**: `import MetaTrader5 as mt5`
  - **REST API Bridge**: Custom API wrapper for remote access
  - **FIX Protocol**: For institutional brokers

**Supported Brokers & Prop Firms**:

**Retail Brokers**:
- **IC Markets**: Server: `ICMarketsSC-Demo`, `ICMarketsSC-Live`
- **Pepperstone**: Server: `Pepperstone-Demo`, `Pepperstone-Live`
- **FP Markets**: Server: `FPMarkets-Demo`, `FPMarkets-Live`
- **Fusion Markets**: Server: `FusionMarkets-Demo`, `FusionMarkets-Live`
- **Exness**: Server: `Exness-MT5Real`, `Exness-MT5Demo`
- **XM Global**: Server: `XM-MT5`, `XM-MT5 2`
- **IG Markets**: Server: `IG-Demo`, `IG-Live`

**Prop Trading Firms** (Funded Accounts):
- **FTMO**: Server: `FTMO-Server`, `FTMO-Server2`, `FTMO-Demo`
  - Challenge accounts, funded accounts
  - Strict rules: max 5% daily loss, 10% total drawdown
- **MyForexFunds (MFF)**: Server: `MyForexFunds-Server`
  - Rapid, Evaluation, Accelerated programs
- **The5ers**: Server: `The5ers-Server`
  - Hyper Growth, Bootcamp programs
- **Funded Next**: Server: `FundedNext-Server`
  - Express, Evaluation models
- **Funded Trading Plus**: Server: `FundedTradingPlus-Server`
- **E8 Funding**: Server: `E8Funding-Server`
- **True Forex Funds**: Server: `TrueForexFunds-Server`
- **Apex Trader Funding**: Server: `ApexTrader-Server`
- **TopStep Trader**: Server: `TopStep-Server` (Futures + Forex)

**Each broker/prop firm has**:
- Unique server address
- Different account number format
- Specific password requirements
- Different trading rules and limits

**Latency**: 10-50ms execution (depends on broker/server location)

#### **MatchTrader** ⭐⭐
- **Why Include**: Popular in Asia/Middle East, multi-asset support
- **Integration**: REST API + WebSocket
- **Features**:
  - Web-based platform (no desktop app required)
  - Multi-asset support (forex, crypto, commodities)
  - Social trading features
  - Copy trading support
- **API Documentation**: MatchTrader API (typically proprietary per broker)
- **Brokers**: Leverate-powered brokers, VantageFX, etc.
- **Best For**: Brokers offering both forex and crypto on same platform

#### **TradeLocker** ⭐⭐
- **Why Include**: Modern platform, growing adoption, excellent API
- **Integration**: REST API + WebSocket (well-documented)
- **Features**:
  - Cloud-based, no installation needed
  - Modern UI/UX
  - Multi-asset support
  - Advanced charting
  - API-first design (great for algo trading)
- **API Docs**: https://tradelocker.com/developers
- **Brokers**: Ox Securities, TradeLocker-powered brokers
- **Latency**: Very low (cloud-native architecture)

#### **cTrader** ⭐⭐
- **Why Include**: Professional-grade, institutional features, strong API
- **Integration**: cTrader Automate (C# based) + FIX API
- **Features**:
  - Level II pricing (market depth)
  - cAlgo for algorithmic trading
  - Advanced order types (OCO, trailing stops, etc.)
  - TradingView integration
  - Copy trading
- **Integration Method**:
  - **cTrader Open API**: REST + WebSocket
  - **FIX Protocol**: For institutional connections
  - **cAlgo**: C# robots (can call Python via IPC)
- **Brokers**: IC Markets, Pepperstone, FxPro, Spotware brokers
- **Best For**: Scalping, high-frequency forex strategies

---

### 9.4 Broker/Prop Firm Account Configuration Management

**Firestore Collection: `forex_accounts`**

Store all broker and prop firm account configurations:

```json
{
  "account_id": "ftmo_challenge_001",
  "platform": "mt5",
  "broker_name": "FTMO",
  "broker_type": "prop_firm",
  "server": "FTMO-Server",
  "account_number": "5001234567",
  "password": "encrypted_password_hash",
  "account_type": "challenge",

  "rules": {
    "max_daily_loss_percent": 5.0,
    "max_total_loss_percent": 10.0,
    "profit_target": 10000.00,
    "allow_news_trading": false
  },

  "status": "active",
  "enabled": true
}
```

**Multi-Account Management System**:

```python
class ForexAccountManager:
    """Manage multiple broker/prop firm accounts"""

    def __init__(self):
        self.accounts = {}
        self.load_accounts_from_firestore()

    def connect_account(self, account_data):
        """Connect to broker/prop firm with specific server"""
        executor = MT5ForexExecutor(
            account=account_data['account_number'],
            password=decrypt(account_data['password']),
            server=account_data['server']  # CRITICAL: Broker-specific server
        )
        self.accounts[account_data['account_id']] = executor

    def check_prop_firm_rules(self, account_id):
        """Enforce prop firm rules before trading"""
        # Check daily loss limits, max drawdown, etc.
        # Pause account if rules violated

    def copy_trade_to_multiple_accounts(self, symbol, side, volume, account_ids):
        """Execute same trade across multiple accounts"""
        for account_id in account_ids:
            self.execute_trade_on_account(account_id, symbol, side, volume)
```

**API Endpoints**:
- `POST /api/v1/forex/accounts/add` - Add broker/prop firm account
- `GET /api/v1/forex/accounts` - List all accounts
- `POST /api/v1/forex/trade` - Execute on specific account(s)

---

### 9.5 Forex Architecture Integration

```
┌──────────────────────────────────────────────────────────────┐
│              Algo-Engine Core (Shared Infrastructure)         │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Core Decision  │  │ Risk Manager   │  │  DuckDB       │  │
│  │    Engine      │  │                │  │  Analytics    │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────────┘
              │                                    │
    ┌─────────┴────────┐                  ┌───────┴────────┐
    │                  │                  │                │
    ▼                  ▼                  ▼                ▼
┌─────────┐      ┌──────────┐      ┌─────────┐     ┌─────────┐
│ Crypto  │      │  Forex   │      │  Crypto │     │  Forex  │
│ Executor│      │ Account  │      │  Data   │     │  Data   │
│         │      │ Manager  │      │ Storage │     │ Storage │
│ Binance │      │          │      │         │     │         │
│  DEXes  │      │ ┌──────┐ │      │ /crypto/│     │ /forex/ │
└─────────┘      │ │FTMO  │ │      └─────────┘     └─────────┘
                 │ │MFF   │ │
                 │ │IC Mkt│ │
                 │ │Pepper│ │
                 │ └──────┘ │
                 └──────────┘
```

**Key Principles**:
- **Multi-broker support**: Connect to FTMO, MFF, IC Markets, Pepperstone simultaneously
- **Prop firm rules**: Auto-enforce daily loss limits, max drawdown
- **Copy trading**: Replicate trades across all accounts
- **Separate execution**: Forex and crypto run independently
- **Shared infrastructure**: Same decision engine, risk management, analytics

---

### 9.6 Forex Platform Integration Details

#### **MT5 Python Integration**

```python
import MetaTrader5 as mt5
from datetime import datetime

class MT5ForexExecutor:
    def __init__(self, account, password, server):
        self.account = account
        self.server = server

        # Initialize MT5 connection
        if not mt5.initialize():
            print("MT5 initialization failed")
            return

        # Login to trading account
        authorized = mt5.login(account, password=password, server=server)
        if authorized:
            print(f"Connected to MT5 account {account}")
        else:
            print("MT5 login failed")

    def get_tick_data(self, symbol):
        """Get latest tick data for symbol"""
        tick = mt5.symbol_info_tick(symbol)
        return {
            'symbol': symbol,
            'bid': tick.bid,
            'ask': tick.ask,
            'last': tick.last,
            'volume': tick.volume,
            'time': datetime.fromtimestamp(tick.time)
        }

    def get_candles(self, symbol, timeframe, count=100):
        """
        Get OHLCV candles
        timeframe: mt5.TIMEFRAME_M1, M5, M15
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        return rates  # Returns numpy array with OHLCV data

    def place_market_order(self, symbol, order_type, volume, sl=None, tp=None):
        """
        Place market order
        order_type: 'buy' or 'sell'
        volume: lot size (0.01 = micro lot, 0.1 = mini lot, 1.0 = standard lot)
        """
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {'error': 'Symbol not found'}

        # Prepare request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if order_type == 'buy' else mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(symbol).ask if order_type == 'buy' else mt5.symbol_info_tick(symbol).bid,
            "sl": sl,
            "tp": tp,
            "deviation": 10,  # Max price deviation in points
            "magic": 234000,  # EA identifier
            "comment": "algo-engine",
            "type_time": mt5.ORDER_TIME_GTC,  # Good till cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,  # Immediate or cancel
        }

        # Send order
        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {'error': result.comment, 'retcode': result.retcode}

        return {
            'success': True,
            'order_id': result.order,
            'volume': result.volume,
            'price': result.price
        }

    def close_position(self, ticket):
        """Close open position by ticket number"""
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            return {'error': 'Position not found'}

        position = position[0]

        # Prepare close request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": 10,
            "magic": 234000,
            "comment": "algo-engine close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        return {'success': result.retcode == mt5.TRADE_RETCODE_DONE}

    def get_open_positions(self):
        """Get all open positions"""
        positions = mt5.positions_get()
        if positions is None:
            return []

        return [{
            'ticket': pos.ticket,
            'symbol': pos.symbol,
            'type': 'buy' if pos.type == mt5.POSITION_TYPE_BUY else 'sell',
            'volume': pos.volume,
            'price_open': pos.price_open,
            'price_current': pos.price_current,
            'profit': pos.profit,
            'sl': pos.sl,
            'tp': pos.tp
        } for pos in positions]

    def get_account_info(self):
        """Get account balance and equity"""
        account_info = mt5.account_info()
        return {
            'balance': account_info.balance,
            'equity': account_info.equity,
            'margin': account_info.margin,
            'free_margin': account_info.margin_free,
            'margin_level': account_info.margin_level,
            'profit': account_info.profit
        }
```

#### **TradeLocker REST API Integration**

```python
import requests
import hmac
import hashlib
import time

class TradeLockerExecutor:
    def __init__(self, api_key, api_secret, account_id):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.base_url = "https://api.tradelocker.com"

    def _generate_signature(self, endpoint, body=""):
        """Generate HMAC signature for authentication"""
        timestamp = str(int(time.time() * 1000))
        message = timestamp + endpoint + body
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp

    def get_quotes(self, symbols):
        """Get real-time quotes for multiple symbols"""
        endpoint = "/v1/quotes"
        signature, timestamp = self._generate_signature(endpoint)

        headers = {
            "X-API-Key": self.api_key,
            "X-Signature": signature,
            "X-Timestamp": timestamp
        }

        params = {"symbols": ",".join(symbols)}
        response = requests.get(f"{self.base_url}{endpoint}", headers=headers, params=params)
        return response.json()

    def place_order(self, symbol, side, volume, order_type="market"):
        """Place order on TradeLocker"""
        endpoint = "/v1/orders"

        body = {
            "accountId": self.account_id,
            "symbol": symbol,
            "side": side,  # "buy" or "sell"
            "volume": volume,
            "type": order_type,  # "market" or "limit"
        }

        signature, timestamp = self._generate_signature(endpoint, str(body))

        headers = {
            "X-API-Key": self.api_key,
            "X-Signature": signature,
            "X-Timestamp": timestamp,
            "Content-Type": "application/json"
        }

        response = requests.post(f"{self.base_url}{endpoint}", headers=headers, json=body)
        return response.json()
```

#### **MatchTrader Integration**

```python
class MatchTraderExecutor:
    def __init__(self, broker_url, username, password):
        self.base_url = broker_url  # Broker-specific URL
        self.token = None
        self.login(username, password)

    def login(self, username, password):
        """Authenticate with MatchTrader"""
        response = requests.post(f"{self.base_url}/api/auth/login", json={
            "username": username,
            "password": password
        })

        if response.status_code == 200:
            self.token = response.json()['token']
        else:
            raise Exception("MatchTrader login failed")

    def get_quotes(self, symbols):
        """Get real-time quotes"""
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(
            f"{self.base_url}/api/quotes",
            headers=headers,
            params={"symbols": ",".join(symbols)}
        )
        return response.json()

    def place_order(self, symbol, side, volume):
        """Place market order"""
        headers = {"Authorization": f"Bearer {self.token}"}
        body = {
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "type": "market"
        }
        response = requests.post(f"{self.base_url}/api/orders", headers=headers, json=body)
        return response.json()
```

#### **cTrader Integration (via Open API)**

```python
import asyncio
import websockets
import json

class CTraderExecutor:
    def __init__(self, client_id, client_secret, account_id):
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.base_url = "https://openapi.ctrader.com"
        self.ws_url = "wss://openapi.ctrader.com/websocket"
        self.access_token = None

    def authenticate(self):
        """Get OAuth2 access token"""
        response = requests.post(f"{self.base_url}/oauth/token", data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        })

        if response.status_code == 200:
            self.access_token = response.json()['access_token']

    async def subscribe_to_quotes(self, symbols):
        """Subscribe to real-time quotes via WebSocket"""
        async with websockets.connect(self.ws_url) as websocket:
            # Authenticate
            auth_message = {
                "payloadType": "PROTO_OA_APPLICATION_AUTH_REQ",
                "clientId": self.client_id,
                "clientSecret": self.client_secret
            }
            await websocket.send(json.dumps(auth_message))

            # Subscribe to symbols
            subscribe_message = {
                "payloadType": "PROTO_OA_SUBSCRIBE_SPOTS_REQ",
                "ctidTraderAccountId": self.account_id,
                "symbolId": symbols
            }
            await websocket.send(json.dumps(subscribe_message))

            # Listen for quotes
            async for message in websocket:
                data = json.loads(message)
                if data['payloadType'] == 'PROTO_OA_SPOT_EVENT':
                    yield data  # Real-time tick data

    def place_market_order(self, symbol_id, volume, trade_side):
        """Place market order via REST API"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        body = {
            "ctidTraderAccountId": self.account_id,
            "symbolId": symbol_id,
            "orderType": "MARKET",
            "tradeSide": trade_side,  # "BUY" or "SELL"
            "volume": volume
        }
        response = requests.post(
            f"{self.base_url}/v2/orders",
            headers=headers,
            json=body
        )
        return response.json()
```

---

### 9.5 Forex Trading Strategies

#### **Strategy 1: Multi-Timeframe Forex Scalping**
- Use same order flow + market profile logic from crypto
- Timeframes: M1 (signal), M5 (filter), M15 (trend)
- Targets: 5-15 pip moves, 1:2 R:R
- Best pairs: EUR/USD, GBP/USD, USD/JPY (tight spreads)

#### **Strategy 2: Session-Based Trading**
- Trade London open (8am GMT) and NY open (1pm GMT)
- High volatility = more opportunities
- Use same supply/demand zones from crypto strategies

#### **Strategy 3: Gold (XAU/USD) Volatility Trading**
- High volatility = large pip moves
- Apply same FVG detection from crypto
- Target 20-50 pip moves

#### **Strategy 4: Correlation Trading**
- Monitor DXY (Dollar Index) for USD strength
- EUR/USD inverse correlation with DXY
- Trade based on currency strength divergence

---

### 9.6 Database Schema for Forex Data

```sql
-- Forex tick data (per broker/platform)
CREATE TABLE forex_ticks (
    timestamp TIMESTAMP,
    platform VARCHAR,  -- 'mt5', 'tradelocker', 'matchtrader', 'ctrader'
    broker VARCHAR,    -- 'ic_markets', 'pepperstone', etc.
    symbol VARCHAR,    -- 'EURUSD', 'GBPUSD', 'XAUUSD'
    bid DECIMAL(20, 5),
    ask DECIMAL(20, 5),
    spread_pips FLOAT,
    volume BIGINT,
    PRIMARY KEY (timestamp, platform, symbol)
);

-- Forex candles (aggregated from ticks)
CREATE TABLE forex_candles_m1 (
    timestamp TIMESTAMP,
    platform VARCHAR,
    broker VARCHAR,
    symbol VARCHAR,
    open DECIMAL(20, 5),
    high DECIMAL(20, 5),
    low DECIMAL(20, 5),
    close DECIMAL(20, 5),
    volume BIGINT,
    tick_volume BIGINT,
    PRIMARY KEY (timestamp, platform, symbol)
);

-- Forex positions
CREATE TABLE forex_positions (
    position_id VARCHAR PRIMARY KEY,
    platform VARCHAR,
    broker VARCHAR,
    symbol VARCHAR,
    side VARCHAR,  -- 'buy' or 'sell'
    volume DECIMAL(10, 2),  -- Lot size
    entry_price DECIMAL(20, 5),
    current_price DECIMAL(20, 5),
    profit_pips FLOAT,
    profit_usd DECIMAL(30, 2),
    sl DECIMAL(20, 5),
    tp DECIMAL(20, 5),
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    status VARCHAR  -- 'open', 'closed', 'stopped_out'
);
```

---

### 9.7 Risk Management for Forex

**Forex-Specific Risks**:
- **Leverage Risk**: MT5 allows up to 500:1 leverage (use conservatively)
- **Spread Widening**: During news events, spreads can widen 10x
- **Slippage**: Fast markets = execution price different from expected
- **Swap Fees**: Holding positions overnight incurs interest charges
- **Weekend Gaps**: Markets closed Sat/Sun, can gap on Monday open

**Risk Limits**:
- Max 2% risk per trade
- Max 5 concurrent forex positions
- No trading during major news events (NFP, FOMC, etc.)
- Stop-loss mandatory on all positions
- Max leverage: 10:1 (even if broker allows higher)

---

### 9.8 Expected Performance (Forex)

**Target Metrics**:
- Win rate: 55-65% (scalping strategies)
- Average R:R: 1:1.5 to 1:2
- Monthly return: 5-15% (conservative)
- Max drawdown: <10%
- Trades per day: 10-30 (per pair)

**Advantages Over Crypto**:
- Lower volatility (more predictable)
- Tighter spreads on majors
- No gas fees or blockchain delays
- 24/5 markets (vs 24/7 crypto)
- Regulatory oversight (more reliable brokers)

---

## 11. Critical Architecture Requirements ⭐

### 12.1 Asynchronous Architecture (Non-Blocking I/O) ⭐⭐⭐

**Design Principle:**
**ALL I/O operations MUST use async/await** to ensure non-blocking execution and maximum concurrency. This is **non-negotiable** for achieving 100+ symbol throughput.

**Async Components (REQUIRED)**:
1. **WebSocket Data Streams**: Async message handling from exchanges
2. **Database Operations**: Async DuckDB queries via `asyncio.to_thread()`
3. **Exchange API Calls**: Async order placement and position queries
4. **Position Monitoring**: Async price checks and stop updates
5. **API Server**: FastAPI (native async support)

**Implementation Requirements**:
```python
# ALL I/O functions must be async
async def store_tick(symbol: str, tick: dict):
    """Store tick data asynchronously"""
    await asyncio.to_thread(db.execute, query, params)

async def fetch_market_data(symbol: str):
    """Fetch market data asynchronously"""
    return await exchange_client.fetch_ticker(symbol)

async def place_order(symbol: str, side: str, quantity: float):
    """Place order asynchronously"""
    return await exchange_client.create_order(...)

# Main event loop runs all tasks concurrently
async def main():
    await asyncio.gather(
        market_data_stream.start(),
        decision_engine.run(),
        position_monitor.start(),
        api_server.start()
    )
```

**Performance Impact**:
- **Synchronous I/O**: 10 symbols/second max throughput
- **Asynchronous I/O**: 100+ symbols/second throughput
- **Latency Reduction**: 50-200ms per operation
- **CPU Efficiency**: Single thread handles many operations

**Benefits**:
- Handle 100+ symbols concurrently in single thread
- WebSocket messages processed immediately without blocking
- Database writes don't block signal generation
- Order execution doesn't block monitoring loop
- Efficient CPU and memory usage

---

### 12.2 Position Reconciliation on Startup ⭐⭐

**Purpose**: Reconcile positions between local state (Firestore) and exchange state on every startup. **Critical** for recovering from crashes or unexpected shutdowns.

**When to Run**: **BEFORE** starting any trading activity.

**Implementation**:
```python
# src/services/position_reconciliation.py
class PositionReconciliationService:
    """
    Reconciles positions between local state and exchange on startup.
    """

    async def reconcile_positions(self):
        """
        Compare local state (Firestore) with exchange state.
        Resolve any discrepancies before starting trading.
        """
        logger.info("Starting position reconciliation...")

        # Step 1: Get positions from Firestore (local state)
        firestore_positions = await self._get_firestore_positions()

        # Step 2: Get positions from exchange (source of truth)
        exchange_positions = await self._get_exchange_positions()

        # Step 3: Compare and reconcile
        discrepancies = self._find_discrepancies(
            firestore_positions,
            exchange_positions
        )

        if not discrepancies:
            logger.info("✅ All positions reconciled - no discrepancies found")
            return

        # Step 4: Resolve discrepancies
        for discrepancy in discrepancies:
            await self._resolve_discrepancy(discrepancy)

        logger.info(f"✅ Position reconciliation complete ({len(discrepancies)} resolved)")

    def _find_discrepancies(self, local, exchange):
        """Find differences between local and exchange state"""
        discrepancies = []

        # Check for positions in Firestore but not on exchange
        for symbol in local.keys():
            if symbol not in exchange:
                discrepancies.append({
                    'type': 'missing_on_exchange',
                    'symbol': symbol,
                    'action': 'Remove from Firestore (position closed)'
                })

        # Check for positions on exchange but not in Firestore
        for symbol in exchange.keys():
            if symbol not in local:
                discrepancies.append({
                    'type': 'missing_in_firestore',
                    'symbol': symbol,
                    'action': 'Import from exchange to Firestore'
                })

        # Check for quantity mismatches
        for symbol in set(local.keys()) & set(exchange.keys()):
            local_qty = float(local[symbol]['quantity'])
            exchange_qty = float(exchange[symbol]['contracts'])

            if abs(local_qty - exchange_qty) > 0.0001:
                discrepancies.append({
                    'type': 'quantity_mismatch',
                    'symbol': symbol,
                    'action': 'Update local quantity to match exchange'
                })

        return discrepancies

# Usage in main.py
async def startup():
    logger.info("Starting Algo Engine...")

    # Initialize services
    exchange = await create_exchange_client()
    firestore = await create_firestore_client()

    # CRITICAL: Reconcile positions BEFORE starting trading
    reconciliation_service = PositionReconciliationService(exchange, firestore)
    await reconciliation_service.reconcile_positions()

    # Now safe to start trading
    await start_trading_engine()
```

**Benefits**:
- **Crash Recovery**: System knows true state after unexpected shutdown
- **Manual Trade Handling**: Detects if operator manually closed position
- **Data Integrity**: Ensures Firestore matches exchange reality
- **Prevents Duplicate Orders**: Won't try to open position that already exists
- **Safe Restart**: System always starts in known-good state

---

### 12.3 Error Handling & Retry Logic ⭐⭐

**Retry with Exponential Backoff**:
```python
# src/core/retry.py
def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )

                    await asyncio.sleep(delay)
                    delay *= backoff_factor

            raise last_exception

        return wrapper
    return decorator

# Usage
@retry_with_backoff(
    max_retries=3,
    initial_delay=1.0,
    exceptions=(NetworkError, RateLimitError)
)
async def fetch_ticker(symbol: str):
    """Fetch ticker with automatic retry"""
    return await exchange.fetch_ticker(symbol)
```

**Circuit Breaker**:
```python
class CircuitBreaker:
    """
    Circuit breaker to prevent hammering failing APIs.
    Opens circuit after threshold failures, closes after cooldown.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.state = 'closed'  # 'closed', 'open', 'half-open'

    def can_attempt(self) -> bool:
        """Check if we can attempt API call"""
        if self.state == 'closed':
            return True

        if self.state == 'open':
            if time.time() - self.last_failure_time > self.cooldown_seconds:
                self.state = 'half-open'
                return True
            return False

        return True  # half-open
```

**Benefits**:
- **Transient Error Recovery**: Network glitches don't break the system
- **Rate Limit Handling**: Automatically backs off when rate limited
- **Prevents API Hammering**: Circuit breaker stops repeated failures
- **Graceful Degradation**: System continues operating despite temporary issues

---

### 12.4 Main Application (Event-Driven 24/7 Operation) ⭐⭐⭐

**The Complete Event-Driven System**:

```python
# main.py
async def main():
    """
    Main entry point - runs 24/7 as event-driven system.

    CORE PRINCIPLE:
    - Event Bus + Data Streaming + Analytics run 24/7
    - Everything else reacts to events
    - SendGrid sends emails for important events
    """

    logger.info("🚀 Starting Algo Engine (Event-Driven Architecture)")

    # 1. Initialize Dependency Injection Container
    container = DependencyContainer()

    # 2. Initialize Event Bus (THE HEART)
    event_bus = EventBus()
    container.register_singleton("EventBus", event_bus)
    logger.info("💓 Event Bus initialized - THE HEART")

    # 3. Initialize SendGrid Notification Service
    sendgrid_service = SendGridNotificationService(
        api_key=os.getenv("SENDGRID_API_KEY"),
        from_email="algo-engine@yourdomain.com",
        to_email=os.getenv("ALERT_EMAIL")
    )
    container.register_singleton("SendGridService", sendgrid_service)
    logger.info("✉️ SendGrid notification service initialized")

    # 4. Initialize Notification System
    notification_system = NotificationSystem(sendgrid_service, event_bus)
    container.register_singleton("NotificationSystem", notification_system)

    # 5. Initialize all other services
    container.register_singleton(
        "ConnectionPool",
        ConnectionPoolManager(max_connections=200)
    )
    container.register_singleton(
        "ExchangeClient",
        BinanceClient(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET")
        )
    )
    container.register_singleton(
        "FirestoreClient",
        FirestoreClient()
    )

    # Register decision engine, execution engine, etc.
    container.register_factory("DecisionEngine", create_decision_engine)
    container.register_factory("ExecutionEngine", create_execution_engine)
    container.register_factory("PositionMonitor", create_position_monitor)
    container.register_factory("AnalyticsEngine", create_analytics_engine)
    container.register_factory("DataStreamingService", create_data_streaming_service)

    # 6. Position Reconciliation (BEFORE trading)
    logger.info("🔄 Reconciling positions with exchange...")
    reconciliation = PositionReconciliationService(
        exchange=container.resolve("ExchangeClient"),
        firestore=container.resolve("FirestoreClient")
    )
    await reconciliation.reconcile_positions()
    logger.info("✅ Position reconciliation complete")

    # 7. Setup Event Subscribers (Wire everything together)
    logger.info("🔌 Wiring up event subscriptions...")
    await setup_event_subscribers(event_bus, container)
    logger.info("✅ Event subscriptions configured")

    # 8. Start ALL Services (24/7 Components + Reactive Components)
    logger.info("🏃 Starting all services...")

    await asyncio.gather(
        # ALWAYS RUNNING (24/7):
        event_bus.process_events(),                      # 💓 THE HEART
        container.resolve("DataStreamingService").start(), # 🔄 Data ingestion
        container.resolve("AnalyticsEngine").start(),      # 📊 Analytics
        container.resolve("PositionMonitor").start(),      # 👁️ Position monitoring
        container.resolve("APIServer").start(),            # 🌐 API server

        # Note: Decision Engine, Execution Engine, Notification System
        # don't need explicit start() - they react to events
    )


async def setup_event_subscribers(event_bus: EventBus, container):
    """
    Wire up all event subscriptions.
    This is where the event-driven magic happens!
    """

    # Resolve all services
    decision_engine = container.resolve("DecisionEngine")
    execution_engine = container.resolve("ExecutionEngine")
    position_monitor = container.resolve("PositionMonitor")
    notification_system = container.resolve("NotificationSystem")
    analytics_engine = container.resolve("AnalyticsEngine")
    data_streaming = container.resolve("DataStreamingService")

    # ============================================
    # DATA STREAMING → ANALYTICS
    # ============================================
    event_bus.subscribe("TradeTickReceived", analytics_engine.on_trade_tick)
    event_bus.subscribe("CandleCompleted", analytics_engine.on_candle_complete)

    # ============================================
    # ANALYTICS → DECISION ENGINE
    # ============================================
    event_bus.subscribe(
        "OrderFlowImbalanceDetected",
        decision_engine.on_order_flow_imbalance
    )
    event_bus.subscribe(
        "MicrostructurePatternDetected",
        decision_engine.on_microstructure_pattern
    )

    # ============================================
    # DECISION ENGINE → EXECUTION ENGINE
    # ============================================
    event_bus.subscribe(
        "TradingSignalGenerated",
        execution_engine.on_trading_signal
    )

    # ============================================
    # EXECUTION ENGINE → POSITION MONITOR
    # ============================================
    event_bus.subscribe(
        "PositionOpened",
        position_monitor.on_position_opened
    )

    # ============================================
    # NOTIFICATION SYSTEM (Listens to Everything)
    # ============================================

    # 🔴 CRITICAL - Immediate Email
    event_bus.subscribe("OrderFailed", notification_system.on_critical_event)
    event_bus.subscribe("MarketDataConnectionLost", notification_system.on_critical_event)
    event_bus.subscribe("SystemError", notification_system.on_critical_event)
    event_bus.subscribe("PositionReconciliationFailed", notification_system.on_critical_event)

    # 🟡 WARNING - Should Email
    event_bus.subscribe("InsufficientDataQuality", notification_system.on_warning_event)
    event_bus.subscribe("ExecutionValidationFailed", notification_system.on_warning_event)

    # 🟢 INFO - Optional Email
    event_bus.subscribe("TradingSignalGenerated", notification_system.on_info_event)
    event_bus.subscribe("OrderFilled", notification_system.on_info_event)
    event_bus.subscribe("PositionOpened", notification_system.on_info_event)
    event_bus.subscribe("PositionClosed", notification_system.on_info_event)

    logger.info("✅ All event subscriptions configured")


if __name__ == "__main__":
    # Run the event-driven system 24/7
    asyncio.run(main())
```

**What This Achieves**:

1. ✅ **Event Bus runs 24/7** - Processes all events continuously
2. ✅ **Data Streaming runs 24/7** - Ingests ticks, emits events
3. ✅ **Analytics Engine runs 24/7** - Calculates metrics, emits events
4. ✅ **Position Monitor runs 24/7** - Monitors positions, emits events
5. ⚡ **Decision Engine reacts** - Waits for analytics events
6. ⚡ **Execution Engine reacts** - Waits for trading signals
7. ⚡ **Notification System reacts** - Sends emails via SendGrid
8. 🔌 **Fully Decoupled** - Components communicate only via events
9. ✉️ **Real-time Alerts** - SendGrid emails for all important events

**Event Flow Example**:
```
1. WebSocket receives trade → DataStreaming emits TradeTickReceived
                             ↓
2. Analytics processes tick → AnalyticsEngine emits OrderFlowImbalanceDetected
                             ↓
3. Decision evaluates      → DecisionEngine emits TradingSignalGenerated
                             ↓
4. Execution validates     → ExecutionEngine emits OrderPlaced
                             ↓
5. Exchange fills order    → ExecutionEngine emits OrderFilled
                             ↓
6. Position monitoring     → PositionMonitor emits PositionOpened
                             ↓
7. Notification sends      → NotificationSystem sends SendGrid email ✉️
```

**Benefits**:
- 🎯 **True Event-Driven**: Everything reacts to events
- 🔄 **24/7 Operation**: Core systems never stop
- ⚡ **Reactive Components**: Decision/Execution trigger only when needed
- ✉️ **Real-time Notifications**: SendGrid emails for all important events
- 🔌 **Fully Decoupled**: Easy to add new components
- 🧪 **Testable**: Mock event bus for testing
- 📊 **Observable**: All events logged for audit trail

---

## 12. Design Document Updates Summary

This design document has been enhanced with **event-driven architecture** at its core and **battle-tested architectural patterns** from the previous Algo Engine implementation:

### ✅ Core Architecture (Event-Driven):

0. **Event-Driven Architecture** (`2.1`):
   - Event Bus at the center of everything (THE HEART)
   - Data Streaming + Analytics run 24/7, emit events continuously
   - Decision Engine, Execution Engine react to events
   - Notification System (SendGrid) sends emails for important events
   - Fully decoupled components via pub/sub pattern

### ✅ Critical Additions:

1. **Event Bus System** (`2.2.0.1`):
   - Central event bus for all system communication
   - Pub/sub pattern with asyncio.Queue
   - All events defined as dataclasses
   - Complete event subscription setup

2. **Notification System** (`2.2.0.2`):
   - SendGrid integration for email notifications
   - Priority-based notifications (Critical/Warning/Info)
   - Email templates for all event types
   - Real-time alerts for critical events

3. **Per-Symbol Database Isolation** (`2.2.5`):
   - Changed from shared DB to isolated DBs per symbol
   - Structure: `/data/{exchange}/{market_type}/{symbol}/trading.duckdb`
   - Eliminates lock contention for 100+ symbols

2. **Connection Pooling with LRU Eviction** (`2.2.5`):
   - 200-connection cache with LRU eviction
   - Sub-millisecond cached queries
   - 95%+ cache hit rate

3. **Dependency Injection Container** (`2.2.0`):
   - Full DI container for service management
   - Auto-dependency resolution via type hints
   - Easy testing with mock dependencies

4. **Chain of Responsibility Execution** (`2.2.4`):
   - 6-handler execution pipeline
   - Fail-fast validation
   - Clear execution order

5. **Composition-Based Signal Generation** (`2.2.2`):
   - Pluggable analyzers and filters
   - Primary (must pass) vs Secondary (scoring) hierarchy
   - Easy to test and extend

6. **Asynchronous Architecture** (`12.1`):
   - All I/O operations use async/await
   - 100+ symbols/second throughput
   - Non-blocking concurrent execution

7. **Position Reconciliation** (`12.2`):
   - Startup reconciliation service
   - Detects discrepancies between local and exchange
   - Safe restart after crashes

8. **Error Handling & Retry Logic** (`12.3`):
   - Exponential backoff retry
   - Circuit breaker pattern
   - Graceful degradation

### 📖 Additional Documentation:

See `OLD_DESIGN_ANALYSIS.md` for:
- Complete analysis of previous implementation
- What worked well and why
- Detailed code examples
- Multi-Timeframe Manager implementation
- Trailing Stop implementation details
- Background jobs and lifecycle management

---

## Conclusion

This design document outlines a comprehensive algorithmic trading engine focused on profitability through multiple strategies. The system leverages Python for flexibility, DuckDB for performance, and Firebase for scalability. The **modular, composition-based architecture** with **dependency injection** and **async/await throughout** allows for iterative development, strategy experimentation, and high-throughput trading.

**Key Architectural Strengths**:
- ✅ Per-symbol database isolation (zero lock contention)
- ✅ Dependency injection (testable, decoupled services)
- ✅ Chain of responsibility (modular execution pipeline)
- ✅ Composition-based signals (pluggable analyzers)
- ✅ Async/await throughout (100+ symbols concurrency)
- ✅ Position reconciliation (crash recovery)
- ✅ Error handling & retry logic (production resilience)

**Next Steps**:
1. Implement DI container (`src/core/di_container.py`)
2. Implement connection pool manager (`src/storage/connection_pool.py`)
3. Implement execution handler chain (`src/trading/execution_handlers.py`)
4. Implement signal analyzers/filters (`src/decision/signal_pipeline.py`)
5. Implement position reconciliation (`src/services/position_reconciliation.py`)
6. Set up async main event loop with all services
5. Strategy parameter optimization framework
