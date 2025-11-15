# Algorithmic Trading Engine - Technical Architecture

## 1. Overview

This document details the technical architecture for the algorithmic trading engine, focusing on the implementation specifics for market profile analysis, order flow trading, and multi-timeframe data processing using Python, Cryptofeed, CCXT, DuckDB, and Firebase.

---

## 2. Technology Stack Details

### 2.1 Core Technologies

**Python 3.12+**
- Async/await for concurrent WebSocket handling
- Type hints for code reliability
- Dataclasses for data structures
- Performance improvements and better error messages

**Cryptofeed** (Market Data - WebSocket)
- Real-time market data ingestion
- Support for Binance WebSocket API
- Callbacks for trades (tick data with actual executed prices) and candles
- Automatic reconnection handling
- **NO orderbook streaming** - orderbooks are heavily manipulated and unreliable

**CCXT** (Order Execution)
- Unified API for Binance and future exchanges
- Order placement, cancellation, modification
- Account balance queries
- Rate limit handling

**Direct Binance API** (Fallback)
- Lower latency for critical operations
- Access to Binance-specific features
- WebSocket user data streams for order updates

**DuckDB** (Analytics Database)
- Embedded SQL database with OLAP capabilities
- Columnar storage for fast analytical queries
- Native Python integration
- In-memory and persistent storage modes

**Firebase**
- Firestore: NoSQL database for state management
- Firebase Storage: Object storage for files/logs
- Python Admin SDK for integration

---

### 2.2 External Integrations & Adapter Pattern

**Swappable Adapter Architecture** for all external integrations (DEX aggregators, CEX, Forex platforms):

**DEX Aggregator Adapters**:
- **Jupiter** (Solana) - Best price routing across Raydium, Orca, Phoenix
- **1inch** (EVM chains) - Multi-chain aggregator for Ethereum, Base, Arbitrum, Polygon, BSC
- **Matcha** (0x Protocol) - Limit orders and aggregated liquidity
- **ParaSwap** (EVM chains) - Alternative aggregator with MEV protection

**DEX Technology Stack**:
- `web3.py` >= 6.0.0 - EVM chain interaction (Ethereum, Base, Arbitrum, Polygon, BSC)
- `solana` >= 0.30.0 - Solana blockchain interaction
- `solders` >= 0.18.0 - Solana Rust bindings for performance

**CEX Adapters**:
- **Binance** - Spot and futures trading via CCXT or direct API
- **Bybit** - Alternative CEX for geographic redundancy
- **Hyperliquid** - Perpetual contracts with ultra-low fees and funding rate arbitrage

**Forex Platform Adapters**:
- **MetaTrader 5** (MT5) - Priority #1, institutional-grade forex trading
  - `MetaTrader5` >= 5.0.0 Python package
  - Multi-broker support (IC Markets, Pepperstone, FTMO, MyForexFunds, etc.)
- **cTrader** - Priority #2, FIX API and OpenAPI support
- **TradeLocker** - Priority #3, modern cloud-based platform
- **MatchTrader** - Priority #3, multi-asset support

**Adapter Pattern Benefits**:
- ✅ Swap aggregators/exchanges via config (no code changes)
- ✅ Fallback support (if Jupiter is down, use Raydium SDK)
- ✅ Testable with mock adapters
- ✅ Add new integrations by implementing interface
- ✅ Unified error handling across all external services

**Interface Examples**:
```python
# All aggregators implement DEXAggregator interface
class DEXAggregator(ABC):
    async def get_quote(input_token, output_token, amount, slippage_bps) -> AggregatorQuote
    async def execute_swap(quote, wallet_address) -> str
    def get_supported_chains() -> list[str]

# All exchanges implement ExchangeAdapter interface
class ExchangeAdapter(ABC):
    async def place_order(symbol, side, type, quantity, price) -> str
    async def cancel_order(symbol, order_id) -> bool
    async def get_balance(asset) -> float

# All forex platforms implement ForexAdapter interface
class ForexAdapter(ABC):
    def connect(server, login, password) -> bool
    async def place_order(symbol, type, volume, price, sl, tp) -> str
    async def get_positions() -> List[Position]
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

# config/forex_platforms.yaml
forex:
  mt5:
    enabled: true
    priority: 1
    brokers:
      - ic_markets
      - pepperstone
      - ftmo
```

**Maps to**: Design Doc Section 2.2.0.0.1 (Adapter Pattern), Section 9 (DEX Trading), Section 10 (Forex Trading)

---

## 3. Data Flow Architecture

### 3.0 Event-Driven Architecture Overview

**THE HEART: Event Bus with 24/7 Components**

```
                          ┌──────────────────────────────────┐
                          │         EVENT BUS (💓 HEART)     │
                          │      asyncio.Queue(10000)        │
                          │    Pub/Sub Event Distribution    │
                          └──────────┬───────────────────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   │                 │                 │
                   ▼                 ▼                 ▼
         ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
         │ Data Streaming   │  │  Analytics   │  │ Notification │
         │   🔄 ALWAYS ON   │  │ 📊 ALWAYS ON │  │   📧 Email   │
         │    (24/7)        │  │   (24/7)     │  │  (SendGrid)  │
         └────────┬─────────┘  └──────┬───────┘  └──────────────┘
                  │                   │
                  │ Emits Events:     │ Emits Events:
                  │ - TickReceived    │ - SignalGenerated
                  │ - CandleUpdated   │ - PatternDetected
                  │                   │ - ConfluenceHigh
                  └───────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │Decision  │    │Execution │    │Position  │
   │ Engine   │    │ Engine   │    │ Monitor  │
   │ ⚡React  │    │ 🎯React  │    │ 👁️ Watch │
   └──────────┘    └──────────┘    └──────────┘
```

**Component Types**:
1. **24/7 Always-Running**: Data Streaming, Analytics Engine, Event Bus
2. **Event-Reactive**: Decision Engine, Execution Engine, Position Monitor
3. **Notification System**: SendGrid (reacts to critical events)

### 3.0.1 Event Bus Implementation

**Core Event Bus System**:
```python
import asyncio
from typing import Dict, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    """Base event class"""
    event_id: str
    timestamp: datetime
    source: str
    data: Dict[str, Any]

class TradeTickReceived(Event):
    """Emitted when new tick arrives from data stream"""
    pass

class SignalGeneratedEvent(Event):
    """Emitted when analytics detects a trading signal"""
    pass

class OrderPlacedEvent(Event):
    """Emitted when order is executed"""
    pass

class OrderFailedEvent(Event):
    """Emitted when order fails (CRITICAL)"""
    pass

class PositionOpenedEvent(Event):
    """Emitted when position is opened"""
    pass

class PositionClosedEvent(Event):
    """Emitted when position is closed"""
    pass

class SystemErrorEvent(Event):
    """Emitted on critical system errors"""
    pass

class ConnectionLostEvent(Event):
    """Emitted when connection to exchange lost"""
    pass

class EventBus:
    """
    THE HEART OF THE SYSTEM
    Central event distribution mechanism for all components
    """

    def __init__(self, max_queue_size: int = 10000):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_queue = asyncio.Queue(maxsize=max_queue_size)
        self.running = False
        self.processed_events = 0

    def subscribe(self, event_type: str, handler: Callable):
        """Register handler for specific event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unregister handler"""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(handler)

    async def publish(self, event: Event):
        """Publish event to queue (non-blocking)"""
        try:
            await self.event_queue.put(event)
        except asyncio.QueueFull:
            # Handle queue overflow - critical error
            print(f"[EVENT BUS] QUEUE FULL - Event dropped: {event}")

    async def process_events(self):
        """
        Main event processing loop - runs 24/7
        This is THE HEART of the system
        """
        self.running = True
        print("[EVENT BUS] 💓 HEART started - Processing events 24/7")

        while self.running:
            try:
                # Get event from queue
                event = await self.event_queue.get()

                # Get event type name
                event_type = event.__class__.__name__

                # Dispatch to all subscribers
                if event_type in self.subscribers:
                    # Run all handlers concurrently
                    await asyncio.gather(
                        *[handler(event) for handler in self.subscribers[event_type]],
                        return_exceptions=True
                    )

                self.processed_events += 1

                # Mark task as done
                self.event_queue.task_done()

            except Exception as e:
                print(f"[EVENT BUS] Error processing event: {e}")
                continue

    async def stop(self):
        """Stop event processing"""
        self.running = False
        print(f"[EVENT BUS] Stopped. Total events processed: {self.processed_events}")
```

### 3.0.2 SendGrid Notification System

**Email Notification Service**:
```python
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import asyncio
from typing import Optional

class SendGridNotificationService:
    """
    Email notification system for trading events
    Uses SendGrid API for reliable email delivery
    """

    # Priority levels
    PRIORITY_CRITICAL = "critical"  # 🔴 Immediate attention required
    PRIORITY_WARNING = "warning"    # 🟡 Important but not urgent
    PRIORITY_INFO = "info"          # 🟢 Informational

    def __init__(
        self,
        api_key: str,
        from_email: str,
        to_email: str
    ):
        self.sg = sendgrid.SendGridAPIClient(api_key=api_key)
        self.from_email = from_email
        self.to_email = to_email

    async def send_email(
        self,
        subject: str,
        html_body: str,
        priority: str = PRIORITY_INFO
    ):
        """Send email via SendGrid"""

        # Add priority indicator to subject
        priority_emoji = {
            self.PRIORITY_CRITICAL: "🔴",
            self.PRIORITY_WARNING: "🟡",
            self.PRIORITY_INFO: "🟢"
        }

        subject_with_priority = f"{priority_emoji.get(priority, '')} {subject}"

        message = Mail(
            from_email=Email(self.from_email),
            to_emails=To(self.to_email),
            subject=subject_with_priority,
            html_content=Content("text/html", html_body)
        )

        try:
            # Send email in thread pool (blocking I/O)
            response = await asyncio.to_thread(
                self.sg.send,
                message
            )
            print(f"[SendGrid] Email sent: {subject} (Status: {response.status_code})")
            return response

        except Exception as e:
            print(f"[SendGrid] Failed to send email: {e}")
            raise

    async def notify_trade_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        confluence_score: float
    ):
        """Send notification for buy/sell signal"""

        subject = f"Trade Signal: {direction.upper()} {symbol}"

        html_body = f"""
        <html>
        <body>
            <h2>Trading Signal Generated</h2>
            <p><strong>Symbol:</strong> {symbol}</p>
            <p><strong>Direction:</strong> {direction.upper()}</p>
            <p><strong>Entry Price:</strong> ${entry_price:,.2f}</p>
            <p><strong>Confluence Score:</strong> {confluence_score:.2f}/10.0</p>
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
        </body>
        </html>
        """

        await self.send_email(
            subject=subject,
            html_body=html_body,
            priority=self.PRIORITY_WARNING
        )

    async def notify_position_opened(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: float
    ):
        """Send notification when position is opened"""

        subject = f"Position Opened: {side.upper()} {symbol}"

        html_body = f"""
        <html>
        <body>
            <h2>Position Opened</h2>
            <p><strong>Symbol:</strong> {symbol}</p>
            <p><strong>Side:</strong> {side.upper()}</p>
            <p><strong>Entry Price:</strong> ${entry_price:,.2f}</p>
            <p><strong>Quantity:</strong> {quantity}</p>
            <p><strong>Stop Loss:</strong> ${stop_loss:,.2f}</p>
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
        </body>
        </html>
        """

        await self.send_email(
            subject=subject,
            html_body=html_body,
            priority=self.PRIORITY_INFO
        )

    async def notify_position_closed(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str
    ):
        """Send notification when position is closed"""

        subject = f"Position Closed: {side.upper()} {symbol} ({pnl_pct:+.2f}%)"

        pnl_color = "green" if pnl > 0 else "red"

        html_body = f"""
        <html>
        <body>
            <h2>Position Closed</h2>
            <p><strong>Symbol:</strong> {symbol}</p>
            <p><strong>Side:</strong> {side.upper()}</p>
            <p><strong>Entry Price:</strong> ${entry_price:,.2f}</p>
            <p><strong>Exit Price:</strong> ${exit_price:,.2f}</p>
            <p><strong>P&L:</strong> <span style="color: {pnl_color};">${pnl:,.2f} ({pnl_pct:+.2f}%)</span></p>
            <p><strong>Reason:</strong> {reason}</p>
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
        </body>
        </html>
        """

        await self.send_email(
            subject=subject,
            html_body=html_body,
            priority=self.PRIORITY_INFO
        )

    async def notify_critical_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None
    ):
        """Send critical error notification"""

        subject = f"CRITICAL ERROR: {error_type}"

        context_html = ""
        if context:
            context_html = "<h3>Context:</h3><ul>"
            for key, value in context.items():
                context_html += f"<li><strong>{key}:</strong> {value}</li>"
            context_html += "</ul>"

        html_body = f"""
        <html>
        <body>
            <h2 style="color: red;">Critical System Error</h2>
            <p><strong>Error Type:</strong> {error_type}</p>
            <p><strong>Message:</strong> {error_message}</p>
            {context_html}
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
            <p style="color: red;"><strong>ACTION REQUIRED: Check system immediately!</strong></p>
        </body>
        </html>
        """

        await self.send_email(
            subject=subject,
            html_body=html_body,
            priority=self.PRIORITY_CRITICAL
        )

    async def notify_order_failed(
        self,
        symbol: str,
        side: str,
        reason: str
    ):
        """Send notification when order fails"""

        subject = f"Order Failed: {side.upper()} {symbol}"

        html_body = f"""
        <html>
        <body>
            <h2 style="color: orange;">Order Execution Failed</h2>
            <p><strong>Symbol:</strong> {symbol}</p>
            <p><strong>Side:</strong> {side.upper()}</p>
            <p><strong>Failure Reason:</strong> {reason}</p>
            <p><strong>Time:</strong> {datetime.utcnow().isoformat()}</p>
        </body>
        </html>
        """

        await self.send_email(
            subject=subject,
            html_body=html_body,
            priority=self.PRIORITY_CRITICAL
        )
```

