import pytest

from src.services.stats_service import StatsService


@pytest.mark.asyncio
async def test_stats_service_summarizes_downloads_by_period(tmp_path):
    service = StatsService(db_path=str(tmp_path / "bot_stats.sqlite3"), cache_dir=str(tmp_path))
    now = 2_000_000.0

    await service.record_download(
        user_id=1,
        track_id="old",
        files_count=1,
        bytes_sent=100,
        cache_hit=False,
        created_at=now - 40 * 24 * 60 * 60,
    )
    await service.record_download(
        user_id=2,
        track_id="month",
        files_count=2,
        bytes_sent=200,
        cache_hit=True,
        created_at=now - 20 * 24 * 60 * 60,
    )
    await service.record_download(
        user_id=1,
        track_id="week",
        files_count=3,
        bytes_sent=300,
        cache_hit=False,
        created_at=now - 2 * 24 * 60 * 60,
    )

    summary = await service.get_summary(now=now)

    assert summary["users"]["total"] == 2
    assert summary["users"]["month"] == 2
    assert summary["users"]["week"] == 1
    assert summary["requests"]["total"] == 3
    assert summary["requests"]["month"] == 2
    assert summary["requests"]["week"] == 1
    assert summary["files"]["total"] == 6
    assert summary["files"]["month"] == 5
    assert summary["files"]["week"] == 3


@pytest.mark.asyncio
async def test_stats_service_reports_cache_size(tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "one.gpx").write_bytes(b"123")
    (cache_dir / "two.gpx").write_bytes(b"12345")
    (cache_dir / "one.json").write_text("{}", encoding="utf-8")
    service = StatsService(db_path=str(tmp_path / "bot_stats.sqlite3"), cache_dir=str(cache_dir))

    summary = await service.get_summary(now=2_000_000.0)

    assert summary["cache"]["files"] == 2
    assert summary["cache"]["bytes"] == 8
