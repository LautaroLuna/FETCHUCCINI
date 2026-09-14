from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import logging
from time import perf_counter

from django.conf import settings
from .stores import ALL_ADAPTERS
from .resilience import (
    StoreConcurrencyBusy,
    circuit_is_open,
    circuit_record_failure,
    circuit_record_success,
    store_request_slot,
)
from .utils import search_query_variants
from .listing_normalization import dedupe_listings
from .metrics import record_store_result

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StoreRun:
    store: str
    count: int
    elapsed_ms: int
    error: str | None = None


class SearchAggregator:
    def __init__(self):
        self.adapter_classes = {cls.key: cls for cls in ALL_ADAPTERS}

    def search_store(self, card_name: str, store_key: str):
        """Run one store in isolation.

        The progressive frontend calls this endpoint once per store so fast
        stores can render immediately instead of waiting for the slowest one.
        """
        adapter_class = self.adapter_classes.get(store_key)
        if adapter_class is None:
            raise KeyError(store_key)

        started = perf_counter()
        is_open, retry_after = circuit_is_open(store_key)
        if is_open:
            error = f"CircuitOpen: tienda pausada temporalmente; reintento en {retry_after}s"
            record_store_result(store_key, elapsed_ms=0, success=False, source="live", count=0)
            return [], StoreRun(adapter_class.name, 0, 0, error)

        adapter = adapter_class()
        try:
            # A process-wide outbound gate protects Railway threads when several
            # users search at the same time. Frontend concurrency remains
            # progressive; this gate only caps aggregate origin traffic.
            with store_request_slot():
                query_variants = search_query_variants(card_name) or [card_name]
                rows = []

                # Try increasingly tolerant MTG-name variants only when the prior
                # variant did not yield a purchasable listing. This keeps ordinary
                # searches at one request while covering accents, curly apostrophes,
                # Unicode dashes and split-card naming differences.
                for variant in query_variants:
                    candidate_rows = adapter.search(variant)
                    candidate_rows = [
                        row for row in candidate_rows
                        if row.available and (row.stock is None or row.stock > 0)
                    ]
                    if candidate_rows:
                        rows = candidate_rows
                        break

            # Normalize store vocabularies and collapse duplicate variants that
            # can appear across storefront pagination/search endpoints.
            rows = dedupe_listings(rows)

            elapsed = int((perf_counter() - started) * 1000)
            circuit_record_success(store_key)
            record_store_result(store_key, elapsed_ms=elapsed, success=True, source="live", count=len(rows))
            if elapsed >= 3000:
                logger.info("slow store search store=%s elapsed_ms=%s count=%s", store_key, elapsed, len(rows))
            return rows, StoreRun(adapter.name, len(rows), elapsed)
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
        selected = store_keys or list(self.adapter_classes)
        selected = [key for key in selected if key in self.adapter_classes]
        results = []
        runs = []

        def run(key):
            rows, status = self.search_store(card_name, key)
            return key, rows, status

        max_workers = max(1, int(getattr(settings, "FETCHUCCINI_STORE_CONCURRENCY", 4)))
        with ThreadPoolExecutor(max_workers=min(max_workers, len(selected) or 1)) as pool:
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