### 3.1 Real-Time Data Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                     CRYPTOFEED LAYER                         │
│         (TRADES ONLY - Real Executed Prices)                 │
│  ┌──────────────┐                      ┌──────────────┐     │
│  │  WebSocket   │                      │  WebSocket   │     │
│  │   Trades     │                      │   Candles    │     │
│  │  (Ticks)     │                      │  (1M/5M/15M) │     │
│  │ price, vol,  │                      │   (OHLCV)    │     │
│  │ side, time   │                      │              │     │
│  └──────┬───────┘                      └──────┬───────┘     │
│         │                                     │              │
│         └─────────────────────────────────────┘              │
│                            │                                 │
│    NO ORDERBOOK - It's manipulated with spoofing!           │
└────────────────────────────┼─────────────────────────────────┘
                             ▼
                        EVENT BUS
                      (TradeTickReceived)
                             │
        ┌────────────────────┼────────────────┐
        │                    │                │
        ▼                    ▼                ▼
┌───────────┐       ┌────────────────┐   ┌──────────────┐
│  DuckDB   │       │  Analytics     │   │  Firestore   │
│  Storage  │◀──────│  Engine        │──▶│  State Sync  │
│  (Insert) │       │  (Process)     │   │  (Positions) │
└───────────┘       └────────┬───────┘   └──────────────┘
                             │
                   (SignalGeneratedEvent)
                             ▼
                        EVENT BUS
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
   ┌─────────────────┐  ┌──────────┐  ┌──────────┐
   │ Decision Engine │  │SendGrid  │  │ Position │
   │   (Evaluate)    │  │(Notify)  │  │ Monitor  │
   └────────┬────────┘  └──────────┘  └──────────┘
            │
   (OrderExecutionEvent)
            ▼
       EVENT BUS
            │
            ▼
   ┌─────────────────────┐
   │  CCXT Order         │
   │  Execution          │
   └─────────────────────┘
```

### 3.2 WebSocket Data Flow (Cryptofeed)

**Connection Setup** (Multi-Market Support):
```python
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Binance, BinanceFutures
from cryptofeed.defines import TRADES, CANDLES

class MarketDataManager:
    """Manage WebSocket connections per exchange/market"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.feed_handlers = {}

    async def start_binance_spot(self, symbols: List[str]):
        """Start Binance SPOT market data feed"""
        fh = FeedHandler()
        fh.add_feed(
            Binance(
                symbols=symbols,
                channels=[TRADES, CANDLES],
                callbacks={
                    TRADES: self.handle_binance_spot_trade,
                    CANDLES: self.handle_binance_spot_candle
                }
            )
        )
        self.feed_handlers['binance_spot'] = fh
        await fh.run()

    async def start_binance_futures(self, symbols: List[str]):
        """Start Binance FUTURES market data feed"""
        fh = FeedHandler()
        fh.add_feed(
            BinanceFutures(  # Different feed for futures
                symbols=symbols,
                channels=[TRADES, CANDLES],
                callbacks={
                    TRADES: self.handle_binance_futures_trade,
                    CANDLES: self.handle_binance_futures_candle
                }
            )
        )
        self.feed_handlers['binance_futures'] = fh
        await fh.run()

    async def handle_binance_spot_trade(self, trade, receipt_timestamp):
        """Process SPOT market trade - write to per-pair database"""
        symbol = trade.symbol
        conn = self.db.get_connection('binance', 'spot', symbol)
        await self.insert_tick(conn, trade)

    async def handle_binance_futures_trade(self, trade, receipt_timestamp):
        """Process FUTURES market trade - write to per-pair database"""
        symbol = trade.symbol
        conn = self.db.get_connection('binance', 'futures', symbol)
        await self.insert_tick(conn, trade)

    async def insert_tick(self, conn, trade):
        """Insert tick to appropriate database"""
        conn.execute("""
            INSERT INTO ticks (timestamp, symbol, price, volume, side, trade_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [trade.timestamp, trade.symbol, trade.price,
              trade.amount, trade.side, trade.id])
```

**Data Processing Pipeline**:
1. WebSocket receives raw trade/candle data from Binance
2. Cryptofeed normalizes format (standardizes across exchanges)
3. Callback function receives structured data:
   - **Trade**: timestamp, symbol, price, volume, side (buy/sell aggressor)
   - **Candle**: timestamp, symbol, OHLCV data, timeframe
4. Data pushed to asyncio queue (non-blocking)
5. Consumer worker processes queue in batches
6. Data inserted into DuckDB (batch inserts for performance)
7. Analytics engine triggered on new data
8. Order flow and price behavior calculated from TRADES ONLY

**Why NO Orderbook?**
- Orderbooks are manipulated with spoofing (fake large orders)
- Whales place fake walls to induce fear/greed
- Orders get pulled right before execution
- TRADES show actual executed prices - the real market truth
- Price behavior and volume are sufficient for analysis

---

## 4. DuckDB Schema and Query Patterns

### 4.0 Multi-Exchange Data Organization

**Directory Structure**:
```
/data/
├── binance/
│   ├── spot/
│   │   └── trading.duckdb           # Binance spot market data (NO backups/)
│   └── futures/
│       └── trading.duckdb           # Binance futures market data (NO backups/)
├── bybit/
│   ├── spot/
│   │   └── trading.duckdb
│   └── futures/
│       └── trading.duckdb
└── dex/
    ├── ethereum/
    │   └── trading.duckdb
    └── solana/
        └── trading.duckdb
```

**Database Manager**:
```python
class DatabaseManager:
    """Manages multiple DuckDB connections per trading pair (per-pair isolation)"""

    def __init__(self, base_path='/data'):
        self.connections = {}

    def get_connection(self, exchange: str, market_type: str, symbol: str):
        """Get or create per-pair DuckDB connection"""
        key = f"{exchange}_{market_type}_{symbol}"
        if key not in self.connections:
            db_path = f"/data/{exchange}/{market_type}/{symbol}/trading.duckdb"
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.connections[key] = duckdb.connect(db_path)
        return self.connections[key]

# Usage - Each pair gets its own isolated database
db = DatabaseManager()
conn_btc = db.get_connection('binance', 'spot', 'BTCUSDT')
conn_eth = db.get_connection('binance', 'spot', 'ETHUSDT')
conn_sol = db.get_connection('binance', 'spot', 'SOLUSDT')
# All 3 can write simultaneously - ZERO contention
```

### 4.1 Schema Definitions (replicated per trading pair)

**Ticks Table** (Raw Trade Data - THE SOURCE OF TRUTH):
```sql
CREATE TABLE ticks (
    timestamp TIMESTAMP,
    price DECIMAL(18, 8),        -- Actual executed price (cannot be faked)
    volume DECIMAL(18, 8),       -- Actual traded volume
    side VARCHAR,                -- 'buy' or 'sell' (aggressor side)
    exchange VARCHAR,
    PRIMARY KEY (timestamp, side)  -- Allow same-time trades, different sides
);

-- NO symbol column - implied by database path (data/{exchange}/{market}/{symbol}/trading.duckdb)
-- NO compound index needed - simple timestamp index is faster
CREATE INDEX idx_ticks_ts ON ticks(timestamp);
CREATE INDEX idx_ticks_side ON ticks(side, timestamp);  -- For order flow analysis

-- This table contains ONLY real executed trades
-- No orderbook data = No manipulation = Pure truth
-- Per-pair isolation = Zero write contention across 100+ pairs
```

**Multi-Timeframe Candles** (Aggregated from Ticks):
```sql
CREATE TABLE candles_1m (
    timestamp TIMESTAMP,
    open DECIMAL(18, 8),
    high DECIMAL(18, 8),
    low DECIMAL(18, 8),
    close DECIMAL(18, 8),
    volume DECIMAL(18, 8),
    buy_volume DECIMAL(18, 8),   -- Volume from buy-side aggressor trades
    sell_volume DECIMAL(18, 8),  -- Volume from sell-side aggressor trades
    num_trades INTEGER,
    num_buy_trades INTEGER,
    num_sell_trades INTEGER,
    PRIMARY KEY (timestamp)
);

-- NO symbol column - implied by database path
-- Same schema for candles_5m and candles_15m tables

-- Similar schema for candles_5m and candles_15m (15M is maximum timeframe)
-- All aggregated from actual trade data (ticks table)
-- Buy/sell volume split provides order flow insight
```

**Order Flow Metrics** (Calculated from Trades Only):
```sql
CREATE TABLE order_flow (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    cvd DECIMAL(18, 8),              -- Cumulative Volume Delta (buy_vol - sell_vol)
    buy_volume DECIMAL(18, 8),       -- Total buy-side aggressor volume
    sell_volume DECIMAL(18, 8),      -- Total sell-side aggressor volume
    imbalance_ratio DECIMAL(8, 4),   -- buy_volume / sell_volume
    delta DECIMAL(18, 8),            -- buy_volume - sell_volume (for this period)
    aggressive_buys INTEGER,         -- Count of buy-aggressor trades
    aggressive_sells INTEGER,        -- Count of sell-aggressor trades
    avg_buy_size DECIMAL(18, 8),     -- Average size of buy trades
    avg_sell_size DECIMAL(18, 8),    -- Average size of sell trades
    PRIMARY KEY (timestamp, symbol)
);

CREATE INDEX idx_orderflow_symbol_ts ON order_flow(symbol, timestamp);

-- All metrics derived from ACTUAL TRADES (ticks table)
-- Buy-side aggressor = market buys (aggressive buyers)
-- Sell-side aggressor = market sells (aggressive sellers)
-- NO orderbook needed for true order flow analysis
```

**Market Profile**:
```sql
CREATE TABLE market_profile (
    timestamp TIMESTAMP,
    symbol VARCHAR,
    timeframe VARCHAR,  -- '1m', '5m', '15m' (max)
    poc_price DECIMAL(18, 8),        -- Point of Control
    value_area_high DECIMAL(18, 8),  -- Top of value area (70% volume)
    value_area_low DECIMAL(18, 8),   -- Bottom of value area
    profile_data JSON,                -- {price: volume} distribution
    profile_shape VARCHAR,            -- 'P', 'b', 'normal', etc.
    PRIMARY KEY (timestamp, symbol, timeframe)
);
```

**Supply/Demand Zones**:
```sql
CREATE TABLE supply_demand_zones (
    zone_id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    timeframe VARCHAR,
    zone_type VARCHAR,           -- 'supply' or 'demand'
    price_low DECIMAL(18, 8),
    price_high DECIMAL(18, 8),
    strength_score DECIMAL(4, 2), -- 0-100
    first_seen TIMESTAMP,
    last_tested TIMESTAMP,
    test_count INTEGER,
    status VARCHAR,              -- 'fresh', 'tested', 'broken'
    created_from VARCHAR         -- 'rejection', 'consolidation', etc.
);

CREATE INDEX idx_zones_symbol_status ON supply_demand_zones(symbol, status);
```

**Fair Value Gaps**:
```sql
CREATE TABLE fair_value_gaps (
    fvg_id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    timeframe VARCHAR,
    fvg_type VARCHAR,            -- 'bullish' or 'bearish'
    gap_low DECIMAL(18, 8),
    gap_high DECIMAL(18, 8),
    gap_size DECIMAL(18, 8),
    created_at TIMESTAMP,
    filled_at TIMESTAMP,
    fill_percentage DECIMAL(5, 2), -- 0-100
    status VARCHAR               -- 'open', 'partial', 'filled'
);

CREATE INDEX idx_fvg_symbol_status ON fair_value_gaps(symbol, status);
```

### 4.2 Query Patterns for Analytics

**Calculate Market Profile (POC and Value Area)**:
```sql
-- Get volume distribution by price for last hour
WITH volume_by_price AS (
    SELECT
        ROUND(price, 2) as price_level,
        SUM(volume) as total_volume
    FROM ticks
    WHERE symbol = 'BTC-USDT'
        AND timestamp >= NOW() - INTERVAL 1 HOUR
    GROUP BY price_level
    ORDER BY total_volume DESC
),
cumulative_volume AS (
    SELECT
        price_level,
        total_volume,
        SUM(total_volume) OVER (ORDER BY total_volume DESC) as cum_volume,
        SUM(total_volume) OVER () as total_vol
    FROM volume_by_price
)
SELECT
    (SELECT price_level FROM volume_by_price ORDER BY total_volume DESC LIMIT 1) as poc,
    MIN(CASE WHEN cum_volume / total_vol <= 0.70 THEN price_level END) as value_area_low,
    MAX(CASE WHEN cum_volume / total_vol <= 0.70 THEN price_level END) as value_area_high
FROM cumulative_volume;
```

**Calculate CVD (Cumulative Volume Delta)**:
```sql
SELECT
    timestamp,
    symbol,
    SUM(CASE WHEN side = 'buy' THEN volume ELSE -volume END)
        OVER (PARTITION BY symbol ORDER BY timestamp) as cvd
FROM ticks
WHERE symbol = 'BTC-USDT'
    AND timestamp >= NOW() - INTERVAL 4 HOURS
ORDER BY timestamp;
```

**Detect Order Flow Imbalance**:
```sql
WITH minute_aggregates AS (
    SELECT
        DATE_TRUNC('minute', timestamp) as minute,
        symbol,
        SUM(CASE WHEN side = 'buy' THEN volume ELSE 0 END) as buy_volume,
        SUM(CASE WHEN side = 'sell' THEN volume ELSE 0 END) as sell_volume
    FROM ticks
    WHERE timestamp >= NOW() - INTERVAL 1 HOUR
    GROUP BY minute, symbol
)
SELECT
    minute,
    symbol,
    buy_volume,
    sell_volume,
    CASE
        WHEN sell_volume > 0 THEN buy_volume / sell_volume
        ELSE NULL
    END as imbalance_ratio
