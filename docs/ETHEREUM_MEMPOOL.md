# Ethereum Mempool Streaming

## Overview

The trading engine now streams **pending transactions** from the Ethereum mempool in real-time, providing visibility into transactions **before they are mined**. This enables:

- **MEV opportunities**: See large swaps before they execute
- **Front-running detection**: Monitor for sandwich attacks
- **Market intelligence**: Track whale movements in real-time
- **Arbitrage opportunities**: React faster than competitors

## Architecture

### Dual Subscription Model

Each Ethereum DEX stream (Uniswap V3, Curve, SushiSwap, Balancer) now maintains **two concurrent subscriptions**:

1. **Finalized Swaps** (`eth_subscribe("logs")`)
   - Monitors actual executed swaps on-chain
   - Provides accurate price and volume data
   - Used for arbitrage detection and price tracking

2. **Pending Transactions** (`eth_subscribe("newPendingTransactions")`)
   - Monitors transactions in the mempool before mining
   - Filters for DEX-related transactions
   - Logs high-value pending swaps

### Implementation (Uniswap V3)

Located in: `src/market_data/stream/dex/ethereum/uniswap_v3.py`

```python
class DEXStream:
    def __init__(
        self,
        alchemy_api_key: Optional[str] = None,
        pools: Optional[List[str]] = None,
        chain: str = "ethereum",
        enable_mempool: bool = True  # ← NEW: Enable mempool monitoring
    ):
        # ...
        self.enable_mempool = enable_mempool
        self.pending_tx_callbacks: List[Callable] = []
        self.pending_tx_count = 0
```

### Key Methods

#### `subscribe_to_mempool()`
Subscribes to Ethereum's pending transaction stream:

```python
async def subscribe_to_mempool(self):
    """Subscribe to pending transactions in mempool."""
    subscription_id = await self.w3.eth.subscribe("newPendingTransactions")

    async for payload in self.w3.socket.process_subscriptions():
        tx_hash = payload["result"]
        # Process asynchronously to avoid blocking
        asyncio.create_task(self._handle_pending_transaction(tx_hash))
```

#### `_handle_pending_transaction(tx_hash)`
Processes each pending transaction:

1. Fetches transaction details from node
2. Checks if transaction is to monitored DEX pools/routers
3. Extracts value, gas price, sender/receiver
4. Logs high-value transactions (> 1 ETH)
5. Notifies registered callbacks

```python
async def _handle_pending_transaction(self, tx_hash: str):
    tx = await self.w3.eth.get_transaction(tx_hash)

    # Filter for Uniswap transactions
    if to_address in [pool addresses or router addresses]:
        pending_tx_data = {
            'exchange': 'UNISWAP_V3',
            'pool': pool_name or 'ROUTER',
            'tx_hash': tx_hash,
            'value_eth': Decimal(str(value_eth)),
            'gas_price_gwei': Decimal(str(gas_price_gwei)),
            'status': 'pending'
        }

        # Notify callbacks
        await self._notify_pending_tx_callbacks(pending_tx_data)
```

## Configuration

### Enable/Disable Mempool Monitoring

Mempool monitoring is **enabled by default**. To disable:

```python
stream = UniswapV3Stream(
    pools=["ETH-USDC-0.3%"],
    enable_mempool=False  # Disable mempool
)
```

### Logging Threshold

By default, only pending transactions with **value > 1 ETH** are logged to reduce noise. Adjust in `_handle_pending_transaction()`:

```python
if value_eth > 1.0:  # ← Change this threshold
    logger.info(f"⏳ Pending TX | Value: {value_eth:.4f} ETH")
```

## Usage

### Register Callback for Pending Transactions

```python
stream = UniswapV3Stream(pools=["ETH-USDC-0.3%"])

async def handle_pending_tx(tx_data):
    """Process pending transaction."""
    print(f"⏳ Pending: {tx_data['pool']}")
    print(f"   Value: {tx_data['value_eth']} ETH")
    print(f"   Gas: {tx_data['gas_price_gwei']} Gwei")
    print(f"   TX: {tx_data['tx_hash']}")

stream.on_pending_tx(handle_pending_tx)
await stream.start()
```

### Example Output

