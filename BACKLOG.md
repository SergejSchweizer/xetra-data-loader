Last reviewed: 2026-08-22

# XETRA Data Loader Backlog

## Status authority

This file is the active implementation authority for `SergejSchweizer/xetra-data-loader`.

The loader work orders previously planned inside `SergejSchweizer/portfell` are moved here. The work-order IDs `PR297`-`PR307` are preserved for traceability; they are planning IDs and do not imply that GitHub pull-request numbers in this repository will be 297-307.

`xetra-data-loader` owns provider access, XETRA discovery, medallion datasets, PostgreSQL publication, synchronization state, and the weekly Sunday loader run. `portfell` is a consumer only and must not contain provider/download/medallion/write logic after cutover.

## Frozen architecture

```text
EODHD
  |
  v
SergejSchweizer/xetra-data-loader
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
SergejSchweizer/portfell
```

### Loader ownership

`xetra-data-loader` owns all of the following:

- EODHD credentials and HTTP client;
- XETRA exchange-symbol discovery;
- every XETRA listing with a normalized non-empty ISIN, without ETF/UCITS/country/currency prefiltering;
- full listing identity `(isin, exchange, code)`;
- EOD quotes, dividends, and splits;
- Bronze, Silver, and Gold dataset contracts and local loader state;
- correction/backfill planning;
- PostgreSQL DDL, writer role, sync state, loader-run records, and idempotent Gold publication;
- scheduled execution, process locking, retries/rate limits, observability, and destructive bootstrap tooling.

`xetra-data-loader` must not contain portfolio optimization, univariate/bivariate/multivariate analytics, Portfell UI, users/tenants/projects, or Portfell application authorization.

## PostgreSQL contract

Production endpoint: `10.10.1.3:54321`, supplied only through configuration/secrets. Passwords and full DSNs must never be committed.

Schemas:

- consumer schema: `portfell_market`;
- loader operational schema: `portfell_loader_sync`.

Consumer tables:

- `portfell_market.listings`;
- `portfell_market.eod_quotes`;
- `portfell_market.dividends`;
- `portfell_market.splits`.

Keys:

- `listings` primary key: `(isin, exchange, code)`;
- `eod_quotes` primary key: `(isin, exchange, code, trade_date)`;
- `dividends` unique business key: `(isin, exchange, code, event_key)`;
- `splits` unique business key: `(isin, exchange, code, event_key)`.

`event_key` is a deterministic SHA-256 of normalized provider business fields. It must not contain run IDs, fetch timestamps, or database-generated identities.

All PostgreSQL timestamp columns use exactly `TIMESTAMPTZ(6)` and all database sessions use `UTC`, matching the `market-regime-loader` contract. This includes `timestamp_eod`, `fetched_at_utc`, `published_at_utc`, `synced_at_utc`, and loader-run timestamps. Naive Python datetimes are rejected by tests.

EOD data is date-granular. `trade_date DATE` is the business date. `timestamp_eod TIMESTAMPTZ(6)` is the canonical UTC anchor `trade_date 00:00:00+00:00`; it must not be described as the physical XETRA market-close timestamp.

Database roles:

- `portfell_data_loader`: writer for loader-owned schemas;
- `portfell_app`: `SELECT` only on `portfell_market`, with no DDL/mutation rights and no access to `portfell_loader_sync`.

## Bootstrap and weekly refresh

Initial bootstrap:

1. discover all EODHD XETRA listings;
2. retain every listing with a normalized non-empty ISIN;
3. preserve `(isin, exchange, code)` even when one ISIN appears more than once;
4. download full available quote history for the full listing set;
5. download full available dividend history;
6. download full available split history;
7. build and validate Gold datasets;
8. publish Gold to PostgreSQL idempotently;
9. verify counts, keys, date bounds, and sync state.

Existing Portfell market-data files/tables do not need migration. A clean redownload is authoritative.

Weekly cycle:

```text
refresh XETRA listing metadata
  -> determine current non-empty-ISIN XETRA set
  -> refresh quotes
  -> refresh dividends
  -> refresh splits
  -> build/validate Gold
  -> idempotently sync semantic Gold delta to PostgreSQL
  -> verify counts/keys/bounds/sync state
```

