# HOTFIX v0.25

## Pirulo
- Corregido el falso error "no disponible online" para cartas sin resultados/stock.
- Si BigCommerce GraphQL responde correctamente con 0 publicaciones, ahora Pirulo devuelve 0 en vez de caer al endpoint legacy que Railway no puede usar.
- El endpoint legacy solo se usa si GraphQL falla realmente.

## Mercadia
- Confirmado por los logs de Railway: Mercadia devuelve HTTP 403 tanto en MageWorx autocomplete como en GraphQL y rutas de catálogo.
- La búsqueda ahora falla rápido con un mensaje claro, evitando probar cuatro rutas bloqueadas y perder tiempo.
- No se agregaron proxies ni técnicas para evadir los controles del sitio. Para recuperar Mercadia en producción hace falta whitelist/API autorizada o un bridge/sync desde una red permitida.

## Archivos tocados
- `searchapp/services/stores/pirulo.py`
- `searchapp/services/stores/mercadia.py`
