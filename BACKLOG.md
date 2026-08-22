Last reviewed: 2026-08-22

# XETRA Data Loader Backlog

## 1. Status authority

This file is the active implementation authority for `SergejSchweizer/xetra-data-loader`.

The previous coarse loader work orders `PR297`-`PR307` are superseded by the repository-local `XDL-PR001`-`XDL-PR032` work orders below. The old IDs remain historical traceability only and must not be implemented as written.

Planning work order for this restructure:

- Work-order name: `xdl-pr000-backlog-restructure`
- Branch: `docs/xdl-pr000-backlog-restructure`
- Required commit: `docs(xdl-pr000-backlog-restructure): ...`
- Git status: planning branch exists; merge/validation pending

## 2. Frozen target architecture

```text
EODHD
  |
  v
xetra-data-loader
  Bronze -> Silver -> Gold
  |
  v
PostgreSQL 10.10.1.3:54321
  schemas:
    portfell_market
    portfell_loader_sync
  |
  | SELECT only through portfell_app
  v
portfell
```

`xetra-data-loader` owns provider access, XETRA discovery, market-data ingestion, medallion persistence, PostgreSQL publication, loader synchronization state, bootstrap/reset tooling, and the Sunday schedule. `portfell` is a read-only consumer and must not import this repository as a Python package.

Frozen invariants:

- initial universe = every EODHD XETRA listing with a normalized non-empty ISIN;
- listing identity = `(isin, exchange, code)`;
- quotes key = `(isin, exchange, code, trade_date)`;
- dividends/splits key = `(isin, exchange, code, event_key)`;
- `event_key` = deterministic SHA-256 over normalized provider business fields only;
- all PostgreSQL timestamps = exactly `TIMESTAMPTZ(6)`;
- PostgreSQL sessions = `UTC`;
- `trade_date` remains a `DATE` and `timestamp_eod` is the canonical `00:00:00+00:00` UTC anchor, not a physical XETRA close timestamp;
- weekly correction overlap = seven calendar days;
- unchanged source state = zero semantic PostgreSQL mutations;
- production endpoint `10.10.1.3:54321` is supplied by configuration, never by committed password/DSN;
- scheduler = exactly `CRON_TZ=Europe/Vienna` and `0 11 * * 0`;
- no portfolio analytics, Portfell UI, user/project runtime, or tenant logic belongs here.

## 3. Mandatory Git / CI contract

All implementation work orders must obey all of these rules:

1. Base every branch on the exact merged dependency SHA documented by the work order.
2. Before editing, record `git status --short --branch`.
3. The exact work-order name must appear literally in:
   - branch name;
   - every commit message on the branch;
   - PR title.
4. Every commit must use Conventional Commits.
5. Example:

```text
Work-order: xdl-pr015-eod-quote-ingestion
Branch:     feat/xdl-pr015-eod-quote-ingestion
Commit:     feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
PR title:   feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
```

6. Weak agents must not broaden scope, edit sibling-owned files, add compatibility shims, or branch from sibling branches.
7. Parallel siblings always start from the same predecessor merge SHA.
8. If a dependency is not merged, the work order remains blocked.
9. Each PR must run focused tests plus the repository push/merge quality gates on the same head SHA.
10. `main` may merge only through the protected-branch merge gate; auto-merge may complete only after every required check is green.

Repository engineering baseline:

- CPython `3.14.7` is the frozen stable runtime for this backlog revision;
- repository-local `.venv` is created from Python `3.14.7` and is never committed;
- `.python-version`, `pyproject.toml`, documentation, local setup, and CI use the same Python version;
- push and merge workflows run `lint`, `type`, `unit`, and `integration` as four independent parallel jobs;
- `policy` is a separate fast job;
- `push-gate` / `merge-gate` aggregate required outcomes;
- `main` requires `merge-gate`, rejects direct feature pushes, force pushes, and deletion;
- repository auto-merge is enabled after protection is established.

## 4. Dependency graph optimized for weak parallel agents

```text
XDL-PR000 planning gate
        |
      PR001
        |
   +----+----+
   |         |
 PR002     PR003
   |         |
   +----+----+
        |
   PR004 || PR005
        |
      PR006
        |
   +----+----------------------+------------------+
   |                           |                  |
 PR007                       PR009              PR013
   |                           |                  |
 PR008                PR010 || PR011 || PR012     |
   |                    |       |       |         |
   |                  PR014   PR015   PR016 || PR017
   |                    |       |       |       |
   |                  PR018   PR019   PR020   PR021
   |                    |       |       |       |
   +--------------------+-------+-------+-------+
                        |
                      PR022
                        |
              PR023 || PR024 || PR025 || PR026
                        |
              +---------+---------+
              |                   |
            PR027               PR030
              |                   |
        PR028 || PR029             |
              |                   |
              +-------- PR031 -----+
                         |
                       PR032
```

Maximum safe parallel waves:

