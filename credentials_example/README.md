# credentials_example

Plantillas (con valores de ejemplo, sin datos reales) de los archivos que deben existir en la carpeta `credentials/` para que el proyecto funcione. La carpeta `credentials/` real **no se sube a git** porque contiene llaves y secretos.

## Cómo usarlo

1. Copia esta carpeta como `credentials/` en la raíz del proyecto (si no existe).
2. Reemplaza cada archivo `*.example.json` por el archivo real correspondiente (sin el `.example` en el nombre), con los valores que te entregue el administrador del proyecto / de Google Cloud.

## Archivos

### `credsDrive.example.json` → `credsDrive.json`
**Sí se usa activamente** en el ETL. Es la cuenta de servicio (service account) de Google que `data_sources.py` usa para leer los Google Sheets (Tesorería, Compras Ariete/Driven, Entregas). La ruta a este archivo se configura en `.env` con la variable `PATH_CREDS_DRIVE`.

Para generarlo: Google Cloud Console → IAM & Admin → Cuentas de servicio → crear/seleccionar cuenta → Llaves → Agregar llave (JSON). El Sheet debe compartirse con el `client_email` de esa cuenta de servicio.

### `credsOAuthEmail.example.json` → `credsOAuthEmail.json`
Al revisar el código actual (`main.py`, `mainOthers.py`, `data_sources.py`), **no encontré ninguna referencia a este archivo** — parece quedar de un uso anterior o de otro script (el `project_id` real que tenía sugiere algo relacionado a notificaciones de Gmail). No es necesario para correr `main.py` / `mainOthers.py` hoy. Se deja la plantilla por si en el futuro se retoma ese flujo; confirma con el equipo antes de asumir que es necesario.

### `token.json`
Es un archivo que generan automáticamente las librerías de Google (`google-auth-oauthlib`) la primera vez que se completa un flujo de autorización OAuth interactivo — no es algo que se escriba a mano, por eso no se incluye una plantilla. Igual que el anterior, no se encontró referencia a él en el código actual del ETL.
