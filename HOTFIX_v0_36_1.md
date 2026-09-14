# HOTFIX v0.36.1 — progreso visible del Mercadia Bridge

## Cambio
- El CMD del bridge ahora muestra **progreso en vivo** durante la sincronización completa.
- La fase de recorrido de Mercadia muestra:
  - barra ASCII de progreso
  - porcentaje de categorías completadas
  - categorías completadas / total
  - tiempo transcurrido
  - ETA estimado
  - cantidad aproximada de publicaciones recopiladas
  - número de errores acumulados
- Las categorías grandes muestran avance por página para que el proceso no parezca trabado.
- La fase de subida a Railway muestra su propio **porcentaje y ETA por lotes**.
- `mercadia_bridge_run.bat` ahora muestra la salida en la consola **y al mismo tiempo conserva `mercadia_bridge.log`**.
- Python se ejecuta en modo `-u` para que la salida no quede bufferizada y el progreso aparezca inmediatamente.

## Archivos tocados
- `scripts/mercadia_catalog_sync.py`
- `mercadia_bridge_run.bat`

## Ejemplo de salida
```text
[PROGRESO CATÁLOGO] [######------------------]  25.0% (38/152) | transcurrido 14:21 | ETA 43:03 | ~15420 publicaciones recopiladas · 0 error(es)
[PROGRESO SUBIDA]   [############------------]  50.0% (76/152) | transcurrido 00:18 | ETA 00:18 | 30400/60401 publicaciones
```
