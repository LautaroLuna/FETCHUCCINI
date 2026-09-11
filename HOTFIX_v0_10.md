# Fetchuccini Hotfix v0.10

- Corrige los SSL EOF intermitentes de MagicDealers.
- La búsqueda de MagicDealers reintenta hasta 5 veces con conexión TLS nueva y backoff progresivo.
- Si falla una página posterior de paginación, conserva los resultados ya obtenidos en vez de descartar toda la tienda.
- Reduce MagicDealers a un solo worker de detalle y aumenta levemente la pausa para disminuir 503/cortes de conexión.
- No modifica el frontend v0.9.
