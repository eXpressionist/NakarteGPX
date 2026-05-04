"""Telegram bot handlers."""

import asyncio
import hashlib
import json
import re
import time
import uuid
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BufferedInputFile
from structlog import BoundLogger

from src.services.cache_service import CacheService
from src.services.nakarte_service import GpxFile, NakarteService
from src.services.stats_service import StatsService
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
        stats_service: Optional[StatsService] = None,
        admin_user_ids: Optional[set[int]] = None,
        rate_limit_requests: int = 5,
        rate_limit_window_seconds: int = 60,
        max_pending_downloads: int = 10,
        max_gpx_files: int = 20,
        max_gpx_bytes: int = 20 * 1024 * 1024,
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
        self.stats_service = stats_service
        self.admin_user_ids = admin_user_ids or set()
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.max_pending_downloads = max_pending_downloads
        self.max_gpx_files = max_gpx_files
        self.max_gpx_bytes = max_gpx_bytes
        self._download_semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self._inflight_downloads: dict[str, asyncio.Task[list[GpxFile]]] = {}
        self._inflight_lock = asyncio.Lock()
        self._pending_downloads = 0
        self._rate_limit_hits: dict[int, list[float]] = {}
        self.logger = logger or get_logger(__name__)

    @staticmethod
    def _safe_hash(value: object) -> str:
        """Short stable hash for sensitive values in logs."""
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]

    def _check_rate_limit(self, user_id: int | str) -> bool:
        """Return True when the user is still within the request budget."""
        if not isinstance(user_id, int) or self.rate_limit_requests <= 0:
            return True

        now = time.monotonic()
        window_start = now - self.rate_limit_window_seconds
        hits = [
            timestamp
            for timestamp in self._rate_limit_hits.get(user_id, [])
            if timestamp >= window_start
        ]
        if len(hits) >= self.rate_limit_requests:
            self._rate_limit_hits[user_id] = hits
            return False

        hits.append(now)
        self._rate_limit_hits[user_id] = hits
        return True

    async def _download_uncached_gpx_files(self, url: str) -> list[GpxFile]:
        """Run expensive GPX extraction with bounded concurrency."""
        if self._pending_downloads >= self.max_pending_downloads:
            raise RuntimeError("Too many downloads are queued")

        self._pending_downloads += 1
        try:
            async with self._download_semaphore:
                if hasattr(self.nakarte_service, "download_gpx_files"):
                    return await self.nakarte_service.download_gpx_files(url)

                gpx_data = await self.nakarte_service.download_gpx(url)
                track_id = self.nakarte_service.extract_track_id(url)
                filename = self.nakarte_service.build_filename_from_gpx(gpx_data, track_id)
                return [GpxFile(data=gpx_data, filename=filename)]
        finally:
            self._pending_downloads -= 1

    async def _download_gpx_singleflight(self, track_id: str, url: str) -> bytes:
        """Share one in-progress download for identical track IDs."""
        files = await self._download_gpx_files_singleflight(track_id, url)
        return files[0].data

    async def _download_gpx_files_singleflight(
        self,
        track_id: str,
        url: str,
    ) -> list[GpxFile]:
        """Share one in-progress multi-file download for identical track IDs."""
        created_task = False
        async with self._inflight_lock:
            task = self._inflight_downloads.get(track_id)
            if task is None:
                task = asyncio.create_task(self._download_uncached_gpx_files(url))
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

    @staticmethod
    def _encode_gpx_files(files: list[GpxFile]) -> bytes:
        """Encode multiple GPX files for byte-oriented cache backends."""
        payload = [
            {
                "filename": file.filename,
                "data": file.data.decode("utf-8"),
            }
            for file in files
        ]
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _decode_gpx_files(payload: bytes) -> Optional[list[GpxFile]]:
        """Decode cached multi-file GPX payload."""
        try:
            raw_files = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(raw_files, list):
            return None

        files = []
        for raw_file in raw_files:
            if not isinstance(raw_file, dict):
                return None
            filename = raw_file.get("filename")
            data = raw_file.get("data")
            if not isinstance(filename, str) or not isinstance(data, str):
                return None
            files.append(GpxFile(data=data.encode("utf-8"), filename=filename))
        return files

    def _validate_gpx_files(self, files: list[GpxFile]) -> None:
        """Reject oversized responses before caching or sending."""
        total_bytes = sum(len(file.data) for file in files)
        if len(files) > self.max_gpx_files:
            raise RuntimeError("Too many GPX files in one response")
        if total_bytes > self.max_gpx_bytes:
            raise RuntimeError("GPX response is too large")

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format byte count for admin stats."""
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{value:.1f} GB"

    def _is_admin(self, message: Message) -> bool:
        """Check whether message sender can use admin commands."""
        user_id = message.from_user.id if message.from_user else None
        return isinstance(user_id, int) and user_id in self.admin_user_ids

    async def _record_download_stats(
        self,
        user_id: int | str,
        track_id: str,
        gpx_files: list[GpxFile],
        cache_hit: bool,
    ) -> None:
        """Record successful download without breaking user flow on stats errors."""
        if not self.stats_service or not isinstance(user_id, int):
            return

        try:
            await self.stats_service.record_download(
                user_id=user_id,
                track_id=track_id,
                files_count=len(gpx_files),
                bytes_sent=sum(len(file.data) for file in gpx_files),
                cache_hit=cache_hit,
            )
        except Exception as e:
            self.logger.error(
                "stats_record_error",
                user_hash=self._safe_hash(user_id),
                track_hash=self._safe_hash(track_id),
                error=str(e),
            )

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
        dp.message.register(self.cmd_stats, Command("stats"))
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

    async def cmd_stats(self, message: Message) -> None:
        """Handle admin /stats command."""
        user_id = message.from_user.id if message.from_user else "unknown"
        user_hash = self._safe_hash(user_id)
        self.logger.info("command_stats", user_hash=user_hash)

        if not self._is_admin(message):
            self.logger.warning("stats_access_denied", user_hash=user_hash)
            if not self._is_group_chat(message):
                await message.answer("Нет доступа к статистике.")
            return

        if not self.stats_service:
            await message.answer("Статистика не настроена.")
            return

        summary = await self.stats_service.get_summary()
        cache_size = self._format_bytes(summary["cache"]["bytes"])

        await message.answer(
            "Статистика бота\n\n"
            "Пользователи:\n"
            f"Всего: {summary['users']['total']}\n"
            f"За 30 дней: {summary['users']['month']}\n"
            f"За 7 дней: {summary['users']['week']}\n\n"
            "Загрузки:\n"
            f"Запросов всего: {summary['requests']['total']}\n"
            f"GPX файлов всего: {summary['files']['total']}\n"
            f"За 30 дней: {summary['requests']['month']} запросов, "
            f"{summary['files']['month']} файлов\n"
            f"За 7 дней: {summary['requests']['week']} запросов, "
            f"{summary['files']['week']} файлов\n\n"
            "Кэш:\n"
            f"Файлов: {summary['cache']['files']}\n"
            f"Размер: {cache_size}"
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
        user_hash = self._safe_hash(user_id)
        request_id = str(uuid.uuid4())
        text = message.text.strip()
        self.logger.info(
            "message_received",
            chat_type=message.chat.type,
            user_hash=user_hash,
            has_entities=bool(message.entities),
            text_length=len(text),
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
                user_hash=user_hash,
                chat_type=message.chat.type,
            )
            return

        url = self._extract_nakarte_url(text)
        if not url:
            self.logger.info(
                "message_ignored_no_nakarte_url",
                user_hash=user_hash,
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
            user_hash=user_hash,
            request_id=request_id,
        )

        # Validate URL
        if not self.nakarte_service.validate_url(url):
            self.logger.warning(
                "invalid_url",
                user_hash=user_hash,
                request_id=request_id,
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
        track_hash = self._safe_hash(track_id)
        if not track_id:
            self.logger.error(
                "track_id_extraction_failed",
                user_hash=user_hash,
                request_id=request_id,
            )
            await message.answer(
                "❌ Не удалось извлечь идентификатор трека из ссылки.\n\n"
                "Убедитесь, что ссылка содержит параметр 'nktl'."
            )
            return

        if not self._check_rate_limit(user_id):
            self.logger.warning(
                "rate_limit_exceeded",
                user_hash=user_hash,
                request_id=request_id,
            )
            await message.answer("Слишком много запросов. Попробуйте позже.")
            return

        # Send processing message
        processing_msg = await message.answer("⏳ Обрабатываю запрос...")

        try:
            # Check cache first
            cache_key = f"gpx:{track_id}"
            cached_gpx = await self.cache_service.get(cache_key)

            if cached_gpx:
                cache_hit = True
                self.logger.info(
                    "cache_hit",
                    user_hash=user_hash,
                    request_id=request_id,
                    track_hash=track_hash,
                )
                cached_files = self._decode_gpx_files(cached_gpx)
                if cached_files is None:
                    filename = self.nakarte_service.build_filename_from_gpx(cached_gpx, track_id)
                    gpx_files = [GpxFile(data=cached_gpx, filename=filename)]
                else:
                    gpx_files = cached_files
            else:
                cache_hit = False
                self.logger.info(
                    "cache_miss",
                    user_hash=user_hash,
                    request_id=request_id,
                    track_hash=track_hash,
                )
                # Download GPX
                await processing_msg.edit_text("⏳ Загружаю трек с nakarte.me...")
                gpx_files = await self._download_gpx_files_singleflight(track_id, url)
                self._validate_gpx_files(gpx_files)

                # Store in cache
                await self.cache_service.set(
                    cache_key,
                    self._encode_gpx_files(gpx_files),
                    self.cache_ttl,
                )

            for index, file in enumerate(gpx_files, 1):
                self._validate_gpx_files(gpx_files)
                gpx_file = BufferedInputFile(file.data, filename=file.filename)
                caption = (
                    f"✅ Трек успешно загружен!\n\nФайл: {file.filename}"
                    if len(gpx_files) == 1
                    else f"✅ Трек {index}/{len(gpx_files)}\n\nФайл: {file.filename}"
                )

                await message.answer_document(document=gpx_file, caption=caption)

            # Delete processing message
            await processing_msg.delete()

            self.logger.info(
                "gpx_sent",
                user_hash=user_hash,
                request_id=request_id,
                track_hash=track_hash,
                files=len(gpx_files),
                size=sum(len(file.data) for file in gpx_files),
            )
            await self._record_download_stats(user_id, track_id, gpx_files, cache_hit)

        except ValueError as e:
            self.logger.error(
                "validation_error",
                user_hash=user_hash,
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
                user_hash=user_hash,
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
                user_hash=user_hash,
                request_id=request_id,
                error=str(e),
            )
            await processing_msg.edit_text(
                "❌ Произошла непредвиденная ошибка.\n\n"
                "Пожалуйста, попробуйте позже."
            )
