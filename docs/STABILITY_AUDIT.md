# Auditoría de estabilidad de OpenMarket

Base auditada: `27a91ae`, versión 0.2.0. Se conserva la licencia AGPL-3.0-or-later.

## Hallazgos

| Prioridad | Hallazgo y evidencia | Estado |
| --- | --- | --- |
| P0 | Dos compras simultáneas de 80 con 100 disponibles confirmaron ambas operaciones y dejaron −60 en un SQLite aislado. El mismo patrón podía reutilizar posiciones para ventas concurrentes. | Corregido. El bloqueo de escritura se toma antes de consultar cartera, saldo y posición. Pruebas de compra y venta simultáneas. |
| P1 | La protección contra acceso remoto dependía del lanzador `python -m openmarket`. La aplicación ASGI permitía peticiones sin token cuando se desplegaba por otra vía. | Corregido. El modo local comprueba el host y la dirección del cliente. En remoto se exige un token de al menos 32 caracteres. |
| P1 | El diagnóstico podía consultar proveedores externos aun con `OPENMARKET_OFFLINE=true`. Los clientes HTTP seguían redirecciones. | Corregido. Pruebas con transporte simulado que comprueban el bloqueo en ambos casos. |
| P1 | `npm audit` registró un hallazgo alto en `undici`. | Corregido en el lockfile. |
| P1 | El modo inicial habilitaba precios sintéticos por defecto y podía servir caché caducada sin límite de antigüedad. | El modo demo exige activación explícita. La política de antigüedad y la etiqueta de caché caducada quedan para el PR de proveedores. |
| P2 | El límite de longitud del CSV se aplicaba después de leer la solicitud y la importación podía guardar filas parciales. | Límite HTTP de 2 MB aplicado también al recibir un cuerpo por fragmentos. Atomicidad de importaciones pendiente. |
| P2 | Un valor no finito podía provocar un error al serializar una respuesta de validación. | Corregido. Los errores omiten los valores originales y se validan importes, cantidades y comisiones en el almacenamiento. |
| P2 | La inicialización repetía DDL y aceptaba versiones desconocidas. Faltaba copia validada y readiness. | Inicialización transaccional, comprobación de versión, readiness y copia comprobada. |
| P2 | Las alertas dependen de la aplicación abierta y el motor financiero aún necesita las comprobaciones de release de sesgos y contabilidad multimoneda. | Pendiente. |
| P3 | La documentación decía que Node 20 era suficiente y la suite emitía un aviso de deprecación de Starlette TestClient. | README ajustado a Node 22.12 o superior. La advertencia de Starlette permanece. |

## Comprobaciones

- Linux, Python 3.13.5, Node 22.22.2. La línea base ejecutó 93 pruebas de backend y 18 de frontend. El lint inicial de Ruff encontró una infracción SIM102. Typecheck y build iniciales correctos.
- Después del cambio, `ruff check .` y 102 pruebas de backend correctas. Los tests usan bases temporales y simulan la red de proveedores.
- `npm ci`, `npm run typecheck`, `npm test` (18), `npm run build` y `npm audit` correctos. Auditoría final sin hallazgos.
- `pip-audit` señaló el instalador pip 25.1.1 del entorno de pruebas. Se actualizó a 26.3 y la segunda auditoría del entorno instalado terminó sin hallazgos.
- Uvicorn arrancó en loopback con SQLite temporal. Se comprobaron health, readiness, entrega del HTML compilado y rechazo del arranque remoto con un token corto.
- El diagnóstico verificó Kraken diario y ticker para BTC-USD y Frankfurter diario para EURUSD mediante consultas reales. Stooq y Finnhub quedan pendientes por falta de claves.
- Brave renderizó la ruta Configuración y mostró el modo demo desactivado según la API. Docker no está disponible en este entorno. La validación de la CI de release queda pendiente.

## Siguiente incremento

El siguiente PR debe aplicar un límite explícito de antigüedad a la caché y exponer su estado caducado en la API y el frontend. Debe comprobar contratos autenticados, normalización de símbolos, esquemas OHLC y validación CSV con pruebas de procedencia. El ciclo posterior debe cerrar atomicidad de importaciones, coherencia multimoneda, backtesting, alertas, build Docker y CI de release. La versión sigue en 0.2.0 hasta completar los criterios de estabilidad.
