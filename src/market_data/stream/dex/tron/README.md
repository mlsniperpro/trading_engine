# TRON DEX Integration

Real-time monitoring for the top 4 TRON decentralized exchanges using TronGrid API.

## Overview

This module provides real-time swap monitoring for TRON's leading DEXs:

1. **SunSwap V3** - Concentrated liquidity (78-89% volume share, $288M TVL)
2. **SunSwap V2** - Uniswap V2 style AMM ($431M TVL, meme coin support)
3. **SunSwap V1** - Original TRON DEX ($452M TVL, highest TVL)
4. **JustMoney** - Multi-chain DEX (taxed token support, growing)

## Architecture

### Technology Stack
- **TronGrid API**: Free REST API for TRON event monitoring
- **aiohttp**: Async HTTP client for efficient polling
- **Python asyncio**: Non-blocking event processing

### Design Pattern
Unlike Ethereum/Solana which use WebSocket streams, TRON uses HTTP polling because:
- TRON doesn't have stable WebSocket endpoints
- TronGrid REST API is more reliable
- Free tier provides sufficient rate limits (10 req/s, 10K req/day)
- With API key: 50 req/s, 100K req/day (still free)

## Files

```
tron/
├── __init__.py           # Module exports
├── base.py              # TronDEXStream base class
├── sunswap_v3.py        # SunSwap V3 (concentrated liquidity)
├── sunswap_v2.py        # SunSwap V2 (Uniswap V2 style)
├── sunswap_v1.py        # SunSwap V1 (legacy)
├── justmoney.py         # JustMoney DEX
└── README.md            # This file
```

## Usage

### Basic Example

```python
from market_data.stream.dex.tron import SunSwapV3Stream

# Create stream
stream = SunSwapV3Stream(
    pools=["TRX-USDT", "WTRX-USDT"],
    trongrid_api_key="YOUR_API_KEY",  # Optional but recommended
    poll_interval=2.0  # Poll every 2 seconds
)

# Register callback
async def handle_swap(event):
    print(f"Swap on {event['dex']}: {event['swap_details']}")

stream.on_swap(handle_swap)

# Start monitoring
await stream.start()
```

### Via MarketDataManager

```python
from market_data.stream.manager import MarketDataManager

manager = MarketDataManager(
    enable_sunswap_v3=True,
    enable_sunswap_v2=True,
    enable_sunswap_v1=True,
    enable_justmoney=True,
)

await manager.start()
```

## DEX Details

### SunSwap V3
- **Type**: Concentrated Liquidity (Uniswap V3 fork)
- **Market Share**: 78-89% of TRON DEX volume
- **TVL**: $288M
- **Daily Volume**: $49-67M
- **Contract**: TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj (Smart Router)

### SunSwap V2
- **Type**: Constant Product AMM (Uniswap V2 fork)
- **TVL**: $431M
- **Use Case**: Meme coins, new token launches
- **Contract**: TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax

### SunSwap V1
- **Type**: Legacy AMM
- **TVL**: $452M (highest among all versions!)
- **Status**: Legacy but still very active
- **Contract**: TXk8rQSAvPvBBNtqSoY6nCfsXWCSSpTVQF

### JustMoney
- **Type**: Multi-chain DEX
- **Features**: First TRON DEX with full taxed token support
- **Daily Volume**: ~$3.5K (growing)
- **Contract**: TBD (pending verification)

## Event Structure

### SunSwap V3 Events
```python
{
    "pool": "contract_address",
    "sender": "sender_address",
    "recipient": "recipient_address",
    "amount0": -1000000,  # Negative = out
    "amount1": 2000000,   # Positive = in
    "price": 2.0,
    "sqrt_price_x96": "...",
    "liquidity": 12345,
    "tick": 100,
    "transaction_id": "...",
    "block_number": 12345,
    "dex": "sunswap_v3"
}
```

