Last reviewed: 2026-08-22

# XETRA Data Loader — Atomic Parallel Backlog

## Status authority

This file is the complete implementation authority for `SergejSchweizer/xetra-data-loader`.

The former coarse loader plan `PR297`-`PR307` is superseded. It is replaced by repository-local work orders `XDL-PR001` through `XDL-PR032`, designed for multiple weak agents that must work independently with minimal merge conflicts.

Planning gate:

- work-order: `xdl-pr000-backlog-restructure`
- branch: `docs/xdl-pr000-backlog-restructure`
- required commit scope: `docs(xdl-pr000-backlog-restructure): ...`
- Git status: branch pushed; PR validation/merge pending

No implementation work starts until XDL-PR000 is merged.

## Frozen architecture

```text
EODHD
  -> xetra-data-loader
       Bronze -> Silver -> Gold
       -> PostgreSQL 10.10.1.3:54321
            portfell_market
            portfell_loader_sync
                 |
                 | SELECT only as portfell_app
                 v
              portfell
```

Frozen business/serving rules:

- initial universe: every EODHD XETRA listing with normalized non-empty ISIN;
- do not prefilter by ETF/UCITS/fund/type/country/currency;
- listing identity: `(isin, exchange, code)`;
- quote identity: `(isin, exchange, code, trade_date)`;
- dividend/split identity: `(isin, exchange, code, event_key)`;
- `event_key`: deterministic SHA-256 from normalized provider business fields only;
- all PostgreSQL timestamp columns: exactly `TIMESTAMPTZ(6)`;
- all PostgreSQL sessions: UTC;
- `trade_date` remains `DATE`;
- `timestamp_eod` is `trade_date 00:00:00+00:00`, not a physical exchange-close timestamp;
- incremental refresh overlap: seven calendar days;
- unchanged source replay must produce zero semantic PostgreSQL mutations;
- exact scheduler: `CRON_TZ=Europe/Vienna` and `0 11 * * 0`;
- secrets/passwords/full DSNs are never committed;
- Portfell code, portfolio analytics, UI, users/tenants/projects, and authorization do not belong here.

## Git / branch / CI rules for every agent

Every work order is self-contained. An agent may read its dependencies but must edit only its owned paths.

Mandatory rules:

1. Start from the exact merged dependency SHA.
2. Run and record `git status --short --branch` before edits.
3. If any dependency is unmerged, stop; do not invent a workaround.
4. Never branch from a sibling work-order branch.
5. Parallel siblings start from the same predecessor merge SHA.
6. The exact work-order name must appear literally in the branch name, every commit message, and PR title.
7. Every commit uses Conventional Commits.
8. Example:

```text
Work-order: xdl-pr015-eod-quote-ingestion
Branch:     feat/xdl-pr015-eod-quote-ingestion
Commit:     feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
PR title:   feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
```

9. Do not edit sibling-owned files, add compatibility shims, broaden scope, or perform opportunistic refactors.
10. Run focused tests and all available repository quality gates on the same head SHA.
11. After XDL-PR006, `main` is protected and merge occurs only through required `merge-gate`; review-ready implementation PRs use auto-merge.

Python/quality baseline:

- CPython `3.14.7`;
- local repository `.venv` built with Python 3.14.7 and never tracked;
- push and merge CI each run `lint`, `type`, `unit`, `integration` as four independent parallel jobs;
- separate fast `policy` job validates Conventional Commits and work-order naming;
- final `push-gate` / `merge-gate` aggregate all required checks.

## Optimized dependency graph

```text
XDL-PR000
   |
 PR001
   |
 +---------+
 |         |
PR002    PR003
 |         |
 +----+----+
      |
 PR004 || PR005
      |
    PR006
      |
 +----+----------------------+--------------------+
 |                           |                    |
PR007                      PR009                PR013
 |                           |                    |
PR008               PR010 || PR011 || PR012      |
 |                    |       |       |           |
 +------ PR022        |       |       |           |
 |          |         |       |       |           |
 |        PR030     PR014   PR015   PR016 || PR017
 |                    |       |       |       |
 |                  PR018   PR019   PR020   PR021
 |                    |       |       |       |
 |                    +--+----+-------+-------+
 |                       |    |       |       |
 +--------------------> PR023 PR024  PR025   PR026
                          \     |      |      /
                           +----+------+-----+
                                |
                              PR027
                                |
                         PR028 || PR029
                                |
                       PR031 <- PR030
                                |
                              PR032
```

Interpretation: `PR022` starts as soon as the database roles and medallion core exist; it does **not** wait for entity ingestion or Gold builders. Each entity can then progress independently from contract -> ingestion -> Gold -> PostgreSQL sync.

