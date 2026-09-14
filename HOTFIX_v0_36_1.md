# HOTFIX v0.36.1 — Mercadia Bridge con progreso visible

## Cambios
- Nuevo `mercadia_bridge_manual.bat` para ejecutar el bridge manualmente sin que la ventana se cierre al terminar o al fallar.
- El bridge manual muestra la salida de Python en vivo.
- La sincronización completa muestra una barra de progreso y porcentaje general.
- Durante el crawl muestra `Categoría X/Y` y una ETA aproximada.
- Durante la subida muestra el lote actual y el porcentaje general.
- `mercadia_bridge_run.bat` conserva el modo silencioso usado por la tarea programada de Windows; por eso la automatización cada 6 horas no queda esperando un `pause`.
- `PYTHONUNBUFFERED=1` para que el progreso aparezca inmediatamente en CMD.

## Uso manual
Hacer doble clic en:

`mercadia_bridge_manual.bat`

No usar `mercadia_bridge_run.bat` para mirar el progreso manual: ese archivo sigue siendo el runner silencioso de la tarea programada.

## Archivos tocados
- `scripts/mercadia_catalog_sync.py`
- `mercadia_bridge_run.bat`
- `mercadia_bridge_setup.bat`
- `mercadia_bridge_manual.bat` (nuevo)
