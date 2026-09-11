# HOTFIX v0.24

## Mercadia
- MageWorx autocomplete is now used as a direct product source before GraphQL.
- Fetchuccini no longer needs to open Mercadia product detail pages when autocomplete already supplies product name, SKU, image, description, price and URL.
- When MageWorx exposes `add_to_cart`, its presence is used as the saleable/in-stock signal.
- GraphQL and the old HTML search remain fallbacks.
- If Mercadia still rejects Railway, the error now records which route failed (`autocomplete`, `graphql`, `autocomplete-detail`, `catalogsearch`) so we can diagnose without a screenshot.

No frontend/theme changes. Pirulo remains unchanged.