Safe parallel waves:

- Wave 1: PR002 + PR003.
- Wave 2: PR004 + PR005.
- Wave 3 after governance: PR007 + PR009 + PR013.
- Wave 4: PR008 + PR010 + PR011 + PR012.
- Wave 5: PR014 + PR015 + PR016 + PR017; PR022 starts independently once PR008+PR009 are green.
- Wave 6: PR018 + PR019 + PR020 + PR021; PR030 can start after PR022.
- Wave 7: PR023 + PR024 + PR025 + PR026, each as soon as its own Gold builder plus PR022 are merged.
- Wave 8: PR028 + PR029 after PR027.

## Work-order index

| ID | Work-order | Branch | Depends on | Atomic result | Git status |
| --- | --- | --- | --- | --- | --- |
| PR001 | `xdl-pr001-python-repository-baseline` | `chore/xdl-pr001-python-repository-baseline` | PR000 | Python/.venv/minimal package skeleton | not started; branch absent; blocked |
| PR002 | `xdl-pr002-quality-command-contract` | `chore/xdl-pr002-quality-command-contract` | PR001 | canonical four local quality commands | not started; branch absent; blocked |
| PR003 | `xdl-pr003-git-policy-validator` | `test/xdl-pr003-git-policy-validator` | PR001 | machine-enforced commit/branch/PR naming policy | not started; branch absent; blocked |
| PR004 | `xdl-pr004-push-quality-workflow` | `ci/xdl-pr004-push-quality-workflow` | PR002+PR003 | parallel push gate | not started; branch absent; blocked |
| PR005 | `xdl-pr005-merge-quality-workflow` | `ci/xdl-pr005-merge-quality-workflow` | PR002+PR003 | parallel merge gate | not started; branch absent; blocked |
| PR006 | `xdl-pr006-main-protection-automerge` | `chore/xdl-pr006-main-protection-automerge` | PR004+PR005 | protected main + required gate + auto-merge | not started; branch absent; blocked |
| PR007 | `xdl-pr007-postgres-market-schema` | `feat/xdl-pr007-postgres-market-schema` | PR006 | frozen market DDL/DTO/timestamp contract | not started; branch absent; blocked |
| PR008 | `xdl-pr008-postgres-role-grants` | `feat/xdl-pr008-postgres-role-grants` | PR007 | writer/read-only grants | not started; branch absent; blocked |
| PR009 | `xdl-pr009-medallion-core-contract` | `feat/xdl-pr009-medallion-core-contract` | PR006 | layer/layout/manifest primitives | not started; branch absent; blocked |
| PR010 | `xdl-pr010-listing-dataset-contract` | `feat/xdl-pr010-listing-dataset-contract` | PR009 | listing dataset contract | not started; branch absent; blocked |
| PR011 | `xdl-pr011-quote-dataset-contract` | `feat/xdl-pr011-quote-dataset-contract` | PR009 | quote dataset contract | not started; branch absent; blocked |
| PR012 | `xdl-pr012-corporate-action-contract` | `feat/xdl-pr012-corporate-action-contract` | PR009 | dividend/split event contract | not started; branch absent; blocked |
| PR013 | `xdl-pr013-eodhd-transport` | `feat/xdl-pr013-eodhd-transport` | PR006 | provider HTTP/retry/rate-limit seam | not started; branch absent; blocked |
| PR014 | `xdl-pr014-xetra-listing-ingestion` | `feat/xdl-pr014-xetra-listing-ingestion` | PR010+PR013 | all non-empty-ISIN XETRA listings | not started; branch absent; blocked |
| PR015 | `xdl-pr015-eod-quote-ingestion` | `feat/xdl-pr015-eod-quote-ingestion` | PR011+PR013 | full/overlap quote ingestion | not started; branch absent; blocked |
| PR016 | `xdl-pr016-dividend-ingestion` | `feat/xdl-pr016-dividend-ingestion` | PR012+PR013 | full/overlap dividend ingestion | not started; branch absent; blocked |
| PR017 | `xdl-pr017-split-ingestion` | `feat/xdl-pr017-split-ingestion` | PR012+PR013 | full/overlap split ingestion | not started; branch absent; blocked |
| PR018 | `xdl-pr018-gold-listing-build` | `feat/xdl-pr018-gold-listing-build` | PR007+PR014 | validated listing Gold | not started; branch absent; blocked |
| PR019 | `xdl-pr019-gold-quote-build` | `feat/xdl-pr019-gold-quote-build` | PR007+PR015 | validated quote Gold | not started; branch absent; blocked |
| PR020 | `xdl-pr020-gold-dividend-build` | `feat/xdl-pr020-gold-dividend-build` | PR007+PR016 | validated dividend Gold | not started; branch absent; blocked |
| PR021 | `xdl-pr021-gold-split-build` | `feat/xdl-pr021-gold-split-build` | PR007+PR017 | validated split Gold | not started; branch absent; blocked |
| PR022 | `xdl-pr022-postgres-sync-core` | `feat/xdl-pr022-postgres-sync-core` | PR008+PR009 | generic transactional sync/state/fingerprint core | not started; branch absent; blocked |
| PR023 | `xdl-pr023-postgres-listing-sync` | `feat/xdl-pr023-postgres-listing-sync` | PR018+PR022 | idempotent listing publication | not started; branch absent; blocked |
| PR024 | `xdl-pr024-postgres-quote-sync` | `feat/xdl-pr024-postgres-quote-sync` | PR019+PR022 | idempotent quote publication | not started; branch absent; blocked |
| PR025 | `xdl-pr025-postgres-dividend-sync` | `feat/xdl-pr025-postgres-dividend-sync` | PR020+PR022 | idempotent dividend publication | not started; branch absent; blocked |
| PR026 | `xdl-pr026-postgres-split-sync` | `feat/xdl-pr026-postgres-split-sync` | PR021+PR022 | idempotent split publication | not started; branch absent; blocked |
| PR027 | `xdl-pr027-weekly-pipeline-orchestrator` | `feat/xdl-pr027-weekly-pipeline-orchestrator` | PR023-PR026 | single ordered weekly command | not started; branch absent; blocked |
| PR028 | `xdl-pr028-loader-lock-restart` | `feat/xdl-pr028-loader-lock-restart` | PR027 | non-overlap/restart-safe wrapper | not started; branch absent; blocked |
| PR029 | `xdl-pr029-sunday-1100-schedule` | `feat/xdl-pr029-sunday-1100-schedule` | PR027 | exact scheduler configuration | not started; branch absent; blocked |
| PR030 | `xdl-pr030-destructive-reset-guard` | `feat/xdl-pr030-destructive-reset-guard` | PR009+PR022 | scoped confirmed reset primitive | not started; branch absent; blocked |
| PR031 | `xdl-pr031-full-xetra-bootstrap` | `feat/xdl-pr031-full-xetra-bootstrap` | PR027+PR030 | clean full-history bootstrap | not started; branch absent; blocked |
| PR032 | `xdl-pr032-loader-e2e-gate` | `test/xdl-pr032-loader-e2e-gate` | PR028+PR029+PR031 | final production-like acceptance gate | not started; branch absent; blocked |

