from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from .stores import ALL_ADAPTERS


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
        adapter = adapter_class()
        try:
            rows = adapter.search(card_name)
            elapsed = int((perf_counter() - started) * 1000)
            return rows, StoreRun(adapter.name, len(rows), elapsed)
        except Exception as exc:
            elapsed = int((perf_counter() - started) * 1000)
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

        with ThreadPoolExecutor(max_workers=min(7, len(selected) or 1)) as pool:
            futures = [pool.submit(run, key) for key in selected]
            for future in as_completed(futures):
                _, rows, status = future.result()
                results.extend(rows)
                runs.append(status)

        results.sort(key=lambda x: (
            0 if x.available else 1,
            x.currency or "ZZZ",
            x.price if x.price is not None else 10**12,
            x.store,
        ))
        return results, sorted(runs, key=lambda r: r.store)
