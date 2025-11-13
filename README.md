# Trading Engine

A high-performance cryptocurrency trading engine with real-time price feeds from CEX (Centralized) and DEX (Decentralized) exchanges, featuring automatic arbitrage detection.

## 🚀 Quick Start

```bash
# Install dependencies
uv sync

# Configure (add your Alchemy API key)
cp .env.example .env

# Start the engine
uv run start
```

That's it! Just **3 commands** to get running.

**That's it!** The system starts:
- FastAPI server on http://localhost:8000
- DEX stream (Uniswap V3)
- CEX stream (Binance)
- Arbitrage detection

See [QUICKSTART.md](QUICKSTART.md) for details.

## ✨ Features

- **Real-time Market Data**
  - ✅ **DEX Support (Top 4 Ethereum DEXs)**:
    - **Uniswap V3** - $39.7B weekly volume (market leader)
    - **Curve Finance** - $2.4B volume (stablecoin specialist)
    - **SushiSwap** - Major AMM (Uniswap V2 fork)
    - **Balancer V2** - Multi-token weighted pools
  - ✅ CEX: Binance trades via WebSocket
  - ✅ Multi-pool/pair support across all DEXs

- **Arbitrage Detection**
  - ✅ Real-time price comparison across 4 DEXs + CEX
  - ✅ Configurable threshold (default: 0.3%)
  - ✅ Instant alerts via logs and API
  - ✅ Cross-DEX arbitrage monitoring

- **Modern Architecture**
  - ✅ FastAPI backend
  - ✅ Async/await throughout
  - ✅ Modular stream design
  - ✅ Event-driven architecture (in progress)

- **Deployment**
  - ✅ Docker containerization
  - ✅ Hetzner Cloud automation
  - ✅ One-command deployment

## 📡 API Endpoints

Once running (`uv run start`):

### System Endpoints
- `GET /` - System status
- `GET /health` - Health check
- `GET /prices` - Current prices (DEX + CEX)
- `GET /docs` - Interactive API documentation

### Log Endpoints
- `GET /logs` - Get logs with optional filtering
  - Query params: `lines`, `level` (ERROR/WARNING/INFO/DEBUG), `search`
  - Example: `/logs?lines=50&level=ERROR&search=ARBITRAGE`
- `GET /logs/recent` - Get recent log lines
  - Query params: `lines` (default: 100, max: 1000)
- `GET /logs/errors` - Get error logs only
  - Query params: `lines` (default: 100, max: 1000)
- `GET /logs/stats` - Get log statistics (buffer size, error count, etc.)

Example response from `/prices`:
```json
{
  "dex": {
    "ETH-USDC-0.3%": 3510.95,
    "ETH-USDT-0.3%": 3510.80
  },
  "cex": {
    "ETH-USDT": 3510.50
  }
}
```

Example response from `/logs/stats`:
```json
{
  "total_logs": 248,
  "max_size": 1000,
  "errors": 0,
  "warnings": 12,
  "info": 236,
  "buffer_full": false,
  "timestamp": "2025-11-13T10:00:00Z"
}
```

## 🏗️ Architecture

```
src/
├── main.py                  # Main entry point (FastAPI + streams)
└── market_data/
    └── stream/
        ├── dex_stream.py    # DEX (Uniswap V3) stream
        ├── cex_stream.py    # CEX (Binance) stream
        └── manager.py       # Coordinator + arbitrage detection
```

**Next:** Add `storage/`, `analytics/`, `decision/`, and `execution/` layers.

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the complete architectural plan.

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[LOGGING.md](LOGGING.md)** - Monitor logs on Hetzner server
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Complete architecture
- **[DESIGN_DOC.md](DESIGN_DOC.md)** - Technical design

## 🎯 Available Commands

### Using Make (Recommended)
```bash
make start          # Start the trading engine
make stop           # Stop the engine
make deploy         # Deploy to Hetzner with Docker
make logs           # View logs from Hetzner
make hetzner-setup  # Create Hetzner Cloud server
make install        # Install dependencies
make clean          # Clean cache files
```