## Exact atomic PR specifications

### PR001 — xdl-pr001-python-repository-baseline

Branch `chore/xdl-pr001-python-repository-baseline`; commit scope `chore(xdl-pr001-python-repository-baseline): ...`; depends on PR000.

Owned paths: `.python-version`, `.gitignore`, `pyproject.toml` package/Python metadata only, `src/xetra_data_loader/__init__.py`, empty package directories, test-root placeholders, README local-setup section.

Tasks: pin Python 3.14.7; set compatible `requires-python`; create installable src-layout package; create `tests/unit` and `tests/integration`; document `python3.14 -m venv .venv`, activation and installation; ignore `.venv/`; add no provider/database/business code.

Acceptance: new `.venv` reports exactly Python 3.14.7; package installs and imports; zero `.venv` files are tracked; package/test roots exist; no EODHD/PostgreSQL/medallion implementation exists.

### PR002 — xdl-pr002-quality-command-contract

Branch `chore/xdl-pr002-quality-command-contract`; commit scope `chore(xdl-pr002-quality-command-contract): ...`; depends on PR001.

Owned paths: quality-tool sections of `pyproject.toml`, `scripts/quality/*` or one task runner, command-specific smoke fixtures.

Tasks: configure one lint command, one static-type command, one unit-test command restricted to `tests/unit`, one integration-test command restricted to `tests/integration`; make each non-interactive and non-zero on failure; document exact invocations; add no workflow YAML.

Acceptance: all four commands run independently; unit never collects integration tests; integration never collects unit tests; no CI workflow file changed.

### PR003 — xdl-pr003-git-policy-validator

Branch `test/xdl-pr003-git-policy-validator`; commit scope `test(xdl-pr003-git-policy-validator): ...`; depends on PR001.

Owned paths: `scripts/ci/validate_git_policy.py`, `tests/unit/test_git_policy.py`, policy fixtures only.

