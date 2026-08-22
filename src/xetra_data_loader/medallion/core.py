"""Deterministic Bronze/Silver/Gold layout and manifest primitives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping


type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]


class Layer(StrEnum):
    """Supported medallion layers."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


@dataclass(frozen=True, slots=True)
class MedallionLayout:
    """Resolve dataset paths without allowing traversal outside the configured root."""

    root: Path

    def dataset_path(self, layer: Layer, dataset: str) -> Path:
        _validate_component(dataset)
        return self.root / layer.value / dataset

    def manifest_path(self, layer: Layer, dataset: str) -> Path:
        return self.dataset_path(layer, dataset) / "manifest.json"


@dataclass(frozen=True, slots=True)
class Manifest:
    """Separate semantic dataset identity from execution-only metadata."""

    dataset: str
    layer: Layer
    semantic_metadata: Mapping[str, JSONValue]
    run_metadata: Mapping[str, JSONValue]

    def semantic_fingerprint(self) -> str:
        payload: dict[str, JSONValue] = {
            "dataset": self.dataset,
            "layer": self.layer.value,
            "semantic_metadata": dict(self.semantic_metadata),
        }
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        payload: dict[str, JSONValue] = {
            "dataset": self.dataset,
            "layer": self.layer.value,
            "semantic_fingerprint": self.semantic_fingerprint(),
            "semantic_metadata": dict(self.semantic_metadata),
            "run_metadata": dict(self.run_metadata),
        }
        return canonical_json(payload)


def canonical_json(value: JSONValue) -> str:
    """Serialize JSON deterministically for stable fingerprints and manifests."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_component(value: str) -> None:
    if not value or value in {".", ".."}:
        raise ValueError("dataset path component must be non-empty and relative")
    if Path(value).name != value or "/" in value or "\\" in value:
        raise ValueError("dataset path component must not contain path separators")