After bootstrap, refresh uses a seven-calendar-day correction overlap. Repeating the same source state must produce zero semantic PostgreSQL mutations. Corrections and retractions inside the overlap must be reconciled deliberately and transactionally.

Exact schedule:

```text
CRON_TZ=Europe/Vienna
0 11 * * 0
```

This means Sunday at 11:00 Vienna local time, including daylight-saving transitions.

## Git and weak-agent contract

Every implementation work order uses the exact work-order name in its branch name, every commit message, and the PR title.

Example:

```text
Work-order: pr301-eod-quote-ingestion
Branch:     feat/pr301-eod-quote-ingestion
Commit:     feat(pr301-eod-quote-ingestion): add deterministic eod quote ingestion
PR title:   must contain pr301-eod-quote-ingestion
```

Before editing, every agent records:

```bash
git status --short --branch
```

Rules:

- start from a clean tree and the exact merged dependency SHA;
- parallel sibling work orders start from the same predecessor merge SHA;
- never branch from a sibling work-order branch;
- if a dependency is not merged, remain blocked;
- do not add compatibility shims, legacy fallbacks, or unrelated refactors;
- run focused tests and the repository quality gate on the same head SHA;
- if owned paths overlap unexpectedly, stop and return the conflict to backlog planning.

## Execution graph

```text
PR297 -> PR298 -> PR299
                  |
          PR300 || PR301 || PR302
                  |
                PR303
                  |
                PR304
                  |
                PR305
                  |
                PR306
                  |
                PR307
```

PR300, PR301, and PR302 are the primary safe parallel wave.

## Active work orders

| Key | Work-order name | Branch | Depends on | Atomic outcome | Git status |
| --- | --- | --- | --- | --- | --- |
| PR297 | `pr297-loader-repository-bootstrap` | `chore/pr297-loader-repository-bootstrap` | initial `main` backlog commit | bootstrap strict loader repository skeleton | not started; branch absent |
| PR298 | `pr298-postgres-serving-contract` | `feat/pr298-postgres-serving-contract` | PR297 | freeze PostgreSQL schema, roles, DTOs, UTC/`TIMESTAMPTZ(6)` contract | not started; branch absent; blocked |
| PR299 | `pr299-medallion-dataset-contracts` | `feat/pr299-medallion-dataset-contracts` | PR298 | freeze Bronze/Silver/Gold datasets, keys, paths, manifests | not started; branch absent; blocked |
| PR300 | `pr300-xetra-listing-ingestion` | `feat/pr300-xetra-listing-ingestion` | PR299 | ingest all XETRA listings with non-empty ISIN | not started; branch absent; blocked |
| PR301 | `pr301-eod-quote-ingestion` | `feat/pr301-eod-quote-ingestion` | PR299 | deterministic full/delta EOD quote ingestion | not started; branch absent; blocked |
| PR302 | `pr302-corporate-action-ingestion` | `feat/pr302-corporate-action-ingestion` | PR299 | deterministic full/delta dividend and split ingestion | not started; branch absent; blocked |
| PR303 | `pr303-gold-serving-build` | `feat/pr303-gold-serving-build` | PR300-PR302 | build validated PostgreSQL-serving Gold datasets | not started; branch absent; blocked |
| PR304 | `pr304-postgres-idempotent-sync` | `feat/pr304-postgres-idempotent-sync` | PR303 | transactional semantic-delta Gold -> PostgreSQL sync | not started; branch absent; blocked |
| PR305 | `pr305-sunday-1100-loader-runner` | `feat/pr305-sunday-1100-loader-runner` | PR304 | restart-safe weekly pipeline and Sunday 11:00 Vienna scheduler | not started; branch absent; blocked |
| PR306 | `pr306-destructive-bootstrap-command` | `feat/pr306-destructive-bootstrap-command` | PR305 | guarded destructive reset and clean full XETRA bootstrap | not started; branch absent; blocked |
| PR307 | `pr307-loader-end-to-end-gate` | `test/pr307-loader-end-to-end-gate` | PR306 | production-like end-to-end loader acceptance gate | not started; branch absent; blocked |

## PR297 - pr297-loader-repository-bootstrap

Repository: `SergejSchweizer/xetra-data-loader`

Branch: `chore/pr297-loader-repository-bootstrap`