Tasks: validate Conventional Commit syntax; extract exact `xdl-prNNN-*` work-order from branch; require that exact value in every introduced commit subject; require it in PR title when metadata is supplied; reject malformed branch names; remain read-only toward GitHub.

Acceptance: valid branch/commit/title passes; invalid Conventional Commit fails; missing work-order in branch fails; missing work-order in any commit fails; missing work-order in PR title fails; validator cannot mutate repository state.

### PR004 — xdl-pr004-push-quality-workflow

Branch `ci/xdl-pr004-push-quality-workflow`; commit scope `ci(xdl-pr004-push-quality-workflow): ...`; depends on PR002+PR003.

Owned path: `.github/workflows/push-quality.yml` only.

Tasks: trigger on non-main branch pushes; define independent jobs named `lint`, `type`, `unit`, `integration`, `policy`; use Python 3.14.7; ensure the four quality jobs have no `needs` relationship among themselves; create final `push-gate` depending on all five; fail aggregate on failed/cancelled/unexpectedly skipped required job.

Acceptance: workflow validates; representative push exposes the four quality jobs in parallel; policy runs separately; `push-gate` cannot succeed unless all required jobs succeed.

### PR005 — xdl-pr005-merge-quality-workflow

Branch `ci/xdl-pr005-merge-quality-workflow`; commit scope `ci(xdl-pr005-merge-quality-workflow): ...`; depends on PR002+PR003.

Owned path: `.github/workflows/merge-quality.yml` only.

Tasks: trigger on PRs targeting main; define independent `lint`, `type`, `unit`, `integration`, `policy`; use Python 3.14.7; create final stable check named exactly `merge-gate`; do not add any merge/push bypass token.

Acceptance: workflow validates; four quality jobs are parallel; failed/cancelled required job prevents `merge-gate`; check is exposed exactly as `merge-gate`.

### PR006 — xdl-pr006-main-protection-automerge

Branch `chore/xdl-pr006-main-protection-automerge`; commit scope `chore(xdl-pr006-main-protection-automerge): ...`; depends on PR004+PR005 and observed successful workflow runs.

Owned scope: GitHub repository settings and `docs/repository-governance.md` only.

Tasks: enable auto-merge; protect `main`; require PRs; require `merge-gate`; reject force pushes and branch deletion; prevent normal direct feature pushes; document exact weak-agent auto-merge procedure.

Acceptance: GitHub reports `main` protected; direct feature push/force push/delete are denied; a PR cannot merge with pending/failing `merge-gate`; a review-ready PR placed into auto-merge completes only after required checks pass.

### PR007 — xdl-pr007-postgres-market-schema

Branch `feat/xdl-pr007-postgres-market-schema`; commit scope `feat(xdl-pr007-postgres-market-schema): ...`; depends on PR006.

Owned paths: `sql/schema/001_portfell_market.sql`, `src/xetra_data_loader/contracts/postgres_market.py`, schema unit/integration tests only.

Tasks: create `portfell_market`; define `listings`, `eod_quotes`, `dividends`, `splits`; enforce frozen business keys; use exact `TIMESTAMPTZ(6)` for timestamp fields; preserve `trade_date DATE`; define matching typed DTOs; reject naive datetimes.

Acceptance: DDL recreates on empty PostgreSQL; introspection confirms exact timestamp types; DTO names/nullability match DDL; duplicate-key and naive-datetime cases fail.

### PR008 — xdl-pr008-postgres-role-grants

Branch `feat/xdl-pr008-postgres-role-grants`; commit scope `feat(xdl-pr008-postgres-role-grants): ...`; depends on PR007.

Owned paths: `sql/roles/002_loader_roles.sql`, `tests/integration/test_postgres_roles.py` only.

Tasks: define `portfell_data_loader` writer grants; define `portfell_app` SELECT-only on `portfell_market`; deny app INSERT/UPDATE/DELETE/DDL; deny app access to `portfell_loader_sync`.

Acceptance: writer performs required DML; app selects market tables; every app mutation/DDL attempt fails; app loader-sync access fails.

### PR009 — xdl-pr009-medallion-core-contract

Branch `feat/xdl-pr009-medallion-core-contract`; commit scope `feat(xdl-pr009-medallion-core-contract): ...`; depends on PR006.

Owned paths: `src/xetra_data_loader/medallion/core.py`, `medallion/layout.py`, corresponding unit tests.

Tasks: define Bronze/Silver/Gold path rules; define manifest fields for dataset/run/source bounds/counts/fingerprints/timestamps; separate semantic from run/fetch metadata; define deterministic serialization.

Acceptance: identical semantic fixture gives identical semantic fingerprint; changing run/fetch metadata alone leaves semantic fingerprint unchanged; invalid layer/path combination fails closed.