- Wave A after `XDL-PR001`: `XDL-PR002` + `XDL-PR003`.
- Wave B after `XDL-PR003` and `XDL-PR002`: `XDL-PR004` + `XDL-PR005`.
- Wave C after governance `XDL-PR006`: `XDL-PR007` + `XDL-PR009` + `XDL-PR013`.
- Wave D: `XDL-PR010` + `XDL-PR011` + `XDL-PR012`; `XDL-PR008` can run at the same time.
- Wave E: `XDL-PR014` + `XDL-PR015` + `XDL-PR016` + `XDL-PR017`.
- Wave F: `XDL-PR018` + `XDL-PR019` + `XDL-PR020` + `XDL-PR021`.
- Wave G after sync core: `XDL-PR023` + `XDL-PR024` + `XDL-PR025` + `XDL-PR026`; `XDL-PR030` may run in parallel once its dependencies are green.
- Wave H after pipeline orchestration: `XDL-PR028` + `XDL-PR029`.

## 5. Active work-order index

| ID | Work-order name | Branch | Depends on | Atomic result | Git status |
| --- | --- | --- | --- | --- | --- |
| XDL-PR001 | `xdl-pr001-python-repository-baseline` | `chore/xdl-pr001-python-repository-baseline` | XDL-PR000 | Python 3.14.7 + `.venv` + minimal package/test skeleton | not started; branch absent; blocked |
| XDL-PR002 | `xdl-pr002-quality-command-contract` | `chore/xdl-pr002-quality-command-contract` | PR001 | canonical lint/type/unit/integration commands | not started; branch absent; blocked |
| XDL-PR003 | `xdl-pr003-git-policy-validator` | `test/xdl-pr003-git-policy-validator` | PR001 | machine-checkable branch/commit/PR naming policy | not started; branch absent; blocked |
| XDL-PR004 | `xdl-pr004-push-quality-workflow` | `ci/xdl-pr004-push-quality-workflow` | PR002 + PR003 | parallel push quality gate | not started; branch absent; blocked |
| XDL-PR005 | `xdl-pr005-merge-quality-workflow` | `ci/xdl-pr005-merge-quality-workflow` | PR002 + PR003 | parallel PR merge gate | not started; branch absent; blocked |
| XDL-PR006 | `xdl-pr006-main-protection-automerge` | `chore/xdl-pr006-main-protection-automerge` | PR004 + PR005 | protected `main` + required `merge-gate` + auto-merge | not started; branch absent; blocked |
| XDL-PR007 | `xdl-pr007-postgres-market-schema` | `feat/xdl-pr007-postgres-market-schema` | PR006 | four consumer tables, keys, UTC timestamp contract | not started; branch absent; blocked |
| XDL-PR008 | `xdl-pr008-postgres-role-grants` | `feat/xdl-pr008-postgres-role-grants` | PR007 | writer/read-only DB roles and grant tests | not started; branch absent; blocked |
| XDL-PR009 | `xdl-pr009-medallion-core-contract` | `feat/xdl-pr009-medallion-core-contract` | PR006 | common Bronze/Silver/Gold layout + manifests | not started; branch absent; blocked |
| XDL-PR010 | `xdl-pr010-listing-dataset-contract` | `feat/xdl-pr010-listing-dataset-contract` | PR009 | deterministic listing schemas/keys | not started; branch absent; blocked |
| XDL-PR011 | `xdl-pr011-quote-dataset-contract` | `feat/xdl-pr011-quote-dataset-contract` | PR009 | deterministic quote schemas/keys | not started; branch absent; blocked |
| XDL-PR012 | `xdl-pr012-corporate-action-contract` | `feat/xdl-pr012-corporate-action-contract` | PR009 | dividend/split schemas + event-key contract | not started; branch absent; blocked |
| XDL-PR013 | `xdl-pr013-eodhd-transport` | `feat/xdl-pr013-eodhd-transport` | PR006 | shared EODHD HTTP/retry/rate-limit seam | not started; branch absent; blocked |
| XDL-PR014 | `xdl-pr014-xetra-listing-ingestion` | `feat/xdl-pr014-xetra-listing-ingestion` | PR010 + PR013 | complete non-empty-ISIN XETRA discovery | not started; branch absent; blocked |
| XDL-PR015 | `xdl-pr015-eod-quote-ingestion` | `feat/xdl-pr015-eod-quote-ingestion` | PR011 + PR013 | full + 7-day overlap quote ingestion | not started; branch absent; blocked |
| XDL-PR016 | `xdl-pr016-dividend-ingestion` | `feat/xdl-pr016-dividend-ingestion` | PR012 + PR013 | deterministic dividend ingestion | not started; branch absent; blocked |
| XDL-PR017 | `xdl-pr017-split-ingestion` | `feat/xdl-pr017-split-ingestion` | PR012 + PR013 | deterministic split ingestion | not started; branch absent; blocked |
| XDL-PR018 | `xdl-pr018-gold-listing-build` | `feat/xdl-pr018-gold-listing-build` | PR007 + PR014 | validated listing Gold | not started; branch absent; blocked |
| XDL-PR019 | `xdl-pr019-gold-quote-build` | `feat/xdl-pr019-gold-quote-build` | PR007 + PR015 | validated quote Gold | not started; branch absent; blocked |
| XDL-PR020 | `xdl-pr020-gold-dividend-build` | `feat/xdl-pr020-gold-dividend-build` | PR007 + PR016 | validated dividend Gold | not started; branch absent; blocked |
| XDL-PR021 | `xdl-pr021-gold-split-build` | `feat/xdl-pr021-gold-split-build` | PR007 + PR017 | validated split Gold | not started; branch absent; blocked |
| XDL-PR022 | `xdl-pr022-postgres-sync-core` | `feat/xdl-pr022-postgres-sync-core` | PR008 + PR009 + PR018-PR021 | transactional sync state/fingerprint core | not started; branch absent; blocked |
| XDL-PR023 | `xdl-pr023-postgres-listing-sync` | `feat/xdl-pr023-postgres-listing-sync` | PR018 + PR022 | idempotent listing publication | not started; branch absent; blocked |
| XDL-PR024 | `xdl-pr024-postgres-quote-sync` | `feat/xdl-pr024-postgres-quote-sync` | PR019 + PR022 | idempotent quote publication | not started; branch absent; blocked |
| XDL-PR025 | `xdl-pr025-postgres-dividend-sync` | `feat/xdl-pr025-postgres-dividend-sync` | PR020 + PR022 | idempotent dividend publication | not started; branch absent; blocked |
| XDL-PR026 | `xdl-pr026-postgres-split-sync` | `feat/xdl-pr026-postgres-split-sync` | PR021 + PR022 | idempotent split publication | not started; branch absent; blocked |
| XDL-PR027 | `xdl-pr027-weekly-pipeline-orchestrator` | `feat/xdl-pr027-weekly-pipeline-orchestrator` | PR023-PR026 | one deterministic weekly pipeline command | not started; branch absent; blocked |
| XDL-PR028 | `xdl-pr028-loader-lock-restart` | `feat/xdl-pr028-loader-lock-restart` | PR027 | non-overlap lock + restart-safe execution wrapper | not started; branch absent; blocked |
| XDL-PR029 | `xdl-pr029-sunday-1100-schedule` | `feat/xdl-pr029-sunday-1100-schedule` | PR027 | exact Vienna Sunday 11:00 scheduler | not started; branch absent; blocked |
| XDL-PR030 | `xdl-pr030-destructive-reset-guard` | `feat/xdl-pr030-destructive-reset-guard` | PR009 + PR022 | safe scoped destructive reset primitive | not started; branch absent; blocked |
| XDL-PR031 | `xdl-pr031-full-xetra-bootstrap` | `feat/xdl-pr031-full-xetra-bootstrap` | PR027 + PR030 | confirmed clean full-history bootstrap | not started; branch absent; blocked |
| XDL-PR032 | `xdl-pr032-loader-e2e-gate` | `test/xdl-pr032-loader-e2e-gate` | PR028 + PR029 + PR031 | production-like acceptance gate + handoff artifact | not started; branch absent; blocked |