Required commit scope: `chore(pr297-loader-repository-bootstrap): ...`

Git status: not started; branch absent.

Atomic outcome: create the minimum production-grade Python repository skeleton needed by later loader PRs without implementing provider ingestion or PostgreSQL behavior.

Tasks:

- create `pyproject.toml` with supported Python version and minimal runtime/dev dependencies;
- create strict package boundaries for `api`, `application`, `ingestion`, `ops`, and shared contracts/configuration;
- create `tests/unit` and `tests/integration` roots;
- add deterministic configuration loading with environment variables and no committed secrets;
- add lint, type-check, unit-test, integration-test, and coverage commands;
- add a minimal GitHub Actions quality gate suitable for later branch protection;
- document local setup and the rule that Portfell is a downstream database consumer only.

Acceptance:

- package imports succeed from a clean environment;
- quality commands are documented and executable;
- no EODHD fetch implementation exists yet;
- no PostgreSQL schema is invented before PR298;
- no Portfell application code is copied into this repository.

Owned paths: initial repository scaffold only.

## PR298 - pr298-postgres-serving-contract

Branch: `feat/pr298-postgres-serving-contract`

Required commit scope: `feat(pr298-postgres-serving-contract): ...`

Depends on: PR297 merged.

Atomic outcome: freeze the database serving contract before ingestion code is allowed to depend on it.

Tasks:

- define DDL for both schemas and all four consumer tables;
- define typed DTOs for listings, quotes, dividends, splits, loader sync state, and loader runs;
- enforce `TIMESTAMPTZ(6)` for every timestamp column and UTC database sessions;
- define business keys and deterministic `event_key` contract;
- define `portfell_data_loader` writer and `portfell_app` read-only grants;
- provide database migration/bootstrap SQL owned by this repository;
- add tests that fail on naive datetimes, wrong timestamp SQL types, wrong keys, or write privileges for `portfell_app`.

Acceptance:

- DDL is deterministic and reproducible on an empty PostgreSQL database;
- `portfell_app` can select from `portfell_market` and cannot insert/update/delete/DDL;
- `portfell_app` cannot access `portfell_loader_sync`;
- all timestamp assertions resolve to exactly `TIMESTAMPTZ(6)` with UTC session semantics.

## PR299 - pr299-medallion-dataset-contracts

Branch: `feat/pr299-medallion-dataset-contracts`

Required commit scope: `feat(pr299-medallion-dataset-contracts): ...`

Depends on: PR298 merged.

Atomic outcome: define deterministic Bronze/Silver/Gold identities and manifests without fetching provider data yet.

Tasks:

- define dataset names and path conventions for listings, EOD quotes, dividends, and splits;
- define Bronze raw-provider preservation rules;
- define Silver normalization rules and typed schemas;
- define Gold schemas matching PR298 consumer contracts;
- define manifest fields, source bounds, row counts, fingerprints, and run identity;
- define business-key uniqueness validation;
- define correction/retraction semantics used by PR301/PR302.

Acceptance:

- fixture datasets round-trip through Bronze -> Silver -> Gold contracts deterministically;
- Gold schemas are contract-compatible with PR298;
- changing only fetch/run metadata does not change semantic row identity.

## PR300 - pr300-xetra-listing-ingestion

Branch: `feat/pr300-xetra-listing-ingestion`

Required commit scope: `feat(pr300-xetra-listing-ingestion): ...`

Depends on: PR299 merged.

Atomic outcome: fetch and normalize the complete current XETRA listing universe with non-empty ISINs.

Tasks:

- implement the minimal EODHD exchange-symbol adapter required for XETRA discovery;
- normalize exchange/code/ISIN fields;
- retain every XETRA row with non-empty normalized ISIN;
- do not filter by ETF, UCITS, fund type, country, currency, or current Portfell selection;
- preserve duplicate ISINs under distinct `(isin, exchange, code)` identities;
- write deterministic Bronze/Silver artifacts and fixture-based tests;
- implement retry/rate-limit behavior only at the shared adapter seam required by this PR.

Acceptance:

- fixture input containing equities, ETFs, funds, certificates, and duplicate ISINs retains every non-empty-ISIN XETRA identity;
- empty/null ISIN rows are excluded deterministically;
- repeated same response produces byte/semantic-equivalent normalized output apart from permitted run metadata.

