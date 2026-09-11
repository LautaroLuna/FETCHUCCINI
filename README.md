# Fetchuccini — MVP 0.19

Comparador de precios y stock de cartas de Magic: The Gathering para:

- MTG Pirulo
- Mercadia City
- Magic Lair
- La Batikueva
- MagicDealers
- La Workshop TCG
- StarCityGames

## Qué incluye esta primera versión

- Django con una sola pantalla de búsqueda.
- API interna `GET /api/search/?q=Lightning+Bolt`.
- Adaptadores separados por tienda.
- Búsquedas en paralelo para que una tienda lenta no bloquee a las demás secuencialmente.
- Normalización común de precio, moneda, stock, edición, collector number, idioma, condición y finish.
- Filtros básicos en el navegador.
- Cache de 5 minutos para no castigar las tiendas con requests repetidos.
- Errores aislados por tienda: si una falla, las otras siguen respondiendo.

> Esta es una versión de desarrollo. Las tiendas pueden cambiar HTML/endpoints sin aviso. Los adaptadores HTML (Mercadia, Batikueva y MagicDealers especialmente) deben validarse con búsquedas reales antes de desplegar públicamente.

## Instalación en Windows

Abrí CMD o PowerShell dentro de la carpeta del proyecto:

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py runserver
```

Después abrí:

`http://127.0.0.1:8000/`

## Prueba rápida desde consola

Con el entorno virtual activado:

```powershell
py scripts\test_search.py "Lightning Bolt" la_workshop starcitygames
```

Primero conviene probar **La Workshop + StarCityGames**, porque son los dos adaptadores con API estructurada más directa. Después habilitamos/ajustamos los demás uno por uno con datos reales.

## Endpoint

```text
GET /api/search/?q=Lightning%20Bolt
GET /api/search/?q=Lightning%20Bolt&stores=la_workshop,starcitygames
```

Formato normalizado de una publicación:

```json
{
  "store": "StarCityGames",
  "card_name": "Lightning Bolt",
  "set_name": "Magic 2010",
  "set_code": null,
  "collector_number": "146",
  "language": "English",
  "condition": "Played",
  "finish": "Non-foil",
  "style": null,
  "price": "2.09",
  "currency": "USD",
  "stock": 1,
  "available": true,
  "url": "https://starcitygames.com/...",
  "image_url": "https://...",
  "product_id": 162370,
  "variant_id": 648110,
  "sku": "SGL-MTG-M10-146-ENN2",
  "scryfall_id": null
}
```

## Arquitectura

```text
searchapp/
  services/
    aggregator.py
    http.py
    models.py
    scryfall.py
    utils.py
    stores/
      pirulo.py
      mercadia.py
      magic_lair.py
      batikueva.py
      magicdealers.py
      la_workshop.py
      starcitygames.py
```

Cada tienda implementa `search(card_name)` y devuelve `Listing` normalizados. Eso permite cambiar un scraper sin tocar el resto del sistema.

## Decisiones de seguridad y estabilidad

- No se guardan cookies de usuario, Authorization, sesiones ni credenciales.
- Pirulo obtiene cualquier metadata pública de storefront dinámicamente; no hay tokens copiados/hardcodeados en el repositorio.
- Timeout + retry limitado en requests.
- Cache corta para reducir carga externa.
- No se usa Selenium/Playwright en el MVP.

## Siguiente fase

1. Ejecutar una prueba real con `Lightning Bolt` en la PC del desarrollador.
2. Corregir selectores de los adaptadores HTML que hayan cambiado.
3. Añadir canonicalización Scryfall completa y deduplicación de impresiones.
4. Añadir conversión opcional ARS/USD y orden por precio comparable.
5. Guardar historial de precios y stock en SQLite/PostgreSQL.
6. Búsqueda de mazos y optimización de compra por tienda.
7. Docker + despliegue.

## v0.11 — búsqueda progresiva y cache persistente

- El frontend consulta cada tienda de forma independiente y muestra resultados apenas termina cada una.
- Se agregó cache persistente por tienda: los resultados recientes sobreviven reinicios del servidor.
- Cache fresca: 5 minutos.
- Fallback stale: hasta 24 horas. Si una tienda falla temporalmente, Fetchuccini puede mostrar el último resultado exitoso y marcarlo como dato anterior.
- La pantalla muestra estados por tienda: buscando, cache, actualizando, lista o fallback anterior.
- MagicDealers reduce las visitas a páginas de detalle: solo enriquece publicaciones con stock, disminuyendo mucho la cantidad de requests sin aumentar la concurrencia.
- Los endpoints progresivos nuevos son `GET /api/search/store/` y `GET /api/search/cache/`.

No requiere migraciones nuevas.


## Deploy público

La v0.12 incluye configuración para Render (`render.yaml`, `build.sh`, WhiteNoise y Gunicorn). Ver `DEPLOY_RENDER.md`.


## Cambios v0.15

- La versión online no consulta Pirulo ni Mercadia mientras rechacen tráfico de servidores públicos.
- Solo se muestran publicaciones realmente disponibles: `available=True` y stock mayor a 0 cuando la tienda informa cantidad.
- Se eliminó el filtro “Solo con stock” porque ahora es el comportamiento fijo.
- Heavily Played / Muy Jugada se muestra en rojo.
- El buscador inicia vacío y conserva `Ej: Lightning Bolt` como placeholder.
- Próximo paso previsto: autocompletado de nombres de cartas usando Scryfall.


## v0.18

- Vista Tarjetas como predeterminada para usuarios nuevos.
- La búsqueda acepta prefijos: `lightning` puede devolver todas las cartas cuyo nombre comienza con Lightning.
- Se conserva la opción de cambiar a Tabla.


## v0.19

- Nueva paleta visual inspirada en la forja enana / martillo al rojo vivo: fondos más oscuros, acentos ember rojo-naranja y highlights cálidos.
- Se agregó favicon local de Fetchuccini (`fetchuccini-forge-icon.png`) para que la pestaña del navegador y buscadores muestren el ícono del martillo sobre el yunque.
- Se añadieron metadatos básicos (`theme-color`, Open Graph y Twitter) usando la misma imagen de marca.
- Versionado estático actualizado a `0.19` para forzar recarga de CSS/JS en producción.
