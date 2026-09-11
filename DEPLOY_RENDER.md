# Publicar Fetchuccini en Render

Fetchuccini v0.12 ya viene preparada para desplegarse como un Web Service de Django en Render.

## Flujo recomendado

1. Subir esta carpeta a un repositorio de GitHub.
2. En Render, crear un Blueprint y conectar ese repositorio.
3. Render detectará `render.yaml` y creará el servicio `fetchuccini`.
4. Al terminar el deploy, Render entregará una URL pública del tipo `https://fetchuccini.onrender.com`.

## Qué hace el deploy

- Instala dependencias desde `requirements.txt`.
- Ejecuta `collectstatic` para CSS/JS.
- Ejecuta migraciones de Django.
- Sirve la aplicación con Gunicorn.
- WhiteNoise sirve los archivos estáticos.
- `/health/` se usa como health check.

## Variables

El `render.yaml` genera `SECRET_KEY`, desactiva DEBUG y configura el cache temporal.

## Render Free

El plan gratis es suficiente para probar con amigos. Tiene dos limitaciones importantes:

- El servicio se duerme tras un período de inactividad, así que la primera visita puede tardar en despertar.
- El sistema de archivos es efímero. El cache de Fetchuccini funciona mientras la instancia está activa, pero se pierde al reiniciar o dormir. Esto no rompe las búsquedas; solamente elimina el cache previo.

Para un uso público más intenso conviene luego pasar a un plan sin spin-down y a un cache persistente administrado.
