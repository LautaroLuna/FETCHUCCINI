# HOTFIX v0.27

## Cambios
- Mercadia Bridge pasa de ejecutarse cada 1 hora a cada 30 minutos.
- Las búsquedas de Mercadia usadas recientemente quedan programadas para resincronizarse cada 30 minutos mientras sigan activas.
- El estado de Mercadia ahora muestra cuándo fue la última sincronización: `Mercadia: X · sincronizado hace N min`.
- Si una consulta todavía no tuvo su primera sincronización, muestra `esperando sincronización…`.
- Si existe un resultado anterior pero toca actualizarlo, mantiene el resultado visible y muestra `actualizando…` o `actualización pendiente`.
- No se modifica el frontend visual de la v0.21; solo el texto de estado de Mercadia.

## Importante
Después de aplicar el hotfix, ejecutá de nuevo `mercadia_bridge_setup.bat`. Como la configuración ya existe, conservará la misma clave y reemplazará la tarea de Windows para que corra cada 30 minutos.
