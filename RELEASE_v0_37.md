# Fetchuccini v0.37.0

Esta versión incluye el hotfix que se había planificado como v0.36.2 y empieza la etapa de consolidación del núcleo.

## Cambios incluidos

- Bug `[] == todas las tiendas` corregido en `SearchAggregator`.
- `SECRET_KEY` obligatoria en producción (`DEBUG=False`).
- Versión única en `searchapp/version.py`: `0.37.0`.
- `STORE_REGISTRY` y `StorePolicy` como fuente única de tiendas y límites operativos.
- Presupuesto por búsqueda: deadline, máximo de requests y timeouts connect/read.
- Caché fresh/stale por política de tienda (MagicDealers conserva 30 min fresh).
- Resultados parciales preservados en adapters paginados cuando falla una página posterior.
- Un resultado parcial usa caché corta y no reemplaza un stale completo existente.
- `/api/search/` unificado con el pipeline protegido usado por `/api/search/store/`.
- Mínimo de búsqueda configurable, default 2 caracteres.
- Store checkboxes y labels generados desde el registry.
- Render frontend solo de la vista activa y limpieza al volver a una URL sin `q`.
- Redis refresh lock con `SET NX EX` + compare-and-delete Lua.
- Deduplicación independiente del precio mutable.
- User-Agent actualizado automáticamente con la versión real.
- CI alineado con `.python-version`.
- Fix de `mercadia_bridge_setup.bat`.

## Antes del deploy en Railway

Crear/confirmar estas variables:

```text
SECRET_KEY=<clave aleatoria larga>
REDIS_URL=<la existente, si Redis ya está conectado>
MERCADIA_BRIDGE_KEY=<la existente>
```

Generar una `SECRET_KEY` nueva en Windows:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Validación recomendada después del deploy

1. Abrir `/health/` y confirmar `version: 0.37.0`.
2. Buscar `Lightning Bolt` con las 7 tiendas.
3. Buscar solamente Mercadia y confirmar que no se disparan las otras tiendas.
4. Repetir la misma búsqueda y verificar respuestas de caché.
5. Probar una query de un solo carácter y confirmar HTTP 400.
6. Ejecutar el bridge manual de Mercadia y verificar progreso + finalización.