### Using Scripts Directly
```bash
# Start the engine
uv run start

# Deployment scripts
uv run python scripts/deploy_docker.py
uv run python scripts/hetzner.py
uv run python scripts/logs.py
```

**Log Monitoring (Fly.io-style!):**
```bash
make logs                              # Follow logs in real-time
uv run python scripts/logs.py --tail 200         # Show last 200 lines
uv run python scripts/logs.py --since 1h         # Show last hour
uv run python scripts/logs.py --errors           # Show only errors
uv run python scripts/logs.py --grep ARBITRAGE   # Filter for specific text
uv run python scripts/logs.py --stats            # Show statistics
```

## 🔧 Configuration

### Environment Variables

Copy the example file and fill in your values:
```bash
cp config/.env.example .env
```

Required:
- `ALCHEMY_API_KEY` - Get free API key at https://dashboard.alchemy.com

Optional (for deployment):
- `HETZNER_API_KEY` - For Hetzner Cloud deployment

### Configuration Files

All configuration is centralized in `config/` directory:

- **`config/dex.yaml`** - All DEX configurations (Uniswap V3, Curve, SushiSwap, Balancer)
  - Pool/pair addresses and ABIs
  - Router addresses
  - Token addresses
  - Arbitrage settings
- **`config/.env.example`** - Environment variables template

To customize pools, add new DEXs, or modify arbitrage settings, edit `config/dex.yaml`

## Deployment

### Option 1: Create Hetzner Server

```bash
# Get API key from https://console.hetzner.cloud/ → Security → API Tokens
# Add to .env: HETZNER_API_KEY=your_key

# Create server (CX43: 8 vCPU, 16GB RAM, €9.99/month)
make hetzner-setup
```

### Option 2: Deploy with Docker

Automated Docker deployment to Hetzner VPS:

```bash
# Deploy to server (creates Docker containers)
make deploy
```

This will:
- Install Docker on the server
- Copy project files via rsync
- Build Docker image
- Start containers with docker-compose
- Configure health checks and auto-restart

**Server Info:**
- Current: 116.203.216.207 (CX43, Nuremberg, Germany)
- User: root
- Docker Compose with .env support

## Development

Project structure:

```
trading_engine/
├── src/
│   ├── main.py                    # FastAPI application
│   └── market_data/               # Market data ingestion
│       ├── cex_feed.py            # CEX feeds (Binance, Coinbase, etc.)
│       ├── dex_feed.py            # DEX feeds (Uniswap V3)
│       └── unified_feed.py        # Combined CEX + DEX
├── scripts/
│   ├── deploy_docker.py           # Docker deployment
│   └── hetzner.py                 # Hetzner Cloud automation
├── Dockerfile                     # Container definition
├── docker-compose.yml             # Orchestration
├── pyproject.toml                # Dependencies
└── .env                          # Configuration
```

### Available Commands

```bash
make start                          # Run FastAPI server
make hetzner-setup                  # Create Hetzner VPS
make deploy                         # Deploy with Docker
make logs                           # View remote logs
```

## 🎯 Current Status (2025-11-13)

**✅ Working:**
- FastAPI backend with real-time data
- DEX stream (Uniswap V3 via Alchemy)
- CEX stream (Binance via CryptoFeed)
- MarketDataManager with arbitrage detection
- Docker deployment infrastructure
- Hetzner Cloud integration
- One-command startup (`uv run start`)

**🚧 In Progress:**
- Database layer (DuckDB persistence)
- Analytics engine (order flow, market profile)
- Decision engine (signal generation)
- Execution engine (order management)

**📈 Performance:**
- DEX: 10-50 swaps/minute on ETH-USDC-0.3%
- CEX: 100-500 trades/minute on Binance
- Memory: <50MB
- Latency: DEX ~12-15s (blockchain), CEX <100ms
