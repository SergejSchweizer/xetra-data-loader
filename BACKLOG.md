Last reviewed: 2026-08-22

# XETRA Data Loader — Atomic Parallel Backlog

## 1. Status authority

This file is the complete implementation authority for `SergejSchweizer/xetra-data-loader`.

The former coarse loader plan `PR297`-`PR307` is superseded. It is replaced by repository-local work orders `XDL-PR001` through `XDL-PR033`, designed for multiple weak agents that must work independently with minimal merge conflicts.

Planning gate:

- work-order: `xdl-pr000-backlog-restructure`
- branch: `docs/xdl-pr000-backlog-restructure`
- required commit scope: `docs(xdl-pr000-backlog-restructure): ...`
- Git status: merged in `origin/main`

The implementation gate was satisfied by XDL-PR000 in `origin/main`.

## 2. Frozen architecture

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

Frozen rules:

- initial universe: every EODHD XETRA listing with normalized non-empty ISIN;
- no ETF/UCITS/fund/type/country/currency prefilter;
- listing identity: `(isin, exchange, code)`;
- quote identity: `(isin, exchange, code, trade_date)`;
- dividend/split identity: `(isin, exchange, code, event_key)`;
- `event_key`: deterministic SHA-256 from normalized provider business fields only;
- all PostgreSQL timestamp columns: exactly `TIMESTAMPTZ(6)`;
- all PostgreSQL sessions: UTC;
- `trade_date` stays `DATE`;
- `timestamp_eod = trade_date 00:00:00+00:00`; it is not a physical exchange-close timestamp;
- incremental refresh overlap: seven calendar days;
- unchanged source replay must cause zero semantic PostgreSQL mutations;
- exact scheduler: `CRON_TZ=Europe/Vienna` and `0 12 * * 0`;
- passwords, provider tokens, and full DSNs are never committed;
- Portfell code, analytics, UI, users/tenants/projects, and authorization do not belong here;
- the project is not complete until a real full XETRA bootstrap has been completely synchronized to PostgreSQL `10.10.1.3:54321` and independently verified by XDL-PR033.

## 3. Git / branch / weak-agent contract

Every work order is self-contained. An agent may read dependencies but edits only its owned paths.

Mandatory rules:

1. Start from the exact merged dependency SHA.
2. Record `git status --short --branch` before edits and in the PR work log.
3. If any dependency is unmerged, stop; do not invent a workaround.
4. Never branch from a sibling work-order branch.
5. Parallel siblings start from the same predecessor merge SHA.
6. The exact work-order name must appear literally in branch name, every commit message, and PR title.
7. Every commit follows Conventional Commits.
8. Example:

```text
Work-order: xdl-pr015-eod-quote-ingestion
Branch:     feat/xdl-pr015-eod-quote-ingestion
Commit:     feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
PR title:   feat(xdl-pr015-eod-quote-ingestion): add deterministic quote ingestion
```

9. Do not edit sibling-owned files, add compatibility shims, broaden scope, or perform opportunistic refactors.
10. Run focused tests plus all available repository quality gates on the same head SHA.
11. After XDL-PR006, `main` is protected and merge occurs only through required `merge-gate`; review-ready implementation PRs use auto-merge.

Python / quality baseline:

- CPython `3.14.7`;
- repository-local `.venv` built with Python 3.14.7 and never tracked;
- push and merge CI each run `lint`, `type`, `unit`, `integration` as four independent parallel jobs;
- separate fast `policy` job validates Conventional Commits and exact work-order naming;
- final `push-gate` / `merge-gate` aggregate all required checks.

## 4. Optimized dependency graph

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
                                |
                              PR033
