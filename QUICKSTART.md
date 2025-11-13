# Trading Engine - Quick Start Guide

## 🚀 Starting the System

```bash
uv run start
```

This single command starts:
- **FastAPI server** on http://localhost:8000
- **DEX stream** (Uniswap V3 on Ethereum)
- **CEX stream** (Binance)
- **Arbitrage detection** (automatic)

## 📡 API Endpoints

Once running, access:

- **http://localhost:8000** - System status
- **http://localhost:8000/health** - Health check
- **http://localhost:8000/prices** - Current prices (DEX + CEX)
- **http://localhost:8000/docs** - Interactive API documentation

## 📊 What You'll See

```
======================================================================
🚀 Starting Trading Engine
======================================================================

Components:
  • FastAPI server on http://0.0.0.0:8000
  • DEX stream (Uniswap V3)
  • CEX stream (Binance)
  • Arbitrage detection

======================================================================
✓ Market data streams started
======================================================================

📊 Current Uniswap V3 ETH/USDC: $3510.95
✓ Subscribed to real-time DEX swaps
✓ Monitoring 2 Uniswap V3 pools

🔄 Swap #1 [ETH-USDC-0.3%] | BUY | ETH: 0.0903 ($317.04) | USDC: 316.88 | Price: $3,510.93
💹 Trade #1 [ETH-USDT] | BUY | Price: $3510.50 | Amount: 0.5000

🚨 ARBITRAGE: 0.35% | DEX: $3511.00 | CEX: $3510.00 | Action: BUY_CEX_SELL_DEX
```

## 🏗️ New Project Structure

```
src/trading_engine/
├── __init__.py              # Main entry point (FastAPI + streams)
└── market_data/
    └── stream/
        ├── dex_stream.py    # DEX (Uniswap) stream
        ├── cex_stream.py    # CEX (Binance) stream
        └── manager.py       # Coordinator + arbitrage detection
```

## 🔧 Configuration

Set your Alchemy API key in `.env`:

```bash
ALCHEMY_API_KEY=your_key_here
```

## 📈 Monitoring Prices

### Via API
```bash
curl http://localhost:8000/prices
```

Response:
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

### Via Browser
Open http://localhost:8000/docs for interactive API

## 🎯 What's Happening

1. **DEX Stream** connects to Ethereum blockchain via Alchemy
2. **Monitors 2 Uniswap V3 pools**:
   - ETH-USDC-0.3% (most liquid, 0.3% fee tier)
   - ETH-USDT-0.3% (alternative stablecoin pair)
3. **CEX Stream** connects to Binance WebSocket
4. **Arbitrage Detection** compares prices in real-time
5. **Alerts when price difference > 0.3%**

## 🔍 Understanding Fee Tiers

Uniswap V3 has multiple pools with different fees:

| Pool Name | Fee | Use Case |
|-----------|-----|----------|
| ETH-USDC-0.05% | 0.05% | Lower fees, less liquidity |
| ETH-USDC-0.3% | 0.3% | **Most popular**, good liquidity |
| ETH-USDC-1% | 1% | Higher fees, rarely used |

## 🛠️ Development

### Run individual components:

**DEX stream only:**
```bash
uv run python -m trading_engine.market_data.stream.dex_stream
```

**CEX stream only:**
```bash
uv run python -m trading_engine.market_data.stream.cex_stream
```

**Arbitrage monitor (example):**
```bash
uv run python examples/monitor_dex_cex_arbitrage.py
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'trading_engine'"
```bash
uv sync  # Reinstall package
```

### "Failed to connect to Ethereum WebSocket"
- Check your `ALCHEMY_API_KEY` in `.env`
- Verify internet connection
- Check Alchemy service status

### "CEX stream not starting"
- The `cryptofeed` library takes a moment to connect
- Check Binance API status

## 📚 Next Steps

1. **Add more pools**: Edit `src/trading_engine/__init__.py` line 79
2. **Change arbitrage threshold**: Edit line 81 (currently 0.3%)
3. **Add storage**: Implement `market_data/storage/` (DuckDB)
4. **Add analytics**: Implement `analytics/` layer
5. **Add trading**: Implement `decision/` and `execution/` layers

## 🏛️ Architecture

This follows the master architecture plan:

```
✅ market_data/stream/    - Real-time data (DEX + CEX)
⏳ market_data/storage/   - TODO: DuckDB persistence
⏳ analytics/             - TODO: Order flow, market profile
⏳ decision/              - TODO: Signal generation
⏳ execution/             - TODO: Order execution
```

## 📖 Documentation

- **Stream README**: `src/trading_engine/market_data/stream/README.md`
- **Architecture**: `PROJECT_STRUCTURE.md`
- **Design Doc**: `DESIGN_DOC.md`

## 🎉 Success Indicators

You know it's working when you see:

1. ✅ Server starts on port 8000
2. ✅ "Connected to Ethereum mainnet"
3. ✅ "Subscribed to real-time DEX swaps"
4. ✅ Swap events appearing with prices
5. ✅ API responds at http://localhost:8000/prices

## ⚡ Performance

- **DEX**: 10-50 swaps/minute on ETH-USDC-0.3%
- **CEX**: 100-500 trades/minute on Binance
- **Memory**: <50MB
- **CPU**: <5% idle, ~15% during active trading

---

**Ready to trade? Start with `uv run start` and watch the markets flow!** 📈
