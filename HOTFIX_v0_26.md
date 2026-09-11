# HOTFIX v0.26 — Mercadia Bridge

Mercadia rechaza actualmente las IPs del hosting público de Fetchuccini con HTTP 403.
Esta versión agrega un bridge local autorizado: tu PC consulta Mercadia desde tu red normal y sincroniza a Railway solamente los resultados normalizados.

## Qué incluye
- Endpoints protegidos por `MERCADIA_BRIDGE_KEY` para pedir trabajos pendientes y subir resultados.
- `scripts/mercadia_bridge.py`: sincronizador local; usa la búsqueda completa de catálogo desde tu conexión doméstica para no quedar limitado al autocomplete.
- `mercadia_bridge_setup.bat`: genera la clave local y crea una tarea de Windows cada 1 hora.
- `mercadia_bridge_run.bat`: ejecuta una sincronización manual o programada.
- `mercadia_bridge_uninstall.bat`: elimina la tarea programada.
- `mercadia_bridge_config.bat` y el log están excluidos de Git.
- El frontend de v0.21 no cambia visualmente.

## Funcionamiento
1. Un usuario busca una carta.
2. Railway deja esa búsqueda de Mercadia en una cola.
3. El BAT horario de Windows consulta la cola.
4. Tu PC consulta Mercadia y sube el resultado a Railway.
5. Las siguientes búsquedas reciben Mercadia desde el cache sincronizado.

Los resultados sincronizados se consideran frescos durante 2 horas y se conservan como fallback hasta 7 días.
