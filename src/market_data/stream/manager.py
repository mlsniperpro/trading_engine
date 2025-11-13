"""
Market Data Manager - Central coordinator for all market data streams.

Manages multiple data streams (DEX + CEX) and provides unified interface.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Callable
from decimal import Decimal

from .dex import (
    UniswapV3Stream, CurveStream, SushiSwapStream, BalancerStream,
    PumpFunStream, RaydiumStream, JupiterStream, OrcaStream, MeteoraStream
)
from .cex import BinanceStream

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Central coordinator for market data streams.

    Manages both DEX and CEX streams, provides arbitrage detection,
    and emits unified market data events.

    Architecture fit:
    - Part of market_data/stream layer
    - Coordinates multiple data sources
    - Future: Will emit events to core/event_bus.py
    - Future: Will store data via storage/database_manager.py

    Usage:
        manager = MarketDataManager(
            enable_dex=True,
            enable_cex=True,
            dex_pools=["ETH-USDC-0.3%"],
            cex_symbols=["ETH-USDT"]
        )
        manager.on_arbitrage(callback)
        await manager.start()
    """

    def __init__(
        self,
        # Ethereum DEX (Decentralized Exchanges)
        enable_uniswap_v3: bool = True,
        enable_curve: bool = False,
        enable_sushiswap: bool = False,
        enable_balancer: bool = False,
        uniswap_pools: Optional[List[str]] = None,
        curve_pools: Optional[List[str]] = None,
        sushiswap_pairs: Optional[List[str]] = None,
        balancer_pools: Optional[List[str]] = None,
        # Solana DEX
        enable_pump_fun: bool = False,
        enable_raydium: bool = False,
        enable_jupiter: bool = False,
        enable_orca: bool = False,
        enable_meteora: bool = False,
        pump_fun_min_mcap: float = 1000,
        raydium_pools: Optional[List[str]] = None,
        orca_pools: Optional[List[str]] = None,
        meteora_pools: Optional[List[str]] = None,
        # CEX (Centralized Exchanges)
        enable_binance: bool = True,
        binance_symbols: Optional[List[str]] = None,
        # Settings
        arbitrage_threshold_pct: float = 0.5,  # 0.5% price difference
    ):
        """
        Initialize MarketDataManager.

        Args:
            # Ethereum DEX (Decentralized Exchanges)
            enable_uniswap_v3: Enable Uniswap V3 stream
            enable_curve: Enable Curve Finance stream
            enable_sushiswap: Enable SushiSwap stream
            enable_balancer: Enable Balancer V2 stream
            uniswap_pools: List of Uniswap V3 pools to monitor
            curve_pools: List of Curve pools to monitor
            sushiswap_pairs: List of SushiSwap pairs to monitor
            balancer_pools: List of Balancer pools to monitor
            # Solana DEX
            enable_pump_fun: Enable Pump.fun stream (meme coin launchpad)
            enable_raydium: Enable Raydium stream (#1 Solana DEX, 34% volume)
            enable_jupiter: Enable Jupiter stream (DEX aggregator)
            enable_orca: Enable Orca stream (Whirlpools, 19% volume)
            enable_meteora: Enable Meteora stream (DLMM, 22% volume)
            pump_fun_min_mcap: Minimum market cap for Pump.fun tokens (USD)
            raydium_pools: List of Raydium pools to monitor
            orca_pools: List of Orca Whirlpools to monitor
            meteora_pools: List of Meteora DLMM pools to monitor
            # CEX (Centralized Exchanges)
            enable_binance: Enable Binance stream
            binance_symbols: List of Binance symbols to monitor
            # Settings
            arbitrage_threshold_pct: Minimum price difference % for arbitrage alert
        """
        # Ethereum DEX flags
        self.enable_uniswap_v3 = enable_uniswap_v3
        self.enable_curve = enable_curve
        self.enable_sushiswap = enable_sushiswap
        self.enable_balancer = enable_balancer

        # Solana DEX flags
        self.enable_pump_fun = enable_pump_fun
        self.enable_raydium = enable_raydium
        self.enable_jupiter = enable_jupiter
        self.enable_orca = enable_orca
        self.enable_meteora = enable_meteora

        # CEX flags
        self.enable_binance = enable_binance

        self.arbitrage_threshold = Decimal(str(arbitrage_threshold_pct / 100))

        # Initialize Ethereum DEX streams
        self.uniswap_stream = UniswapV3Stream(pools=uniswap_pools) if enable_uniswap_v3 else None
        self.curve_stream = CurveStream(pools=curve_pools) if enable_curve else None
        self.sushiswap_stream = SushiSwapStream(pairs=sushiswap_pairs) if enable_sushiswap else None
        self.balancer_stream = BalancerStream(pools=balancer_pools) if enable_balancer else None

        # Initialize Solana DEX streams
        self.pump_fun_stream = PumpFunStream(min_market_cap_usd=pump_fun_min_mcap) if enable_pump_fun else None
        self.raydium_stream = RaydiumStream(pools=raydium_pools) if enable_raydium else None
        self.jupiter_stream = JupiterStream() if enable_jupiter else None
        self.orca_stream = OrcaStream(pools=orca_pools) if enable_orca else None
        self.meteora_stream = MeteoraStream(pools=meteora_pools) if enable_meteora else None

        # Initialize CEX streams
        self.binance_stream = BinanceStream(symbols=binance_symbols) if enable_binance else None

        # Price tracking
        self.dex_prices: Dict[str, Decimal] = {}  # pool_name -> price
        self.cex_prices: Dict[str, Decimal] = {}  # symbol -> price

        # Callbacks
        self.arbitrage_callbacks: List[Callable] = []
        self.unified_price_callbacks: List[Callable] = []

        self._running = False

    async def _handle_dex_swap(self, swap_data: Dict):
        """Handle DEX swap event (Uniswap V3, Curve, SushiSwap, Balancer)."""
        try:
            pool = swap_data['pool']
            price = swap_data.get('price')
            exchange = swap_data.get('exchange', 'UNISWAP_V3')

            # Update DEX price if available
            if price:
                self.dex_prices[f"{exchange}:{pool}"] = price

                # Check for arbitrage opportunities
                await self._check_arbitrage(source='DEX', pool=pool, price=price, exchange=exchange)

            # Emit unified price event
            volume = swap_data.get('trade_value_usd', 0)
            await self._emit_unified_price({
                'source': 'DEX',
                'venue': exchange,
                'pair': pool,
                'price': price,
                'timestamp': swap_data.get('timestamp'),
                'volume': volume,
            })

        except Exception as e:
            logger.error(f"Error handling DEX swap: {e}")

    async def _handle_cex_trade(self, trade_data: Dict):
        """Handle CEX trade event."""
        try:
            symbol = trade_data['symbol']
            price = trade_data['price']

            # Update CEX price
            self.cex_prices[symbol] = price

            # Check for arbitrage opportunities
            await self._check_arbitrage(source='CEX', symbol=symbol, price=price)

            # Emit unified price event
            await self._emit_unified_price({
                'source': 'CEX',
                'venue': trade_data['exchange'],
                'pair': symbol,
                'price': price,
                'timestamp': trade_data['timestamp'],
                'volume': trade_data['price'] * trade_data['amount'],
            })

        except Exception as e:
            logger.error(f"Error handling CEX trade: {e}")

    async def _handle_pump_fun_launch(self, launch_data: Dict):
        """Handle Pump.fun token launch event."""
        try:
            # Just log for now - no arbitrage check for new launches
            logger.info(
                f"🚀 New Pump.fun launch: {launch_data['token_address'][:12]}... | "
                f"Mcap: ${launch_data['initial_market_cap_usd']:,.0f}"
            )
        except Exception as e:
            logger.error(f"Error handling Pump.fun launch: {e}")

    async def _handle_pump_fun_trade(self, trade_data: Dict):
        """Handle Pump.fun bonding curve trade."""
        try:
            # Track bonding curve price
            token = trade_data['token_address']
            price = trade_data['price']
            self.dex_prices[f"PUMP_FUN:{token}"] = Decimal(str(price))
        except Exception as e:
            logger.error(f"Error handling Pump.fun trade: {e}")

    async def _handle_pump_fun_graduate(self, grad_data: Dict):
        """Handle Pump.fun graduation to Raydium."""
        try:
            logger.warning(
                f"🎓 Pump.fun graduation: {grad_data['token_address'][:12]}... | "
                f"Mcap: ${grad_data['final_market_cap_usd']:,.0f}"
            )
        except Exception as e:
            logger.error(f"Error handling Pump.fun graduation: {e}")

    async def _handle_raydium_swap(self, swap_data: Dict):
        """Handle Raydium swap event."""
        try:
            pool = swap_data['pool']
            price = swap_data.get('price')

            if price:
                self.dex_prices[f"RAYDIUM:{pool}"] = Decimal(str(price))

                # Future: Check for cross-chain arbitrage (Solana vs Ethereum)
                # For now, just track Solana prices

        except Exception as e:
            logger.error(f"Error handling Raydium swap: {e}")

    async def _handle_jupiter_swap(self, swap_data: Dict):
        """Handle Jupiter aggregator swap event."""
        try:
            pair = f"{swap_data['input_mint']}-{swap_data['output_mint']}"
            price = swap_data.get('price')

            if price:
                self.dex_prices[f"JUPITER:{pair}"] = Decimal(str(price))

        except Exception as e:
            logger.error(f"Error handling Jupiter swap: {e}")

    async def _handle_orca_swap(self, swap_data: Dict):
        """Handle Orca Whirlpool swap event."""
        try:
            pool = swap_data['whirlpool']
            price = swap_data.get('price')

            if price:
                self.dex_prices[f"ORCA:{pool}"] = Decimal(str(price))

        except Exception as e:
            logger.error(f"Error handling Orca swap: {e}")

    async def _handle_meteora_swap(self, swap_data: Dict):
        """Handle Meteora DLMM swap event."""
        try:
            pool = swap_data['pool']
            price = swap_data.get('price')

            if price:
                self.dex_prices[f"METEORA:{pool}"] = Decimal(str(price))

        except Exception as e:
            logger.error(f"Error handling Meteora swap: {e}")

    async def _check_arbitrage(
        self,
        source: str,
        price: Decimal,
        pool: Optional[str] = None,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None
    ):
        """
        Check for arbitrage opportunities between DEX and CEX.

        Args:
            source: 'DEX' or 'CEX'
            price: Current price
            pool: DEX pool name (if source='DEX')
            symbol: CEX symbol (if source='CEX')
        """
        try:
            # Only check ETH pairs for now
            if source == 'DEX' and pool and 'ETH-USDC' in pool:
                # Compare with Binance ETH-USDT
                cex_price = self.cex_prices.get('ETH-USDT')
                if cex_price:
                    dex_price = price
                    price_diff = abs(dex_price - cex_price)
                    price_diff_pct = (price_diff / cex_price) * 100

                    if price_diff_pct >= (self.arbitrage_threshold * 100):
                        arbitrage_data = {
                            'dex_price': dex_price,
                            'cex_price': cex_price,
                            'dex_pool': pool,
                            'cex_symbol': 'ETH-USDT',
                            'price_diff': price_diff,
                            'price_diff_pct': price_diff_pct,
                            'direction': 'BUY_CEX_SELL_DEX' if cex_price < dex_price else 'BUY_DEX_SELL_CEX',
                        }

                        logger.warning(
                            f"🚨 ARBITRAGE OPPORTUNITY! | "
                            f"DEX: ${dex_price:.2f} | CEX: ${cex_price:.2f} | "
                            f"Diff: {price_diff_pct:.2f}% | "
                            f"Action: {arbitrage_data['direction']}"
                        )

                        await self._notify_arbitrage_callbacks(arbitrage_data)

            elif source == 'CEX' and symbol == 'ETH-USDT':
                # Compare with all ETH-USDC DEX pools
                for pool_name, dex_price in self.dex_prices.items():
                    if 'ETH-USDC' in pool_name:
                        cex_price = price
                        price_diff = abs(dex_price - cex_price)
                        price_diff_pct = (price_diff / cex_price) * 100

                        if price_diff_pct >= (self.arbitrage_threshold * 100):
                            arbitrage_data = {
                                'dex_price': dex_price,
                                'cex_price': cex_price,
                                'dex_pool': pool_name,
                                'cex_symbol': symbol,
                                'price_diff': price_diff,
                                'price_diff_pct': price_diff_pct,
                                'direction': 'BUY_CEX_SELL_DEX' if cex_price < dex_price else 'BUY_DEX_SELL_CEX',
                            }

                            logger.warning(
                                f"🚨 ARBITRAGE OPPORTUNITY! | "
                                f"DEX: ${dex_price:.2f} | CEX: ${cex_price:.2f} | "
                                f"Diff: {price_diff_pct:.2f}% | "
                                f"Action: {arbitrage_data['direction']}"
                            )

                            await self._notify_arbitrage_callbacks(arbitrage_data)
                            break  # Only report once per CEX update

        except Exception as e:
            logger.error(f"Error checking arbitrage: {e}")

    async def _emit_unified_price(self, price_data: Dict):
        """Emit unified price event to callbacks."""
        for callback in self.unified_price_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(price_data)
                else:
                    callback(price_data)
            except Exception as e:
                logger.error(f"Error in unified price callback: {e}")

    async def _notify_arbitrage_callbacks(self, arbitrage_data: Dict):
        """Notify all registered arbitrage callbacks."""
        for callback in self.arbitrage_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(arbitrage_data)
                else:
                    callback(arbitrage_data)
            except Exception as e:
                logger.error(f"Error in arbitrage callback: {e}")

    def on_arbitrage(self, callback: Callable):
        """
        Register callback for arbitrage opportunities.

        Args:
            callback: Function(arbitrage_data) - called when arbitrage detected
        """
        self.arbitrage_callbacks.append(callback)

    def on_price(self, callback: Callable):
        """
        Register callback for unified price updates.

        Args:
            callback: Function(price_data) - called on each price update
        """
        self.unified_price_callbacks.append(callback)

    async def start(self):
        """Start all enabled streams."""
        self._running = True

        logger.info("=" * 60)
        logger.info("🚀 Starting Market Data Manager")
        logger.info("=" * 60)

        tasks = []

        # Start Uniswap V3 stream
        if self.enable_uniswap_v3 and self.uniswap_stream:
            self.uniswap_stream.on_swap(self._handle_dex_swap)
            tasks.append(self.uniswap_stream.start())
            logger.info("✓ Uniswap V3 stream enabled")

        # Start Curve stream
        if self.enable_curve and self.curve_stream:
            self.curve_stream.on_swap(self._handle_dex_swap)
            tasks.append(self.curve_stream.start())
            logger.info("✓ Curve Finance stream enabled")

        # Start SushiSwap stream
        if self.enable_sushiswap and self.sushiswap_stream:
            self.sushiswap_stream.on_swap(self._handle_dex_swap)
            tasks.append(self.sushiswap_stream.start())
            logger.info("✓ SushiSwap stream enabled")

        # Start Balancer stream
        if self.enable_balancer and self.balancer_stream:
            self.balancer_stream.on_swap(self._handle_dex_swap)
            tasks.append(self.balancer_stream.start())
            logger.info("✓ Balancer V2 stream enabled")

        # Start Pump.fun stream
        if self.enable_pump_fun and self.pump_fun_stream:
            self.pump_fun_stream.on_launch(self._handle_pump_fun_launch)
            self.pump_fun_stream.on_trade(self._handle_pump_fun_trade)
            self.pump_fun_stream.on_graduate(self._handle_pump_fun_graduate)
            tasks.append(self.pump_fun_stream.start())
            logger.info("✓ Pump.fun stream enabled (Solana meme coin launchpad)")

        # Start Raydium stream
        if self.enable_raydium and self.raydium_stream:
            self.raydium_stream.on_swap(self._handle_raydium_swap)
            tasks.append(self.raydium_stream.start())
            logger.info("✓ Raydium stream enabled (Solana #1 DEX, 34% volume)")

        # Start Jupiter stream
        if self.enable_jupiter and self.jupiter_stream:
            self.jupiter_stream.on_swap(self._handle_jupiter_swap)
            tasks.append(self.jupiter_stream.start())
            logger.info("✓ Jupiter stream enabled (Solana DEX aggregator)")

        # Start Orca stream
        if self.enable_orca and self.orca_stream:
            self.orca_stream.on_swap(self._handle_orca_swap)
            tasks.append(self.orca_stream.start())
            logger.info("✓ Orca stream enabled (Whirlpools, 19% volume)")

        # Start Meteora stream
        if self.enable_meteora and self.meteora_stream:
            self.meteora_stream.on_swap(self._handle_meteora_swap)
            tasks.append(self.meteora_stream.start())
            logger.info("✓ Meteora stream enabled (DLMM, 22% volume)")

        # Start Binance stream
        if self.enable_binance and self.binance_stream:
            self.binance_stream.on_trade(self._handle_cex_trade)
            tasks.append(self.binance_stream.start())
            logger.info("✓ Binance stream enabled")

        if not tasks:
            logger.error("No streams enabled!")
            return

        logger.info("=" * 60)
        logger.info(f"Arbitrage threshold: {self.arbitrage_threshold * 100}%")
        logger.info("=" * 60)

        # Run all streams concurrently
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in market data manager: {e}")
            raise

    async def stop(self):
        """Stop all streams."""
        self._running = False

        # Stop Ethereum DEX streams
        if self.uniswap_stream:
            await self.uniswap_stream.stop()

        if self.curve_stream:
            await self.curve_stream.stop()

        if self.sushiswap_stream:
            await self.sushiswap_stream.stop()

        if self.balancer_stream:
            await self.balancer_stream.stop()

        # Stop Solana DEX streams
        if self.pump_fun_stream:
            await self.pump_fun_stream.stop()

        if self.raydium_stream:
            await self.raydium_stream.stop()

        if self.jupiter_stream:
            await self.jupiter_stream.stop()

        if self.orca_stream:
            await self.orca_stream.stop()

        if self.meteora_stream:
            await self.meteora_stream.stop()

        # Stop CEX streams
        if self.binance_stream:
            await self.binance_stream.stop()

        logger.info("Market Data Manager stopped")

    def get_current_prices(self) -> Dict:
        """
        Get current prices from all sources.

        Returns:
            Dict with 'dex' and 'cex' price mappings
        """
        return {
            'dex': dict(self.dex_prices),
            'cex': dict(self.cex_prices),
        }


# Example usage
async def main():
    """Example: Monitor both DEX and CEX for arbitrage."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Create manager
    manager = MarketDataManager(
        enable_uniswap_v3=True,
        enable_binance=True,
        uniswap_pools=["ETH-USDC-0.3%", "ETH-USDT-0.3%"],
        binance_symbols=["ETH-USDT"],
        arbitrage_threshold_pct=0.3,  # Alert on 0.3%+ difference
    )

    # Register arbitrage callback
    async def handle_arbitrage(data):
        """Handle arbitrage opportunities."""
        print("\n" + "=" * 60)
        print(f"🚨 ARBITRAGE ALERT!")
        print(f"DEX ({data['dex_pool']}): ${data['dex_price']:.2f}")
        print(f"CEX ({data['cex_symbol']}): ${data['cex_price']:.2f}")
        print(f"Difference: {data['price_diff_pct']:.2f}%")
        print(f"Strategy: {data['direction']}")
        print("=" * 60 + "\n")

    manager.on_arbitrage(handle_arbitrage)

    # Start manager
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
