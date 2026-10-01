# data_processing.py

import pandas as pd
import re
import numpy as np
import unicodedata
import datetime as dt
import traceback # Importar el módulo traceback

# Configuración de pandas para evitar notación científica
pd.set_option('display.float_format', lambda x: '%.3f' % x)

def clean_NoSerie(x):
    try:
        return re.sub(r'[^a-zA-Z0-9]', '', x)
    except:
        return x


def limpiar_columnas(df):
    """
    Limpia los nombres de las columnas de un DataFrame:
    - Convierte a minúsculas
    - Reemplaza símbolos por espacios
    - Elimina espacios extras
    - Elimina acentos
    """
    columnas_limpias = []
    for col in df.columns:
        # Convertir a minúsculas
        nueva_col = col.lower()

        # Eliminar acentos
        nueva_col = ''.join(
            c for c in unicodedata.normalize('NFD', nueva_col)
            if unicodedata.category(c) != 'Mn'
        )

        # Reemplazar cualquier símbolo o caracter no alfanumérico por espacio
        nueva_col = re.sub(r'[^a-z0-9]+', '', nueva_col)

        # Eliminar espacios al inicio/final y reemplazar espacios intermedios por "_"
        nueva_col = nueva_col.strip().replace(" ", "")

        columnas_limpias.append(nueva_col)

    # Asignar los nuevos nombres al DataFrame
    df.columns = columnas_limpias
    return df

def aggregate_payment_data(db_payment):
    """
    Agrupa los datos por 'previousdoc' y realiza agregaciones personalizadas.
    """
    if db_payment.empty:
        return pd.DataFrame()

        # 1. PREPARACIÓN Y LIMPIEZA DE TIPOS
    db_payment['trandate'] = pd.to_datetime(db_payment['trandate'], errors='coerce')

    # Definición de la función de concatenación
    def concatenate_tranids(series):
        """Concatena todos los valores de 'tranid' dentro del grupo, de forma inversa."""
        return ', '.join(series.astype(str).tolist()[::-1])

    # 3. APLICACIÓN DEL GROUPBY OPTIMIZADO
    df_summary = db_payment.groupby('previousdoc').agg(
        # 1. Número de Registros Totales
        PagoRecords=('tranid', 'size'),
        # 2. Fecha Máxima
        Max_DatePago=('trandate', 'max'),
        # 3. Concatenación de todos los 'tranid'
        PagoDocs=('tranid', concatenate_tranids)
    ).reset_index()

    return df_summary


def preprocess_inventory_data(df):
    """
    Realiza el preprocesamiento y consolidación de datos de inventario por NoSerie.
    """
    if df.empty:
        return pd.DataFrame()

    df_processed = df.copy()

    # 0. Ordenar el DataFrame (CRÍTICO)
    # df_processed = df_processed.sort_values(by=["NoSerie", "Registro", "id"]).reset_index(drop=True)
    # La columna 'id' no está en tu DF original para Oracle. Asumo que el orden por Registro es suficiente.
    df_processed = df_processed.sort_values(by=["NoSerie", "Registro"]).reset_index(drop=True)

    df_processed['FechaPropiedad'] = pd.to_datetime(df_processed['FechaPropiedad'], errors='coerce')
    df_processed['IsActive'] = df_processed['isinactive'] == 'F'

    # 1. Realizar la agrupación y agregación
    df_summary = df_processed.groupby('NoSerie').agg(
        # Concatenar MVA (solo si existen múltiples valores diferentes)
        MVA=('Registro', lambda x: ', '.join(x.astype(str).unique().tolist()) if len(x.unique()) > 1 else x.iloc[0]),

        # MVA_Consolidado (Usando la columna 'MVA' del DF original de Oracle)
        MVA_Consolidado=(
        'MVA', lambda x: ', '.join(x.astype(str).unique().tolist()) if len(x.unique()) > 1 else x.iloc[0]),

        # Máxima Fecha de Propiedad (solo si isinactive == 'F')
        MaxMVAFacDate=('FechaPropiedad', lambda x: x[df_processed.loc[x.index, 'IsActive']].max()),

        # Contar MVA únicos por NoSerie
        CountUniques=('Registro', 'nunique'),

        # Contar el total de registros por NoSerie
        TotalRegistros=('Registro', 'count'),

    ).reset_index()

    return df_summary


