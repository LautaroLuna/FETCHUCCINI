# Fetchuccini v0.36 — Redis, escalabilidad y observabilidad

Base: v0.35 estable.

## Redis opcional y fallback seguro
- Si existe `REDIS_URL`, Django usa Redis para caché, rate limiting, circuit breaker, métricas y locks de refresh.
- Si `REDIS_URL` no existe, Fetchuccini sigue funcionando con el cache de archivos de v0.35.
- Redis queda configurado con timeouts cortos e `IGNORE_EXCEPTIONS`, por lo que una caída de Redis no debe tirar abajo el buscador.
- `/health/` informa si el cache está sano y qué backend está activo.
- El healthcheck de Mercadia usa metadata liviana/sidecar y ya no necesita parsear el catálogo completo en un cold start.

## Single-flight / anti stampede
- Dos usuarios buscando la misma carta en la misma tienda al mismo tiempo ya no deberían disparar automáticamente dos consultas iguales al origen.
- La primera request refresca; las demás esperan brevemente por el nuevo snapshot.
- Si existe un snapshot stale, puede mostrarse mientras la actualización está en curso.
- Con Redis, el lock se comparte entre workers de Gunicorn.

## Control de concurrencia del servidor
- El endpoint agregado usa por defecto hasta 4 tiendas simultáneas (`FETCHUCCINI_STORE_CONCURRENCY`).
- Hay un límite global por proceso de 6 trabajos externos simultáneos (`FETCHUCCINI_GLOBAL_STORE_CONCURRENCY`).
- Esto protege los 8 threads actuales cuando varios usuarios buscan a la vez.

## Observabilidad
- Todas las respuestas incluyen `X-Request-ID`.
- Incluyen `X-Fetchuccini-Version: 0.36` y `Server-Timing`.
- Requests API lentas/erróneas quedan correlacionadas en logs por request ID.
- `/health/` informa versión, uptime, backend de cache, latencia, concurrencia, catálogo y circuit breakers; `/health/?details=1` agrega métricas acumuladas por tienda sin hacer pesado el healthcheck de Railway.

## Gunicorn configurable
- Nuevo `gunicorn.conf.py`.
- Valores por defecto siguen conservadores: 1 worker / 8 threads.
- Se puede ajustar luego con `WEB_CONCURRENCY` y `GUNICORN_THREADS` sin tocar código.

## Railway + Redis
1. En el Canvas de Railway: `+ New` → `Database` → `Redis`.
2. En el servicio `fetchuccini`, crear la variable `REDIS_URL` como referencia al `REDIS_URL` del servicio Redis, normalmente `${{Redis.REDIS_URL}}`.
3. Redeploy.
4. Abrir `/health/` y confirmar `"cache": {"backend": "redis", "ok": true, ...}`.

No es obligatorio crear Redis antes de desplegar este hotfix: sin `REDIS_URL` la aplicación usa el fallback de archivos.

## Archivos principales tocados
- `requirements.txt`
- `railway.toml`
- `render.yaml`
- `gunicorn.conf.py`
- `config/settings.py`
- `searchapp/middleware.py`
- `searchapp/views.py`
- `searchapp/services/aggregator.py`
- `searchapp/services/resilience.py`
- `searchapp/services/cache_runtime.py`
- `searchapp/services/metrics.py`
- `searchapp/services/mercadia_catalog.py`
- `searchapp/static/searchapp/app.js`
- `searchapp/tests/test_scalability.py`
- `searchapp/tests/test_mercadia_catalog.py`
