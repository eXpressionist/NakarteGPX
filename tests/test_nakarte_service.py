import sys
import types


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

from src.services.nakarte_service import NakarteService


def test_split_multitrack_gpx_returns_one_file_per_track():
    service = NakarteService()
    gpx = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <time>2026-05-04T00:00:00Z</time>
  </metadata>
  <trk>
    <name>First</name>
    <trkseg><trkpt lat="1" lon="2"></trkpt></trkseg>
  </trk>
  <trk>
    <name>Second</name>
    <trkseg><trkpt lat="3" lon="4"></trkpt></trkseg>
  </trk>
</gpx>"""

    files = service.split_gpx_files(gpx.encode("utf-8"), "track123")

    assert [file.filename for file in files] == ["First.gpx", "Second.gpx"]
    assert all(file.data.decode("utf-8").count("<trk>") == 1 for file in files)