### PR010 — xdl-pr010-listing-dataset-contract

Branch `feat/xdl-pr010-listing-dataset-contract`; commit scope `feat(xdl-pr010-listing-dataset-contract): ...`; depends on PR009.

Owned paths: `src/xetra_data_loader/contracts/listings.py`, listing-only fixtures/tests.

Tasks: define raw Bronze listing fields; normalized Silver fields; Gold fields matching PR007; normalize ISIN; freeze `(isin,exchange,code)` identity; define deterministic field ordering.

Acceptance: non-empty normalized ISIN retained; empty/null ISIN excluded from normalized layer; same ISIN with distinct code remains distinct; round-trip output is deterministic.

### PR011 — xdl-pr011-quote-dataset-contract

Branch `feat/xdl-pr011-quote-dataset-contract`; commit scope `feat(xdl-pr011-quote-dataset-contract): ...`; depends on PR009.

Owned paths: `src/xetra_data_loader/contracts/quotes.py`, quote-only fixtures/tests.

Tasks: define Bronze/Silver/Gold quote fields; freeze key `(isin,exchange,code,trade_date)`; derive aware UTC midnight `timestamp_eod`; define semantic comparison fields and seven-day-overlap boundary behavior.

Acceptance: `timestamp_eod` is UTC midnight; no physical close time is inferred; duplicate key fails; fetch/run metadata does not affect semantic equality.

### PR012 — xdl-pr012-corporate-action-contract

Branch `feat/xdl-pr012-corporate-action-contract`; commit scope `feat(xdl-pr012-corporate-action-contract): ...`; depends on PR009.

Owned paths: `src/xetra_data_loader/contracts/corporate_actions.py`, corporate-action fixtures/tests.

Tasks: define separate dividend and split normalized fields; define deterministic SHA-256 `event_key`; define correction and retraction representation; exclude run IDs/fetch timestamps/DB IDs from event identity.

Acceptance: identical business event gives identical event key; changed business field changes semantic identity/reconciliation deterministically; run metadata change does not alter identity; dividend and split schemas remain distinct.

### PR013 — xdl-pr013-eodhd-transport

Branch `feat/xdl-pr013-eodhd-transport`; commit scope `feat(xdl-pr013-eodhd-transport): ...`; depends on PR006.

Owned paths: `src/xetra_data_loader/ingestion/eodhd/client.py`, `retry.py`, `rate_limit.py`, transport-only tests/fixtures.

Tasks: read EODHD token from environment; typed GET transport with timeout; bounded retry/backoff; rate-limit handling; fixture transport seam; scrub credentials from logs/errors.

Acceptance: missing token fails clearly; retryable failure retries within bound; permanent failure surfaces typed error/non-zero behavior; logs contain no token/full secret URL.

### PR014 — xdl-pr014-xetra-listing-ingestion

Branch `feat/xdl-pr014-xetra-listing-ingestion`; commit scope `feat(xdl-pr014-xetra-listing-ingestion): ...`; depends on PR010+PR013.

Owned paths: `src/xetra_data_loader/ingestion/listings.py`, listing-ingestion tests/fixtures.

Tasks: fetch XETRA exchange symbols through PR013; persist raw Bronze payload; normalize via PR010; retain every XETRA row with non-empty normalized ISIN; do not apply ETF/UCITS/type/country/currency filters; preserve duplicate ISIN under distinct identity.

Acceptance: mixed fixture retains every non-empty-ISIN identity; only empty/null ISIN is excluded from normalized output; repeated response produces same semantic output.

### PR015 — xdl-pr015-eod-quote-ingestion

Branch `feat/xdl-pr015-eod-quote-ingestion`; commit scope `feat(xdl-pr015-eod-quote-ingestion): ...`; depends on PR011+PR013.

Owned paths: `src/xetra_data_loader/ingestion/quotes.py`, quote-ingestion tests/fixtures.

Tasks: fetch by exchange/code; full-history mode; incremental start = last business date minus seven calendar days; normalize through PR011; persist Bronze/Silver; detect changed historical rows inside overlap.

Acceptance: identical replay = no semantic change; one corrected overlap row detected exactly once; one new business date creates one new business key; all derived timestamps are aware UTC.

### PR016 — xdl-pr016-dividend-ingestion

Branch `feat/xdl-pr016-dividend-ingestion`; commit scope `feat(xdl-pr016-dividend-ingestion): ...`; depends on PR012+PR013.

Owned paths: `src/xetra_data_loader/ingestion/dividends.py`, dividend-only tests/fixtures.

