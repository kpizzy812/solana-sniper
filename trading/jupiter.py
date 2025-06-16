import asyncio
import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

import aiohttp
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
import base64
from loguru import logger

from config.settings import settings


@dataclass
class TradeResult:
    """Result of a single trade attempt"""
    success: bool
    signature: Optional[str]
    error: Optional[str]
    input_amount: float
    output_amount: Optional[float]
    price_impact: Optional[float]
    execution_time_ms: float
    trade_index: int


@dataclass
class QuoteResponse:
    """Jupiter quote response"""
    input_mint: str
    output_mint: str
    in_amount: str
    out_amount: str
    price_impact_pct: str
    route_plan: List[Dict]


class HighSpeedJupiterTrader:
    """Ultra-fast Jupiter trading system"""

    def __init__(self):
        self.solana_client: Optional[AsyncClient] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.wallet_keypair: Optional[Keypair] = None

        # Trading stats
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0

        self.setup_wallet()

    def setup_wallet(self):
        """Setup Solana wallet from private key"""
        try:
            if settings.solana.private_key:
                # Decode base58 private key
                import base58
                private_key_bytes = base58.b58decode(settings.solana.private_key)
                self.wallet_keypair = Keypair.from_bytes(private_key_bytes)
                logger.info(f"Wallet loaded: {self.wallet_keypair.pubkey()}")
            else:
                logger.error("No private key configured")
        except Exception as e:
            logger.error(f"Failed to setup wallet: {e}")

    async def start(self):
        """Initialize trading system"""
        try:
            # Setup Solana RPC client
            self.solana_client = AsyncClient(
                endpoint=settings.solana.rpc_url,
                commitment=Confirmed
            )

            # Setup HTTP session for Jupiter API
            timeout = aiohttp.ClientTimeout(total=settings.jupiter.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)

            # Test connections
            await self.health_check()

            logger.info("Jupiter trader initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start Jupiter trader: {e}")
            return False

    async def stop(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        if self.solana_client:
            await self.solana_client.close()
        logger.info("Jupiter trader stopped")

    async def execute_sniper_trades(self, token_address: str, source_info: Dict) -> List[TradeResult]:
        """
        Execute multiple simultaneous trades for sniping
        """
        logger.critical(f"🎯 SNIPING TOKEN: {token_address}")
        logger.info(
            f"Executing {settings.trading.num_purchases} trades of {settings.trading.trade_amount_sol} SOL each")

        start_time = time.time()

        # Create trade tasks for concurrent execution
        trade_tasks = []
        for i in range(settings.trading.num_purchases):
            task = asyncio.create_task(
                self.execute_single_trade(token_address, i, source_info)
            )
            trade_tasks.append(task)

        # Execute all trades simultaneously
        results = await asyncio.gather(*trade_tasks, return_exceptions=True)

        # Process results
        trade_results = []
        successful_count = 0
        total_tokens_bought = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Trade {i + 1} failed with exception: {result}")
                trade_results.append(TradeResult(
                    success=False,
                    signature=None,
                    error=str(result),
                    input_amount=settings.trading.trade_amount_sol,
                    output_amount=None,
                    price_impact=None,
                    execution_time_ms=0,
                    trade_index=i
                ))
            else:
                trade_results.append(result)
                if result.success:
                    successful_count += 1
                    if result.output_amount:
                        total_tokens_bought += result.output_amount

        total_time = (time.time() - start_time) * 1000

        # Log summary
        logger.critical(f"🎯 SNIPER COMPLETE:")
        logger.info(f"  ✅ Successful trades: {successful_count}/{settings.trading.num_purchases}")
        logger.info(f"  💰 Total SOL spent: {successful_count * settings.trading.trade_amount_sol}")
        logger.info(f"  🪙 Total tokens bought: {total_tokens_bought:,.0f}")
        logger.info(f"  ⚡ Total execution time: {total_time:.0f}ms")
        logger.info(f"  📊 Average per trade: {total_time / settings.trading.num_purchases:.0f}ms")

        # Update stats
        self.total_trades += len(trade_results)
        self.successful_trades += successful_count
        self.failed_trades += (len(trade_results) - successful_count)

        return trade_results

    async def execute_single_trade(self, token_address: str, trade_index: int, source_info: Dict) -> TradeResult:
        """Execute a single trade with Jupiter"""
        start_time = time.time()

        try:
            logger.debug(f"Starting trade {trade_index + 1} for {token_address}")

            # Step 1: Get quote from Jupiter
            quote = await self.get_quote(
                input_mint=settings.trading.base_token,  # SOL
                output_mint=token_address,
                amount=int(settings.trading.trade_amount_sol * 1e9),  # Convert to lamports
                slippage_bps=settings.trading.slippage_bps
            )

            if not quote:
                return TradeResult(
                    success=False,
                    signature=None,
                    error="Failed to get quote",
                    input_amount=settings.trading.trade_amount_sol,
                    output_amount=None,
                    price_impact=None,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    trade_index=trade_index
                )

            logger.debug(f"Trade {trade_index + 1} quote: {quote.out_amount} tokens, {quote.price_impact_pct}% impact")

            # Step 2: Get swap transaction
            swap_transaction = await self.get_swap_transaction(quote)

            if not swap_transaction:
                return TradeResult(
                    success=False,
                    signature=None,
                    error="Failed to get swap transaction",
                    input_amount=settings.trading.trade_amount_sol,
                    output_amount=None,
                    price_impact=float(quote.price_impact_pct),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    trade_index=trade_index
                )

            # Step 3: Sign and send transaction
            signature = await self.send_transaction(swap_transaction)

            if signature:
                output_amount = float(quote.out_amount) / 1e9  # Convert from lamports
                logger.success(f"Trade {trade_index + 1} SUCCESS: {signature}")

                return TradeResult(
                    success=True,
                    signature=signature,
                    error=None,
                    input_amount=settings.trading.trade_amount_sol,
                    output_amount=output_amount,
                    price_impact=float(quote.price_impact_pct),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    trade_index=trade_index
                )
            else:
                return TradeResult(
                    success=False,
                    signature=None,
                    error="Transaction failed to send",
                    input_amount=settings.trading.trade_amount_sol,
                    output_amount=None,
                    price_impact=float(quote.price_impact_pct),
                    execution_time_ms=(time.time() - start_time) * 1000,
                    trade_index=trade_index
                )

        except Exception as e:
            logger.error(f"Trade {trade_index + 1} error: {e}")
            return TradeResult(
                success=False,
                signature=None,
                error=str(e),
                input_amount=settings.trading.trade_amount_sol,
                output_amount=None,
                price_impact=None,
                execution_time_ms=(time.time() - start_time) * 1000,
                trade_index=trade_index
            )

    async def get_quote(self, input_mint: str, output_mint: str, amount: int, slippage_bps: int) -> Optional[
        QuoteResponse]:
        """Get quote from Jupiter API"""
        try:
            url = f"{settings.jupiter.api_url}/quote"
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': False,  # Allow multi-hop for better prices
                'asLegacyTransaction': False
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return QuoteResponse(
                        input_mint=data['inputMint'],
                        output_mint=data['outputMint'],
                        in_amount=data['inAmount'],
                        out_amount=data['outAmount'],
                        price_impact_pct=data.get('priceImpactPct', '0'),
                        route_plan=data.get('routePlan', [])
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Quote API error {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return None

    async def get_swap_transaction(self, quote: QuoteResponse) -> Optional[str]:
        """Get swap transaction from Jupiter API"""
        try:
            url = f"{settings.jupiter.swap_api_url}"
            payload = {
                'quoteResponse': {
                    'inputMint': quote.input_mint,
                    'outputMint': quote.output_mint,
                    'inAmount': quote.in_amount,
                    'outAmount': quote.out_amount,
                    'priceImpactPct': quote.price_impact_pct,
                    'routePlan': quote.route_plan
                },
                'userPublicKey': str(self.wallet_keypair.pubkey()),
                'wrapAndUnwrapSol': True,
                'useSharedAccounts': True,
                'feeAccount': None,
                'prioritizationFeeLamports': settings.trading.priority_fee
            }

            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('swapTransaction')
                else:
                    error_text = await response.text()
                    logger.error(f"Swap API error {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get swap transaction: {e}")
            return None

    async def send_transaction(self, swap_transaction_b64: str) -> Optional[str]:
        """Sign and send transaction to Solana"""
        try:
            # Decode transaction
            transaction_bytes = base64.b64decode(swap_transaction_b64)
            transaction = VersionedTransaction.from_bytes(transaction_bytes)

            # Sign transaction
            transaction.sign([self.wallet_keypair])

            # Send with high priority
            response = await self.solana_client.send_raw_transaction(
                bytes(transaction),
                opts={
                    'skipPreflight': True,  # Skip simulation for speed
                    'preflightCommitment': 'confirmed',
                    'maxRetries': settings.trading.max_retries
                }
            )

            if response.value:
                signature = str(response.value)
                logger.debug(f"Transaction sent: {signature}")

                # Optional: Wait for confirmation (can be disabled for speed)
                # await self.confirm_transaction(signature)

                return signature
            else:
                logger.error("Transaction failed to send")
                return None

        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            return None

    async def confirm_transaction(self, signature: str, timeout: float = 30.0) -> bool:
        """Confirm transaction (optional, slows down execution)"""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                status = await self.solana_client.get_signature_statuses([signature])
                if status.value and status.value[0]:
                    confirmation_status = status.value[0]
                    if confirmation_status.confirmation_status:
                        logger.debug(f"Transaction confirmed: {signature}")
                        return True

                await asyncio.sleep(1)

            logger.warning(f"Transaction confirmation timeout: {signature}")
            return False

        except Exception as e:
            logger.error(f"Failed to confirm transaction: {e}")
            return False

    async def get_token_balance(self, token_address: str) -> float:
        """Get token balance for the wallet"""
        try:
            # Implementation depends on token type (SPL token)
            # This is a simplified version
            response = await self.solana_client.get_token_accounts_by_owner(
                self.wallet_keypair.pubkey(),
                {'mint': Pubkey.from_string(token_address)}
            )

            if response.value:
                # Parse token account balance
                # This would need proper SPL token parsing
                return 0.0

            return 0.0

        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return 0.0

    async def get_sol_balance(self) -> float:
        """Get SOL balance"""
        try:
            response = await self.solana_client.get_balance(self.wallet_keypair.pubkey())
            if response.value:
                return response.value / 1e9  # Convert lamports to SOL
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get SOL balance: {e}")
            return 0.0

    async def health_check(self) -> Dict:
        """Health check for trading system"""
        try:
            # Check Solana connection
            response = await self.solana_client.get_health()
            solana_healthy = response.value == "ok"

            # Check Jupiter API
            async with self.session.get(f"{settings.jupiter.api_url}/quote") as resp:
                jupiter_healthy = resp.status in [200, 400]  # 400 is expected without params

            # Check wallet balance
            sol_balance = await self.get_sol_balance()

            return {
                "status": "healthy" if solana_healthy and jupiter_healthy else "degraded",
                "solana_rpc": "healthy" if solana_healthy else "error",
                "jupiter_api": "healthy" if jupiter_healthy else "error",
                "wallet_address": str(self.wallet_keypair.pubkey()),
                "sol_balance": sol_balance,
                "stats": {
                    "total_trades": self.total_trades,
                    "successful_trades": self.successful_trades,
                    "failed_trades": self.failed_trades,
                    "success_rate": self.successful_trades / max(self.total_trades, 1) * 100
                }
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global trader instance
jupiter_trader = HighSpeedJupiterTrader()