# Fetchuccini v0.32.1

Corrección del test de contrato de Mercadia.

El adaptador de Mercadia normaliza el código `EN` como `Inglés`; el test de v0.32 esperaba por error `English`. Esta versión corrige únicamente la expectativa del test, sin cambiar el comportamiento de producción.
