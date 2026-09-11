Fetchuccini Hotfix v0.11

Objetivo: que la búsqueda se sienta rápida sin aumentar agresivamente la cantidad de requests.

Cambios:
- Búsqueda progresiva: cada tienda aparece apenas termina.
- StarCityGames / La Workshop ya no esperan a MagicDealers o Batikueva.
- Cache persistente en disco por tienda.
- Cache fresca de 5 minutos.
- Fallback de último resultado exitoso hasta 24 horas si una tienda falla.
- Indicadores visuales de "buscando", "cache", "actualizando" y "último dato".
- MagicDealers solo abre páginas de detalle para publicaciones con stock, reduciendo decenas de requests lentos.
- Se conserva el endpoint /api/search/ anterior para compatibilidad.
- Nuevos endpoints: /api/search/store/ y /api/search/cache/.
- No requiere migrate.
