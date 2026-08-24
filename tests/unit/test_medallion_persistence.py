"""Filesystem contracts for atomic, partitioned medallion persistence."""

import json
from pathlib import Path

import pytest

import xetra_loader.medallion.core as medallion_core
from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.medallion.core import Layer, MedallionLayout, atomic_write_text
from xetra_loader.ops.bootstrap import PostgresEodhdBootstrapRuntime


def test_atomic_write_failure_preserves_last_committed_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "gold" / "quotes" / "data.json"
    atomic_write_text(target, "old\n")

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("injected replace failure")

    monkeypatch.setattr(medallion_core.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert not list(target.parent.glob(".data.json.*.tmp"))


def test_partition_finalization_is_deterministic_and_bounded(tmp_path: Path) -> None:
    runtime = object.__new__(PostgresEodhdBootstrapRuntime)
    runtime._layout = MedallionLayout(tmp_path)
    first = ListingRecord(isin="DE0000000002", exchange="XETRA", code="BBB")
    second = ListingRecord(isin="DE0000000001", exchange="XETRA", code="AAA")

    runtime._write_partition(
        Layer.SILVER,
        "eod_quotes",
        first,
        [{"code": "BBB", "trade_date": "2026-08-22"}],
    )
    runtime._write_partition(
        Layer.SILVER,
        "eod_quotes",
        second,
        [{"code": "AAA", "trade_date": "2026-08-21"}],
    )
    runtime._finalize_partitions("eod_quotes")

    data = tmp_path / "silver" / "eod_quotes" / "data.json"
    assert json.loads(data.read_text(encoding="utf-8")) == [
        {"code": "AAA", "trade_date": "2026-08-21"},
        {"code": "BBB", "trade_date": "2026-08-22"},
    ]
    assert len(list((tmp_path / "silver" / "eod_quotes" / "partitions").glob("*.json"))) == 2
