# Copia y restauración de OpenMarket

Identifica el archivo real configurado con `OPENMARKET_DB`. La ruta por defecto es `data/openmarket.db` desde la raíz del repositorio. Conserva copias fuera del checkout con permisos restrictivos y en un disco separado cuando sea posible. Las copias incluyen datos privados de carteras, alertas y listas de seguimiento.

## Copia coherente

Desde `backend/`, con el entorno virtual del proyecto instalado, ejecuta lo siguiente. El directorio de destino debe existir y el archivo de destino debe ser nuevo.

```sh
../.venv/bin/python -m openmarket.backup /ruta/openmarket.db /ruta/respaldos/openmarket.db
```

El comando usa la API de backup de SQLite, incluida la información confirmada en el WAL, ejecuta comprobaciones de integridad y relaciones y evita sobrescribir el destino.

## Restauración

Detén OpenMarket, preserva la base actual y usa el mismo comando para restaurar hacia una ruta nueva.

```sh
../.venv/bin/python -m openmarket.backup /ruta/respaldos/openmarket.db /ruta/restaurada.db
OPENMARKET_DB=/ruta/restaurada.db ../.venv/bin/python -m openmarket
```

Verifica `/api/ready` y consulta las carteras y alertas desde el dashboard. Si hay token, la comprobación de readiness requiere la cabecera `Authorization`. Para volver a la base previa, detén el proceso y restablece el valor original de `OPENMARKET_DB`.

La versión actual conserva el esquema 1 de las bases existentes. La inicialización de esquemas nuevos se ejecuta en una transacción y el arranque rechaza un esquema de versión superior.
