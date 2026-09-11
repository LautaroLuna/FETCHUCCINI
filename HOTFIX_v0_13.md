Fetchuccini v0.13 — producción / Render

Objetivo: reducir requests externos y evitar rate limits en el hosting público.

Cambios:
- Magic Lair ya no abre un .js por cada producto. Lee variantes, stock, condición y precio directamente de las tarjetas de búsqueda.
- La Batikueva ya no abre una página de detalle por cada producto para enriquecer set/collector.
- MagicDealers ya no abre páginas de detalle para cada publicación con stock. Usa la información de la búsqueda directamente.
- Las tres tiendas hacen muchos menos requests y deberían responder mucho más rápido en Render.
- El frontend muestra mensajes más claros para 403, 429, timeout y errores SSL.
- Cada tienda tiene un límite de espera de 90 s en el navegador para evitar búsquedas eternas.
- Pirulo y Mercadia pueden seguir mostrando 403 si sus orígenes bloquean el tráfico del proveedor de hosting. No se intenta eludir ese bloqueo.
