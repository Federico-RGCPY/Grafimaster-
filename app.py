import streamlit as st
import pandas as pd
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y EVITAR ERRORES DE TRADUCCIÓN DEL NAVEGADOR
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
# 2. CONEXIÓN DIRECTA NATIVA A GOOGLE SHEETS (GSPREAD)
# -----------------------------------------------------------------------------
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def obtener_cliente_gspread():
    """Autentica con la cuenta de servicio corrigiendo automáticamente la clave PEM."""
    # Copiamos la configuración de secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # Reparar automáticamente la clave privada para evitar el error PEM InvalidByte
    p_key = creds_dict["private_key"]
    p_key = p_key.replace("\\n", "\n")
    p_key = p_key.strip("'\"")
    creds_dict["private_key"] = p_key
    
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

# -----------------------------------------------------------------------------
# 3. INICIALIZACIÓN
# -----------------------------------------------------------------------------
if 'cargado' not in st.session_state:
    cargar_datos()
    st.session_state.cargado = True

FECHA_ACTUAL = date.today()

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
        "📋 Registrar Facturas",
        "🏷️ Gestionar Timbrados",
        "💵 Cobranzas de Facturas",
        "🏦 Movimientos Banco Itaú",
        "⚙️ Configurar Saldo Inicial"
    ]
)

# =============================================================================
# MÓDULO 1: ESTADO DE CUENTA & DASHBOARD
# =============================================================================
if menu == "📊 Estado de Cuenta & Dashboard":
    st.header("📊 Estado de Cuenta Consolidado - Banco Itaú")

    saldo_inicial = st.session_state.saldo_inicial
    ingresos_banco = pd.to_numeric(st.session_state.banco[st.session_state.banco["Monto_PYG"] > 0]["Monto_PYG"], errors='coerce').sum() if not st.session_state.banco.empty else 0.0
    egresos_banco = pd.to_numeric(st.session_state.banco[st.session_state.banco["Monto_PYG"] < 0]["Monto_PYG"], errors='coerce').sum() if not st.session_state.banco.empty else 0.0
    
    saldo_actual_banco = saldo_inicial + ingresos_banco + egresos_banco

    total_facturado = pd.to_numeric(st.session_state.facturas["Monto_PYG"], errors='coerce').sum() if not st.session_state.facturas.empty else 0.0
    total_cobrado = pd.to_numeric(st.session_state.facturas["Monto_Pagado"], errors='coerce').sum() if not st.session_state.facturas.empty else 0.0
    pendiente_cobro = total_facturado - total_cobrado

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo Inicial", formatear_pyg(saldo_inicial))
    c2.metric("Saldo Actual Itaú", formatear_pyg(saldo_actual_banco))
    c3.metric("Total Facturado", formatear_pyg(total_facturado))
    c4.metric("Pendiente de Cobro", formatear_pyg(pendiente_cobro))

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
        st.subheader("🧾 Facturas y Trabajos")
        if not st.session_state.facturas.empty:
            df_f = st.session_state.facturas.copy()
            df_f["Fecha"] = df_f["Fecha"].apply(formatear_fecha)
            df_f["Monto_PYG"] = df_f["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_f[["ID", "Cliente", "Trabajo", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_PYG"]], use_container_width=True)
        else:
            st.info("No hay facturas registradas.")

# =============================================================================
# MÓDULO 2: REGISTRAR FACTURAS
# =============================================================================
elif menu == "📋 Registrar Facturas":
    st.header("📋 Registrar Nueva Factura Emitida")

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

