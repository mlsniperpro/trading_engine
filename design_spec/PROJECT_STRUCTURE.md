# Algo Engine - Project Structure

**BUILDABLE CODE STRUCTURE FOR ALGORITHMIC TRADING ENGINE**

This document provides the complete, real project folder structure for the Algo Engine codebase. This is the actual directory tree where we'll write Python code.

---

## Table of Contents
1. [Project Structure Tree](#project-structure-tree)
2. [Root Level Files](#root-level-files)
3. [Source Code Organization](#source-code-organization)
4. [Configuration Structure](#configuration-structure)
5. [Data Directory Structure](#data-directory-structure)
6. [Testing Structure](#testing-structure)
7. [Design Document Mapping](#design-document-mapping)

---

## Project Structure Tree

```
algo-engine/
│
├── src/                                    # Main source code
│   ├── __init__.py
│   │
│   ├── core/                               # Core system components (Event Bus, DI)
│   │   ├── __init__.py
│   │   ├── event_bus.py                    # Event Bus - THE HEART (Section 2.2.0.1)
│   │   ├── events.py                       # Event type definitions
│   │   ├── di_container.py                 # Dependency Injection Container (Section 2.2.0)
│   │   └── base.py                         # Base classes and interfaces
│   │
│   ├── market_data/                        # Market data ingestion layer (renamed from data/)
│   │   ├── __init__.py
│   │   ├── stream/                         # WebSocket streaming (always-on)
│   │   │   ├── __init__.py
│   │   │   ├── manager.py                  # MarketDataManager - multi-exchange handler
│   │   │   ├── cryptofeed_handler.py       # Cryptofeed WebSocket integration
│   │   │   ├── binance_spot_stream.py      # Binance SPOT market stream
│   │   │   ├── binance_futures_stream.py   # Binance FUTURES market stream
│   │   │   └── connection_monitor.py       # Connection health monitoring
│   │   │
│   │   ├── storage/                        # Database layer (DuckDB)
│   │   │   ├── __init__.py
│   │   │   ├── database_manager.py         # Multi-DB connection manager (Section 12.1)
│   │   │   ├── connection_pool.py          # Connection pooling (Section 12.2)
│   │   │   ├── schema.py                   # Schema definitions and migrations
│   │   │   ├── queries.py                  # SQL query templates
│   │   │   └── models.py                   # Data models (Tick, Candle, etc.)
│   │   │
│   │   ├── mempool/                        # Mempool monitoring (EVM chains only)
│   │   │   ├── __init__.py
│   │   │   ├── mempool_monitor.py          # MempoolMonitor (Section 2.2.6)
│   │   │   ├── transaction_tracker.py      # TransactionConfirmationTracker
│   │   │   ├── gas_oracle.py               # GasPriceOracle
│   │   │   ├── mev_protection.py           # MEVProtectionStrategy
│   │   │   └── tx_decoder.py               # DEX transaction decoder
│   │   │
│   │   └── normalizer.py                   # Data normalization across exchanges
│   │
│   ├── analytics/                          # Analytics engine (always-on)
│   │   ├── __init__.py
│   │   ├── engine.py                       # Main analytics coordinator
│   │   ├── order_flow.py                   # Order flow analyzer (CVD, imbalances)
│   │   ├── market_profile.py               # Market profile (POC, Value Area)
│   │   ├── microstructure.py               # Price rejection patterns
│   │   ├── supply_demand.py                # Supply/demand zone detector
│   │   ├── fair_value_gap.py               # FVG detector
│   │   ├── indicators.py                   # Technical indicators (EMA, RSI, etc.)
│   │   ├── mean_reversion.py               # Mean reversion calculator
│   │   ├── autocorrelation.py              # Autocorrelation analyzer
│   │   └── multi_timeframe.py              # Multi-timeframe manager
│   │
│   ├── decision/                           # Decision engine (reactive)
│   │   ├── __init__.py
│   │   ├── engine.py                       # DecisionEngine orchestrator
│   │   ├── signal_pipeline.py              # Signal generation pipeline
│   │   ├── analyzers/                      # Primary signal analyzers
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # SignalAnalyzer base class
│   │   │   ├── order_flow_analyzer.py      # PRIMARY #1: Order flow imbalance
│   │   │   └── microstructure_analyzer.py  # PRIMARY #2: Rejection patterns
│   │   │
│   │   ├── filters/                        # Secondary signal filters
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # SignalFilter base class
│   │   │   ├── market_profile_filter.py    # FILTER #1: Profile analysis
│   │   │   ├── mean_reversion_filter.py    # FILTER #2: Mean reversion
│   │   │   ├── autocorrelation_filter.py   # FILTER #3: Autocorrelation
│   │   │   ├── demand_zone_filter.py       # FILTER #4: Demand zones
│   │   │   ├── supply_zone_filter.py       # FILTER #5: Supply zones
│   │   │   └── fvg_filter.py               # FILTER #6: Fair value gaps
│   │   │
│   │   └── confluence.py                   # Confluence score calculator
│   │
│   ├── execution/                          # Execution engine (reactive)
│   │   ├── __init__.py
│   │   ├── engine.py                       # ExecutionEngine orchestrator
│   │   ├── pipeline.py                     # Execution pipeline with chain
│   │   ├── handlers/                       # Execution handler chain
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # ExecutionHandler base
│   │   │   ├── validator.py                # Validate signal/order
│   │   │   ├── risk_manager.py             # Position sizing, risk checks
│   │   │   ├── executor.py                 # Execute order via exchange
│   │   │   └── reconciler.py               # Reconcile execution result
│   │   │
│   │   ├── exchanges/                      # Exchange adapters
│   │   │   ├── __init__.py
│   │   │   ├── base.py                     # Exchange interface
│   │   │   ├── binance_ccxt.py             # Binance via CCXT
│   │   │   ├── binance_direct.py           # Binance direct API
│   │   │   └── exchange_factory.py         # Factory for exchange instances
│   │   │
│   │   └── order_manager.py                # Order state management
│   │
│   ├── position/                           # Position monitoring (always-on)
│   │   ├── __init__.py
│   │   ├── monitor.py                      # PositionMonitor - main tracker
│   │   ├── portfolio_risk_manager.py       # Portfolio Risk Manager (Section 2.2.5)
│   │   ├── trailing_stop.py                # TrailingStopManager (Section 8.1)
│   │   ├── reconciliation.py               # Position reconciliation (Design Doc Section 12.2)
│   │   └── models.py                       # Position data models
│   │
│   ├── integrations/                       # External integrations (adapters)
│   │   ├── __init__.py
│   │   │
│   │   ├── dex/                            # DEX aggregator adapters
│   │   │   ├── __init__.py
│   │   │   ├── aggregator_adapter.py       # DEXAggregator interface + AggregatorQuote
│   │   │   ├── aggregator_factory.py       # AggregatorFactory for chain selection
│   │   │   ├── jupiter_adapter.py          # Jupiter (Solana) adapter
│   │   │   ├── oneinch_adapter.py          # 1inch (EVM chains) adapter
│   │   │   ├── matcha_adapter.py           # Matcha/0x adapter
│   │   │   └── paraswap_adapter.py         # ParaSwap adapter
│   │   │
│   │   ├── cex/                            # Centralized exchange adapters
│   │   │   ├── __init__.py
│   │   │   ├── exchange_adapter.py         # ExchangeAdapter interface
│   │   │   ├── exchange_factory.py         # ExchangeFactory for exchange selection
│   │   │   ├── binance_adapter.py          # Binance CEX adapter
│   │   │   ├── bybit_adapter.py            # Bybit adapter
│   │   │   └── hyperliquid_adapter.py      # Hyperliquid perpetuals adapter
│   │   │
│   │   └── forex/                          # Forex platform adapters
│   │       ├── __init__.py
│   │       ├── forex_adapter.py            # ForexAdapter interface
│   │       ├── forex_factory.py            # ForexFactory for platform selection
│   │       ├── mt5_adapter.py              # MetaTrader 5 adapter
│   │       ├── ctrader_adapter.py          # cTrader adapter
│   │       ├── tradelocker_adapter.py      # TradeLocker adapter
│   │       └── matchtrader_adapter.py      # MatchTrader adapter
│   │
│   ├── notifications/                      # Notification system (reactive)
│   │   ├── __init__.py
│   │   ├── service.py                      # NotificationSystem orchestrator
│   │   ├── sendgrid_client.py              # SendGrid API client (Section 2.2.0.2)
│   │   ├── templates.py                    # Email HTML templates
│   │   └── priority.py                     # Priority handling (critical/warning/info)
│   │
│   ├── strategies/                         # Trading strategies
│   │   ├── __init__.py
│   │   ├── base.py                         # Strategy interface
│   │   ├── bid_ask_bounce.py               # Bid-ask bounce strategy
│   │   ├── market_quality.py               # Market quality trading
│   │   ├── supply_demand.py                # Supply/demand zone strategy
│   │   └── strategy_manager.py             # Strategy selector and manager
│   │
│   ├── config/                             # Configuration management
│   │   ├── __init__.py
│   │   ├── loader.py                       # Config loader (YAML + Firestore)
│   │   ├── settings.py                     # Settings dataclasses
│   │   ├── validator.py                    # Config validation
│   │   └── firebase_sync.py                # Firebase Firestore sync
│   │
│   ├── utils/                              # Utility modules
│   │   ├── __init__.py
│   │   ├── logger.py                       # Logging configuration
│   │   ├── metrics.py                      # Performance metrics
│   │   ├── time_utils.py                   # Time/timezone utilities
│   │   └── math_utils.py                   # Math/statistical functions
│   │
│   └── api/                                # Optional REST/WebSocket API
│       ├── __init__.py
│       ├── server.py                       # FastAPI server (optional)
│       ├── routes.py                       # API endpoints
│       └── websocket.py                    # WebSocket for live updates
│
├── config/                                 # Configuration files
│   ├── config.yaml                         # Main configuration
│   ├── exchanges.yaml                      # Exchange-specific configs
│   ├── aggregators.yaml                    # DEX aggregator configs (Jupiter, 1inch, etc.)
│   ├── forex_platforms.yaml                # Forex platform configs (MT5, cTrader, etc.)
│   ├── strategies.yaml                     # Strategy parameters
│   ├── notifications.yaml                  # Notification settings
│   ├── risk.yaml                           # Risk management rules
│   ├── portfolio_risk.yaml                 # Portfolio-level risk monitoring
│   ├── mempool.yaml                        # Mempool monitoring (EVM chains)
│   └── .env.example                        # Environment variables template
│
├── data/                                   # Data storage (gitignored)
│   ├── binance/
│   │   ├── spot/
│   │   │   ├── BTCUSDT/
│   │   │   │   └── trading.duckdb          # Per-pair isolated database
│   │   │   ├── ETHUSDT/
│   │   │   │   └── trading.duckdb
│   │   │   └── SOLUSDT/
│   │   │       └── trading.duckdb
│   │   └── futures/
│   │       ├── BTCUSDT/
│   │       │   └── trading.duckdb
│   │       └── ETHUSDT/
│   │           └── trading.duckdb
│   ├── bybit/
│   │   ├── spot/
│   │   │   ├── BTCUSDT/
│   │   │   │   └── trading.duckdb
│   │   │   └── ETHUSDT/
│   │   │       └── trading.duckdb
│   │   └── futures/
│   │       └── BTCUSDT/
│   │           └── trading.duckdb
│   ├── dex/
│   │   ├── ethereum/
│   │   │   ├── WETH_USDC/
│   │   │   │   └── trading.duckdb
│   │   │   └── WBTC_USDC/
│   │   │       └── trading.duckdb
│   │   └── solana/
│   │       ├── SOL_USDC/
│   │       │   └── trading.duckdb
│   │       └── BONK_SOL/
│   │           └── trading.duckdb
│   └── logs/                               # Application logs (auto-rotate, no archive/)
│       ├── app.log
│       ├── trades.log
│       └── errors.log
│
├── tests/                                  # Test suite
│   ├── __init__.py
│   ├── conftest.py                         # Pytest fixtures
│   │
│   ├── unit/                               # Unit tests
│   │   ├── __init__.py
│   │   ├── test_event_bus.py
│   │   ├── test_di_container.py
│   │   ├── test_order_flow.py
│   │   ├── test_decision_engine.py
│   │   ├── test_execution_pipeline.py
│   │   ├── test_trailing_stop.py
│   │   └── test_analyzers.py
│   │
│   ├── integration/                        # Integration tests
│   │   ├── __init__.py
│   │   ├── test_data_pipeline.py
│   │   ├── test_analytics_flow.py
│   │   ├── test_trading_flow.py
│   │   └── test_event_flow.py
│   │
│   └── mocks/                              # Mock objects
│       ├── __init__.py
│       ├── mock_exchange.py
│       ├── mock_event_bus.py
│       └── mock_database.py
│
├── scripts/                                # Utility scripts
│   ├── setup_database.py                   # Initialize DuckDB schemas
│   ├── import_historical.py                # Import historical data
│   ├── backtest.py                         # Backtesting script
│   ├── position_reconcile.py               # Manual position reconciliation
│   ├── monitor_health.py                   # Health check script
│   └── deploy.sh                           # Deployment script
│
├── notebooks/                              # Jupyter notebooks (research)
│   ├── data_exploration.ipynb              # Explore market data
│   ├── strategy_backtest.ipynb             # Strategy backtesting
│   ├── signal_analysis.ipynb               # Analyze signal performance
│   └── aggregator_analysis.ipynb           # DEX aggregator performance analysis
│
├── docs/                                   # Additional documentation
│   ├── SETUP.md                            # Setup instructions
│   ├── DEPLOYMENT.md                       # Deployment guide
│   ├── API.md                              # API documentation
│   └── TROUBLESHOOTING.md                  # Common issues
│
├── .github/                                # GitHub workflows (if using)
│   └── workflows/
│       ├── tests.yml                       # Run tests on push
│       └── deploy.yml                      # Deploy to production
│
├── main.py                                 # Main application entry point
├── requirements.txt                        # Python dependencies
├── setup.py                                # Package setup
├── .env                                    # Environment variables (gitignored)
├── .gitignore                              # Git ignore rules
├── README.md                               # Project README
├── DESIGN_DOC.md                           # Design document (existing)
├── TECHNICAL_ARCHITECTURE.md               # Technical architecture (existing)
└── PROJECT_STRUCTURE.md                    # This file
```

---

## Root Level Files

### main.py
**Purpose**: Application entry point - starts the 24/7 event-driven system

**Contents**:
- DI container setup
- Event bus initialization
- Service registration (data streaming, analytics, decision, execution)
- Event subscriber wiring
- Graceful shutdown handling

**Key Functions**:
```python
def setup_di_container() -> DependencyContainer
async def setup_event_subscribers(event_bus, container)
async def start_always_on_components(container)
async def main()
```

**Maps to**: Design Doc Section 2.2.0 (DI Container & Event Bus Setup)

---

### requirements.txt
**Purpose**: Python dependencies

**Key Dependencies**:
```
# Core async (Python 3.12+)
asyncio
aiohttp

# Market data
cryptofeed>=2.4.0
ccxt>=4.0.0
python-binance>=1.0.0

# DEX integrations
web3>=6.0.0                  # EVM chains (Ethereum, Base, Arbitrum, etc.)
solana>=0.30.0               # Solana blockchain
solders>=0.18.0              # Solana Rust bindings

# DEX aggregator SDKs (hypothetical names - actual packages may vary)
# jupiter-py                 # Jupiter aggregator for Solana
# oneinch-py                 # 1inch aggregator for EVM
# 0x-py                      # Matcha/0x protocol

# Forex integrations
MetaTrader5>=5.0.0           # MT5 Python API
# ctrader-py                 # cTrader API wrapper
# tradelocker-py             # TradeLocker API wrapper

# Database
duckdb>=0.9.0

# Firebase
firebase-admin>=6.0.0

# Notifications
sendgrid>=6.10.0

# Web framework (optional)
fastapi>=0.104.0
uvicorn>=0.24.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Utilities
pydantic>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
```

---

### .env.example
**Purpose**: Template for environment variables

```bash
# Exchange API Keys
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Firebase
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
FIRESTORE_PROJECT_ID=your_project_id

# SendGrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
ALERT_EMAIL=trader@example.com
ALERT_FROM_EMAIL=algo-engine@yourdomain.com

# System
ENVIRONMENT=development  # development, staging, production
LOG_LEVEL=INFO
DATA_DIR=/data
```

---

## Source Code Organization

### 1. Core (`src/core/`)

#### event_bus.py
**Purpose**: THE HEART - Central event distribution system running 24/7

**Classes**:
- `EventBus` - Main event bus with pub/sub mechanism
  - `subscribe(event_type, handler)` - Register event handlers
  - `publish(event)` - Publish events to queue
  - `process_events()` - Main 24/7 event loop

**Maps to**: Design Doc Section 2.2.0.1, Tech Arch Section 3.0.1

---

#### events.py
**Purpose**: Event type definitions

**Classes** (all dataclasses):
- `Event` - Base event class
- **Market Data Events**:
  - `TradeTickReceived` - Trade tick from WebSocket
  - `CandleCompleted` - Candle aggregation complete
  - `MarketDataConnectionLost` - Connection lost (CRITICAL)
- **Analytics Events**:
  - `AnalyticsUpdated` - Analytics recalculated
  - `OrderFlowImbalanceDetected` - Order flow signal
  - `MicrostructurePatternDetected` - Price pattern signal
- **Trading Events**:
  - `TradingSignalGenerated` - Entry signal
  - `OrderPlaced` - Order sent to exchange
  - `OrderFilled` - Order executed
  - `OrderFailed` - Order failed (CRITICAL)
- **Position Events**:
  - `PositionOpened` - New position
  - `PositionClosed` - Position closed
  - `TrailingStopHit` - Trailing stop triggered
- **System Events**:
  - `SystemError` - Critical error (CRITICAL)

**Maps to**: Design Doc Section 2.2.0.1

---

#### di_container.py
**Purpose**: Dependency Injection container for service lifecycle management

**Classes**:
- `DependencyContainer` - Main DI container
  - `register_singleton(name, instance)` - Register singleton service
  - `register_factory(name, factory)` - Register factory function
  - `register_type(interface, implementation)` - Register type with auto-resolution
  - `resolve(service_name)` - Resolve service with dependencies

**Benefits**:
- No global state
- Testability with mock dependencies
- Clear dependency graph
- Proper initialization order

**Maps to**: Design Doc Section 2.2.0

---

#### base.py
**Purpose**: Base classes and interfaces

**Classes**:
- `Component` - Base class for all system components
- `AlwaysOnComponent` - Base for 24/7 running components
- `ReactiveComponent` - Base for event-reactive components

---

### 2. Market Data Layer (`src/market_data/`)

#### stream/manager.py
**Purpose**: Orchestrates all WebSocket connections across exchanges

**Classes**:
- `MarketDataManager` - Main coordinator
  - `start_binance_spot(symbols)` - Start Binance SPOT stream
  - `start_binance_futures(symbols)` - Start Binance FUTURES stream
  - `handle_trade(trade)` - Process trade tick
  - `handle_candle(candle)` - Process candle data

**State**: Always-On (24/7)

**Maps to**: Tech Arch Section 3.2

---

#### stream/cryptofeed_handler.py
**Purpose**: Cryptofeed WebSocket integration

**Classes**:
- `CryptofeedHandler` - Wraps Cryptofeed library
  - Manages FeedHandler instances
  - Callbacks for TRADES and CANDLES
  - Auto-reconnection handling

**Maps to**: Tech Arch Section 3.2

---

#### storage/database_manager.py
**Purpose**: Manages DuckDB connections per trading pair for realtime analytics

**Classes**:
- `DatabaseManager` - Connection manager
  - `get_connection(exchange, market_type, symbol)` - Get/create per-pair connection
  - `close_all()` - Graceful shutdown
  - **Per-pair database isolation** (critical for race condition prevention)

**Key Design**:
```python
# Separate databases PER TRADING PAIR (NO backups/)
data/binance/spot/BTCUSDT/trading.duckdb
data/binance/spot/ETHUSDT/trading.duckdb
data/binance/futures/BTCUSDT/trading.duckdb
data/bybit/spot/BTCUSDT/trading.duckdb
data/dex/ethereum/WETH_USDC/trading.duckdb
data/dex/solana/SOL_USDC/trading.duckdb
```

**Per-Pair Database Isolation Benefits**:
- ✅ **ZERO write contention** - Each pair has its own database file
- ✅ **Race condition prevention** - Critical when scanning 100+ pairs simultaneously
- ✅ **Independent analytics** - Parallel queries across all pairs without locks
- ✅ **Independent scaling** - Add/remove pairs without affecting others
- ✅ **Crash isolation** - One pair's DB corruption doesn't affect others
- ✅ **NO backups/** directories - just live databases per pair

**Why Per-Pair Instead of Per-Exchange?**:
- When scanning 100+ pairs, shared DB = write lock contention
- DuckDB optimized for analytics, not concurrent writes
- Per-pair = true parallelism with zero contention

**Maps to**: Tech Arch Section 4.0, Section 12.1

---

#### storage/connection_pool.py
**Purpose**: Connection pooling for concurrent analytics queries (per-pair)

**Classes**:
- `ConnectionPoolManager` - Pool manager
  - `acquire(exchange, market_type, symbol)` - Get per-pair connection from pool
  - `release(connection)` - Return connection to pool
  - Max 200 connections globally (distributed across all pairs)

**Connection Pool Strategy** (Shared LRU Pool):
- **NOT dedicated** - Shared pool of 200 connections across ALL pairs
- LRU (Least Recently Used) eviction when pool is full
- Active pairs stay cached, inactive pairs get evicted automatically
- Example: 100 active pairs = ~100 cached connections, 100 slots for new pairs
- High-frequency pairs (BTC, ETH) stay cached, low-volume pairs get evicted/reopened

**Use Cases**:
- Concurrent analytics across 100+ pairs simultaneously
- Parallel queries within same pair (multiple timeframes)
- Position monitoring across all open pairs

**Example**:
```python
# Each pair operates independently - zero contention
conn_btc = pool.acquire('binance', 'spot', 'BTCUSDT')
conn_eth = pool.acquire('binance', 'spot', 'ETHUSDT')
conn_sol = pool.acquire('binance', 'spot', 'SOLUSDT')
# All 3 can write/read simultaneously without locks
```

**Maps to**: Tech Arch Section 12.2

---

#### storage/schema.py
**Purpose**: DuckDB schema definitions for realtime data and analytics

**Key Tables (per trading pair's trading.duckdb)**:
- `ticks` - Raw trade ticks (SOURCE OF TRUTH for analytics) - **symbol column not needed, implied by DB path**
- `candles_1m`, `candles_5m`, `candles_15m` - Multi-timeframe candles (max 15m)
- `order_flow` - Order flow metrics (CVD, imbalance ratios)
- `market_profile` - Market profile data (POC, Value Area)
- `supply_demand_zones` - Supply/demand zones
- `fair_value_gaps` - Fair value gaps
- `positions` - Open positions (for this pair only)
- `trades_history` - Trade history (for this pair only)

**Schema Simplification with Per-Pair DBs**:
- ❌ No `symbol` column needed in any table (implied by database path)
- ❌ No compound indexes on (symbol, timestamp) - just (timestamp)
- ✅ Simpler queries: `SELECT * FROM ticks WHERE timestamp > ?` (no symbol filter)
- ✅ Better performance: Index on timestamp only, no multi-column overhead

**Data Lifecycle & Retention Policy**:

| Data Type | Retention | Cleanup Frequency | Storage |
|-----------|-----------|-------------------|---------|
| Ticks | 15 minutes | Every 5 minutes | Per-pair DuckDB |
| 1m Candles | 15 minutes | Every 15 minutes | Per-pair DuckDB |
| 5m Candles | 1 hour | Every 15 minutes | Per-pair DuckDB |
| 15m Candles | 1 hour | Every 15 minutes | Per-pair DuckDB |
| Order Flow | 15 minutes | Every 5 minutes | Per-pair DuckDB |
| Market Profile | 15 minutes | Every 5 minutes | Per-pair DuckDB |
| Supply/Demand Zones | Permanent (max 50) | On zone break | Per-pair DuckDB |
| Fair Value Gaps | Until filled or 24h | On fill or daily | Per-pair DuckDB |
| Trade Executions | Immediate to Firestore | Every 5 minutes | Firestore (not DuckDB) |
| Positions | Active only | On position close | Per-pair DuckDB + Firestore |

- Realtime data flows from WebSocket → Per-pair DuckDB
- Analytics calculated via SQL queries on per-pair tables
- NO backups/ directories - just live databases per pair
- Aggressive cleanup keeps each pair's DB < 10 MB
- Completed trades immediately moved to Firestore

**Why DuckDB + Per-Pair?**:
- Fast in-memory analytics with disk persistence
- Efficient window functions for order flow, market profile
- Low latency SQL queries for decision engine
- **Per-pair = zero write contention across 100+ pairs**
- No need for backups - data is ephemeral, regenerated from realtime streams

**Maps to**: Tech Arch Section 4.1

---

#### storage/queries.py
**Purpose**: SQL query templates for analytics on DuckDB tables

**Analytics Queries**:
- `calculate_market_profile_query()` - POC and Value Area calculation from ticks
- `calculate_cvd_query()` - Cumulative Volume Delta from trade ticks
- `detect_order_flow_imbalance_query()` - Imbalance detection (buy/sell ratio)
- `identify_fvg_query()` - Fair value gap detection from candles
- `multi_timeframe_trend_query()` - Trend alignment across timeframes

**Trade Queries**:
- `get_trades_by_date(start_date, end_date)` - Get trades in date range
- `get_trades_by_symbol(symbol)` - Get trades for specific symbol
- `calculate_daily_pnl()` - Calculate daily P&L from trades
- `get_trade_statistics()` - Win rate, avg P&L, Sharpe ratio, etc.

**Query Performance**:
- DuckDB's columnar format optimized for analytics
- Window functions for rolling calculations
- Materialized views for frequently accessed analytics
- No need to backup query results - regenerated on-demand

**Maps to**: Tech Arch Section 4.2

---

#### mempool/mempool_monitor.py
**Purpose**: Monitor pending transactions on EVM chains for MEV protection and slippage prediction

**Classes**:
- `MempoolMonitor` - Main mempool stream monitor (runs 24/7 for EVM chains only)
  - `start()` - Subscribe to pending transactions via eth_subscribe
  - `process_pending_transaction(tx)` - Process each pending TX
  - `track_our_transaction(tx)` - Track our own pending TXs
  - `handle_large_pending_swap(swap_data, tx)` - Alert on large swaps (>$100k)
  - `is_dex_swap(tx)` - Check if TX is DEX swap
  - `decode_swap(tx)` - Decode DEX swap transaction data
  - `detect_mev_activity(tx)` - Detect frontrunning/sandwich attacks

**State**: Always-On (24/7) for EVM chains (Ethereum, Base, Polygon, BSC)

**Event Integration**:
- Emits: `OurTransactionPending`, `OurTransactionConfirmed`, `OurTransactionFailed`, `LargePendingSwap`, `MEVBotDetected`

**Chains Supported**:
- ✅ Ethereum, Base, Polygon, BSC (full mempool access)
- ⚠️ Arbitrum (limited L2 sequencer visibility)
- ❌ Solana (no traditional mempool)

**Maps to**: Design Doc Section 2.2.6

---

#### mempool/transaction_tracker.py
**Purpose**: Track our DEX transactions from pending → confirmed

**Classes**:
- `TransactionConfirmationTracker` - Monitor TX confirmation
  - `monitor_confirmation(tx_hash, max_wait_seconds)` - Wait for confirmation
  - Returns: 'confirmed', 'failed', 'timeout', 'replaced'
  - Emits events on status changes

**Use Cases**:
- Verify our DEX swaps executed
- Detect failed/reverted transactions
- Timeout detection (stuck in mempool)

**Maps to**: Design Doc Section 2.2.6

---

#### mempool/gas_oracle.py
**Purpose**: Determine optimal gas prices based on mempool congestion

**Classes**:
- `GasPriceOracle` - Gas price recommendation engine
  - `get_optimal_gas_price(urgency)` - Get gas price for urgency level
    - 'low': 25th percentile (next 10 blocks ~2 min)
    - 'normal': 50th percentile (median, next 3 blocks ~36 sec)
    - 'high': 75th percentile (next block ~12 sec)
    - 'urgent': 90th percentile (immediate inclusion)

**Use Cases**:
- Optimize gas spending based on urgency
- Avoid overpaying during low congestion
- Ensure fast inclusion during high urgency trades

**Maps to**: Design Doc Section 2.2.6

---

#### mempool/mev_protection.py
**Purpose**: Protect against frontrunning and sandwich attacks

**Classes**:
- `MEVProtectionStrategy` - MEV protection strategies
  - `use_private_mempool(tx)` - Send TX via Flashbots/Eden (avoids public mempool)
  - `use_limit_orders(token_in, token_out, amount, limit_price)` - Use limit orders instead of market
  - `split_large_orders(total_amount, num_splits)` - Split large orders to reduce MEV

**Use Cases**:
- Large DEX swaps (>$50k) → use private mempool
- Meme coin buys → prevent frontrunning
- Arbitrage trades → protect alpha

**Maps to**: Design Doc Section 2.2.6

---

#### mempool/tx_decoder.py
**Purpose**: Decode and parse DEX transaction calldata

**Functions**:
- `decode_uniswap_v2_swap(tx_input)` - Decode Uniswap V2 swap
- `decode_uniswap_v3_swap(tx_input)` - Decode Uniswap V3 swap
- `decode_1inch_swap(tx_input)` - Decode 1inch aggregator swap
- `identify_dex_router(address)` - Identify which DEX router
- `extract_token_path(decoded)` - Extract token swap path
- `calculate_expected_slippage(decoded, pool_reserves)` - Estimate slippage

**Use Cases**:
- Parse pending large swaps to predict price impact
- Identify token pairs being traded
- Detect unusual slippage tolerances (potential manipulation)

**Maps to**: Design Doc Section 2.2.6

---

### 3. Analytics Engine (`src/analytics/`)

#### engine.py
**Purpose**: Main analytics coordinator - runs 24/7

**Classes**:
- `AnalyticsEngine` - Orchestrator
  - Subscribes to `TradeTickReceived` and `CandleCompleted` events
  - Triggers all analytics calculations
  - Emits `AnalyticsUpdated`, `OrderFlowImbalanceDetected`, etc.

**State**: Always-On (24/7)

**Maps to**: Design Doc Section 2.2.2

---

#### order_flow.py
**Purpose**: Order flow analysis (CVD, imbalances)

**Classes**:
- `OrderFlowAnalyzer` - Calculates order flow metrics
  - `calculate_cvd(symbol, lookback)` - Cumulative Volume Delta
  - `detect_imbalance(symbol, window)` - Buy/sell imbalance ratio
  - `detect_large_trades(symbol)` - Whale detection

**Maps to**: Tech Arch Section 5.2

---

#### market_profile.py
**Purpose**: Market profile calculation (POC, Value Area)

**Classes**:
- `MarketProfileAnalyzer` - Profile calculator
  - `calculate_profile(symbol, timeframe)` - Calculate POC, VAH, VAL
  - `get_volume_distribution()` - Price-volume histogram

**Maps to**: Tech Arch Section 5.1

---

#### microstructure.py
**Purpose**: Price rejection pattern detection

**Classes**:
- `MicrostructureAnalyzer` - Pattern detector
  - `detect_rejection(candle)` - Pin bars, wicks
  - `analyze_candle_strength()` - Close position analysis

---

#### supply_demand.py
**Purpose**: Supply/demand zone detection

**Classes**:
- `SupplyDemandDetector` - Zone detector
  - `identify_demand_zones()` - Support zones
  - `identify_supply_zones()` - Resistance zones
  - `update_zone_status()` - Track fresh/tested/broken

**Maps to**: Tech Arch Section 5.3

---

#### fair_value_gap.py
**Purpose**: Fair value gap detection

**Classes**:
- `FairValueGapDetector` - FVG detector
  - `identify_fvgs()` - 3-candle gap detection
  - `track_fill_percentage()` - Gap fill tracking

**Maps to**: Tech Arch Section 5.4

---

#### indicators.py
**Purpose**: Technical indicators (RSI, ADX, Directional Persistence)

**Functions**:
- `calculate_rsi(data, period)` - Relative Strength Index
- `calculate_adx(data, period)` - Average Directional Index (trend strength)
- `calculate_directional_persistence(data, period)` - Price movement consistency
- `calculate_price_action_structure(candles)` - Higher highs/lows detection

---

#### mean_reversion.py
**Purpose**: Mean reversion analysis

**Classes**:
- `MeanReversionCalculator` - Deviation calculator
  - `calculate_deviation(price, tick_mean)` - Distance from 15-min tick mean
  - `detect_extreme_deviation()` - Beyond 2σ from tick mean

---

#### autocorrelation.py
**Purpose**: Autocorrelation analysis

**Classes**:
- `AutocorrelationAnalyzer` - Correlation calculator
  - `calculate_autocorrelation(prices, lag)` - Price correlation

---

#### multi_timeframe.py
**Purpose**: Multi-timeframe coordination

**Classes**:
- `MultiTimeframeManager` - Timeframe coordinator
  - `get_current_candles(symbol, timeframes)` - Fetch all TFs
  - `check_trend_alignment()` - Multi-TF trend agreement

**Maps to**: Tech Arch Section 12.9

---

### 4. Decision Engine (`src/decision/`)

#### engine.py
**Purpose**: Main decision orchestrator - evaluates signals

**Classes**:
- `DecisionEngine` - Signal evaluator
  - Subscribes to analytics events
  - Runs primary analyzers (ALL must pass)
  - Runs secondary filters (weighted scoring)
  - Emits `TradingSignalGenerated` if confluence >= threshold

**State**: Reactive (triggered by events)

**Maps to**: Design Doc Section 2.2.2, Tech Arch Section 12.5

---

#### signal_pipeline.py
**Purpose**: Signal generation pipeline infrastructure

**Classes**:
- `SignalResult` - Result from analyzer
- `TradeSignal` - Generated trading signal

---

#### analyzers/base.py
**Purpose**: Base class for primary analyzers

**Classes**:
- `SignalAnalyzer` - Abstract base
  - `analyze(market_data) -> SignalResult` - Must be implemented

---

#### analyzers/order_flow_analyzer.py
**Purpose**: PRIMARY SIGNAL #1 - Order flow imbalance

**Classes**:
- `OrderFlowAnalyzer(SignalAnalyzer)` - Imbalance detector
  - Threshold: >2.5:1 buy/sell ratio
  - Lookback: 30 seconds - 2 minutes

**Maps to**: Design Doc Section 2.2.2

---

#### analyzers/microstructure_analyzer.py
**Purpose**: PRIMARY SIGNAL #2 - Rejection patterns

**Classes**:
- `MicrostructureAnalyzer(SignalAnalyzer)` - Pattern detector
  - Detects pin bars, rejection wicks
  - Candle close strength

**Maps to**: Design Doc Section 2.2.2

---

#### filters/base.py
**Purpose**: Base class for secondary filters

**Classes**:
- `SignalFilter` - Abstract base
  - `evaluate(market_data) -> float` - Return score (0 to weight)

---

#### filters/market_profile_filter.py
**Purpose**: FILTER #1 - Market profile (weight: 1.5)

**Classes**:
- `MarketProfileFilter(SignalFilter)` - Profile evaluator
  - At VAH/VAL: +1.5 points
  - Inside value area: +0.5 points

---

#### filters/mean_reversion_filter.py
**Purpose**: FILTER #2 - Mean reversion (weight: 1.5)

**Classes**:
- `MeanReversionFilter(SignalFilter)` - Deviation evaluator
  - Beyond 2σ: +1.5 points
  - Beyond 1σ: +0.75 points

---

#### filters/autocorrelation_filter.py
**Purpose**: FILTER #3 - Autocorrelation (weight: 1.0)

**Classes**:
- `AutocorrelationFilter(SignalFilter)` - Correlation evaluator
  - High/low correlation: +1.0 point

---

#### filters/demand_zone_filter.py
**Purpose**: FILTER #4 - Demand zones (weight: 2.0)

**Classes**:
- `DemandZoneFilter(SignalFilter)` - Demand zone proximity
  - Fresh zone: +2.0 points
  - Tested zone: +1.0 point

---

#### filters/supply_zone_filter.py
**Purpose**: FILTER #5 - Supply zones (weight: 0.5)

**Classes**:
- `SupplyZoneFilter(SignalFilter)` - Supply zone target
  - Zone above price: +0.5 points

---

#### filters/fvg_filter.py
**Purpose**: FILTER #6 - Fair value gaps (weight: 1.5)

**Classes**:
- `FairValueGapFilter(SignalFilter)` - FVG evaluator
  - Unfilled FVG in direction: +1.5 points

---

#### confluence.py
**Purpose**: Confluence score calculator

**Classes**:
- `ConfluenceCalculator` - Score aggregator
  - Aggregates filter contributions
  - Total: 10.0 points max

**Maps to**: Tech Arch Section 5.6

---

### 5. Execution Engine (`src/execution/`)

#### engine.py
**Purpose**: Main execution orchestrator

**Classes**:
- `ExecutionEngine` - Orchestrator
  - Subscribes to `TradingSignalGenerated` events
  - Triggers execution pipeline
  - Emits `OrderPlaced`, `OrderFilled`, `OrderFailed` events

**State**: Reactive (triggered by signals)

---

#### pipeline.py
**Purpose**: Execution pipeline with handler chain

**Classes**:
- `ExecutionPipeline` - Chain coordinator
  - Runs handlers in sequence: Validator → Risk → Executor → Reconciler

**Maps to**: Tech Arch Section 12.4

---

#### handlers/base.py
**Purpose**: Base execution handler

**Classes**:
- `ExecutionHandler` - Abstract base
  - `handle(context) -> Result` - Chain of responsibility pattern

---

#### handlers/validator.py
**Purpose**: Validate signal and order parameters

**Classes**:
- `ValidationHandler(ExecutionHandler)` - Validator
  - Check signal validity
  - Validate order parameters
  - Confirm market conditions

---

#### handlers/risk_manager.py
**Purpose**: Position sizing and risk checks

**Classes**:
- `RiskManagementHandler(ExecutionHandler)` - Risk manager
  - Calculate position size
  - Check max concurrent positions
  - Validate stop-loss placement

---

#### handlers/executor.py
**Purpose**: Execute order via exchange

**Classes**:
- `OrderExecutorHandler(ExecutionHandler)` - Order executor
  - Place order via exchange adapter
  - Handle order errors
  - Retry logic

**Maps to**: Tech Arch Section 12.8

---

#### handlers/reconciler.py
**Purpose**: Reconcile execution result

**Classes**:
- `ReconciliationHandler(ExecutionHandler)` - Reconciler
  - Verify order fill
  - Update position state
  - Sync with database

**Maps to**: Tech Arch Section 12.7

---

#### exchanges/base.py
**Purpose**: Exchange adapter interface

**Classes**:
- `ExchangeAdapter` - Abstract base
  - `place_order()` - Place order
  - `cancel_order()` - Cancel order
  - `get_balance()` - Get account balance
  - `get_positions()` - Get open positions

---

#### exchanges/binance_ccxt.py
**Purpose**: Binance via CCXT

**Classes**:
- `BinanceCCXTAdapter(ExchangeAdapter)` - CCXT wrapper
  - Uses `ccxt.binance`
  - Rate limit handling

**Maps to**: Tech Arch Section 7.1

---

#### exchanges/binance_direct.py
**Purpose**: Binance direct API (low latency)

**Classes**:
- `BinanceDirectAdapter(ExchangeAdapter)` - Direct API
  - Uses `python-binance`
  - Lower latency for critical operations

**Maps to**: Tech Arch Section 7.2

---

#### exchanges/exchange_factory.py
**Purpose**: Factory for exchange instances

**Classes**:
- `ExchangeFactory` - Factory
  - `create_exchange(exchange_name, config)` - Create adapter

---

#### order_manager.py
**Purpose**: Order state management

**Classes**:
- `OrderManager` - Order tracker
  - Track pending orders
  - Handle order updates from WebSocket
  - Order lifecycle management

---

### 6. Position Monitoring (`src/position/`)

#### monitor.py
**Purpose**: Main position monitor - runs 24/7

**Classes**:
- `PositionMonitor` - Position tracker
  - Subscribes to `PositionOpened` events
  - Monitors position P&L
  - Triggers trailing stops
  - Emits `PositionClosed` events

**State**: Always-On (24/7)

**Maps to**: Design Doc Section 2.1

---

#### portfolio_risk_manager.py
**Purpose**: Portfolio-level risk monitoring and proactive dump detection

**Classes**:
- `PortfolioRiskManager` - Main orchestrator running 24/7
  - Monitors ALL open positions simultaneously
  - Detects dumps before trailing stops hit
  - Executes portfolio-level exits
  - Enforces daily drawdown circuit breaker

- `DumpDetector` - Dump signal detection
  - `detect_position_dump(position)` - Volume reversal, order flow flip, momentum break
  - Triggers: Sell volume > buy, order flow reversal, liquidity evaporation
  - Action: EXIT IMMEDIATELY, don't wait for trailing stop

- `CorrelationMonitor` - Market leader correlation tracking
  - `monitor_market_leaders()` - Watch BTC, ETH for dumps >1.5% in 5 min
  - `calculate_position_correlation(position, leader)` - Rolling 24h correlation
  - Action: Exit all positions with >0.7 correlation to dumping leader

- `PortfolioHealthMonitor` - Portfolio health scoring
  - `calculate_health_score()` - Score 0-100 based on P&L, quality, concentration, hold time
  - Score < 30: Close worst 2 positions
  - Score < 50: Tighten all stops to 0.3%
  - Score < 70: Stop new entries

- `DrawdownCircuitBreaker` - Daily drawdown protection
  - `monitor_daily_drawdown()` - Track total P&L from session start
  - 3% drawdown: Close worst 50% of positions
  - 4% drawdown: Close ALL positions
  - 5% drawdown: Close all + STOP TRADING

- `HoldTimeEnforcer` - Maximum hold time enforcement
  - `enforce_max_hold_times()` - Force close positions exceeding max hold
  - Scalping: 30 min max
  - Meme coins: 24 hours max
  - Forex: Close before session end

**State**: Always-On (24/7)

**Event Integration**:
- Subscribes to: `TradeTickReceived`, `CandleCompleted`, `PositionOpened`, `PositionClosed`
- Emits: `DumpDetected`, `PortfolioHealthDegraded`, `ForceExitRequired`, `CorrelatedDumpDetected`, `CircuitBreakerTriggered`, `MaxHoldTimeExceeded`

**Database Tables**:
- `portfolio_health_snapshots` - Health score history
- `position_correlations` - Correlation matrix tracking
- `dump_detections` - Dump event logs with P&L

**Maps to**: Design Doc Section 2.2.5

---

#### trailing_stop.py
**Purpose**: Trailing stop-loss manager

**Classes**:
- `TrailingStopManager` - Stop-loss tracker
  - `add_position(position)` - Start tracking
  - `update_on_tick(symbol, price)` - Update stops on every tick
  - `_trigger_stop(position_id)` - Execute stop-loss
  - Regular crypto: 0.5% trailing distance
  - Meme coins: 15-20% trailing distance

**Maps to**: Tech Arch Section 8.1, Design Doc trailing stop sections

---

#### reconciliation.py
**Purpose**: Position reconciliation on startup

**Classes**:
- `PositionReconciler` - Reconciliation logic
  - Compare local state vs exchange positions
  - Handle state mismatches
  - Emit reconciliation events

**Maps to**: Tech Arch Section 12.7, Design Doc Section 12.2

---

#### models.py
**Purpose**: Position data models

**Classes**:
- `Position` - Position dataclass
- `PositionState` - State enum (OPEN, CLOSING, CLOSED)

---

### 7. External Integrations (`src/integrations/`)

#### integrations/dex/aggregator_adapter.py
**Purpose**: DEX aggregator interface and standard quote format

**Classes**:
- `AggregatorQuote` - Standard quote dataclass (input_token, output_token, amounts, slippage, gas)
- `DEXAggregator(ABC)` - Abstract base class for all aggregators
  - `get_quote(input_token, output_token, amount, slippage_bps)` - Get swap quote
  - `execute_swap(quote, wallet_address)` - Execute swap
  - `get_supported_chains()` - Return list of supported chains

**Maps to**: Design Doc Section 2.2.0.0.1

---

#### integrations/dex/aggregator_factory.py
**Purpose**: Factory for selecting appropriate aggregator per chain

**Classes**:
- `AggregatorFactory` - Factory class
  - `get_aggregator(chain)` - Return appropriate aggregator (Jupiter for Solana, 1inch for EVM)
  - Caches aggregator instances
  - Config-driven selection with fallback support

**Maps to**: Design Doc Section 2.2.0.0.1

---

#### integrations/dex/jupiter_adapter.py
**Purpose**: Jupiter aggregator adapter for Solana

**Classes**:
- `JupiterAggregator(DEXAggregator)` - Jupiter implementation
  - Wraps Jupiter Python SDK
  - Converts Jupiter quotes to standard AggregatorQuote format
  - Handles Solana-specific token decimals

**Maps to**: Design Doc Section 9.3

---

#### integrations/dex/oneinch_adapter.py
**Purpose**: 1inch aggregator adapter for EVM chains

**Classes**:
- `OneInchAggregator(DEXAggregator)` - 1inch implementation
  - Wraps 1inch Python SDK
  - Supports Ethereum, Base, Arbitrum, Polygon, BSC
  - Chain ID mapping for multi-chain support

**Maps to**: Design Doc Section 9.3

---

#### integrations/cex/exchange_adapter.py
**Purpose**: Centralized exchange adapter interface

**Classes**:
- `ExchangeAdapter(ABC)` - Abstract base for CEX
  - `get_ticker(symbol)` - Get current price
  - `place_order(symbol, side, type, quantity, price)` - Place order
  - `get_balance(asset)` - Get balance
  - `cancel_order(symbol, order_id)` - Cancel order

**Maps to**: Design Doc Section 2.2.0.0.1

---

#### integrations/cex/binance_adapter.py
**Purpose**: Binance exchange adapter

**Classes**:
- `BinanceAdapter(ExchangeAdapter)` - Binance implementation
  - Uses CCXT or direct Binance API
  - Rate limit handling
  - Unified interface across spot and futures

---

#### integrations/cex/hyperliquid_adapter.py
**Purpose**: Hyperliquid perpetuals exchange adapter

**Classes**:
- `HyperliquidAdapter(ExchangeAdapter)` - Hyperliquid implementation
  - Custom SDK integration (non-Web3)
  - Perpetual contract trading
  - Funding rate access

**Maps to**: Design Doc Section 9.8

---

#### integrations/forex/forex_adapter.py
**Purpose**: Forex platform adapter interface

**Classes**:
- `ForexAdapter(ABC)` - Abstract base for forex platforms
  - `connect(server, login, password)` - Connect to broker
  - `get_symbol_info(symbol)` - Get symbol specifications
  - `place_order(symbol, type, volume, price, sl, tp)` - Place forex order
  - `get_positions()` - Get open positions
  - `close_position(position_id)` - Close position

**Maps to**: Design Doc Section 10

---

#### integrations/forex/mt5_adapter.py
**Purpose**: MetaTrader 5 platform adapter

**Classes**:
- `MT5Adapter(ForexAdapter)` - MT5 implementation
  - Uses MetaTrader5 Python package
  - Multi-broker support (IC Markets, Pepperstone, FTMO, etc.)
  - Server-specific connection handling
  - Symbol mapping (EURUSD vs EURUSD.raw)

**Maps to**: Design Doc Section 10.3

---

#### integrations/forex/ctrader_adapter.py
**Purpose**: cTrader platform adapter

**Classes**:
- `CTraderAdapter(ForexAdapter)` - cTrader implementation
  - FIX API integration
  - OpenAPI support

---

### 8. Notifications (`src/notifications/`)

#### service.py
**Purpose**: Notification orchestrator

**Classes**:
- `NotificationSystem` - Main service
  - Subscribes to important events
  - Routes events to appropriate handlers
  - Priority handling (critical/warning/info)

**State**: Reactive (triggered by events)

**Maps to**: Design Doc Section 2.2.0.2

---

#### sendgrid_client.py
**Purpose**: SendGrid API client

**Classes**:
- `SendGridNotificationService` - Email sender
  - `send_email(subject, body, priority)` - Send email
  - `notify_trade_signal()` - Signal notification
  - `notify_position_opened()` - Position notification
  - `notify_position_closed()` - Close notification
  - `notify_critical_error()` - Critical alert
  - `notify_order_failed()` - Order failure alert

**Maps to**: Tech Arch Section 3.0.2

---

#### templates.py
**Purpose**: HTML email templates

**Functions**:
- `render_signal_email(signal)` - Trade signal template
- `render_position_opened_email(position)` - Position opened template
- `render_position_closed_email(position)` - Position closed template
- `render_critical_error_email(error)` - Critical error template

---

#### priority.py
**Purpose**: Priority handling logic

**Classes**:
- `PriorityHandler` - Priority router
  - CRITICAL: Immediate email (order failures, connection loss)
  - WARNING: Should email (data quality issues)
  - INFO: Optional email (signals, fills)

---

### 9. Strategies (`src/strategies/`)

#### base.py
**Purpose**: Strategy interface

**Classes**:
- `TradingStrategy` - Abstract base
  - `evaluate(market_data)` - Evaluate strategy
  - `get_parameters()` - Strategy parameters

---

#### bid_ask_bounce.py
**Purpose**: Bid-ask bounce strategy

**Classes**:
- `BidAskBounceStrategy(TradingStrategy)` - Bounce strategy
  - Capture spread on quick reversals

**Maps to**: Design Doc Section 3.1

---

#### market_quality.py
**Purpose**: Market quality trading

**Classes**:
- `MarketQualityStrategy(TradingStrategy)` - Quality strategy
  - Trade high-quality setups only

**Maps to**: Design Doc Section 3.2

---

#### supply_demand.py
**Purpose**: Supply/demand zone strategy

**Classes**:
- `SupplyDemandStrategy(TradingStrategy)` - Zone strategy
  - Trade bounces from zones

---

#### strategy_manager.py
**Purpose**: Strategy selector and manager

**Classes**:
- `StrategyManager` - Strategy coordinator
  - Select active strategy
  - Strategy parameters
  - Strategy switching

---

### 10. Configuration (`src/config/`)

#### loader.py
**Purpose**: Configuration loader

**Classes**:
- `ConfigLoader` - Config loader
  - Load from YAML files
  - Load from Firestore
  - Merge configurations
  - Hot reload support

**Maps to**: Tech Arch Section 6.1

---

#### settings.py
**Purpose**: Configuration dataclasses

**Classes**:
- `ExchangeConfig` - Exchange settings
- `StrategyConfig` - Strategy parameters
- `RiskConfig` - Risk management rules
- `NotificationConfig` - Notification settings
- `SystemConfig` - System-wide settings

---

#### validator.py
**Purpose**: Configuration validation

**Classes**:
- `ConfigValidator` - Validator
  - Validate all config sections
  - Type checking
  - Range validation

---

#### firebase_sync.py
**Purpose**: Firebase Firestore synchronization

**Classes**:
- `FirestoreConfigSync` - Firestore sync
  - Sync configs to Firestore
  - Load configs from Firestore
  - Watch for config changes

---

### 11. Utilities (`src/utils/`)

#### logger.py
**Purpose**: Logging configuration

**Functions**:
- `setup_logging(log_level, log_dir)` - Configure logging
- Separate log files: app.log, trades.log, errors.log

**Maps to**: Tech Arch Section 10.2

---

#### metrics.py
**Purpose**: Performance metrics collection

**Classes**:
- `MetricsCollector` - Metrics collector
  - Event processing latency
  - Order execution latency
  - System health metrics

**Maps to**: Tech Arch Section 10.1

---

#### time_utils.py
**Purpose**: Time and timezone utilities

**Functions**:
- `utc_now()` - Current UTC timestamp
- `convert_timezone(dt, tz)` - Timezone conversion
- `parse_binance_timestamp(ts)` - Parse exchange timestamps

---

#### math_utils.py
**Purpose**: Mathematical and statistical functions

**Functions**:
- `calculate_std_dev(data)` - Standard deviation
- `calculate_correlation(x, y)` - Correlation coefficient
- `round_to_tick(price, tick_size)` - Round to tick size

---

### 12. API (Optional) (`src/api/`)

#### server.py
**Purpose**: FastAPI server for monitoring and control

**Classes**:
- `TradingAPI` - API server
  - Health check endpoints
  - Position monitoring
  - Manual control endpoints

---

#### routes.py
**Purpose**: API endpoint definitions

**Endpoints**:
- `GET /health` - Health check
- `GET /positions` - Get open positions
- `GET /metrics` - System metrics
- `POST /pause` - Pause trading
- `POST /resume` - Resume trading

---

#### websocket.py
**Purpose**: WebSocket for live updates

**Classes**:
- `WebSocketManager` - WebSocket manager
  - Stream live positions
  - Stream live P&L
  - Stream system events

---

## Configuration Structure

### config/config.yaml
**Main system configuration**

```yaml
system:
  environment: development  # development, staging, production
  log_level: INFO
  data_dir: /data

exchange:
  default_exchange: binance
  default_market: spot  # spot or futures

symbols:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT

timeframes:
  primary: 1m
  confirmation: [5m, 15m]

risk:
  max_concurrent_positions: 3
  position_size_pct: 2.0
  max_daily_loss_pct: 5.0

decision:
  min_confluence_score: 3.0
  enabled_strategies:
    - order_flow_scalping
    - supply_demand_bounce
```

---

### config/exchanges.yaml
**Exchange-specific configuration**

```yaml
binance:
  spot:
    api_key_env: BINANCE_API_KEY
    api_secret_env: BINANCE_API_SECRET
    rate_limit_per_minute: 1200
    order_type: limit
    time_in_force: IOC

  futures:
    api_key_env: BINANCE_FUTURES_API_KEY
    api_secret_env: BINANCE_FUTURES_API_SECRET
    rate_limit_per_minute: 2400
    leverage: 5
```

---

### config/strategies.yaml
**Strategy parameters**

```yaml
order_flow_scalping:
  enabled: true
  imbalance_threshold: 2.5
  lookback_seconds: 30
  min_trades_in_window: 5

supply_demand_bounce:
  enabled: true
  zone_strength_min: 70
  use_fresh_zones_only: true
```

---

### config/notifications.yaml
**Notification settings**

```yaml
sendgrid:
  api_key_env: SENDGRID_API_KEY
  from_email: algo-engine@yourdomain.com
  to_emails:
    - trader@example.com

priority_rules:
  critical:
    send_immediately: true
    retry_on_failure: true
    max_retries: 3
    events:
      - OrderFailed
      - MarketDataConnectionLost
      - SystemError

  warning:
    send_immediately: false
    batch_interval_seconds: 300

  info:
    send_immediately: false
    batch_interval_seconds: 600
```

---

### config/risk.yaml
**Risk management rules**

```yaml
position_sizing:
  default_pct: 2.0
  max_pct: 5.0

limits:
  max_concurrent_positions: 3
  max_daily_trades: 50
  max_daily_loss_pct: 5.0
  max_position_hold_time_minutes: 30

trailing_stop:
  regular_distance_pct: 0.5
  meme_distance_pct: 17.5
  activate_immediately: true

stop_loss:
  initial_distance_pct: 0.5
  max_distance_pct: 2.0
```

---

### config/portfolio_risk.yaml
**Portfolio-level risk monitoring configuration**

```yaml
portfolio_risk:
  enabled: true
  check_interval_seconds: 10  # Check portfolio health every 10 seconds

  # Daily drawdown circuit breaker
  max_daily_drawdown_pct: 5.0
  drawdown_levels:
    alert_pct: 2.0       # Log warning, notify user
    warning_pct: 3.0     # Close worst 50% of positions
    critical_pct: 4.0    # Close ALL positions
    circuit_breaker_pct: 5.0  # Close all + STOP TRADING

  # Correlation-based exits
  correlation_exit:
    enabled: true
    leaders: ['BTC', 'ETH']  # Monitor market leaders
    btc_dump_threshold_pct: 1.5  # Exit if BTC dumps >1.5% in 5 min
    min_correlation: 0.7  # Exit positions with >0.7 correlation
    rolling_window_hours: 24

  # Dump detection signals
  dump_detection:
    enabled: true
    volume_reversal:
      consecutive_candles: 3  # Sell > buy for 3 candles
      sell_buy_ratio: 1.5     # Sell volume > 1.5x Buy volume
    order_flow_flip:
      imbalance_threshold: 2.5  # Flip from 2.5:1 buy to 2.5:1 sell
    liquidity_drop:
      threshold_pct: 30    # DEX liquidity drops >30%
      window_minutes: 10
    momentum_break:
      lower_highs: 3       # 3 consecutive lower highs
      timeframe: '5m'      # Check on 5m candles

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
      score_30_action: close_worst_2           # Close worst 2 positions
      score_50_action: tighten_stops_to_0.3pct # Tighten stops to 0.3%
      score_70_action: stop_new_entries        # Stop opening new positions

  # Exit rules (NO time-based exits except forex session close)
  exit_rules:
    trailing_stop_pct: 0.5    # 0.5% for ALL markets (crypto, forex, meme coins)
    forex_session_close: true # Close forex positions before session end (Friday)
    no_time_based_exits: true # Hold as long as trailing stop not hit
```

---

### config/mempool.yaml
**Mempool monitoring configuration (EVM chains only)**

```yaml
mempool:
  enabled: true  # Only for EVM chains (Ethereum, Base, Polygon, BSC)

  chains:
    ethereum:
      rpc_url: ${ETHEREUM_RPC_URL}
      monitor_pending_txs: true
    base:
      rpc_url: ${BASE_RPC_URL}
      monitor_pending_txs: true
    polygon:
      rpc_url: ${POLYGON_RPC_URL}
      monitor_pending_txs: false  # Optional

  # MEV protection
  mev_protection:
    use_flashbots: true  # Ethereum only
    use_eden: false      # Alternative private mempool
    large_order_threshold_usd: 50000  # Use private mempool for orders > $50k

  # Gas price strategy
  gas_oracle:
    urgency_levels:
      low: 25th_percentile    # ~2 min
      normal: 50th_percentile # ~36 sec
      high: 75th_percentile   # ~12 sec
      urgent: 90th_percentile # immediate
```

---

### config/aggregators.yaml
**DEX aggregator configuration**

```yaml
aggregators:
  # Solana aggregators
  solana:
    primary: jupiter
    jupiter:
      api_url: https://quote-api.jup.ag/v6
      slippage_bps: 50  # 0.5%
      timeout_seconds: 10

  # EVM aggregators
  ethereum:
    primary: 1inch
    1inch:
      api_url: https://api.1inch.dev/swap/v5.2/1
      api_key: ${ONEINCH_API_KEY}
      slippage_bps: 50
      timeout_seconds: 10
    backup: matcha
    matcha:
      api_url: https://api.0x.org/swap/v1
      slippage_bps: 100

  base:
    primary: 1inch
    1inch:
      api_url: https://api.1inch.dev/swap/v5.2/8453
      api_key: ${ONEINCH_API_KEY}
      slippage_bps: 50
```

---

### config/forex_platforms.yaml
**Forex platform configuration**

```yaml
forex:
  # MetaTrader 5 (Priority #1)
  mt5:
    enabled: true
    brokers:
      ic_markets:
        server: ICMarketsSC-Demo
        login: ${MT5_IC_LOGIN}
        password: ${MT5_IC_PASSWORD}
      pepperstone:
        server: Pepperstone-Demo
        login: ${MT5_PEPPER_LOGIN}
        password: ${MT5_PEPPER_PASSWORD}
    symbols:
      - EURUSD
      - GBPUSD
      - XAUUSD  # Gold

  # cTrader (Priority #2)
  ctrader:
    enabled: false
    api_url: https://api.ctrader.com
    client_id: ${CTRADER_CLIENT_ID}
    client_secret: ${CTRADER_CLIENT_SECRET}

  # TradeLocker (Priority #3)
  tradelocker:
    enabled: false
    api_url: https://api.tradelocker.com
    api_key: ${TRADELOCKER_API_KEY}
```

---

## Data Directory Structure

### Per-Pair DuckDB Isolation - No Backups, No Archives

```
data/
├── binance/
│   ├── spot/
│   │   ├── BTCUSDT/
│   │   │   └── trading.duckdb          # Per-pair isolated database
│   │   ├── ETHUSDT/
│   │   │   └── trading.duckdb
│   │   ├── SOLUSDT/
│   │   │   └── trading.duckdb
│   │   └── [100+ more pairs...]
│   └── futures/
│       ├── BTCUSDT/
│       │   └── trading.duckdb
│       ├── ETHUSDT/
│       │   └── trading.duckdb
│       └── [100+ more pairs...]
│
├── bybit/
│   ├── spot/
│   │   ├── BTCUSDT/
│   │   │   └── trading.duckdb
│   │   └── ETHUSDT/
│   │       └── trading.duckdb
│   └── futures/
│       └── BTCUSDT/
│           └── trading.duckdb
│
├── dex/
│   ├── ethereum/
│   │   ├── WETH_USDC/
│   │   │   └── trading.duckdb
│   │   └── WBTC_USDC/
│   │       └── trading.duckdb
│   └── solana/
│       ├── SOL_USDC/
│       │   └── trading.duckdb
│       └── BONK_SOL/
│           └── trading.duckdb
│
└── logs/
    ├── app.log                         # Current logs only (auto-rotate, delete old)
    ├── trades.log
    └── errors.log
```

**Per-Pair Data Storage Philosophy**:
- ✅ **Realtime market data (ticks, candles)** → Flows into per-pair DuckDB for fast analytics
- ✅ **Analytics (CVD, order flow, market profile)** → Calculated and stored per-pair in DuckDB
- ✅ **Decisions/signals** → Generated from per-pair analytics, stored ephemerally per-pair
- ✅ **Trades** → Stored per-pair in DuckDB for performance tracking, tax records
- ✅ **Logs** → Current logs only, auto-rotate/delete old ones (no archive/)

**Why Per-Pair Isolation?**:
- ✅ **ZERO race conditions** - Each pair writes to its own DB file
- ✅ **True parallelism** - 100+ pairs can write simultaneously without contention
- ✅ **Crash isolation** - One pair's corruption doesn't affect others
- ✅ **Dynamic scaling** - Add/remove pairs without touching others
- ✅ **Simpler schema** - No symbol column needed (implied by path)
- ✅ **Better performance** - Single-column timestamp indexes, no compound keys

**Why NO Backups?**:
- ❌ No `backups/` directories - waste of disk space
- ❌ No duplicating data - DuckDB is already fast and efficient
- ❌ No long-term historical storage - realtime trading engine, not a data warehouse
- ✅ If we need historical data, re-fetch from exchange APIs on-demand

**Why NO Log Archives?**:
- ❌ No `archive/` directory - we don't need old logs
- ✅ Logs auto-rotate (keep last 7 days, delete older)
- ✅ Critical events are sent via email notifications
- ✅ Trades stored per-pair in DuckDB, so we have the important data

**Per-Pair DuckDB Benefits**:
- Fast in-memory analytics with disk persistence
- Window queries for order flow, market profile, etc. - per pair
- No need for backups - data is ephemeral, regenerated from realtime streams
- **Separate DB per trading pair = zero write contention**
- Each pair's DB is small (15 min of ticks = ~5-10 MB), fast to query

**Example Workflow**:
```python
# 100 pairs scan simultaneously - zero contention
for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', ...]:  # 100+ symbols
    db_path = f"data/binance/spot/{symbol}/trading.duckdb"
    conn = duckdb.connect(db_path)  # Each pair gets its own connection
    conn.execute("INSERT INTO ticks ...")  # No locks, no waiting
    analytics = conn.execute("SELECT cvd FROM order_flow").fetchone()
```

**Maps to**: Tech Arch Section 12.1

---

## Testing Structure

### tests/unit/
**Unit tests for individual components**

- `test_event_bus.py` - Event Bus functionality
- `test_di_container.py` - DI container resolution
- `test_order_flow.py` - Order flow calculations
- `test_decision_engine.py` - Signal generation logic
- `test_execution_pipeline.py` - Execution handlers
- `test_trailing_stop.py` - Trailing stop logic
- `test_analyzers.py` - Primary analyzers
- `test_filters.py` - Secondary filters

---

### tests/integration/
**Integration tests for component interactions**

- `test_data_pipeline.py` - Data ingestion → Database → Analytics
- `test_analytics_flow.py` - Analytics → Decision → Signal
- `test_trading_flow.py` - Signal → Execution → Position
- `test_event_flow.py` - End-to-end event flow

---

### tests/conftest.py
**Pytest fixtures**

```python
@pytest.fixture
def event_bus():
    """Create test event bus"""
    return EventBus()

@pytest.fixture
def di_container():
    """Create test DI container with mocks"""
    container = DependencyContainer()
    # Register mock services
    return container

@pytest.fixture
def mock_exchange():
    """Mock exchange adapter"""
    return MockExchange()
```

---

### tests/mocks/
**Mock objects for testing**

- `mock_exchange.py` - Mock exchange adapter
- `mock_event_bus.py` - Mock event bus
- `mock_database.py` - Mock database connection

---

## Design Document Mapping

### Core System Components

| Design Doc Section | File Location | Component |
|-------------------|---------------|-----------|
| 2.2.0 - DI Container | `src/core/di_container.py` | `DependencyContainer` |
| 2.2.0.1 - Event Bus | `src/core/event_bus.py` | `EventBus` |
| 2.2.0.2 - SendGrid | `src/notifications/sendgrid_client.py` | `SendGridNotificationService` |
| 2.2.1 - Data Ingestion | `src/market_data/stream/manager.py` | `MarketDataManager` |
| 2.2.2 - Decision Engine | `src/decision/engine.py` | `DecisionEngine` |

---

### Analytics Components

| Design Doc Section | File Location | Component |
|-------------------|---------------|-----------|
| PRIMARY #1 - Order Flow | `src/decision/analyzers/order_flow_analyzer.py` | `OrderFlowAnalyzer` |
| PRIMARY #2 - Microstructure | `src/decision/analyzers/microstructure_analyzer.py` | `MicrostructureAnalyzer` |
| FILTER #1 - Market Profile | `src/decision/filters/market_profile_filter.py` | `MarketProfileFilter` |
| FILTER #2 - Mean Reversion | `src/decision/filters/mean_reversion_filter.py` | `MeanReversionFilter` |
| FILTER #3 - Autocorrelation | `src/decision/filters/autocorrelation_filter.py` | `AutocorrelationFilter` |
| FILTER #4 - Demand Zones | `src/decision/filters/demand_zone_filter.py` | `DemandZoneFilter` |
| FILTER #5 - Supply Zones | `src/decision/filters/supply_zone_filter.py` | `SupplyZoneFilter` |
| FILTER #6 - Fair Value Gaps | `src/decision/filters/fvg_filter.py` | `FairValueGapFilter` |

---

### Execution & Position Management

| Design Doc Section | File Location | Component |
|-------------------|---------------|-----------|
| Execution Engine | `src/execution/engine.py` | `ExecutionEngine` |
| Execution Pipeline | `src/execution/pipeline.py` | `ExecutionPipeline` |
| CCXT Integration | `src/execution/exchanges/binance_ccxt.py` | `BinanceCCXTAdapter` |
| Direct API | `src/execution/exchanges/binance_direct.py` | `BinanceDirectAdapter` |
| Position Monitor | `src/position/monitor.py` | `PositionMonitor` |
| 8.1 - Trailing Stop | `src/position/trailing_stop.py` | `TrailingStopManager` |
| 13.2 - Reconciliation | `src/position/reconciliation.py` | `PositionReconciler` |

---

### Technical Architecture Mapping

| Tech Arch Section | File Location | Component |
|------------------|---------------|-----------|
| 3.0.1 - Event Bus | `src/core/event_bus.py` | `EventBus` |
| 3.0.2 - SendGrid | `src/notifications/sendgrid_client.py` | `SendGridNotificationService` |
| 3.2 - WebSocket Flow | `src/market_data/stream/cryptofeed_handler.py` | `CryptofeedHandler` |
| 4.0 - Multi-Exchange | `src/market_data/storage/database_manager.py` | `DatabaseManager` |
| 4.1 - Schema | `src/market_data/storage/schema.py` | Schema definitions |
| 4.2 - Query Patterns | `src/market_data/storage/queries.py` | SQL templates |
| 5.1 - Market Profile | `src/analytics/market_profile.py` | `MarketProfileAnalyzer` |
| 5.2 - Order Flow | `src/analytics/order_flow.py` | `OrderFlowAnalyzer` |
| 5.3 - Supply/Demand | `src/analytics/supply_demand.py` | `SupplyDemandDetector` |
| 5.4 - FVG | `src/analytics/fair_value_gap.py` | `FairValueGapDetector` |
| 5.6 - Confluence | `src/decision/confluence.py` | `ConfluenceCalculator` |
| 6.1 - Config Management | `src/config/loader.py` | `ConfigLoader` |
| 7.1 - CCXT | `src/execution/exchanges/binance_ccxt.py` | `BinanceCCXTAdapter` |
| 7.2 - Direct API | `src/execution/exchanges/binance_direct.py` | `BinanceDirectAdapter` |
| 8.1 - Trailing Stop | `src/position/trailing_stop.py` | `TrailingStopManager` |
| 12.1 - Per-Symbol DB | `src/market_data/storage/database_manager.py` | Database isolation |
| 12.2 - Connection Pool | `src/market_data/storage/connection_pool.py` | `ConnectionPoolManager` |
| 12.3 - DI Container | `src/core/di_container.py` | `DependencyContainer` |
| 12.4 - Execution Chain | `src/execution/pipeline.py` | `ExecutionPipeline` |
| 12.5 - Signal Composition | `src/decision/signal_pipeline.py` | Composition pattern |
| 12.7 - Reconciliation | `src/position/reconciliation.py` | `PositionReconciler` |
| 12.8 - Error Handling | `src/execution/handlers/executor.py` | Retry logic |
| 12.9 - Multi-Timeframe | `src/analytics/multi_timeframe.py` | `MultiTimeframeManager` |

---

## Key Architectural Principles

### 1. Event-Driven Architecture
- **ALL** component communication via Event Bus
- No direct coupling between components
- Reactive components triggered by events

### 2. Always-On vs Reactive
**Always-On (24/7)**:
- Event Bus (`src/core/event_bus.py`)
- Data Streaming (`src/market_data/stream/manager.py`)
- Analytics Engine (`src/analytics/engine.py`)
- Position Monitor (`src/position/monitor.py`)

**Reactive (Event-Triggered)**:
- Decision Engine (`src/decision/engine.py`)
- Execution Engine (`src/execution/engine.py`)
- Notification System (`src/notifications/service.py`)

### 3. Dependency Injection
- All services registered in DI container
- No global state or singletons
- Clear dependency graph
- Easy testing with mocks

### 4. Per-Pair Database Isolation (CRITICAL)
- **Separate DuckDB per trading pair** (not per exchange/market)
- ✅ **ZERO write contention** - Each pair writes to its own DB file
- ✅ **Zero race conditions** - Critical for scanning 100+ pairs simultaneously
- ✅ **Independent scaling** - Add/remove pairs dynamically
- ✅ **Crash isolation** - One pair's failure doesn't affect others
- ✅ **Better performance** - No symbol columns, simpler indexes

### 5. Connection Pooling (Per-Pair)
- Max 200 connections globally (distributed across all pairs)
- Each pair gets 1-2 dedicated connections from pool
- LRU eviction for inactive pairs (auto-cleanup)
- Prevents connection exhaustion across 100+ pairs

### 6. Composition Over Inheritance
- Primary analyzers as independent classes
- Secondary filters as composable components
- Execution handlers as chain of responsibility

### 7. Configuration Management
- YAML files for static config
- Firestore for dynamic config
- Environment variables for secrets
- Hot reload support

---

## Implementation Order

### Phase 1: Foundation
1. `src/core/event_bus.py` - Event Bus
2. `src/core/events.py` - Event definitions
3. `src/core/di_container.py` - DI Container
4. `src/market_data/storage/database_manager.py` - Database manager
5. `src/market_data/storage/schema.py` - Schema setup

### Phase 2: Data Pipeline
6. `src/market_data/stream/cryptofeed_handler.py` - WebSocket integration
7. `src/market_data/stream/manager.py` - Market data manager
8. `src/market_data/storage/connection_pool.py` - Connection pooling
9. `src/analytics/engine.py` - Analytics engine

### Phase 3: Decision System
10. `src/analytics/order_flow.py` - Order flow analyzer
11. `src/analytics/market_profile.py` - Market profile
12. `src/decision/analyzers/` - Primary analyzers
13. `src/decision/filters/` - Secondary filters
14. `src/decision/engine.py` - Decision engine

### Phase 4: Execution
15. `src/execution/exchanges/binance_ccxt.py` - Exchange adapter
16. `src/execution/handlers/` - Execution handlers
17. `src/execution/pipeline.py` - Execution pipeline
18. `src/execution/engine.py` - Execution engine

### Phase 5: Position Management
19. `src/position/trailing_stop.py` - Trailing stop
20. `src/position/monitor.py` - Position monitor
21. `src/position/reconciliation.py` - Reconciliation

### Phase 6: Supporting Systems
22. `src/notifications/sendgrid_client.py` - SendGrid integration
23. `src/notifications/service.py` - Notification system
24. `src/config/loader.py` - Config loader
25. `main.py` - Application entry point

---

## Summary

This project structure provides:

✅ **Clear separation of concerns** - Each component has a specific responsibility

✅ **Event-driven architecture** - All communication via Event Bus

✅ **Modular design** - Easy to add new analyzers, filters, exchanges

✅ **Testable code** - DI container enables easy mocking

✅ **Scalable database** - Per-exchange/market isolation with connection pooling

✅ **Production-ready** - Error handling, retry logic, reconciliation

✅ **Complete mapping** - Every design doc section has a corresponding code file

✅ **Buildable structure** - Ready for actual Python implementation

This is the REAL project structure where we'll write code, not abstract documentation. Every file listed here will contain actual Python classes and functions that implement the Algo Engine design.
