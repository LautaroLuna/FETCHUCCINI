from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging
from time import perf_counter

from django.conf import settings

from .listing_normalization import dedupe_listings
from .metrics import record_store_result
from .resilience import (
    StoreConcurrencyBusy,
    circuit_is_open,
    circuit_record_failure,
    circuit_record_success,
    store_request_slot,
)
from .store_registry import STORE_REGISTRY
from .utils import search_query_variants

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StoreRun:
    store: str
    count: int
    elapsed_ms: int
    error: str | None = None
    partial: bool = False
    warning: str | None = None


class SearchAggregator:
    def __init__(self):
        self.store_registry = STORE_REGISTRY
        # Kept as a compatibility attribute for existing view/tests while the
        # registry becomes the canonical source of truth.
        self.adapter_classes = {
            key: definition.adapter_class for key, definition in self.store_registry.items()
        }

    def search_store(self, card_name: str, store_key: str):
        """Run one store in isolation under its operational policy."""
        definition = self.store_registry.get(store_key)
        if definition is None:
            raise KeyError(store_key)

        adapter_class = definition.adapter_class
        started = perf_counter()
        is_open, retry_after = circuit_is_open(store_key)
        if is_open:
            error = f"CircuitOpen: tienda pausada temporalmente; reintento en {retry_after}s"
            record_store_result(store_key, elapsed_ms=0, success=False, source="live", count=0)
            return [], StoreRun(definition.name, 0, 0, error)

        adapter = adapter_class()
        adapter.configure_policy(definition.policy)
        try:
            # A process-wide outbound gate protects Railway threads when several
            # users search at the same time. The per-store policy additionally
            # caps logical HTTP calls and total wall-clock time for this search.
            with store_request_slot():
                query_variants = search_query_variants(card_name) or [card_name]
                rows = []

                # Try tolerant MTG-name variants only when the prior variant did
                # not yield a purchasable listing. The same request/time budget
                # is shared across variants, preventing pathological fan-out.
                for variant in query_variants:
                    candidate_rows = adapter.search(variant)
                    candidate_rows = [
                        row for row in candidate_rows
                        if row.available and (row.stock is None or row.stock > 0)
                    ]
                    if candidate_rows:
                        rows = candidate_rows
                        break

            rows = dedupe_listings(rows)
            elapsed = int((perf_counter() - started) * 1000)
            circuit_record_success(store_key)
            record_store_result(store_key, elapsed_ms=elapsed, success=True, source="live", count=len(rows))
            if elapsed >= 3000:
                logger.info(
                    "slow store search store=%s elapsed_ms=%s count=%s requests=%s partial=%s",
                    store_key,
                    elapsed,
                    len(rows),
                    adapter.http.requests_made,
                    adapter.partial,
                )
            return rows, StoreRun(
                adapter.name,
                len(rows),
                elapsed,
                partial=bool(adapter.partial),
                warning=adapter.partial_error,
            )
        except StoreConcurrencyBusy as exc:
            elapsed = int((perf_counter() - started) * 1000)
            # Internal load shedding is not an origin failure: do not poison the
            # store circuit breaker just because Railway is temporarily busy.
            record_store_result(store_key, elapsed_ms=elapsed, success=False, source="live", count=0)
            logger.warning("store concurrency busy store=%s elapsed_ms=%s", store_key, elapsed)
            return [], StoreRun(adapter.name, 0, elapsed, f"StoreConcurrencyBusy: {exc}")
        except Exception as exc:
            elapsed = int((perf_counter() - started) * 1000)
            circuit_record_failure(store_key, f"{type(exc).__name__}: {exc}")
            record_store_result(store_key, elapsed_ms=elapsed, success=False, source="live", count=0)
            return [], StoreRun(
                adapter.name,
                0,
                elapsed,
                f"{type(exc).__name__}: {exc}",
            )

    def search(self, card_name: str, store_keys: list[str] | None = None):
        # Important distinction: None means "all stores"; [] means "no stores".
        # v0.36 treated both the same, which could accidentally fan a Mercadia-
        # only compatibility request out to every live adapter.
        selected = list(self.adapter_classes) if store_keys is None else list(store_keys)
        selected = [key for key in selected if key in self.adapter_classes]
        results = []
        runs = []

        if not selected:
            return [], []

        def run(key):
            rows, status = self.search_store(card_name, key)
            return key, rows, status

        max_workers = max(1, int(getattr(settings, "FETCHUCCINI_STORE_CONCURRENCY", 4)))
        with ThreadPoolExecutor(max_workers=min(max_workers, len(selected))) as pool:
            futures = [pool.submit(run, key) for key in selected]
            for future in as_completed(futures):
                _, rows, status = future.result()
                results.extend(rows)
                runs.append(status)

        results = dedupe_listings(results)
        results.sort(key=lambda x: (
            0 if x.available else 1,
            x.currency or "ZZZ",
            x.price if x.price is not None else 10**12,
            x.store,
        ))
        return results, sorted(runs, key=lambda r: r.store)