## 6. Exact work orders

### XDL-PR001 — xdl-pr001-python-repository-baseline

Branch: `chore/xdl-pr001-python-repository-baseline`

Commit scope: `chore(xdl-pr001-python-repository-baseline): ...`

Depends on: XDL-PR000 merged.

Owned paths: `.python-version`, `.gitignore`, `pyproject.toml` Python/package metadata only, `src/xetra_data_loader/__init__.py`, package directory placeholders, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `README.md` setup section.

Tasks:

- pin CPython `3.14.7` in `.python-version` and package metadata;
- define `requires-python` compatible with the exact 3.14 baseline;
- create minimal installable `src/xetra_data_loader` package and test roots;
- document creation/activation of repository-local `.venv` with Python 3.14.7;
- ignore `.venv/`; do not commit virtual-environment contents;
- add only dependencies needed for an empty package/test bootstrap.

Acceptance:

- fresh `.venv` reports `Python 3.14.7`;
- editable/package install succeeds;
- `import xetra_data_loader` succeeds;
- `git ls-files .venv` returns no tracked files;
- no EODHD, PostgreSQL, medallion, or business logic exists.

### XDL-PR002 — xdl-pr002-quality-command-contract

Branch: `chore/xdl-pr002-quality-command-contract`

Commit scope: `chore(xdl-pr002-quality-command-contract): ...`

Depends on: PR001 merged.

Owned paths: quality-tool sections of `pyproject.toml`, `scripts/quality/*` or one `Makefile`/task runner, minimal smoke tests required by commands.

Tasks:

- choose/configure one lint command;
- choose/configure one static type command;
- define unit-test command restricted to `tests/unit`;
- define integration-test command restricted to `tests/integration`;
- make every command non-interactive and return non-zero on failure;
- document exact commands without adding workflows yet.

Acceptance:

- all four commands run independently on clean PR001;
- unit command does not execute integration tests and vice versa;
- no workflow YAML is changed.

### XDL-PR003 — xdl-pr003-git-policy-validator

