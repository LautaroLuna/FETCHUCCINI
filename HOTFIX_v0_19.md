# Fetchuccini v0.19

- Se aplicó una nueva paleta de colores inspirada en la imagen de referencia de la forja: carbón oscuro, rojo rúnico, naranja ígneo y detalles cálidos para botones, bordes y tarjetas.
- Se agregó la imagen del martillo sobre el yunque como favicon real de la app (`searchapp/static/searchapp/fetchuccini-forge-icon.png`).
- Se añadieron metatags visuales (`theme-color`, `og:image`, `twitter:image`) usando el mismo asset para mejorar la identidad al compartir o abrir la página.
- Se actualizó el cache busting de assets de `0.18` a `0.19`.

## Archivos tocados

- `searchapp/templates/searchapp/index.html`
- `searchapp/static/searchapp/style.css`
- `searchapp/static/searchapp/fetchuccini-forge-icon.png`
- `README.md`

## Cómo actualizar tu repo

1. Reemplazá tu carpeta del proyecto por esta versión, o copiá solo los archivos modificados.
2. Si usás Git:
   - `git add .`
   - `git commit -m "Forge theme + favicon branding"`
   - `git push`
3. Railway/Render redeployará automáticamente. Si no ves el favicon enseguida, hacé hard refresh (`Ctrl + F5`).
