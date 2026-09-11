from unittest import TestCase
from searchapp.services.utils import exactish_card_name, parse_ars

class UtilsTests(TestCase):
    def test_exactish_card_name(self):
        self.assertTrue(exactish_card_name("Lightning Bolt", "Lightning Bolt"))
        self.assertTrue(exactish_card_name("Lightning Bolt (Borderless)", "Lightning Bolt"))
        self.assertTrue(exactish_card_name("Lightning Bolt - Showcase", "Lightning Bolt"))
        self.assertFalse(exactish_card_name("Forked Bolt", "Lightning Bolt"))
        self.assertFalse(exactish_card_name("Emeritus of Conflict // Lightning Bolt", "Lightning Bolt"))

    def test_parse_ars(self):
        self.assertEqual(str(parse_ars("ARS$ 4.250,00")), "4250.00")
