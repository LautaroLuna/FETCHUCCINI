# Fetchuccini v0.37.2

## MagicDealers latency

- Reutiliza una única conexión HTTP/TLS durante la paginación de una búsqueda de MagicDealers.
- Mantiene las páginas secuenciales: no aumenta la concurrencia ni la presión sobre CrystalCommerce.
- Si el origen corta una conexión keep-alive, descarta la sesión y reintenta una vez con una conexión fresca.
- Agrega un log `magicdealers pagination` con tiempo, coincidencias y stock por página para medir la tienda en producción.
- No reduce todavía el máximo de 8 páginas, para no perder ediciones válidas mientras medimos el impacto real de la reutilización de conexión.

Esta versión incluye íntegramente v0.37.1 y todas las correcciones de v0.37.0.
