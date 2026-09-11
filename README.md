# Fetchuccini — MVP 0.18

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


## v0.20

- La paleta forge se oscureció: fondo más carbón/negro y rojos menos brillantes, manteniendo naranja fuego en acciones importantes.
- Se agregó paginación frontend de 24 publicaciones por página después de aplicar filtros y ordenamiento.
- La paginación funciona tanto en Tarjetas como en Tabla, conserva filtros y permite navegar con anterior/siguiente y números de página.
- El modal de carta sigue apuntando al resultado correcto dentro de cada página.


## v0.23

- Pirulo y Mercadia vuelven a habilitarse en producción mediante APIs públicas de sus propias plataformas.
- Pirulo usa BigCommerce Storefront GraphQL como ruta principal y el suggest externo solo como fallback.
- Mercadia usa Magento GraphQL como ruta principal, MageWorx autocomplete como segundo fallback y el HTML tradicional como último recurso.
- No se usan proxies, rotación de IPs ni credenciales privadas.


## v0.24

- Mercadia now prefers its public MageWorx autocomplete payload directly, avoiding detail-page requests whenever possible.
- GraphQL and legacy HTML remain fallback sources.
- Mercadia errors include a route-by-route diagnostic chain for hosted deployments.


## v0.25

- Pirulo ya considera una búsqueda GraphQL exitosa con cero publicaciones como un resultado válido; esto evita falsos errores para cartas que Pirulo no tiene en stock.
- Mercadia detecta el 403 del hosting y falla rápido con un mensaje explícito. La tienda bloquea actualmente las rutas públicas probadas desde Railway, por lo que su recuperación requiere whitelist/API autorizada o una estrategia de sincronización desde una red permitida.


## v0.26 — Mercadia Bridge

- Mercadia puede sincronizarse desde una PC Windows mediante un bridge local protegido por una clave privada.
- Railway nunca necesita consultar directamente el origen de Mercadia cuando el bridge está habilitado.
- Incluye BAT de instalación, ejecución manual y desinstalación de la tarea horaria.
- El cache de Mercadia sincronizado es fresco por 2 horas y conserva fallback hasta 7 días.


## v0.27

- Mercadia Bridge se ejecuta cada 30 minutos.
- Las búsquedas activas de Mercadia se resincronizan automáticamente cada 30 minutos.
- La interfaz muestra la antigüedad de la última sincronización de Mercadia.


## v0.28

- MagicDealers reduce drásticamente su presupuesto de retries y corta paginación irrelevante.
- Cache fresca de MagicDealers ampliada a 30 minutos.
- El Bridge de Mercadia de v0.27 se mantiene sin cambios.
