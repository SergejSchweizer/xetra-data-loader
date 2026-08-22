from datetime import UTC, date, datetime
from decimal import Decimal

from xetra_data_loader.contracts.corporate_actions import (
    ActionStatus,
    CorporateActionRunMetadata,
    DividendEvent,
    SplitEvent,
    retract_dividend,
    retract_split,
)


def _dividend(value: str = "1.25") -> DividendEvent:
    return DividendEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 1),
        value=Decimal(value),
        currency="EUR",
        period="Annual",
    )


def _split(ratio: str = "2:1") -> SplitEvent:
    return SplitEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 2),
        split_ratio=ratio,
        split_factor=Decimal("2"),
    )


def test_same_business_event_has_same_event_key() -> None:
    assert _dividend().event_key == _dividend().event_key
    assert _split().event_key == _split().event_key


def test_changed_business_field_changes_event_key() -> None:
    assert _dividend("1.25").event_key != _dividend("1.30").event_key
    assert _split("2:1").event_key != _split("3:1").event_key


def test_retraction_preserves_event_key_and_changes_only_status() -> None:
    dividend = _dividend()
    split = _split()
    retracted_dividend = retract_dividend(dividend)
    retracted_split = retract_split(split)
    assert retracted_dividend.event_key == dividend.event_key
    assert retracted_split.event_key == split.event_key
    assert retracted_dividend.status is ActionStatus.RETRACTED
    assert retracted_split.status is ActionStatus.RETRACTED


def test_run_metadata_is_excluded_from_event_key() -> None:
    event = _dividend()
    key = event.event_key
    CorporateActionRunMetadata("run-a", datetime(2026, 8, 22, 10, 0, tzinfo=UTC))
    CorporateActionRunMetadata("run-b", datetime(2026, 8, 22, 11, 0, tzinfo=UTC))
    assert event.event_key == key


def test_dividend_and_split_namespaces_are_distinct() -> None:
    dividend = DividendEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 1),
        value=Decimal("2"),
    )
    split = SplitEvent(
        isin="DE0000000001",
        exchange="XETRA",
        code="AAA",
        event_date=date(2026, 8, 1),
        split_ratio="2",
        split_factor=Decimal("2"),
    )
    assert dividend.event_key != split.event_key
