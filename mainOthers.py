import pandas as pd
import datetime as dt
import traceback  # Importar el módulo traceback
import numpy as np

# Importar módulos personalizados

from data_sources import (
    ConnCGestion,  # classes
    fetch_data_from_oracle, fetch_data_from_sql_trusted  # functions
)

# --- Consultas SQL ---

SQL_NOTAS_MVA = """
select v.id IdSalesCar,s.id,s.date,s.field,s.newvalue,s.recordid
from SystemNote s
join CUSTOMRECORD_ARI_CARSALES v on s.recordid=v.custrecord_ari_carsales_mva
join customrecord_ari_mva_ariete m on s.recordid=m.id
where s.field='CUSTRECORD_ARI_MVA_VALIDADO'
"""
SQL_NOTAS_PROPIEDAD = """
select v.id IdSalesCar,s.id,s.date,s.field,s.newvalue,s.recordid
--select s.id,s.date,s.field,s.newvalue,s.record,s.recordid,s.recordtypeid,m.custrecord_ari_numerodeserie NoSerie
from SystemNote s
join CUSTOMRECORD_ARI_CARSALES v on s.recordid=v.custrecord_ari_carsales_mva
join customrecord_ari_mva_ariete m on s.recordid=m.id
where s.field='CUSTRECORD_ARI_MVA_PROPERTY_OWNER' 
"""
SQL_NOTAS_CLIENTE = """
select v.id IdSalesCar,s.id,s.date,s.field,s.newvalue,s.recordid
--select s.id,s.date,s.field,s.newvalue,s.record,s.recordid,s.recordtypeid,c.altname Cliente,c.custentity_ari_fiscal FiscalStatusActual,c.custentity_ari_fiscal_comment FiscalComentario
from SystemNote s
join CUSTOMRECORD_ARI_CARSALES v on s.recordid=v.custrecord_ari_carsales_customer
join Customer c on s.recordid=c.id
where  s.field='CUSTENTITY_ARI_FISCAL'
"""

SQL_NOTAS_CARTA = """
select v.id IdSalesCar,s.id,s.date,s.field,s.newvalue,s.recordid
from SystemNote s
join CUSTOMRECORD_ARI_CARSALES v on s.recordid=v.id
where  s.field='CUSTRECORD_ARI_CARSALES_CARTAACEPTACION'
--AND s.recordid=99102     
"""


def extract_data():
    """Extrae datos de todas las fuentes."""
    print("Iniciando extracción de datos...")

    print("Oracle Source")
    # 5. NetSuite (Oracle)
    print("Validación MVA")
    db_notas_MVA = fetch_data_from_oracle(SQL_NOTAS_MVA)
    print("Validación propiedad")
    db_notas_Propiedad = fetch_data_from_oracle(SQL_NOTAS_PROPIEDAD)
    print("Validación Cliente")
    db_notas_Cliente = fetch_data_from_oracle(SQL_NOTAS_CLIENTE)
    print("Carta de Aceptación")
    db_notas_Carta = fetch_data_from_oracle(SQL_NOTAS_CARTA)

    return {"db_notas_MVA": db_notas_MVA,
            "db_notas_Propiedad": db_notas_Propiedad,
            "db_notas_Cliente": db_notas_Cliente,
            "db_notas_Carta": db_notas_Carta
            }


def transform_data(data):
    db_notas_MVA = data["db_notas_MVA"].copy()
    db_notas_Propiedad = data["db_notas_Propiedad"].copy()
    db_notas_Cliente = data["db_notas_Cliente"].copy()
    db_notas_Carta = data["db_notas_Carta"].copy()

    # Notas.md de Propiedad
    # Verificamos si el 'newvalue' contiene 'Ariete' O 'Driven' (ignorar mayúsculas/minúsculas).
    db_notas_Propiedad['newvalue'] = db_notas_Propiedad['newvalue'].str.contains('Ariete|Driven', case=False, na=False)
    # Asignamos las cadenas de texto T or F dependiendo del valor True/False del paso anteriore
    db_notas_Propiedad['newvalue'] = np.where(db_notas_Propiedad['newvalue'],
                                              # Sub-condición: ¿Contiene "Ariete" o "Driven"?
                                              'T',  # SI: Asignar 'T' (True)
                                              'F')  # NO: Asignar 'F' (False)
    # Notas.md de la Carta de Aceptación
    db_notas_Carta['newvalue'] = (db_notas_Carta['newvalue'].str.contains("http", na=False)) & (
            db_notas_Carta['newvalue'].str.len() > 2)
    # Asignamos las cadenas de texto T or F dependiendo del valor True/False del paso anteriore
    db_notas_Carta['newvalue'] = np.where(db_notas_Carta['newvalue'],  # Sub-condición: ¿Contiene "Ariete" o "Driven"?
                                          'T',  # SI: Asignar 'T' (True)
                                          'F')  # NO: Asignar 'F' (False)

    # joins all notes
    db_notes = pd.concat([db_notas_MVA, db_notas_Propiedad, db_notas_Cliente, db_notas_Carta], axis=0)
    # Ordenar el DataFrame por 'id' de forma descendente.
    # Esto asegura que el registro MÁS NUEVO (ID más alto) esté en la parte superior de cada grupo.
    db_notes = db_notes.sort_values(by='id', ascending=False)
    # Eliminar duplicados basándose en 'recordid' y 'field'. Al usar keep='first', Pandas mantiene el primer registro encontrado para esa combinación
    db_notes = db_notes.drop_duplicates(subset=['recordid', 'field'], keep='first')

    dic_field = {"CUSTRECORD_ARI_MVA_VALIDADO": 1,
                 "CUSTRECORD_ARI_MVA_PROPERTY_OWNER": 2,
                 "CUSTENTITY_ARI_FISCAL": 3,
                 "CUSTRECORD_ARI_CARSALES_CARTAACEPTACION": 4}
    db_notes["field"] = db_notes["field"].map(dic_field)

    return db_notes


