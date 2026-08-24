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

For an existing PostgreSQL installation, run the migrations in `sql/migrations/` in order
with an administrative connection before starting the renamed loader. They preserve the
existing loader data while renaming the role to `xetra-loader` and the schemas to
`xetra_loader` and `xetra_loader_sync`.

## Local secrets

Copy `config.example.yaml` to `config.yaml` and fill in the EODHD token plus separate PostgreSQL writer and admin credentials. `postgres.writer_dsn` (or `XDL_POSTGRES_WRITER_DSN`) is used by the weekly runner and must authenticate as the non-superuser `xetra_data_loader_writer`; the runner rejects superuser sessions. `postgres.admin_dsn` (or `XDL_POSTGRES_ADMIN_DSN`) is required only for schema provisioning, migration, reset, and the controlled full bootstrap. The loader reads this ignored local file; never commit it. `EODHD_API_TOKEN` and `XDL_MEDALLION_ROOT` can still be provided through the environment.

## Current scope

The dependency-ordered work orders in `BACKLOG.md` provide the EODHD transport, XETRA listing and corporate-action ingestion, Bronze/Silver/Gold datasets, transactional PostgreSQL publication, weekly orchestration, guarded bootstrap, and acceptance verification. The real-target acceptance run remains an operational deployment step and requires valid access to the configured PostgreSQL instance.