Branch: `test/xdl-pr003-git-policy-validator`

Commit scope: `test(xdl-pr003-git-policy-validator): ...`

Depends on: PR001 merged.

Owned paths: `scripts/ci/validate_git_policy.py`, `tests/unit/test_git_policy.py`, policy fixture files only.

Tasks:

- validate Conventional Commit syntax;
- extract exact `xdl-prNNN-*` work-order name from branch;
- require that exact name in every introduced commit subject;
- require that exact name in PR title when PR metadata is available;
- reject malformed/missing work-order branch names;
- cover valid/invalid cases with unit tests.

Acceptance:

- valid example passes;
- invalid Conventional Commit fails;
- commit missing work-order name fails;
- branch missing work-order name fails;
- PR title missing work-order name fails;
- validator has no GitHub API write capability.

### XDL-PR004 — xdl-pr004-push-quality-workflow

Branch: `ci/xdl-pr004-push-quality-workflow`

Commit scope: `ci(xdl-pr004-push-quality-workflow): ...`

Depends on: PR002 + PR003 merged.

Owned paths: `.github/workflows/push-quality.yml` only.

Tasks:

- trigger on non-main work-order branch pushes;
- create independent jobs `lint`, `type`, `unit`, `integration`, `policy`;
- ensure the four code-quality jobs have no dependencies on each other;
- create final `push-gate` job depending on all required jobs;
- make `push-gate` fail on failed/cancelled/unexpectedly skipped required jobs;
- use Python 3.14.7.

Acceptance:

- workflow syntax validates;
- a test push shows four code-quality jobs eligible to run in parallel;
- `push-gate` is green only when all required jobs are green.

### XDL-PR005 — xdl-pr005-merge-quality-workflow

Branch: `ci/xdl-pr005-merge-quality-workflow`

Commit scope: `ci(xdl-pr005-merge-quality-workflow): ...`

Depends on: PR002 + PR003 merged.

Owned paths: `.github/workflows/merge-quality.yml` only.

Tasks:

- trigger on pull requests targeting `main`;
- create independent `lint`, `type`, `unit`, `integration`, `policy` jobs;
- create final required `merge-gate` aggregator;
- use Python 3.14.7;
- expose stable check name exactly `merge-gate`.

Acceptance:

- workflow syntax validates;
- four code-quality jobs can run in parallel;
- failed policy or quality job prevents `merge-gate` success;
- no merge or push token bypass is implemented.

### XDL-PR006 — xdl-pr006-main-protection-automerge

Branch: `chore/xdl-pr006-main-protection-automerge`

Commit scope: `chore(xdl-pr006-main-protection-automerge): ...`

Depends on: PR004 + PR005 merged and observed on GitHub Actions.

Owned paths: repository settings plus `docs/repository-governance.md`; no application code.

Tasks:

- enable repository auto-merge;
- protect `main`;
- require PRs to merge to `main`;
- require status check `merge-gate`;
- reject force pushes and branch deletion;
- prevent normal direct feature pushes;
- document exact auto-merge procedure for weak agents.

Acceptance:

- GitHub reports `main` protected;
- direct feature push/force push/delete are denied;
- representative PR cannot merge while `merge-gate` is pending/failing;
- representative review-ready PR can be put into auto-merge and completes only after required checks pass.

### XDL-PR007 — xdl-pr007-postgres-market-schema

Branch: `feat/xdl-pr007-postgres-market-schema`

Commit scope: `feat(xdl-pr007-postgres-market-schema): ...`

Depends on: PR006 merged.

Owned paths: `sql/schema/001_portfell_market.sql`, `src/xetra_data_loader/contracts/postgres_market.py`, schema-focused tests only.

Tasks:

- create schema `portfell_market`;
- define `listings`, `eod_quotes`, `dividends`, `splits`;
- enforce frozen primary/unique business keys;
- use `TIMESTAMPTZ(6)` for every timestamp field and preserve `trade_date DATE`;
- define typed DTOs matching DDL exactly;
- reject naive datetimes.

Acceptance:

- DDL recreates cleanly on empty PostgreSQL;
- introspection confirms every timestamp is `TIMESTAMPTZ(6)`;
- DTO/DDL names and nullable rules match;
- key-violation and naive-datetime tests fail as expected.

### XDL-PR008 — xdl-pr008-postgres-role-grants

Branch: `feat/xdl-pr008-postgres-role-grants`

Commit scope: `feat(xdl-pr008-postgres-role-grants): ...`

Depends on: PR007 merged.

Owned paths: `sql/roles/002_loader_roles.sql`, `tests/integration/test_postgres_roles.py`.

Tasks:

- define `portfell_data_loader` writer grants for loader-owned schemas;
- define `portfell_app` SELECT-only access to `portfell_market`;
- deny `portfell_app` mutation/DDL;
- deny `portfell_app` access to `portfell_loader_sync`.

Acceptance:

- writer can perform required market-table DML;
- app can SELECT market tables;
- app INSERT/UPDATE/DELETE/DDL fails;
- app access to loader-sync schema fails.

