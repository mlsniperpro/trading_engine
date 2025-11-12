# Trading Engine

A cryptocurrency trading engine with real-time price feeds from CEX (Centralized) and DEX (Decentralized) exchanges.

## Features

- **Real-time CEX Data**: Live prices from Binance, Coinbase, Kraken, Bybit via WebSocket
- **Real-time DEX Data**: On-chain Uniswap V3 swap monitoring via Alchemy
- **Unified Price Feed**: Combined CEX + DEX data with arbitrage detection
- **FastAPI Backend**: High-performance async API
- **Docker Deployment**: Containerized deployment to Hetzner Cloud
- **100% Free Data**: Uses free tiers (Alchemy 300M compute units/month + CryptoFeed)

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Alchemy API key (free tier: https://www.alchemy.com)

### Installation

1. Install dependencies:
```bash
uv sync
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your keys:
# - ALCHEMY_API_KEY (get from https://dashboard.alchemy.com)
# - HETZNER_API_KEY (optional, for deployment)
```

### Running the Price Feeds

**Test CEX Feed (Binance, Coinbase, Kraken, Bybit):**
```bash
uv run python -m trading_engine.price_feed
```

**Test DEX Feed (Uniswap V3 via Alchemy):**
```bash
uv run python -m trading_engine.dex_feed
```

**Test Unified Feed (CEX + DEX with arbitrage detection):**
```bash
uv run python -m trading_engine.unified_feed
```

### Running the API

**Option 1: Using the CLI entry point**
```bash
uv run trading-engine
```

**Option 2: Using uvicorn directly**
```bash
uv run uvicorn trading_engine.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Hello world endpoint
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Deployment

### Option 1: Create Hetzner Server

```bash
# Get API key from https://console.hetzner.cloud/ → Security → API Tokens
# Add to .env: HETZNER_API_KEY=your_key

# Create server (CX43: 8 vCPU, 16GB RAM, €9.99/month)
uv run hetzner-setup
```

### Option 2: Deploy with Docker

Automated Docker deployment to Hetzner VPS:

```bash
# Deploy to server (creates Docker containers)
uv run deploy
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

The project uses a `src` layout:

```
trading_engine/
├── src/trading_engine/
│   ├── main.py              # FastAPI application
│   ├── price_feed.py        # CEX price feed (4 exchanges)
│   ├── dex_feed.py          # DEX price feed (Uniswap V3)
│   ├── unified_feed.py      # Combined CEX + DEX
│   ├── deploy_docker.py     # Docker deployment
│   └── hetzner.py           # Hetzner Cloud automation
├── Dockerfile               # Container definition
├── docker-compose.yml       # Orchestration
├── pyproject.toml          # Dependencies
└── .env                    # Configuration
```

### Available Commands

```bash
uv run trading-engine    # Run FastAPI server
uv run hetzner-setup    # Create Hetzner VPS
uv run deploy           # Deploy with Docker
```

## Current Status (2025-11-12)

- ✅ FastAPI backend with health endpoints
- ✅ Docker deployment infrastructure
- ✅ Hetzner Cloud integration (CX43 server: 116.203.216.207)
- ✅ CEX price feed (CryptoFeed - Binance, Coinbase, Kraken, Bybit)
- ✅ DEX price feed (Alchemy WebSocket - connects successfully)
- ⚠️  DEX eth_subscribe compatibility issue (investigating)
- ⏳ Unified feed pending testing
- ⏳ Arbitrage detection pending testing