Tasks: fetch dividends; full-history mode; seven-day-overlap refresh; normalize through PR012; persist Bronze/Silver dividend artifacts; detect dividend corrections and source retractions.

Acceptance: identical replay leaves same event keys/semantics; one correction is reconciled once; removed overlap event is marked as retraction; no split code is added or modified.

### PR017 — xdl-pr017-split-ingestion

Branch `feat/xdl-pr017-split-ingestion`; commit scope `feat(xdl-pr017-split-ingestion): ...`; depends on PR012+PR013.

Owned paths: `src/xetra_data_loader/ingestion/splits.py`, split-only tests/fixtures.

Tasks: fetch splits; full-history mode; seven-day-overlap refresh; normalize through PR012; persist Bronze/Silver split artifacts; detect split corrections and source retractions.

Acceptance: identical replay leaves same event keys/semantics; one correction is reconciled once; removed overlap event is marked as retraction; no dividend code is added or modified.

### PR018 — xdl-pr018-gold-listing-build

Branch `feat/xdl-pr018-gold-listing-build`; commit scope `feat(xdl-pr018-gold-listing-build): ...`; depends on PR007+PR014.

Owned paths: `src/xetra_data_loader/application/gold/listings.py`, listing-Gold tests only.

Tasks: build listing Gold from normalized listing input; match PR007 DTO/DDL; enforce required fields and unique listing key; emit row count, semantic fingerprint and validation result.

Acceptance: Gold loads into listing table without ad-hoc transformation; duplicate/invalid key fails closed; same semantic input produces same output fingerprint.

### PR019 — xdl-pr019-gold-quote-build

Branch `feat/xdl-pr019-gold-quote-build`; commit scope `feat(xdl-pr019-gold-quote-build): ...`; depends on PR007+PR015.

Owned paths: `src/xetra_data_loader/application/gold/quotes.py`, quote-Gold tests only.

Tasks: build quote Gold; match PR007 DTO/DDL; enforce quote business key; enforce `trade_date`/UTC-anchor rules; emit deterministic counts/fingerprint/validation.

Acceptance: Gold loads into quote table directly; duplicate key or naive timestamp fails closed; semantic replay gives identical fingerprint.

### PR020 — xdl-pr020-gold-dividend-build

Branch `feat/xdl-pr020-gold-dividend-build`; commit scope `feat(xdl-pr020-gold-dividend-build): ...`; depends on PR007+PR016.

Owned paths: `src/xetra_data_loader/application/gold/dividends.py`, dividend-Gold tests only.

Tasks: build dividend Gold; match PR007 DTO/DDL; enforce dividend business key/event key; carry explicit correction/retraction reconciliation; emit deterministic validation metadata.

Acceptance: direct load into dividend table succeeds; duplicate/invalid event fails closed; correction/retraction fixture gives exactly intended normalized state; no split files changed.

### PR021 — xdl-pr021-gold-split-build

Branch `feat/xdl-pr021-gold-split-build`; commit scope `feat(xdl-pr021-gold-split-build): ...`; depends on PR007+PR017.

Owned paths: `src/xetra_data_loader/application/gold/splits.py`, split-Gold tests only.

Tasks: build split Gold; match PR007 DTO/DDL; enforce split business key/event key; carry explicit correction/retraction reconciliation; emit deterministic validation metadata.

Acceptance: direct load into split table succeeds; duplicate/invalid event fails closed; correction/retraction fixture gives exactly intended normalized state; no dividend files changed.

### PR022 — xdl-pr022-postgres-sync-core

Branch `feat/xdl-pr022-postgres-sync-core`; commit scope `feat(xdl-pr022-postgres-sync-core): ...`; depends on PR008+PR009 only.

Owned paths: `sql/schema/003_portfell_loader_sync.sql`, `src/xetra_data_loader/application/postgres_sync/core.py`, `state.py`, sync-core tests.

Tasks: create `portfell_loader_sync` run/state tables with UTC `TIMESTAMPTZ(6)`; implement semantic row fingerprint helper; define one transaction boundary coupling serving mutation and sync-state advance; define generic insert/update/retraction counters; prove rollback with synthetic fixtures; add no entity-specific publication SQL.

Acceptance: injected failure before commit changes neither serving fixture data nor sync state; semantic fingerprint ignores run/fetch metadata; loader timestamp introspection is exact; no listings/quotes/dividends/splits sync implementation exists here.

### PR023 — xdl-pr023-postgres-listing-sync

Branch `feat/xdl-pr023-postgres-listing-sync`; commit scope `feat(xdl-pr023-postgres-listing-sync): ...`; depends on PR018+PR022.

