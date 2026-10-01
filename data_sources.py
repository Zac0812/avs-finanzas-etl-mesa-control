# data_sources.py

import pandas as pd
import urllib
import sqlalchemy
import pyodbc
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Importar configuraciones
from config import (
    PATH_CREDS_DRIVE, SCOPES_SHEETS,
    SQL_USER_CGestion, SQL_PASS_CGestion, SQL_SERVER_CGestion, SQL_DB_CGestion,
    ORACLE_USER, ORACLE_PASS, ORACLE_HOST, ORACLE_PORT, ORACLE_ROLE_ID,
    SICAF_SERVER, SICAF_DB, INFOR_SERVER, INFOR_DB
    #,NETSUITE_DW_SERVER, NETSUITE_DW_DB
)



class ConnCGestion:
    """Clase para manejar la conexión y carga de datos a la base de datos CGestion (SQL Server)."""

    def __init__(self):
        # Crear la cadena de conexión de forma segura usando las credenciales de config.py
        conn_str = (
            f'Driver={{SQL Server Native Client 11.0}};'
            f'Server={SQL_SERVER_CGestion};'
            f'Database={SQL_DB_CGestion};'
            f'UID={SQL_USER_CGestion};'
            f'PWD={SQL_PASS_CGestion}'
        )
        self.params_cgestion = urllib.parse.quote_plus(conn_str)

    # def upload_DF_SQL(self, df, name_schema, name_DB, action="append", deleteAllRecords=False):
    #     """Sube un DataFrame a SQL Server."""
    #     engine = None
    #     conn = None
    #     try:
    #         # Crear engine de SQLAlchemy
    #         engine = sqlalchemy.create_engine("mssql+pyodbc:///?odbc_connect={}".format(self.params_cgestion))
    #         conn = engine.connect()
    #
    #         # 1. Eliminar registros si es necesario
    #         if deleteAllRecords:
    #             t_sql = sqlalchemy.text(f"delete from {name_schema}.{name_DB}")
    #             conn.execute(t_sql)  # Uso directo de conn.execute() para comandos DML con SQLAlchemy 2.0 style
    #             conn.commit()  # Asegurarse de que el DELETE se ejecute
    #
    #         # 2. Subir DataFrame
    #         df.to_sql(name=name_DB, con=conn, schema=name_schema, if_exists=action, index=False)
    #
    #     except Exception as e:
    #         return False, e
    #     else:
    #         return True, "Successful upload DB"
    #     finally:
    #         if conn is not None:
    #             conn.close()
    #         if engine is not None:
    #             engine.dispose()


    # def upload_DF_SQL(self, df, name_schema, name_DB, action="append", deleteAllRecords=False):
    #     """Sube un DataFrame a SQL Server."""
    #     engine = None
    #     try:
    #         # Crear engine de SQLAlchemy
    #         engine = sqlalchemy.create_engine("mssql+pyodbc:///?odbc_connect={}".format(self.params_cgestion))
    #         # Iniciar la conexión y la transacción explícita usando 'with'
    #         with engine.connect() as conn:
    #             # 1. Eliminar registros si es necesario (Dentro de la transacción)
    #             if deleteAllRecords:
    #                 t_sql = sqlalchemy.text(f"delete from {name_schema}.{name_DB}")
    #                 conn.execute(t_sql)
    #                 # El commit manual ya no es necesario aquí, se hace al final del bloque 'with'
    #             # 2. Subir DataFrame
    #             # Nota: .to_sql abre su propia sub-transacción/conexión,
    #             # pero funciona bien con la conexión abierta por el 'with'.
    #             # Pasar la conexión abierta al to_sql
    #             df.to_sql(name=name_DB, con=conn, schema=name_schema, if_exists=action, index=False)
    #
    #             # Confirmar todos los cambios (DELETE y to_sql) al salir del bloque 'with'
    #             # Es necesario llamarlo explícitamente en el objeto Connection dentro del with
    #             conn.commit()
    #         # Si todo el bloque with se ejecuta sin errores, se confirma la transacción.
    #         return True, "Successful upload DB"
    #
    #     except Exception as e:
    #         # Si algo falla, el rollback se gestiona automáticamente al salir de 'with'
    #         # (aunque es buena práctica asegurar que el rollback se maneje si el error ocurre antes del conn.commit()).
    #         return False, f"Error en la carga: {e}"
    #     finally:
    #         if engine is not None:
    #             engine.dispose()

    def upload_DF_SQL(self, df, name_schema, name_DB, action="append", deleteAllRecords=False):
        """
        Sube un DataFrame a SQL Server. El borrado (DELETE) y la carga (to_sql) se
        manejan en conexiones separadas para evitar errores de compatibilidad
        con la versión de Pandas/SQLAlchemy (AttributeError: 'Connection' object has no attribute 'connect').
        """
        engine = None

        try:
            # 1. Crear engine de SQLAlchemy
            engine = sqlalchemy.create_engine("mssql+pyodbc:///?odbc_connect={}".format(self.params_cgestion))

            # --- 2. GESTIÓN DEL BORRADO (DELETE) ---
            if deleteAllRecords:
                print(f"Eliminando registros existentes en {name_schema}.{name_DB}...")

                # Usar una conexión temporal para la operación de DELETE (Transaction #1)
                with engine.connect() as conn_delete:
                    # Iniciar transacción para asegurar el commit
                    with conn_delete.begin():
                        t_sql = sqlalchemy.text(f"DELETE FROM {name_schema}.{name_DB}")
                        conn_delete.execute(t_sql)
                # La conexión 'conn_delete' se cierra y se confirma (COMMIT) automáticamente.

            # --- 3. SUBIR DATAFRAME (to_sql) ---
            print("Cargando nuevos datos (usando Engine)...")

            # ¡SOLUCIÓN! Pasar el objeto 'engine' directamente al to_sql.
            # Esto fuerza a Pandas a manejar la conexión y la inserción internamente,
            # lo cual evita el error de atributo que estás experimentando.
            df.to_sql(name=name_DB,
                      con=engine,  # <-- ¡CLAVE! Usar el ENGINE
                      schema=name_schema,
                      if_exists=action,
                      index=False)

            return True, "Successful upload DB"

        except Exception as e:
            # Capturamos cualquier error de la DB, conexión o Pandas.
            print(f"Error fatal en upload_DF_SQL: {e}")
            return False, str(e)  # Devolvemos la cadena de error

        finally:
            # 4. Liberar recursos
            if engine is not None:
                engine.dispose()


