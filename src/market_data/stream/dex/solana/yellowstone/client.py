"""
Yellowstone gRPC client for real-time Solana data streaming.

PublicNode provides FREE unlimited access to Yellowstone gRPC.
This replaces Helius Enhanced API completely - no rate limits, no costs!
"""

import asyncio
import base58
import grpc
import logging
from typing import AsyncIterator, Optional, List, Dict, Any
from dataclasses import dataclass

from .proto import geyser_pb2, geyser_pb2_grpc
from .jupiter_parser import get_jupiter_parser
from .raydium_parser import RaydiumSwapParser
from .meteora_parser import MeteoraSwapParser

logger = logging.getLogger(__name__)


@dataclass
class SwapData:
    """Parsed swap data from Yellowstone stream."""
    signature: str
    slot: int
    block_time: Optional[int]
    success: bool
    error: Optional[str]

    # Transaction accounts
    accounts: List[str]

    # Program IDs involved
    programs: List[str]

    # Account data (base58 encoded)
    account_data: Dict[str, bytes]

    # Logs
    logs: List[str]

    # Raw transaction for further parsing
    raw_transaction: bytes

    # Parsed swap details (if available)
    swap_details: Optional[Dict[str, Any]] = None


class YellowstoneClient:
    """
    Yellowstone gRPC client for real-time Solana transaction streaming.

    This provides full transaction data in real-time, completely FREE via PublicNode.
    No rate limits, no API keys, no costs - unlimited access!
    """

    def __init__(self, endpoint: str = "solana-yellowstone-grpc.publicnode.com:443", program_id: Optional[str] = None):
        """
        Initialize Yellowstone gRPC client.

        Args:
            endpoint: gRPC endpoint (default: PublicNode free unlimited)
            program_id: Program ID to use for parser selection (optional)
        """
        self.endpoint = endpoint
        self.program_id = program_id
        self.channel: Optional[grpc.aio.Channel] = None
        self.stub: Optional[geyser_pb2_grpc.GeyserStub] = None

        # Initialize parsers based on program_id
        self._init_parsers()

    def _init_parsers(self):
        """Initialize appropriate parsers based on program_id."""
        # Known Solana program IDs
        RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
        JUPITER_PROGRAM_ID = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
        METEORA_PROGRAM_ID = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"

        # Select parser based on program
        if self.program_id == RAYDIUM_PROGRAM_ID:
            self.parser = RaydiumSwapParser()
            self.parser_name = "Raydium"
        elif self.program_id == JUPITER_PROGRAM_ID:
            self.parser = get_jupiter_parser()
            self.parser_name = "Jupiter"
        elif self.program_id == METEORA_PROGRAM_ID:
            self.parser = MeteoraSwapParser()
            self.parser_name = "Meteora"
        else:
            # Default to Jupiter parser for unknown programs
            self.parser = get_jupiter_parser()
            self.parser_name = "Generic"

    async def connect(self):
        """Establish gRPC connection."""
        logger.info(f"🔌 Connecting to Yellowstone gRPC: {self.endpoint}")

        # Create SSL credentials for secure connection
        credentials = grpc.ssl_channel_credentials()

        # Create async channel with SSL
        self.channel = grpc.aio.secure_channel(
            self.endpoint,
            credentials,
            options=[
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
                ('grpc.max_send_message_length', 100 * 1024 * 1024),
            ]
        )

        self.stub = geyser_pb2_grpc.GeyserStub(self.channel)
        logger.info("✅ Connected to Yellowstone gRPC")

    async def close(self):
        """Close gRPC connection."""
        if self.channel:
            await self.channel.close()
            logger.info("🔌 Closed Yellowstone gRPC connection")

    async def ping(self) -> Dict[str, Any]:
        """Test connection with ping."""
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first.")

        request = geyser_pb2.PingRequest(count=1)
        response = await self.stub.Ping(request)

        return {
            "count": response.count
        }

    async def subscribe_to_program(
        self,
        program_ids: List[str],
        commitment: str = "confirmed"
    ) -> AsyncIterator[SwapData]:
        """
        Subscribe to transactions for specific program IDs.

        This is the KEY method - it streams ALL transactions that interact with
        the specified programs in REAL-TIME with FULL parsed data.

        Args:
            program_ids: List of program public keys (e.g., Jupiter, Raydium, etc.)
            commitment: Commitment level (processed, confirmed, finalized)

        Yields:
            SwapData objects with full transaction details
        """
        if not self.stub:
            raise RuntimeError("Not connected. Call connect() first.")

        logger.info(f"📡 Subscribing to programs: {program_ids} ({commitment})")

        # Build subscription request
        # We want to subscribe to transactions that mention these program IDs
        transactions_filter = {}

        for program_id in program_ids:
            # Subscribe to all transactions mentioning this program
            transactions_filter[f"program_{program_id}"] = geyser_pb2.SubscribeRequestFilterTransactions(
                vote=False,  # Exclude vote transactions
                failed=False,  # Exclude failed transactions
                account_include=[program_id],  # Include txs that mention this program
            )

        # Create subscription request
        request = geyser_pb2.SubscribeRequest(
            transactions=transactions_filter,
            commitment=self._get_commitment_level(commitment),
        )

        # Create async generator to send requests
        async def request_generator():
            yield request
            # Keep connection alive
            while True:
                await asyncio.sleep(30)  # Send keepalive every 30s

        try:
            # Subscribe and stream responses
            response_stream = self.stub.Subscribe(request_generator())

            async for update in response_stream:
                # Process transaction updates
                if update.HasField("transaction"):
                    tx_update = update.transaction

                    # Parse transaction data
                    swap_data = self._parse_transaction(tx_update)
                    if swap_data:
                        yield swap_data

        except grpc.aio.AioRpcError as e:
            logger.error(f"❌ gRPC error: {e.code()} - {e.details()}")
            raise
        except Exception as e:
            logger.error(f"❌ Subscription error: {e}")
            raise

    def _parse_transaction(self, tx_update) -> Optional[SwapData]:
        """
        Parse transaction update from Yellowstone.

        This extracts all the juicy data we need for trading!
        """
        try:
            # Get the transaction field
            if not tx_update.HasField("transaction"):
                return None

            tx_info = tx_update.transaction

            # Get transaction and metadata
            if not tx_info.HasField("transaction"):
                return None

            tx = tx_info.transaction
            meta = tx_info.meta if tx_info.HasField("meta") else None

            # Get signature (first signature in the list)
            if not tx.signatures or len(tx.signatures) == 0:
                return None
            signature = base58.b58encode(bytes(tx.signatures[0])).decode('utf-8')

            # Get slot (from the update, not tx_info)
            slot = tx_update.slot if hasattr(tx_update, 'slot') else 0

            # Check if transaction succeeded
            success = True
            error = None
            if meta and meta.HasField("err"):
                success = False
                error = str(meta.err)

            # Get accounts
            accounts = []
            if tx.HasField("message"):
                msg = tx.message
                if hasattr(msg, 'account_keys'):
                    for account_key in msg.account_keys:
                        accounts.append(base58.b58encode(bytes(account_key)).decode('utf-8'))

            # Get program IDs (all programs invoked)
            programs = []
            if tx.HasField("message") and hasattr(tx.message, 'instructions'):
                for ix in tx.message.instructions:
                    if hasattr(ix, 'program_id_index') and ix.program_id_index < len(accounts):
                        programs.append(accounts[ix.program_id_index])

            # Get logs
            logs = []
            if meta and hasattr(meta, 'log_messages'):
                logs = list(meta.log_messages)

            # Get block time
            block_time = None
            if meta and hasattr(meta, 'block_time'):
                block_time = meta.block_time

            # Parse swap details from logs using selected parser
            swap_details = self.parser.parse_swap_from_logs(logs, accounts)

            # Create SwapData
            swap_data = SwapData(
                signature=signature,
                slot=slot,
                block_time=block_time,
                success=success,
                error=error,
                accounts=accounts,
                programs=programs,
                account_data={},  # Will be populated if needed
                logs=logs,
                raw_transaction=tx.SerializeToString(),
                swap_details=swap_details,
            )

            return swap_data

        except Exception as e:
            logger.error(f"❌ Error parsing transaction: {e}", exc_info=True)
            return None

    def _get_commitment_level(self, commitment: str) -> int:
        """Convert commitment string to geyser enum."""
        commitment_map = {
            "processed": 0,
            "confirmed": 1,
            "finalized": 2,
        }
        return commitment_map.get(commitment.lower(), 1)  # Default to confirmed


async def example_usage():
    """Example of using Yellowstone client."""

    # Jupiter program ID
    JUPITER_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"

    # Create client
    client = YellowstoneClient()

    try:
        # Connect
        await client.connect()

        # Test ping
        pong = await client.ping()
        print(f"✅ Ping successful: {pong}")

        # Subscribe to Jupiter swaps
        print(f"\n📡 Subscribing to Jupiter swaps...")

        async for swap in client.subscribe_to_program([JUPITER_PROGRAM]):
            print(f"\n🔄 Jupiter Swap:")
            print(f"  Signature: {swap.signature}")
            print(f"  Slot: {swap.slot}")
            print(f"  Success: {swap.success}")
            print(f"  Accounts: {len(swap.accounts)}")
            print(f"  Programs: {swap.programs}")
            print(f"  Logs: {len(swap.logs)}")

            # Print first few logs
            for i, log in enumerate(swap.logs[:3]):
                print(f"    [{i+1}] {log}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
