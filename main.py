#!/usr/bin/env python3
"""
🎯 MORI Token Sniper Bot
Ultra-fast social media monitoring and trading system

Features:
- 1-second monitoring of Telegram, Twitter, websites
- Instant regex + optional AI analysis
- Concurrent Jupiter trading (10 purchases simultaneously)
- Security checks and risk management
"""

import asyncio
import signal
import sys
import time
from typing import Dict, List
from datetime import datetime

# Setup faster event loop on Linux/Mac
try:
    import uvloop

    uvloop.install()
except ImportError:
    pass

from loguru import logger
from config.settings import settings
from ai.analyzer import analyzer
from monitors.telegram import telegram_monitor
from monitors.twitter import twitter_monitor
from monitors.website import website_monitor
from trading.jupiter import jupiter_trader


class MoriSniperBot:
    """Main sniper bot orchestrator"""

    def __init__(self):
        self.running = False
        self.start_time = None
        self.monitors = {}
        self.stats = {
            'posts_analyzed': 0,
            'contracts_detected': 0,
            'trades_executed': 0,
            'total_sol_spent': 0,
            'uptime_seconds': 0
        }

        # Setup logging
        self.setup_logging()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def setup_logging(self):
        """Configure logging system"""
        logger.remove()  # Remove default handler

        # Console logging with colors
        logger.add(
            sys.stdout,
            level=settings.logging.level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | {message}",
            colorize=True
        )

        # File logging
        logger.add(
            settings.logging.file_path,
            level="DEBUG",
            format=settings.logging.format,
            rotation=settings.logging.max_size,
            retention=settings.logging.retention,
            compression="zip"
        )

    async def start(self):
        """Start the sniper bot"""
        logger.info("🎯 Starting MORI Sniper Bot...")
        logger.info(f"Network: {settings.solana.network}")
        logger.info(f"Trade settings: {settings.trading.num_purchases}x {settings.trading.trade_amount_sol} SOL")
        logger.info(
            f"Total investment per signal: {settings.trading.num_purchases * settings.trading.trade_amount_sol} SOL")

        try:
            # Validate configuration
            settings.validate()
            logger.success("✅ Configuration validated")

            # Initialize components
            await self.initialize_components()

            # Start monitoring
            await self.start_monitoring()

            # Set running state
            self.running = True
            self.start_time = time.time()

            logger.critical("🚨 SNIPER BOT ACTIVE - Monitoring for contracts...")
            logger.info("Press Ctrl+C to stop")

            # Main loop
            await self.main_loop()

        except Exception as e:
            logger.error(f"Failed to start sniper bot: {e}")
            await self.stop()

    async def initialize_components(self):
        """Initialize all bot components"""
        logger.info("Initializing components...")

        # Initialize AI analyzer
        if await analyzer.health_check():
            logger.success("✅ AI Analyzer ready")
        else:
            logger.warning("⚠️ AI Analyzer issues detected")

        # Initialize trading system
        if await jupiter_trader.start():
            logger.success("✅ Jupiter Trader ready")
        else:
            logger.error("❌ Jupiter Trader failed to start")
            raise Exception("Trading system initialization failed")

        # Initialize Telegram monitor
        if settings.monitoring.telegram_bot_token:
            telegram_monitor.trading_callback = self.handle_trading_signal
            if await telegram_monitor.start():
                logger.success("✅ Telegram Monitor ready")
                self.monitors['telegram'] = telegram_monitor
            else:
                logger.warning("⚠️ Telegram Monitor not available")
        else:
            logger.info("⏭️ Telegram token not configured, skipping Telegram monitor")

        # Initialize Twitter monitor
        if settings.monitoring.twitter_bearer_token:
            twitter_monitor.trading_callback = self.handle_trading_signal
            if await twitter_monitor.start():
                logger.success("✅ Twitter Monitor ready")
                self.monitors['twitter'] = twitter_monitor
            else:
                logger.warning("⚠️ Twitter Monitor not available")
        else:
            logger.info("⏭️ Twitter token not configured, skipping Twitter monitor")

        # Initialize Website monitor
        if settings.monitoring.website_urls and any(settings.monitoring.website_urls):
            website_monitor.trading_callback = self.handle_trading_signal
            if await website_monitor.start():
                logger.success("✅ Website Monitor ready")
                self.monitors['website'] = website_monitor
            else:
                logger.warning("⚠️ Website Monitor not available")
        else:
            logger.info("⏭️ Website URLs not configured, skipping Website monitor")

        logger.success(f"✅ {len(self.monitors)} monitors initialized")

    async def start_monitoring(self):
        """Start all monitoring systems"""
        logger.info("Starting monitoring systems...")

        # Monitors are already started in initialize_components
        # This method can be used for additional monitoring setup

        logger.success("🔍 All monitors active")

    async def main_loop(self):
        """Main event loop"""
        while self.running:
            try:
                # Update uptime
                self.stats['uptime_seconds'] = int(time.time() - self.start_time)

                # Health checks every minute
                if self.stats['uptime_seconds'] % 60 == 0:
                    await self.health_check()

                # Status update every 5 minutes
                if self.stats['uptime_seconds'] % 300 == 0:
                    self.log_status()

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def handle_trading_signal(self, signal_data: Dict):
        """Handle trading signal from monitors"""
        try:
            logger.critical("🚨 TRADING SIGNAL RECEIVED")
            logger.info(f"Platform: {signal_data['platform']}")
            logger.info(f"Source: {signal_data['source']}")
            logger.info(f"Contracts: {signal_data['contracts']}")
            logger.info(f"Confidence: {signal_data['confidence']:.2f}")

            # Update stats
            self.stats['contracts_detected'] += 1

            # Execute trades for each detected contract
            for contract_address in signal_data['contracts']:
                logger.critical(f"🎯 EXECUTING SNIPER TRADES FOR: {contract_address}")

                # Security checks could be added here
                # if not await self.security_check(contract_address):
                #     continue

                # Execute concurrent trades
                trade_results = await jupiter_trader.execute_sniper_trades(
                    token_address=contract_address,
                    source_info=signal_data
                )

                # Update stats
                successful_trades = sum(1 for result in trade_results if result.success)
                self.stats['trades_executed'] += len(trade_results)
                self.stats['total_sol_spent'] += successful_trades * settings.trading.trade_amount_sol

                # Log results summary
                self.log_trade_results(contract_address, trade_results, signal_data)

        except Exception as e:
            logger.error(f"Error handling trading signal: {e}")

    def log_trade_results(self, contract_address: str, results: List, signal_data: Dict):
        """Log detailed trading results"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        logger.critical("📊 TRADE RESULTS SUMMARY:")
        logger.info(f"  Contract: {contract_address}")
        logger.info(f"  Source: {signal_data['platform']} - {signal_data['source']}")
        logger.info(f"  Successful: {len(successful)}/{len(results)}")
        logger.info(f"  SOL Spent: {len(successful) * settings.trading.trade_amount_sol}")

        if successful:
            avg_time = sum(r.execution_time_ms for r in successful) / len(successful)
            logger.info(f"  Avg Execution Time: {avg_time:.0f}ms")

            # Log signatures for successful trades
            logger.info("  Signatures:")
            for i, result in enumerate(successful):
                logger.info(f"    {i + 1}. {result.signature}")

        if failed:
            logger.warning(f"  Failed trades: {len(failed)}")
            for result in failed:
                if result.error:
                    logger.warning(f"    Trade {result.trade_index + 1}: {result.error}")

    async def health_check(self):
        """Perform health checks on all components"""
        try:
            # Check trading system
            trader_health = await jupiter_trader.health_check()

            # Check monitors
            monitor_health = {}
            for name, monitor in self.monitors.items():
                monitor_health[name] = await monitor.health_check()

            # Log health status
            if trader_health.get('status') == 'healthy':
                logger.debug("🟢 Trading system healthy")
            else:
                logger.warning(f"🟡 Trading system: {trader_health.get('status')}")

            for name, health in monitor_health.items():
                status = health.get('status', 'unknown')
                if status == 'healthy':
                    logger.debug(f"🟢 {name.title()} monitor healthy")
                else:
                    logger.warning(f"🟡 {name.title()} monitor: {status}")

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def log_status(self):
        """Log current bot status"""
        uptime_minutes = self.stats['uptime_seconds'] // 60
        logger.info(f"📈 STATUS UPDATE - Uptime: {uptime_minutes} minutes")
        logger.info(f"  Posts analyzed: {self.stats['posts_analyzed']}")
        logger.info(f"  Contracts detected: {self.stats['contracts_detected']}")
        logger.info(f"  Trades executed: {self.stats['trades_executed']}")
        logger.info(f"  Total SOL spent: {self.stats['total_sol_spent']}")

        if self.stats['contracts_detected'] > 0:
            success_rate = (self.stats['trades_executed'] / (
                        self.stats['contracts_detected'] * settings.trading.num_purchases)) * 100
            logger.info(f"  Trade success rate: {success_rate:.1f}%")

    async def stop(self):
        """Stop the sniper bot gracefully"""
        logger.info("🛑 Stopping sniper bot...")
        self.running = False

        # Stop all monitors
        for name, monitor in self.monitors.items():
            try:
                await monitor.stop()
                logger.info(f"✅ {name.title()} monitor stopped")
            except Exception as e:
                logger.error(f"Error stopping {name} monitor: {e}")

        # Stop trading system
        try:
            await jupiter_trader.stop()
            logger.info("✅ Trading system stopped")
        except Exception as e:
            logger.error(f"Error stopping trading system: {e}")

        # Final stats
        if self.start_time:
            total_uptime = int(time.time() - self.start_time)
            logger.info(f"📊 FINAL STATS - Uptime: {total_uptime // 60} minutes")
            logger.info(f"  Total posts analyzed: {self.stats['posts_analyzed']}")
            logger.info(f"  Total contracts detected: {self.stats['contracts_detected']}")
            logger.info(f"  Total trades executed: {self.stats['trades_executed']}")
            logger.info(f"  Total SOL spent: {self.stats['total_sol_spent']}")

        logger.success("🎯 Sniper bot stopped successfully")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())


async def main():
    """Main entry point"""
    print("🎯 MORI Token Sniper Bot")
    print("=" * 50)

    # Create and start bot
    bot = MoriSniperBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await bot.stop()


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())