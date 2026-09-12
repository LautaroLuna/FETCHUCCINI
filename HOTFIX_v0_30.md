# Fetchuccini Hotfix v0.30

Cambio visual de estado de tiendas:

- Toda tienda que termina correctamente queda en verde, incluso si devolvió 0 publicaciones.
- Mercadia mantiene su estado verde de catálogo sincronizado.
- Si una tienda no puede completar la consulta online, queda en rojo con el mensaje:
  `No se pudo conectar a la pagina online`
- Los detalles técnicos del error se conservan en el atributo `title` del indicador para diagnóstico.
- No se modifica el diseño general v0.21 ni la lógica de resultados, filtros, tarjetas o catálogo de Mercadia.
