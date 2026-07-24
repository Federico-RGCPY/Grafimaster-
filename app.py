import streamlit as st
import pandas as pd
from datetime import datetime, date
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y EVITAR ERRORES DE TRADUCCIÓN DEL NAVEGADOR
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Facturación - Banco Itaú",
    page_icon="🏦",
    layout="wide"
)

# Bloquea la traducción automática del navegador que causa el error "removeChild"
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
# 2. CONEXIÓN Y PERSISTENCIA CON GOOGLE SHEETS
# -----------------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_NAME = st.secrets["spreadsheet"]["spreadsheet_name"]

def cargar_datos():
    """Lee la información registrada en las pestañas de Google Sheets."""
    try:
        df_facturas = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Facturas")
        df_banco = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Banco_Itau")
        df_config = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Configuracion")

        # Formato de Facturas
        if df_facturas is not None and not df_facturas.empty:
            df_facturas["Fecha"] = pd.to_datetime(df_facturas["Fecha"]).dt.date
        else:
            df_facturas = pd.DataFrame(columns=[
                "ID", "Cliente", "Contador", "Monto_PYG", "Fecha", "Timbrado_Estado", "Estado", "Monto_Pagado"
            ])

        # Formato de Banco Itaú
        if df_banco is not None and not df_banco.empty:
            df_banco["Fecha"] = pd.to_datetime(df_banco["Fecha"]).dt.date
        else:
            df_banco = pd.DataFrame(columns=[
                "ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"
            ])

        # Formato de Configuración / Saldo Inicial
        if df_config is not None and not df_config.empty:
            config_dict = dict(zip(df_config["Clave"], df_config["Valor"]))
            saldo_inicial = float(config_dict.get("Saldo_Inicial", 0.0))
        else:
            saldo_inicial = 0.0

        st.session_state.facturas = df_facturas
        st.session_state.banco = df_banco
        st.session_state.saldo_inicial = saldo_inicial

    except Exception as e:
        st.error(f"⚠️ Atención: Ocurrió un inconveniente al conectar con Google Sheets: {e}")
        st.warning("Verifica que la planilla esté compartida como 'Editor' con el correo de tu cuenta de servicio.")
        
        # Asignación de variables por defecto para evitar que colapse la interfaz de usuario
        st.session_state.facturas = pd.DataFrame(columns=[
            "ID", "Cliente", "Contador", "Monto_PYG", "Fecha", "Timbrado_Estado", "Estado", "Monto_Pagado"
        ])
        st.session_state.banco = pd.DataFrame(columns=[
            "ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"
        ])
        st.session_state.saldo_inicial = 0.0

def guardar_tabla(df, worksheet_name):
    """Guarda los cambios de los dataframes en la pestaña correspondiente de Google Sheets."""
    try:
        conn.update(spreadsheet=SPREADSHEET_NAME, worksheet=worksheet_name, data=df)
    except Exception as e:
        st.error(f"Error al guardar los cambios en Google Sheets: {e}")

def formatear_pyg(monto):
    """Formatea importes numéricos a Guaraníes (₲ 1.000.000)."""
    return f"₲ {monto:,.0f}".replace(",", ".")

