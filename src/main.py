"""Main entry point for the Nakarte GPX Bot."""

import asyncio
import os
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.bot.handlers import BotHandlers
from src.services.cache_service import create_cache_service, CacheService
from src.services.nakarte_service import NakarteService
from src.utils.logger import setup_logging, get_logger


class Application:
    """Main application class."""

    def __init__(self):
        """Initialize application."""
        # Load environment variables
        load_dotenv()

        # Setup logging
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(log_level)
        self.logger = get_logger(__name__)

        # Get configuration from environment
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            self.logger.error("missing_bot_token")
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        self.cache_type = os.getenv("CACHE_TYPE", "file")
        cache_ttl = os.getenv("CACHE_TTL")
        self.cache_ttl = int(cache_ttl) if cache_ttl else None
        self.browser_headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        self.browser_timeout = int(os.getenv("BROWSER_TIMEOUT", "30000"))
        self.nakarte_app_ready_timeout = int(os.getenv("NAKARTE_APP_READY_TIMEOUT", "8000"))
        self.download_concurrency = int(os.getenv("DOWNLOAD_CONCURRENCY", "1"))

        # Redis configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        self.redis_password = os.getenv("REDIS_PASSWORD") or None

        # Initialize services
        self.nakarte_service: Optional[NakarteService] = None
        self.cache_service: Optional[CacheService] = None
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None

        self.logger.info(
            "application_initialized",
            cache_type=self.cache_type,
            cache_ttl=self.cache_ttl,
            browser_headless=self.browser_headless,
        )

    async def setup(self) -> None:
        """Setup application components."""
        self.logger.info("setting_up_application")

        # Initialize Nakarte service
        self.nakarte_service = NakarteService(
            headless=self.browser_headless,
            timeout=self.browser_timeout,
            app_ready_timeout=self.nakarte_app_ready_timeout,
            logger=self.logger,
        )

        # Initialize cache service
        self.cache_service = create_cache_service(
            cache_type=self.cache_type,
            redis_host=self.redis_host,
            redis_port=self.redis_port,
            redis_db=self.redis_db,
            redis_password=self.redis_password,
            cache_dir="./cache",
            logger=self.logger,
        )

        # Initialize bot
        self.bot = Bot(
            token=self.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        bot_info = await self.bot.get_me()
        bot_username = bot_info.username or ""
        bot_id = bot_info.id

        # Initialize dispatcher
        self.dp = Dispatcher()

        # Register handlers
        handlers = BotHandlers(
            nakarte_service=self.nakarte_service,
            cache_service=self.cache_service,
            cache_ttl=self.cache_ttl,
            bot_username=bot_username,
            bot_id=bot_id,
            max_concurrent_downloads=self.download_concurrency,
            logger=self.logger,
        )
        handlers.register_handlers(self.dp)

        self.logger.info("application_setup_complete")

    async def start(self) -> None:
        """Start the bot."""
        if not self.bot or not self.dp:
            raise RuntimeError("Application not setup. Call setup() first.")

        self.logger.info("starting_bot")

        try:
            # Start polling
            await self.dp.start_polling(self.bot)
        except Exception as e:
            self.logger.error("bot_error", error=str(e))
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown application gracefully."""
        self.logger.info("shutting_down_application")

        # Close services
        if self.nakarte_service:
            await self.nakarte_service.close()

        if self.cache_service:
            await self.cache_service.close()

        # Close bot session
        if self.bot:
            await self.bot.session.close()

        self.logger.info("application_shutdown_complete")

    async def run(self) -> None:
        """Run the application."""
        await self.setup()
        await self.start()


async def main() -> None:
    """Main entry point."""
    app = Application()

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def signal_handler(sig: int) -> None:
        """Handle shutdown signals."""
        app.logger.info("received_signal", signal=sig)
        loop.create_task(app.shutdown())
        loop.stop()

    # Register signal handlers
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    else:
        # Windows doesn't support add_signal_handler
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s))
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s))

    try:
        await app.run()
    except KeyboardInterrupt:
        app.logger.info("keyboard_interrupt")
    except Exception as e:
        app.logger.error("application_error", error=str(e))
        raise
    finally:
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