FROM minute_aggregates
WHERE imbalance_ratio > 2.0  -- Significant buy pressure
    OR imbalance_ratio < 0.5   -- Significant sell pressure
ORDER BY minute DESC;
```

**Identify Fair Value Gaps**:
```sql
WITH candle_gaps AS (
    SELECT
        c1.timestamp as candle1_time,
        c1.high as candle1_high,
        c1.low as candle1_low,
        c3.timestamp as candle3_time,
        c3.high as candle3_high,
        c3.low as candle3_low,
        CASE
            WHEN c1.high < c3.low THEN 'bullish'
            WHEN c1.low > c3.high THEN 'bearish'
            ELSE NULL
        END as fvg_type,
        CASE
            WHEN c1.high < c3.low THEN c3.low - c1.high
            WHEN c1.low > c3.high THEN c1.low - c3.high
            ELSE 0
        END as gap_size
    FROM candles_1m c1
    JOIN candles_1m c3 ON c3.timestamp = c1.timestamp + INTERVAL 2 MINUTES
    WHERE c1.symbol = 'BTC-USDT'
        AND c1.timestamp >= NOW() - INTERVAL 4 HOURS
)
SELECT *
FROM candle_gaps
WHERE fvg_type IS NOT NULL
    AND gap_size > 0
ORDER BY candle3_time DESC;
```

**Multi-Timeframe Trend Alignment**:
```sql
-- Check if all timeframes agree on trend direction
WITH timeframe_trends AS (
    SELECT
        '1m' as tf,
        symbol,
        CASE WHEN close > open THEN 'bullish' ELSE 'bearish' END as trend
    FROM candles_1m
    WHERE timestamp = (SELECT MAX(timestamp) FROM candles_1m WHERE symbol = 'BTC-USDT')
        AND symbol = 'BTC-USDT'
    UNION ALL
    SELECT
        '15m' as tf,
        symbol,
        CASE WHEN close > open THEN 'bullish' ELSE 'bearish' END as trend
    FROM candles_15m
    WHERE timestamp = (SELECT MAX(timestamp) FROM candles_15m WHERE symbol = 'BTC-USDT')
        AND symbol = 'BTC-USDT'
)
SELECT
    symbol,
    COUNT(*) as total_timeframes,
    COUNT(CASE WHEN trend = 'bullish' THEN 1 END) as bullish_count,
    CASE
        WHEN COUNT(CASE WHEN trend = 'bullish' THEN 1 END) = COUNT(*) THEN 'ALIGNED_BULLISH'
        WHEN COUNT(CASE WHEN trend = 'bearish' THEN 1 END) = COUNT(*) THEN 'ALIGNED_BEARISH'
        ELSE 'MIXED'
    END as alignment
FROM timeframe_trends
GROUP BY symbol;
```

---

## 5. Analytics Engine Architecture

### 5.1 Market Profile Calculator

**Purpose**: Calculate Value Area, POC, and volume distribution

**Implementation Approach**:
```python
import duckdb
from typing import Dict, Tuple
from datetime import datetime, timedelta

class MarketProfileAnalyzer:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def calculate_profile(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        timeframe: str,  # '1m', '5m', '15m' (max)
        lookback_minutes: int
    ) -> Dict:
        """Calculate market profile for given timeframe"""

        # Get connection for specific exchange/market
        conn = self.db.get_connection(exchange, market_type)

        # Query volume by price
        query = """
        WITH volume_by_price AS (
            SELECT
                ROUND(price, 2) as price_level,
                SUM(volume) as total_volume
            FROM ticks
            WHERE symbol = ?
                AND timestamp >= NOW() - INTERVAL ? MINUTES
            GROUP BY price_level
        ),
        total AS (
            SELECT SUM(total_volume) as total_vol FROM volume_by_price
        ),
        ranked AS (
            SELECT
                price_level,
                total_volume,
                total_volume / total.total_vol as pct_volume,
                SUM(total_volume) OVER (ORDER BY total_volume DESC) / total.total_vol as cum_pct
            FROM volume_by_price, total
            ORDER BY total_volume DESC
        )
        SELECT
            price_level,
            total_volume,
            pct_volume,
            cum_pct
        FROM ranked;
        """

        result = conn.execute(query, [symbol, lookback_minutes]).fetchall()

        # Find POC (highest volume price)
        poc_price = result[0][0] if result else None

        # Find Value Area (70% of volume)
        value_area_prices = [row[0] for row in result if row[3] <= 0.70]
        value_area_high = max(value_area_prices) if value_area_prices else None
        value_area_low = min(value_area_prices) if value_area_prices else None

        return {
            'poc': poc_price,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low,
            'profile_data': {row[0]: row[1] for row in result}
        }
```

### 5.2 Order Flow Analyzer

**Purpose**: Detect order flow imbalances and CVD

**Implementation**:
```python
class OrderFlowAnalyzer:
    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)

    async def calculate_cvd(self, symbol: str, lookback_hours: int) -> float:
        """Calculate Cumulative Volume Delta"""

        query = """
        SELECT
            SUM(CASE WHEN side = 'buy' THEN volume ELSE -volume END) as cvd
        FROM ticks
        WHERE symbol = ?
            AND timestamp >= NOW() - INTERVAL ? HOURS;
        """

        result = self.conn.execute(query, [symbol, lookback_hours]).fetchone()
        return result[0] if result else 0.0

    async def detect_imbalance(self, symbol: str) -> Dict:
        """Detect current order flow imbalance (last 1 minute)"""

        query = """
        SELECT
            SUM(CASE WHEN side = 'buy' THEN volume ELSE 0 END) as buy_vol,
            SUM(CASE WHEN side = 'sell' THEN volume ELSE 0 END) as sell_vol
        FROM ticks
        WHERE symbol = ?
            AND timestamp >= NOW() - INTERVAL 1 MINUTE;
        """

        result = self.conn.execute(query, [symbol]).fetchone()
        buy_vol, sell_vol = result if result else (0, 0)

        imbalance_ratio = buy_vol / sell_vol if sell_vol > 0 else float('inf')

        return {
            'buy_volume': buy_vol,
            'sell_volume': sell_vol,
            'imbalance_ratio': imbalance_ratio,
            'signal': 'BUY' if imbalance_ratio > 2.0 else 'SELL' if imbalance_ratio < 0.5 else 'NEUTRAL'
        }
