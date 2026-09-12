# HOTFIX v0.33 — Sello visual de "Mejor Precio"

## Objetivo
Hacer que las publicaciones con el mejor precio destaquen más dentro de la vista de tarjetas, usando una estética más vistosa y coherente con la identidad visual de Fetchuccini.

## Cambios realizados
- Se reemplazó el badge inline de "Mejor precio" dentro de las tarjetas por un **sello/medalla superpuesta**.
- El nuevo sello usa una estética de **oro envejecido + cintas rojizas**, alineada con la paleta cálida de la página.
- Se mantuvo el badge compacto original en la **vista tabla**, para no cargar visualmente el listado.
- Se agregó espacio visual en la esquina superior derecha de las tarjetas para evitar que el sello tape el título.
- Se reforzó levemente el highlight de las tarjetas ganadoras con borde/brillo cálido.
- Se ajustó el comportamiento responsive del sello para mobile.

## Archivos tocados
- `searchapp/static/searchapp/app.js`
- `searchapp/static/searchapp/style.css`

## Resultado esperado
- En la vista **Tarjetas**, las cartas con mejor precio deberían mostrar una medalla visible en la esquina superior derecha con el texto:
  - `MEJOR`
  - `PRECIO`
- En la vista **Tabla**, se mantiene el badge textual chico debajo del precio.