# =============================================================================
# MÓDULO 3: GESTIONAR TIMBRADOS
# =============================================================================
elif menu == "🏷️ Gestionar Timbrados":
    st.header("🏷️ Control de Timbrados: Firmados y Devueltos a Imprenta")

    if not st.session_state.facturas.empty:
        facturas_con_timbrado = st.session_state.facturas[st.session_state.facturas["Aplica_Timbrado"] != "No"]

        if facturas_con_timbrado.empty:
            st.info("No hay facturas registradas que requieran timbrado.")
        else:
            df_show = facturas_con_timbrado.copy()
            df_show["Fecha"] = df_show["Fecha"].apply(formatear_fecha)
            df_show["Monto_PYG"] = df_show["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_show[["ID", "Cliente", "Trabajo", "Contador", "Fecha", "Timbrado_Estado", "Monto_PYG"]], use_container_width=True)

            st.markdown("---")
            st.subheader("✏️ Actualizar Estado de Timbrado")

            opciones_dict = {}
            for _, r in facturas_con_timbrado.iterrows():
                key_text = f"Factura #{r['ID']} - {r['Cliente']} ({r['Trabajo']}) [Estado: {r['Timbrado_Estado']}]"
                opciones_dict[key_text] = int(r['ID'])

            factura_sel_text = st.selectbox("Seleccione la Factura a actualizar:", list(opciones_dict.keys()))
            id_fact_sel = opciones_dict[factura_sel_text]

            nuevo_estado_t = st.radio(
                "Marcar Nuevo Estado:",
                [
                    "🔴 Pendiente de Firma",
                    "🟡 Firmado (En proceso)",
                    "🟢 Firmado y Devuelto a Imprenta"
                ]
            )

            if st.button("💾 Actualizar Timbrado"):
                idx = st.session_state.facturas[st.session_state.facturas["ID"] == id_fact_sel].index[0]
                st.session_state.facturas.at[idx, "Timbrado_Estado"] = nuevo_estado_t
                guardar_tabla(st.session_state.facturas, "Facturas")
                st.success("✅ Estado de timbrado actualizado y guardado.")
                st.rerun()
    else:
        st.info("Aún no hay facturas registradas.")

# =============================================================================
# MÓDULO 4: COBRANZAS DE FACTURAS
# =============================================================================
elif menu == "💵 Cobranzas de Facturas":
    st.header("💵 Registrar Cobranza -> Impacta en Banco Itaú")

    if not st.session_state.facturas.empty:
        facturas_pendientes = st.session_state.facturas[st.session_state.facturas["Estado"] != "Pagado Total"]
        
        if facturas_pendientes.empty:
            st.success("🎉 Todas las facturas registradas están totalmente cobradas.")
        else:
            opciones_dict = {}
            for _, row in facturas_pendientes.iterrows():
                pend = float(row['Monto_PYG']) - float(row['Monto_Pagado'])
                key_text = f"Factura #{row['ID']} - {row['Cliente']} [{row['Trabajo']}] (Pendiente: {formatear_pyg(pend)})"
                opciones_dict[key_text] = int(row['ID'])
            
            seleccion = st.selectbox("Seleccione Factura a Cobrar:", list(opciones_dict.keys()))
            factura_id_sel = opciones_dict[seleccion]
            
            factura_actual = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].iloc[0]
            monto_pendiente = float(factura_actual["Monto_PYG"]) - float(factura_actual["Monto_Pagado"])

            with st.form("form_cobro"):
                c1, c2 = st.columns(2)
                with c1:
                    monto_a_cobrar = st.number_input(
                        f"Monto a Cobrar (Pendiente: {formatear_pyg(monto_pendiente)})", 
                        min_value=1.0, 
                        max_value=float(monto_pendiente), 
                        value=float(monto_pendiente),
                        step=100000.0
                    )
                    fecha_pago = st.date_input("Fecha de Cobro", value=FECHA_ACTUAL, format="DD/MM/YYYY")
                with c2:
                    concepto_pago = st.text_input("Concepto", value=f"Cobro Factura #{factura_id_sel} - {factura_actual['Cliente']} ({factura_actual['Trabajo']})")

                if st.form_submit_button("💳 Registrar Pago en Banco Itaú"):
                    idx = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].index[0]
                    nuevo_pagado = float(st.session_state.facturas.at[idx, "Monto_Pagado"]) + monto_a_cobrar
                    st.session_state.facturas.at[idx, "Monto_Pagado"] = nuevo_pagado
                    
                    if nuevo_pagado >= float(st.session_state.facturas.at[idx, "Monto_PYG"]):
                        st.session_state.facturas.at[idx, "Estado"] = "Pagado Total"
                    else:
                        st.session_state.facturas.at[idx, "Estado"] = "Pagado Parcial"

                    nuevo_id_banco = len(st.session_state.banco) + 1
                    nuevo_mov_banco = {
                        "ID": nuevo_id_banco,
                        "Fecha": str(fecha_pago),
                        "Tipo": "Ingreso (Cobro)",
                        "Concepto": concepto_pago,
                        "Cliente_Asociado": factura_actual["Cliente"],
                        "Factura_ID": factura_id_sel,
                        "Monto_PYG": float(monto_a_cobrar)
                    }
                    st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([nuevo_mov_banco])], ignore_index=True)

                    guardar_tabla(st.session_state.facturas, "Facturas")
                    guardar_tabla(st.session_state.banco, "Banco_Itau")
                    st.success(f"✅ Cobro registrado e impactado en el Banco Itaú.")
                    st.rerun()
    else:
        st.info("No existen facturas registradas.")

