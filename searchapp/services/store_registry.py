from __future__ import annotations

from dataclasses import dataclass

from .stores import ALL_ADAPTERS


@dataclass(frozen=True, slots=True)
class StorePolicy:
    """Operational limits for one upstream store.

    ``max_requests`` counts logical HTTP calls made by Fetchuccini. urllib3 may
    still perform a bounded transport retry inside one logical request. The
    deadline protects broad/slow searches from monopolising Railway workers.
    """

    fresh_cache_seconds: int = 5 * 60
    stale_cache_seconds: int = 24 * 60 * 60
    deadline_seconds: float = 20.0
    max_requests: int = 12
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 9.0


@dataclass(frozen=True, slots=True)
class StoreDefinition:
    key: str
    name: str
    adapter_class: type
    currency: str | None = None
    policy: StorePolicy = StorePolicy()


# One source of truth for store identity and operational policy. Adapter classes
# remain responsible for parsing upstream data; this registry is responsible for
# how Fetchuccini treats each store as a service.
_POLICY_OVERRIDES: dict[str, dict] = {
    "pirulo": {
        "currency": "USD",
        "policy": StorePolicy(deadline_seconds=20, max_requests=8),
    },
    "mercadia": {
        "currency": "USD",
        "policy": StorePolicy(deadline_seconds=18, max_requests=10),
    },
    "magic_lair": {
        "currency": "ARS",
        "policy": StorePolicy(deadline_seconds=18, max_requests=9),
    },
    "batikueva": {
        "currency": "ARS",
        "policy": StorePolicy(deadline_seconds=20, max_requests=15),
    },
    "magicdealers": {
        "currency": "ARS",
        "policy": StorePolicy(
            fresh_cache_seconds=30 * 60,
            deadline_seconds=22,
            max_requests=10,
            connect_timeout_seconds=4,
            read_timeout_seconds=9,
        ),
    },
    "la_workshop": {
        "currency": "USD",
        "policy": StorePolicy(deadline_seconds=20, max_requests=15),
    },
    "starcitygames": {
        "currency": "USD",
        "policy": StorePolicy(deadline_seconds=20, max_requests=10),
    },
}


def _build_registry() -> dict[str, StoreDefinition]:
    registry: dict[str, StoreDefinition] = {}
    for adapter_class in ALL_ADAPTERS:
        override = _POLICY_OVERRIDES.get(adapter_class.key, {})
        registry[adapter_class.key] = StoreDefinition(
            key=adapter_class.key,
            name=adapter_class.name,
            adapter_class=adapter_class,
            currency=override.get("currency"),
            policy=override.get("policy", StorePolicy()),
        )
    return registry


STORE_REGISTRY = _build_registry()


def store_definition(store_key: str) -> StoreDefinition | None:
    return STORE_REGISTRY.get(store_key)


def enabled_store_definitions(disabled_keys=()):
    disabled = set(disabled_keys)
    return [definition for key, definition in STORE_REGISTRY.items() if key not in disabled]
