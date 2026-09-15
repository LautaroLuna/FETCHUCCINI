# Fetchuccini v0.37.5 — performance rollback

Esta build vuelve deliberadamente al camino de red y a los adapters probados de v0.36.1.

Conserva únicamente cambios de v0.37 que no alteran scraping ni latencia de origen:

- corrige la semántica `store_keys=[]` para que no signifique «todas las tiendas»;
- versión centralizada en `0.37.5`;
- `SECRET_KEY` obligatoria en producción;
- mínimo de 2 caracteres para búsquedas;
- endurecimiento del origen de IP para rate limiting;
- render del frontend solo de la vista activa;
- limpieza correcta al navegar hacia atrás a una URL sin consulta;
- corrección de `mercadia_bridge_setup.bat`.

## Rollback intencional

Se retiraron del camino crítico `StorePolicy`, `SearchBudget`, cambios de HttpClient y las optimizaciones experimentales de adapters de v0.37.1–v0.37.4. MagicDealers, Batikueva y el resto vuelven a su implementación de red de v0.36.1.

El objetivo de esta versión es recuperar primero la referencia de rendimiento estable y volver a optimizar después, una modificación por vez y con benchmark frío/caliente antes de conservar cada cambio.
