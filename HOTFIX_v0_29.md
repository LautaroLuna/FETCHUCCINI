# HOTFIX v0.29 — Mercadia Persistent Catalog

## Qué cambia

- Mercadia deja de depender de una búsqueda individual por carta desde Railway.
- El Bridge de Windows recorre las categorías MTG de Mercadia y arma un catálogo completo de publicaciones actualmente comprables.
- El catálogo se sube a Railway por lotes y se reemplaza de forma atómica: mientras se sincroniza, la web sigue usando la copia anterior.
- Fetchuccini busca Mercadia directamente en ese catálogo local, por lo que una búsqueda responde en milisegundos y funciona aunque Mercadia bloquee la IP de Railway.
- El catálogo conserva nombre, edición/categoría, código de set cuando se puede inferir, collector, idioma, condición, acabado, precio, imagen, SKU, product id y URL.
- El Bridge se programa cada 1 hora.
- Si una categoría falla durante un ciclo, conserva el último snapshot local de esa categoría en lugar de borrarla.
- Se mantienen los endpoints del Bridge anterior como fallback.

## Persistencia en Railway

La v0.29 usa `/data/fetchuccini/mercadia_catalog.json` automáticamente cuando existe un volumen montado en `/data`.
Si no hay volumen, usa almacenamiento temporal y el catálogo seguirá funcionando, pero puede perderse después de un deploy/reinicio hasta la siguiente sincronización.

Recomendado: agregar un Railway Volume al servicio Fetchuccini con mount path `/data`.

## Después de aplicar el hotfix

1. Subí la v0.29 a GitHub/Railway.
2. En Railway conservá `MERCADIA_BRIDGE_KEY`.
3. Recomendado: agregá un Volume montado en `/data`.
4. Ejecutá otra vez `mercadia_bridge_setup.bat` para cambiar la tarea de Windows a cada 1 hora.
5. Hacé doble click en `mercadia_bridge_run.bat` para hacer la primera carga completa sin esperar una hora.
6. El progreso se guarda en `mercadia_bridge.log`.

La primera sincronización es la más larga porque tiene que recorrer todo el catálogo MTG. Las siguientes conservan estado local y nunca publican un catálogo incompleto por una categoría que falle.
