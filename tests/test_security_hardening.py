import sys
import types

import pytest

from test_bot_handlers import (
    BotHandlers,
    FakeCacheService,
    FakeHugeNakarteService,
    FakeMessage,
    FakeMultiFileNakarteService,
)
from src.services.nakarte_service import NakarteService

sys.modules.setdefault(
    "aiogram.client.default",
    types.SimpleNamespace(DefaultBotProperties=lambda *args, **kwargs: object()),
)
sys.modules.setdefault(
    "aiogram.enums",
    types.SimpleNamespace(ParseMode=types.SimpleNamespace(HTML="HTML")),
)


@pytest.mark.asyncio
async def test_download_is_rejected_when_user_rate_limit_is_exceeded():
    nakarte_service = FakeMultiFileNakarteService()
    handlers = BotHandlers(
        nakarte_service,
        FakeCacheService(),
        rate_limit_requests=1,
        rate_limit_window_seconds=60,
    )

    await handlers.handle_url(FakeMessage(user_id=77))
    second_message = FakeMessage(user_id=77)
    await handlers.handle_url(second_message)

    assert nakarte_service.download_calls == 1
    assert any("Слишком много запросов" in answer for answer in second_message.answers)


@pytest.mark.asyncio
async def test_download_is_rejected_when_payload_is_too_large():
    handlers = BotHandlers(
        FakeHugeNakarteService(),
        FakeCacheService(),
        max_gpx_bytes=10,
    )
    message = FakeMessage(user_id=77)

    await handlers.handle_url(message)

    assert message.documents == []


def test_request_allowlist_rejects_private_network_targets():
    service = NakarteService()

    assert service.is_allowed_request_url("https://nakarte.me/")
    assert service.is_allowed_request_url("https://tracks.nakarte.me/track/abc")
    assert not service.is_allowed_request_url("http://127.0.0.1:8000/")
    assert not service.is_allowed_request_url("http://169.254.169.254/latest/meta-data/")
    assert not service.is_allowed_request_url("file:///etc/passwd")


def test_admin_user_ids_parser_ignores_invalid_tokens():
    from src.main import Application

    assert Application._parse_admin_user_ids("123,abc, 456") == {123, 456}
