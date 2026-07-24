import streamlit as st
import pandas as pd
from datetime import datetime, date
from streamlit_gsheets import GSheetsConnection

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Facturación - Banco Itaú",
    page_icon="🏦",
    layout="wide"
)

# Conexión a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
SPREADSHEET_NAME = st.secrets["spreadsheet"]["spreadsheet_name"]

# -----------------------------------------------------------------------------
# FUNCIONES DE LECTURA Y ESCRITURA EN GOOGLE SHEETS
# -----------------------------------------------------------------------------
def cargar_datos():
    try:
        df_facturas = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Facturas")
        df_banco = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Banco_Itau")
        df_config = conn.read(spreadsheet=SPREADSHEET_NAME, worksheet="Configuracion")

        # Limpiar y dar formato a los DataFrames
        if df_facturas is not None and not df_facturas.empty:
            df_facturas["Fecha"] = pd.to_datetime(df_facturas["Fecha"]).dt.date
        else:
            df_facturas = pd.DataFrame(columns=["ID", "Cliente", "Contador", "Monto_PYG", "Fecha", "Timbrado_Estado", "Estado", "Monto_Pagado"])

        if df_banco is not None and not df_banco.empty:
            df_banco["Fecha"] = pd.to_datetime(df_banco["Fecha"]).dt.date
        else:
            df_banco = pd.DataFrame(columns=["ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"])

        if df_config is not None and not df_config.empty:
            config_dict = dict(zip(df_config["Clave"], df_config["Valor"]))
            saldo_inicial = float(config_dict.get("Saldo_Inicial", 0.0))
        else:
            saldo_inicial = 0.0

        st.session_state.facturas = df_facturas
        st.session_state.banco = df_banco
        st.session_state.saldo_inicial = saldo_inicial
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")

def guardar_tabla(df, worksheet_name):
    conn.update(spreadsheet=SPREADSHEET_NAME, worksheet=worksheet_name, data=df)

def formatear_pyg(monto):
    return f"₲ {monto:,.0f}".replace(",", ".")

def formatear_fecha(fecha_obj):
    if pd.isna(fecha_obj) or fecha_obj is None:
        return ""
    if isinstance(fecha_obj, str):
        try:
            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()
        except ValueError:
            return fecha_obj
    return fecha_obj.strftime("%d/%m/%Y")

# Inicialización
if 'cargado' not in st.session_state:
    cargar_datos()
    st.session_state.cargado = True

FECHA_ACTUAL = date.today()

st.title("🏦 Sistema de Facturación y Banco Itaú (Google Sheets Sync)")
st.caption(f"Sincronizado en tiempo real con Google Sheets | Fecha actual: {formatear_fecha(FECHA_ACTUAL)}")
st.markdown("---")

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
# MÓDULO 1: DASHBOARD
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
    c2.metric("Saldo Banco Itaú", formatear_pyg(saldo_actual_banco))
    c3.metric("Total Facturado", formatear_pyg(total_facturado))
    c4.metric("Pendiente de Cobro", formatear_pyg(pendiente_cobro))

    st.markdown("---")

    col_izq, col_der = st.columns(2)
    with col_izq:
        st.subheader("📑 Extracto Banco Itaú")
        if not st.session_state.banco.empty:
            df_b = st.session_state.banco.copy()
            df_b["Fecha"] = df_b["Fecha"].apply(formatear_fecha)
            df_b["Monto_PYG"] = df_b["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_b[["ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Monto_PYG"]], use_container_width=True)
        else:
            st.info("Sin movimientos.")

    with col_der:
        st.subheader("🧾 Facturas Emitidas")
        if not st.session_state.facturas.empty:
            df_f = st.session_state.facturas.copy()
            df_f["Fecha"] = df_f["Fecha"].apply(formatear_fecha)
            df_f["Monto_PYG"] = df_f["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(df_f[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_PYG"]], use_container_width=True)
        else:
            st.info("Sin facturas.")

# =============================================================================
# MÓDULO 2: REGISTRAR FACTURAS
# =============================================================================
elif menu == "📋 Registrar Facturas":
    st.header("📋 Registrar Nueva Factura")

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
            monto = st.number_input("Monto Total (₲) *", min_value=0.0, step=100000.0, value=1000000.0)
        
        with col2:
            fecha_emision = st.date_input("Fecha de Emisión", value=FECHA_ACTUAL, format="DD/MM/YYYY")
            timbrado_estado = st.selectbox("Estado del Timbrado:", OPCIONES_TIMBRADO)
            
        submitted = st.form_submit_button("💾 Guardar en Google Sheets")

        if submitted:
            if not cliente or not contador:
                st.error("Completa los campos obligatorios (*).")
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
                st.success(f"✅ Factura #{nuevo_id} guardada en Google Sheets.")
                st.rerun()

