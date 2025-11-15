"""
Transaction Decoder

Decodes blockchain transaction data for:
- DEX trade parameters extraction
- Function call identification
- Token transfer analysis
- Smart contract interaction parsing
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import json

from src.market_data.mempool.mempool_monitor import MempoolTransaction, ChainType


class FunctionType(Enum):
    """Types of decoded functions."""
    SWAP = "SWAP"
    ADD_LIQUIDITY = "ADD_LIQUIDITY"
    REMOVE_LIQUIDITY = "REMOVE_LIQUIDITY"
    TRANSFER = "TRANSFER"
    APPROVE = "APPROVE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DecodedFunction:
    """Decoded function call data."""
    function_type: FunctionType
    function_name: str
    parameters: Dict[str, Any]
    estimated_gas: int
    value_transferred: float = 0.0


@dataclass
class SwapParameters:
    """Decoded swap transaction parameters."""
    token_in: str
    token_out: str
    amount_in: float
    amount_out_min: float
    path: List[str]
    recipient: str
    deadline: int
    dex_name: str
    slippage_tolerance: float = 0.0


@dataclass
class LiquidityParameters:
    """Decoded liquidity transaction parameters."""
    token_a: str
    token_b: str
    amount_a: float
    amount_b: float
    amount_a_min: float = 0.0
    amount_b_min: float = 0.0
    recipient: str = ""
    deadline: int = 0


class TransactionDecoder:
    """
    Blockchain transaction decoder for DeFi operations.
    
    Features:
    - Function signature detection
    - Parameter extraction
    - Multi-DEX support
    - Token transfer analysis
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Function signatures for major DEXes
        self._function_signatures = {
            # Uniswap V2 Router
            "0x38ed1739": {
                "name": "swapExactTokensForTokens",
                "type": FunctionType.SWAP,
                "dex": "Uniswap V2"
            },
            "0x8803dbee": {
                "name": "swapTokensForExactTokens", 
                "type": FunctionType.SWAP,
                "dex": "Uniswap V2"
            },
            "0x7ff36ab5": {
                "name": "swapExactETHForTokens",
                "type": FunctionType.SWAP,
                "dex": "Uniswap V2"
            },
            "0x18cbafe5": {
                "name": "swapExactTokensForETH",
                "type": FunctionType.SWAP,
                "dex": "Uniswap V2"
            },
            
            # Uniswap V3 Router
            "0x414bf389": {
                "name": "exactInputSingle",
                "type": FunctionType.SWAP,
                "dex": "Uniswap V3"
            },
            "0x5ae401dc": {
                "name": "multicall",
                "type": FunctionType.SWAP,
                "dex": "Uniswap V3"
            },
            
            # Sushiswap (same as Uniswap V2 mostly)
            "0x38ed1739": {
                "name": "swapExactTokensForTokens",
                "type": FunctionType.SWAP,
                "dex": "Sushiswap"
            },
            
            # 1inch
            "0x7c025200": {
                "name": "swap",
                "type": FunctionType.SWAP,
                "dex": "1inch"
            },
            
            # Generic ERC20
            "0xa9059cbb": {
                "name": "transfer",
                "type": FunctionType.TRANSFER,
                "dex": "ERC20"
            },
            "0x095ea7b3": {
                "name": "approve",
                "type": FunctionType.APPROVE,
                "dex": "ERC20"
            },
            
            # Liquidity operations
            "0xe8e33700": {
                "name": "addLiquidity",
                "type": FunctionType.ADD_LIQUIDITY,
                "dex": "Uniswap V2"
            },
            "0xf305d719": {
                "name": "addLiquidityETH",
                "type": FunctionType.ADD_LIQUIDITY,
                "dex": "Uniswap V2"
            }
        }
        
        # Common token addresses for major chains
        self._common_tokens = {
            ChainType.ETHEREUM: {
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2": "WETH",
                "0xA0b86a33E6441949620B533169F70E81d5E95876": "USDC",
                "0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
                "0x6B175474E89094C44Da98b954EedeAC495271d0F": "DAI"
            },
            # Add other chains as needed
        }
        
        self.logger.info("Transaction Decoder initialized")
    
    def decode_transaction(self, tx: MempoolTransaction) -> Optional[DecodedFunction]:
        """
        Decode a blockchain transaction.
        
        Args:
            tx: Mempool transaction to decode
            
        Returns:
            Decoded function data or None
        """
        try:
            if not tx.data or len(tx.data) < 10:
                return None
            
            # Extract function selector (first 4 bytes)
            function_selector = tx.data[:10]  # 0x + 8 hex chars
            
            # Look up function signature
            signature_info = self._function_signatures.get(function_selector)
            
            if not signature_info:
                # Try to identify by pattern matching
                signature_info = self._identify_by_pattern(tx.data)
            
            if not signature_info:
                return DecodedFunction(
                    function_type=FunctionType.UNKNOWN,
                    function_name="unknown",
                    parameters={},
                    estimated_gas=tx.gas_limit
                )
            
            # Decode parameters based on function type
            parameters = self._decode_parameters(
                tx.data, 
                signature_info["type"],
                signature_info.get("dex", "Unknown")
            )
            
            return DecodedFunction(
                function_type=signature_info["type"],
                function_name=signature_info["name"],
                parameters=parameters,
                estimated_gas=tx.gas_limit,
                value_transferred=tx.value
            )
            
        except Exception as e:
            self.logger.error(f"Error decoding transaction: {e}")
            return None
    
    def _identify_by_pattern(self, data: str) -> Optional[Dict[str, Any]]:
        """Identify function by data pattern when signature is unknown."""
        # Simple pattern matching for unknown functions
        data_lower = data.lower()
        
        # Look for swap-like patterns
        if any(pattern in data_lower for pattern in ["swap", "exchange"]):
            return {
                "name": "unknown_swap",
                "type": FunctionType.SWAP,
                "dex": "Unknown"
            }
        
        # Look for transfer patterns
        if "transfer" in data_lower:
            return {
                "name": "unknown_transfer", 
                "type": FunctionType.TRANSFER,
                "dex": "Unknown"
            }
        
        return None
    
    def _decode_parameters(self, 
                          data: str, 
                          function_type: FunctionType, 
                          dex_name: str) -> Dict[str, Any]:
        """Decode function parameters from transaction data."""
        try:
            parameters = {"dex_name": dex_name}
            
            if function_type == FunctionType.SWAP:
                parameters.update(self._decode_swap_parameters(data, dex_name))
            elif function_type == FunctionType.ADD_LIQUIDITY:
                parameters.update(self._decode_liquidity_parameters(data))
            elif function_type == FunctionType.TRANSFER:
                parameters.update(self._decode_transfer_parameters(data))
            elif function_type == FunctionType.APPROVE:
                parameters.update(self._decode_approve_parameters(data))
            
            return parameters
            
        except Exception as e:
            self.logger.error(f"Error decoding parameters: {e}")
            return {"dex_name": dex_name, "error": str(e)}
    
    def _decode_swap_parameters(self, data: str, dex_name: str) -> Dict[str, Any]:
        """Decode swap transaction parameters."""
        # This is a simplified decoder - real implementation would use ABI decoding
        params = {}
        
        try:
            # Extract basic parameters (simplified)
            if len(data) >= 74:  # Minimum length for basic swap
                # Amount in (next 32 bytes after function selector)
                amount_in_hex = data[10:74]
                try:
                    amount_in = int(amount_in_hex, 16)
                    params["amount_in"] = amount_in
                except ValueError:
                    params["amount_in"] = 0
                
                # Amount out minimum (next 32 bytes)
                if len(data) >= 138:
                    amount_out_hex = data[74:138]
                    try:
                        amount_out_min = int(amount_out_hex, 16)
                        params["amount_out_min"] = amount_out_min
                        
                        # Calculate slippage tolerance
                        if amount_in > 0:
                            slippage = ((amount_in - amount_out_min) / amount_in) * 100
                            params["slippage_tolerance"] = min(100, max(0, slippage))
                    except ValueError:
                        params["amount_out_min"] = 0
            
            # Extract token addresses (simplified - would need proper ABI decoding)
            params["token_addresses"] = self._extract_token_addresses(data)
            
            # Add timestamp/deadline if present
            params["deadline"] = int(datetime.now().timestamp()) + 1800  # Assume 30 min default
            
        except Exception as e:
            self.logger.debug(f"Error in swap parameter decoding: {e}")
        
        return params
    
    def _decode_liquidity_parameters(self, data: str) -> Dict[str, Any]:
        """Decode liquidity transaction parameters."""
        params = {}
        
        # Simplified liquidity parameter extraction
        try:
            if len(data) >= 200:  # Minimum for liquidity params
                # Token A amount
                token_a_amount_hex = data[10:74]
                params["token_a_amount"] = int(token_a_amount_hex, 16)
                
                # Token B amount
                token_b_amount_hex = data[74:138]
                params["token_b_amount"] = int(token_b_amount_hex, 16)
                
                # Minimum amounts
                token_a_min_hex = data[138:202]
                params["token_a_min"] = int(token_a_min_hex, 16)
        
        except Exception as e:
            self.logger.debug(f"Error in liquidity parameter decoding: {e}")
        
        return params
    
    def _decode_transfer_parameters(self, data: str) -> Dict[str, Any]:
        """Decode transfer transaction parameters."""
        params = {}
        
        try:
            if len(data) >= 138:  # Transfer has recipient + amount
                # Recipient address (20 bytes, but padded to 32)
                recipient_hex = data[10:74]
                params["recipient"] = "0x" + recipient_hex[-40:]  # Last 20 bytes
                
                # Amount (next 32 bytes)
                amount_hex = data[74:138]
                params["amount"] = int(amount_hex, 16)
        
        except Exception as e:
            self.logger.debug(f"Error in transfer parameter decoding: {e}")
        
        return params
    
    def _decode_approve_parameters(self, data: str) -> Dict[str, Any]:
        """Decode approve transaction parameters."""
        params = {}
        
        try:
            if len(data) >= 138:  # Approve has spender + amount
                # Spender address
                spender_hex = data[10:74]
                params["spender"] = "0x" + spender_hex[-40:]
                
                # Amount
                amount_hex = data[74:138]
                amount = int(amount_hex, 16)
                params["amount"] = amount
                
                # Check for unlimited approval
                max_uint256 = 2**256 - 1
                params["unlimited"] = amount >= max_uint256
        
        except Exception as e:
            self.logger.debug(f"Error in approve parameter decoding: {e}")
        
        return params
    
    def _extract_token_addresses(self, data: str) -> List[str]:
        """Extract token addresses from transaction data."""
        addresses = []
        
        try:
            # Look for address patterns (0x followed by 40 hex chars)
            # This is simplified - real implementation would use ABI decoding
            data_lower = data.lower()
            i = 0
            while i < len(data_lower) - 40:
                if data_lower[i:i+2] == "00" and len(data_lower[i:i+42]) == 42:
                    # Potential address (padded with zeros)
                    potential_addr = "0x" + data_lower[i+2:i+42]
                    if self._is_valid_address(potential_addr):
                        addresses.append(potential_addr)
                i += 1
        
        except Exception as e:
            self.logger.debug(f"Error extracting token addresses: {e}")
        
        return addresses[:4]  # Limit to first 4 addresses found
    
    def _is_valid_address(self, address: str) -> bool:
        """Check if string is a valid Ethereum address."""
        if not address.startswith("0x"):
            return False
        
        if len(address) != 42:
            return False
        
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False
    
    def decode_swap_transaction(self, tx: MempoolTransaction) -> Optional[SwapParameters]:
        """Decode specifically swap transactions with full parameters."""
        decoded = self.decode_transaction(tx)
        
        if not decoded or decoded.function_type != FunctionType.SWAP:
            return None
        
        try:
            params = decoded.parameters
            
            # Extract addresses
            addresses = params.get("token_addresses", [])
            token_in = addresses[0] if len(addresses) > 0 else ""
            token_out = addresses[-1] if len(addresses) > 1 else ""
            
            return SwapParameters(
                token_in=token_in,
                token_out=token_out,
                amount_in=params.get("amount_in", 0),
                amount_out_min=params.get("amount_out_min", 0),
                path=addresses,
                recipient=tx.from_address,  # Simplified
                deadline=params.get("deadline", 0),
                dex_name=params.get("dex_name", "Unknown"),
                slippage_tolerance=params.get("slippage_tolerance", 0.0)
            )
            
        except Exception as e:
            self.logger.error(f"Error creating swap parameters: {e}")
            return None
    
    def get_token_symbol(self, address: str, chain: ChainType) -> str:
        """Get token symbol from address."""
        tokens = self._common_tokens.get(chain, {})
        return tokens.get(address.lower(), f"Token_{address[:8]}...")
    
    def estimate_gas_cost(self, decoded: DecodedFunction, gas_price: float) -> Dict[str, float]:
        """Estimate gas cost for decoded transaction."""
        # Base gas estimates by function type
        base_gas = {
            FunctionType.SWAP: 150000,
            FunctionType.ADD_LIQUIDITY: 200000,
            FunctionType.REMOVE_LIQUIDITY: 120000,
            FunctionType.TRANSFER: 21000,
            FunctionType.APPROVE: 45000,
            FunctionType.UNKNOWN: 100000
        }
        
        estimated_gas = base_gas.get(decoded.function_type, 100000)
        
        # Adjust for complex operations
        if "multicall" in decoded.function_name.lower():
            estimated_gas *= 2  # Multicalls use more gas
        
        cost_eth = (gas_price * estimated_gas) / 1e9  # gwei to ETH
        cost_usd = cost_eth * 2000  # Simplified ETH price
        
        return {
            "estimated_gas": estimated_gas,
            "gas_price_gwei": gas_price,
            "cost_eth": cost_eth,
            "cost_usd": cost_usd
        }