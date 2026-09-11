# Fetchuccini hotfix v0.4

Corrige la inestabilidad de MagicDealers observada durante búsquedas grandes.

- Reduce las lecturas simultáneas de páginas de detalle de 4 a 2.
- Agrega una pausa breve entre detalles para evitar ráfagas de requests.
- Si MagicDealers responde 429/5xx en un detalle, conserva el precio, stock, idioma,
  condición y URL obtenidos desde la página de búsqueda en vez de descartar toda la tienda.
- Un fallo aislado de un producto ya no provoca que MagicDealers aparezca como error total.
