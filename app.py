import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
import gspread
from google.oauth2.service_account import Credentials
import hmac

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
# CONTROL DE ACCESO / AUTENTICACIÓN (CONTRASEÑA: Mafe2026)
# -----------------------------------------------------------------------------
def verificar_autenticacion():
    """Valida la contraseña y bloquea el resto de la app hasta que sea correcta."""
    if st.session_state.get("autenticado", False):
        return True

    clave_correcta = "Mafe2026"

    col_izq, col_centro, col_der = st.columns([1, 1.2, 1])
    with col_centro:
        st.markdown(
            """
            <div style='background: #1e293b; color: white; padding: 25px; border-radius: 15px; text-align: center; margin-bottom: 20px;'>
                <h2 style='margin: 0; color: white;'>🔒 ACCESO RESTRINGIDO</h2>
                <p style='color: #94a3b8; margin: 8px 0 0 0;'>Sistema de Facturación - Banco Itaú</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.form("form_login"):
            password_ingresada = st.text_input("Contraseña de Acceso", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Ingresar al Sistema", use_container_width=True)

            if submit:
                if hmac.compare_digest(password_ingresada, clave_correcta):
                    st.session_state["autenticado"] = True
                    st.success("Acceso concedido.")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta. Intente nuevamente.")

    st.stop()

verificar_autenticacion()

with st.sidebar:
    st.caption("👤 Sesión iniciada")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()

# -----------------------------------------------------------------------------
# 2. CONEXIÓN DIRECTA NATIVA A GOOGLE SHEETS (GSPREAD)
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
        st.error(f"⚠️ Error conectando a Google Sheets: {e}")
        st.session_state.facturas = pd.DataFrame(columns=COLUMNAS_FACTURAS)
        st.session_state.banco = pd.DataFrame(columns=COLUMNAS_BANCO)
        st.session_state.saldo_inicial = 0.0

def guardar_tabla(df, worksheet_name):
    """Escribe los datos en Google Sheets limpiando y subiendo la tabla."""
    try:
        sh = obtener_hoja()
        ws = sh.worksheet(worksheet_name)
        
        df_save = df.copy()
        if "Fecha" in df_save.columns:
            df_save["Fecha"] = df_save["Fecha"].astype(str)
            
        df_save = df_save.fillna("")
        
        ws.clear()
        datos_completos = [df_save.columns.values.tolist()] + df_save.values.tolist()
        ws.update(datos_completos)
    except Exception as e:
        st.error(f"Error al guardar los datos en {worksheet_name}: {e}")

def formatear_pyg(monto):
    """Formatea valores numéricos a Guaraníes (₲ 1.000.000)."""
    try:
        return f"₲ {float(monto):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "₲ 0"

def formatear_fecha(fecha_obj):
    """Formatea objetos fecha a DD/MM/YYYY."""
    if pd.isna(fecha_obj) or fecha_obj is None or fecha_obj == "":
        return ""
    if isinstance(fecha_obj, str):
        try:
            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()
        except ValueError:
            return fecha_obj
    return fecha_obj.strftime("%d/%m/%Y")

def convertir_df_a_csv(df):
    """Convierte un dataframe a CSV descargable en UTF-8."""
    return df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

# Nombres de meses en español
NOMBRES_MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# -----------------------------------------------------------------------------
# 3. INICIALIZACIÓN
# -----------------------------------------------------------------------------
if 'cargado' not in st.session_state:
    cargar_datos()
    st.session_state.cargado = True

FECHA_ACTUAL = date.today()
MES_ACTUAL = FECHA_ACTUAL.month
ANIO_ACTUAL = FECHA_ACTUAL.year

st.title("🏦 Sistema de Facturación y Control Bancario - Banco Itaú")
st.caption(f"Conexión Directa GSpread | Fecha actual: {formatear_fecha(FECHA_ACTUAL)}")
st.markdown("---")

# -----------------------------------------------------------------------------
# 4. MENÚ NAVEGACIÓN
# -----------------------------------------------------------------------------
menu = st.sidebar.radio(
    "📍 Menú Principal",
    [
        "📊 Estado de Cuenta & Dashboard",
        "👨‍💼 Reporte por Contador",
        "📋 Registrar y Anular Facturas",
        "🏷️ Gestionar Timbrados",
        "💵 Cobranzas de Facturas",
        "🏦 Movimientos Banco Itaú",
        "⚙️ Configurar Saldo Inicial"
    ]
)

# =============================================================================
# MÓDULO 1: ESTADO DE CUENTA & DASHBOARD (CON FILTRO Y REINICIO MENSUAL)
# =============================================================================
if menu == "📊 Estado de Cuenta & Dashboard":
    st.header("📊 Estado de Cuenta Consolidado - Banco Itaú")

    # Controles de filtro mensual
    col_mes, col_anio = st.columns(2)
    with col_mes:
        mes_sel = st.selectbox("📅 Seleccione Mes:", list(NOMBRES_MESES.keys()), format_func=lambda x: NOMBRES_MESES[x], index=MES_ACTUAL - 1)
    with col_anio:
        anios_disponibles = sorted(list(set([ANIO_ACTUAL - 1, ANIO_ACTUAL, ANIO_ACTUAL + 1])))
        anio_sel = st.selectbox("📅 Seleccione Año:", anios_disponibles, index=anios_disponibles.index(ANIO_ACTUAL))

    st.caption(f"Mostrando métricas de facturación correspondientes a: **{NOMBRES_MESES[mes_sel]} {anio_sel}**")

    # Saldo del banco (acumulado total real)
    saldo_inicial = st.session_state.saldo_inicial
    ingresos_banco = pd.to_numeric(st.session_state.banco[st.session_state.banco["Monto_PYG"] > 0]["Monto_PYG"], errors='coerce').sum() if not st.session_state.banco.empty else 0.0
    egresos_banco = pd.to_numeric(st.session_state.banco[st.session_state.banco["Monto_PYG"] < 0]["Monto_PYG"], errors='coerce').sum() if not st.session_state.banco.empty else 0.0
    saldo_actual_banco = saldo_inicial + ingresos_banco + egresos_banco

    # Filtrar facturas del mes/año seleccionado y que no estén anuladas
    facturas_validas = st.session_state.facturas[st.session_state.facturas["Estado"] != "Anulada"].copy() if not st.session_state.facturas.empty else pd.DataFrame()

    if not facturas_validas.empty:
        facturas_validas["Fecha_DT"] = pd.to_datetime(facturas_validas["Fecha"], errors='coerce')
        facturas_mes = facturas_validas[
            (facturas_validas["Fecha_DT"].dt.month == mes_sel) & 
            (facturas_validas["Fecha_DT"].dt.year == anio_sel)
        ]
    else:
        facturas_mes = pd.DataFrame()

    total_facturado_mes = pd.to_numeric(facturas_mes["Monto_PYG"], errors='coerce').sum() if not facturas_mes.empty else 0.0
    total_cobrado_mes = pd.to_numeric(facturas_mes["Monto_Pagado"], errors='coerce').sum() if not facturas_mes.empty else 0.0
    pendiente_cobro_mes = total_facturado_mes - total_cobrado_mes

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo Banco Itaú (Actual)", formatear_pyg(saldo_actual_banco))
    c2.metric(f"Facturado ({NOMBRES_MESES[mes_sel]})", formatear_pyg(total_facturado_mes))
    c3.metric(f"Cobrado ({NOMBRES_MESES[mes_sel]})", formatear_pyg(total_cobrado_mes))
    c4.metric(f"Pendiente ({NOMBRES_MESES[mes_sel]})", formatear_pyg(pendiente_cobro_mes))

    st.markdown("---")

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("📑 Extracto / Movimientos de Banco Itaú")
        if not st.session_state.banco.empty:
            df_b = st.session_state.banco.copy()
            df_b["Fecha"] = df_b["Fecha"].apply(formatear_fecha)
            df_b["Monto_PYG"] = df_b["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_b[["ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Monto_PYG"]], use_container_width=True)
        else:
            st.info("No hay movimientos bancarios registrados.")

    with col_der:
        st.subheader(f"🧾 Facturas Emitidas ({NOMBRES_MESES[mes_sel]} {anio_sel})")
        if not facturas_mes.empty:
            df_f = facturas_mes.copy()
            df_f["Fecha"] = df_f["Fecha"].apply(formatear_fecha)
            df_f["Monto_PYG"] = df_f["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_f[["ID", "Cliente", "Trabajo", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_PYG"]], use_container_width=True)
        else:
            st.info(f"No hay facturas registradas en {NOMBRES_MESES[mes_sel]} {anio_sel}.")

# =============================================================================
# MÓDULO 2: REPORTE & ESTADO DE CUENTA POR CONTADOR (CON FILTRO DE MES)
# =============================================================================
elif menu == "👨‍💼 Reporte por Contador":
    st.header("👨‍💼 Estado de Cuenta Filtrado por Contador")

    if not st.session_state.facturas.empty:
        df_validas = st.session_state.facturas[st.session_state.facturas["Estado"] != "Anulada"].copy()
        
        lista_contadores = sorted([str(c).strip() for c in df_validas["Contador"].unique() if str(c).strip() != ""])

        if not lista_contadores:
            st.info("No hay facturas activas asociadas a ningún contador.")
        else:
            col_c, col_m, col_a = st.columns(3)
            with col_c:
                contador_seleccionado = st.selectbox("🔍 Contador:", ["-- Todos los Contadores --"] + lista_contadores)
            with col_m:
                mes_rep = st.selectbox("📅 Mes:", [0] + list(NOMBRES_MESES.keys()), format_func=lambda x: "Todos los Meses" if x == 0 else NOMBRES_MESES[x], index=MES_ACTUAL)
            with col_a:
                anios_rep = sorted(list(set([ANIO_ACTUAL - 1, ANIO_ACTUAL, ANIO_ACTUAL + 1])))
                anio_rep = st.selectbox("📅 Año:", anios_rep, index=anios_rep.index(ANIO_ACTUAL))

            df_filtrado = df_validas.copy()
            df_filtrado["Fecha_DT"] = pd.to_datetime(df_filtrado["Fecha"], errors='coerce')

            if contador_seleccionado != "-- Todos los Contadores --":
                df_filtrado = df_filtrado[df_filtrado["Contador"] == contador_seleccionado]

            if mes_rep != 0:
                df_filtrado = df_filtrado[
                    (df_filtrado["Fecha_DT"].dt.month == mes_rep) & 
                    (df_filtrado["Fecha_DT"].dt.year == anio_rep)
                ]
            else:
                df_filtrado = df_filtrado[df_filtrado["Fecha_DT"].dt.year == anio_rep]

            tot_fact = df_filtrado["Monto_PYG"].sum()
            tot_cob = df_filtrado["Monto_Pagado"].sum()
            tot_pend = tot_fact - tot_cob

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Facturado", formatear_pyg(tot_fact))
            m2.metric("Total Cobrado", formatear_pyg(tot_cob))
            m3.metric("Saldo Pendiente", formatear_pyg(tot_pend))

            st.markdown("---")

            df_export = df_filtrado.copy()
            df_export["Saldo_Pendiente"] = df_export["Monto_PYG"] - df_export["Monto_Pagado"]
            
            if "Fecha_DT" in df_export.columns:
                df_export = df_export.drop(columns=["Fecha_DT"])

            csv_data = convertir_df_a_csv(df_export)
            
            txt_mes = NOMBRES_MESES[mes_rep] if mes_rep != 0 else "Anual"
            st.download_button(
                label=f"📥 Descargar Estado de Cuenta ({contador_seleccionado} - {txt_mes} {anio_rep})",
                data=csv_data,
                file_name=f"Estado_de_Cuenta_{contador_seleccionado.replace(' ', '_')}_{txt_mes}_{anio_rep}.csv",
                mime="text/csv",
                use_container_width=True
            )

            st.subheader(f"📋 Detalle de Facturas - {contador_seleccionado} ({txt_mes} {anio_rep})")
            
            df_vis = df_export.copy()
            df_vis["Fecha"] = df_vis["Fecha"].apply(formatear_fecha)
            df_vis["Monto_PYG"] = df_vis["Monto_PYG"].apply(formatear_pyg)
            df_vis["Monto_Pagado"] = df_vis["Monto_Pagado"].apply(formatear_pyg)
            df_vis["Saldo_Pendiente"] = df_vis["Saldo_Pendiente"].apply(formatear_pyg)

            st.dataframe(
                df_vis[["ID", "Cliente", "Trabajo", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_PYG", "Monto_Pagado", "Saldo_Pendiente"]],
                use_container_width=True
            )
    else:
        st.info("No hay facturas registradas en la base de datos.")

# =============================================================================
# MÓDULO 3: REGISTRAR Y ANULAR FACTURAS
# =============================================================================
elif menu == "📋 Registrar y Anular Facturas":
    st.header("📋 Gestión de Facturación: Emisión y Anulación")

    tab_registro, tab_anulacion = st.tabs(["📝 Emitir Nueva Factura", "🚫 Anular Factura Creada"])

    with tab_registro:
        OPCIONES_TIMBRADO = [
            "🔴 Pendiente de Firma",
            "🟡 Firmado (En proceso)",
            "🟢 Firmado y Devuelto a Imprenta"
        ]

        with st.form("form_registro_factura", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                cliente = st.text_input("Nombre / Razón Social del Cliente *")
                trabajo = st.text_input("Trabajo / Descripción Correspondiente *", placeholder="Ej: Impresión de Folletos")
                contador = st.text_input("Contador Asociado *")
                monto = st.number_input("Monto Total (en Guaraníes ₲) *", min_value=0.0, step=100000.0, value=1000000.0)
            
            with col2:
                fecha_emision = st.date_input("Fecha de Emisión", value=FECHA_ACTUAL, format="DD/MM/YYYY")
                aplica_timbrado = st.checkbox("¿Aplica / Requiere Timbrado?", value=True)
                
                if aplica_timbrado:
                    timbrado_estado = st.selectbox("Estado del Timbrado:", OPCIONES_TIMBRADO)
                else:
                    timbrado_estado = "⚪ No Aplica"
                
            submitted = st.form_submit_button("💾 Guardar Factura en Google Sheets")

            if submitted:
                if not cliente or not contador or not trabajo:
                    st.error("Por favor completa los campos obligatorios (*).")
                else:
                    nuevo_id = len(st.session_state.facturas) + 1
                    nueva_factura = {
                        "ID": nuevo_id,
                        "Cliente": cliente.strip(),
                        "Contador": contador.strip(),
                        "Trabajo": trabajo.strip(),
                        "Monto_PYG": float(monto),
                        "Fecha": str(fecha_emision),
                        "Aplica_Timbrado": "Sí" if aplica_timbrado else "No",
                        "Timbrado_Estado": timbrado_estado,
                        "Estado": "Pendiente",
                        "Monto_Pagado": 0.0
                    }
                    
                    st.session_state.facturas = pd.concat([
                        st.session_state.facturas, 
                        pd.DataFrame([nueva_factura])
                    ], ignore_index=True)
                    
                    guardar_tabla(st.session_state.facturas, "Facturas")
                    st.success(f"✅ Factura #{nuevo_id} guardada con éxito.")
                    st.rerun()

        st.subheader("📋 Lista de Facturas")
        if not st.session_state.facturas.empty:
            df_disp = st.session_state.facturas.copy()
            df_disp["Fecha"] = df_disp["Fecha"].apply(formatear_fecha)
            df_disp["Monto_PYG"] = df_disp["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_disp, use_container_width=True)

    with tab_anulacion:
        st.subheader("🚫 Anular Factura Emitida")
        st.caption("Selecciona una factura registrada por error. Su estado pasará a 'Anulada' y sus valores no afectarán los totales.")

        if not st.session_state.facturas.empty:
            facturas_activas = st.session_state.facturas[st.session_state.facturas["Estado"] != "Anulada"]

            if facturas_activas.empty:
                st.info("Todas las facturas registradas ya se encuentran anuladas.")
            else:
                dict_fact_anular = {}
                for _, r in facturas_activas.iterrows():
                    lbl = f"Factura #{r['ID']} - {r['Cliente']} [{r['Trabajo']}] - Contador: {r['Contador']} - Monto: {formatear_pyg(r['Monto_PYG'])}"
                    dict_fact_anular[lbl] = int(r['ID'])

                sel_label = st.selectbox("Seleccione la Factura a Anular:", list(dict_fact_anular.keys()))
                id_fact_anular = dict_fact_anular[sel_label]

                factura_obj = st.session_state.facturas[st.session_state.facturas["ID"] == id_fact_anular].iloc[0]

                st.warning(f"⚠️ **Atención:** Se anulará la Factura #{id_fact_anular} de **