```

### 5.3 Supply/Demand Zone Detector

**Purpose**: Identify key support/resistance zones

**Implementation**:
```python
class SupplyDemandDetector:
    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)

    async def identify_zones(self, symbol: str, timeframe: str) -> List[Dict]:
        """Identify supply/demand zones from price action"""

        # Get candles for analysis
        table = f"candles_{timeframe.lower()}"
        query = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM {table}
        WHERE symbol = ?
            AND timestamp >= NOW() - INTERVAL 24 HOURS
        ORDER BY timestamp ASC;
        """

        candles = self.conn.execute(query, [symbol]).fetchall()

        zones = []

        # Identify demand zones (strong rejection from lows)
        for i in range(2, len(candles) - 1):
            prev_candle = candles[i-1]
            current = candles[i]
            next_candle = candles[i+1]

            # Bullish rejection pattern
            wick_size = current[2] - current[3]  # high - low
            body_size = abs(current[4] - current[1])  # close - open

            if wick_size > body_size * 2 and current[4] > current[1]:
                # Strong bullish rejection
                zones.append({
                    'type': 'demand',
                    'price_low': current[3],
                    'price_high': current[1],  # open price
                    'timestamp': current[0],
                    'strength': min(100, (wick_size / body_size) * 20)
                })

        return zones
```

### 5.4 Fair Value Gap Detector

**Purpose**: Detect FVG patterns for potential fill trades

**Implementation**:
```python
class FairValueGapDetector:
    def __init__(self, db_path: str):
        self.conn = duckdb.connect(db_path)

    async def detect_fvgs(self, symbol: str, timeframe: str) -> List[Dict]:
        """Detect Fair Value Gaps"""

        table = f"candles_{timeframe.lower()}"
        query = f"""
        WITH numbered_candles AS (
            SELECT
                timestamp,
                high,
                low,
                ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
            FROM {table}
            WHERE symbol = ?
                AND timestamp >= NOW() - INTERVAL 4 HOURS
        )
        SELECT
            c1.timestamp as time1,
            c1.high as c1_high,
            c1.low as c1_low,
            c3.timestamp as time3,
            c3.high as c3_high,
            c3.low as c3_low
        FROM numbered_candles c1
        JOIN numbered_candles c3 ON c3.rn = c1.rn - 2
        WHERE c1.high < c3.low OR c1.low > c3.high;
        """

        result = self.conn.execute(query, [symbol]).fetchall()

        fvgs = []
        for row in result:
            if row[1] < row[4]:  # c1_high < c3_low (bullish FVG)
                fvgs.append({
                    'type': 'bullish',
                    'gap_low': row[1],  # c1_high
                    'gap_high': row[4],  # c3_low
                    'size': row[4] - row[1],
                    'created_at': row[3]
                })
            elif row[2] > row[5]:  # c1_low > c3_high (bearish FVG)
                fvgs.append({
                    'type': 'bearish',
                    'gap_low': row[5],  # c3_high
                    'gap_high': row[2],  # c1_low
                    'size': row[2] - row[5],
                    'created_at': row[3]
                })

        return fvgs
```

### 5.6 Confluence Score Calculator

**Purpose**: Calculate weighted confluence score from primary signals and secondary filters

**Implementation**:
```python
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class ConfluenceSignal:
    """Result from confluence analysis"""
    score: float
    max_score: float
    primary_signals_met: bool
    secondary_breakdown: Dict[str, float]
    signal_direction: str  # 'long', 'short', or 'none'
    probability: str  # 'low', 'medium', 'high'

class ConfluenceScoreCalculator:
    """
    Calculates weighted confluence score from multiple signal sources
    PRIMARY signals must both be TRUE, then secondary filters are weighted
    """

    # Weight configuration (total: 10.0 points)
    WEIGHTS = {
        'market_profile': 1.5,
        'mean_reversion': 1.5,
        'autocorrelation': 1.0,
        'demand_zone': 2.0,
        'supply_zone': 0.5,
        'fvg': 1.5
    }

    # Thresholds
    THRESHOLD_LOW = 3.0      # Consider entry (low probability)
    THRESHOLD_MEDIUM = 5.0   # Strong entry signal
    THRESHOLD_HIGH = 7.0     # Very strong entry

    def __init__(self):
        self.max_possible_score = sum(self.WEIGHTS.values())

    async def calculate_confluence(
        self,
        # PRIMARY SIGNALS (both must be true)
        order_flow_signal: str,  # 'buy', 'sell', or 'neutral'
        microstructure_signal: str,  # 'bullish', 'bearish', or 'neutral'

        # SECONDARY FILTERS (weighted)
        market_profile_data: Dict,  # {poc, vah, val, current_price}
        mean_reversion_data: Dict,  # {price, ema, std_dev, distance_sigma}
        autocorrelation: float,  # r value (-1 to 1)
        demand_zones: List[Dict],  # [{price_low, price_high, touch_count}]
        supply_zones: List[Dict],  # [{price_low, price_high, touch_count}]
        fvg_data: List[Dict],  # [{type: 'bullish'/'bearish', gap_low, gap_high}]
        current_price: float
    ) -> ConfluenceSignal:
        """
        Calculate confluence score from all signals
        """

        # Step 1: Check PRIMARY signals (must both agree)
        if order_flow_signal == 'neutral' or microstructure_signal == 'neutral':
            return ConfluenceSignal(
                score=0.0,
                max_score=self.max_possible_score,
                primary_signals_met=False,
                secondary_breakdown={},
                signal_direction='none',
                probability='none'
            )

        # Determine direction from primary signals
        if order_flow_signal == 'buy' and microstructure_signal == 'bullish':
            signal_direction = 'long'
        elif order_flow_signal == 'sell' and microstructure_signal == 'bearish':
            signal_direction = 'short'
        else:
            # Primary signals conflict
            return ConfluenceSignal(
                score=0.0,
                max_score=self.max_possible_score,
                primary_signals_met=False,
                secondary_breakdown={},
                signal_direction='none',
                probability='none'
            )

        # Step 2: Calculate SECONDARY filter scores
        breakdown = {}
        total_score = 0.0

        # Market Profile scoring
        mp_score = self._score_market_profile(
            market_profile_data, current_price, signal_direction
        )
        breakdown['market_profile'] = mp_score
        total_score += mp_score

        # Mean Reversion scoring
        mr_score = self._score_mean_reversion(mean_reversion_data, signal_direction)
        breakdown['mean_reversion'] = mr_score
        total_score += mr_score

        # Autocorrelation scoring
        ac_score = self._score_autocorrelation(autocorrelation)
        breakdown['autocorrelation'] = ac_score
        total_score += ac_score

        # Demand Zone scoring
        dz_score = self._score_demand_zones(demand_zones, current_price, signal_direction)
        breakdown['demand_zone'] = dz_score
        total_score += dz_score

        # Supply Zone scoring
        sz_score = self._score_supply_zones(supply_zones, current_price, signal_direction)
        breakdown['supply_zone'] = sz_score
        total_score += sz_score

        # FVG scoring
        fvg_score = self._score_fvg(fvg_data, current_price, signal_direction)
        breakdown['fvg'] = fvg_score
        total_score += fvg_score

        # Determine probability level
        if total_score >= self.THRESHOLD_HIGH:
            probability = 'high'
        elif total_score >= self.THRESHOLD_MEDIUM:
            probability = 'medium'
        elif total_score >= self.THRESHOLD_LOW:
            probability = 'low'
        else:
            probability = 'insufficient'
            signal_direction = 'none'

        return ConfluenceSignal(
            score=total_score,
            max_score=self.max_possible_score,
            primary_signals_met=True,
            secondary_breakdown=breakdown,
            signal_direction=signal_direction,
            probability=probability
        )

    def _score_market_profile(self, mp_data: Dict, current_price: float, direction: str) -> float:
        """Score market profile position"""
        if not mp_data:
            return 0.0

        vah = mp_data.get('value_area_high')
        val = mp_data.get('value_area_low')
        poc = mp_data.get('poc')

        if not all([vah, val, poc]):
            return 0.0

        # At value area extremes: full weight
        if direction == 'long' and abs(current_price - val) < (vah - val) * 0.05:
            return self.WEIGHTS['market_profile']  # 1.5
        elif direction == 'short' and abs(current_price - vah) < (vah - val) * 0.05:
            return self.WEIGHTS['market_profile']  # 1.5

        # Inside value area: partial weight
        if val <= current_price <= vah:
            return self.WEIGHTS['market_profile'] * 0.33  # 0.5

        return 0.0

    def _score_mean_reversion(self, mr_data: Dict, direction: str) -> float:
        """Score mean reversion distance"""
        distance_sigma = mr_data.get('distance_sigma', 0.0)

        # Beyond 2σ: full weight
        if abs(distance_sigma) >= 2.0:
            # Check if direction aligns with mean reversion
            if (direction == 'long' and distance_sigma < -2.0) or \
               (direction == 'short' and distance_sigma > 2.0):
                return self.WEIGHTS['mean_reversion']  # 1.5

        # Beyond 1σ: partial weight
        if abs(distance_sigma) >= 1.0:
            if (direction == 'long' and distance_sigma < -1.0) or \
               (direction == 'short' and distance_sigma > 1.0):
                return self.WEIGHTS['mean_reversion'] * 0.5  # 0.75

        return 0.0

    def _score_autocorrelation(self, r: float) -> float:
        """Score autocorrelation value"""
        # High correlation (trend) OR low correlation (range/mean reversion)
        if abs(r) > 0.6 or abs(r) < 0.3:
            return self.WEIGHTS['autocorrelation']  # 1.0

        # Medium correlation
        return self.WEIGHTS['autocorrelation'] * 0.5  # 0.5

    def _score_demand_zones(self, zones: List[Dict], current_price: float, direction: str) -> float:
        """Score demand zone proximity and freshness"""
        if not zones or direction != 'long':
            return 0.0

        # Find nearest demand zone below current price
        nearest_zone = None
        min_distance = float('inf')

        for zone in zones:
            zone_high = zone.get('price_high', 0)
            if zone_high <= current_price:
                distance = current_price - zone_high
                if distance < min_distance:
                    min_distance = distance
                    nearest_zone = zone

        if not nearest_zone:
            return 0.0

        # Check if we're near the zone (within 0.5%)
        if min_distance / current_price > 0.005:
            return 0.0

        # Fresh zone (untested): full weight
        touch_count = nearest_zone.get('touch_count', 0)
        if touch_count == 0:
            return self.WEIGHTS['demand_zone']  # 2.0

        # Tested zone (1-2 touches): half weight
        if touch_count <= 2:
            return self.WEIGHTS['demand_zone'] * 0.5  # 1.0

        return 0.0

    def _score_supply_zones(self, zones: List[Dict], current_price: float, direction: str) -> float:
        """Score supply zone as profit target"""
        if not zones:
            return 0.0

        # For long: supply above as target
        # For short: supply below not relevant
        if direction == 'long':
            for zone in zones:
                zone_low = zone.get('price_low', 0)
                if zone_low > current_price:
                    # Supply zone exists above as target
                    return self.WEIGHTS['supply_zone']  # 0.5

        elif direction == 'short':
            for zone in zones:
                zone_high = zone.get('price_high', 0)
                if zone_high < current_price:
                    # Supply zone exists below as target
                    return self.WEIGHTS['supply_zone']  # 0.5

        return 0.0

    def _score_fvg(self, fvgs: List[Dict], current_price: float, direction: str) -> float:
        """Score fair value gap in trade direction"""
        if not fvgs:
            return 0.0

        for fvg in fvgs:
            fvg_type = fvg.get('type')
            gap_low = fvg.get('gap_low', 0)
            gap_high = fvg.get('gap_high', 0)

            # For long: look for bullish FVG above current price
            if direction == 'long' and fvg_type == 'bullish' and gap_low > current_price:
                return self.WEIGHTS['fvg']  # 1.5

            # For short: look for bearish FVG below current price
            if direction == 'short' and fvg_type == 'bearish' and gap_high < current_price:
                return self.WEIGHTS['fvg']  # 1.5

        return 0.0
```

---

## 6. Trading Configuration System

### 6.1 Configuration Management (Firestore)

**Document Structure**:
```json
{
  "trading_configs": {
    "config_1": {
      "name": "Ultra-Short Scalping",
      "timeframes": ["1m", "5m", "15m"],
      "primary_timeframe": "1m",
      "hold_duration_seconds": [30, 300],
      "target_trades_per_hour": 10,
      "risk_reward": 1.5,
      "enabled_strategies": ["order_flow_scalping", "bid_ask_bounce"],
      "position_size_pct": 2.0,
      "max_concurrent_positions": 3
    },
    "config_2": {
      "name": "Micro-Trend Following",
      "timeframes": ["1m", "15m", "1h"],
      "primary_timeframe": "1m",
      "hold_duration_seconds": [300, 900],
      "target_trades_per_day": 20,
      "risk_reward": 2.0,
      "enabled_strategies": ["supply_demand_bounce", "order_flow_scalping"],
      "position_size_pct": 3.0,
      "max_concurrent_positions": 2
    }
  },
  "active_config": "config_1"
}
```

### 6.2 Strategy Parameters per Configuration

**Config 1: Ultra-Short Scalping**:
- Focus on 1M chart with 5M/15M filters
- Quick entries on order flow imbalances
- Initial stop-loss: 0.2-0.3% (at demand/supply zone)
- **Trailing stop-loss: 0.5% distance** (activates immediately)
- Quick profit targets (0.5-1.0%)
- High win rate required (>60%)

**Config 2: Micro-Trend Following**:
- Focus on 1M entries with 5M/15M trend confirmation
- Enter at supply/demand zones
- Initial stop-loss: 0.5-0.8% (at zone boundary)
- **Trailing stop-loss: 0.5% distance** (activates immediately)
- Larger profit targets (1.0-2.0%)
- Lower win rate acceptable (>50%)

---

## 7. Order Execution Architecture

### 7.1 CCXT Integration

**Exchange Connection**:
```python
import ccxt.async_support as ccxt

class OrderExecutor:
    def __init__(self, api_key: str, api_secret: str):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # or 'spot'
            }
        })

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float = None
    ):
        """Place order via CCXT"""
        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type=order_type,  # 'limit', 'market'
                side=side,  # 'buy', 'sell'
                amount=amount,
                price=price,
                params={
                    'timeInForce': 'IOC'  # Immediate or Cancel
                }
            )
            return order
        except Exception as e:
            # Handle errors
            print(f"Order failed: {e}")
            return None
```

### 7.2 Direct Binance API (Fallback)

**For lower latency and WebSocket order updates**:
```python
from binance.client import AsyncClient
from binance.enums import *

class BinanceDirectExecutor:
    def __init__(self, api_key: str, api_secret: str):
        self.client = None

    async def initialize(self):
        self.client = await AsyncClient.create(
            api_key=self.api_key,
            api_secret=self.api_secret
        )

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float
    ):
        """Place limit order with post-only option"""
        order = await self.client.create_order(
            symbol=symbol,
            side=SIDE_BUY if side == 'buy' else SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=price,
            newOrderRespType='RESULT'
        )
        return order
```

---

## 8. Trailing Stop-Loss System

### 8.1 TrailingStopManager Implementation

```python
from typing import Dict
from datetime import datetime

class TrailingStopManager:
    """
    Manages trailing stop-losses for all open positions
    - Regular trading (Binance, Forex): 0.5% trailing distance
    - High-volatility (Meme coins): 15-20% trailing distance
    """

    def __init__(self, db_manager: DatabaseManager, executor: OrderExecutor):
        self.db = db_manager
        self.executor = executor
        self.positions = {}  # {position_id: position_data}
        self.position_locks = {}  # {position_id: asyncio.Lock()} for thread-safe updates
        self.global_lock = asyncio.Lock()  # For adding/removing positions

        # Trailing distance configuration by asset type
        self.TRAILING_DISTANCE_REGULAR = 0.5  # 0.5% for regular crypto/forex
        self.TRAILING_DISTANCE_MEME = 17.5     # 17.5% for meme coins (avg of 15-20%)

    async def add_position(self, position: Dict):
        """
        Add position to trailing stop tracking
        Activates immediately on entry
        """
        position_id = position['position_id']

        # Determine asset type and appropriate trailing distance
        asset_type = position.get('asset_type', 'regular')  # 'regular' or 'meme'
        trailing_pct = self._get_trailing_distance(asset_type)

        async with self.global_lock:
            self.positions[position_id] = {
                'symbol': position['symbol'],
                'side': position['side'],  # 'long' or 'short'
                'entry_price': position['entry_price'],
                'quantity': position['quantity'],
                'exchange': position['exchange'],
                'market_type': position['market_type'],
                'asset_type': asset_type,
                'trailing_distance_pct': trailing_pct,

                # Trailing stop state
                'highest_price': position['entry_price'] if position['side'] == 'long' else None,
                'lowest_price': position['entry_price'] if position['side'] == 'short' else None,
                'trailing_stop_price': self._calculate_initial_stop(position, trailing_pct),
                'stop_triggered': False,
                'created_at': datetime.utcnow()
            }
            # Create dedicated lock for this position
            self.position_locks[position_id] = asyncio.Lock()

    def _get_trailing_distance(self, asset_type: str) -> float:
        """Get appropriate trailing distance based on asset type"""
        if asset_type == 'meme':
            return self.TRAILING_DISTANCE_MEME  # 17.5%
        else:
            return self.TRAILING_DISTANCE_REGULAR  # 0.5%

    def _calculate_initial_stop(self, position: Dict, trailing_pct: float) -> float:
        """Calculate initial trailing stop price"""
        entry = position['entry_price']
        distance = entry * (trailing_pct / 100)

        if position['side'] == 'long':
            # Long: stop below entry
            return entry - distance
        else:
            # Short: stop above entry
            return entry + distance

    async def update_on_tick(self, symbol: str, current_price: float):
        """
        Update trailing stops for all positions of this symbol
        Called on EVERY tick update
        Thread-safe with per-position locks to prevent race conditions
        """
        # Get all position IDs for this symbol (read-only, no lock needed)
        position_ids = [pid for pid, pos in self.positions.items()
                       if pos['symbol'] == symbol and not pos['stop_triggered']]

        # Update each position sequentially with its own lock
        for position_id in position_ids:
            if position_id not in self.position_locks:
                continue  # Position was removed

            async with self.position_locks[position_id]:
                # Re-check position exists (could have been removed while waiting for lock)
                if position_id not in self.positions:
                    continue

                pos = self.positions[position_id]

                # Double-check symbol and stop status
                if pos['symbol'] != symbol or pos['stop_triggered']:
                    continue

                # Update highest/lowest price reached
                if pos['side'] == 'long':
                    if current_price > pos['highest_price']:
                        pos['highest_price'] = current_price
                        # Trail stop using position-specific distance
                        new_stop = current_price * (1 - pos['trailing_distance_pct'] / 100)
                        # Stop can only move UP (never down)
                        if new_stop > pos['trailing_stop_price']:
                            pos['trailing_stop_price'] = new_stop
                            print(f"[TSL] {symbol} Long stop trailed up to {new_stop:.8f}")

                    # Check if stop hit
                    if current_price <= pos['trailing_stop_price']:
                        await self._trigger_stop(position_id, current_price, "Trailing stop hit")

                elif pos['side'] == 'short':
                    if current_price < pos['lowest_price']:
                        pos['lowest_price'] = current_price
                        # Trail stop using position-specific distance
                        new_stop = current_price * (1 + pos['trailing_distance_pct'] / 100)
                        # Stop can only move DOWN (never up)
                        if new_stop < pos['trailing_stop_price']:
                            pos['trailing_stop_price'] = new_stop
                            print(f"[TSL] {symbol} Short stop trailed down to {new_stop:.8f}")

                    # Check if stop hit
                    if current_price >= pos['trailing_stop_price']:
                        await self._trigger_stop(position_id, current_price, "Trailing stop hit")

    async def _trigger_stop(self, position_id: str, exit_price: float, reason: str):
        """
        Execute trailing stop-loss
        NOTE: This method is called while holding the position lock,
        so position state is already protected
        """
        pos = self.positions[position_id]
        pos['stop_triggered'] = True

        print(f"[TSL] STOP TRIGGERED: {pos['symbol']} {pos['side']} at {exit_price:.8f} - {reason}")

        # Execute market order to close position
        await self.executor.close_position(
            exchange=pos['exchange'],
            market_type=pos['market_type'],
            position_id=position_id,
            exit_price=exit_price,
            reason=reason
        )

        # Calculate P&L
        if pos['side'] == 'long':
            pnl_pct = ((exit_price - pos['entry_price']) / pos['entry_price']) * 100
        else:
            pnl_pct = ((pos['entry_price'] - exit_price) / pos['entry_price']) * 100

        print(f"[TSL] Position closed - P&L: {pnl_pct:.2f}%")

        # Remove from tracking (lock will be released by caller)
        async with self.global_lock:
            if position_id in self.positions:
                del self.positions[position_id]
            if position_id in self.position_locks:
                del self.position_locks[position_id]

    async def remove_position(self, position_id: str):
        """Remove position from trailing stop tracking (manual close)"""
        async with self.global_lock:
            if position_id in self.positions:
                del self.positions[position_id]
            if position_id in self.position_locks:
                del self.position_locks[position_id]

    def get_position_info(self, position_id: str) -> Dict:
        """Get current trailing stop info for position"""
        if position_id not in self.positions:
            return None

        pos = self.positions[position_id]
        return {
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry_price': pos['entry_price'],
            'trailing_stop_price': pos['trailing_stop_price'],
            'highest_price': pos['highest_price'],
            'lowest_price': pos['lowest_price'],
            'distance_pct': self.TRAILING_DISTANCE_PCT
        }
```

### 8.2 Integration with Trading Engine

```python
class TradingEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.executor = OrderExecutor()
        self.trailing_stop = TrailingStopManager(self.db, self.executor)
        self.market_data = MarketDataManager(self.db)

    async def handle_trade(self, trade, receipt_timestamp):
        """Process incoming tick and update trailing stops"""

        # 1. Store tick in DuckDB
        await self.db.insert_tick(trade)

        # 2. Update ALL trailing stops for this symbol
        await self.trailing_stop.update_on_tick(trade.symbol, trade.price)

        # 3. Run analytics and generate signals
        signal = await self.analytics.analyze(trade)

        # 4. If new signal, execute trade
        if signal:
            position = await self.executor.place_order(signal)

            # 5. Add to trailing stop tracking immediately
            await self.trailing_stop.add_position(position)

    async def manual_close_position(self, position_id: str):
        """Manual position close (user-initiated)"""

        # 1. Remove from trailing stop tracking
        await self.trailing_stop.remove_position(position_id)

        # 2. Execute close order
        await self.executor.close_position(position_id)
```

### 8.3 Trailing Stop-Loss for Different Markets

**Crypto (Binance Spot/Futures)**:
- 0.5% trailing distance works well for volatility
- Updated on every tick (high-frequency)
- No native trailing stop support, managed in-app

**Forex (MT5/TradeLocker/cTrader)**:
- 0.5% = ~50 pips on EUR/USD (depending on price)
- Can use platform native trailing stops OR manage in-app
- Prefer in-app management for consistency

**Implementation Example for Binance**:
```python
# Position enters at $50,000
# Trailing stop: $49,750 (0.5% below)

# Price moves to $50,500
# Trailing stop: $50,247.50 (0.5% below new high)

# Price moves to $51,000
# Trailing stop: $50,745 (0.5% below new high)

# Price drops to $50,745
# STOP TRIGGERED - Position closed at $50,745
# Profit: +1.49% (instead of risking reversal)
```

---

### 8.3 Portfolio Risk Manager Implementation

**Purpose**: Portfolio-level monitoring and proactive dump detection to protect entire account.

**Core Components**:

```python
from typing import Dict, List
from dataclasses import dataclass
import asyncio

@dataclass
class PortfolioHealth:
    """Portfolio health snapshot"""
    timestamp: datetime
    total_positions: int
    total_unrealized_pnl: float
    health_score: float  # 0-100
    btc_correlation_avg: float
    daily_drawdown_pct: float
    action_taken: str

class PortfolioRiskManager:
    """
    Monitor ALL positions simultaneously
    Exit positions BEFORE trailing stops hit when dump signals detected
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        executor: OrderExecutor,
        event_bus: EventBus,
        config: Dict
    ):
        self.db = db_manager
        self.executor = executor
        self.event_bus = event_bus
        self.config = config['portfolio_risk']

        # Sub-components
        self.dump_detector = DumpDetector(config)
        self.correlation_monitor = CorrelationMonitor(config)
        self.health_monitor = PortfolioHealthMonitor(config)
        self.circuit_breaker = DrawdownCircuitBreaker(config)
        self.hold_time_enforcer = HoldTimeEnforcer(config)

        # State
        self.open_positions: Dict[str, Dict] = {}
        self.daily_pnl: float = 0.0
        self.session_start_balance: float = 0.0

    async def start(self):
        """Start portfolio monitoring (runs 24/7)"""
        # Subscribe to events
        self.event_bus.subscribe("PositionOpened", self.on_position_opened)
        self.event_bus.subscribe("PositionClosed", self.on_position_closed)
        self.event_bus.subscribe("TradeTickReceived", self.on_tick_received)
        self.event_bus.subscribe("CandleCompleted", self.on_candle_completed)

        # Start monitoring loops
        await asyncio.gather(
            self.check_portfolio_health(),
            self.monitor_correlations(),
            self.enforce_hold_times()
        )

    async def on_position_opened(self, event):
        """Track new position"""
        position = event.position
        self.open_positions[position['id']] = position
        print(f"[Portfolio] Tracking new position: {position['symbol']}")

    async def on_position_closed(self, event):
        """Remove closed position"""
        position_id = event.position_id
        if position_id in self.open_positions:
            del self.open_positions[position_id]

    async def on_tick_received(self, event):
        """Check for dumps on every tick"""
        for position_id, position in self.open_positions.items():
            if position['symbol'] == event.symbol:
                # Check dump signals
                if await self.dump_detector.detect_dump(position, event.price):
                    await self._force_exit(
                        position_id,
                        reason="Dump detected",
                        price=event.price
                    )

    async def on_candle_completed(self, event):
        """Update correlations every 5 minutes"""
        if event.timeframe == '5m':
            await self.correlation_monitor.update_correlations(
                self.open_positions
            )

            # Check for market leader dumps
            if await self.correlation_monitor.check_btc_dump():
                await self._exit_correlated_positions('BTC')

    async def check_portfolio_health(self):
        """Monitor portfolio health every 10 seconds"""
        while True:
            await asyncio.sleep(self.config['check_interval_seconds'])

            if not self.open_positions:
                continue

            # Calculate health score
            health = await self.health_monitor.calculate_health(
                self.open_positions
            )

            # Take action based on score
            if health.score < 30:
                # CRITICAL: Close worst 2 positions
                await self._close_worst_positions(2)
                self.event_bus.publish(PortfolioHealthDegraded(health))

            elif health.score < 50:
                # WARNING: Tighten all stops
                await self._tighten_all_stops(0.3)
                self.event_bus.publish(PortfolioHealthDegraded(health))

            elif health.score < 70:
                # CAUTION: Stop new entries
                self.event_bus.publish(StopNewEntries(reason="Portfolio health degraded"))

            # Check circuit breaker
            if self.circuit_breaker.should_trigger(self.daily_pnl):
                await self._trigger_circuit_breaker()

    async def monitor_correlations(self):
        """Check market leader dumps every 1 minute"""
        while True:
            await asyncio.sleep(60)  # Check every minute

            # Monitor BTC dumps
            btc_dump = await self.correlation_monitor.check_leader_dump('BTC')
            if btc_dump:
                print(f"[Portfolio] BTC dump detected: {btc_dump['pct_change']:.2f}%")
                await self._exit_correlated_positions('BTC', min_correlation=0.7)

    async def enforce_hold_times(self):
        """Force close positions exceeding max hold time"""
        while True:
            await asyncio.sleep(60)  # Check every minute

            for position_id, position in list(self.open_positions.items()):
                should_close, reason = self.hold_time_enforcer.should_close(position)
                if should_close:
                    await self._force_exit(
                        position_id,
                        reason=reason,
                        price=None  # Market close
                    )

    async def _force_exit(self, position_id: str, reason: str, price: float = None):
        """Force exit position immediately"""
        if position_id not in self.open_positions:
            return

        position = self.open_positions[position_id]
        print(f"[Portfolio] FORCE EXIT: {position['symbol']} - {reason}")

        # Execute market close
        await self.executor.close_position(
            exchange=position['exchange'],
            market_type=position['market_type'],
            position_id=position_id,
            exit_price=price,  # None = market order
            reason=reason
        )

        # Emit event
        self.event_bus.publish(ForceExitRequired(
            position_id=position_id,
            reason=reason
        ))

    async def _exit_correlated_positions(self, leader: str, min_correlation: float = 0.7):
        """Exit all positions highly correlated with market leader"""
        correlated = await self.correlation_monitor.get_correlated_positions(
            leader,
            self.open_positions,
            min_correlation
        )

        print(f"[Portfolio] Exiting {len(correlated)} positions correlated with {leader}")

        for position_id in correlated:
            await self._force_exit(
                position_id,
                reason=f"Correlated with {leader} dump"
            )

    async def _close_worst_positions(self, count: int):
        """Close N worst performing positions"""
        # Sort positions by unrealized P&L
        sorted_positions = sorted(
            self.open_positions.items(),
            key=lambda x: x[1].get('unrealized_pnl', 0)
        )

        # Close worst N
        for position_id, _ in sorted_positions[:count]:
            await self._force_exit(
                position_id,
                reason="Portfolio health < 30"
            )

    async def _tighten_all_stops(self, new_distance_pct: float):
        """Tighten trailing stops on all positions"""
        print(f"[Portfolio] Tightening all stops to {new_distance_pct}%")

        for position_id in self.open_positions:
            # Emit event to TrailingStopManager
            self.event_bus.publish(TightenStop(
                position_id=position_id,
                new_distance_pct=new_distance_pct
            ))

    async def _trigger_circuit_breaker(self):
        """Daily loss limit hit - close all and stop trading"""
        print(f"[Portfolio] CIRCUIT BREAKER TRIGGERED - Daily loss: {self.daily_pnl:.2f}%")

        # Close ALL positions
        for position_id in list(self.open_positions.keys()):
            await self._force_exit(
                position_id,
                reason="Circuit breaker: Max daily loss"
            )

        # Emit circuit breaker event
        self.event_bus.publish(CircuitBreakerTriggered(
            daily_pnl=self.daily_pnl,
            max_loss_pct=self.config['max_daily_drawdown_pct']
        ))

        # Stop new trading
        self.event_bus.publish(StopAllTrading(
            reason="Circuit breaker triggered"
        ))