# =============================================================================
# MÓDULO 5: MOVIMIENTOS BANCO ITAÚ
# =============================================================================
elif menu == "🏦 Movimientos Banco Itaú":
    st.header("🏦 Libro de Banco Itaú (Ingresos & Egresos Directos)")

    with st.form("form_mov_banco", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de Transacción", ["Ingreso Directo", "Egreso / Gasto"])
            concepto = st.text_input("Concepto / Descripción *", placeholder="Ej: Pago de alquiler, Honorarios")
            cliente_ref = st.text_input("Cliente / Proveedor Referencia", placeholder="Opcional")
        with col2:
            monto_mov = st.number_input("Monto en Guaraníes (₲) *", min_value=1.0, step=100000.0, value=250000.0)
            fecha_mov = st.date_input("Fecha del Movimiento", value=FECHA_ACTUAL, format="DD/MM/YYYY")

        if st.form_submit_button("💾 Guardar Movimiento"):
            if not concepto:
                st.error("Debes ingresar un concepto.")
            else:
                monto_final = float(monto_mov) if tipo == "Ingreso Directo" else -float(monto_mov)
                nuevo_mov = {
                    "ID": len(st.session_state.banco) + 1,
                    "Fecha": str(fecha_mov),
                    "Tipo": tipo,
                    "Concepto": concepto.strip(),
                    "Cliente_Asociado": cliente_ref.strip() if cliente_ref else "N/A",
                    "Factura_ID": "N/A",
                    "Monto_PYG": monto_final
                }
                st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([nuevo_mov])], ignore_index=True)
                guardar_tabla(st.session_state.banco, "Banco_Itau")
                st.success(f"✅ Movimiento registrado con éxito.")
                st.rerun()

    st.subheader("📋 Historial de Movimientos")
    if not st.session_state.banco.empty:
        df_b_disp = st.session_state.banco.copy()
        df_b_disp["Fecha"] = df_b_disp["Fecha"].apply(formatear_fecha)
        df_b_disp["Monto_PYG"] = df_b_disp["Monto_PYG"].apply(formatear_pyg)
        st.dataframe(df_b_disp, use_container_width=True)

# =============================================================================
# MÓDULO 6: CONFIGURAR SALDO INICIAL
# =============================================================================
elif menu == "⚙️ Configurar Saldo Inicial":
    st.header("⚙️ Ajuste de Saldo Inicial del Banco Itaú")

    saldo_actual_conf = st.session_state.saldo_inicial
    st.write(f"**Saldo Inicial Activo:** {formatear_pyg(saldo_actual_conf)}")

    with st.form("form_saldo_inicial"):
        nuevo_saldo = st.number_input("Establecer Saldo Inicial (en Guaraníes ₲):", value=float(saldo_actual_conf), step=1000000.0, min_value=0.0)
        if st.form_submit_button("💾 Actualizar Saldo Inicial"):
            st.session_state.saldo_inicial = float(nuevo_saldo)
            df_conf = pd.DataFrame([{"Clave": "Saldo_Inicial", "Valor": nuevo_saldo}])
            guardar_tabla(df_conf, "Configuracion")
            st.success(f"✅ Saldo Inicial actualizado a {formatear_pyg(nuevo_saldo)}.")
            st.rerun()
