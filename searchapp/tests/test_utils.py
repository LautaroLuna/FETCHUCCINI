from unittest import TestCase
from searchapp.services.utils import exactish_card_name, parse_ars, search_query_variants

class UtilsTests(TestCase):
    def test_exactish_card_name(self):
        self.assertTrue(exactish_card_name("Lightning Bolt", "Lightning Bolt"))
        self.assertTrue(exactish_card_name("Lightning Bolt (Borderless)", "Lightning Bolt"))
        self.assertTrue(exactish_card_name("Lightning Bolt - Showcase", "Lightning Bolt"))
        self.assertFalse(exactish_card_name("Forked Bolt", "Lightning Bolt"))
        self.assertFalse(exactish_card_name("Emeritus of Conflict // Lightning Bolt", "Lightning Bolt"))
        self.assertTrue(exactish_card_name("Gloin the Mighty // Easy Pickings - Foil", "Glóin the Mighty"))
        self.assertTrue(exactish_card_name("Glóin the Mighty", "Gloin the Mighty"))

    def test_accent_folded_search_query_variant(self):
        self.assertEqual(search_query_variants("Glóin the Mighty"), ["Glóin the Mighty", "Gloin the Mighty"])
        self.assertEqual(search_query_variants("Lightning Bolt"), ["Lightning Bolt"])

    def test_parse_ars(self):
        self.assertEqual(str(parse_ars("ARS$ 4.250,00")), "4250.00")
