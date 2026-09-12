# Fetchuccini v0.32

Robustez para publicación pública:

- Rate limiting por IP en autocomplete y endpoints de búsqueda.
- Circuit breaker por tienda: 3 fallos consecutivos pausan llamadas durante 5 minutos.
- Logs claros de rate limit, apertura y recuperación de circuitos para Railway.
- `/health/` incluye presencia/tamaño del catálogo Mercadia y circuitos abiertos sin llamar a terceros ni parsear el JSON completo.
- Tests offline para los 7 adaptadores, Mercadia indexado, rate limiting y circuit breaker.
- GitHub Actions ejecuta la suite automáticamente en cada push a `main` y en pull requests.
- Modal con foco accesible y navegación Tab atrapada correctamente.
- Estado general más limpio: si no hay filtros activos muestra `N publicaciones encontradas`.
