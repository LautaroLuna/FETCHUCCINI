# Fetchuccini v0.34 — Mobile & Safe Performance

Base: v0.33.6 + hotfix v0.33.7.

## Responsive / celular
- Ajustes específicos para 320–430 px.
- Tarjetas obligatorias en <=700 px; se evita la tabla horizontal gigante en móvil.
- Imágenes y títulos de cards reducidos correctamente con selectores de igual/mayor especificidad.
- Footer de las cards adaptado: `Ver` y `Comprar` ocupan dos columnas completas y no desbordan.
- Filtros plegables con botón `Filtros` en móvil.
- A <=520 px los filtros pasan a una sola columna.
- Estados por tienda pasan a una tira horizontal desplazable.
- Modal adaptado a `100dvh`, con scroll interno y botón de compra a ancho completo.
- Autocomplete limitado por altura visible para convivir mejor con el teclado del teléfono.
- Sticky toolbar desactivada en móvil.
- Soporte de safe-area para teléfonos con notch/isla.
- Viewport actualizado con `viewport-fit=cover`.

## Rendimiento / Railway
- Máximo 4 búsquedas de tiendas simultáneas por navegador.
- Al iniciar una búsqueda nueva se cancelan las requests de la búsqueda anterior.
- La cache snapshot también se puede cancelar al cambiar de búsqueda.

## Magic Lair
- Se lee la paginación real de Shopify.
- Se detiene cuando no existe página siguiente.
- Una búsqueda sin coincidencias exactas deja de recorrer páginas después de 3 páginas iniciales vacías, en lugar de poder llegar a 9.

## Pirulo
- El token público de Storefront se guarda sólo en memoria durante 20 minutos.
- Evita volver a descargar una página de Pirulo para obtener el mismo token en cada búsqueda.
- Si el token queda inválido y GraphQL responde 401/403, se fuerza una renovación y se reintenta una vez.

## Assets
- Icono principal reducido de ~2 MB a menos de 600 KB.
- Nuevos favicon 32x32 y Apple Touch Icon 180x180.
- Se eliminaron los querystrings manuales `?v=0.32`; WhiteNoise ya usa manifest/versionado de static en producción.

## Tests
- Nuevos tests de contrato responsive/frontend.
- Tests de paginación de Magic Lair.
- Test del cache en memoria del token de Pirulo.
