import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y PREVENCIÓN DE ERRORES DE TRADUCCIÓN DEL NAVEGADOR
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Facturación - Banco Itaú",
    page_icon="🏦",
    layout="wide"
)

# Evita que traductores automáticos del navegador rompan la interfaz de Streamlit (error removeChild)
st.markdown(
    """
    <html lang="es">
    <head>
        <meta name="google" content="notranslate">
    </head>
    </html>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# 2. CONTROL DE ACCESO POR CONTRASEÑA
# -----------------------------------------------------------------------------
PASSWORD_CORRECTA = "Mafe2026"

def verificar_contrasena():
    """Retorna True si el usuario ya inició sesión correctamente."""
    if st.session_state.get("autenticado", False):
        return True

    st.markdown(
        """
        <div style="max-width: 420px; margin: 40px auto 20px auto; text-align: center;">
            <h2>🔐 Acceso Restringido</h2>
            <p style="color: #64748b;">Ingresa la contraseña para acceder al sistema.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_izq, col_centro, col_der = st.columns([1, 1.2, 1])
    with col_centro:
        with st.form("form_login"):
            clave_ingresada = st.text_input("Contraseña:", type="password", placeholder="Ingresa tu clave...")
            btn_entrar = st.form_submit_button("Ingresar al Sistema", use_container_width=True)

            if btn_entrar:
                if clave_ingresada == PASSWORD_CORRECTA:
                    st.session_state["autenticado"] = True
                    st.success("Acceso concedido.")
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta. Inténtalo nuevamente.")

    return False

# Si no está autenticado, detiene la ejecución aquí
if not verificar_contrasena():
    st.stop()

# Botón para cerrar sesión en la barra lateral
with st.sidebar:
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()

# -----------------------------------------------------------------------------
# 3. CONEXIÓN DIRECTA NATIVA A GOOGLE SHEETS (GSPREAD)
# -----------------------------------------------------------------------------
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def obtener_cliente_gspread():
    """Autentica cargando credenciales directamente en JSON o diccionario sin errores de PEM."""
    if "gcp_json" in st.secrets:
        json_raw = st.secrets["gcp_json"]
        json_raw = json_raw.strip("'\"")
        creds_dict = json.loads(json_raw, strict=False)
    elif "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            pk = str(creds_dict["private_key"]).strip("'\"")
            pk = pk.replace("\\n", "\n").replace("\t", "").replace("\\t", "")
            creds_dict["private_key"] = pk
    else:
        raise ValueError("No se encontraron las credenciales de Google Cloud en los Secrets.")

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

SPREADSHEET_NAME = st.secrets["spreadsheet"]["spreadsheet_name"]

def obtener_hoja():
    """Abre el documento de Google Sheets por Nombre o por URL/ID."""
    gc = obtener_cliente_gspread()
    if SPREADSHEET_NAME.startswith("http"):
        return gc.open_by_url(SPREADSHEET_NAME)
    else:
        return gc.open(SPREADSHEET_NAME)

COLUMNAS_FACTURAS = [
    "ID", "Cliente", "Contador", "Trabajo", "Monto_PYG", 
    "Fecha", "Aplica_Timbrado", "Timbrado_Estado", "Estado", "Monto_Pagado"
]

COLUMNAS_BANCO = [
    "ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"
]

def normalizar_df(records, columnas_requeridas):
    """Convierte los registros de gspread en DataFrame seguro con todas sus columnas."""
    if not records:
        return pd.DataFrame(columns=columnas_requeridas)
    df = pd.DataFrame(records)
    for col in columnas_requeridas:
        if col not in df.columns:
            df[col] = ""
    return df[columnas_requeridas]

def cargar_datos():
    """Lee todas las pestañas de Google Sheets directamente con gspread."""
    try:
        sh = obtener_hoja()
        
        # Pestaña Facturas
        ws_f = sh.worksheet("Facturas")
        rec_f = ws_f.get_all_records()
        df_f = normalizar_df(rec_f, COLUMNAS_FACTURAS)

        # Pestaña Banco_Itau
        ws_b = sh.worksheet("Banco_Itau")
        rec_b = ws_b.get_all_records()
        df_b = normalizar_df(rec_b, COLUMNAS_BANCO)

        # Pestaña Configuracion
        ws_c = sh.worksheet("Configuracion")
        rec_c = ws_c.get_all_records()
        df_c = pd.DataFrame(rec_c)
        
        saldo_inicial = 0.0
        if not df_c.empty and "Clave" in df_c.columns and "Valor" in df_c.columns:
            config_dict = dict(zip(df_c["Clave"], df_c["Valor"]))
            try:
                saldo_inicial = float(config_dict.get("Saldo_Inicial", 0.0))
            except ValueError:
                saldo_inicial = 0.0

        # Parsear tipos de datos numéricos y fechas
        if not df_f.empty:
            df_f["Monto_PYG"] = pd.to_numeric(df_f["Monto_PYG"], errors='coerce').fillna(0.0)
            df_f["Monto_Pagado"] = pd.to_numeric(df_f["Monto_Pagado"], errors='coerce').fillna(0.0)
            df_f["Fecha"] = pd.to_datetime(df_f["Fecha"], errors='coerce').dt.date

        if not df_b.empty:
            df_b["Monto_PYG"] = pd.to_numeric(df_b["Monto_PYG"], errors='coerce').fillna(0.0)
            df_b["Fecha"] = pd.to_datetime(df_b["Fecha"], errors='coerce').dt.date

        st.session_state.facturas = df_f
        st.session_state.banco = df_b
        st.session_state.saldo_inicial = saldo_inicial

    except Exception as e:
        st.error(f"⚠️ Error conectando a Google