# def votar_fechas(df):
#     """
#     Implementa la lógica de votación de fechas con prioridad.
#     """
#     if df.empty:
#         return df
#
#     cols = ['VendorBillFactDate', 'SheetTesorFactura', 'SheetContaFacDate', 'MVAFacDate', 'InforDate',
#             'LocaFechaPropiedad']
#     fuentes = ['VendorBill', 'Tesoreria', 'Conta', 'MVA', 'Infor', 'Loca']
#
#     # Asegurar formato datetime (solo una vez)
#     df[cols] = df[cols].apply(pd.to_datetime, errors='coerce')
#
#     # Crear matriz numpy para trabajar más rápido
#     arr = df[cols].to_numpy()
#
#     # Inicializar columnas de salida
#     fecha_final = np.full(len(df), pd.NaT, dtype=object)
#     fuente_final = np.full(len(df), None, dtype=object)
#
#     for i in range(len(arr)):
#         fila = arr[i, :]
#         # Filtrar valores no nulos y convertirlos a string para comparación de "fechas iguales"
#         no_nulos = fila[~pd.isna(fila)]
#
#         if len(no_nulos) == 0:
#             continue
#
#         # Convertir a timestamp para una comparación uniforme
#         # unique, counts = np.unique([pd.to_datetime(d).timestamp() for d in no_nulos], return_counts=True)
#
#         # Usar la función de unique de numpy para los objetos datetime
#         unique, counts = np.unique(no_nulos, return_counts=True)
#         idx_max = np.argmax(counts)
#
#         if counts[idx_max] > 1:
#             # Caso: votación
#             fecha_final[i] = unique[idx_max]
#             fuente_final[i] = "Votacion"
#         else:
#             # Caso: prioridad (se toma el primer valor no nulo según el orden de 'cols')
#             for col_idx, valor in enumerate(fila):
#                 if pd.notna(valor):
#                     fecha_final[i] = valor
#                     fuente_final[i] = fuentes[col_idx]
#                     break
#
#     df = df.copy()
#     df["FechaFacturaPropiedad"] = fecha_final
#     df["FuenteFecha"] = fuente_final
#     return df


