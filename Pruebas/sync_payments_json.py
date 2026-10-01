#NO SE HA USADO PERO EN .ENV, Congif & DATASOURCES SE ANEXARON LAS NUEVAS CREDENCIALES & CONN PARA DW

import pandas as pd
import sqlalchemy
import json
from datetime import datetime, timedelta
from config import SQL_DB_CGestion
from data_sources import fetch_data_from_oracle, ConnCGestion


def aggregate_payment_data_json(df):
    """Groups the data and creates a JSON array of Payment IDs."""
    if df.empty:
        return pd.DataFrame()
    df['trandate'] = pd.to_datetime(df['trandate'], errors='coerce')

    def create_json_array(series):
        list_ids = series.astype(str).unique().tolist()
        return json.dumps(list_ids[::-1])

    df_summary = df.groupby('previousdoc').agg(
        PagoRecords=('tranid', 'size'),
        Max_DatePago=('trandate', 'max'),
        PagoDocs=('tranid', create_json_array)
    ).reset_index()
    return df_summary


def main():
    cgestion = ConnCGestion()
    engine_sql = sqlalchemy.create_engine(f"mssql+pyodbc:///?odbc_connect={cgestion.params_cgestion}")
    print(f"[{datetime.now()}] --- Starting Optimized Keyset Pipeline ---")

    CHUNK_SIZE = 50000
    current_max_id = 0  # We start looking for IDs greater than 0
    has_more_data = True
    global_max_modified = None
    try:
        # 1. Fetch Last Sync Timestamp
        with engine_sql.connect() as conn:
            res = conn.execute(sqlalchemy.text("SELECT MAX(LastSync) FROM MesaControl.SyncLog")).fetchone()
            last_sync_dt = res[0] if res[0] else datetime(2024, 1, 1)
        safe_sync_time = last_sync_dt - timedelta(minutes=1)
        last_sync_str = safe_sync_time.strftime('%Y-%m-%d %H:%M:%S')

        print(f"Filtering updates since: {last_sync_str}")

        # 2. Keyset Pagination Loop
        while has_more_data:
            print(f"---> Fetching next {CHUNK_SIZE:,} rows starting after NetSuite ID: {current_max_id}")

            # Keyset query utilizing primary keys for maximum speed
            ns_query = f"""
            SELECT nd.nextdoc, nd.previousdoc, t.id as payment_id, t.tranid, t.trandate, t.lastmodifieddate
            FROM NextTransactionLink nd
            JOIN transaction t ON t.id = nd.nextdoc
            WHERE nd.linktype = 'Payment'
              AND t.type IN ('CustPymt','CustCred','Journal')
              AND t.lastmodifieddate > TO_DATE('{last_sync_str}', 'YYYY-MM-DD HH24:MI:SS')
              AND t.id > {current_max_id}
            ORDER BY t.id ASC
            FETCH NEXT {CHUNK_SIZE} ROWS ONLY
            """

            df_raw = fetch_data_from_oracle(ns_query)

            if df_raw.empty:
                print("No more records remaining.")
                break

            # Capture the new boundary point for the next loop execution
            current_max_id = int(df_raw['payment_id'].max())

            # Log the high watermark date
            chunk_max_mod = df_raw['lastmodifieddate'].max()
            if global_max_modified is None or chunk_max_mod > global_max_modified:
                global_max_modified = chunk_max_mod

            print(f"Downloaded {len(df_raw):,} rows. Aggregating data...")

            # 3. Process Aggregation
            df_final = aggregate_payment_data_json(df_raw)

            # 4. Push Chunk to Staging Table
            success, msg = cgestion.upload_DF_SQL(
                df_final,
                name_schema="MesaControl",
                name_DB="Temp_Payments_Update",
                action="replace"
            )

            if not success:
                print(f"SQL staging upload failed: {msg}")
                return

            # 5. Execute Atomic UPSERT via MERGE
            with engine_sql.connect() as conn:
                with conn.begin():
                    merge_sql = """
                    MERGE MesaControl.Payments AS target
                    USING MesaControl.Temp_Payments_Update AS source
                    ON (target.previousdoc = source.previousdoc)
                    WHEN MATCHED THEN
                        UPDATE SET 
                            target.PagoRecords = source.PagoRecords,
                            target.Max_DatePago = source.Max_DatePago,
                            target.PagoDocs = source.PagoDocs
                    WHEN NOT MATCHED THEN
                        INSERT (previousdoc, PagoRecords, Max_DatePago, PagoDocs)
                        VALUES (source.previousdoc, source.PagoRecords, source.Max_DatePago, source.PagoDocs);
                    """
                    conn.execute(sqlalchemy.text(merge_sql))

            # Loop brake if the batch size drops below the threshold
            if len(df_raw) < CHUNK_SIZE:
                print("Final page processed successfully.")
                has_more_data = False

        # 6. Final High Watermark Logging
        if global_max_modified:
            with engine_sql.connect() as conn:
                with conn.begin():
                    conn.execute(sqlalchemy.text(
                        f"INSERT INTO MesaControl.SyncLog (LastSync) VALUES ('{global_max_modified}')"
                    ))

        print(f"\n[{datetime.now()}] --- Pipeline Completed Successfully ---")

    except Exception as e:
        print(f"Critical System Failure: {e}")
    finally:
        engine_sql.dispose()


if __name__ == "__main__":
    main()