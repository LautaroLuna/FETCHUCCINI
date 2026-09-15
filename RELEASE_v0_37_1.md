# Fetchuccini v0.37.1

Corrective performance build inside the v0.37 line.

## La Batikueva
- Stops after two consecutive Tiendanube result pages without a card-name match instead of walking broad search pagination until the HTTP budget is exhausted.
- Hard page cap: 6 pages.
- Store budget reduced to 6 requests / 6 seconds, with 2.5 s connect and 4 s read timeouts.
- The early relevance stop is graceful: it does not mark a normal zero-result lookup as a partial/error response.

This specifically addresses the production case where `Lightning Bolt` took ~8 s and ended with `SearchBudgetExceeded: se alcanzó el máximo de 15 requests para la tienda`.