### XDL-PR009 — xdl-pr009-medallion-core-contract

Branch: `feat/xdl-pr009-medallion-core-contract`

Commit scope: `feat(xdl-pr009-medallion-core-contract): ...`

Depends on: PR006 merged.

Owned paths: `src/xetra_data_loader/medallion/core.py`, `src/xetra_data_loader/medallion/layout.py`, related unit tests.

Tasks:

- define Bronze/Silver/Gold path conventions;
- define immutable manifest structure with dataset, run id, source bounds, counts, fingerprints, timestamps;
- separate semantic fingerprint fields from run/fetch metadata;
- define deterministic serialization ordering.

Acceptance:

- identical semantic fixture gives identical semantic fingerprint;
- run/fetch timestamp-only changes do not alter semantic fingerprint;
- invalid layer/dataset/path combinations fail closed.

### XDL-PR010 — xdl-pr010-listing-dataset-contract

Branch: `feat/xdl-pr010-listing-dataset-contract`

Commit scope: `feat(xdl-pr010-listing-dataset-contract): ...`

Depends on: PR009 merged.

Owned paths: `src/xetra_data_loader/contracts/listings.py`, listing fixtures/tests only.

Tasks:

- define Bronze preservation fields for exchange-symbol response;
- define normalized Silver listing fields;
- define Gold listing fields compatible with PR007;
- freeze `(isin, exchange, code)` identity and ISIN normalization.

Acceptance:

- non-empty normalized ISIN retained;
- null/empty ISIN rejected from Silver/Gold;
- duplicate ISIN under distinct code remains distinct;
- contract round-trip is deterministic.

### XDL-PR011 — xdl-pr011-quote-dataset-contract

Branch: `feat/xdl-pr011-quote-dataset-contract`

Commit scope: `feat(xdl-pr011-quote-dataset-contract): ...`

Depends on: PR009 merged.

Owned paths: `src/xetra_data_loader/contracts/quotes.py`, quote fixtures/tests only.

Tasks:

- freeze Bronze/Silver/Gold quote fields;
- freeze business key `(isin, exchange, code, trade_date)`;
- define canonical UTC `timestamp_eod` from `trade_date`;
- define seven-day overlap comparison semantics.

Acceptance:

- date anchor is timezone-aware UTC midnight;
- no physical close time is inferred;
- duplicate business keys fail;
- semantic equality ignores fetch/run metadata.

### XDL-PR012 — xdl-pr012-corporate-action-contract

Branch: `feat/xdl-pr012-corporate-action-contract`

Commit scope: `feat(xdl-pr012-corporate-action-contract): ...`

Depends on: PR009 merged.

Owned paths: `src/xetra_data_loader/contracts/corporate_actions.py`, corporate-action fixtures/tests only.

Tasks:

- define dividend and split Bronze/Silver/Gold fields;
- define deterministic normalized SHA-256 `event_key`;
- define correction and retraction representation;
- exclude run IDs, fetch timestamps, and DB IDs from event identity.

Acceptance:

- same semantic event always yields same `event_key`;
- changed business field changes `event_key`/correction representation deterministically;
- run metadata changes do not change event identity.

### XDL-PR013 — xdl-pr013-eodhd-transport

Branch: `feat/xdl-pr013-eodhd-transport`

Commit scope: `feat(xdl-pr013-eodhd-transport): ...`

Depends on: PR006 merged.

Owned paths: `src/xetra_data_loader/ingestion/eodhd/client.py`, `retry.py`, `rate_limit.py`, transport fixtures/tests.

Tasks:

- load EODHD token from environment only;
- implement typed GET transport with timeout;
- implement bounded retry/backoff for retryable failures;
- implement rate-limit handling at transport seam;
- expose deterministic fixture seam for downstream adapter tests;
- never log credentials/full secret-bearing URLs.

Acceptance:

- missing token fails clearly;
- retryable fixture failure retries within configured bound;
- permanent failure exits non-zero/raises typed error;
- logs contain no token.

### XDL-PR014 — xdl-pr014-xetra-listing-ingestion

Branch: `feat/xdl-pr014-xetra-listing-ingestion`

Commit scope: `feat(xdl-pr014-xetra-listing-ingestion): ...`

Depends on: PR010 + PR013 merged.

Owned paths: `src/xetra_data_loader/ingestion/listings.py`, listing ingestion tests/fixtures only.

Tasks:

- call EODHD XETRA exchange-symbol endpoint through PR013;
- preserve raw Bronze response;
- normalize Silver via PR010;
- keep every non-empty-ISIN XETRA row;
- do not filter ETF/UCITS/type/country/currency;
- preserve duplicate ISINs under distinct codes.

Acceptance:

- mixed fixture retains every non-empty-ISIN identity;
- null/empty ISIN removed only at normalized layer;
- repeated payload yields same semantic output.

### XDL-PR015 — xdl-pr015-eod-quote-ingestion

Branch: `feat/xdl-pr015-eod-quote-ingestion`

