# Pruebas / Prototipos

Esta carpeta guarda scripts que **no forman parte del flujo productivo** (`main.py` / `mainOthers.py`), pero que se conservan como referencia, prototipo o prueba de concepto.

## Contenido

### `sync_payments_json.py`

Prototipo de un pipeline **incremental** para la tabla `MesaControl.Payments`, pensado como alternativa al método actual (que en `main.py` borra y recarga la tabla completa en cada corrida).

- **Enfoque**: sincronización incremental por *keyset pagination*, usando una tabla `MesaControl.SyncLog` para recordar la última fecha sincronizada y una tabla de staging `MesaControl.Temp_Payments_Update` para hacer `MERGE` (UPSERT) contra `MesaControl.Payments`.
- **Estado**: no se ha usado en producción. Las tablas `MesaControl.SyncLog` y `MesaControl.Temp_Payments_Update` que necesita **no existen** en la base de datos (`CGestion`), por lo que el script fallaría en su primera consulta si se ejecuta tal cual.
- **No está referenciado** por ningún otro archivo del proyecto (no lo importa `main.py`, `mainOthers.py`, ni nada más).
- **Diferencia de formato importante**: si llegara a activarse, guarda la columna `PagoDocs` como un arreglo JSON (`["JE1201364","CM12095"]`), mientras que el proceso activo en `main.py` la guarda como texto separado por comas (`"CM12095, JE1201364"`). Antes de retomar este script habría que decidir un solo formato y resolver el choque con la carga completa de `main.py`, que seguiría borrando la tabla en cada corrida.

Si en algún momento se retoma esta idea, conviene crear las tablas faltantes, unificar el formato de `PagoDocs` y decidir si reemplaza o convive con la carga completa de `main.py`.
