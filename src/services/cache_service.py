"""Cache service for storing GPX files."""

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from structlog import BoundLogger

from src.utils.logger import get_logger


class CacheService(ABC):
    """Abstract cache service interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close cache connection."""
        pass


class RedisCache(CacheService):
    """Redis-based cache implementation."""

    def __init__(
        self,
        host: str,
        port: int,
        db: int,
        password: Optional[str] = None,
        logger: Optional[BoundLogger] = None,
    ):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            logger: Logger instance
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.logger = logger or get_logger(__name__)
        self._client = None

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis
            except ImportError as exc:
                raise RuntimeError(
                    "Redis cache requires the 'redis' package to be installed"
                ) from exc

            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password if self.password else None,
                decode_responses=False,
            )
            self.logger.info("redis_connected", host=self.host, port=self.port)
        return self._client

    async def get(self, key: str) -> Optional[bytes]:
        """Get value from Redis cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                self.logger.info("cache_hit", key=key)
            else:
                self.logger.info("cache_miss", key=key)
            return value
        except Exception as e:
            self.logger.error("cache_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> None:
        """Set value in Redis cache with TTL."""
        try:
            client = await self._get_client()
            if ttl is None:
                await client.set(key, value)
            else:
                await client.setex(key, ttl, value)
            self.logger.info("cache_set", key=key, ttl=ttl)
        except Exception as e:
            self.logger.error("cache_set_error", key=key, error=str(e))

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis cache."""
        try:
            client = await self._get_client()
            result = await client.exists(key)
            return bool(result)
        except Exception as e:
            self.logger.error("cache_exists_error", key=key, error=str(e))
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self.logger.info("redis_closed")


class FileCache(CacheService):
    """File-based cache implementation."""

    def __init__(
        self,
        cache_dir: str = "./cache",
        logger: Optional[BoundLogger] = None,
    ):
        """
        Initialize file cache.
        
        Args:
            cache_dir: Directory to store cache files
            logger: Logger instance
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or get_logger(__name__)
        self.logger.info("file_cache_initialized", cache_dir=str(self.cache_dir))

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Use hash to create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.gpx"

    async def get(self, key: str) -> Optional[bytes]:
        """Get value from file cache."""
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                with open(file_path, "rb") as f:
                    value = f.read()
                self.logger.info("cache_hit", key=key, file=str(file_path))
                return value
            else:
                self.logger.info("cache_miss", key=key)
                return None
        except Exception as e:
            self.logger.error("cache_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> None:
        """Set value in file cache permanently."""
        try:
            file_path = self._get_file_path(key)
            with open(file_path, "wb") as f:
                f.write(value)
            self.logger.info("cache_set", key=key, file=str(file_path), ttl=ttl)
        except Exception as e:
            self.logger.error("cache_set_error", key=key, error=str(e))

    async def exists(self, key: str) -> bool:
        """Check if key exists in file cache."""
        try:
            file_path = self._get_file_path(key)
            return file_path.exists()
        except Exception as e:
            self.logger.error("cache_exists_error", key=key, error=str(e))
            return False

    async def close(self) -> None:
        """Close file cache (no-op for file-based cache)."""
        self.logger.info("file_cache_closed")


def create_cache_service(
    cache_type: str = "file",
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    redis_password: Optional[str] = None,
    cache_dir: str = "./cache",
    logger: Optional[BoundLogger] = None,
) -> CacheService:
    """
    Factory function to create cache service.
    
    Args:
        cache_type: Type of cache ('redis' or 'file')
        redis_host: Redis host (for redis cache)
        redis_port: Redis port (for redis cache)
        redis_db: Redis database number (for redis cache)
        redis_password: Redis password (for redis cache)
        cache_dir: Cache directory (for file cache)
        logger: Logger instance
        
    Returns:
        Cache service instance
    """
    if cache_type.lower() == "redis":
        return RedisCache(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            logger=logger,
        )
    else:
        return FileCache(cache_dir=cache_dir, logger=logger)