Owned paths: `src/xetra_data_loader/application/postgres_sync/listings.py`, listing-sync integration tests.

Tasks: publish listing Gold using PR022 transaction/state primitives; conflict-safe UPSERT on listing key; compare semantic fingerprints; report insert/update/no-op counts.

Acceptance: first fixture inserts expected rows; identical replay produces zero semantic mutations; one changed listing produces exactly one semantic update; failed transaction leaves state/data unchanged.

### PR024 — xdl-pr024-postgres-quote-sync

Branch `feat/xdl-pr024-postgres-quote-sync`; commit scope `feat(xdl-pr024-postgres-quote-sync): ...`; depends on PR019+PR022.

Owned paths: `src/xetra_data_loader/application/postgres_sync/quotes.py`, quote-sync integration tests.

Tasks: publish quote Gold using PR022; UPSERT on `(isin,exchange,code,trade_date)`; distinguish no-op/correction/new-date; transactionally advance quote sync state.

Acceptance: first fixture inserts expected rows; identical replay = zero mutations; one corrected row = exactly one update; one new date = exactly one insert; rollback preserves state/data.

### PR025 — xdl-pr025-postgres-dividend-sync

Branch `feat/xdl-pr025-postgres-dividend-sync`; commit scope `feat(xdl-pr025-postgres-dividend-sync): ...`; depends on PR020+PR022.

Owned paths: `src/xetra_data_loader/application/postgres_sync/dividends.py`, dividend-sync integration tests.

Tasks: publish dividend Gold using PR022; reconcile insert/correction/retraction by frozen business identity; transactionally advance dividend state; report exact mutation counts.

Acceptance: initial load correct; identical replay = zero mutations; one correction affects only intended event; one retraction removes/deactivates only intended event per contract; rollback preserves state/data; no split files changed.

### PR026 — xdl-pr026-postgres-split-sync

Branch `feat/xdl-pr026-postgres-split-sync`; commit scope `feat(xdl-pr026-postgres-split-sync): ...`; depends on PR021+PR022.

Owned paths: `src/xetra_data_loader/application/postgres_sync/splits.py`, split-sync integration tests.

Tasks: publish split Gold using PR022; reconcile insert/correction/retraction by frozen business identity; transactionally advance split state; report exact mutation counts.

Acceptance: initial load correct; identical replay = zero mutations; one correction affects only intended event; one retraction removes/deactivates only intended event per contract; rollback preserves state/data; no dividend files changed.

### PR027 — xdl-pr027-weekly-pipeline-orchestrator

Branch `feat/xdl-pr027-weekly-pipeline-orchestrator`; commit scope `feat(xdl-pr027-weekly-pipeline-orchestrator): ...`; depends on PR023+PR024+PR025+PR026.

Owned paths: `src/xetra_data_loader/application/pipeline.py`, `src/xetra_data_loader/ops/run_weekly.py`, orchestration tests.

Tasks: compose exact order `listings -> quotes -> dividends -> splits -> Gold validation -> four PostgreSQL syncs -> verification`; stop on first failure; emit structured stage/run results; expose one non-interactive weekly command; add no lock and no scheduler.

Acceptance: success fixture executes exact order; failed stage prevents every downstream stage; success returns complete stage summary; no cron/locking implementation exists.

### PR028 — xdl-pr028-loader-lock-restart

Branch `feat/xdl-pr028-loader-lock-restart`; commit scope `feat(xdl-pr028-loader-lock-restart): ...`; depends on PR027.

Owned paths: `src/xetra_data_loader/ops/locking.py`, `checkpoints.py`, `locked_runner.py`, related tests.

Tasks: wrap PR027 runner in one process/distributed lock; deny concurrent weekly invocation; persist restart checkpoints outside semantic row identity; safely recover/release lock after failure; restart without duplicate semantic publication.

Acceptance: second concurrent invocation cannot execute pipeline; failure releases/recovers lock safely; restart from fixture failure does not duplicate DB semantic mutations.

### PR029 — xdl-pr029-sunday-1100-schedule

Branch `feat/xdl-pr029-sunday-1100-schedule`; commit scope `feat(xdl-pr029-sunday-1100-schedule): ...`; depends on PR027.

Owned paths: cron/scheduler deployment files and scheduler tests only.

Tasks: commit literal `CRON_TZ=Europe/Vienna`; commit literal `0 11 * * 0`; invoke weekly runner entry point; test Vienna-local DST behavior without converting schedule to UTC.

Acceptance: committed expression is exact; generated/parsed next-run examples remain Sunday 11:00 Vienna local time before/after DST; no pipeline business code changed.

### PR030 — xdl-pr030-destructive-reset-guard

