"""Production stage factory used by the non-interactive Sunday runner."""

from __future__ import annotations

from dataclasses import dataclass, field

from xetra_loader.contracts.corporate_actions import DividendEvent, SplitEvent
from xetra_loader.contracts.quotes import QuoteRecord
from xetra_loader.gold.dividends import DividendGoldResult, build_dividend_gold
from xetra_loader.gold.listings import ListingGoldResult, build_listing_gold
from xetra_loader.gold.quotes import QuoteGoldResult, build_quote_gold
from xetra_loader.gold.splits import SplitGoldResult, build_split_gold
from xetra_loader.gold.validation import validate_complete_gold
from xetra_loader.ops.bootstrap import PostgresEodhdBootstrapRuntime
from xetra_loader.pipeline.orchestrator import PipelineStages
from xetra_loader.sync.core import JSONValue, SyncOutcome


@dataclass(slots=True)
class _WeeklyState:
    runtime: PostgresEodhdBootstrapRuntime
    listings: ListingGoldResult | None = None
    quotes: QuoteGoldResult | None = None
    dividends: DividendGoldResult | None = None
    splits: SplitGoldResult | None = None
    outcomes: dict[str, SyncOutcome] = field(default_factory=dict)

    def ingest_listings(self) -> dict[str, JSONValue]:
        batch = self.runtime.fetch_listings()
        self.listings = build_listing_gold(batch.rows)
        self.runtime.persist_gold(
            "listings",
            self.listings.semantic_rows(),
            row_count=self.listings.row_count,
            semantic_fingerprint=self.listings.semantic_fingerprint,
        )
        return {"rows": self.listings.row_count, "requests": batch.metrics.logical_requests}

    def ingest_quotes(self) -> dict[str, JSONValue]:
        listings = self._require_listings()
        records: list[QuoteRecord] = []
        requests = 0
        for listing in listings.rows:
            batch = self.runtime.fetch_quotes(listing)
            records.extend(batch.rows)
            requests += batch.metrics.logical_requests
        self.quotes = build_quote_gold(records)
        self.runtime.persist_gold(
            "eod_quotes",
            self.quotes.semantic_rows(),
            row_count=self.quotes.row_count,
            semantic_fingerprint=self.quotes.semantic_fingerprint,
        )
        return {"rows": self.quotes.row_count, "requests": requests}

    def ingest_dividends(self) -> dict[str, JSONValue]:
        listings = self._require_listings()
        records: list[DividendEvent] = []
        requests = 0
        for listing in listings.rows:
            batch = self.runtime.fetch_dividends(listing)
            records.extend(batch.rows)
            requests += batch.metrics.logical_requests
        self.dividends = build_dividend_gold(records)
        self.runtime.persist_gold(
            "dividends",
            self.dividends.semantic_rows(),
            row_count=self.dividends.row_count,
            semantic_fingerprint=self.dividends.semantic_fingerprint,
            retracted_keys=self.dividends.retracted_keys,
        )
        return {"rows": self.dividends.row_count, "requests": requests}

    def ingest_splits(self) -> dict[str, JSONValue]:
        listings = self._require_listings()
        records: list[SplitEvent] = []
        requests = 0
        for listing in listings.rows:
            batch = self.runtime.fetch_splits(listing)
            records.extend(batch.rows)
            requests += batch.metrics.logical_requests
        self.splits = build_split_gold(records)
        self.runtime.persist_gold(
            "splits",
            self.splits.semantic_rows(),
            row_count=self.splits.row_count,
            semantic_fingerprint=self.splits.semantic_fingerprint,
            retracted_keys=self.splits.retracted_keys,
        )
        return {"rows": self.splits.row_count, "requests": requests}

    def validate_gold(self) -> dict[str, JSONValue]:
        listings, quotes, dividends, splits = self._require_gold()
        return validate_complete_gold(listings, quotes, dividends, splits).as_dict()

    def sync_listings(self) -> dict[str, JSONValue]:
        outcome = self.runtime.publish_listings(self._require_listings())
        self.outcomes["listings"] = outcome
        return _sync_details(outcome)

    def sync_quotes(self) -> dict[str, JSONValue]:
        outcome = self.runtime.publish_quotes(self._require_quotes())
        self.outcomes["eod_quotes"] = outcome
        return _sync_details(outcome)

    def sync_dividends(self) -> dict[str, JSONValue]:
        outcome = self.runtime.publish_dividends(self._require_dividends())
        self.outcomes["dividends"] = outcome
        return _sync_details(outcome)

    def sync_splits(self) -> dict[str, JSONValue]:
        outcome = self.runtime.publish_splits(self._require_splits())
        self.outcomes["splits"] = outcome
        return _sync_details(outcome)

    def verify(self) -> dict[str, JSONValue]:
        listings, quotes, dividends, splits = self._require_gold()
        try:
            verification = self.runtime.verify(
                listings,
                quotes,
                dividends,
                splits,
                self.outcomes,
            )
            if not verification.passed:
                raise RuntimeError("weekly PostgreSQL verification failed")
            return verification.as_dict()
        finally:
            self.runtime.close()

    def _require_listings(self) -> ListingGoldResult:
        if self.listings is None:
            raise RuntimeError("listing Gold must exist before this stage")
        return self.listings

    def _require_quotes(self) -> QuoteGoldResult:
        if self.quotes is None:
            raise RuntimeError("quote Gold must exist before this stage")
        return self.quotes

    def _require_dividends(self) -> DividendGoldResult:
        if self.dividends is None:
            raise RuntimeError("dividend Gold must exist before this stage")
        return self.dividends

    def _require_splits(self) -> SplitGoldResult:
        if self.splits is None:
            raise RuntimeError("split Gold must exist before this stage")
        return self.splits

    def _require_gold(
        self,
    ) -> tuple[ListingGoldResult, QuoteGoldResult, DividendGoldResult, SplitGoldResult]:
        return (
            self._require_listings(),
            self._require_quotes(),
            self._require_dividends(),
            self._require_splits(),
        )


def build_weekly_stages() -> PipelineStages:
    """Build the concrete factory referenced by the deployed Vienna cron entry."""

    state = _WeeklyState(PostgresEodhdBootstrapRuntime.from_environment())
    return PipelineStages(
        listings=state.ingest_listings,
        quotes=state.ingest_quotes,
        dividends=state.ingest_dividends,
        splits=state.ingest_splits,
        gold_validation=state.validate_gold,
        postgres_listings_sync=state.sync_listings,
        postgres_quotes_sync=state.sync_quotes,
        postgres_dividends_sync=state.sync_dividends,
        postgres_splits_sync=state.sync_splits,
        verification=state.verify,
    )


def _sync_details(outcome: SyncOutcome) -> dict[str, JSONValue]:
    return {
        "status": outcome.status,
        "inserted": outcome.counters.inserted,
        "updated": outcome.counters.updated,
        "deleted": outcome.counters.deleted,
        "retracted": outcome.counters.retracted,
    }
