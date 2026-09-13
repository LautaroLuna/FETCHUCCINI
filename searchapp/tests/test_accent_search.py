from decimal import Decimal
from unittest import TestCase

from searchapp.services.aggregator import SearchAggregator
from searchapp.services.models import Listing


class AccentSearchFallbackTests(TestCase):
    def test_retries_store_without_diacritics_when_canonical_query_is_empty(self):
        class AccentSensitiveAdapter:
            key = "accent-test"
            name = "Accent Test"
            calls = []

            def search(self, card_name):
                self.__class__.calls.append(card_name)
                if card_name == "Gloin the Mighty":
                    return [Listing(
                        store=self.name,
                        card_name="Gloin the Mighty // Easy Pickings",
                        price=Decimal("1250"),
                        currency="ARS",
                        stock=3,
                        available=True,
                        url="https://example.test/gloin",
                    )]
                return []

        aggregator = SearchAggregator()
        aggregator.adapter_classes = {AccentSensitiveAdapter.key: AccentSensitiveAdapter}

        rows, run = aggregator.search_store("Glóin the Mighty", AccentSensitiveAdapter.key)

        self.assertEqual(AccentSensitiveAdapter.calls, ["Glóin the Mighty", "Gloin the Mighty"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].card_name, "Gloin the Mighty // Easy Pickings")
        self.assertIsNone(run.error)
