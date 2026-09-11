# Fetchuccini v0.14 — Railway deployment fix

- Railway pasa a ser reconocido como entorno de producción.
- Gunicorn escucha explícitamente en `0.0.0.0:$PORT`.
- Se agrega `healthcheck.railway.app` a `ALLOWED_HOSTS`.
- Se admite `RAILWAY_PUBLIC_DOMAIN`.
- Se configura `/health/` como health check.
- `collectstatic` se ejecuta en build y las migraciones en pre-deploy.
- Render sigue siendo compatible.
