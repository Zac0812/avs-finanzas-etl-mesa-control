# MesaControl

ETL en Python que extrae información de ventas de autos seminuevos desde varias fuentes (NetSuite/Oracle, SQL Server, Google Sheets), la consolida y la guarda en SQL Server para dar seguimiento operativo del proceso ("Mesa de Control de Ventas").

## ¿Qué hace el proyecto?

El proyecto corre dos pipelines independientes, cada uno con su propio flujo de **extracción → transformación → carga**:

### 1. `main.py` — Mesa_Control_Vtas_ETL

Es el pipeline principal. Extrae y consolida:

- **NetSuite / Oracle**: control de ventas de autos (`CUSTOMRECORD_ARI_CARSALES`), MVA, pagos de clientes, LSG, Vendor Bill.
- **SQL Server (SICAF/Flota)**: localización y propiedad de la flota, último check-in de RAC.
- **SQL Server (Infor)**: activos fijos / depreciación.
- **Google Sheets**: Tesorería (prioridad de pago semanal), Compras Ariete/Driven, Avance de Entregas.

Y carga el resultado en SQL Server (base `CGestion`, esquema `MesaControl`), en las tablas:

| Tabla | Contenido |
|---|---|
| `MesaControl.ControlVta` | Tabla principal: una fila por venta (`IdSalesCar`) con fechas, estatus, cliente, facturación, pagos, etc. |
| `MesaControl.FechasFacturas` | Fecha de facturación/propiedad "votada" entre varias fuentes, por número de serie. |
| `MesaControl.LastIncome` | Último ingreso del vehículo (RAC o LSG) por número de serie. |
| `MesaControl.Payments` | Resumen de pagos por documento de venta. |

**Importante**: cada corrida **borra y recarga por completo** estas tablas (`deleteAllRecords=True`), no es incremental.

### 2. `mainOthers.py` — Mesa_Control_StatusOrdenes_ETL

Pipeline independiente que extrae el historial de cambios (`SystemNote`) de NetSuite para ciertos campos de validación (MVA validado, propiedad, estatus fiscal del cliente, carta de aceptación) y lo carga en `MesaControl.SubEtapasSeminuevos`.

Ambos pipelines registran su resultado (éxito/falla, duración, error) en la tabla `dbo.ETL_Process_Log`.

## Estructura del proyecto

```
MesaControl/
├── main.py                  # Pipeline principal (Mesa_Control_Vtas_ETL)
├── mainOthers.py             # Pipeline de sub-etapas (Mesa_Control_StatusOrdenes_ETL)
├── data_sources.py           # Conexiones (SQL Server, Oracle/NetSuite, Google Sheets) y helpers de extracción/carga
├── data_processing.py        # Funciones de limpieza y transformación de datos
├── config.py                 # Carga de configuración/credenciales desde .env
├── Notas.md                  # Notas personales del autor del proyecto (se versiona en git)
├── requirements.txt          # Dependencias de Python
├── .env.example               # Plantilla de variables de entorno (copiar como .env)
├── .env                        # Variables de entorno reales (NO se sube a git)
├── credentials_example/       # Plantillas de los JSON de credenciales de Google
├── credentials/                # JSON de credenciales reales de Google (NO se sube a git)
├── Pruebas/                    # Scripts de prueba / prototipos no usados en producción
└── venv/                        # Entorno virtual de Python (NO se sube a git)
```

## Requisitos previos

- Python 3.10+ (el proyecto se desarrolló y probó con 3.10.11).
- Acceso de red a los servidores: SQL Server de `CGestion`, SICAF/Flota, Infor, y a NetSuite.
- Drivers ODBC instalados en el sistema operativo (no se instalan con `pip`):
  - **SQL Server Native Client 11.0**
  - **NetSuite Drivers 64bit**
- Una cuenta de servicio de Google con acceso a los Google Sheets usados (Tesorería, Compras, Entregas).

## Instalación

```bash
# Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

1. Copia `.env.example` como `.env` y llena los valores reales (credenciales de SQL Server, Oracle/NetSuite, rutas, etc.). Pide las credenciales al responsable del proyecto.
2. Copia `credentials_example/` como `credentials/` y reemplaza los archivos `*.example.json` por los JSON reales de la cuenta de servicio de Google (ver `credentials_example/README.md` para el detalle de cada archivo).

## Ejecución

Con el entorno virtual activado:

```bash
python main.py
python mainOthers.py
```

### Automatización con Tareas Programadas de Windows

La idea es simple: tener las librerías instaladas (`pip install -r requirements.txt`) y crear un `.bat` como este, apuntando a la ruta real del proyecto en esa PC:

```bat
cd C:\Users\Luis.Meza\Desktop\Python Projects\MesaControl
python main.py
python mainOthers.py
```

Ese `.bat` es lo que se programa en el **Programador de tareas de Windows** (Task Scheduler) para que el ETL corra solo, en el horario que se defina.

## Carpeta `Pruebas/`

Contiene scripts que no forman parte del flujo productivo (prototipos, pruebas de concepto). Ver `Pruebas/README.md` para el detalle de cada uno.

## Seguridad

- `.env` y `credentials/` contienen secretos reales y **nunca deben subirse a git** (ver `.gitignore`).
- Si alguna de estas credenciales fue compartida o expuesta accidentalmente (por ejemplo, en una conversación, captura de pantalla o log), rota/regenera esa credencial antes de continuar usándola.
