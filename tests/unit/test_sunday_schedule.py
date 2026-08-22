from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CRON_PATH = Path("deploy/cron/xetra-data-loader.cron")


def test_cron_contract_is_exact_sunday_1100_vienna() -> None:
    lines = CRON_PATH.read_text(encoding="utf-8").splitlines()

    assert lines[0] == "CRON_TZ=Europe/Vienna"
    assert lines[1].startswith("0 11 * * 0 ")
    assert "xdl-weekly" in lines[1]


def test_vienna_1100_remains_local_1100_across_dst() -> None:
    vienna = ZoneInfo("Europe/Vienna")
    winter = datetime(2026, 1, 11, 11, 0, tzinfo=vienna)
    summer = datetime(2026, 7, 12, 11, 0, tzinfo=vienna)

    assert winter.weekday() == 6
    assert summer.weekday() == 6
    assert winter.hour == summer.hour == 11
    assert winter.utcoffset().total_seconds() == 3600
    assert summer.utcoffset().total_seconds() == 7200
