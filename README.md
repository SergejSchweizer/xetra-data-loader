# xetra-loader

Deterministic XETRA market-data loader. The repository will own EODHD access, Bronze/Silver/Gold datasets, PostgreSQL publication, and the scheduled loader lifecycle defined in `BACKLOG.md`.

## Python setup

The repository is pinned to **CPython 3.14.7**.

```bash
python3.14 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python --version           # must report Python 3.14.7
python -m pip install --upgrade pip
python -m pip install -e .
python -c "import xetra_loader; print(xetra_loader.__version__)"
```

The repository-local `.venv/` is intentionally ignored and must never be committed.

For an existing PostgreSQL installation, run `sql/migrations/001_rename_to_xetra_loader.sql`
once with an administrative connection before starting the renamed loader. It preserves the
existing loader data while renaming the role to `xetra-loader` and the schemas to
`xetra_market` and `xetra_loader_sync`.

## Local secrets

Copy `config.example.yaml` to `config.yaml` and fill in the EODHD token and PostgreSQL credentials. The loader reads this file for bootstrap and database connections; `config.yaml` is ignored by Git and must remain local. Environment variables (`EODHD_API_TOKEN`, `XDL_POSTGRES_DSN`, and `XDL_MEDALLION_ROOT`) still override the corresponding file values.

## Current scope

The dependency-ordered work orders in `BACKLOG.md` provide the EODHD transport, XETRA listing and corporate-action ingestion, Bronze/Silver/Gold datasets, transactional PostgreSQL publication, weekly orchestration, guarded bootstrap, and acceptance verification. The real-target acceptance run remains an operational deployment step and requires valid access to the configured PostgreSQL instance.
