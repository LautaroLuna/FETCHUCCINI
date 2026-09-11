# HOTFIX v0.23 — Pirulo + Mercadia online

Esta versión vuelve a habilitar Pirulo y Mercadia en Railway/Render sin usar proxies ni técnicas de evasión.

## Pirulo
- Ya no depende primero de `lgsc-search.lgs-companion.com`, que respondía 403 desde hosting.
- Usa la API pública Storefront GraphQL de BigCommerce para buscar productos y variantes.
- El token público de Storefront se obtiene dinámicamente del HTML de Pirulo; no se hardcodea ni se guarda en el repo.
- Se conserva el endpoint público de sugerencias como fallback.
- Solo devuelve variantes realmente comprables/con stock.

## Mercadia
- Ya no depende primero de la página `catalogsearch/result`, que respondía 403 desde hosting.
- Usa primero el endpoint público GraphQL de Magento para búsqueda, precio, disponibilidad e imagen.
- Si GraphQL no está disponible, intenta el autocomplete público de MageWorx y por último el HTML anterior.
- Solo devuelve publicaciones en stock.

## Configuración
- Pirulo y Mercadia vuelven a estar habilitadas por defecto online.
- Si alguna tienda vuelve a cambiar, se puede desactivar sin tocar código con `FETCHUCCINI_DISABLED_STORES`.

## Importante
La versión está preparada para probarse en Railway. Como los bloqueos originales ocurren específicamente desde el hosting, la validación definitiva debe hacerse después del deploy.
