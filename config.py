import os
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# --- Google Sheets/Drive ---
PATH_CREDS_DRIVE = os.getenv("PATH_CREDS_DRIVE")
SCOPES_DRIVE = ['https://www.googleapis.com/auth/drive.metadata.readonly']
FOLDER_ID = '1fLij4NfncnEcfTL3pGysTgstRlHIcgrL' # ID de la carpeta
SCOPES_SHEETS = ['https://www.googleapis.com/auth/spreadsheets']

# --- Conexión SQL CGestion (Destino) ---
SQL_USER_CGestion = os.getenv("SQL_USER_CGestion")
SQL_PASS_CGestion = os.getenv("SQL_PASS_CGestion")
SQL_SERVER_CGestion = os.getenv("SQL_SERVER_CGestion")
SQL_DB_CGestion = os.getenv("SQL_DB_CGestion")

# --- Conexión Oracle (NetSuite) ---
ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASS = os.getenv("ORACLE_PASS")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_ROLE_ID = os.getenv("ORACLE_ROLE_ID")

# --- Conexión SQL Trusted (SICA/Flota e Infor) ---
SICAF_SERVER = os.getenv("SICAF_SERVER")
SICAF_DB = os.getenv("SICAF_DB")
INFOR_SERVER = os.getenv("INFOR_SERVER")
INFOR_DB = os.getenv("INFOR_DB")