Commit scope: `feat(xdl-pr015-eod-quote-ingestion): ...`

Depends on: PR011 + PR013 merged.

Owned paths: `src/xetra_data_loader/ingestion/quotes.py`, quote ingestion tests/fixtures only.

Tasks:

- fetch quote history by `(exchange, code)`;
- support full-history mode;
- support incremental start = last business date minus seven calendar days;
- normalize via PR011;
- detect changed historical rows inside overlap;
- persist Bronze/Silver artifacts through existing medallion seams.

Acceptance:

- identical replay creates no semantic change;
- one corrected overlap row is detected exactly once;
- one new date appends exactly one key;
- all timestamps are aware UTC.

### XDL-PR016 — xdl-pr016-dividend-ingestion

Branch: `feat/xdl-pr016-dividend-ingestion`

Commit scope: `feat(xdl-pr016-dividend-ingestion): ...`

Depends on: PR012 + PR013 merged.

Owned paths: `src/xetra_data_loader/ingestion/dividends.py`, dividend tests/fixtures only.

Tasks:

- fetch dividend history through PR013;
- support full and seven-day-overlap refresh;
- normalize events and event keys via PR012;
- detect corrections/retractions inside overlap.

Acceptance:

- identical event replay is stable;
- correction is detected deterministically;
- retraction is explicitly represented;
- no split logic is added.

### XDL-PR017 — xdl-pr017-split-ingestion

Branch: `feat/xdl-pr017-split-ingestion`

Commit scope: `feat(xdl-pr017-split-ingestion): ...`

Depends on: PR012 + PR013 merged.

Owned paths: `src/xetra_data_loader/ingestion/splits.py`, split tests/fixtures only.

Tasks/Acceptance: same deterministic full/overlap/correction/retraction behavior as PR016, but for splits only; no dividend implementation is modified.

### XDL-PR018 — xdl-pr018-gold-listing-build

Branch: `feat/xdl-pr018-gold-listing-build`

Commit scope: `feat(xdl-pr018-gold-listing-build): ...`

Depends on: PR007 + PR014 merged.

Owned paths: `src/xetra_data_loader/application/gold/listings.py`, Gold listing tests only.

Tasks:

- convert normalized listing Silver to PR007-compatible Gold;
- enforce key uniqueness and required fields;
- emit counts/fingerprint/validation result.

Acceptance: Gold loads into listing DDL without transformation; duplicates/invalid ISIN fail closed; same semantic input yields same output fingerprint.

### XDL-PR019 — xdl-pr019-gold-quote-build

Branch: `feat/xdl-pr019-gold-quote-build`

Commit scope: `feat(xdl-pr019-gold-quote-build): ...`

Depends on: PR007 + PR015 merged.

Owned paths: `src/xetra_data_loader/application/gold/quotes.py`, Gold quote tests only.

Tasks/Acceptance: build PR007-compatible quote Gold, enforce key uniqueness, listing identity fields and UTC/date rules, emit deterministic validation metadata; invalid/duplicate rows fail closed.

### XDL-PR020 — xdl-pr020-gold-dividend-build

Branch: `feat/xdl-pr020-gold-dividend-build`

Commit scope: `feat(xdl-pr020-gold-dividend-build): ...`

Depends on: PR007 + PR016 merged.

Owned paths: `src/xetra_data_loader/application/gold/dividends.py`, Gold dividend tests only.

Tasks/Acceptance: build PR007-compatible dividend Gold, reconcile correction/retraction representation, enforce event business key and deterministic validation; no split code changes.

### XDL-PR021 — xdl-pr021-gold-split-build

Branch: `feat/xdl-pr021-gold-split-build`

Commit scope: `feat(xdl-pr021-gold-split-build): ...`

Depends on: PR007 + PR017 merged.

Owned paths: `src/xetra_data_loader/application/gold/splits.py`, Gold split tests only.

Tasks/Acceptance: build PR007-compatible split Gold with the same deterministic validation/reconciliation guarantees as PR020; no dividend code changes.

### XDL-PR022 — xdl-pr022-postgres-sync-core

Branch: `feat/xdl-pr022-postgres-sync-core`

Commit scope: `feat(xdl-pr022-postgres-sync-core): ...`

Depends on: PR008 + PR009 + PR018 + PR019 + PR020 + PR021 merged.

Owned paths: `sql/schema/003_portfell_loader_sync.sql`, `src/xetra_data_loader/application/postgres_sync/core.py`, `state.py`, sync-core tests only.

Tasks:

- create `portfell_loader_sync` run/state tables;
- define UTC `TIMESTAMPTZ(6)` loader timestamps;
- implement semantic row fingerprint helper;
- provide transaction boundary that couples data mutation and sync-state advance;
- provide generic insert/update/retraction result counters;
- add rollback integration tests without entity-specific SQL.

Acceptance:

- failure before commit changes neither sync state nor serving data;
- unchanged semantic row fingerprint is stable across run metadata changes;
- loader timestamps pass DDL introspection.

### XDL-PR023 — xdl-pr023-postgres-listing-sync