```

**Dump Detector Implementation**:

```python
class DumpDetector:
    """Detect early dump signals before trailing stop hits"""

    async def detect_dump(self, position: Dict, current_price: float) -> bool:
        """
        Returns True if dump signals detected

        Signals:
        1. Volume reversal (sell > buy for 3 candles)
        2. Order flow flip (2.5:1 buy → 2.5:1 sell)
        3. Liquidity evaporation (meme coins only)
        4. Momentum break (price below 5M EMA)
        5. Resistance rejection
        """

        # Get recent market data
        candles = await self.db.get_recent_candles(
            position['symbol'],
            timeframe='1m',
            limit=3
        )

        # Check volume reversal
        if self._check_volume_reversal(candles):
            print(f"[Dump] Volume reversal detected: {position['symbol']}")
            return True

        # Check order flow flip
        order_flow = await self.db.get_order_flow(
            position['symbol'],
            window_seconds=60
        )
        if self._check_order_flow_flip(order_flow):
            print(f"[Dump] Order flow flip detected: {position['symbol']}")
            return True

        # Check momentum break
        ema_5m = await self.db.get_ema(position['symbol'], '5m', period=20)
        if current_price < ema_5m:
            print(f"[Dump] Momentum break detected: {position['symbol']}")
            return True

        # Meme coin specific: liquidity check
        if position.get('asset_type') == 'meme':
            if await self._check_liquidity_evaporation(position):
                print(f"[Dump] Liquidity evaporation: {position['symbol']}")
                return True

        return False

    def _check_volume_reversal(self, candles: List[Dict]) -> bool:
        """Check if sell volume > buy volume for consecutive candles"""
        consecutive_sell = 0
        for candle in candles[-3:]:
            if candle['sell_volume'] > candle['buy_volume'] * 1.5:
                consecutive_sell += 1

        return consecutive_sell >= 3

    def _check_order_flow_flip(self, order_flow: Dict) -> bool:
        """Check if order flow flipped from bullish to bearish"""
        if not order_flow:
            return False

        current_ratio = order_flow['buy_volume'] / max(order_flow['sell_volume'], 1)

        # Flip from 2.5:1 buy to 2.5:1 sell
        return current_ratio < 0.4  # Sell dominant

    async def _check_liquidity_evaporation(self, position: Dict) -> bool:
        """Check if DEX liquidity dropping (rug pull warning)"""
        # Get aggregator quote
        aggregator = self.aggregator_factory.get_aggregator(position['chain'])

        try:
            quote = await aggregator.get_quote(
                input_token=position['token_address'],
                output_token='USDC',  # or WETH, SOL depending on chain
                amount=position['quantity'],
                slippage_bps=1000  # 10%
            )

            # If slippage > 10%, liquidity too thin
            return quote.estimated_slippage > 0.10

        except Exception as e:
            print(f"[Dump] Liquidity check failed: {e}")
            return True  # Assume worst case
```

**Configuration** (from config/portfolio_risk.yaml):
```yaml
portfolio_risk:
  enabled: true
  check_interval_seconds: 10

  # Daily drawdown circuit breaker
  max_daily_drawdown_pct: 5.0
  drawdown_levels:
    alert_pct: 2.0
    warning_pct: 3.0
    critical_pct: 4.0
    circuit_breaker_pct: 5.0

  # Correlation exits
  correlation_exit:
    enabled: true
    leaders: ['BTC', 'ETH']
    btc_dump_threshold_pct: 1.5
    min_correlation: 0.7
    rolling_window_hours: 24

  # Dump detection
  dump_detection:
    enabled: true
    volume_reversal:
      consecutive_candles: 3
      sell_buy_ratio: 1.5
    order_flow_flip:
      imbalance_threshold: 2.5
    liquidity_drop:
      threshold_pct: 30
      window_minutes: 10
```

**Benefits**:
- ✅ Exit positions showing dump signals BEFORE trailing stop hits
- ✅ Protect account from correlated losses (BTC dumps → exit correlated alts)
- ✅ Meme coin rug pull early warning (liquidity evaporation detection)
- ✅ Circuit breaker prevents catastrophic daily losses
- ✅ Enforce max hold times per strategy

**Maps to**: Design Doc Section 2.2.5, PROJECT_STRUCTURE.md src/position/portfolio_risk_manager.py

---

## 9. System Startup and Orchestration

### 9.1 Event-Driven Main Application Flow

**Complete main.py with Event Bus Integration**:

```python
import asyncio
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Binance
from cryptofeed.defines import TRADES, CANDLES
import os

