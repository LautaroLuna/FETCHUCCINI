# Fetchuccini v0.18

- Vista **Tarjetas** como predeterminada para usuarios nuevos.
- Se conserva el selector **Tabla / Tarjetas** y la preferencia elegida se sigue guardando localmente.
- Búsqueda por prefijo: `lightning` puede devolver Lightning Bolt, Lightning Axe, Lightning Helix, etc.
- Los adaptadores filtran resultados para quedarse solo con nombres que empiezan con el texto buscado.
- Magic Lair usa búsqueda no citada para permitir prefijos.
- StarCityGames usa búsqueda por keyword y luego filtra por prefijo.
- Los resultados parciales muestran el nombre real de cada carta, no el texto incompleto ingresado.
- Cache de tiendas actualizado a namespace v18 para no reutilizar resultados vacíos de la búsqueda exacta anterior.
