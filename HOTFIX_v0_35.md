# Fetchuccini v0.35 — Backend quality, normalization & Mercadia safety

Base: v0.34.

## Normalización MTG v2
- Matching tolerante a acentos: `Glóin` = `Gloin`.
- Apóstrofes rectos/curvos: `Urza's` = `Urza’s`.
- Guiones Unicode y espacios normalizados.
- Split cards: `Fire // Ice` y `Fire / Ice` comparten matching; el front face se usa sólo como fallback cuando no hubo resultados.
- Las variantes se prueban únicamente si el intento anterior no devolvió publicaciones comprables.

## Caché normalizada
- Las variantes equivalentes del mismo nombre comparten clave de caché.
- Ej.: `Glóin the Mighty` y `Gloin the Mighty` ya no crean dos snapshots distintos.
- También se normaliza la cola legacy del Mercadia Bridge y el autocomplete.

## Normalización de publicaciones
- Idiomas comunes pasan a nombres consistentes en español (`English`/`EN` → `Inglés`).
- Condiciones comunes se unifican (`NM` → `Near Mint`, `LP` → `Lightly Played`, etc.).
- Acabados se unifican (`Normal`/`Non Foil` → `Non-foil`).
- Monedas se normalizan en mayúsculas.
- URLs externas sólo se exponen al navegador si son `http://` o `https://`.

## Deduplicación
- Se eliminan duplicados repetidos por paginación/endpoints dentro de cada tienda.
- Se preserva la fila más completa y el mayor stock conocido cuando dos filas representan la misma variante.
- El endpoint agregado también deduplica antes de responder.

## Mercadia: catálogo más seguro
- Si una sincronización completa cae sospechosamente respecto del catálogo anterior, Railway la rechaza y conserva el último catálogo sano.
- Umbrales por defecto: mínimo 15.000 publicaciones y al menos 65% del tamaño anterior.
- El primer catálogo también debe superar el mínimo absoluto.
- Archivos `.jsonl/.meta.json` abandonados se limpian automáticamente después de 24 h.
- Estado de antigüedad: verde <12 h, amarillo 12–36 h, rojo >36 h.
- El Bridge informa claramente cuando Railway preservó el catálogo anterior.
- El instalador de la tarea de Windows queda alineado con el ciclo actual de 6 horas.

## Seguridad
- CSP, Permissions-Policy, Referrer-Policy y X-Permitted-Cross-Domain-Policies.
- HSTS conservador en producción.
- Rate limiting usa `X-Real-IP` en Railway y conserva fallbacks para otros entornos.

## Tests
- Tests de normalización de nombres MTG.
- Tests de vocabularios de idioma/condición/acabado.
- Tests de deduplicación y URLs seguras.
- Tests del guard anti-catálogo-parcial y de freshness de Mercadia.
- Test de limpieza de staging viejo.
- Tests de headers de seguridad y resolución de IP.
- Contrato frontend para estados de catálogo viejo.

## Archivos principales tocados
- `config/settings.py`
- `mercadia_bridge_setup.bat`
- `scripts/mercadia_catalog_sync.py`
- `searchapp/middleware.py`
- `searchapp/services/aggregator.py`
- `searchapp/services/listing_normalization.py`
- `searchapp/services/mercadia_catalog.py`
- `searchapp/services/models.py`
- `searchapp/services/utils.py`
- `searchapp/static/searchapp/app.js`
- `searchapp/views.py`
- tests asociados
