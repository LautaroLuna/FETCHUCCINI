# HOTFIX v0.36.1 — Barra de progreso del Mercadia Bridge

## Cambio
- El bridge manual ya no crea una línea nueva por cada categoría.
- En modo manual muestra **una única barra de progreso que se redibuja en la misma línea**.
- La barra indica porcentaje, categorías completadas, categoría actual, página, stock encontrado, tiempo transcurrido y ETA aproximado.
- La etapa de subida a Railway usa otra barra de progreso en una sola línea.
- Los errores reales siguen imprimiéndose en líneas separadas para que no se pierdan.
- La tarea automática cada 6 horas conserva un log limpio y compacto, sin caracteres `\r` de la barra interactiva.
- Se agrega `mercadia_bridge_manual.bat` para ejecutar la sincronización manual viendo el progreso y mantener la ventana abierta al terminar.

## Archivos tocados
- `scripts/mercadia_catalog_sync.py`
- `mercadia_bridge_manual.bat`