class GoogleSheetFetcher:
    """Clase para obtener datos de Google Sheets."""

    def __init__(self):
        # La conexión se establece en el método get_sheet_df para manejar el scope específico
        pass

    def get_sheet_df(self, id_spread_sheet, rangeSheet):
        """
        Obtiene un DataFrame de una Google Sheet.
        :param id_spread_sheet: spreadsheet id
        :param rangeSheet: range format A1
        :return: a dataframe without transformation (all columns are strings)
        """
        try:
            # Conexión con service_account
            credentials = service_account.Credentials.from_service_account_file(PATH_CREDS_DRIVE)
            scoped_credentials = credentials.with_scopes(SCOPES_SHEETS)
            service = build('sheets', 'v4', credentials=scoped_credentials)

            result = service.spreadsheets().values().get(spreadsheetId=id_spread_sheet, range=rangeSheet).execute()

            # Obtener dataframe
            if not result.get('values'):
                return pd.DataFrame()  # Retornar DF vacío si no hay datos

            cols = result["values"][0]
            df = pd.DataFrame(result['values'], columns=cols).drop(0).reset_index(drop=True)
            return df

        except Exception as e:
            print(f"Error al obtener datos de Google Sheets: {e}")
            return pd.DataFrame()


# --- FUNCIONES DE CONEXIÓN SQL SERVER (Trusted) ---

def get_sql_conn_trusted(server, database):
    """Retorna una conexión pyodbc con Trusted_Connection=yes."""
    try:
        conn = pyodbc.connect(
            f'Driver={{SQL Server Native Client 11.0}};'
            f'Server={server};'
            f'Database={database};'
            f'Trusted_Connection=yes;'
        )
        return conn
    except Exception as e:
        print(f"Error al conectar con SQL Server ({server}/{database}): {e}")
        return None

def fetch_data_from_sql_trusted(server, database, t_sql):
    """Ejecuta una consulta SQL con Trusted Connection y retorna un DataFrame."""
    conn = get_sql_conn_trusted(server, database)
    if conn is None:
        return pd.DataFrame()

    try:
        df = pd.read_sql(sql=t_sql, con=conn)
        return df
    except Exception as e:
        print(f"Error al ejecutar consulta SQL: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()


# --- FUNCIONES DE CONEXIÓN ORACLE (NetSuite) ---

def get_oracle_conn():
    """Retorna una conexión pyodbc a Oracle/NetSuite."""
    try:
        conn = pyodbc.connect(
            'DRIVER=NetSuite Drivers 64bit;'
            f'Host={ORACLE_HOST};'
            f'Port={ORACLE_PORT};'
            'Encrypted=1;'
            'ServerDataSource=NetSuite2.com;'
            'Truststore=system;'
            f'LogonId={ORACLE_USER};'
            f'Password={ORACLE_PASS};'
            'AllowSinglePacketLogout=1;'
            'CustomProperties=AccountID=7029150;'
            f'RoleID={ORACLE_ROLE_ID}'
        )
        return conn
    except Exception as e:
        print(f"Error al conectar con Oracle/NetSuite: {e}")
        return None


def fetch_data_from_oracle(t_sql):
    """Ejecuta una consulta Oracle y retorna un DataFrame."""
    conn = get_oracle_conn()
    if conn is None:
        return pd.DataFrame()

    try:
        df = pd.read_sql(sql=t_sql, con=conn)
        return df
    except Exception as e:
        print(f"Error al ejecutar consulta Oracle: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()