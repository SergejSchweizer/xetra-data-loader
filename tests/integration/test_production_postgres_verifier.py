import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from xetra_loader.contracts.corporate_actions import DividendEvent, SplitEvent
from xetra_loader.contracts.listings import ListingRecord
from xetra_loader.contracts.quotes import QuoteRecord
from xetra_loader.gold.dividends import build_dividend_gold
from xetra_loader.gold.listings import build_listing_gold
from xetra_loader.gold.quotes import build_quote_gold
from xetra_loader.gold.splits import build_split_gold
from xetra_loader.medallion.core import (
    JSONValue,
    Layer,
    Manifest,
    MedallionLayout,
    canonical_json,
)
from xetra_loader.ops.verify_postgres_sync import (
    DATASETS,
    DatasetVerification,
    ProductionAcceptanceReport,
    RoleVerification,
    TimestampVerification,
    load_gold_snapshots,
    semantic_fingerprint,
    write_production_report,
)

pytestmark = pytest.mark.integration


def _records() -> tuple[ListingRecord, QuoteRecord, DividendEvent, SplitEvent]:
    listing = ListingRecord(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        name="Fixture",
        instrument_type="ETF",
        currency="EUR",
        country="Germany",
    )
    quote = QuoteRecord(
        isin=listing.isin,
        exchange=listing.exchange,
        code=listing.code,
        trade_date=date(2026, 8, 21),
        open=Decimal("10"),
        high=Decimal("12"),
        low=Decimal("9"),
        close=Decimal("11"),
        adjusted_close=Decimal("11"),
        volume=100,
    )
    dividend = DividendEvent(
        isin=listing.isin,
        exchange=listing.exchange,
        code=listing.code,
        event_date=date(2026, 8, 20),
        value=Decimal("1.25"),
        currency="EUR",
    )
    split = SplitEvent(
        isin=listing.isin,
        exchange=listing.exchange,
        code=listing.code,
        event_date=date(2026, 8, 19),
        split_ratio="2:1",
        split_factor=Decimal("2"),
    )
    return listing, quote, dividend, split


def _write_dataset(
    layout: MedallionLayout,
    dataset: str,
    rows: list[dict[str, JSONValue]],
    fingerprint: str,
) -> None:
    for layer in (Layer.SILVER, Layer.GOLD):
        directory = layout.dataset_path(layer, dataset)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "data.json").write_text(
            canonical_json(rows),
            encoding="utf-8",
        )
    manifest = Manifest(
        dataset=dataset,
        layer=Layer.GOLD,
        semantic_metadata={
            "row_count": len(rows),
            "builder_semantic_fingerprint": fingerprint,
        },
        run_metadata={},
    )
    layout.manifest_path(Layer.GOLD, dataset).write_text(
        manifest.to_json(),
        encoding="utf-8",
    )


def test_gold_snapshot_recomputes_exact_builder_fingerprints(tmp_path: Path) -> None:
    listing, quote, dividend, split = _records()
    listing_gold = build_listing_gold([listing])
    quote_gold = build_quote_gold([quote])
    dividend_gold = build_dividend_gold([dividend])
    split_gold = build_split_gold([split])
    layout = MedallionLayout(tmp_path)

    rows_by_dataset = {
        "listings": (
            [dict(row) for row in listing_gold.semantic_rows()],
            listing_gold.semantic_fingerprint,
        ),
        "eod_quotes": (
            [dict(row) for row in quote_gold.semantic_rows()],
            quote_gold.semantic_fingerprint,
        ),
        "dividends": (
            [dict(row) for row in dividend_gold.semantic_rows()],
            dividend_gold.semantic_fingerprint,
        ),
        "splits": (
            [dict(row) for row in split_gold.semantic_rows()],
            split_gold.semantic_fingerprint,
        ),
    }
    for dataset, (rows, fingerprint) in rows_by_dataset.items():
        _write_dataset(layout, dataset, rows, fingerprint)
        assert semantic_fingerprint(dataset, rows) == fingerprint

    snapshots = load_gold_snapshots(tmp_path)
    assert tuple(snapshots) == DATASETS
    assert all(snapshot.source_count == 1 for snapshot in snapshots.values())
    assert all(snapshot.row_count == 1 for snapshot in snapshots.values())
    assert all(snapshot.fingerprint_valid for snapshot in snapshots.values())


def _passing_dataset() -> DatasetVerification:
    return DatasetVerification(
        source_count=1,
        gold_count=1,
        postgres_count=1,
        missing_keys=0,
        extra_keys=0,
        duplicate_keys=0,
        gold_fingerprint="a" * 64,
        postgres_fingerprint="a" * 64,
        gold_manifest_valid=True,
        gold_min_date="2026-08-21",
        gold_max_date="2026-08-21",
        postgres_min_date="2026-08-21",
        postgres_max_date="2026-08-21",
    )


def _passing_report() -> ProductionAcceptanceReport:
    return ProductionAcceptanceReport(
        target_host="10.10.1.3",
        target_port=54321,
        resolved_addresses=("10.10.1.3",),
        target_matches=True,
        initial_run_ids={dataset: f"run-{dataset}" for dataset in DATASETS},
        committed_runs={dataset: True for dataset in DATASETS},
        datasets={dataset: _passing_dataset() for dataset in DATASETS},
        orphan_counts={"eod_quotes": 0, "dividends": 0, "splits": 0},
        timestamps=TimestampVerification(
            session_timezone="UTC",
            checked_columns=("xetra_loader.listings.fetched_at_utc",),
            invalid_columns=(),
            missing_columns=(),
        ),
        role=RoleVerification(
            select_tables={dataset: True for dataset in DATASETS},
            insert_denied=True,
            update_denied=True,
            delete_denied=True,
            ddl_denied=True,
            sync_schema_select_denied=True,
        ),
        replay_mutations={dataset: 0 for dataset in DATASETS},
    )


def test_acceptance_report_is_sanitized_and_fails_closed(tmp_path: Path) -> None:
    passing = _passing_report()
    assert passing.passed
    output = write_production_report(passing, tmp_path / "report.json")
    text = output.read_text(encoding="utf-8")
    decoded = json.loads(text)
    assert decoded["status"] == "PASS"
    assert "password" not in text.lower()
    assert "dsn" not in text.lower()
    assert "api_token" not in text.lower()

    failing = ProductionAcceptanceReport(
        target_host=passing.target_host,
        target_port=passing.target_port,
        resolved_addresses=passing.resolved_addresses,
        target_matches=passing.target_matches,
        initial_run_ids=passing.initial_run_ids,
        committed_runs=passing.committed_runs,
        datasets={
            **passing.datasets,
            "eod_quotes": replace(_passing_dataset(), missing_keys=1),
        },
        orphan_counts=passing.orphan_counts,
        timestamps=passing.timestamps,
        role=passing.role,
        replay_mutations=passing.replay_mutations,
    )
    assert not failing.passed