# Import all event types
from events import (
    EventBus,
    TradeTickReceived,
    SignalGeneratedEvent,
    OrderPlacedEvent,
    OrderFailedEvent,
    PositionOpenedEvent,
    PositionClosedEvent,
    SystemErrorEvent,
    ConnectionLostEvent
)

# Import services
from services.notification import SendGridNotificationService
from services.database import ConnectionPoolManager
from services.analytics import AnalyticsEngine
from services.decision import DecisionEngine
from services.execution import ExecutionEngine
from services.position_monitor import PositionMonitor
from core.di_container import DependencyContainer

class TradingEngine:
    """
    Main Trading Engine with Event-Driven Architecture
    """

    def __init__(self):
        self.event_bus = None
        self.container = None
        self.feed_handler = None
        self.running = False

    async def start(self):
        """Start the trading engine with event-driven architecture"""

        print("[SYSTEM] 🚀 Starting Algo Engine...")

        # ═══════════════════════════════════════════════════════════
        # STEP 1: Initialize Event Bus (THE HEART)
        # ═══════════════════════════════════════════════════════════
        self.event_bus = EventBus(max_queue_size=10000)
        print("[SYSTEM] 💓 Event Bus initialized (THE HEART)")

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Initialize SendGrid Notification Service
        # ═══════════════════════════════════════════════════════════
        sendgrid_service = SendGridNotificationService(
            api_key=os.getenv('SENDGRID_API_KEY'),
            from_email=os.getenv('SENDGRID_FROM_EMAIL'),
            to_email=os.getenv('SENDGRID_TO_EMAIL')
        )
        print("[SYSTEM] 📧 SendGrid notification service initialized")

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Initialize Dependency Injection Container
        # ═══════════════════════════════════════════════════════════
        self.container = DependencyContainer()
        self.container.register_singleton("EventBus", self.event_bus)
        self.container.register_singleton("SendGridService", sendgrid_service)

        # Connection pool
        conn_pool = ConnectionPoolManager(max_connections=200)
        self.container.register_singleton("ConnectionPool", conn_pool)

        # Analytics engine
        analytics_engine = AnalyticsEngine(conn_pool, self.event_bus)
        self.container.register_singleton("AnalyticsEngine", analytics_engine)

        # Decision engine
        decision_engine = DecisionEngine(conn_pool, self.event_bus)
        self.container.register_singleton("DecisionEngine", decision_engine)

        # Execution engine
        execution_engine = ExecutionEngine(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET'),
            event_bus=self.event_bus
        )
        self.container.register_singleton("ExecutionEngine", execution_engine)

        # Position monitor
        position_monitor = PositionMonitor(
            conn_pool,
            execution_engine,
            self.event_bus
        )
        self.container.register_singleton("PositionMonitor", position_monitor)

        print("[SYSTEM] ✅ All services initialized")

        # ═══════════════════════════════════════════════════════════
        # STEP 4: Setup Event Subscribers
        # ═══════════════════════════════════════════════════════════
        await self.setup_event_subscribers()
        print("[SYSTEM] ✅ Event subscribers registered")

        # ═══════════════════════════════════════════════════════════
        # STEP 5: Position Reconciliation (CRITICAL)
        # ═══════════════════════════════════════════════════════════
        print("[SYSTEM] 🔄 Running position reconciliation...")
        await position_monitor.reconcile_positions()
        print("[SYSTEM] ✅ Position reconciliation complete")

        # ═══════════════════════════════════════════════════════════
        # STEP 6: Start Cryptofeed Data Streaming (24/7)
        # ═══════════════════════════════════════════════════════════
        self.feed_handler = FeedHandler()
        self.feed_handler.add_feed(
            Binance(
                symbols=['BTC-USDT', 'ETH-USDT'],
                channels=[TRADES, CANDLES],
                callbacks={
                    TRADES: self.handle_trade,
                    CANDLES: self.handle_candle
                }
            )
        )
        print("[SYSTEM] 🔄 Cryptofeed data streaming starting...")

        # ═══════════════════════════════════════════════════════════
        # STEP 7: Start All Services in Parallel
        # ═══════════════════════════════════════════════════════════
        self.running = True

        await asyncio.gather(
            # 💓 THE HEART - Event Bus (24/7)
            self.event_bus.process_events(),

            # 🔄 Data Streaming (24/7)
            self.run_feed_handler(),

            # 📊 Analytics Engine (24/7)
            analytics_engine.start(),

            # 👁️ Position Monitoring (24/7)
            position_monitor.start(),

            # Handle graceful shutdown
            self.handle_shutdown()
        )

    async def setup_event_subscribers(self):
        """Setup all event subscribers"""

        # Get services from container
        analytics = self.container.resolve("AnalyticsEngine")
        decision = self.container.resolve("DecisionEngine")
        execution = self.container.resolve("ExecutionEngine")
        position_monitor = self.container.resolve("PositionMonitor")
        sendgrid = self.container.resolve("SendGridService")

        # TradeTickReceived → Analytics Engine
        self.event_bus.subscribe(
            "TradeTickReceived",
            analytics.on_tick_received
        )

        # SignalGeneratedEvent → Decision Engine
        self.event_bus.subscribe(
            "SignalGeneratedEvent",
            decision.on_signal_generated
        )

        # SignalGeneratedEvent → SendGrid (notify)
        async def notify_signal(event: SignalGeneratedEvent):
            await sendgrid.notify_trade_signal(
                symbol=event.data['symbol'],
                direction=event.data['direction'],
                entry_price=event.data['entry_price'],
                confluence_score=event.data['confluence_score']
            )
        self.event_bus.subscribe("SignalGeneratedEvent", notify_signal)

        # OrderPlacedEvent → Position Monitor
        self.event_bus.subscribe(
            "OrderPlacedEvent",
            position_monitor.on_order_placed
        )

        # OrderPlacedEvent → SendGrid (notify)
        async def notify_position_opened(event: OrderPlacedEvent):
            await sendgrid.notify_position_opened(
                symbol=event.data['symbol'],
                side=event.data['side'],
                entry_price=event.data['entry_price'],
                quantity=event.data['quantity'],
                stop_loss=event.data['stop_loss']
            )
        self.event_bus.subscribe("OrderPlacedEvent", notify_position_opened)

        # PositionClosedEvent → SendGrid (notify)
        async def notify_position_closed(event: PositionClosedEvent):
            await sendgrid.notify_position_closed(
                symbol=event.data['symbol'],
                side=event.data['side'],
                entry_price=event.data['entry_price'],
                exit_price=event.data['exit_price'],
                pnl=event.data['pnl'],
                pnl_pct=event.data['pnl_pct'],
                reason=event.data['reason']
            )
        self.event_bus.subscribe("PositionClosedEvent", notify_position_closed)

        # OrderFailedEvent → SendGrid (CRITICAL notification)
        async def notify_order_failed(event: OrderFailedEvent):
            await sendgrid.notify_order_failed(
                symbol=event.data['symbol'],
                side=event.data['side'],
                reason=event.data['reason']
            )
        self.event_bus.subscribe("OrderFailedEvent", notify_order_failed)

        # SystemErrorEvent → SendGrid (CRITICAL notification)
        async def notify_system_error(event: SystemErrorEvent):
            await sendgrid.notify_critical_error(
                error_type=event.data['error_type'],
                error_message=event.data['message'],
                context=event.data.get('context')
            )
        self.event_bus.subscribe("SystemErrorEvent", notify_system_error)

        # ConnectionLostEvent → SendGrid (CRITICAL notification)
        async def notify_connection_lost(event: ConnectionLostEvent):
            await sendgrid.notify_critical_error(
                error_type="Connection Lost",
                error_message=f"Lost connection to {event.data['exchange']}",
                context=event.data
            )
        self.event_bus.subscribe("ConnectionLostEvent", notify_connection_lost)

        print("[SYSTEM] Event subscribers configured:")
        print("  ✅ TradeTickReceived → Analytics Engine")
        print("  ✅ SignalGeneratedEvent → Decision Engine + SendGrid")
        print("  ✅ OrderPlacedEvent → Position Monitor + SendGrid")
        print("  ✅ PositionClosedEvent → SendGrid")
        print("  ✅ OrderFailedEvent → SendGrid (CRITICAL)")
        print("  ✅ SystemErrorEvent → SendGrid (CRITICAL)")
        print("  ✅ ConnectionLostEvent → SendGrid (CRITICAL)")

    async def handle_trade(self, trade, receipt_timestamp):
        """Handle incoming trade from Cryptofeed"""

        # Publish TradeTickReceived to Event Bus
        event = TradeTickReceived(
            event_id=f"tick_{trade.symbol}_{trade.timestamp}",
            timestamp=datetime.utcnow(),
            source="cryptofeed",
            data={
                'symbol': trade.symbol,
                'price': trade.price,
                'volume': trade.amount,
                'side': trade.side,
                'trade_id': trade.id,
                'exchange': 'binance'
            }
        )

        await self.event_bus.publish(event)

    async def handle_candle(self, candle, receipt_timestamp):
        """Handle incoming candle from Cryptofeed"""
        # Similar to handle_trade - publish CandleUpdatedEvent
        pass

    async def run_feed_handler(self):
        """Run Cryptofeed feed handler"""
        try:
            await self.feed_handler.run()
        except Exception as e:
            # Publish ConnectionLostEvent
            error_event = ConnectionLostEvent(
                event_id=f"conn_lost_{datetime.utcnow().timestamp()}",
                timestamp=datetime.utcnow(),
                source="cryptofeed",
                data={
                    'exchange': 'binance',
                    'error': str(e)
                }
            )
            await self.event_bus.publish(error_event)

    async def handle_shutdown(self):
        """Handle graceful shutdown"""
        try:
            # Wait for shutdown signal
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            print("[SYSTEM] 🛑 Shutdown signal received")
            self.running = False
            await self.event_bus.stop()


async def main():
    """Main entry point"""
    engine = TradingEngine()
    await engine.start()


if __name__ == "__main__":
    asyncio.run(main())
```

**Event Flow Example**:

```
1. WebSocket receives trade
   ↓
2. handle_trade() publishes TradeTickReceived to Event Bus
   ↓
3. Event Bus dispatches to subscribers:
   - Analytics Engine processes tick → calculates indicators
   ↓
4. Analytics detects signal → publishes SignalGeneratedEvent
   ↓
5. Event Bus dispatches to:
   - Decision Engine → evaluates confluence
   - SendGrid → sends email notification 🟡
   ↓
6. Decision Engine decides to trade → publishes OrderExecutionEvent
   ↓
7. Event Bus dispatches to:
   - Execution Engine → places order
   ↓
8. Order placed successfully → publishes OrderPlacedEvent
   ↓
9. Event Bus dispatches to:
   - Position Monitor → activates trailing stop
   - SendGrid → sends email notification 🟢
   ↓
10. Trailing stop hit → publishes PositionClosedEvent
    ↓
11. Event Bus dispatches to:
    - SendGrid → sends email notification 🟢 (with P&L)
```

---

## 9. Performance Considerations

### 9.1 Data Ingestion Optimization

- Use async/await for non-blocking I/O
- Batch insert to DuckDB (every 100 ticks or 1 second)
- Use connection pooling for Firestore
- In-memory cache for hot data (last 1 hour)

### 9.2 Query Optimization

- Partition tables by date and symbol
- Use covering indexes for common queries
- Pre-aggregate data for faster lookups (1M → 5M → 15M)
- Cache analytical results for 1 second

### 9.3 Order Execution Speed

- Keep WebSocket connections alive
- Use direct Binance API for critical paths
- Pre-validate orders before sending
- Concurrent order placement for multiple pairs

---

## 10. Monitoring and Logging

### 10.1 System Metrics

- WebSocket connection status
- Data ingestion rate (ticks/second)
- DuckDB query latency
- Order execution latency
- PnL tracking

### 10.2 Logging Strategy

- **DEBUG**: All data ingestion events
- **INFO**: Trading signals, order placement
- **WARNING**: Failed orders, connection issues
- **ERROR**: Critical failures, risk breaches

**Log Storage**: Firebase Storage (daily rotation)

---

## 11. Deployment Architecture

### 11.1 Recommended Deployment

**Single Server Setup** (Phase 1):
- Ubuntu 22.04 LTS
- Python 3.10+ with virtual environment
- DuckDB local file (trading.duckdb)
- Supervisor for process management
- Nginx for API endpoints (optional dashboard)

**Cloud Setup** (Phase 2):
- GCP Compute Engine or AWS EC2
- Firestore for state (multi-region)
- Firebase Storage for logs
- Load balancer for multiple instances

---

## 12. Critical Implementation Patterns

### 12.1 Per-Symbol Database Isolation (CRITICAL)

**Database Structure**:
```
data/
├── binance/
│   ├── spot/
│   │   ├── BTCUSDT/
│   │   │   └── trading.duckdb        # All data: ticks, candles, analytics, trades
│   │   ├── ETHUSDT/
│   │   │   └── trading.duckdb
│   └── futures/
│       ├── BTCUSDT/
│       │   └── trading.duckdb
```

**Why**:
- Zero lock contention for 100+ symbols
- Parallel writes without blocking
- Independent scaling per trading pair

**Implementation**: `src/storage/connection_pool.py`

---

### 12.2 Connection Pool Manager (CRITICAL)

**Requirements**:
- Maximum 200 concurrent DuckDB connections
- LRU eviction when pool is full
- Thread-safe access
- Per-symbol connection tracking

**Implementation**:
```python
class ConnectionPoolManager:
    def __init__(self, max_connections: int = 200):
        self.pool: Dict[str, duckdb.DuckDBPyConnection] = {}
        self.access_times: Dict[str, float] = {}
        self.max_connections = max_connections
        self.lock = threading.Lock()

    def get_connection(self, exchange: str, market_type: str, symbol: str):
        key = f"{exchange}_{market_type}_{symbol}"

        with self.lock:
            self.access_times[key] = time.time()

            if key in self.pool:
                return self.pool[key]

            # Evict LRU if pool is full
            if len(self.pool) >= self.max_connections:
                lru_key = min(self.access_times, key=self.access_times.get)
                self.pool[lru_key].close()
                del self.pool[lru_key]
                del self.access_times[lru_key]

            # Create new connection
            db_path = f"data/{exchange}/{market_type}/{symbol}/trading.duckdb"
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = duckdb.connect(db_path)
            self.pool[key] = conn

            return conn
