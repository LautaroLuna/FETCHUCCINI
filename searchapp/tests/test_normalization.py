from decimal import Decimal
from unittest import TestCase

from searchapp.services.listing_normalization import (
    dedupe_listing_dicts,
    dedupe_listings,
    normalize_condition,
    normalize_finish,
    normalize_language,
    normalize_listing,
)
from searchapp.services.models import Listing
from searchapp.services.utils import (
    exactish_card_name,
    normalize_card_search_text,
    safe_http_url,
    search_query_variants,
)


class CardNameNormalizationTests(TestCase):
    def test_accents_apostrophes_and_split_separators_share_keys(self):
        self.assertEqual(normalize_card_search_text("Glóin the Mighty"), normalize_card_search_text("Gloin the Mighty"))
        self.assertEqual(normalize_card_search_text("Urza’s Saga"), normalize_card_search_text("Urza's Saga"))
        self.assertEqual(normalize_card_search_text("Fire // Ice"), normalize_card_search_text("Fire / Ice"))

    def test_split_card_variants_include_single_slash_and_front_face(self):
        variants = search_query_variants("Fire // Ice")
        self.assertEqual(variants[0], "Fire // Ice")
        self.assertIn("Fire / Ice", variants)
        self.assertIn("Fire", variants)
        self.assertTrue(exactish_card_name("Fire / Ice", "Fire // Ice"))

    def test_curly_apostrophe_gets_ascii_fallback(self):
        self.assertEqual(search_query_variants("Urza’s Saga"), ["Urza’s Saga", "Urza's Saga"])


class ListingNormalizationTests(TestCase):
    def test_store_vocabularies_are_normalized_for_filters(self):
        self.assertEqual(normalize_language("English"), "Inglés")
        self.assertEqual(normalize_language("EN"), "Inglés")
        self.assertEqual(normalize_language("Spanish"), "Español")
        self.assertEqual(normalize_condition("NM"), "Near Mint")
        self.assertEqual(normalize_condition("EX-NM"), "Excelente")
        self.assertEqual(normalize_finish("Normal"), "Non-foil")
        self.assertEqual(normalize_finish("Foil Etched"), "Foil Etched")

    def test_listing_normalization_blocks_non_http_urls(self):
        row = normalize_listing(Listing(
            store="Test",
            card_name="Lightning Bolt",
            language="English",
            condition="NM",
            finish="Normal",
            price=Decimal("1.25"),
            currency="usd",
            stock=1,
            available=True,
            url="javascript:alert(1)",
            image_url="data:text/html,bad",
        ))
        self.assertEqual(row.language, "Inglés")
        self.assertEqual(row.condition, "Near Mint")
        self.assertEqual(row.finish, "Non-foil")
        self.assertEqual(row.currency, "USD")
        self.assertIsNone(row.url)
        self.assertIsNone(row.image_url)
        self.assertEqual(safe_http_url("https://example.test/card"), "https://example.test/card")

    def test_duplicate_store_variant_is_collapsed_and_keeps_richer_row(self):
        rows = [
            Listing(store="Store", card_name="Bolt", variant_id="42", price=Decimal("2"), currency="USD", stock=1, available=True),
            Listing(store="Store", card_name="Bolt", variant_id="42", price=Decimal("2"), currency="USD", stock=3, available=True, condition="NM", url="https://example.test/bolt"),
        ]
        deduped = dedupe_listings(rows)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].stock, 3)
        self.assertEqual(deduped[0].condition, "Near Mint")
        self.assertEqual(deduped[0].url, "https://example.test/bolt")


    def test_price_change_does_not_create_duplicate_listing_identity(self):
        rows = [
            {"store":"Store","card_name":"Bolt","product_id":"P1","condition":"NM","available":True,"stock":1,"price":"10","currency":"USD"},
            {"store":"Store","card_name":"Bolt","product_id":"P1","condition":"NM","available":True,"stock":1,"price":"9","currency":"USD"},
        ]
        deduped = dedupe_listing_dicts(rows)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["price"], "9")

    def test_duplicate_dict_rows_are_collapsed(self):
        rows = [
            {"store":"Mercadia","card_name":"Bolt","sku":"A-1","available":True,"stock":1,"price":"10","currency":"ars"},
            {"store":"Mercadia","card_name":"Bolt","sku":"A-1","available":True,"stock":2,"price":"10","currency":"ARS","language":"English"},
        ]
        deduped = dedupe_listing_dicts(rows)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["stock"], 2)
        self.assertEqual(deduped[0]["language"], "Inglés")
