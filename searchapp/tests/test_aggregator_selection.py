from unittest import TestCase
from unittest.mock import patch

from searchapp.services.aggregator import SearchAggregator


class AggregatorSelectionRegressionTests(TestCase):
    def test_none_means_all_stores_but_empty_list_means_none(self):
        aggregator = SearchAggregator()
        rows, runs = aggregator.search("Lightning Bolt", [])
        self.assertEqual(rows, [])
        self.assertEqual(runs, [])

    def test_one_store_does_not_fan_out(self):
        aggregator = SearchAggregator()
        with patch.object(aggregator, "search_store", return_value=([], None)) as mocked:
            # Avoid dereferencing the mocked run by exercising the worker selector only
            # through an empty result object with a real-looking run.
            from searchapp.services.aggregator import StoreRun
            mocked.return_value = ([], StoreRun("Pirulo", 0, 0))
            aggregator.search("Lightning Bolt", ["pirulo"])
            mocked.assert_called_once_with("Lightning Bolt", "pirulo")