```

**Performance**:
- Cached connection: 0.5-2ms query time
- New connection: 50-150ms overhead
- Cache hit rate: >95%

---

### 12.3 Dependency Injection Container (CRITICAL)

**Purpose**: Manage service lifecycle and dependencies

**Implementation**: `src/core/di_container.py`

```python
class DependencyContainer:
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}

    def register_singleton(self, name: str, instance: Any):
        self._singletons[name] = instance

    def register_factory(self, name: str, factory: Callable):
        self._factories[name] = factory

    def resolve(self, service_name: str) -> Any:
        if service_name in self._singletons:
            return self._singletons[service_name]

        if service_name in self._factories:
            factory = self._factories[service_name]
            dependencies = self._resolve_dependencies(factory)
            return factory(**dependencies)

        raise ValueError(f"Service '{service_name}' not registered")

    def _resolve_dependencies(self, func: Callable) -> Dict[str, Any]:
        sig = inspect.signature(func)
        dependencies = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            param_type = param.annotation
            if param_type != inspect.Parameter.empty:
                type_name = param_type.__name__
                dependencies[param_name] = self.resolve(type_name)

        return dependencies
```

**Usage**:
```python
# Setup in main.py
container = DependencyContainer()
container.register_singleton("ConnectionPool", ConnectionPoolManager(200))
container.register_factory("DecisionEngine", lambda pool: DecisionEngine(pool))
engine = container.resolve("DecisionEngine")
```

---

### 12.4 Execution Handler Chain (CRITICAL)

**Pattern**: Chain of Responsibility

**Handlers** (in order):
1. ExistingPositionHandler - Check for duplicates
2. ReversalDetectionHandler - Handle reversals
3. PositionLimitHandler - Enforce max positions
4. ExposureCheckHandler - Check total exposure
5. OrderPlacementHandler - Execute order
6. PositionMonitoringHandler - Activate trailing stop

**Implementation**: `src/trading/execution_handlers.py`

```python
class ExecutionHandler(ABC):
    def __init__(self):
        self._next_handler: Optional[ExecutionHandler] = None

    def set_next(self, handler: 'ExecutionHandler'):
        self._next_handler = handler
        return handler

    @abstractmethod
    def handle(self, trade_signal: TradeSignal) -> ExecutionResult:
        pass

    def _pass_to_next(self, trade_signal: TradeSignal):
        if self._next_handler:
            return self._next_handler.handle(trade_signal)
        return ExecutionResult(success=True)

# Create pipeline
def create_execution_pipeline():
    existing_position = ExistingPositionHandler()
    reversal = ReversalDetectionHandler()
    position_limit = PositionLimitHandler()
    exposure = ExposureCheckHandler()
    order_placement = OrderPlacementHandler()
    monitoring = PositionMonitoringHandler()

    existing_position.set_next(reversal) \
                     .set_next(position_limit) \
                     .set_next(exposure) \
                     .set_next(order_placement) \
                     .set_next(monitoring)

    return existing_position
```

---

### 12.5 Hierarchical Multi-Timeframe Strategy (CRITICAL)

**Pattern**: Short-Circuit Filtering with Cascade Detection

**Purpose**: Efficiently filter 100+ trading pairs by rejecting ranging markets immediately and only analyzing trending markets with proper order flow acceleration.

**Implementation**: `src/analytics/trend_detector.py` + `src/analytics/cascade_detector.py`

```python
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum

class MarketRegime(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGING = "ranging"

@dataclass
class TrendAnalysis:
    regime: MarketRegime
    strength: float  # 0-100
    allowed_direction: Optional[str]  # "LONG", "SHORT", or None

class HierarchicalStrategyEngine:
    """
    4-Level hierarchical strategy with short-circuit filtering
    Rejects ranging markets at Level 1 to save computational resources
    """

    def __init__(
        self,
        connection_pool: ConnectionPoolManager,
        config: Dict  # Config 1 or Config 2
    ):
        self.conn_pool = connection_pool
        self.config = config
        self.longest_tf = config['timeframes']['longest']  # 15m or 1h
        self.middle_tf = config['timeframes']['middle']    # 5m or 15m
        self.fastest_tf = config['timeframes']['fastest']  # 1m

    async def evaluate_pair(
        self,
        exchange: str,
        market_type: str,
        symbol: str
    ) -> Optional[TradeSignal]:
        """
        Evaluate trading pair through 4-level hierarchy
        Returns None at ANY level if conditions not met (short-circuit)
        """

        # ═══════════════════════════════════════════════════════════
        # LEVEL 1: Trend & Regime Detection (LONGEST TIMEFRAME)
        # ⚡ SHORT-CIRCUIT: Ranging markets rejected immediately
        # ═══════════════════════════════════════════════════════════
        trend = await self.detect_trend_regime(
            exchange, market_type, symbol, self.longest_tf
        )

        if trend.regime == MarketRegime.RANGING:
            # 🚫 RANGING MARKET: Skip this pair entirely
            # Do NOT proceed to further analysis
            return None

        # ✅ TRENDING MARKET: Continue to Level 2
        allowed_direction = trend.allowed_direction  # "LONG" or "SHORT"

        # ═══════════════════════════════════════════════════════════
        # LEVEL 2: Market Profile Zone Analysis (LONGEST TIMEFRAME)
        # Identify WHERE to look for trades
        # ═══════════════════════════════════════════════════════════
        zones = await self.identify_zones(
            exchange, market_type, symbol, self.longest_tf, allowed_direction
        )

        current_price = await self.get_current_price(symbol)

        # Check if price is near a relevant zone
        at_zone = self.check_price_near_zone(current_price, zones, allowed_direction)

        if not at_zone:
            # Not at a zone, wait
            return None

        # ✅ AT ZONE: Continue to Level 3

        # ═══════════════════════════════════════════════════════════
        # LEVEL 3: Order Flow Cascade Detection (ALL TIMEFRAMES)
        # Confirm institutional acceleration
        # ═══════════════════════════════════════════════════════════
        cascade = await self.detect_order_flow_cascade(
            exchange, market_type, symbol, allowed_direction
        )

        if not cascade.valid:
            # Cascade not confirmed, wait
            return None

        # ✅ CASCADE CONFIRMED: Continue to Level 4

        # ═══════════════════════════════════════════════════════════
        # LEVEL 4: Bid-Ask Bounce + Volume Confirmation (FASTEST TF)
        # Final execution trigger
        # ═══════════════════════════════════════════════════════════
        trigger = await self.detect_bounce_and_volume(
            exchange, market_type, symbol, allowed_direction, at_zone
        )

        if not trigger.valid:
            # Bounce not confirmed, wait
            return None

        # ✅ ALL LEVELS PASSED: Generate trade signal
        entry_score = trigger.bounce_strength * cascade.imbalance_1m

        return TradeSignal(
            symbol=symbol,
            direction=allowed_direction,
            entry_price=current_price,
            stop_loss=at_zone.boundary_price,
            entry_score=entry_score,
            zone_strength=at_zone.strength,
            cascade_confirmed=True
        )

    async def detect_trend_regime(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        timeframe: str
    ) -> TrendAnalysis:
        """
        LEVEL 1: Detect market regime on LONGEST timeframe
        Returns RANGING, UPTREND, or DOWNTREND
        """

        conn = self.conn_pool.get_connection(exchange, market_type, symbol)

        # Get candles for trend analysis
        table = f"candles_{timeframe.lower()}"
        query = f"""
        SELECT timestamp, close
        FROM {table}
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 200  -- Last 200 candles for EMA calculation
        """

        candles = conn.execute(query, [symbol]).fetchall()
        prices = [c[1] for c in candles]

        # Calculate EMAs
        ema_20 = self.calculate_ema(prices, 20)
        ema_50 = self.calculate_ema(prices, 50)
        ema_200 = self.calculate_ema(prices, 200)

        # Calculate ADX for trend strength
        adx = await self.calculate_adx(conn, symbol, timeframe, lookback=14)

        # Calculate ATR for volatility check
        atr = await self.calculate_atr(conn, symbol, timeframe, lookback=14)
        avg_price = sum(prices[:20]) / 20
        atr_percent = (atr / avg_price) * 100

        # Calculate Directional Persistence (Hurst Exponent)
        directional_persistence = self.calculate_hurst_exponent(prices[:100])

        # Calculate Mean Reversion Strength
        mean_reversion_strength = await self.calculate_mean_reversion_strength(
            conn, symbol, timeframe, ema_20, lookback=50
        )

        current_price = prices[0]

        # Determine regime with enhanced filters
        if (
            adx < 20                          # Weak trend
            or atr_percent < 0.5              # Low volatility
            or directional_persistence < 0.55 # Random/choppy
            or mean_reversion_strength > 0.6  # Snaps back too fast
        ):
            # ❌ RANGING/CHOPPY/RISKY: Multiple reasons to reject
            return TrendAnalysis(
                regime=MarketRegime.RANGING,
                strength=0.0,
                allowed_direction=None
            )

        # Check EMA alignment
        if ema_20 > ema_50 > ema_200 and current_price > ema_20:
            # ✅ UPTREND confirmed
            return TrendAnalysis(
                regime=MarketRegime.UPTREND,
                strength=adx,
                allowed_direction="LONG"
            )

        elif ema_20 < ema_50 < ema_200 and current_price < ema_20:
            # ✅ DOWNTREND confirmed
            return TrendAnalysis(
                regime=MarketRegime.DOWNTREND,
                strength=adx,
                allowed_direction="SHORT"
            )

        else:
            # ❌ RANGING: EMAs not aligned
            return TrendAnalysis(
                regime=MarketRegime.RANGING,
                strength=0.0,
                allowed_direction=None
            )

    async def identify_zones(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        timeframe: str,
        direction: str
    ) -> Dict:
        """
        LEVEL 2: Identify demand/supply zones on LONGEST timeframe
        Only looks for zones relevant to allowed direction
        """

        conn = self.conn_pool.get_connection(exchange, market_type, symbol)

        # Calculate Market Profile (POC, Value Area)
        profile = await self.calculate_market_profile(conn, symbol, timeframe)

        # Identify support/resistance zones
        if direction == "LONG":
            # Look for DEMAND ZONES (support)
            zones = await self.find_demand_zones(conn, symbol, timeframe)
        else:
            # Look for SUPPLY ZONES (resistance)
            zones = await self.find_supply_zones(conn, symbol, timeframe)

        return {
            'poc': profile.poc,
            'value_area_high': profile.vah,
            'value_area_low': profile.val,
            'zones': zones
        }

    async def detect_order_flow_cascade(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        direction: str
    ) -> CascadeResult:
        """
        LEVEL 3: Detect order flow cascade across all timeframes
        Must show ACCELERATION at smaller timeframes
        """

        conn = self.conn_pool.get_connection(exchange, market_type, symbol)

        # Calculate imbalance on each timeframe
        imbalance_1m = await self.calculate_imbalance(
            conn, symbol, "1m", lookback_minutes=1
        )
        imbalance_middle = await self.calculate_imbalance(
            conn, symbol, self.middle_tf, lookback_minutes=5
        )
        imbalance_longest = await self.calculate_imbalance(
            conn, symbol, self.longest_tf, lookback_minutes=15
        )

        # Check cascade validity
        if direction == "LONG":
            # For LONG: Buy pressure should ACCELERATE at smaller timeframes
            # 1m imbalance > 5m imbalance > 15m imbalance
            cascade_valid = (
                imbalance_1m > imbalance_middle > imbalance_longest
                and imbalance_1m > 2.0  # At least 2:1 buy pressure
            )

        else:  # SHORT
            # For SHORT: Sell pressure should ACCELERATE at smaller timeframes
            # 1m imbalance < 5m imbalance < 15m imbalance
            # (lower imbalance = more selling)
            cascade_valid = (
                imbalance_1m < imbalance_middle < imbalance_longest
                and imbalance_1m < 0.5  # At least 2:1 sell pressure
            )

        return CascadeResult(
            valid=cascade_valid,
            imbalance_1m=imbalance_1m,
            imbalance_middle=imbalance_middle,
            imbalance_longest=imbalance_longest
        )

    async def calculate_imbalance(
        self,
        conn,
        symbol: str,
        timeframe: str,
        lookback_minutes: int
    ) -> float:
        """
        Calculate order flow imbalance ratio
        Returns: buy_volume / sell_volume
        """

        query = """
        SELECT
            SUM(CASE WHEN side = 'buy' THEN volume ELSE 0 END) as buy_vol,
            SUM(CASE WHEN side = 'sell' THEN volume ELSE 0 END) as sell_vol
        FROM ticks
        WHERE symbol = ?
            AND timestamp >= NOW() - INTERVAL ? MINUTES
        """

        result = conn.execute(query, [symbol, lookback_minutes]).fetchone()

        buy_vol, sell_vol = result if result else (0, 0)

        if sell_vol == 0:
            return float('inf') if buy_vol > 0 else 1.0

        imbalance = buy_vol / sell_vol

        return imbalance

    async def detect_bounce_and_volume(
        self,
        exchange: str,
        market_type: str,
        symbol: str,
        direction: str,
        zone: Dict
    ) -> BounceResult:
        """
        LEVEL 4: Detect bid-ask bounce + volume spike on 1-minute
        Final execution trigger
        """

        conn = self.conn_pool.get_connection(exchange, market_type, symbol)

        # Get last 20 1-minute candles
        query = """
        SELECT timestamp, open, high, low, close, volume
        FROM candles_1m
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 20
        """

        candles = conn.execute(query, [symbol]).fetchall()
        current_candle = candles[0]
        avg_volume = sum(c[5] for c in candles[1:]) / 19

        # Analyze bounce
        bounce_strength = self.analyze_bounce_strength(
            current_candle, zone, direction
        )

        # Check volume spike
        volume_spike = current_candle[5] / avg_volume

        # Validate bounce + volume
        bounce_valid = (
            bounce_strength > 0.7  # Strong rejection of zone
            and volume_spike > 1.5  # 50% more volume than average
        )

        return BounceResult(
            valid=bounce_valid,
            bounce_strength=bounce_strength,
            volume_spike=volume_spike
        )

    def calculate_hurst_exponent(self, prices: List[float]) -> float:
        """
        Calculate Hurst Exponent (Directional Persistence)

        Returns:
        - > 0.6: Strong trending (persistent directional movement)
        - 0.45-0.55: Random walk (unpredictable)
        - < 0.45: Mean reverting (constant bouncing)
        """
        import numpy as np

        if len(prices) < 20:
            return 0.5  # Default to random walk

        prices = np.array(prices)

        # Calculate log returns
        log_returns = np.diff(np.log(prices))

        # Use rescaled range (R/S) analysis
        lags = [10, 20, 50]
        rs_values = []

        for lag in lags:
            if len(log_returns) < lag:
                continue

            # Split into chunks
            chunks = [log_returns[i:i+lag] for i in range(0, len(log_returns), lag)]

            rs_list = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue

                # Mean-adjusted series
                mean_adj = chunk - np.mean(chunk)

                # Cumulative sum
                cumsum = np.cumsum(mean_adj)

                # Range
                R = np.max(cumsum) - np.min(cumsum)

                # Standard deviation
                S = np.std(chunk)

                if S > 0:
                    rs_list.append(R / S)

            if rs_list:
                rs_values.append(np.mean(rs_list))

        if len(rs_values) < 2:
            return 0.5

        # Fit log(R/S) vs log(lag)
        log_lags = np.log(lags[:len(rs_values)])
        log_rs = np.log(rs_values)

        # Hurst exponent is the slope
        hurst = np.polyfit(log_lags, log_rs, 1)[0]

        # Clamp between 0 and 1
        return max(0.0, min(1.0, hurst))

    async def calculate_mean_reversion_strength(
        self,
        conn,
        symbol: str,
        timeframe: str,
        ema: float,
        lookback: int = 50
    ) -> float:
        """
        Calculate Mean Reversion Strength

        Measures how quickly price returns to EMA after displacement

        Returns:
        - < 0.5: Weak reversion (trending - price drifts away)
        - 0.5-0.7: Moderate reversion
        - > 0.7: Strong reversion (ranging - price snaps back fast)
        """
        table = f"candles_{timeframe.lower()}"
        query = f"""
        SELECT timestamp, close
        FROM {table}
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """

        candles = conn.execute(query, [symbol, lookback]).fetchall()

        if len(candles) < 20:
            return 0.5  # Default

        prices = [c[1] for c in candles]

        # Calculate standard deviation
        import numpy as np
        std_dev = np.std(prices)

        # Find instances where price exceeded 2σ from EMA
        excursions = []

        for i in range(len(prices) - 1):
            deviation = abs(prices[i] - ema)

            if deviation > 2 * std_dev:
                # Price exceeded 2σ - measure how long until it returns
                for j in range(i + 1, min(i + 20, len(prices))):
                    if abs(prices[j] - ema) < std_dev:
                        # Returned within 1σ
                        candles_to_return = j - i
                        excursions.append(candles_to_return)
                        break

        if not excursions:
            return 0.5  # No significant excursions

        # Average return speed
        avg_return_speed = np.mean(excursions)

        # Convert to strength (faster return = higher strength)
        # 1-3 candles = 0.9 (very strong reversion)
        # 5-10 candles = 0.5 (moderate)
        # 15+ candles = 0.2 (weak reversion / trending)

        if avg_return_speed <= 3:
            strength = 0.9  # Strong reversion
        elif avg_return_speed <= 7:
            strength = 0.7  # Moderate reversion
        elif avg_return_speed <= 12:
            strength = 0.5  # Mild reversion
        else:
            strength = 0.3  # Weak reversion (trending)

        return strength

@dataclass
class CascadeResult:
    valid: bool
    imbalance_1m: float
    imbalance_middle: float
    imbalance_longest: float

@dataclass
class BounceResult:
    valid: bool
    bounce_strength: float
    volume_spike: float
```

**Key Benefits**:
1. **Short-Circuit at Level 1**: Ranging markets rejected immediately (saves 75% of CPU)
2. **Directional Filter**: Only LONG in uptrends, only SHORT in downtrends
3. **Zone-Based Entries**: Only trade at institutional support/resistance
4. **Cascade Confirmation**: Ensures institutional acceleration
5. **Precise Trigger**: Bounce + volume spike for best entry timing

---

### 12.6 Composition-Based Signal Generation (CRITICAL)

**Pattern**: Strategy + Composition

**Components**:
- **Primary Analyzers** (ALL must pass): OrderFlowAnalyzer, MicrostructureAnalyzer
- **Secondary Filters** (Weighted scoring): MarketProfileFilter, MeanReversionFilter, etc.

**Implementation**: `src/decision/signal_pipeline.py`

```python
class SignalAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, market_data: MarketData) -> SignalResult:
        pass

