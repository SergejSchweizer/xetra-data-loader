# xetra-data-loader

Deterministic XETRA market-data loader. The repository will own EODHD access, Bronze/Silver/Gold datasets, PostgreSQL publication, and the scheduled loader lifecycle defined in `BACKLOG.md`.

## Python setup

The repository is pinned to **CPython 3.14.7**.

```bash
python3.14 -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python --version           # must report Python 3.14.7
python -m pip install --upgrade pip
python -m pip install -e .
python -c "import xetra_data_loader; print(xetra_data_loader.__version__)"
```

The repository-local `.venv/` is intentionally ignored and must never be committed.

## Current scope

The initial repository baseline contains no provider, database, or business implementation. Those capabilities are introduced by the dependency-ordered work orders in `BACKLOG.md`.
