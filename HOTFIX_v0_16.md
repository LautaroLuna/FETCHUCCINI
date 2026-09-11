# Fetchuccini v0.16 — Autocomplete con Scryfall

- Autocomplete de nombres oficiales de cartas usando la API pública de Scryfall.
- Empieza a consultar recién desde 2 caracteres.
- Debounce de 280 ms para evitar requests innecesarios mientras se escribe.
- Cache de 1 hora por búsqueda en Django para respetar los límites de Scryfall.
- Máximo 12 sugerencias por consulta.
- Soporte de teclado: flechas, Enter y Escape.
- Soporte de mouse y atributos ARIA para accesibilidad.
- Las sugerencias solo completan el nombre; la búsqueda en tiendas se ejecuta cuando el usuario presiona Buscar/Enter.
- User-Agent y Accept explícitos al consultar Scryfall.
