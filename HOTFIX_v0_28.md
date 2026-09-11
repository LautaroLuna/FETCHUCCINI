# HOTFIX v0.28

## MagicDealers
- Eliminé los reintentos anidados que podían convertir una sola búsqueda fallida en hasta 15 intentos HTTP.
- MagicDealers ahora usa como máximo 2 conexiones frescas por página, timeout de 9 s y backoff corto.
- La paginación se corta cuando una página ya no contiene cartas que coinciden con el prefijo buscado.
- Se limita a 8 páginas como protección adicional.
- La normalización de resultados ya no usa un ThreadPool innecesario porque no se consultan páginas de detalle.
- Los resultados exitosos de MagicDealers quedan frescos 30 minutos para no repetir una búsqueda lenta por cada usuario.

## Mercadia
- No cambia el Bridge de v0.27. Esta versión prepara el camino para pasar el inventario sincronizado a almacenamiento persistente en una siguiente etapa.
