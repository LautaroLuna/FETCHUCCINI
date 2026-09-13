# HOTFIX v0.33.7 — búsqueda tolerante a acentos

## Problema
Scryfall/autocomplete devuelve el nombre canónico de cartas como `Glóin the Mighty`, pero algunas tiendas publican e indexan la misma carta como `Gloin the Mighty`. Una búsqueda literal con el acento podía devolver 0 resultados aunque la carta existiera.

## Solución
- Las comparaciones de nombres ahora son **insensibles a acentos**.
- Si una tienda devuelve 0 resultados con el nombre canónico y el nombre contiene diacríticos, Fetchuccini hace **un único segundo intento sin acentos**.
- No se duplica tráfico para búsquedas normales sin acentos.
- La consulta original/canónica se mantiene para la interfaz y el autocomplete.
- Se agregaron tests para `Glóin` ↔ `Gloin` y para el fallback por tienda.

## Archivos tocados
- `searchapp/services/utils.py`
- `searchapp/services/aggregator.py`
- `searchapp/tests/test_utils.py`
- `searchapp/tests/test_accent_search.py`
