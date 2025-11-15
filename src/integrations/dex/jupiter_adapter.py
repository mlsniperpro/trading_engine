"""
Jupiter Aggregator Adapter (Solana)

Integration with Jupiter DEX aggregator for Solana:
- Route optimization across Solana DEXes
- Best price discovery
- Slippage protection
- Multi-hop routing

Jupiter is the primary DEX aggregator for Solana ecosystem.
"""

try:
    import aiohttp
except ImportError:
    print("Warning: aiohttp not installed. HTTP requests will be simulated.")
    aiohttp = None
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from src.integrations.dex.aggregator_adapter import AggregatorAdapter, RouteQuote, SwapResult


@dataclass
class JupiterRoute:
    """Jupiter-specific route data."""
    input_mint: str
    output_mint: str
    amount: int
    slippage_bps: int
    platform_fee_bps: int
    price_impact_pct: float
    market_infos: List[Dict[str, Any]]
    other_amount_threshold: int


class JupiterAdapter(AggregatorAdapter):
    """
    Jupiter DEX aggregator adapter for Solana.
    
    Features:
    - Multi-DEX route optimization
    - Real-time price quotes
    - Slippage protection
    - Transaction building
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("Jupiter", "Solana")
        self.api_key = api_key
        
        # Jupiter API endpoints
        self.base_url = "https://quote-api.jup.ag/v6"
        self.swap_url = "https://quote-api.jup.ag/v6/swap"
        
        # Request session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Token configuration
        self.supported_tokens = {}
        self.token_list_url = "https://token.jup.ag/strict"
        
        # Rate limiting
        self.requests_per_second = 10
        self.last_request_time = 0.0
        
        self.logger.info("Jupiter adapter initialized")
    
    async def initialize(self) -> bool:
        """Initialize the Jupiter adapter."""
        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Load supported tokens
            await self._load_token_list()
            
            # Test API connectivity
            test_result = await self._test_connection()
            
            if test_result:
                self.is_initialized = True
                self.logger.info("Jupiter adapter initialized successfully")
            else:
                self.logger.error("Jupiter adapter initialization failed")
            
            return test_result
            
        except Exception as e:
            self.logger.error(f"Error initializing Jupiter adapter: {e}")
            return False
    
    async def _load_token_list(self):
        """Load Jupiter's supported token list."""
        try:
            if not self.session:
                return
            
            async with self.session.get(self.token_list_url) as response:
                if response.status == 200:
                    tokens = await response.json()
                    
                    for token in tokens:
                        symbol = token.get('symbol', '')
                        address = token.get('address', '')
                        
                        if symbol and address:
                            self.supported_tokens[symbol.upper()] = {
                                'address': address,
                                'name': token.get('name', ''),
                                'decimals': token.get('decimals', 9),
                                'logoURI': token.get('logoURI', ''),
                                'verified': token.get('verified', False)
                            }
                    
                    self.logger.info(f"Loaded {len(self.supported_tokens)} Jupiter tokens")
                else:
                    self.logger.warning(f"Failed to load Jupiter token list: {response.status}")
                    
        except Exception as e:
            self.logger.error(f"Error loading Jupiter token list: {e}")
    
    async def _test_connection(self) -> bool:
        """Test connection to Jupiter API."""
        try:
            if not self.session:
                return False
            
            # Test with a simple quote request
            params = {
                'inputMint': 'So11111111111111111111111111111111111111112',  # SOL
                'outputMint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
                'amount': '1000000',  # 0.001 SOL (6 decimals)
                'slippageBps': '50'  # 0.5%
            }
            
            async with self.session.get(f"{self.base_url}/quote", params=params) as response:
                return response.status == 200
                
        except Exception as e:
            self.logger.error(f"Jupiter connection test failed: {e}")
            return False
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount_in: float,
                       slippage_bps: int = 50) -> Optional[RouteQuote]:
        """Get quote from Jupiter aggregator."""
        try:
            await self._rate_limit()
            
            # Get token addresses
            token_in_addr = self._get_token_address(token_in)
            token_out_addr = self._get_token_address(token_out)
            
            if not token_in_addr or not token_out_addr:
                self.logger.error(f"Token addresses not found: {token_in} -> {token_out}")
                return None
            
            # Convert amount to token units
            amount_units = self._amount_to_units(amount_in, token_in)
            
            # Build request parameters
            params = {
                'inputMint': token_in_addr,
                'outputMint': token_out_addr,
                'amount': str(amount_units),
                'slippageBps': str(slippage_bps),
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }
            
            if not self.session:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/quote", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_jupiter_quote(data, token_in, token_out, amount_in)
                else:
                    error_text = await response.text()
                    self.logger.error(f"Jupiter quote failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error getting Jupiter quote: {e}")
            return None
    
    def _parse_jupiter_quote(self, 
                           data: Dict[str, Any], 
                           token_in: str, 
                           token_out: str,
                           amount_in: float) -> RouteQuote:
        """Parse Jupiter API response into RouteQuote."""
        try:
            # Extract output amount
            out_amount_units = int(data.get('outAmount', 0))
            amount_out = self._units_to_amount(out_amount_units, token_out)
            
            # Calculate price impact
            price_impact_pct = float(data.get('priceImpactPct', 0))
            
            # Extract route information
            route_plan = data.get('routePlan', [])
            dexes_used = []
            for step in route_plan:
                swap_info = step.get('swapInfo', {})
                amm_key = swap_info.get('ammKey', '')
                if amm_key:
                    # Map AMM keys to readable names
                    dex_name = self._map_amm_to_dex(amm_key)
                    if dex_name not in dexes_used:
                        dexes_used.append(dex_name)
            
            # Calculate fees (Jupiter typically charges 0.1% platform fee)
            platform_fee_bps = data.get('platformFee', {}).get('feeBps', 0)
            estimated_fee = amount_in * (platform_fee_bps / 10000)
            
            # Build metadata
            metadata = {
                'route_plan': route_plan,
                'price_impact_pct': price_impact_pct,
                'platform_fee_bps': platform_fee_bps,
                'market_infos': data.get('contextSlot', 0),
                'swap_mode': data.get('swapMode', 'ExactIn'),
                'jupiter_quote_data': data  # Store full data for swap execution
            }
            
            return RouteQuote(
                aggregator="Jupiter",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=price_impact_pct,
                estimated_gas=85000,  # Typical Solana transaction cost
                dexes_used=dexes_used,
                route_description=f"Via {' -> '.join(dexes_used)}",
                estimated_fee=estimated_fee,
                metadata=metadata,
                valid_until=datetime.now().timestamp() + 30  # 30 seconds validity
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing Jupiter quote: {e}")
            raise
    
    async def execute_swap(self, quote: RouteQuote, user_wallet: str) -> Optional[SwapResult]:
        """Execute swap using Jupiter."""
        try:
            await self._rate_limit()
            
            # Get original Jupiter quote data
            jupiter_data = quote.metadata.get('jupiter_quote_data')
            if not jupiter_data:
                self.logger.error("Missing Jupiter quote data for swap execution")
                return None
            
            # Build swap request
            swap_request = {
                'quoteResponse': jupiter_data,
                'userPublicKey': user_wallet,
                'wrapAndUnwrapSol': True,
                'dynamicComputeUnitLimit': True,
                'prioritizationFeeLamports': 'auto'
            }
            
            if not self.session:
                await self.initialize()
            
            # Request swap transaction
            async with self.session.post(
                f"{self.base_url}/swap",
                json=swap_request,
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status == 200:
                    swap_data = await response.json()
                    
                    return SwapResult(
                        success=True,
                        transaction_hash="",  # Will be set after broadcast
                        amount_out=quote.amount_out,
                        gas_used=85000,  # Estimated
                        actual_price_impact=quote.price_impact,
                        metadata={
                            'swap_transaction': swap_data.get('swapTransaction'),
                            'last_valid_block_height': swap_data.get('lastValidBlockHeight'),
                            'prioritization_fee_lamports': swap_data.get('prioritizationFeeLamports'),
                            'compute_unit_limit': swap_data.get('computeUnitLimit')
                        }
                    )
                else:
                    error_text = await response.text()
                    self.logger.error(f"Jupiter swap failed: {response.status} - {error_text}")
                    
                    return SwapResult(
                        success=False,
                        error=f"Swap failed: {error_text}",
                        amount_out=0.0,
                        gas_used=0,
                        actual_price_impact=0.0
                    )
                    
        except Exception as e:
            self.logger.error(f"Error executing Jupiter swap: {e}")
            return SwapResult(
                success=False,
                error=str(e),
                amount_out=0.0,
                gas_used=0,
                actual_price_impact=0.0
            )
    
    def _get_token_address(self, token_symbol: str) -> Optional[str]:
        """Get token contract address from symbol."""
        token_info = self.supported_tokens.get(token_symbol.upper())
        return token_info['address'] if token_info else None
    
    def _amount_to_units(self, amount: float, token_symbol: str) -> int:
        """Convert human-readable amount to token units."""
        token_info = self.supported_tokens.get(token_symbol.upper())
        decimals = token_info['decimals'] if token_info else 9  # Default to 9 for Solana
        return int(amount * (10 ** decimals))
    
    def _units_to_amount(self, units: int, token_symbol: str) -> float:
        """Convert token units to human-readable amount."""
        token_info = self.supported_tokens.get(token_symbol.upper())
        decimals = token_info['decimals'] if token_info else 9
        return units / (10 ** decimals)
    
    def _map_amm_to_dex(self, amm_key: str) -> str:
        """Map AMM key to human-readable DEX name."""
        # Common Solana DEX mappings
        amm_mappings = {
            'CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK': 'Orca',
            '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8': 'Raydium',
            '9W959DqEETiGZocYWisQQ4S71jqjmBhgPH5PJgA2GXeK': 'Mercurial',
            '5fNfvyp5czQVX77yoACa3JJVEhdRaWjPuazuWgjhTqEH': 'Serum',
            'AmkgJLCCFMoN2UyxQWzfnAE7kuvLc1uP6MH1QeSGt5SJ': 'Aldrin'
        }
        
        return amm_mappings.get(amm_key, f"AMM_{amm_key[:8]}")
    
    async def _rate_limit(self):
        """Implement rate limiting."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def get_supported_tokens(self) -> List[str]:
        """Get list of supported token symbols."""
        return list(self.supported_tokens.keys())
    
    def is_token_supported(self, token_symbol: str) -> bool:
        """Check if token is supported."""
        return token_symbol.upper() in self.supported_tokens
    
    async def get_token_info(self, token_symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed token information."""
        return self.supported_tokens.get(token_symbol.upper())
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.logger.info("Jupiter adapter cleanup completed")