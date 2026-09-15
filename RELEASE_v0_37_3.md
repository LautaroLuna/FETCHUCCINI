# Fetchuccini v0.37.3

Parche de observabilidad dentro de la serie v0.37.

## Cambios

- Habilita el logger `searchapp.services.stores.magicdealers` en nivel `INFO`.
- Los recorridos de MagicDealers de más de una página ahora registran `magicdealers pagination` con:
  - página,
  - tiempo por página,
  - coincidencias,
  - publicaciones con stock,
  - cantidad total de requests.
- No modifica la lógica de búsqueda ni de caché respecto de v0.37.2.

## Validación esperada

Después del deploy, `/health/` debe reportar `0.37.3`. Ejecutar una búsqueda nueva de MagicDealers y buscar `magicdealers pagination` en Railway Logs.
