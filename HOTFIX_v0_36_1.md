# HOTFIX v0.36.1 — progreso visible del Mercadia Bridge

## Cambios
- El CMD del bridge ahora muestra la salida en vivo **y** la guarda simultáneamente en `mercadia_bridge.log`.
- La sincronización completa de Mercadia muestra **porcentaje total de progreso**.
- Durante el rastreo se muestra:
  - porcentaje aproximado total
  - categoría actual / total
  - tiempo transcurrido
  - ETA estimada de la etapa
  - cantidad de publicaciones encontradas en la categoría
- Durante la subida a Railway se muestra:
  - porcentaje 90–100%
  - lote actual / total
  - publicaciones subidas / total
  - ETA estimada
- Al completar aparece explícitamente `100.0%`.
- Se fuerza UTF-8 en el CMD para que acentos y mensajes se vean correctamente.
- `/health/` y los headers de diagnóstico reportan ahora la versión `0.36.1`.

## Archivos tocados
- `scripts/mercadia_catalog_sync.py`
- `mercadia_bridge_run.bat`
- `config/settings.py`
- `searchapp/tests/test_scalability.py`
- `README.md`

## Ejemplo
```text
[PROGRESO]  37.8% | Catálogo 214/510 | transcurrido 19m 12s | ETA 26m 34s | Modern Horizons 3 · 148 publicaciones
...
[PROGRESO]  96.4% | Subida 97/152 | transcurrido 1m 08s | ETA 38s | 38800/60401 publicaciones
[PROGRESO] 100.0% | Sincronización completa
```
