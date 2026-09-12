from unittest import TestCase
from bs4 import BeautifulSoup

from searchapp.services.stores.batikueva import BatikuevaAdapter
from searchapp.services.stores.la_workshop import LaWorkshopAdapter
from searchapp.services.stores.magic_lair import MagicLairAdapter
from searchapp.services.stores.magicdealers import MagicDealersAdapter
from searchapp.services.stores.mercadia import MercadiaAdapter
from searchapp.services.stores.pirulo import PiruloAdapter
from searchapp.services.stores.starcitygames import StarCityGamesAdapter


class FakeResponse:
    def __init__(self, data=None, text=""):
        self._data = data or {}
        self.text = text

    def json(self):
        return self._data


class QueueHttp:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, *args, **kwargs):
        return self.responses.pop(0)

    def post(self, *args, **kwargs):
        return self.responses.pop(0)


class StoreAdapterContractTests(TestCase):
    def test_pirulo_title_parser(self):
        meta = PiruloAdapter()._title_meta("Lightning Bolt (A25) (Foil) (#141)", "Lightning Bolt")
        self.assertEqual(meta["card_name"], "Lightning Bolt")
        self.assertEqual(meta["set_code"], "A25")
        self.assertEqual(meta["collector_number"], "141")
        self.assertEqual(meta["finish"], "Foil")

    def test_mercadia_autocomplete_parser(self):
        item = {
            "name": "Lightning Bolt",
            "url": "/lightning-bolt.html",
            "sku": "LB-1",
            "description": "M10 Lightning Bolt EN NM Normal",
            "price": "$ 2500,00",
            "add_to_cart": "1",
        }
        listing = MercadiaAdapter()._listing_from_autocomplete_item(item, "Lightning Bolt", True)
        self.assertIsNotNone(listing)
        self.assertEqual(listing.set_code, "M10")
        self.assertEqual(listing.language, "English")
        self.assertTrue(listing.available)

    def test_magic_lair_search_card_parser(self):
        html = """<div class="productCard__card" data-productid="10">
          <div class="productCard__title"><a href="/products/lightning-bolt">Lightning Bolt</a></div>
          <div class="productCard__setName">Magic 2010</div>
          <img src="/bolt.jpg">
          <span class="productChip" data-variantid="99" data-varianttitle="Near Mint Foil" data-variantqty="2" data-variantavailable="true" data-variantprice="250000"></span>
        </div>"""
        rows = MagicLairAdapter()._parse_page(html, "Lightning Bolt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0].price), "2500")
        self.assertEqual(rows[0].finish, "Foil")

    def test_batikueva_product_meta_parser(self):
        soup = BeautifulSoup("""<article><a href="/productos/lightning-bolt/" title="Lightning Bolt">Lightning Bolt</a><img src="//img.test/bolt.jpg"><span data-product-id="77"></span></article>""", "html.parser")
        title, href, image, product_id = BatikuevaAdapter()._product_meta(soup.article)
        self.assertEqual(title, "Lightning Bolt")
        self.assertEqual(product_id, "77")
        self.assertTrue(image.startswith("https:"))
        self.assertIn("/productos/", href)

    def test_magicdealers_search_parser(self):
        html = """<ul><li class="product"><a href="/catalog/lightning_bolt/123"><img src="/bolt.jpg">Lightning Bolt</a><span class="category">Magic 2010</span><span>2 In Stock ARS$ 3.500,00 Near Mint, English</span></li></ul>"""
        rows, next_url = MagicDealersAdapter()._parse_page(html, "Lightning Bolt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["stock"], 2)
        self.assertIsNone(next_url)

    def test_la_workshop_api_contract(self):
        data = {"products":[{"name":"Lightning Bolt","edition":"M10","edition_code":"M10","collector_number":"146","id":1,"listings":[{"id":9,"stock":2,"current_price":"1.25","language":"English","condition":"Near Mint","finish":"Non-foil"}]}],"pages":1}
        rows = LaWorkshopAdapter(http=QueueHttp([FakeResponse(data=data)])).search("Lightning Bolt")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stock, 2)
        self.assertEqual(rows[0].currency, "USD")

    def test_starcitygames_api_contract(self):
        data = {"Results":[{"Document":{"card_name":["Lightning Bolt"],"set":["Magic 2010"],"collector_number":["146"],"image":["https://img.test/bolt.jpg"],"url_detail":["/bolt"],"hawk_child_attributes":[{"calculated_price":["1.50"],"qty":["3"],"variant_instockonly":["yes"],"purchasing_disabled":[False],"condition":["Near Mint"],"variant_language":["English"],"url":["/bolt?variant=1"]}]}}],"Pagination":{"NofPages":1}}
        rows = StarCityGamesAdapter(http=QueueHttp([FakeResponse(data=data)])).search("Lightning Bolt")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].available)
        self.assertEqual(rows[0].stock, 3)