Branch: `feat/xdl-pr023-postgres-listing-sync`

Commit scope: `feat(xdl-pr023-postgres-listing-sync): ...`

Depends on: PR018 + PR022 merged.

Owned paths: `src/xetra_data_loader/application/postgres_sync/listings.py`, listing-sync integration tests only.

Tasks/Acceptance: UPSERT listing Gold on frozen key, advance state transactionally, first load inserts expected count, identical replay causes zero semantic mutations, one changed listing causes exactly one update.

### XDL-PR024 — xdl-pr024-postgres-quote-sync

Branch: `feat/xdl-pr024-postgres-quote-sync`

Commit scope: `feat(xdl-pr024-postgres-quote-sync): ...`

Depends on: PR019 + PR022 merged.

Owned paths: `src/xetra_data_loader/application/postgres_sync/quotes.py`, quote-sync integration tests only.

Tasks/Acceptance: UPSERT quote Gold on `(isin,exchange,code,trade_date)`; identical replay = zero semantic mutations; one correction = exactly one update; one new date = one insert.

### XDL-PR025 — xdl-pr025-postgres-dividend-sync

Branch: `feat/xdl-pr025-postgres-dividend-sync`

Commit scope: `feat(xdl-pr025-postgres-dividend-sync): ...`

Depends on: PR020 + PR022 merged.

Owned paths: `src/xetra_data_loader/application/postgres_sync/dividends.py`, dividend-sync integration tests only.

Tasks/Acceptance: publish dividend Gold transactionally; identical replay = zero mutation; correction/retraction reconciles exactly intended event; no split path changes.

### XDL-PR026 — xdl-pr026-postgres-split-sync

Branch: `feat/xdl-pr026-postgres-split-sync`

Commit scope: `feat(xdl-pr026-postgres-split-sync): ...`

Depends on: PR021 + PR022 merged.

Owned paths: `src/xetra_data_loader/application/postgres_sync/splits.py`, split-sync integration tests only.

Tasks/Acceptance: same guarantees as PR025 for split events only; no dividend path changes.

### XDL-PR027 — xdl-pr027-weekly-pipeline-orchestrator

Branch: `feat/xdl-pr027-weekly-pipeline-orchestrator`

Commit scope: `feat(xdl-pr027-weekly-pipeline-orchestrator): ...`

Depends on: PR023 + PR024 + PR025 + PR026 merged.

Owned paths: `src/xetra_data_loader/application/pipeline.py`, `src/xetra_data_loader/ops/run_weekly.py`, orchestration tests only.

Tasks:

- compose exactly: listings -> quotes -> dividends -> splits -> Gold builds -> four PostgreSQL syncs -> verification;
- stop immediately on failed stage;
- emit structured stage/run results;
- expose one non-interactive weekly command;
- do not add lock or scheduler behavior yet.

Acceptance:

- fixture run invokes stages in exact order;
- failure prevents downstream stages;
- success returns complete deterministic summary;
- no cron/lock code exists in this PR.

### XDL-PR028 — xdl-pr028-loader-lock-restart

Branch: `feat/xdl-pr028-loader-lock-restart`

Commit scope: `feat(xdl-pr028-loader-lock-restart): ...`

Depends on: PR027 merged.

Owned paths: `src/xetra_data_loader/ops/locking.py`, `checkpoints.py`, `locked_runner.py`, associated tests only.

Tasks:

- provide one process/distributed lock around weekly runner;
- prevent concurrent duplicate run;
- persist safe stage checkpoints outside semantic data identity;
- restart after failed local stage without publishing incomplete downstream state.

Acceptance:

- second concurrent invocation is denied;
- failed run releases/recovers lock safely;
- restart does not duplicate semantic PostgreSQL mutations.

### XDL-PR029 — xdl-pr029-sunday-1100-schedule

Branch: `feat/xdl-pr029-sunday-1100-schedule`

Commit scope: `feat(xdl-pr029-sunday-1100-schedule): ...`

Depends on: PR027 merged.

Owned paths: scheduler/cron deployment files and scheduler tests only.

Tasks:

- commit exactly `CRON_TZ=Europe/Vienna`;
- commit exactly `0 11 * * 0`;
- invoke the weekly runner entry point;
- test Vienna-local DST semantics without converting expression to UTC.

Acceptance:

- committed expression is literal and exact;
- next Sunday invocation remains 11:00 Vienna local time across DST boundaries.

### XDL-PR030 — xdl-pr030-destructive-reset-guard

Branch: `feat/xdl-pr030-destructive-reset-guard`

Commit scope: `feat(xdl-pr030-destructive-reset-guard): ...`

Depends on: PR009 + PR022 merged.

Owned paths: `src/xetra_data_loader/ops/destructive_reset.py`, reset tests only.

Tasks:

- enumerate loader-owned DB schemas/tables and medallion paths;
- provide dry-run output of exact destruction scope;
- require literal `--confirm-destructive-reset` for mutation;
- never include unrelated/Portfell optimizer state;
- reset loader-owned local state and DB objects only.