def formatear_fecha(fecha_obj):
    """Formatea objetos fecha a DD/MM/YYYY (ej: 24/07/2026)."""
    if pd.isna(fecha_obj) or fecha_obj is None:
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
st.caption(f"Sincronizado con Google Sheets | Fecha actual: {formatear_fecha(FECHA_ACTUAL)}")
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
    ingresos_banco = st.session_state.banco[st.session_state.banco["Monto_PYG"] > 0]["Monto_PYG"].sum() if not st.session_state.banco.empty else 0.0
    egresos_banco = st.session_state.banco[st.session_state.banco["Monto_PYG"] < 0]["Monto_PYG"].sum() if not st.session_state.banco.empty else 0.0
    
    saldo_actual_banco = saldo_inicial + ingresos_banco + egresos_banco

    total_facturado = st.session_state.facturas["Monto_PYG"].sum() if not st.session_state.facturas.empty else 0.0
    total_cobrado = st.session_state.facturas["Monto_Pagado"].sum() if not st.session_state.facturas.empty else 0.0
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
        st.subheader("🧾 Facturas y Timbrados")
        if not st.session_state.facturas.empty:
            df_f = st.session_state.facturas.copy()
            df_f["Fecha"] = df_f["Fecha"].apply(formatear_fecha)
            df_f["Monto_PYG"] = df_f["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_f[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_PYG"]], use_container_width=True)
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
            contador = st.text_input("Contador Asociado *")
            monto = st.number_input("Monto Total (en Guaraníes ₲) *", min_value=0.0, step=100000.0, value=1000000.0)
        
        with col2:
            fecha_emision = st.date_input("Fecha de Emisión", value=FECHA_ACTUAL, format="DD/MM/YYYY")
            timbrado_estado = st.selectbox("Estado del Timbrado:", OPCIONES_TIMBRADO)
            
        submitted = st.form_submit_button("💾 Guardar Factura en Google Sheets")

        if submitted:
            if not cliente or not contador:
                st.error("Por favor completa los campos obligatorios (*).")
            else:
                nuevo_id = len(st.session_state.facturas) + 1
                nueva_factura = {
                    "ID": nuevo_id,
                    "Cliente": cliente.strip(),
                    "Contador": contador.strip(),
                    "Monto_PYG": float(monto),
                    "Fecha": str(fecha_emision),
                    "Timbrado_Estado": timbrado_estado,
                    "Estado": "Pendiente",
                    "Monto_Pagado": 0.0
                }
                
                st.session_state.facturas = pd.concat([
                    st.session_state.facturas, 
                    pd.DataFrame([nueva_factura])
                ], ignore_index=True)
                
                guardar_tabla(st.session_state.facturas, "Facturas")
                st.success(f"✅ Factura #{nuevo_id} guardada con éxito en Google Sheets.")
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
        df_show = st.session_state.facturas.copy()
        df_show["Fecha"] = df_show["Fecha"].apply(formatear_fecha)
        df_show["Monto_PYG"] = df_show["Monto_PYG"].apply(formatear_pyg)
        st.dataframe(df_show[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado", "Monto_PYG"]], use_container_width=True)

        st.markdown("---")
        st.subheader("✏️ Actualizar Estado de Timbrado")

        factura_sel = st.selectbox(
            "Seleccione la Factura a actualizar:",
            st.session_state.facturas.apply(lambda r: f"Factura #{r['ID']} - {r['Cliente']} (Estado: {r['Timbrado_Estado']})", axis=1)
        )
        id_fact_sel = int(factura_sel.split(" ")[0].replace("Factura", "").replace("#", ""))

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
            opciones = facturas_pendientes.apply(
                lambda row: f"Factura #{row['ID']} - {row['Cliente']} (Pendiente: {formatear_pyg(row['Monto_PYG'] - row['Monto_Pagado'])})", 
                axis=1
            )
            
            seleccion = st.selectbox("Seleccione Factura a Cobrar:", opciones)
            factura_id_sel = int(seleccion.split(" ")[0].replace("Factura", "").replace("#", ""))
            
            factura_actual = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].iloc[0]
            monto_pendiente = factura_actual["Monto_PYG"] - factura_actual["Monto_Pagado"]

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
                    concepto_pago = st.text_input("Concepto", value=f"Cobro Factura #{factura_id_sel} - {factura_actual['Cliente']}")

                if st.form_submit_button("💳 Registrar Pago en Banco Itaú"):
                    idx = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].index[0]
                    nuevo_pagado = st.session_state.facturas.at[idx, "Monto_Pagado"] + monto_a_cobrar
                    st.session_state.facturas.at[idx, "Monto_Pagado"] = nuevo_pagado
                    
                    if nuevo_pagado >= st.session_state.facturas.at[idx, "Monto_PYG"]:
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