class SignalFilter(ABC):
    def __init__(self, weight: float):
        self.weight = weight

    @abstractmethod
    async def evaluate(self, market_data: MarketData) -> float:
        pass

class DecisionEngine:
    def __init__(
        self,
        primary_analyzers: List[SignalAnalyzer],
        secondary_filters: List[SignalFilter],
        min_confluence: float = 3.0
    ):
        self.primary_analyzers = primary_analyzers
        self.secondary_filters = secondary_filters
        self.min_confluence = min_confluence

    async def evaluate(self, market_data: MarketData):
        # Step 1: ALL primary analyzers must pass
        for analyzer in self.primary_analyzers:
            result = await analyzer.analyze(market_data)
            if not result.passed:
                return None

        # Step 2: Calculate confluence score
        confluence = sum(
            await filter.evaluate(market_data)
            for filter in self.secondary_filters
        )

        # Step 3: Check threshold
        if confluence < self.min_confluence:
            return None

        return TradeSignal(confluence_score=confluence, ...)
```

**Setup**:
```python
primary = [OrderFlowAnalyzer(2.5), MicrostructureAnalyzer()]
secondary = [
    MarketProfileFilter(1.5),
    MeanReversionFilter(1.5),
    DemandZoneFilter(2.0),
    FairValueGapFilter(1.5)
]
engine = DecisionEngine(primary, secondary, min_confluence=3.0)
```

---

### 12.6 Async/Await Throughout (CRITICAL)

**Requirement**: ALL I/O operations MUST be async

**Components**:
- WebSocket handlers: `async def on_trade()`
- Database operations: `await asyncio.to_thread(db.execute, ...)`
- Exchange API: `await exchange.create_order()`
- Position monitoring: `async def monitor_positions()`

**Main Event Loop**:
```python
async def main():
    await asyncio.gather(
        market_data_stream.start(),
        decision_engine.run(),
        position_monitor.start(),
        api_server.start()
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Performance**:
- Synchronous: 10 symbols/second
- Asynchronous: 100+ symbols/second

---

### 12.7 Position Reconciliation (CRITICAL)

**Purpose**: Reconcile local state with exchange on startup

**Implementation**: `src/services/position_reconciliation.py`

```python
class PositionReconciliationService:
    async def reconcile_positions(self):
        # Step 1: Get local positions (Firestore)
        local = await self._get_firestore_positions()

        # Step 2: Get exchange positions (source of truth)
        exchange = await self._get_exchange_positions()

        # Step 3: Find discrepancies
        discrepancies = self._find_discrepancies(local, exchange)

        # Step 4: Resolve each discrepancy
        for disc in discrepancies:
            await self._resolve_discrepancy(disc)
```

**When to Run**: BEFORE starting any trading activity

**Discrepancy Types**:
1. Missing on exchange → Remove from Firestore
2. Missing in Firestore → Import from exchange
3. Quantity mismatch → Update local to match exchange

---

### 12.8 Error Handling & Retry Logic (CRITICAL)

**Retry with Exponential Backoff**:
```python
def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except (NetworkError, RateLimitError) as e:
                    if attempt == max_retries:
                        raise
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3)
async def fetch_ticker(symbol):
    return await exchange.fetch_ticker(symbol)
```

**Circuit Breaker**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown: float = 60.0):
        self.failures = 0
        self.threshold = failure_threshold
        self.state = 'closed'  # closed, open, half-open

    def can_attempt(self) -> bool:
        if self.state == 'closed':
            return True
        if self.state == 'open':
            if time.time() - self.last_failure > self.cooldown:
                self.state = 'half-open'
                return True
            return False
        return True
```

---

### 12.9 Multi-Timeframe Manager

**Purpose**: Manage analytics across 15s, 1m, 5m timeframes

**Implementation**: `src/decision/timeframe_manager.py`

```python
class TimeframeManager:
    def __init__(self):
        self.timeframes = {
            '15s': TimeframeConfig(window=15, min_ticks=30, update_freq=5),
            '1m': TimeframeConfig(window=60, min_ticks=60, update_freq=10),
            '5m': TimeframeConfig(window=300, min_ticks=200, update_freq=30)
        }
        self.cache = {}

    async def get_analytics(self, symbol: str, timeframe: str):
        config = self.timeframes[timeframe]

        # Check cache freshness
        if self._is_cache_fresh(symbol, timeframe, config.update_freq):
            return self.cache[f"{symbol}_{timeframe}"]

        # Recalculate
        analytics = await self._calculate_analytics(symbol, config)
        self.cache[f"{symbol}_{timeframe}"] = analytics

        return analytics
```

---

### 12.10 Trailing Stop Implementation

**Implementation**: `src/trading/position_monitor.py`

```python
class PositionMonitor:
    def __init__(self, trailing_percent: float = 0.005):  # 0.5%
        self.trailing_percent = trailing_percent
        self.active_stops: Dict[str, TrailingStop] = {}

    def activate_trailing_stop(self, symbol: str, entry_price: float, side: str):
        if side == "long":
            stop_price = entry_price * (1 - self.trailing_percent)
            self.active_stops[symbol] = TrailingStop(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_stop=stop_price,
                highest_price=entry_price
            )

    async def _monitoring_loop(self):
        while self.running:
            for symbol in list(self.active_stops.keys()):
                await self._update_trailing_stop(symbol)
            await asyncio.sleep(0.1)  # Check every 100ms

    async def _update_trailing_stop(self, symbol: str):
        stop = self.active_stops[symbol]
        current_price = await self._get_current_price(symbol)

        if stop.side == "long":
            if current_price > stop.highest_price:
                stop.highest_price = current_price
                new_stop = current_price * (1 - self.trailing_percent)
                if new_stop > stop.current_stop:
                    stop.current_stop = new_stop

            if current_price <= stop.current_stop:
                await self._execute_stop_loss(symbol, current_price)
```

---

## 13. Implementation Checklist

### Phase 1: Foundation (Week 1-2)
- [ ] DI Container (`src/core/di_container.py`)
- [ ] Connection Pool Manager (`src/storage/connection_pool.py`)
- [ ] Per-Symbol Database Manager (`src/storage/database_manager.py`)
- [ ] Async main event loop (`main.py`)

### Phase 2: Core Trading (Week 3-4)
- [ ] Signal analyzers (`src/decision/primary_analyzers.py`)
- [ ] Signal filters (`src/decision/secondary_filters.py`)
- [ ] Decision engine (`src/decision/signal_pipeline.py`)
- [ ] Execution handlers (`src/trading/execution_handlers.py`)
- [ ] Position monitor (`src/trading/position_monitor.py`)

### Phase 3: Reliability (Week 5-6)
- [ ] Position reconciliation (`src/services/position_reconciliation.py`)
- [ ] Retry decorator (`src/core/retry.py`)
- [ ] Circuit breaker (`src/core/circuit_breaker.py`)
- [ ] FastAPI lifespan (`src/api/main.py`)

### Phase 4: Testing (Week 7-8)
- [ ] Unit tests for all components
- [ ] Integration tests
- [ ] Load testing (100+ symbols)
- [ ] Performance benchmarking

---

## Conclusion

This technical architecture provides a complete blueprint for implementing the algorithmic trading engine with focus on:

1. Real-time data ingestion via Cryptofeed
2. Ultra-fast analytics with DuckDB (per-symbol isolation)
3. Multi-timeframe order flow and market profile analysis
4. Composition-based signal generation (pluggable analyzers)
5. Chain of responsibility execution pipeline
6. Async/await throughout for 100+ symbol concurrency
7. Position reconciliation for crash recovery
8. Error handling with retry logic and circuit breakers
9. Reliable order execution via CCXT and Direct Binance API
10. Persistent state management with Firebase

**Key Architectural Strengths**:
- ✅ Per-symbol database isolation (zero lock contention)
- ✅ Connection pooling with LRU eviction (200 connections)
- ✅ Dependency injection (testable, decoupled)
- ✅ Modular execution pipeline (fail-fast)
- ✅ Pluggable signal generation (easy to extend)
- ✅ 100+ symbols concurrency (async/await)
- ✅ Crash recovery (position reconciliation)
- ✅ Production resilience (retry + circuit breaker)

The architecture is designed for scalability and can be extended to support additional exchanges, strategies, and markets.
