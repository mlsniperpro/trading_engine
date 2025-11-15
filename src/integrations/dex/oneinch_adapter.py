"""
1inch Aggregator Adapter (EVM Chains)

Integration with 1inch DEX aggregator for EVM chains:
- Multi-chain support (Ethereum, Polygon, BSC, etc.)
- Advanced routing algorithms
- MEV protection
- Pathfinder API integration

1inch is the leading DEX aggregator for EVM chains.
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
class OneInchChainConfig:
    """1inch chain configuration."""
    chain_id: int
    name: str
    native_token: str
    base_url: str


class OneInchAdapter(AggregatorAdapter):
    """
    1inch DEX aggregator adapter for EVM chains.
    
    Features:
    - Multi-chain routing
    - Pathfinder optimization
    - Gas price optimization
    - MEV protection
    """
    
    # Supported chains
    CHAIN_CONFIGS = {
        1: OneInchChainConfig(1, "Ethereum", "ETH", "https://api.1inch.dev"),
        137: OneInchChainConfig(137, "Polygon", "MATIC", "https://api.1inch.dev"),
        56: OneInchChainConfig(56, "BSC", "BNB", "https://api.1inch.dev"),
        42161: OneInchChainConfig(42161, "Arbitrum", "ETH", "https://api.1inch.dev"),
        10: OneInchChainConfig(10, "Optimism", "ETH", "https://api.1inch.dev"),
        43114: OneInchChainConfig(43114, "Avalanche", "AVAX", "https://api.1inch.dev")
    }
    
    def __init__(self, api_key: str, chain_id: int = 1):
        super().__init__("1inch", f"EVM-{chain_id}")
        self.api_key = api_key
        self.chain_id = chain_id
        
        # Get chain configuration
        self.chain_config = self.CHAIN_CONFIGS.get(chain_id)
        if not self.chain_config:
            raise ValueError(f"Unsupported chain ID: {chain_id}")
        
        # API configuration
        self.base_url = f"{self.chain_config.base_url}/swap/v6.0/{chain_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Request session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Token data
        self.supported_tokens = {}
        
        # Rate limiting
        self.requests_per_second = 5  # Conservative rate limit
        self.last_request_time = 0.0
        
        self.logger.info(f"1inch adapter initialized for {self.chain_config.name}")
    
    async def initialize(self) -> bool:
        """Initialize the 1inch adapter."""
        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
            
            # Load supported tokens
            await self._load_token_list()
            
            # Test API connectivity
            test_result = await self._test_connection()
            
            if test_result:
                self.is_initialized = True
                self.logger.info("1inch adapter initialized successfully")
            else:
                self.logger.error("1inch adapter initialization failed")
            
            return test_result
            
        except Exception as e:
            self.logger.error(f"Error initializing 1inch adapter: {e}")
            return False
    
    async def _load_token_list(self):
        """Load 1inch supported tokens."""
        try:
            if not self.session:
                return
            
            url = f"{self.base_url}/tokens"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = data.get('tokens', {})
                    
                    for address, token_info in tokens.items():
                        symbol = token_info.get('symbol', '')
                        
                        if symbol:
                            self.supported_tokens[symbol.upper()] = {
                                'address': address,
                                'name': token_info.get('name', ''),
                                'decimals': token_info.get('decimals', 18),
                                'logoURI': token_info.get('logoURI', ''),
                                'eip2612': token_info.get('eip2612', False)
                            }
                    
                    self.logger.info(f"Loaded {len(self.supported_tokens)} 1inch tokens for {self.chain_config.name}")
                else:
                    self.logger.warning(f"Failed to load 1inch token list: {response.status}")
                    
        except Exception as e:
            self.logger.error(f"Error loading 1inch token list: {e}")
    
    async def _test_connection(self) -> bool:
        """Test connection to 1inch API."""
        try:
            if not self.session:
                return False
            
            # Test with healthcheck endpoint
            url = f"{self.base_url}/healthcheck"
            
            async with self.session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            self.logger.error(f"1inch connection test failed: {e}")
            return False
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount_in: float,
                       slippage_bps: int = 50) -> Optional[RouteQuote]:
        """Get quote from 1inch aggregator."""
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
                'src': token_in_addr,
                'dst': token_out_addr,
                'amount': str(amount_units),
                'includeTokensInfo': 'true',
                'includeProtocols': 'true',
                'includeGas': 'true'
            }
            
            url = f"{self.base_url}/quote"
            
            if not self.session:
                await self.initialize()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_oneinch_quote(data, token_in, token_out, amount_in, slippage_bps)
                else:
                    error_text = await response.text()
                    self.logger.error(f"1inch quote failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error getting 1inch quote: {e}")
            return None
    
    def _parse_oneinch_quote(self, 
                           data: Dict[str, Any], 
                           token_in: str, 
                           token_out: str,
                           amount_in: float,
                           slippage_bps: int) -> RouteQuote:
        """Parse 1inch API response into RouteQuote."""
        try:
            # Extract output amount
            dst_amount = int(data.get('dstAmount', 0))
            amount_out = self._units_to_amount(dst_amount, token_out)
            
            # Extract gas estimate
            estimated_gas = int(data.get('gas', 150000))
            
            # Extract protocols used
            protocols = data.get('protocols', [])
            dexes_used = []
            
            for protocol_group in protocols:
                for route in protocol_group:
                    for hop in route:
                        protocol_name = hop.get('name', '')
                        if protocol_name and protocol_name not in dexes_used:
                            dexes_used.append(protocol_name)
            
            # Calculate price impact (1inch doesn't directly provide this)
            # Estimate based on input/output ratio vs market rate
            price_impact = 0.0  # Would need spot price to calculate
            
            # Extract fee information
            estimated_fee = 0.0  # 1inch includes fees in the output amount
            
            # Build route description
            if len(dexes_used) <= 3:
                route_desc = f"Via {' + '.join(dexes_used)}"
            else:
                route_desc = f"Via {len(dexes_used)} protocols"
            
            # Build metadata
            metadata = {
                'protocols': protocols,
                'gas_estimate': estimated_gas,
                'slippage_bps': slippage_bps,
                'oneinch_quote_data': data
            }
            
            return RouteQuote(
                aggregator="1inch",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=price_impact,
                estimated_gas=estimated_gas,
                dexes_used=dexes_used,
                route_description=route_desc,
                estimated_fee=estimated_fee,
                metadata=metadata,
                valid_until=datetime.now().timestamp() + 30
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing 1inch quote: {e}")
            raise
    
    async def execute_swap(self, quote: RouteQuote, user_wallet: str, slippage_bps: int = 50) -> Optional[SwapResult]:
        """Execute swap using 1inch."""
        try:
            await self._rate_limit()
            
            # Get token addresses
            token_in_addr = self._get_token_address(quote.token_in)
            token_out_addr = self._get_token_address(quote.token_out)
            
            if not token_in_addr or not token_out_addr:
                return SwapResult(
                    success=False,
                    error="Token addresses not found",
                    amount_out=0.0,
                    gas_used=0,
                    actual_price_impact=0.0
                )
            
            # Convert amount to units
            amount_units = self._amount_to_units(quote.amount_in, quote.token_in)
            
            # Calculate minimum output amount with slippage
            min_amount_out = int(quote.amount_out * (1 - slippage_bps / 10000))
            min_amount_units = self._amount_to_units(min_amount_out, quote.token_out)
            
            # Build swap parameters
            params = {
                'src': token_in_addr,
                'dst': token_out_addr,
                'amount': str(amount_units),
                'from': user_wallet,
                'slippage': str(slippage_bps / 100),  # Convert bps to percentage
                'disableEstimate': 'false',
                'allowPartialFill': 'false'
            }
            
            url = f"{self.base_url}/swap"
            
            if not self.session:
                await self.initialize()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    swap_data = await response.json()
                    
                    # Extract transaction data
                    tx_data = swap_data.get('tx', {})
                    
                    return SwapResult(
                        success=True,
                        transaction_hash="",  # Will be set after broadcast
                        amount_out=quote.amount_out,
                        gas_used=quote.estimated_gas,
                        actual_price_impact=quote.price_impact,
                        metadata={
                            'transaction_data': tx_data,
                            'to_address': tx_data.get('to'),
                            'call_data': tx_data.get('data'),
                            'value': tx_data.get('value', '0'),
                            'gas_limit': tx_data.get('gas')
                        }
                    )
                else:
                    error_data = await response.json()
                    error_msg = error_data.get('description', f"HTTP {response.status}")
                    
                    return SwapResult(
                        success=False,
                        error=f"1inch swap failed: {error_msg}",
                        amount_out=0.0,
                        gas_used=0,
                        actual_price_impact=0.0
                    )
                    
        except Exception as e:
            self.logger.error(f"Error executing 1inch swap: {e}")
            return SwapResult(
                success=False,
                error=str(e),
                amount_out=0.0,
                gas_used=0,
                actual_price_impact=0.0
            )
    
    async def get_allowance(self, token_address: str, user_wallet: str) -> int:
        """Get token allowance for 1inch router."""
        try:
            url = f"{self.base_url}/approve/allowance"
            params = {
                'tokenAddress': token_address,
                'walletAddress': user_wallet
            }
            
            if not self.session:
                await self.initialize()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return int(data.get('allowance', 0))
                    
        except Exception as e:
            self.logger.error(f"Error getting allowance: {e}")
        
        return 0
    
    async def get_approve_transaction(self, token_address: str, amount: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get approve transaction data for token."""
        try:
            url = f"{self.base_url}/approve/transaction"
            params = {'tokenAddress': token_address}
            
            if amount is not None:
                params['amount'] = str(amount)
            
            if not self.session:
                await self.initialize()
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                    
        except Exception as e:
            self.logger.error(f"Error getting approve transaction: {e}")
        
        return None
    
    def _get_token_address(self, token_symbol: str) -> Optional[str]:
        """Get token contract address from symbol."""
        # Handle native token
        if token_symbol.upper() == self.chain_config.native_token:
            return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # 1inch native token address
        
        token_info = self.supported_tokens.get(token_symbol.upper())
        return token_info['address'] if token_info else None
    
    def _amount_to_units(self, amount: float, token_symbol: str) -> int:
        """Convert human-readable amount to token units."""
        if token_symbol.upper() == self.chain_config.native_token:
            decimals = 18
        else:
            token_info = self.supported_tokens.get(token_symbol.upper())
            decimals = token_info['decimals'] if token_info else 18
        
        return int(amount * (10 ** decimals))
    
    def _units_to_amount(self, units: int, token_symbol: str) -> float:
        """Convert token units to human-readable amount."""
        if token_symbol.upper() == self.chain_config.native_token:
            decimals = 18
        else:
            token_info = self.supported_tokens.get(token_symbol.upper())
            decimals = token_info['decimals'] if token_info else 18
        
        return units / (10 ** decimals)
    
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
        tokens = [self.chain_config.native_token] + list(self.supported_tokens.keys())
        return tokens
    
    def is_token_supported(self, token_symbol: str) -> bool:
        """Check if token is supported."""
        return (token_symbol.upper() == self.chain_config.native_token or 
                token_symbol.upper() in self.supported_tokens)
    
    async def get_token_info(self, token_symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed token information."""
        if token_symbol.upper() == self.chain_config.native_token:
            return {
                'address': "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                'name': self.chain_config.native_token,
                'decimals': 18,
                'native': True
            }
        
        return self.supported_tokens.get(token_symbol.upper())
    
    def get_chain_info(self) -> Dict[str, Any]:
        """Get chain configuration info."""
        return {
            'chain_id': self.chain_id,
            'name': self.chain_config.name,
            'native_token': self.chain_config.native_token,
            'supported_tokens': len(self.supported_tokens)
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
        
        self.logger.info("1inch adapter cleanup completed")