Branch `feat/xdl-pr030-destructive-reset-guard`; commit scope `feat(xdl-pr030-destructive-reset-guard): ...`; depends on PR009+PR022.

Owned paths: `src/xetra_data_loader/ops/destructive_reset.py`, reset-only tests.

Tasks: enumerate loader-owned DB schemas/tables and medallion paths; provide dry-run exact scope; require literal `--confirm-destructive-reset`; delete only loader-owned state; never touch unrelated/Portfell optimizer state.

Acceptance: without confirmation zero destructive actions; dry run lists exact targets; confirmed fixture reset removes all loader-owned targets; unrelated schema/path survives unchanged.

### PR031 — xdl-pr031-full-xetra-bootstrap

Branch `feat/xdl-pr031-full-xetra-bootstrap`; commit scope `feat(xdl-pr031-full-xetra-bootstrap): ...`; depends on PR027+PR030.

Owned paths: `src/xetra_data_loader/ops/bootstrap.py`, bootstrap-only tests.

Tasks: require/forward destructive confirmation; perform scoped reset; discover full current non-empty-ISIN XETRA universe; run full available quote/dividend/split history; build Gold; publish all entities; verify counts/keys/date bounds/sync state; record measured requests/retries/elapsed time/failures/output rows without estimating duration.

Acceptance: absent confirmation performs zero reset/bootstrap mutation; clean fixture bootstrap reaches verified serving state; subsequent unchanged weekly fixture run is a semantic no-op; metrics are measured and emitted.

### PR032 — xdl-pr032-loader-e2e-gate

Branch `test/xdl-pr032-loader-e2e-gate`; commit scope `test(xdl-pr032-loader-e2e-gate): ...`; depends on PR028+PR029+PR031.

Owned paths: `tests/e2e/*`, acceptance-report generator and fixture outputs only.

Tasks: bootstrap from empty loader state; verify all fixture non-empty-ISIN listings; verify quote/dividend/split publication; replay unchanged source and assert zero mutations; test one quote correction; test dividend correction/retraction; test split correction/retraction; add a new listing and verify next cycle; introspect exact timestamp types/UTC; verify `portfell_app` read-only; verify lock behavior and exact scheduler; emit machine-readable serving-contract/acceptance report.

Acceptance: all scenarios pass on one SHA; lint/type/unit/integration/policy/merge-gate green; no test imports Portfell; machine-readable artifact contains schema version/columns/types/keys/fixture expectations and is sufficient for Portfell cross-repo smoke testing.

## Cross-repository handoff to Portfell

Portfell may begin its read-contract work after XDL-PR007 freezes the consumer DDL; permission-level integration waits for XDL-PR008. Portfell's final cross-repository contract gate is blocked until XDL-PR032 is merged and green.

Portfell may consume only the PostgreSQL contract, read-only-role contract, and final machine-readable acceptance fixtures/report. It must not import `xetra-data-loader`, call EODHD, read medallion files, or mutate loader schemas.

## Mapping from superseded coarse loader plan

| Old plan | Atomic replacement |
| --- | --- |
| PR297 repository bootstrap/governance | XDL-PR001..PR006 |
| PR298 PostgreSQL serving contract | XDL-PR007..PR008 |
| PR299 medallion contracts | XDL-PR009..PR012 |
| PR300 listing ingestion | XDL-PR013 + PR014 |
| PR301 quote ingestion | XDL-PR011 + PR013 + PR015 |
| PR302 corporate actions | XDL-PR012 + PR013 + PR016 + PR017 |
| PR303 Gold serving build | XDL-PR018..PR021 |
| PR304 PostgreSQL sync | XDL-PR022..PR026 |
| PR305 weekly runner/schedule | XDL-PR027..PR029 |
| PR306 destructive bootstrap | XDL-PR030..PR031 |
| PR307 end-to-end gate | XDL-PR032 |

Any old PR297-PR307 implementation branch is superseded and must not be merged as current authority.

## Completion gate

Complete only when XDL-PR001..PR032 are merged from clean protected `main` and all conditions hold: Python 3.14.7 `.venv` reproducible/untracked; push+merge gates parallelize lint/type/unit/integration; policy CI enforces Conventional Commits and exact work-order naming; main protected with required merge-gate and gated auto-merge; full XETRA non-empty-ISIN universe discoverable; full quote/dividend/split bootstrap works; Gold validates; PostgreSQL publication transactional/idempotent; unchanged replay is zero-mutation; corrections/retractions deterministic; timestamp contract exact; `portfell_app` read-only; Sunday 11:00 Vienna schedule exact; destructive reset confirmed/scoped; final E2E acceptance artifact green.