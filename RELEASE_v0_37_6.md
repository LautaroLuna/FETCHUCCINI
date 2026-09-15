# Fetchuccini v0.37.6

Restauración de la rama optimizada v0.37 después de validar en producción que la latencia fría observada también ocurre con la v0.36.1 original.

## Base restaurada

Esta build conserva íntegramente el comportamiento de v0.37.4 y descarta el rollback selectivo v0.37.5.

Incluye:

- corrección de `store_keys=[]` para que una lista vacía no dispare todas las tiendas;
- `SECRET_KEY` obligatoria en producción;
- versión centralizada;
- `STORE_REGISTRY` y `StorePolicy`;
- presupuestos de búsqueda, deadlines y límites por tienda;
- caché fresh/stale y resultados parciales protegidos;
- `/api/search/` unificado con el pipeline protegido;
- mínimo configurable de 2 caracteres;
- frontend dinámico desde el registro de tiendas y render de una sola vista;
- lock Redis atómico para refresh;
- deduplicación independiente del precio;
- corrección del bridge `.bat`;
- corte temprano de paginación irrelevante en La Batikueva;
- conexión HTTP/TLS persistente en MagicDealers;
- Advanced Search de MagicDealers con `search[in_stock]=1`, relevancia y fallback al buscador clásico;
- telemetría de paginación de MagicDealers.

## Resultado de la validación

La v0.36.1 original mostró también latencias frías de varios segundos en Magic Lair, La Batikueva y MagicDealers. Por lo tanto, esas latencias no se atribuyen a la arquitectura v0.37 y se restaura la rama mejorada.

No se introduce ningún cambio funcional adicional respecto de v0.37.4 aparte del número de versión y esta documentación.
