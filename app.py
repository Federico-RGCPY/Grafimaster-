import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
import urllib.parse
import re
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Grafimaster — Control Bancario & Facturación (CLP)",
    page_icon="💼",
    layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    .stApp { background-color: #f8fafc; }
    .header-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    .header-title {
        font-family: 'Montserrat', sans-serif;
        font-size: 2.8rem;
        font-weight: 800;
        letter-spacing: 2px;
        margin: 0;
        color: #ffffff;
    }
    .header-sub {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 5px;
    }
    .recibo-box {
        background-color: #ffffff;
        border: 2px dashed #22c55e;
        border-radius: 12px;
        padding: 20px;
        margin-top: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(34, 197, 94, 0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class='header-box'>
        <div class='header-title'>GRAFIMASTER</div>
        <div class='header-sub'>Control Financiero, Movimientos Bancarios y Facturación (Pesos Chilenos - CLP $)</div>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# 2. RESOLUCIÓN DE HOJA Y CREDENCIALES GOOGLE SHEETS
# -----------------------------------------------------------------------------
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def obtener_spreadsheet_id():
    if "spreadsheet" in st.secrets:
        sec = st.secrets["spreadsheet"]
        if "spreadsheet_id" in sec:
            return str(sec["spreadsheet_id"]).strip()
        if "spreadsheet_name" in sec:
            val = str(sec["spreadsheet_name"]).strip()
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", val)
            if match:
                return match.group(1)
            return val
    return "1Sly0ibsn65FV-6iDM4OptFAbm15GHHWBzA1fd8R7q-U"

SPREADSHEET_ID = obtener_spreadsheet_id()

def conectar_sheet():
    creds_dict = None
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
    elif "gcp_json" in st.secrets:
        raw_val = str(st.secrets["gcp_json"]).strip()
        try:
            creds_dict = json.loads(raw_val, strict=False)
        except Exception:
            try:
                clean_json = raw_val.strip("'''").strip('"""').strip()
                creds_dict = json.loads(clean_json, strict=False)
            except Exception as e:
                return None, f"Error al parsear gcp_json: {e}"

    if not creds_dict:
        return None, "No se encontraron credenciales en Secrets ([gcp_service_account] o gcp_json)."

    try:
        pk = creds_dict.get("private_key", "")
        if "\\n" in pk:
            creds_dict["private_key"] = pk.replace("\\n", "\n")

        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(SPREADSHEET_ID)
        return sh, None
    except Exception as e:
        return None, str(e)

def obtener_o_crear_pestana(sh, nombre_pestana, encabezados_default):
    try:
        return sh.worksheet(nombre_pestana)
    except Exception:
        for ws in sh.worksheets():
            if ws.title.strip().lower() == nombre_pestana.strip().lower():
                return ws
        ws = sh.add_worksheet(title=nombre_pestana, rows="100", cols="20")
        ws.append_row(encabezados_default, value_input_option="USER_ENTERED")
        return ws

def limpiar_key(texto):
    replacements = (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"))
    s = str(texto).lower().strip()
    for a, b in replacements:
        s = s.replace(a, b)
    return s

def obtener_datos(pestana_nombre, encabezados_default):
    sh, err = conectar_sheet()
    if sh:
        try:
            ws = obtener_o_crear_pestana(sh, pestana_nombre, encabezados_default)
            vals = ws.get_all_values()
            if len(vals) >= 1:
                headers_raw = [str(h).strip() for h in vals[0]]
                data = vals[1:]
                rows_clean = []
                for idx, r in enumerate(data):
                    if not any(r):
                        continue
                    row_dict = {}
                    for c_idx, val in enumerate(r):
                        row_dict[f"col_{c_idx}"] = val
                        if c_idx < len(headers_raw):
                            clean_k = limpiar_key(headers_raw[c_idx])
                            row_dict[clean_k] = val
                            row_dict[headers_raw[c_idx]] = val
                    row_dict["_fila_num"] = idx + 2
                    rows_clean.append(row_dict)
                return pd.DataFrame(rows_clean)
        except Exception:
            pass
    return pd.DataFrame()

def agregar_fila(pestana_nombre, fila_datos, encabezados_default):
    sh, err = conectar_sheet()
    if sh:
        try:
            ws = obtener_o_crear_pestana(sh, pestana_nombre, encabezados_default)
            ws.append_row([str(x) for x in fila_datos], value_input_option="USER_ENTERED")
            return True, None
        except Exception as e:
            return False, str(e)
    return False, f"Sin conexión: {err}"

def actualizar_fila(pestana_nombre, fila_num, datos_actualizados, encabezados_default):
    sh, err = conectar_sheet()
    if sh:
        try:
            ws = obtener_o_crear_pestana(sh, pestana_nombre, encabezados_default)
            num_cols = len(datos_actualizados)
            col_letra = chr(64 + num_cols) if num_cols <= 26 else "H"
            rango = f"A{fila_num}:{col_letra}{fila_num}"
            ws.update(rango, [[str(x) for x in datos_actualizados]], value_input_option="USER_ENTERED")
            return True, None
        except Exception as e:
            return False, str(e)
    return False, f"Sin conexión: {err}"

def eliminar_fila(pestana_nombre, fila_num, encabezados_default):
    sh, err = conectar_sheet()
    if sh:
        try:
            ws = obtener_o_crear_pestana(sh, pestana_nombre, encabezados_default)
            ws.delete_rows(int(fila_num))
            return True, None
        except Exception as e:
            return False, str(e)
    return False, f"Sin conexión: {err}"

HEADERS_FACTURAS = ["Nº_Factura", "Cliente", "Monto_CLP", "Fecha_Emision", "Estado", "Monto_Pagado", "Saldo_Pendiente", "Estado_Timbrado"]
HEADERS_MOVIMIENTOS = ["ID_Movimiento", "Banco", "Tipo", "Monto_CLP", "Fecha", "Cliente_Asociado", "Detalle"]
HEADERS_CONFIG = ["Banco", "Saldo_Inicial_CLP"]

# -----------------------------------------------------------------------------
# 3. VERIFICACIÓN DE CONEXIÓN
# -----------------------------------------------------------------------------
sh_test, err_test = conectar_sheet()
if not sh_test:
    st.error(f"⚠️ **Error de conexión con Google Sheets:** `{err_test}`")
    st.info(f"ID de hoja en uso: `{SPREADSHEET_ID}`. Asegúrate de haber compartido la hoja como 'Editor' con tu Service Account.")
