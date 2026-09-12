# HOTFIX v0.33.1 — badge "Mejor precio" usando imagen real

## Objetivo
Reemplazar el sello CSS generado por un badge visual usando la imagen `medalla_dorada_al_mejor_precio.png`, manteniendo la estética premium de Fetchuccini.

## Cambios realizados
- Se agregó el asset `searchapp/static/searchapp/medalla_dorada_al_mejor_precio.png`.
- Se actualizó `searchapp/static/searchapp/app.js` para renderizar la imagen real del badge en la vista Tarjetas cuando una publicación tiene el mejor precio.
- Se actualizó `searchapp/static/searchapp/style.css` para posicionar el badge como sello superpuesto en la esquina superior derecha de la card.
- Se ajustó el padding derecho del bloque superior de la card para evitar que la medalla tape el contenido.
- La vista Tabla conserva el badge compacto de texto `Mejor precio`.

## Archivos tocados
- `searchapp/static/searchapp/app.js`
- `searchapp/static/searchapp/style.css`
- `searchapp/static/searchapp/medalla_dorada_al_mejor_precio.png`

## Notas
- Cambio visual/frontend בלבד, sin cambios en lógica de búsqueda.
- Si querés después se puede hacer una v0.33.2 para afinar tamaño, rotación o hover de la medalla.