def votar_fechas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Implementa la lógica de votación de fechas con prioridad,
    concatenando las fuentes en caso de votación.
    """
    if df.empty:
        return df

    cols = ['VendorBillFactDate', 'SheetTesorFactura', 'SheetContaFacDate', 'MVAFacDate', 'InforDate',
            'LocaFechaPropiedad']
    fuentes = ['VendorBill', 'Tesoreria', 'Conta', 'MVA', 'Infor', 'Loca']


    df['LocaFechaPropiedad'] = pd.NaT


    # 1. Asegurar formato datetime (solo una vez)
    # pd.to_datetime en toda la columna es más eficiente que apply
    for col in cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    # Crear matriz numpy para trabajar más rápido
    # Es crucial usar 'datetime64[ns]' para que np.unique funcione correctamente con fechas
    arr = df[cols].to_numpy(dtype='datetime64[ns]')

    # Inicializar columnas de salida
    fecha_final = np.full(len(df), pd.NaT, dtype=object)
    fuente_final = np.full(len(df), None, dtype=object)

    for i in range(len(arr)):
        fila = arr[i, :]
        # Filtrar valores no nulos
        not_null_mask = ~pd.isna(fila)
        no_nulos = fila[not_null_mask]

        if len(no_nulos) == 0:
            continue

        # 2. Encontrar la fecha más frecuente
        unique, counts = np.unique(no_nulos, return_counts=True)
        idx_max = np.argmax(counts)
        fecha_ganadora = unique[idx_max]

        if counts[idx_max] > 1:
            # Caso: votación
            fecha_final[i] = fecha_ganadora

            # **MODIFICACIÓN CLAVE AQUÍ**
            # Identificar las fuentes que tienen la fecha ganadora en esta fila
            # 1. Crear una máscara booleana para encontrar dónde en la fila (incluyendo nulos)
            #    está la fecha_ganadora. Usamos pd.to_datetime para manejar la comparación
            #    con el objeto datetime de fecha_ganadora.
            mask_voto = (fila == fecha_ganadora)

            # 2. Filtrar la lista de 'fuentes' usando esta máscara
            fuentes_votantes = [fuentes[j] for j, is_voter in enumerate(mask_voto) if is_voter]

            # 3. Concatenar los nombres de las fuentes
            fuente_final[i] = "Votacion (" + ",".join(fuentes_votantes) + ")"
        else:
            # Caso: prioridad (se toma el primer valor no nulo según el orden de 'cols')
            # La lógica de la prioridad se mantiene igual
            for col_idx, valor in enumerate(fila):
                if pd.notna(valor):
                    fecha_final[i] = valor
                    fuente_final[i] = fuentes[col_idx]
                    break

    df = df.copy()
    # Usar .dt.normalize() para asegurar que el tipo de datos sea consistente si es necesario,
    # aunque con numpy.datetime64[ns] ya debería ser estable.
    df["FechaFacturaPropiedad"] = pd.to_datetime(fecha_final, errors='coerce')
    df["FuenteFecha"] = fuente_final
    return df


def process_last_income(db_rac, db_lsg):
    """
    Consolida y obtiene el último registro de ingresos (RAC o LSG) por NoSerie.
    """
    if db_rac.empty and db_lsg.empty:
        return pd.DataFrame()

    # Preparación de RAC
    df_rac = db_rac[["NumEconomico", "NoSerie", "MaxCheckIn"]].rename(
        columns={"NumEconomico": "MVA", "MaxCheckIn": "MaxOnRent"})
    df_rac["TipoLast"] = "RAC"
    # Convertir a date para una comparación justa si las horas son inconsistentes
    df_rac["MaxOnRent"] = pd.to_datetime(df_rac['MaxOnRent'], errors='coerce').dt.date

    # Preparación de LSG
    df_lsg = db_lsg[["MVA", "NoSerie", "trandate", "UNegocio"]].rename(
        columns={"trandate": "MaxOnRent", "UNegocio": "TipoLast"})
    df_lsg["MaxOnRent"] = pd.to_datetime(df_lsg['MaxOnRent'], errors='coerce').dt.date

    # Concatenar y consolidar
    db_LastIncome = pd.concat([df_rac, df_lsg], axis=0)
    db_LastIncome = db_LastIncome.dropna(subset=['NoSerie', 'MaxOnRent'])

    if db_LastIncome.empty:
        return pd.DataFrame()

    db_LastIncome = db_LastIncome.sort_values(by=["NoSerie", "MaxOnRent"], ascending=[True, False]).reset_index(
        drop=True)
    db_LastIncome["Id"] = db_LastIncome.groupby("NoSerie").cumcount() + 1
    db_LastIncome = db_LastIncome.query("Id==1").drop(columns=["Id"])

    return db_LastIncome


def _intentar_crear_fecha(dia, mes, anio, fecha_original):
    """
    Intenta crear una fecha válida. Si el día es inválido (ej. 31 de febrero),
    retrocede días hasta encontrar uno válido.
    """
    current_day = dia
    for _ in range(32):
        try:
            # CAMBIO: dt.datetime
            return dt.datetime(anio, mes, current_day)
        except ValueError:
            current_day -= 1
            if current_day < 1:
                return pd.NaT
    return pd.NaT

def _determinar_fecha(fila):
    fecha_creacion = fila['Creado']
    mes_columna = fila['MesPromesa']
    agno_promesa = fila['AgnoPromesa']  # Asegúrate que tu columna se llame 'Agno'

    if pd.isna(mes_columna):
        return fecha_creacion

    mes_columna = int(mes_columna)
    dia_creacion = fecha_creacion.day

    if pd.notna(agno_promesa):
        # CAMBIO: dt.datetime e int()
        return dt.datetime(int(agno_promesa), mes_columna, 1)

    mes_creacion = fecha_creacion.month
    if mes_creacion == mes_columna:
        # CAMBIO: dt.datetime
        return dt.datetime(fecha_creacion.year, mes_columna, 1)

    anio_creacion = fecha_creacion.year
    anios_candidatos = [anio_creacion, anio_creacion - 1, anio_creacion + 1]
    distancias = []

    for anio in anios_candidatos:
        fecha_candidata = _intentar_crear_fecha(dia_creacion, mes_columna, anio, fecha_creacion)
        if pd.notna(fecha_candidata):
            distancias.append(abs((fecha_candidata - fecha_creacion).days))
        else:
            distancias.append(np.inf)

    if all(d == np.inf for d in distancias):
        return pd.NaT

    anio_mas_cercano = anios_candidatos[np.argmin(distancias)]

    # CAMBIO: dt.datetime
    return dt.datetime(anio_mas_cercano, mes_columna, 1)