def load_data(df_final, name_schema, name_DB):
    """Carga el DataFrame final a la base de datos de destino."""
    print("Iniciando carga de datos...")
    if df_final.empty:
        print("El DataFrame final está vacío. No se realiza la carga.")
        return False, "DataFrame vacío."

    cgestion = ConnCGestion()
    result_upload, msg_upload = cgestion.upload_DF_SQL(
        df=df_final,
        name_schema=name_schema,
        name_DB=name_DB,
        action="append",
        deleteAllRecords=True
    )
    print(f"Resultado de la carga: {msg_upload}")
    return result_upload, msg_upload


def insert_final_log(pipeline_name, start_time, end_time, status, error_info):
    """
        Inserta un único registro de log con el resultado final del proceso.
        """
    cgestion = ConnCGestion()
    duration = (end_time - start_time).total_seconds()

    # Limitar el mensaje de error para evitar exceder límites si es necesario
    error_message_text = str(error_info)[:8000] if error_info else None

    # Crear el DataFrame para la inserción final
    df_log = pd.DataFrame({
        'PipelineName': [pipeline_name],
        'ExecutionStartDT': [start_time.strftime('%Y-%m-%d %H:%M:%S')],
        'ExecutionEndDT': [end_time.strftime('%Y-%m-%d %H:%M:%S')],
        'Status': [status],
        'DurationSeconds': [round(duration, 2)],
        'ErrorMessage': [error_message_text]
    })
    # Usar upload_DF_SQL para APPEND simple
    result, msg = cgestion.upload_DF_SQL(
        df=df_log, name_schema="dbo",  # Esquema de tu tabla de logs
        name_DB="ETL_Process_Log", action="append",  # Siempre 'append' para logs
        deleteAllRecords=False)
    if result:
        print(f"✅ Log final de '{status}' insertado con éxito en ETL_Process_Log.")
    else:
        print(f"❌ ERROR CRÍTICO: Falló la inserción del log final. Mensaje: {msg}")


def main():
    """Función principal para orquestar la extracción, transformación y carga (ETL)."""
    print("Iniciando proceso ETL...")
    PIPELINE_NAME = "Mesa_Control_StatusOrdenes_ETL"
    start_time = dt.datetime.now()
    status = 'SUCCESS'
    error_info = None
    try:
        # 1. Extracción
        raw_data = extract_data()
        # 2. Transformación
        db_notes = transform_data(raw_data)
        # 3. Carga
        load_data(df_final=db_notes, name_schema="MesaControl", name_DB="SubEtapasSeminuevos")
        # db_notes.to_excel("C:/Users/luis.meza/Desktop/Notas.xlsx", index=False)

        print("Proceso ETL finalizado exitosamente. 🎉")

    except Exception as e:
        status = 'FAILED'
        # Esto imprimirá el error completo, incluyendo el módulo y la línea
        print("\n" + "=" * 50)
        print("🚨 OCURRIÓ UN ERROR CRÍTICO EN EL PROCESO ETL 🚨")
        print("=" * 50)
        # Aquí usamos traceback.format_exc() para obtener el error completo como un string
        error_info = traceback.format_exc()
        print(error_info)
        # Opcional: imprimir el mensaje de error simple
        print(f"Mensaje del error: {e}")
        print("=" * 50)
    finally:
        end_time = dt.datetime.now()
        duration = (end_time - start_time).total_seconds()
        insert_final_log(PIPELINE_NAME, start_time, end_time, status, error_info)
        if status == 'SUCCESS':
            print("Proceso ETL de datos finalizado exitosamente. 🎉")
        else:
            print("Proceso ETL de datos terminado con FALLA. ❌")


if __name__ == "__main__":
    main()
