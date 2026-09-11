# MTG Price Finder — Hotfix v0.2

Changes:
- Pirulo: use the storefront's public suggestion limit (12) instead of an invalid 128 that caused HTTP 400.
- La Batikueva: tolerate both JSON and HTML responses from Tiendanube hybrid-scroll search pages and add AJAX-compatible request headers.
- MagicDealers: parallelize product detail reads with a conservative pool of 4 workers.
- Mercadia: parallelize product detail reads with a conservative pool of 4 workers.
- Magic Lair: parallelize Shopify product JSON reads with a conservative pool of 4 workers.

Validated locally with Python compileall and the project's unit tests.