Acceptance:

- no confirmation = zero deletion;
- dry run exactly names target scope;
- unrelated fixture schema/path survives confirmed reset.

### XDL-PR031 — xdl-pr031-full-xetra-bootstrap

Branch: `feat/xdl-pr031-full-xetra-bootstrap`

Commit scope: `feat(xdl-pr031-full-xetra-bootstrap): ...`

Depends on: PR027 + PR030 merged.

Owned paths: `src/xetra_data_loader/ops/bootstrap.py`, bootstrap tests only.

Tasks:

- call confirmed reset primitive;
- discover current full XETRA non-empty-ISIN universe;
- run full-history quote/dividend/split ingestion;
- build Gold and publish all four datasets;
- verify counts, keys, date bounds, sync state;
- record measured request count, retries, elapsed time, failures, output row counts; do not estimate duration.

Acceptance:

- without confirmation no reset/bootstrap mutation occurs;
- clean fixture bootstrap reaches verified serving state;
- repeated post-bootstrap weekly run is semantic no-op when source unchanged.

### XDL-PR032 — xdl-pr032-loader-e2e-gate

Branch: `test/xdl-pr032-loader-e2e-gate`

Commit scope: `test(xdl-pr032-loader-e2e-gate): ...`

Depends on: PR028 + PR029 + PR031 merged.

Owned paths: `tests/e2e/*`, acceptance-report generator/fixture outputs only.

Tasks:

- test clean bootstrap from empty loader-owned state;
- test every fixture non-empty-ISIN XETRA listing retained;
- test full quote/dividend/split publication;
- replay unchanged state and assert zero semantic DB mutations;
- test one quote correction;
- test dividend/split correction and retraction;
- add new listing and verify next-cycle ingestion;
- introspect every timestamp column for exact `TIMESTAMPTZ(6)` and UTC session;
- verify `portfell_app` read-only permissions;
- verify lock and exact Sunday schedule;
- emit machine-readable contract/acceptance artifact for Portfell.

Acceptance:

- all scenarios pass on one commit SHA;
- `lint`, `type`, `unit`, `integration`, `policy`, and `merge-gate` are green;
- no test imports Portfell code;
- acceptance artifact is sufficient for Portfell's cross-repository smoke test.

## 7. Cross-repository handoff

Portfell may begin its read-contract work only after `XDL-PR007` has frozen the serving-table DDL; permission verification additionally depends on `XDL-PR008`. Portfell's final cross-repository contract gate remains blocked until `XDL-PR032` is merged and green.

Portfell consumes only:

- PostgreSQL DDL/column contract;
- read-only role contract;
- machine-readable acceptance fixtures/report.

Portfell must not import `xetra-data-loader`, call EODHD, read the loader medallion filesystem, or mutate loader schemas.

## 8. Superseded coarse planning IDs

| Old work order | Replacement |
| --- | --- |
| PR297 repository bootstrap/governance | XDL-PR001 through XDL-PR006 |
| PR298 PostgreSQL serving contract | XDL-PR007 + XDL-PR008 |
| PR299 medallion contracts | XDL-PR009 through XDL-PR012 |
| PR300 listing ingestion | XDL-PR013 + XDL-PR014 |
| PR301 quote ingestion | XDL-PR011 + XDL-PR013 + XDL-PR015 |
| PR302 corporate actions | XDL-PR012 + XDL-PR013 + XDL-PR016 + XDL-PR017 |
| PR303 Gold serving build | XDL-PR018 through XDL-PR021 |
| PR304 PostgreSQL sync | XDL-PR022 through XDL-PR026 |
| PR305 weekly runner/schedule | XDL-PR027 + XDL-PR028 + XDL-PR029 |
| PR306 destructive bootstrap | XDL-PR030 + XDL-PR031 |
| PR307 end-to-end gate | XDL-PR032 |

Old PR297-PR307 branches, if ever created, are superseded and must not be merged as implementation authority.

## 9. Loader completion gate

The loader side is complete only when all `XDL-PR001`-`XDL-PR032` work orders are merged and the following hold from clean protected `main`:

- Python 3.14.7 `.venv` setup is reproducible and `.venv` is untracked;
- push/merge quality workflows run lint/type/unit/integration in parallel;
- Conventional Commit and work-order naming policy is machine-enforced;
- `main` is protected and requires `merge-gate`;
- auto-merge cannot complete before required checks pass;
- every current XETRA non-empty-ISIN listing can be discovered from scratch;
- full available quote/dividend/split history can be bootstrapped;
- Gold validates frozen schema/keys/referential rules;
- PostgreSQL sync is transactional and idempotent;
- unchanged replay creates zero semantic mutations;
- corrections/retractions reconcile deterministically;
- timestamps are `TIMESTAMPTZ(6)` and sessions UTC;
- `portfell_app` is read-only;
- exact scheduler is Sunday 11:00 Europe/Vienna;
- destructive reset requires explicit confirmation and cannot affect unrelated state;
- final machine-readable acceptance artifact is green and consumable by Portfell.