```

Interpretation: PR022 starts as soon as DB roles and medallion core exist; it does not wait for entity ingestion or Gold builders. Each entity then progresses independently through contract -> ingestion -> Gold -> PostgreSQL sync. PR033 is intentionally final and serial: it is the real target-PostgreSQL completion gate, not a fixture-only test.

Safe parallel waves:

- Wave 1: PR002 + PR003.
- Wave 2: PR004 + PR005.
- Wave 3: PR007 + PR009 + PR013.
- Wave 4: PR008 + PR010 + PR011 + PR012.
- Wave 5: PR014 + PR015 + PR016 + PR017; PR022 starts independently once PR008+PR009 are green.
- Wave 6: PR018 + PR019 + PR020 + PR021; PR030 can start after PR022.
- Wave 7: PR023 + PR024 + PR025 + PR026, each as soon as its own Gold builder plus PR022 are merged.
- Wave 8: PR028 + PR029 after PR027.
- Final serial gates: PR031 -> PR032 -> PR033.

## 5. Work-order index

| ID | Work-order | Branch | Depends on | Atomic result | Git status |
| --- | --- | --- | --- | --- | --- |
| PR001 | `xdl-pr001-python-repository-baseline` | `chore/xdl-pr001-python-repository-baseline` | PR000 | Python/.venv/minimal package skeleton | merged in `origin/main` |
| PR002 | `xdl-pr002-quality-command-contract` | `chore/xdl-pr002-quality-command-contract` | PR001 | canonical local quality commands | merged in `origin/main` |
| PR003 | `xdl-pr003-git-policy-validator` | `test/xdl-pr003-git-policy-validator` | PR001 | machine-enforced git/PR naming policy | merged in `origin/main` |
| PR004 | `xdl-pr004-push-quality-workflow` | `ci/xdl-pr004-push-quality-workflow` | PR002+PR003 | parallel push gate | merged in `origin/main` |
| PR005 | `xdl-pr005-merge-quality-workflow` | `ci/xdl-pr005-merge-quality-workflow` | PR002+PR003 | parallel merge gate | merged in `origin/main` |
| PR006 | `xdl-pr006-main-protection-automerge` | `chore/xdl-pr006-main-protection-automerge` | PR004+PR005 | protected main + required gate + auto-merge | merged in `origin/main` |
| PR007 | `xdl-pr007-postgres-market-schema` | `feat/xdl-pr007-postgres-market-schema` | PR006 | market DDL/DTO/timestamp contract | merged in `origin/main` |
| PR008 | `xdl-pr008-postgres-role-grants` | `feat/xdl-pr008-postgres-role-grants` | PR007 | writer/read-only grants | merged in `origin/main` |
| PR009 | `xdl-pr009-medallion-core-contract` | `feat/xdl-pr009-medallion-core-contract` | PR006 | medallion layout/manifest primitives | merged in `origin/main` |
| PR010 | `xdl-pr010-listing-dataset-contract` | `feat/xdl-pr010-listing-dataset-contract` | PR009 | listing dataset contract | merged in `origin/main` |
| PR011 | `xdl-pr011-quote-dataset-contract` | `feat/xdl-pr011-quote-dataset-contract` | PR009 | quote dataset contract | merged in `origin/main` |
| PR012 | `xdl-pr012-corporate-action-contract` | `feat/xdl-pr012-corporate-action-contract` | PR009 | dividend/split event contract | merged in `origin/main` |
| PR013 | `xdl-pr013-eodhd-transport` | `feat/xdl-pr013-eodhd-transport` | PR006 | provider HTTP/retry/rate-limit seam | merged in `origin/main` |
| PR014 | `xdl-pr014-xetra-listing-ingestion` | `feat/xdl-pr014-xetra-listing-ingestion` | PR010+PR013 | all XETRA non-empty-ISIN listings | merged in `origin/main` |
| PR015 | `xdl-pr015-eod-quote-ingestion` | `feat/xdl-pr015-eod-quote-ingestion` | PR011+PR013 | full/overlap quote ingestion | merged in `origin/main` |
| PR016 | `xdl-pr016-dividend-ingestion` | `feat/xdl-pr016-dividend-ingestion` | PR012+PR013 | full/overlap dividend ingestion | merged in `origin/main` |
| PR017 | `xdl-pr017-split-ingestion` | `feat/xdl-pr017-split-ingestion` | PR012+PR013 | full/overlap split ingestion | merged in `origin/main` |
| PR018 | `xdl-pr018-gold-listing-build` | `feat/xdl-pr018-gold-listing-build` | PR007+PR014 | validated listing Gold | merged in `origin/main` |
| PR019 | `xdl-pr019-gold-quote-build` | `feat/xdl-pr019-gold-quote-build` | PR007+PR015 | validated quote Gold | merged in `origin/main` |
| PR020 | `xdl-pr020-gold-dividend-build` | `feat/xdl-pr020-gold-dividend-build` | PR007+PR016 | validated dividend Gold | merged in `origin/main` |
| PR021 | `xdl-pr021-gold-split-build` | `feat/xdl-pr021-gold-split-build` | PR007+PR017 | validated split Gold | merged in `origin/main` |
| PR022 | `xdl-pr022-postgres-sync-core` | `feat/xdl-pr022-postgres-sync-core` | PR008+PR009 | transactional sync/state/fingerprint core | merged in `origin/main` |
| PR023 | `xdl-pr023-postgres-listing-sync` | `feat/xdl-pr023-postgres-listing-sync` | PR018+PR022 | idempotent listing publication | merged in `origin/main` |
| PR024 | `xdl-pr024-postgres-quote-sync` | `feat/xdl-pr024-postgres-quote-sync` | PR019+PR022 | idempotent quote publication | merged in `origin/main` |
| PR025 | `xdl-pr025-postgres-dividend-sync` | `feat/xdl-pr025-postgres-dividend-sync` | PR020+PR022 | idempotent dividend publication | merged in `origin/main` |
| PR026 | `xdl-pr026-postgres-split-sync` | `feat/xdl-pr026-postgres-split-sync` | PR021+PR022 | idempotent split publication | merged in `origin/main` |
| PR027 | `xdl-pr027-weekly-pipeline-orchestrator` | `feat/xdl-pr027-weekly-pipeline-orchestrator` | PR023-PR026 | ordered weekly command including verification | merged in `origin/main` |
| PR028 | `xdl-pr028-loader-lock-restart` | `feat/xdl-pr028-loader-lock-restart` | PR027 | non-overlap/restart-safe wrapper | merged in `origin/main` |
| PR029 | `xdl-pr029-sunday-1100-schedule` | `feat/xdl-pr029-sunday-1100-schedule` | PR027 | exact Sunday scheduler | merged in `origin/main` |
| PR030 | `xdl-pr030-destructive-reset-guard` | `feat/xdl-pr030-destructive-reset-guard` | PR009+PR022 | scoped confirmed reset primitive | merged in `origin/main` |
| PR031 | `xdl-pr031-full-xetra-bootstrap` | `feat/xdl-pr031-full-xetra-bootstrap` | PR027+PR030 | full-history bootstrap command | merged in `origin/main` |
| PR032 | `xdl-pr032-loader-e2e-gate` | `test/xdl-pr032-loader-e2e-gate` | PR028+PR029+PR031 | production-like fixture acceptance gate | merged in `origin/main` |
| PR033 | `xdl-pr033-production-postgres-full-sync-verification` | `chore/xdl-pr033-production-postgres-full-sync-verification` | PR032 | real full sync to target PostgreSQL + independent verification | implemented locally; real-target acceptance pending |

## 6. Exact atomic PR specifications

### PR001 — xdl-pr001-python-repository-baseline
Branch `chore/xdl-pr001-python-repository-baseline`; commit scope `chore(xdl-pr001-python-repository-baseline): ...`; depends on PR000.
Owned paths: `.python-version`, `.gitignore`, package metadata in `pyproject.toml`, minimal `src/xetra_data_loader/*`, test-root placeholders, README setup section.
Tasks: pin Python 3.14.7; create installable src layout; document creation/activation of `.venv`; ignore `.venv/`; create unit/integration roots.
Acceptance: `.venv` reports exactly Python 3.14.7; package installs/imports; no `.venv` files tracked; no provider/DB/business implementation.

### PR002 — xdl-pr002-quality-command-contract
Branch `chore/xdl-pr002-quality-command-contract`; commit scope `chore(xdl-pr002-quality-command-contract): ...`; depends on PR001.
Owned paths: quality-tool config and `scripts/quality/*` only.
Tasks: one lint, type, unit, integration command; unit and integration collection isolated; commands non-interactive and fail non-zero.
Acceptance: all four commands run independently; each collects only intended tests; no workflow YAML changed.

### PR003 — xdl-pr003-git-policy-validator
Branch `test/xdl-pr003-git-policy-validator`; commit scope `test(xdl-pr003-git-policy-validator): ...`; depends on PR001.
Owned paths: `scripts/ci/validate_git_policy.py`, policy unit tests/fixtures.
Tasks: validate Conventional Commits; exact `xdl-prNNN-*` in branch, every introduced commit, PR title.
Acceptance: valid examples pass; each malformed/missing case fails; validator is read-only.

### PR004 — xdl-pr004-push-quality-workflow
Branch `ci/xdl-pr004-push-quality-workflow`; commit scope `ci(xdl-pr004-push-quality-workflow): ...`; depends on PR002+PR003.
Owned path: `.github/workflows/push-quality.yml` only.
Tasks: non-main branch trigger; independent `lint`, `type`, `unit`, `integration`, `policy`; final `push-gate`; Python 3.14.7.
Acceptance: four code-quality jobs are parallel; `push-gate` cannot pass if any required job fails/cancels/skips unexpectedly.

### PR005 — xdl-pr005-merge-quality-workflow
Branch `ci/xdl-pr005-merge-quality-workflow`; commit scope `ci(xdl-pr005-merge-quality-workflow): ...`; depends on PR002+PR003.
Owned path: `.github/workflows/merge-quality.yml` only.
Tasks: PR-to-main trigger; independent `lint`, `type`, `unit`, `integration`, `policy`; final check exactly `merge-gate`; no bypass token.
Acceptance: four code-quality jobs are parallel; failing/cancelled required job blocks `merge-gate`.

### PR006 — xdl-pr006-main-protection-automerge
Branch `chore/xdl-pr006-main-protection-automerge`; commit scope `chore(xdl-pr006-main-protection-automerge): ...`; depends on PR004+PR005 and observed green workflow runs.
Owned scope: GitHub repository settings + `docs/repository-governance.md`.
Tasks: enable auto-merge; protect `main`; require PR and `merge-gate`; block direct feature pushes, force pushes, deletion; document auto-merge procedure.
Acceptance: GitHub reports protection active; representative PR cannot merge before required checks and auto-merges only after all requirements pass.

### PR007 — xdl-pr007-postgres-market-schema
Branch `feat/xdl-pr007-postgres-market-schema`; commit scope `feat(xdl-pr007-postgres-market-schema): ...`; depends on PR006.
Owned paths: `sql/schema/001_portfell_market.sql`, typed market DTOs, schema tests.
Tasks: create `portfell_market`; tables `listings`, `eod_quotes`, `dividends`, `splits`; frozen keys; exact `TIMESTAMPTZ(6)`; `trade_date DATE`; reject naive datetime DTOs.
Acceptance: DDL recreates on empty PostgreSQL; introspection/types/keys exact; duplicate keys and naive datetimes fail.

### PR008 — xdl-pr008-postgres-role-grants
Branch `feat/xdl-pr008-postgres-role-grants`; commit scope `feat(xdl-pr008-postgres-role-grants): ...`; depends on PR007.
Owned paths: role SQL + role integration test.
Tasks: `xetra-data-loader` writer; `portfell_app` SELECT-only market schema; deny app DML/DDL and loader-sync access.
Acceptance: required writer DML works; all forbidden app operations fail.

### PR009 — xdl-pr009-medallion-core-contract
Branch `feat/xdl-pr009-medallion-core-contract`; commit scope `feat(xdl-pr009-medallion-core-contract): ...`; depends on PR006.
Owned paths: medallion core/layout + tests.
Tasks: Bronze/Silver/Gold paths; manifests; semantic vs run metadata; deterministic serialization/fingerprint.
Acceptance: semantic fingerprint stable under run-metadata changes; invalid layer/path fails.

### PR010 — xdl-pr010-listing-dataset-contract
Branch `feat/xdl-pr010-listing-dataset-contract`; commit scope `feat(xdl-pr010-listing-dataset-contract): ...`; depends on PR009.
Owned paths: listing contracts/fixtures/tests.
Tasks: Bronze/Silver/Gold listing fields; normalized ISIN; `(isin,exchange,code)` key; deterministic ordering.
Acceptance: only empty/null ISIN excluded; duplicate ISIN with distinct code retained; round-trip deterministic.

### PR011 — xdl-pr011-quote-dataset-contract
Branch `feat/xdl-pr011-quote-dataset-contract`; commit scope `feat(xdl-pr011-quote-dataset-contract): ...`; depends on PR009.
Owned paths: quote contracts/fixtures/tests.
Tasks: quote layers/key; UTC midnight `timestamp_eod`; semantic fields; seven-day overlap boundary.
Acceptance: no physical close inferred; duplicate key fails; run metadata does not change semantics.

### PR012 — xdl-pr012-corporate-action-contract
Branch `feat/xdl-pr012-corporate-action-contract`; commit scope `feat(xdl-pr012-corporate-action-contract): ...`; depends on PR009.
Owned paths: corporate-action contracts/fixtures/tests.
Tasks: separate dividend/split schemas; deterministic `event_key`; correction/retraction representation.
Acceptance: same event same key; changed business field deterministically changes reconciliation; run metadata excluded.

### PR013 — xdl-pr013-eodhd-transport
Branch `feat/xdl-pr013-eodhd-transport`; commit scope `feat(xdl-pr013-eodhd-transport): ...`; depends on PR006.
Owned paths: EODHD transport/retry/rate-limit + tests.
Tasks: token from env; typed GET; timeout; bounded retry/backoff; rate-limit handling; fixture seam; secret scrubbing.
Acceptance: missing token clear; retries bounded; permanent error surfaced; logs leak no token/full secret URL.

### PR014 — xdl-pr014-xetra-listing-ingestion
Branch `feat/xdl-pr014-xetra-listing-ingestion`; commit scope `feat(xdl-pr014-xetra-listing-ingestion): ...`; depends on PR010+PR013.
Owned paths: listing ingestion + fixtures/tests.
Tasks: fetch XETRA exchange symbols; Bronze raw; normalize; retain every non-empty-ISIN identity; no instrument filters.
Acceptance: mixed fixture preserves every valid identity and excludes only missing ISIN; replay deterministic.

### PR015 — xdl-pr015-eod-quote-ingestion
Branch `feat/xdl-pr015-eod-quote-ingestion`; commit scope `feat(xdl-pr015-eod-quote-ingestion): ...`; depends on PR011+PR013.
Owned paths: quote ingestion + fixtures/tests.
Tasks: fetch by exchange/code; full history; incremental from last business date minus seven calendar days; Bronze/Silver; correction detection.
Acceptance: replay no semantic change; corrected row detected once; new date one new key; timestamps aware UTC.

### PR016 — xdl-pr016-dividend-ingestion
Branch `feat/xdl-pr016-dividend-ingestion`; commit scope `feat(xdl-pr016-dividend-ingestion): ...`; depends on PR012+PR013.
Owned paths: dividend ingestion + fixtures/tests.
Tasks: full history; seven-day overlap; normalize; Bronze/Silver; corrections/retractions.
Acceptance: replay stable; correction once; removed overlap event retracted; split files untouched.

### PR017 — xdl-pr017-split-ingestion
Branch `feat/xdl-pr017-split-ingestion`; commit scope `feat(xdl-pr017-split-ingestion): ...`; depends on PR012+PR013.
Owned paths: split ingestion + fixtures/tests.
Tasks: full history; seven-day overlap; normalize; Bronze/Silver; corrections/retractions.
Acceptance: replay stable; correction once; removed overlap event retracted; dividend files untouched.

### PR018 — xdl-pr018-gold-listing-build
Branch `feat/xdl-pr018-gold-listing-build`; commit scope `feat(xdl-pr018-gold-listing-build): ...`; depends on PR007+PR014.
Owned paths: listing Gold builder + tests.
Tasks: build listing Gold; match DDL/DTO; validate required fields/key; emit count/fingerprint/result.
Acceptance: direct load-compatible; duplicate/invalid key fails; semantic fingerprint deterministic.

### PR019 — xdl-pr019-gold-quote-build
Branch `feat/xdl-pr019-gold-quote-build`; commit scope `feat(xdl-pr019-gold-quote-build): ...`; depends on PR007+PR015.
Owned paths: quote Gold builder + tests.
Tasks: build quote Gold; key/timestamp validation; deterministic count/fingerprint.
Acceptance: direct load-compatible; duplicate or naive timestamp fails; replay fingerprint stable.

### PR020 — xdl-pr020-gold-dividend-build
Branch `feat/xdl-pr020-gold-dividend-build`; commit scope `feat(xdl-pr020-gold-dividend-build): ...`; depends on PR007+PR016.
Owned paths: dividend Gold builder + tests.
Tasks: enforce dividend key/event key; correction/retraction reconciliation; deterministic validation metadata.
Acceptance: direct load-compatible; invalid/duplicate event fails; exact expected reconciled state; split files untouched.

### PR021 — xdl-pr021-gold-split-build
Branch `feat/xdl-pr021-gold-split-build`; commit scope `feat(xdl-pr021-gold-split-build): ...`; depends on PR007+PR017.
Owned paths: split Gold builder + tests.
Tasks: enforce split key/event key; correction/retraction reconciliation; deterministic validation metadata.
Acceptance: direct load-compatible; invalid/duplicate event fails; exact expected reconciled state; dividend files untouched.

### PR022 — xdl-pr022-postgres-sync-core
Branch `feat/xdl-pr022-postgres-sync-core`; commit scope `feat(xdl-pr022-postgres-sync-core): ...`; depends on PR008+PR009.
Owned paths: loader-sync schema, generic sync core/state + tests.
Tasks: `portfell_loader_sync` state/run tables with `TIMESTAMPTZ(6)`; semantic fingerprint; transaction coupling data mutation and state advance; generic mutation counters; rollback proof.
Acceptance: injected failure changes neither serving data nor sync state; run metadata excluded from fingerprint; no entity-specific sync code.

### PR023 — xdl-pr023-postgres-listing-sync
Branch `feat/xdl-pr023-postgres-listing-sync`; commit scope `feat(xdl-pr023-postgres-listing-sync): ...`; depends on PR018+PR022.
Owned paths: listing sync + integration test.
Tasks: conflict-safe UPSERT; semantic comparison; transaction/state; insert/update/no-op counts.
Acceptance: first load exact; replay zero mutations; one change exactly one update; rollback clean.

### PR024 — xdl-pr024-postgres-quote-sync
Branch `feat/xdl-pr024-postgres-quote-sync`; commit scope `feat(xdl-pr024-postgres-quote-sync): ...`; depends on PR019+PR022.
Owned paths: quote sync + integration test.
Tasks: UPSERT on quote key; distinguish no-op/correction/new date; transactional state.
Acceptance: initial exact; replay zero; correction one update; new date one insert; rollback clean.

### PR025 — xdl-pr025-postgres-dividend-sync
Branch `feat/xdl-pr025-postgres-dividend-sync`; commit scope `feat(xdl-pr025-postgres-dividend-sync): ...`; depends on PR020+PR022.
Owned paths: dividend sync + integration test.
Tasks: transactional insert/correction/retraction reconciliation and exact counters.
Acceptance: initial exact; replay zero; correction/retraction only intended event; rollback clean.

### PR026 — xdl-pr026-postgres-split-sync
Branch `feat/xdl-pr026-postgres-split-sync`; commit scope `feat(xdl-pr026-postgres-split-sync): ...`; depends on PR021+PR022.
Owned paths: split sync + integration test.
Tasks: transactional insert/correction/retraction reconciliation and exact counters.
Acceptance: initial exact; replay zero; correction/retraction only intended event; rollback clean.

### PR027 — xdl-pr027-weekly-pipeline-orchestrator
Branch `feat/xdl-pr027-weekly-pipeline-orchestrator`; commit scope `feat(xdl-pr027-weekly-pipeline-orchestrator): ...`; depends on PR023+PR024+PR025+PR026.
Owned paths: pipeline/orchestration command + tests.
Tasks: exact order `listings -> quotes -> dividends -> splits -> Gold validation -> four PostgreSQL syncs -> verification`; stop on failure; structured summary; one non-interactive command.
Acceptance: exact order observable; failure blocks downstream stages; success summary covers every stage; no lock/cron code.

### PR028 — xdl-pr028-loader-lock-restart
Branch `feat/xdl-pr028-loader-lock-restart`; commit scope `feat(xdl-pr028-loader-lock-restart): ...`; depends on PR027.
Owned paths: lock/checkpoint/restart wrapper + tests.
Tasks: deny concurrent runs; restart checkpoints outside semantic identity; safe recovery/release.
Acceptance: second concurrent run denied; failed run recovers; restart produces no duplicate semantic DB mutations.

### PR029 — xdl-pr029-sunday-1100-schedule
Branch `feat/xdl-pr029-sunday-1100-schedule`; commit scope `feat(xdl-pr029-sunday-1100-schedule): ...`; depends on PR027.
Owned paths: cron/scheduler deployment config + tests.
Tasks: literal `CRON_TZ=Europe/Vienna`; literal `0 12 * * 0`; invoke the full guarded bootstrap; DST tests.
Acceptance: expression exact and remains Sunday 12:00 Vienna before/after DST; no pipeline business code changed.

### PR030 — xdl-pr030-destructive-reset-guard
Branch `feat/xdl-pr030-destructive-reset-guard`; commit scope `feat(xdl-pr030-destructive-reset-guard): ...`; depends on PR009+PR022.
Owned paths: destructive reset command + tests.
Tasks: enumerate loader-owned DB objects/medallion paths; dry run; require literal `--confirm-destructive-reset`; delete only owned state.
Acceptance: no confirmation = zero deletion; dry-run scope exact; unrelated schema/path survives.

### PR031 — xdl-pr031-full-xetra-bootstrap
Branch `feat/xdl-pr031-full-xetra-bootstrap`; commit scope `feat(xdl-pr031-full-xetra-bootstrap): ...`; depends on PR027+PR030.
Owned paths: bootstrap command + bootstrap tests.
Tasks: forward destructive confirmation; reset owned state; discover full XETRA non-empty-ISIN universe; fetch full available quotes/dividends/splits; build Gold; publish all four entities; verify counts/keys/date bounds/sync state; emit measured requests/retries/time/failures/rows.
Acceptance: absent confirmation zero mutation; clean fixture bootstrap reaches verified serving state; unchanged subsequent fixture run is semantic no-op; metrics measured, never guessed.

### PR032 — xdl-pr032-loader-e2e-gate
Branch `test/xdl-pr032-loader-e2e-gate`; commit scope `test(xdl-pr032-loader-e2e-gate): ...`; depends on PR028+PR029+PR031.
Owned paths: `tests/e2e/*`, acceptance report generator, fixture outputs only.
Tasks: empty-state fixture bootstrap; all valid listings; all histories; replay zero mutations; quote correction; dividend/split correction+retraction; new listing; timestamp/UTC introspection; read-only app role; lock; scheduler; machine-readable contract report.
Acceptance: all scenarios pass on one SHA; lint/type/unit/integration/policy/merge-gate green; no Portfell import; artifact sufficient for cross-repo contract tests.

### PR033 — xdl-pr033-production-postgres-full-sync-verification
Branch `chore/xdl-pr033-production-postgres-full-sync-verification`; commit scope `chore(xdl-pr033-production-postgres-full-sync-verification): ...`; depends on PR032 merged and green.

Atomic outcome: perform the real complete initial XETRA synchronization to PostgreSQL `10.10.1.3:54321` and independently prove that PostgreSQL exactly represents the validated Gold serving state. This is the mandatory loader completion gate.

Owned paths:

- `src/xetra_data_loader/ops/verify_postgres_sync.py` or equivalent read-only verification command;
- focused verification integration tests;
- `docs/acceptance/production-postgres-full-sync.md`;
- sanitized machine-readable acceptance report, e.g. `artifacts/acceptance/postgres-full-sync.json`;
- no provider, ingestion, Gold-builder, or entity-sync implementation changes.

Tasks:

1. Verify runtime target host/port resolves to exactly `10.10.1.3:54321`; credentials remain secret/env-only.
2. Execute the confirmed full bootstrap/sync using the production loader path: full current XETRA non-empty-ISIN universe plus full available quote, dividend, and split histories.
3. Require a successful committed loader run in `portfell_loader_sync`; partial or failed runs cannot count as completion.
4. After the committed sync, run an independent read-only verification against PostgreSQL rather than trusting only writer counters.
5. For `listings`, `eod_quotes`, `dividends`, and `splits`, compare Gold and PostgreSQL row counts and require exact equality.
6. Compare business keys in both directions (Gold minus PostgreSQL and PostgreSQL minus Gold) and require zero missing/extra keys.
7. Compare deterministic semantic fingerprints/aggregates for all four datasets and require equality; run/fetch metadata is excluded.
8. Assert zero duplicate business keys in PostgreSQL.
9. Assert zero orphan quote/dividend/split rows relative to `(isin,exchange,code)` listings.
10. Compare relevant minimum/maximum business-date/event-date bounds between Gold and PostgreSQL.
11. Introspect every PostgreSQL timestamp column and require exactly `TIMESTAMPTZ(6)`; require DB session timezone `UTC`.
12. Verify `portfell_app` can SELECT all four serving tables and cannot INSERT/UPDATE/DELETE/DDL or access `portfell_loader_sync`.
13. Immediately rerun against unchanged source/Gold state and require exactly zero semantic inserts, updates, retractions, or deletes across all four serving tables.
14. Emit a sanitized acceptance report containing target host/port, run ID, source/Gold/PostgreSQL row counts, key-difference counts, duplicate/orphan counts, date bounds, semantic fingerprints, timestamp/UTC checks, role checks, and no-op replay mutation counters. Never include passwords, tokens, full DSNs, or raw provider payloads.
15. Fail closed: any non-zero mismatch, missing table, unexpected row, duplicate, orphan, fingerprint mismatch, timestamp mismatch, privilege violation, failed run, or non-zero unchanged-replay mutation prevents completion.

Acceptance:

- a real full synchronization to `10.10.1.3:54321` finishes successfully for all four serving datasets;
- the PostgreSQL row count equals validated Gold row count for every serving table;
- symmetric business-key difference is zero for every serving table;
- semantic fingerprints match Gold for every serving table;
- duplicate-key count is zero;
- orphan count is zero;
- business/date bounds match the corresponding validated Gold bounds;
- all timestamp columns are exactly `TIMESTAMPTZ(6)` and the verified session timezone is UTC;
- `portfell_app` passes SELECT-only verification and all prohibited operations fail;
- immediate unchanged replay reports zero semantic mutations for listings, quotes, dividends, and splits;
- sanitized production acceptance report is generated and marked `PASS`;
- branch push gate and PR merge gate are green on the same head SHA;
- PR033 must not be merged and the loader must not be declared complete until the real target-PostgreSQL report is `PASS`.

## 7. Cross-repository handoff to Portfell

Portfell may begin read-contract implementation after XDL-PR007 freezes consumer DDL; permission-level integration waits for XDL-PR008.

Portfell's final cross-repository serving/cutover gate is blocked until **XDL-PR033 is merged and its real target-PostgreSQL full-sync acceptance report is PASS**. XDL-PR032 alone is fixture/production-like evidence and is not sufficient for final Portfell cutover.

Portfell may consume only the PostgreSQL contract, read-only-role contract, and sanitized acceptance artifacts. It must not import `xetra-data-loader`, call EODHD, read medallion files, or mutate loader schemas.

## 8. Mapping from superseded coarse loader plan

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
| PR307 end-to-end/cutover gate | XDL-PR032 + XDL-PR033 |

Any old PR297-PR307 implementation branch is superseded and must not be merged as current authority.

## 9. Completion gate

`xetra-data-loader` is complete only when **XDL-PR001 through XDL-PR033** are merged from clean protected `main` and all conditions below hold:

- Python 3.14.7 `.venv` is reproducible and untracked;
- push/merge gates parallelize lint/type/unit/integration and policy validation enforces Conventional Commits plus exact work-order naming;
- `main` is protected with required `merge-gate` and gated auto-merge;
- the complete current XETRA non-empty-ISIN universe is discoverable;
- full available quote/dividend/split bootstrap succeeds;
- Gold validates all keys/types/references;
- PostgreSQL publication is transactional and idempotent;
- corrections/retractions are deterministic;
- unchanged replay is zero-mutation;
- timestamp contract is exactly `TIMESTAMPTZ(6)` + UTC;
- `portfell_app` is SELECT-only;
- Sunday schedule is exactly 12:00 Europe/Vienna;
- destructive reset is explicit and scoped;
- XDL-PR032 production-like E2E artifact is green;
- **a complete real synchronization has been executed against PostgreSQL `10.10.1.3:54321`;**
- **all four PostgreSQL serving tables have been independently reconciled to validated Gold with exact row counts, zero symmetric key differences, matching semantic fingerprints, zero duplicate keys, zero orphans, and matching date bounds;**
- **the immediate unchanged replay against the real target database produces zero semantic mutations;**
- **XDL-PR033's sanitized production PostgreSQL acceptance report is `PASS`.**

No fixture-only success, partial table sync, successful writer counters without independent reconciliation, or unverified production database state may be treated as project completion.
