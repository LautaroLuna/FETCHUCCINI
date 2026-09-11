"""Quick CLI smoke test once dependencies are installed.
Usage: python scripts/test_search.py "Lightning Bolt" la_workshop starcitygames
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from searchapp.services.aggregator import SearchAggregator

query = sys.argv[1] if len(sys.argv) > 1 else "Lightning Bolt"
stores = sys.argv[2:] or ["la_workshop", "starcitygames"]
results, runs = SearchAggregator().search(query, stores)
for run in runs:
    print(run)
for row in results[:30]:
    print(row.to_dict())