### SunSwap V2 Events
```python
{
    "pair": "contract_address",
    "sender": "sender_address",
    "recipient": "recipient_address",
    "amount0_in": 1000000,
    "amount1_in": 0,
    "amount0_out": 0,
    "amount1_out": 2000000,
    "price": 2.0,
    "direction": "TOKEN0_TO_TOKEN1",
    "transaction_id": "...",
    "dex": "sunswap_v2"
}
```

## Configuration

Configuration is stored in `/config/tron_dex.yaml`:

```yaml
sunswap_v3:
  router: "TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj"
  tvl_usd: 288000000
  pools:
    - name: "TRX-USDT"
      fee_tier: 3000

trongrid:
  mainnet_url: "https://api.trongrid.io"
  free_tier:
    rate_limit_per_second: 50
```

## Rate Limits

### Without API Key (Free)
- 10 requests per second
- 10,000 requests per day

### With API Key (Still Free!)
- 50 requests per second
- 100,000 requests per day

Get your free API key at: https://www.trongrid.io/

## Implementation Notes

### Why Polling Instead of WebSocket?

1. **No Stable WebSocket**: TRON doesn't have reliable WebSocket endpoints
2. **REST is Sufficient**: With 2-3 second polling, we get near real-time data
3. **More Reliable**: REST APIs are more stable than WebSocket for TRON
4. **Lower Complexity**: No reconnection logic needed

### Contract Address Discovery

Some contract addresses are marked as "TBD" because:
- SunSwap uses a unified Smart Router for V1/V2/V3
- Individual pool addresses need to be queried from factory contracts
- JustMoney's official contract addresses need verification

**To get actual pool addresses:**
```python
# Query factory contract for pair addresses
# This is TODO for production deployment
```

### Event Parsing Accuracy

Event field names are based on:
- Uniswap V2/V3 specifications (SunSwap is a fork)
- Available documentation
- Common Solidity event patterns

**Testing Required**: Actual event structures should be verified against real TRON mainnet events.

## Testing Recommendations

### 1. Contract Address Verification
```bash
# Verify SunSwap V3 Router
curl "https://api.trongrid.io/v1/contracts/TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj"

# Verify SunSwap V2 Router
curl "https://api.trongrid.io/v1/contracts/TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"
```

### 2. Event Structure Verification
```bash
# Get recent swap events from SunSwap V3
curl "https://api.trongrid.io/v1/contracts/TCFNp179Lg46D16zKoumd4Poa2WFFdtqYj/events?event_name=Swap&limit=10"
```

### 3. Integration Testing
```python
# Test with manager
import asyncio
from market_data.stream.manager import MarketDataManager

async def test():
    manager = MarketDataManager(enable_sunswap_v3=True)
    await manager.start()

asyncio.run(test())
```

## Known Limitations

1. **JustMoney Contract**: Need to verify actual contract address
2. **Pool Addresses**: Individual pool addresses need to be populated
3. **Event Fields**: Field names may need adjustment based on actual events
4. **Rate Limits**: Default polling may hit rate limits with many DEXs enabled
5. **Token Decimals**: Price calculations don't account for token decimals yet

## Future Enhancements

1. **Config-based Contracts**: Load addresses from `tron_dex.yaml`
2. **Factory Queries**: Auto-discover pool addresses from factory contracts
3. **Token Metadata**: Fetch and cache token decimals for accurate pricing
4. **Batch Queries**: Query multiple contracts in single request
5. **Event Caching**: Deduplicate events across different streams

## Troubleshooting

### No Events Received
- Check contract address is correct
- Verify event_name matches contract events
- Ensure TronGrid API is accessible
- Try reducing poll_interval

### Rate Limit Errors
- Get a free TronGrid API key
- Increase poll_interval
- Reduce number of enabled DEXs

### Parsing Errors
- Log raw event data to inspect structure
- Adjust field names in `_parse_swap_event()`
- Check event signature in contract

## Resources

- TronGrid API: https://www.trongrid.io/
- TRON Developer Docs: https://developers.tron.network/
- SunSwap Docs: https://docs.sun.io/
- TronPy Library: https://tronpy.readthedocs.io/
- TRON Network Explorer: https://tronscan.org/
