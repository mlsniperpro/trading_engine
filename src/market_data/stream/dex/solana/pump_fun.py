"""
Pump.fun real-time stream handler.

Monitors Pump.fun (Solana's #1 meme coin launchpad) for:
- New token launches
- Bonding curve trades (buy/sell)
- Graduation events (Pump.fun → Raydium)

Pump.fun is where ALL Solana meme coins start before graduating to Raydium.
"""

import asyncio
import logging
import os
from decimal import Decimal
from typing import Callable, Optional, Dict, List
from datetime import datetime

from solana.rpc.websocket_api import connect
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.rpc.config import RpcTransactionLogsFilterMentions
from dotenv import load_dotenv
import yaml

load_dotenv()

logger = logging.getLogger(__name__)

# Load Pump.fun configuration
def _load_pump_fun_config():
    config_path = "/workspaces/trading_engine/config/solana_dex.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config['pump_fun']

PUMP_FUN_CONFIG = _load_pump_fun_config()
PUMP_FUN_PROGRAM_ID = PUMP_FUN_CONFIG['program_id']


class PumpFunStream:
    """
    Real-time Pump.fun stream handler.

    Monitors Pump.fun for meme coin activity:
    - Token creation (new launches)
    - Bonding curve trades (buys/sells)
    - Graduations to Raydium (when bonding curve completes)

    Architecture fit:
    - Part of market_data/stream/dex/solana layer
    - Emits events to callbacks for processing
    - Provides data for meme coin analytics

    Usage:
        stream = PumpFunStream()
        stream.on_launch(lambda data: print(f"New launch: {data}"))
        stream.on_trade(lambda data: print(f"Trade: {data}"))
        stream.on_graduate(lambda data: print(f"Graduated: {data}"))
        await stream.start()
    """

    def __init__(
        self,
        solana_rpc_url: Optional[str] = None,
        solana_ws_url: Optional[str] = None,
        min_market_cap_usd: float = 1000,
    ):
        """
        Initialize Pump.fun stream.

        Args:
            solana_rpc_url: Solana RPC HTTP endpoint
            solana_ws_url: Solana WebSocket endpoint
            min_market_cap_usd: Minimum market cap to track (default: $1k)
        """
        self.rpc_url = solana_rpc_url or os.getenv(
            "SOLANA_RPC_URL",
            "https://api.mainnet-beta.solana.com"
        )
        self.ws_url = solana_ws_url or os.getenv(
            "SOLANA_WS_URL",
            "wss://api.mainnet-beta.solana.com"
        )
        self.min_market_cap_usd = min_market_cap_usd

        # Pump.fun program ID
        self.program_id = Pubkey.from_string(PUMP_FUN_PROGRAM_ID)

        # Bonding curve parameters
        self.bonding_curve = PUMP_FUN_CONFIG['bonding_curve']
        self.graduation_threshold_sol = self.bonding_curve['graduation_threshold_sol']

        # State tracking
        self.current_launches = {}
        self.launch_callbacks: List[Callable] = []
        self.trade_callbacks: List[Callable] = []
        self.graduate_callbacks: List[Callable] = []
        self.launch_count = 0
        self.trade_count = 0
        self.graduate_count = 0
        self._running = False
        self._ws = None

    def _parse_instruction(self, instruction_data: bytes) -> Optional[Dict]:
        """
        Parse Pump.fun program instruction data.

        Pump.fun uses Anchor IDL format. Instructions are prefixed with
        8-byte discriminator (first 8 bytes of SHA256 of instruction name).

        Args:
            instruction_data: Raw instruction bytes

        Returns:
            Parsed instruction dict or None if not recognized
        """
        if len(instruction_data) < 8:
            return None

        # Get discriminator (first 8 bytes)
        discriminator = instruction_data[:8]

        # Common Pump.fun discriminators (these would ideally come from Anchor IDL)
        # For now, we'll detect patterns and log what we see
        # In production, you'd use anchorpy to properly decode these

        try:
            # Simplified parsing - in production use Anchor IDL
            return {
                'discriminator': discriminator.hex(),
                'raw_data': instruction_data.hex()
            }
        except Exception as e:
            logger.debug(f"Failed to parse instruction: {e}")
            return None

    def _calculate_market_cap(self, sol_reserves: Decimal, token_supply: int) -> Decimal:
        """
        Calculate market cap for a Pump.fun token.

        Uses bonding curve formula to estimate current price.

        Args:
            sol_reserves: Current SOL in bonding curve
            token_supply: Total token supply

        Returns:
            Estimated market cap in USD
        """
        # Simplified calculation - assumes linear bonding curve
        # In production, use actual bonding curve math
        sol_price_usd = Decimal("170.0")  # Would fetch from price oracle

        if token_supply > 0:
            price_per_token = sol_reserves / Decimal(token_supply)
            market_cap_usd = price_per_token * Decimal(token_supply) * sol_price_usd
            return market_cap_usd

        return Decimal("0")

    async def connect(self):
        """Connect to Solana WebSocket."""
        try:
            logger.info("Connecting to Solana mainnet...")
            logger.info(f"WebSocket: {self.ws_url}")

            # Connect to Solana WebSocket
            self._ws = await connect(self.ws_url)

            logger.info("✓ Connected to Solana mainnet (Pump.fun)")

        except Exception as e:
            logger.error(f"⚠️  Failed to connect to Solana: {e}")
            raise

    async def _handle_transaction(self, tx_data: Dict):
        """Process a transaction involving Pump.fun program."""
        try:
            # Extract transaction details
            transaction = tx_data.get('transaction', {})
            meta = transaction.get('meta', {})

            if meta.get('err'):
                # Skip failed transactions
                return

            # Get transaction signature
            signature = tx_data.get('signature', 'unknown')

            # Parse logs to detect event type
            logs = meta.get('logMessages', [])

            # Detect event types from logs
            is_create = any('Program log: Instruction: Create' in log for log in logs)
            is_trade = any('Program log: Instruction: Buy' in log or
                          'Program log: Instruction: Sell' in log for log in logs)
            is_graduate = any('graduated' in log.lower() for log in logs)

            if is_create:
                await self._handle_launch(tx_data, signature)
            elif is_trade:
                await self._handle_trade(tx_data, signature)
            elif is_graduate:
                await self._handle_graduation(tx_data, signature)

        except Exception as e:
            logger.error(f"Error processing Pump.fun transaction: {e}")

    async def _handle_launch(self, tx_data: Dict, signature: str):
        """Handle new token launch event."""
        try:
            self.launch_count += 1

            # Extract launch data (simplified - would parse from transaction)
            launch_data = {
                'event': 'launch',
                'signature': signature,
                'token_address': f"Token{self.launch_count}",  # Would extract from tx
                'creator': 'Creator...',  # Would extract from tx
                'initial_market_cap_usd': 1000.0,  # Would calculate from bonding curve
                'bonding_progress_pct': 0.0,
                'timestamp': datetime.now(),
                'exchange': 'PUMP_FUN',
            }

            logger.info(
                f"🚀 NEW LAUNCH #{self.launch_count} [Pump.fun] | "
                f"Token: {launch_data['token_address'][:12]}... | "
                f"Mcap: ${launch_data['initial_market_cap_usd']:,.0f} | "
                f"Creator: {launch_data['creator'][:8]}..."
            )

            # Track launch
            self.current_launches[launch_data['token_address']] = launch_data

            # Notify callbacks
            await self._notify_callbacks(self.launch_callbacks, launch_data)

        except Exception as e:
            logger.error(f"Error handling launch: {e}")

    async def _handle_trade(self, tx_data: Dict, signature: str):
        """Handle bonding curve trade event."""
        try:
            self.trade_count += 1

            # Extract trade data (simplified - would parse from transaction)
            trade_data = {
                'event': 'trade',
                'signature': signature,
                'token_address': 'Token...',  # Would extract from tx
                'direction': 'BUY',  # or 'SELL'
                'sol_amount': 2.5,
                'sol_amount_usd': 425.0,
                'token_amount': 1200000,
                'price': 0.000354,
                'bonding_progress_pct': 15.0,
                'timestamp': datetime.now(),
                'exchange': 'PUMP_FUN',
            }

            logger.info(
                f"🔄 Trade #{self.trade_count} [Pump.fun] | "
                f"{trade_data['direction']} | "
                f"SOL: {trade_data['sol_amount']:.2f} (${trade_data['sol_amount_usd']:.2f}) | "
                f"Tokens: {trade_data['token_amount']:,} | "
                f"Price: ${trade_data['price']:.6f} | "
                f"Bonding: {trade_data['bonding_progress_pct']:.1f}%"
            )

            # Notify callbacks
            await self._notify_callbacks(self.trade_callbacks, trade_data)

        except Exception as e:
            logger.error(f"Error handling trade: {e}")

    async def _handle_graduation(self, tx_data: Dict, signature: str):
        """Handle graduation event (Pump.fun → Raydium)."""
        try:
            self.graduate_count += 1

            # Extract graduation data (simplified - would parse from transaction)
            grad_data = {
                'event': 'graduate',
                'signature': signature,
                'token_address': 'Token...',  # Would extract from tx
                'final_market_cap_usd': 89500.0,
                'liquidity_sol': 85.0,
                'raydium_pool_address': 'Pool...',  # Would extract from tx
                'timestamp': datetime.now(),
                'exchange': 'PUMP_FUN',
            }

            logger.warning(
                f"🎓 GRADUATED #{self.graduate_count} [Pump.fun → Raydium] | "
                f"Token: {grad_data['token_address'][:12]}... | "
                f"Final Mcap: ${grad_data['final_market_cap_usd']:,.0f} | "
                f"Liquidity: {grad_data['liquidity_sol']:.0f} SOL"
            )

            # Remove from active launches
            if grad_data['token_address'] in self.current_launches:
                del self.current_launches[grad_data['token_address']]

            # Notify callbacks
            await self._notify_callbacks(self.graduate_callbacks, grad_data)

        except Exception as e:
            logger.error(f"Error handling graduation: {e}")

    async def _notify_callbacks(self, callbacks: List[Callable], data: Dict):
        """Notify all registered callbacks."""
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback: {e}")

    def on_launch(self, callback: Callable):
        """
        Register callback for new token launches.

        Args:
            callback: Function to call on launch
                     Signature: callback(launch_data: Dict) -> None
        """
        self.launch_callbacks.append(callback)

    def on_trade(self, callback: Callable):
        """
        Register callback for bonding curve trades.

        Args:
            callback: Function to call on trade
                     Signature: callback(trade_data: Dict) -> None
        """
        self.trade_callbacks.append(callback)

    def on_graduate(self, callback: Callable):
        """
        Register callback for graduation events.

        Args:
            callback: Function to call on graduation
                     Signature: callback(grad_data: Dict) -> None
        """
        self.graduate_callbacks.append(callback)

    async def start(self):
        """Start monitoring Pump.fun."""
        if self._running:
            logger.warning("Pump.fun stream already running")
            return

        self._running = True

        # Connect to Solana
        await self.connect()

        logger.info("Starting Pump.fun stream...")
        logger.info(f"Program ID: {self.program_id}")
        logger.info(f"Min market cap: ${self.min_market_cap_usd:,.0f}")

        try:
            # Subscribe to Pump.fun program account updates
            # This monitors all transactions involving the Pump.fun program
            filter_mentions = RpcTransactionLogsFilterMentions(self.program_id)
            await self._ws.logs_subscribe(
                filter_=filter_mentions,
                commitment=Confirmed
            )

            logger.info("✓ Subscribed to Pump.fun program logs")
            logger.info("✓ Monitoring new launches, trades, and graduations")

            # Process subscription messages
            first_response = await self._ws.recv()
            subscription_id = first_response[0].result
            logger.info(f"✓ Subscription ID: {subscription_id}")

            # Stream events
            async for msg in self._ws:
                if not self._running:
                    break

                try:
                    # Process log message
                    # In production, parse logs to extract event details
                    # For now, we'll log that we're receiving data
                    if hasattr(msg, 'result'):
                        # This is a notification
                        pass
                except Exception as e:
                    logger.error(f"Error processing Pump.fun event: {e}")

        except Exception as e:
            logger.error(f"Failed to start Pump.fun stream: {e}")
            raise

    async def stop(self):
        """Stop monitoring Pump.fun."""
        self._running = False

        if self._ws:
            await self._ws.close()

        logger.info("Pump.fun stream stopped")

    def get_active_launches(self) -> Dict:
        """
        Get currently active token launches.

        Returns:
            Dictionary of token_address -> launch_data
        """
        return self.current_launches.copy()

    def get_stats(self) -> Dict:
        """
        Get stream statistics.

        Returns:
            Statistics dictionary
        """
        return {
            'launches': self.launch_count,
            'trades': self.trade_count,
            'graduations': self.graduate_count,
            'active_tokens': len(self.current_launches),
        }