```
✓ Mempool monitoring enabled
🔮 Subscribing to Ethereum mempool (pending transactions)...
✓ Subscribed to mempool (ID: 0xc608f1ec9f7f48ca4a760dc21aae79c6)

⏳ Pending TX #42 | Pool: ETH-USDC-0.3% | Value: 5.2500 ETH | Gas: 45.23 Gwei | TX: 0x1234abcd...
⏳ Pending TX #43 | Pool: ROUTER | Value: 12.5000 ETH | Gas: 120.50 Gwei | TX: 0x5678ef01...
```

## Performance Considerations

### Asynchronous Processing

Pending transactions are processed **asynchronously** to avoid blocking the main event loop:

```python
# Don't block the subscription stream
asyncio.create_task(self._handle_pending_transaction(tx_hash))
```

### Filtering Strategy

The mempool contains thousands of transactions per second. We filter aggressively:

1. **DEX-specific**: Only Uniswap pools/routers
2. **High-value**: Only log > 1 ETH transactions
3. **Error handling**: Silent failure for invalid transactions

### Network Requirements

- **Alchemy/Infura**: Requires WebSocket connection with mempool access
- **Bandwidth**: ~50-200 KB/s for pending transaction hashes
- **API limits**: Check your RPC provider's rate limits

## Comparison to Solana

| Feature | Ethereum (Web3.py) | Solana (Yellowstone) |
|---------|-------------------|---------------------|
| **Subscription** | `newPendingTransactions` | gRPC transaction stream |
| **Latency** | ~100-500ms | ~50-200ms |
| **Volume** | ~150 tx/s (ETH mainnet) | ~3000 tx/s (Solana) |
| **Decoding** | Requires transaction fetch | Built-in IDL parsing |
| **Cost** | Free (Alchemy/Infura) | Paid (Helius/Triton) |

## Limitations

1. **No transaction decoding**: We receive transaction hashes, not decoded data
2. **Additional RPC calls**: Must fetch transaction details separately
3. **No guarantee of execution**: Pending transactions may fail or be replaced
4. **Rate limits**: Heavy mempool monitoring can hit API limits

## Future Enhancements

### Planned Features

- [ ] **Transaction decoding**: Parse swap amounts from calldata
- [ ] **MEV detection**: Identify sandwich attacks and front-running
- [ ] **Gas price analysis**: Track gas wars and priority fees
- [ ] **Mempool analytics**: Statistics on pending transaction flow
- [ ] **Multi-DEX aggregation**: Shared mempool monitor for all Ethereum DEXs

### Advanced Use Cases

- **Sandwich attack detection**: Identify front-run → victim → back-run patterns
- **Whale tracking**: Monitor large holders' pending transactions
- **Gas market analysis**: Track priority fee distributions
- **Smart order routing**: Adjust routing based on pending transactions

## Troubleshooting

### No pending transactions logged

This is normal if:
- No high-value (> 1 ETH) Uniswap transactions are occurring
- Mempool is quiet (rare on mainnet)

To verify mempool is working, lower the logging threshold temporarily.

### Connection errors

```
ERROR: Mempool subscription failed
```

**Solutions**:
1. Check Alchemy API key is valid
2. Verify WebSocket connection
3. Ensure your plan supports mempool streaming
4. Check rate limits haven't been exceeded

### High CPU/memory usage

Mempool monitoring processes thousands of transactions. To reduce load:

1. Increase the logging threshold (e.g., > 10 ETH)
2. Add more aggressive filtering
3. Disable mempool for less critical DEXs
4. Use batched processing

## Security Considerations

1. **Transaction validation**: Always validate pending transactions before acting
2. **Slippage protection**: Mempool data may be stale by execution time
3. **Reentrancy**: Process callbacks asynchronously to prevent blocking
4. **Rate limiting**: Implement backoff for RPC calls

## References

- [Ethereum JSON-RPC Specification](https://ethereum.org/en/developers/docs/apis/json-rpc/)
- [Alchemy WebSocket API](https://docs.alchemy.com/reference/subscription-api)
- [MEV Research](https://ethereum.org/en/developers/docs/mev/)
- [Flashbots Documentation](https://docs.flashbots.net/)