# =============================================================================
# MÓDULO 3: GESTIONAR TIMBRADOS
# =============================================================================
elif menu == "🏷️ Gestionar Timbrados":
    st.header("🏷️ Control de Timbrados")

    if not st.session_state.facturas.empty:
        df_show = st.session_state.facturas.copy()
        df_show["Fecha"] = df_show["Fecha"].apply(formatear_fecha)
        st.dataframe(df_show[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado"]], use_container_width=True)

        st.subheader("✏️ Actualizar Estado de Timbrado")
        factura_sel = st.selectbox(
            "Seleccione Factura:",
            st.session_state.facturas.apply(lambda r: f"Factura #{r['ID']} - {r['Cliente']} ({r['Timbrado_Estado']})", axis=1)
        )
        id_fact_sel = int(factura_sel.split(" ")[0].replace("Factura", "").replace("#", ""))

        nuevo_estado_t = st.radio(
            "Nuevo Estado:",
            ["🔴 Pendiente de Firma", "🟡 Firmado (En proceso)", "🟢 Firmado y Devuelto a Imprenta"]
        )

        if st.button("💾 Actualizar en Google Sheets"):
            idx = st.session_state.facturas[st.session_state.facturas["ID"] == id_fact_sel].index[0]
            st.session_state.facturas.at[idx, "Timbrado_Estado"] = nuevo_estado_t
            guardar_tabla(st.session_state.facturas, "Facturas")
            st.success("✅ Estado de timbrado actualizado.")
            st.rerun()

# =============================================================================
# MÓDULO 4: COBRANZAS
# =============================================================================
elif menu == "💵 Cobranzas de Facturas":
    st.header("💵 Registrar Cobranza -> Impacta en Banco Itaú")

    if not st.session_state.facturas.empty:
        facturas_pendientes = st.session_state.facturas[st.session_state.facturas["Estado"] != "Pagado Total"]
        
        if not facturas_pendientes.empty:
            opciones = facturas_pendientes.apply(
                lambda row: f"Factura #{row['ID']} - {row['Cliente']} (Pendiente: {formatear_pyg(row['Monto_PYG'] - row['Monto_Pagado'])})", axis=1
            )
            seleccion = st.selectbox("Factura a cobrar:", opciones)
            factura_id_sel = int(seleccion.split(" ")[0].replace("Factura", "").replace("#", ""))
            
            factura_actual = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].iloc[0]
            monto_pendiente = factura_actual["Monto_PYG"] - factura_actual["Monto_Pagado"]

            with st.form("form_cobro"):
                monto_a_cobrar = st.number_input("Monto a Cobrar (₲)", min_value=1.0, max_value=float(monto_pendiente), value=float(monto_pendiente))
                fecha_pago = st.date_input("Fecha de Cobro", value=FECHA_ACTUAL, format="DD/MM/YYYY")
                concepto_pago = st.text_input("Concepto", value=f"Cobro Factura #{factura_id_sel} - {factura_actual['Cliente']}")

                if st.form_submit_button("💳 Confirmar Cobro"):
                    idx = st.session_state.facturas[st.session_state.facturas["ID"] == factura_id_sel].index[0]
                    nuevo_pagado = st.session_state.facturas.at[idx, "Monto_Pagado"] + monto_a_cobrar
                    st.session_state.facturas.at[idx, "Monto_Pagado"] = nuevo_pagado
                    st.session_state.facturas.at[idx, "Estado"] = "Pagado Total" if nuevo_pagado >= st.session_state.facturas.at[idx, "Monto_PYG"] else "Pagado Parcial"

                    nuevo_mov = {
                        "ID": len(st.session_state.banco) + 1,
                        "Fecha": str(fecha_pago),
                        "Tipo": "Ingreso (Cobro)",
                        "Concepto": concepto_pago,
                        "Cliente_Asociado": factura_actual["Cliente"],
                        "Factura_ID": factura_id_sel,
                        "Monto_PYG": float(monto_a_cobrar)
                    }
                    st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([nuevo_mov])], ignore_index=True)

                    guardar_tabla(st.session_state.facturas, "Facturas")
                    guardar_tabla(st.session_state.banco, "Banco_Itau")
                    st.success("✅ Cobro guardado e impactado en Banco Itaú.")
                    st.rerun()

# =============================================================================
# MÓDULO 5: MOVIMIENTOS BANCO ITAÚ
# =============================================================================
elif menu == "🏦 Movimientos Banco Itaú":
    st.header("🏦 Movimientos Banco Itaú")

    with st.form("form_mov_banco", clear_on_submit=True):
        tipo = st.selectbox("Tipo", ["Ingreso Directo", "Egreso / Gasto"])
        concepto = st.text_input("Concepto *")
        monto_mov = st.number_input("Monto (₲) *", min_value=1.0, value=250000.0)
        fecha_mov = st.date_input("Fecha", value=FECHA_ACTUAL, format="DD/MM/YYYY")

        if st.form_submit_button("💾 Guardar Movimiento"):
            monto_final = float(monto_mov) if tipo == "Ingreso Directo" else -float(monto_mov)
            nuevo_mov = {
                "ID": len(st.session_state.banco) + 1,
                "Fecha": str(fecha_mov),
                "Tipo": tipo,
                "Concepto": concepto,
                "Cliente_Asociado": "N/A",
                "Factura_ID": "N/A",
                "Monto_PYG": monto_final
            }
            st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([nuevo_mov])], ignore_index=True)
            guardar_tabla(st.session_state.banco, "Banco_Itau")
            st.success("✅ Movimiento bancario registrado.")
            st.rerun()

# =============================================================================
# MÓDULO 6: SALDO INICIAL
# =============================================================================
elif menu == "⚙️ Configurar Saldo Inicial":
    st.header("⚙️ Saldo Inicial Banco Itaú")

    nuevo_saldo = st.number_input("Nuevo Saldo Inicial (₲):", value=float(st.session_state.saldo_inicial))
    if st.button("💾 Guardar Saldo Inicial"):
        st.session_state.saldo_inicial = float(nuevo_saldo)
        df_conf = pd.DataFrame([{"Clave": "Saldo_Inicial", "Valor": nuevo_saldo}])
        guardar_tabla(df_conf, "Configuracion")
        st.success("✅ Saldo Inicial guardado en Google Sheets.")
        st.rerun()