## PR301 - pr301-eod-quote-ingestion

Branch: `feat/pr301-eod-quote-ingestion`

Required commit scope: `feat(pr301-eod-quote-ingestion): ...`

Depends on: PR299 merged.

Atomic outcome: implement full bootstrap and seven-calendar-day correction-overlap EOD quote ingestion for a supplied listing universe.

Tasks:

- implement EODHD EOD quote retrieval by `(exchange, code)`;
- support full-history bootstrap;
- support incremental refresh from `last_business_date - 7 calendar days`;
- normalize to `(isin, exchange, code, trade_date)` business identity;
- derive canonical `timestamp_eod = trade_date 00:00:00+00:00`;
- detect changed historical rows inside the overlap;
- write Bronze/Silver artifacts and deterministic fixtures;
- never infer a physical exchange close timestamp from date-only provider data.

Acceptance:

- same source payload repeated creates no semantic changes;
- a corrected OHLCV row inside the overlap replaces the previous semantic row;
- a new business date appends exactly one business-key row;
- timestamp tests enforce timezone-aware UTC values.

## PR302 - pr302-corporate-action-ingestion

Branch: `feat/pr302-corporate-action-ingestion`

Required commit scope: `feat(pr302-corporate-action-ingestion): ...`

Depends on: PR299 merged.

Atomic outcome: implement deterministic dividend and split ingestion with corrections and retractions.

Tasks:

- implement EODHD dividend retrieval;
- implement EODHD split retrieval;
- normalize business fields and generate deterministic SHA-256 `event_key`;
- support full bootstrap and seven-calendar-day correction overlap;
- detect changed events and source retractions inside the overlap;
- write Bronze/Silver artifacts and fixture-based tests.

Acceptance:

- repeated identical source events preserve the same `event_key`;
- corrections update the semantic event rather than creating run-dependent duplicates;
- retractions are represented explicitly for downstream reconciliation;
- event identity contains no run timestamps or database IDs.

## PR303 - pr303-gold-serving-build

Branch: `feat/pr303-gold-serving-build`

Required commit scope: `feat(pr303-gold-serving-build): ...`

Depends on: PR300, PR301, and PR302 merged.

Atomic outcome: materialize validated Gold datasets that exactly match the PostgreSQL serving contract.

Tasks:

- assemble listing, quote, dividend, and split Gold tables;
- enforce all PR298 keys, types, timestamp rules, and referential relationships;
- apply correction/retraction reconciliation;
- emit counts, key uniqueness, date bounds, source/run fingerprints, and validation report;
- fail closed on contract violations.

Acceptance:

- Gold fixture outputs load into PR298 DDL without transformation ambiguity;
- duplicate primary/business keys fail the build;
- referentially invalid market rows fail the build;
- validation artifacts are deterministic for the same semantic input.

## PR304 - pr304-postgres-idempotent-sync

Branch: `feat/pr304-postgres-idempotent-sync`

Required commit scope: `feat(pr304-postgres-idempotent-sync): ...`

Depends on: PR303 merged.

Atomic outcome: publish only semantic Gold deltas to PostgreSQL and advance sync state in the same transaction.

Tasks:

- implement row fingerprints over normalized semantic fields;
- implement deterministic insert/update/retraction handling;
- use conflict-safe UPSERT behavior on frozen business keys;
- keep data mutation and sync-state mutation in one transaction;
- record loader-run metadata separately from semantic row identity;
- add integration tests against PostgreSQL for initial load, no-op replay, correction, retraction, and transaction rollback.

Acceptance:

- first fixture load inserts expected rows;
- immediate replay of identical Gold produces zero semantic data mutations;
- one corrected row produces exactly one semantic update;
- one retraction removes/deactivates exactly the intended semantic event according to the frozen contract;
- injected failure before commit leaves both serving data and sync state unchanged.

## PR305 - pr305-sunday-1100-loader-runner

Branch: `feat/pr305-sunday-1100-loader-runner`

Required commit scope: `feat(pr305-sunday-1100-loader-runner): ...`

Depends on: PR304 merged.

Atomic outcome: compose the complete restart-safe weekly loader pipeline and exact Sunday schedule.

Tasks:

