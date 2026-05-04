import asyncio
import sys
import types

import pytest


class _FilterStub:
    text = object()


sys.modules.setdefault(
    "aiogram",
    types.SimpleNamespace(Bot=object, Dispatcher=object, F=_FilterStub()),
)
sys.modules.setdefault(
    "aiogram.filters",
    types.SimpleNamespace(
        Command=lambda *args, **kwargs: object(),
        CommandStart=lambda *args, **kwargs: object(),
    ),
)
sys.modules.setdefault(
    "aiogram.types",
    types.SimpleNamespace(
        Message=object,
        BufferedInputFile=lambda data, filename: types.SimpleNamespace(
            data=data,
            filename=filename,
        ),
    ),
)
sys.modules.setdefault("playwright", types.SimpleNamespace())
sys.modules.setdefault(
    "playwright.async_api",
    types.SimpleNamespace(
        Browser=object,
        Page=object,
        TimeoutError=TimeoutError,
        async_playwright=lambda *args, **kwargs: None,
    ),
)

structlog_stub = types.SimpleNamespace(
    BoundLogger=object,
    configure=lambda *args, **kwargs: None,
    get_logger=lambda name=None: types.SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
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

from src.bot.handlers import BotHandlers


class FakeNakarteService:
    def __init__(self):
        self.download_calls = 0

    def validate_url(self, url):
        return "nktl=track123" in url

    def extract_track_id(self, url):
        return "track123"

    async def download_gpx(self, url):
        self.download_calls += 1
        await asyncio.sleep(0.01)
        return b"<?xml version='1.0'?><gpx><trk><name>Track</name></trk></gpx>"

    def build_filename_from_gpx(self, gpx_data, track_id):
        return f"{track_id}.gpx"


class FakeMultiFileNakarteService(FakeNakarteService):
    async def download_gpx_files(self, url):
        self.download_calls += 1
        await asyncio.sleep(0.01)
        return [
            types.SimpleNamespace(
                data=b"<?xml version='1.0'?><gpx><trk><name>One</name></trk></gpx>",
                filename="One.gpx",
            ),
            types.SimpleNamespace(
                data=b"<?xml version='1.0'?><gpx><trk><name>Two</name></trk></gpx>",
                filename="Two.gpx",
            ),
        ]


class FakeCacheService:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ttl=None):
        self.values[key] = value


class FakeProcessingMessage:
    async def edit_text(self, text):
        self.text = text

    async def delete(self):
        self.deleted = True


class FakeMessage:
    def __init__(self):
        self.text = "https://nakarte.me/#m=1/2/3&nktl=track123"
        self.chat = types.SimpleNamespace(type="private")
        self.from_user = types.SimpleNamespace(id=42)
        self.entities = []
        self.reply_to_message = None
        self.documents = []

    async def answer(self, text):
        return FakeProcessingMessage()

    async def answer_document(self, document, caption):
        self.documents.append((document, caption))


@pytest.mark.asyncio
async def test_concurrent_same_track_downloads_once():
    nakarte_service = FakeNakarteService()
    cache_service = FakeCacheService()
    handlers = BotHandlers(nakarte_service, cache_service)

    await asyncio.gather(
        handlers.handle_url(FakeMessage()),
        handlers.handle_url(FakeMessage()),
    )

    assert nakarte_service.download_calls == 1


@pytest.mark.asyncio
async def test_multi_track_url_sends_each_gpx_as_separate_document():
    nakarte_service = FakeMultiFileNakarteService()
    cache_service = FakeCacheService()
    handlers = BotHandlers(nakarte_service, cache_service)
    message = FakeMessage()

    await handlers.handle_url(message)

    assert [document.filename for document, _ in message.documents] == [
        "One.gpx",
        "Two.gpx",
    ]
