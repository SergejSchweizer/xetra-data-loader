from pathlib import Path

import pytest

from xetra_data_loader.medallion import Layer, Manifest, MedallionLayout


def test_layout_resolves_each_layer() -> None:
    layout = MedallionLayout(Path("/data/xetra"))
    assert layout.dataset_path(Layer.BRONZE, "listings") == Path("/data/xetra/bronze/listings")
    assert layout.dataset_path(Layer.SILVER, "quotes") == Path("/data/xetra/silver/quotes")
    assert layout.manifest_path(Layer.GOLD, "splits") == Path(
        "/data/xetra/gold/splits/manifest.json"
    )


@pytest.mark.parametrize("dataset", ["", ".", "..", "../quotes", "nested/quotes", "nested\\quotes"])
def test_layout_rejects_invalid_dataset_path(dataset: str) -> None:
    with pytest.raises(ValueError):
        MedallionLayout(Path("/data/xetra")).dataset_path(Layer.GOLD, dataset)


def test_semantic_fingerprint_ignores_run_metadata() -> None:
    first = Manifest(
        dataset="quotes",
        layer=Layer.GOLD,
        semantic_metadata={"rows": 10, "max_trade_date": "2026-08-21"},
        run_metadata={"run_id": "a", "fetched_at": "2026-08-22T10:00:00Z"},
    )
    second = Manifest(
        dataset="quotes",
        layer=Layer.GOLD,
        semantic_metadata={"max_trade_date": "2026-08-21", "rows": 10},
        run_metadata={"run_id": "b", "fetched_at": "2026-08-22T11:00:00Z"},
    )
    assert first.semantic_fingerprint() == second.semantic_fingerprint()
    assert first.to_json() != second.to_json()


def test_semantic_change_changes_fingerprint() -> None:
    base = Manifest("listings", Layer.GOLD, {"rows": 2}, {"run_id": "a"})
    changed = Manifest("listings", Layer.GOLD, {"rows": 3}, {"run_id": "a"})
    assert base.semantic_fingerprint() != changed.semantic_fingerprint()
