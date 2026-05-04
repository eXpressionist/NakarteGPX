"""Telegram bot handlers."""

import asyncio
import re
import uuid
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile
from structlog import BoundLogger

from src.services.cache_service import CacheService
from src.services.nakarte_service import NakarteService
from src.utils.logger import get_logger


class BotHandlers:
    """Telegram bot message handlers."""

    URL_RE = re.compile(r"https?://(?:www\.)?nakarte\.me/[^\s]+", re.IGNORECASE)

    def __init__(
        self,
        nakarte_service: NakarteService,
        cache_service: CacheService,
        cache_ttl: Optional[int] = None,
        bot_username: str = "",
        bot_id: Optional[int] = None,
        max_concurrent_downloads: int = 1,
        logger: Optional[BoundLogger] = None,
    ):
        """
        Initialize bot handlers.
        
        Args:
            nakarte_service: Nakarte service instance
            cache_service: Cache service instance
            cache_ttl: Optional cache TTL in seconds
            logger: Logger instance
        """
        self.nakarte_service = nakarte_service
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
        self.bot_username = bot_username.lower().lstrip("@")
        self.bot_id = bot_id
        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self._inflight_downloads: dict[str, asyncio.Task[bytes]] = {}
        self._inflight_lock = asyncio.Lock()
        self.logger = logger or get_logger(__name__)

    async def _download_uncached_gpx(self, url: str) -> bytes:
        """Run expensive GPX extraction with bounded concurrency."""
        async with self._download_semaphore:
            return await self.nakarte_service.download_gpx(url)

    async def _download_gpx_singleflight(self, track_id: str, url: str) -> bytes:
        """Share one in-progress download for identical track IDs."""
        created_task = False
        async with self._inflight_lock:
            task = self._inflight_downloads.get(track_id)
            if task is None:
                task = asyncio.create_task(self._download_uncached_gpx(url))
                self._inflight_downloads[track_id] = task
                created_task = True
                self.logger.info("download_started", track_id=track_id)
            else:
                self.logger.info("download_joined", track_id=track_id)

        try:
            return await task
        finally:
            if created_task:
                async with self._inflight_lock:
                    if self._inflight_downloads.get(track_id) is task:
                        self._inflight_downloads.pop(track_id, None)

    def _extract_nakarte_url(self, text: str) -> Optional[str]:
        """Extract first nakarte URL from message text."""
        match = self.URL_RE.search(text or "")
        if not match:
            return None
        return match.group(0).rstrip(".,;:!?)]}>\"'")

    def _is_group_chat(self, message: Message) -> bool:
        """Check if message comes from group/supergroup."""
        return message.chat.type in {"group", "supergroup"}

    def _is_bot_mentioned(self, message: Message) -> bool:
        """Check whether bot is explicitly mentioned in message text/entities."""
        if not self.bot_username:
            # Fallback: if username is not available, try entity by user id
            for entity in (message.entities or []):
                if entity.type == "text_mention" and entity.user and self.bot_id:
                    if entity.user.id == self.bot_id:
                        return True
            return False

        text = message.text or ""
        mention = f"@{self.bot_username}"
        if mention in text.lower():
            return True

        for entity in (message.entities or []):
            if entity.type == "mention":
                entity_text = text[entity.offset : entity.offset + entity.length].lower()
                if entity_text == mention:
                    return True
            if entity.type == "text_mention" and entity.user and self.bot_id:
                if entity.user.id == self.bot_id:
                    return True

        return False

    def register_handlers(self, dp: Dispatcher) -> None:
        """
        Register all bot handlers.
        
        Args:
            dp: Aiogram dispatcher
        """
        dp.message.register(self.cmd_start, CommandStart())
        dp.message.register(self.cmd_help, Command("help"))
        dp.message.register(self.handle_url, F.text)

    async def cmd_start(self, message: Message) -> None:
        """
        Handle /start command.
        
        Args:
            message: Telegram message
        """
        user_id = message.from_user.id if message.from_user else "unknown"
        self.logger.info("command_start", user_id=user_id)

        await message.answer(
            "👋 Привет! Я бот для скачивания GPX треков с nakarte.me\n\n"
            "Просто отправь мне ссылку на трек с nakarte.me, "
            "и я пришлю тебе GPX файл.\n\n"
            "Пример ссылки:\n"
            "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA\n\n"
            "Используй /help для получения дополнительной информации."
        )

    async def cmd_help(self, message: Message) -> None:
        """
        Handle /help command.
        
        Args:
            message: Telegram message
        """
        user_id = message.from_user.id if message.from_user else "unknown"
        self.logger.info("command_help", user_id=user_id)

        await message.answer(
            "ℹ️ Помощь\n\n"
            "Этот бот позволяет скачивать GPX треки с сайта nakarte.me.\n\n"
            "📝 Как использовать:\n"
            "1. Откройте nakarte.me и создайте или откройте трек\n"
            "2. Скопируйте ссылку из адресной строки браузера\n"
            "3. Отправьте ссылку боту\n"
            "4. Получите GPX файл\n\n"
            "⚡ Особенности:\n"
            "• Быстрая обработка благодаря кешированию\n"
            "• Поддержка всех треков с nakarte.me\n"
            "• Автоматическая валидация ссылок\n\n"
            "❓ Проблемы?\n"
            "Убедитесь, что ссылка содержит параметр 'nktl' с идентификатором трека."
        )

    async def handle_url(self, message: Message) -> None:
        """
        Handle URL messages.
        
        Args:
            message: Telegram message
        """
        if not message.text:
            return

        user_id = message.from_user.id if message.from_user else "unknown"
        request_id = str(uuid.uuid4())
        text = message.text.strip()
        self.logger.info(
            "message_received",
            chat_type=message.chat.type,
            user_id=user_id,
            has_entities=bool(message.entities),
            text_preview=text[:120],
        )

        # In groups, process only when the bot is tagged in the message
        is_reply_to_bot = bool(
            message.reply_to_message
            and message.reply_to_message.from_user
            and self.bot_id
            and message.reply_to_message.from_user.id == self.bot_id
        )
        mentioned = self._is_bot_mentioned(message)
        if self._is_group_chat(message) and not (mentioned or is_reply_to_bot):
            self.logger.info(
                "group_message_ignored",
                reason="no_mention_or_reply",
                user_id=user_id,
                chat_type=message.chat.type,
            )
            return

        url = self._extract_nakarte_url(text)
        if not url:
            self.logger.info(
                "message_ignored_no_nakarte_url",
                user_id=user_id,
                chat_type=message.chat.type,
            )
            if not self._is_group_chat(message):
                await message.answer(
                    "❌ Не вижу ссылки nakarte.me в сообщении.\n\n"
                    "Отправьте ссылку вида:\n"
                    "https://nakarte.me/#...&nktl=..."
                )
            return

        self.logger.info(
            "url_received",
            user_id=user_id,
            request_id=request_id,
            url=url,
        )

        # Validate URL
        if not self.nakarte_service.validate_url(url):
            self.logger.warning(
                "invalid_url",
                user_id=user_id,
                request_id=request_id,
                url=url,
            )
            await message.answer(
                "❌ Неверный формат ссылки!\n\n"
                "Пожалуйста, отправьте корректную ссылку с nakarte.me.\n\n"
                "Пример:\n"
                "https://nakarte.me/#m=15/41.69442/44.81043&l=O&nktl=FqYcC2069tzeSG-foUKGsA"
            )
            return

        # Extract track ID for cache key
        track_id = self.nakarte_service.extract_track_id(url)
        if not track_id:
            self.logger.error(
                "track_id_extraction_failed",
                user_id=user_id,
                request_id=request_id,
                url=url,
            )
            await message.answer(
                "❌ Не удалось извлечь идентификатор трека из ссылки.\n\n"
                "Убедитесь, что ссылка содержит параметр 'nktl'."
            )
            return

        # Send processing message
        processing_msg = await message.answer("⏳ Обрабатываю запрос...")

        try:
            # Check cache first
            cache_key = f"gpx:{track_id}"
            cached_gpx = await self.cache_service.get(cache_key)

            if cached_gpx:
                self.logger.info(
                    "cache_hit",
                    user_id=user_id,
                    request_id=request_id,
                    track_id=track_id,
                )
                gpx_data = cached_gpx
            else:
                self.logger.info(
                    "cache_miss",
                    user_id=user_id,
                    request_id=request_id,
                    track_id=track_id,
                )
                # Download GPX
                await processing_msg.edit_text("⏳ Загружаю трек с nakarte.me...")
                gpx_data = await self._download_gpx_singleflight(track_id, url)

                # Store in cache
                await self.cache_service.set(cache_key, gpx_data, self.cache_ttl)

            # Build friendly filename from GPX metadata
            filename = self.nakarte_service.build_filename_from_gpx(gpx_data, track_id)
            gpx_file = BufferedInputFile(gpx_data, filename=filename)

            await message.answer_document(
                document=gpx_file,
                caption=f"✅ Трек успешно загружен!\n\nФайл: {filename}",
            )

            # Delete processing message
            await processing_msg.delete()

            self.logger.info(
                "gpx_sent",
                user_id=user_id,
                request_id=request_id,
                track_id=track_id,
                size=len(gpx_data),
            )

        except ValueError as e:
            self.logger.error(
                "validation_error",
                user_id=user_id,
                request_id=request_id,
                error=str(e),
            )
            await processing_msg.edit_text(
                f"❌ Ошибка валидации: {str(e)}\n\n"
                "Проверьте правильность ссылки."
            )

        except RuntimeError as e:
            self.logger.error(
                "download_error",
                user_id=user_id,
                request_id=request_id,
                error=str(e),
            )
            await processing_msg.edit_text(
                "❌ Не удалось загрузить трек.\n\n"
                "Возможные причины:\n"
                "• Трек не найден на nakarte.me\n"
                "• Проблемы с доступом к сайту\n"
                "• Неверный формат данных\n\n"
                "Попробуйте позже или проверьте ссылку."
            )

        except Exception as e:
            self.logger.error(
                "unexpected_error",
                user_id=user_id,
                request_id=request_id,
                error=str(e),
            )
            await processing_msg.edit_text(
                "❌ Произошла непредвиденная ошибка.\n\n"
                "Пожалуйста, попробуйте позже."
            )
