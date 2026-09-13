from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[2]


class FrontendResponsiveContractTests(TestCase):
    def test_mobile_filter_toggle_exists(self):
        template = (ROOT / "searchapp/templates/searchapp/index.html").read_text(encoding="utf-8")
        self.assertIn('id="mobile-filters-toggle"', template)
        self.assertIn('viewport-fit=cover', template)

    def test_mobile_card_overrides_prevent_overflow(self):
        css = (ROOT / "searchapp/static/searchapp/style.css").read_text(encoding="utf-8")
        self.assertIn('@media(max-width:700px)', css)
        self.assertIn('.result-card .thumb{width:92px', css)
        self.assertIn('grid-template-columns:1fr 1fr', css)
        self.assertIn('.filters.mobile-filters-collapsed .filters-grid{display:none}', css)

    def test_frontend_limits_parallel_store_requests_and_cancels_old_searches(self):
        js = (ROOT / "searchapp/static/searchapp/app.js").read_text(encoding="utf-8")
        self.assertIn('const MAX_PARALLEL_STORES = 4;', js)
        self.assertIn('abortActiveSearchRequests()', js)
        self.assertIn('runWithConcurrency(toRefresh, MAX_PARALLEL_STORES', js)

    def test_favicon_assets_are_optimized_for_mobile(self):
        static_dir = ROOT / "searchapp/static/searchapp"
        self.assertLess((static_dir / "fetchuccini-forge-icon.png").stat().st_size, 600_000)
        self.assertTrue((static_dir / "fetchuccini-forge-icon-32.png").exists())
        self.assertTrue((static_dir / "fetchuccini-forge-icon-180.png").exists())
