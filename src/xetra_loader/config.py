"""Secret-aware configuration loaded from an ignored YAML file or the environment."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

import yaml


class ConfigurationError(ValueError):
    """Raised when the configured loader values are missing or malformed."""


@dataclass(frozen=True, slots=True)
class FileConfiguration:
    """Raw configuration sections read from one YAML file."""

    values: Mapping[str, Any]
    path: Path


def load_file_configuration(path: Path | None = None) -> FileConfiguration:
    """Load YAML without exposing its values in exceptions or log output."""

    configured_path = path or Path(os.getenv("XDL_CONFIG_FILE", "config.yaml"))
    if not configured_path.exists():
        return FileConfiguration({}, configured_path)
    try:
        decoded = yaml.safe_load(configured_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(f"unable to read configuration file: {configured_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML configuration: {configured_path}") from exc
    if decoded is None:
        return FileConfiguration({}, configured_path)
    if not isinstance(decoded, Mapping):
        raise ConfigurationError("configuration root must be a YAML mapping")
    return FileConfiguration(cast(Mapping[str, Any], decoded), configured_path)


def resolve_eodhd_token(explicit: str | None = None) -> str:
    """Resolve the EODHD token, preferring explicit and environment values."""

    token = explicit or os.getenv("EODHD_API_TOKEN")
    if not token:
        section = _section(load_file_configuration().values, "eodhd")
        token = _string(section, "api_token")
    if not token or not token.strip():
        raise ValueError("EODHD_API_TOKEN is required")
    return token.strip()


def resolve_postgres_writer_dsn(explicit: str | None = None) -> str:
    """Resolve the least-privilege weekly writer DSN without exposing its secret."""

    dsn = explicit or os.getenv("XDL_POSTGRES_WRITER_DSN") or os.getenv("XDL_POSTGRES_DSN")
    if dsn and dsn.strip():
        return dsn.strip()

    section = _section(load_file_configuration().values, "postgres")
    configured_dsn = _string(section, "writer_dsn") or _string(section, "dsn")
    if configured_dsn:
        return configured_dsn

    host = _string(section, "host")
    user = _string(section, "user")
    password = _string(section, "password")
    port = _port(section.get("port", 5432))
    database = _string(section, "database")
    if not host or not user or not password:
        raise ValueError("XDL_POSTGRES_WRITER_DSN is required")
    authority = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    suffix = f"/{quote(database, safe='')}" if database else ""
    return f"postgresql://{authority}{suffix}"


def resolve_postgres_admin_dsn(explicit: str | None = None) -> str:
    """Resolve the explicit privileged DSN used only for bootstrap and migrations."""

    dsn = explicit or os.getenv("XDL_POSTGRES_ADMIN_DSN")
    if dsn and dsn.strip():
        return dsn.strip()
    configured = _string(_section(load_file_configuration().values, "postgres"), "admin_dsn")
    if configured and configured.strip():
        return configured.strip()
    raise ValueError("XDL_POSTGRES_ADMIN_DSN is required for bootstrap or migrations")


def resolve_postgres_dsn(explicit: str | None = None) -> str:
    """Backward-compatible alias for the normal least-privilege writer resolver."""

    return resolve_postgres_writer_dsn(explicit)


def resolve_medallion_root(explicit: str | None = None) -> str:
    """Resolve the local Bronze/Silver/Gold root."""

    root = explicit or os.getenv("XDL_MEDALLION_ROOT")
    if not root:
        root = _string(_section(load_file_configuration().values, "medallion"), "root")
    if not root or not root.strip():
        raise ValueError("XDL_MEDALLION_ROOT is required")
    return root.strip()


def _section(values: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    section = values.get(name)
    return cast(Mapping[str, Any], section) if isinstance(section, Mapping) else {}


def _string(values: Mapping[str, Any], name: str) -> str | None:
    value = values.get(name)
    return value if isinstance(value, str) else None


def _port(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigurationError("postgres.port must be an integer between 1 and 65535")
    return value
