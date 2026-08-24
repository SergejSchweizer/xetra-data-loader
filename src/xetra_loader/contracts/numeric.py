"""Exact decimal parsing and canonical numeric semantics for provider data."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def provider_decimal(value: object, *, field: str) -> Decimal:
    """Parse one provider scalar without accepting non-finite or structured values."""

    if value is None or value == "" or isinstance(value, (bool, list, dict)):
        raise ValueError(f"{field} must be numeric")
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    require_finite(decimal, field=field)
    return decimal


def require_finite(value: Decimal, *, field: str) -> None:
    """Reject NaN and either infinity before they reach semantic state."""

    if not value.is_finite():
        raise ValueError(f"{field} must be finite")


def canonical_decimal(value: Decimal) -> str:
    """Render semantically equal finite Decimals with one deterministic spelling."""

    require_finite(value, field="numeric value")
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