- compose listing -> quotes -> dividends -> splits -> Gold -> PostgreSQL sync -> verification in exactly that order;
- add a process/distributed lock preventing overlapping scheduled runs;
- propagate failure with non-zero exit and structured stage/run logging;
- ensure safe restart after partial local artifacts or a failed database transaction;
- add scheduler configuration exactly `CRON_TZ=Europe/Vienna` and `0 11 * * 0`;
- test DST-independent local scheduling semantics without replacing the required cron expression.

Acceptance:

- one command executes the full weekly pipeline;
- a second concurrent invocation cannot run the same scheduled job;
- a failed stage prevents downstream publication;
- the committed scheduler expression is exactly the frozen expression.

## PR306 - pr306-destructive-bootstrap-command

Branch: `feat/pr306-destructive-bootstrap-command`

Required commit scope: `feat(pr306-destructive-bootstrap-command): ...`

Depends on: PR305 merged.

Atomic outcome: provide a deliberate, inspectable command that resets loader-owned state and performs a clean full XETRA bootstrap.

Tasks:

- add dry-run mode that prints every loader-owned PostgreSQL schema/table and local path that would be reset;
- require literal `--confirm-destructive-reset` before deletion;
- never delete Portfell optimizer/analysis state or unrelated schemas/paths;
- after confirmed reset, discover the current full XETRA non-empty-ISIN set and run full historical ingestion for quotes/dividends/splits;
- build Gold, publish, and verify counts/keys/bounds;
- record measured provider requests, elapsed time, failures/retries, and resulting row counts; do not hardcode a duration estimate.

Acceptance:

- command without confirmation performs zero destructive actions;
- dry run names the exact destruction scope;
- confirmed fixture/integration bootstrap starts from empty loader-owned state and reaches a verified serving state;
- unrelated database objects survive unchanged.

## PR307 - pr307-loader-end-to-end-gate

Branch: `test/pr307-loader-end-to-end-gate`

Required commit scope: `test(pr307-loader-end-to-end-gate): ...`

Depends on: PR306 merged.

Atomic outcome: prove the loader contract in a production-like acceptance suite before Portfell can complete cross-repository cutover.

Tasks:

- test clean bootstrap from empty loader-owned state;
- verify every fixture XETRA non-empty-ISIN listing is retained;
- verify full quote/dividend/split publication;
- replay identical source state and assert zero semantic database mutations;
- apply a quote correction and assert exactly one semantic update;
- apply a dividend/split correction and retraction and assert exact reconciliation;
- add a new listing and assert it enters the next cycle with associated histories;
- verify all PostgreSQL timestamp columns are `TIMESTAMPTZ(6)` and sessions UTC;
- verify `portfell_app` is read-only;
- emit a concise machine-readable acceptance report for the cross-repository contract gate.

Acceptance:

- all scenarios pass on the same commit SHA;
- quality gate passes;
- no test imports code from the Portfell repository;
- acceptance artifacts are sufficient for Portfell's cross-repository contract smoke test.

## Cross-repository handoff to Portfell

Portfell may consume only the frozen PostgreSQL contract and acceptance fixtures/artifacts. It must not import this repository as a Python package and must not call EODHD directly.

Portfell work orders remain in `SergejSchweizer/portfell/BACKLOG.md`. The Portfell cross-repository gate is blocked until PR307 in this repository is merged and green.

## Loader completion gate

The loader side is complete when all of the following are true from clean `main`:

- all current XETRA listings with non-empty ISIN can be discovered from scratch;
- full available EOD quote, dividend, and split history can be bootstrapped for that universe;
- Gold passes frozen keys/types/referential validation;
- PostgreSQL publication is transactional and idempotent;
- replaying unchanged source data yields zero semantic DB mutations;
- corrections/retractions reconcile deterministically;
- every PostgreSQL timestamp column is `TIMESTAMPTZ(6)` and the DB session timezone is UTC;
- `portfell_data_loader` can write only what it owns and `portfell_app` is read-only on `portfell_market`;
- weekly schedule is exactly Sunday 11:00 Europe/Vienna;
- destructive bootstrap requires explicit confirmation and cannot delete unrelated state;
- no portfolio analytics, user/project runtime, or Portfell UI/backend code exists in this repository.
