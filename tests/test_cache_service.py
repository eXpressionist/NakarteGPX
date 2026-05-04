import sys
import types

import pytest

structlog_stub = types.SimpleNamespace(
    BoundLogger=object,
    configure=lambda *args, **kwargs: None,
    get_logger=lambda name=None: types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    ),
    processors=types.SimpleNamespace(
        TimeStamper=lambda *args, **kwargs: None,
        StackInfoRenderer=lambda *args, **kwargs: None,
        format_exc_info=lambda *args, **kwargs: None,
        JSONRenderer=lambda *args, **kwargs: None,
    ),
    stdlib=types.SimpleNamespace(
        LoggerFactory=lambda *args, **kwargs: None,
        add_log_level=lambda *args, **kwargs: None,
        add_logger_name=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault("structlog", structlog_stub)
sys.modules.setdefault(
    "structlog.types",
    types.SimpleNamespace(EventDict=dict, Processor=object),
)

import src.services.cache_service as cache_module
from src.services.cache_service import FileCache, create_cache_service


def test_create_cache_service_defaults_to_file_cache():
    cache = create_cache_service()

    assert isinstance(cache, FileCache)


@pytest.mark.asyncio
async def test_file_cache_set_does_not_require_ttl(tmp_path):
    cache = FileCache(cache_dir=str(tmp_path))

    await cache.set("gpx:track", b"<gpx />")

    assert await cache.get("gpx:track") == b"<gpx />"


@pytest.mark.asyncio
async def test_file_cache_respects_ttl(tmp_path, monkeypatch):
    current_time = 1000.0
    monkeypatch.setattr(cache_module.time, "time", lambda: current_time)
    cache = FileCache(cache_dir=str(tmp_path))

    await cache.set("gpx:track", b"<gpx />", ttl=10)

    assert await cache.get("gpx:track") == b"<gpx />"

    current_time = 1011.0

    assert await cache.get("gpx:track") is None


@pytest.mark.asyncio
async def test_file_cache_prunes_oldest_files_when_size_limit_is_exceeded(tmp_path):
    cache = FileCache(cache_dir=str(tmp_path), max_cache_bytes=10)

    await cache.set("gpx:first", b"123456")
    await cache.set("gpx:second", b"abcdef")

    assert await cache.get("gpx:first") is None
    assert await cache.get("gpx:second") == b"abcdef"
