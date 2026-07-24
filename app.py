import streamlit as st
import pandas as pd
import os
from datetime import datetime, date

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Facturación y Banco Itaú",
    page_icon="🏦",
    layout="wide"
)

EXCEL_FILE = "base_datos_itau.xlsx"
BANCO_NOMBRE = "Banco Itaú"

# -----------------------------------------------------------------------------
# FUNCIONES DE PERSISTENCIA EN EXCEL
# -----------------------------------------------------------------------------
def inicializar_excel():
    """Crea el archivo Excel con las pestañas necesarias si no existe."""
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
            df_facturas = pd.DataFrame(columns=[
                "ID", "Cliente", "Contador", "Monto_PYG", "Fecha", "Timbrado_Estado", "Estado", "Monto_Pagado"
            ])
            df_facturas.to_excel(writer, sheet_name="Facturas", index=False)

            df_banco = pd.DataFrame(columns=[
                "ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"
            ])
            df_banco.to_excel(writer, sheet_name="Banco_Itau", index=False)

            df_config = pd.DataFrame([
                {"Clave": "Saldo_Inicial", "Valor": 0.0}
            ])
            df_config.to_excel(writer, sheet_name="Configuracion", index=False)

def cargar_datos():
    """Carga todas las hojas del Excel a st.session_state."""
    inicializar_excel()
    try:
        xls = pd.ExcelFile(EXCEL_FILE)
        
        # Facturas
        if "Facturas" in xls.sheet_names:
            df_f = pd.read_excel(xls, sheet_name="Facturas")
            if not df_f.empty and "Fecha" in df_f.columns:
                df_f["Fecha"] = pd.to_datetime(df_f["Fecha"]).dt.date
            st.session_state.facturas = df_f
        else:
            st.session_state.facturas = pd.DataFrame(columns=[
                "ID", "Cliente", "Contador", "Monto_PYG", "Fecha", "Timbrado_Estado", "Estado", "Monto_Pagado"
            ])

        # Banco Itaú
        if "Banco_Itau" in xls.sheet_names:
            df_b = pd.read_excel(xls, sheet_name="Banco_Itau")
            if not df_b.empty and "Fecha" in df_b.columns:
                df_b["Fecha"] = pd.to_datetime(df_b["Fecha"]).dt.date
            st.session_state.banco = df_b
        else:
            st.session_state.banco = pd.DataFrame(columns=[
                "ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Factura_ID", "Monto_PYG"
            ])

        # Configuración / Saldo Inicial
        if "Configuracion" in xls.sheet_names:
            df_c = pd.read_excel(xls, sheet_name="Configuracion")
            config_dict = dict(zip(df_c["Clave"], df_c["Valor"]))
            st.session_state.saldo_inicial = float(config_dict.get("Saldo_Inicial", 0.0))
        else:
            st.session_state.saldo_inicial = 0.0

    except Exception as e:
        st.error(f"Error al cargar la base de datos Excel: {e}")

def guardar_datos():
    """Guarda todo el estado actual en el archivo Excel de respaldo."""
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        st.session_state.facturas.to_excel(writer, sheet_name="Facturas", index=False)
        st.session_state.banco.to_excel(writer, sheet_name="Banco_Itau", index=False)
        
        df_config = pd.DataFrame([
            {"Clave": "Saldo_Inicial", "Valor": st.session_state.saldo_inicial}
        ])
        df_config.to_excel(writer, sheet_name="Configuracion", index=False)

def formatear_pyg(monto):
    """Formatea montos en Guaraníes Paraguayos (₲)."""
    return f"₲ {monto:,.0f}".replace(",", ".")

def formatear_fecha(fecha_obj):
    """Formatea objetos fecha al estándar DD/MM/YYYY (ej: 13/07/2026)."""
    if pd.isna(fecha_obj) or fecha_obj is None:
        return ""
    if isinstance(fecha_obj, str):
        try:
            fecha_obj = datetime.strptime(fecha_obj, "%Y-%m-%d").date()
        except ValueError:
            return fecha_obj
    return fecha_obj.strftime("%d/%m/%Y")

# -----------------------------------------------------------------------------
# INICIALIZACIÓN
# -----------------------------------------------------------------------------
if 'cargado' not in st.session_state:
    cargar_datos()
    st.session_state.cargado = True

FECHA_ACTUAL = date.today()

st.title("🏦 Sistema de Facturación y Control Bancario - Banco Itaú")
st.caption(f"Moneda: Guaraníes (₲) | Fecha de hoy: {formatear_fecha(FECHA_ACTUAL)}")
st.markdown("---")

# -----------------------------------------------------------------------------
# MENÚ NAVEGACIÓN
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
    c1.metric("Saldo Inicial (Banco Itaú)", formatear_pyg(saldo_inicial))
    c2.metric("Saldo Actual en Banco Itaú", formatear_pyg(saldo_actual_banco), delta=formatear_pyg(ingresos_banco + egresos_banco))
    c3.metric("Total Facturado", formatear_pyg(total_facturado))
    c4.metric("Pendiente de Cobro", formatear_pyg(pendiente_cobro), delta_color="inverse")

    st.markdown("---")

    col_izq, col_der = st.columns([1, 1])

    with col_izq:
        st.subheader("📑 Extracto / Movimientos de Banco Itaú")
        if not st.session_state.banco.empty:
            df_banco_view = st.session_state.banco.copy()
            df_banco_view["Fecha"] = df_banco_view["Fecha"].apply(formatear_fecha)
            df_banco_view["Monto_Formateado"] = df_banco_view["Monto_PYG"].apply(formatear_pyg)
            st.dataframe(
                df_banco_view[["ID", "Fecha", "Tipo", "Concepto", "Cliente_Asociado", "Monto_Formateado"]],
                use_container_width=True
            )
        else:
            st.info("Aún no hay movimientos registrados en Banco Itaú.")

    with col_der:
        st.subheader("🧾 Facturas y Estado de Timbrados")
        if not st.session_state.facturas.empty:
            df_fact_view = st.session_state.facturas.copy()
            df_fact_view["Fecha"] = df_fact_view["Fecha"].apply(formatear_fecha)
            df_fact_view["Monto_Total"] = df_fact_view["Monto_PYG"].apply(formatear_pyg)
            df_fact_view["Monto_Cobrado"] = df_fact_view["Monto_Pagado"].apply(formatear_pyg)
            st.dataframe(
                df_fact_view[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado", "Estado", "Monto_Total"]],
                use_container_width=True
            )
        else:
            st.info("Aún no se han registrado facturas.")

# =============================================================================
# MÓDULO 2: REGISTRAR FACTURAS
# =============================================================================
elif menu == "📋 Registrar Facturas":
    st.header("📋 Registrar Nueva Factura Emitida")

    # Opciones de timbrado
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
            # Fecha por defecto: FECHA ACTUAL DE HOY
            fecha_emision = st.date_input("Fecha de Emisión (Por defecto Hoy)", value=FECHA_ACTUAL, format="DD/MM/YYYY")
            timbrado_estado = st.selectbox("Estado del Timbrado:", OPCIONES_TIMBRADO)
            
        submitted = st.form_submit_button("💾 Guardar Factura")

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
                    "Fecha": fecha_emision,
                    "Timbrado_Estado": timbrado_estado,
                    "Estado": "Pendiente",
                    "Monto_Pagado": 0.0
                }
                
                st.session_state.facturas = pd.concat([
                    st.session_state.facturas, 
                    pd.DataFrame([nueva_factura])
                ], ignore_index=True)
                
                guardar_datos()
                st.success(f"✅ Factura #{nuevo_id} registrada con fecha {formatear_fecha(fecha_emision)} y respaldada.")

    st.subheader("📋 Lista de Facturas Registradas")
    if not st.session_state.facturas.empty:
        df_display = st.session_state.facturas.copy()
        df_display["Fecha"] = df_display["Fecha"].apply(formatear_fecha)
        df_display["Monto_PYG"] = df_display["Monto_PYG"].apply(formatear_pyg)
        df_display["Monto_Pagado"] = df_display["Monto_Pagado"].apply(formatear_pyg)
        st.dataframe(df_display, use_container_width=True)

# =============================================================================
# MÓDULO 3: GESTIONAR TIMBRADOS (FIRMADO / DEVUELTO A IMPRENTA)
# =============================================================================
elif menu == "🏷️ Gestionar Timbrados":
    st.header("🏷️ Control de Timbrados: Firmados y Devueltos a Imprenta")

    if not st.session_state.facturas.empty:
        df_timbrados = st.session_state.facturas.copy()
        
        st.subheader("Listado de Estado de Timbrados")
        df_show = df_timbrados.copy()
        df_show["Fecha"] = df_show["Fecha"].apply(formatear_fecha)
        df_show["Monto_PYG"] = df_show["Monto_PYG"].apply(formatear_pyg)
        
        st.dataframe(
            df_show[["ID", "Cliente", "Contador", "Fecha", "Timbrado_Estado", "Monto_PYG"]],
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("✏️ Actualizar Estado de Timbrado")

        factura_sel = st.selectbox(
            "Seleccione la Factura a actualizar:",
            df_timbrados.apply(lambda r: f"Factura #{r['ID']} - Cliente: {r['Cliente']} (Estado actual: {r['Timbrado_Estado']})", axis=1)
        )

        id_fact_sel = int(factura_sel.split(" ")[0].replace("Factura", "").replace("#", ""))

        nuevo_estado_t = st.radio(
            "Marcar Nuevo Estado del Timbrado:",
            [
                "🔴 Pendiente de Firma",
                "🟡 Firmado (En proceso)",
                "🟢 Firmado y Devuelto a Imprenta"
            ]
        )

        if st.button("💾 Actualizar y Guardar Timbrado"):
            idx = st.session_state.facturas[st.session_state.facturas["ID"] == id_fact_sel].index[0]
            st.session_state.facturas.at[idx, "Timbrado_Estado"] = nuevo_estado_t
            guardar_datos()
            st.success(f"✅ Factura #{id_fact_sel} actualizada a '{nuevo_estado_t}' exitosamente.")
            st.rerun()
    else:
        st.info("Aún no hay facturas cargadas en el sistema.")

# =============================================================================
# MÓDULO 4: COBRANZAS DE FACTURAS
# =============================================================================
elif menu == "💵 Cobranzas de Facturas":
    st.header("💵 Registrar Cobranza -> Impacta en Banco Itaú")

    if not st.session_state.facturas.empty:
        facturas_pendientes = st.session_state.facturas[st.session_state.facturas["Estado"] != "Pagado Total"]
        
        if facturas_pendientes.empty:
            st.success("🎉 Todas las facturas registradas están cobradas totalmente.")
        else:
            opciones = facturas_pendientes.apply(
                lambda row: f"Factura #{row['ID']} - {row['Cliente']} (Total: {formatear_pyg(row['Monto_PYG'])} | Cobrado: {formatear_pyg(row['Monto_Pagado'])})", 
                axis=1
            )
            
            seleccion = st.selectbox("Seleccione la Factura a Cobrar:", opciones)
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
                    concepto_pago = st.text_input("Concepto / Referencia", value=f"Cobro Factura #{factura_id_sel} - {factura_actual['Cliente']}")
                    st.info("Al confirmar, este pago se acreditará de inmediato en el Banco Itaú.")

                btn_cobrar = st.form_submit_button("💳 Registrar Pago en Banco Itaú")

                if btn_cobrar:
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
                        "Fecha": fecha_pago,
                        "Tipo": "Ingreso (Cobro)",
                        "Concepto": concepto_pago,
                        "Cliente_Asociado": factura_actual["Cliente"],
                        "Factura_ID": factura_id_sel,
                        "Monto_PYG": float(monto_a_cobrar)
                    }
                    st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([nuevo_mov_banco])], ignore_index=True)

                    guardar_datos()
                    st.success(f"✅ Cobro de {formatear_pyg(monto_a_cobrar)} registrado para la fecha {formatear_fecha(fecha_pago)}.")
                    st.rerun()
    else:
        st.info("No existen facturas registradas en el sistema.")

# =============================================================================
# MÓDULO 5: MOVIMIENTOS BANCO ITAÚ
# =============================================================================
elif menu == "🏦 Movimientos Banco Itaú":
    st.header("🏦 Movimientos Directos de Banco Itaú (Ingresos & Egresos)")

    with st.form("form_mov_banco", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de Transacción", ["Ingreso Directo", "Egreso / Gasto"])
            concepto = st.text_input("Concepto / Descripción *", placeholder="Ej: Pago de alquiler, Honorarios contables")
            cliente_ref = st.text_input("Cliente / Proveedor Referencia", placeholder="Opcional")
        with col2:
            monto_mov = st.number_input("Monto en Guaraníes (₲) *", min_value=1.0, step=100000.0, value=250000.0)
            fecha_mov = st.date_input("Fecha del Movimiento", value=FECHA_ACTUAL, format="DD/MM/YYYY")

        btn_guardar_mov = st.form_submit_button("💾 Guardar Movimiento")

        if btn_guardar_mov:
            if not concepto:
                st.error("Debes ingresar un concepto.")
            else:
                monto_final = float(monto_mov) if tipo == "Ingreso Directo" else -float(monto_mov)
                nuevo_id_b = len(st.session_state.banco) + 1
                
                mov = {
                    "ID": nuevo_id_b,
                    "Fecha": fecha_mov,
                    "Tipo": tipo,
                    "Concepto": concepto.strip(),
                    "Cliente_Asociado": cliente_ref.strip() if cliente_ref else "N/A",
                    "Factura_ID": "N/A",
                    "Monto_PYG": monto_final
                }
                
                st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([mov])], ignore_index=True)
                guardar_datos()
                st.success(f"✅ Movimiento de {formatear_pyg(monto_final)} registrado con fecha {formatear_fecha(fecha_mov)}.")

    st.subheader("📋 Historial de Movimientos de Banco Itaú")
    if not st.session_state.banco.empty:
        df_banco_disp = st.session_state.banco.copy()
        df_banco_disp["Fecha"] = df_banco_disp["Fecha"].apply(formatear_fecha)
        df_banco_disp["Monto_PYG"] = df_banco_disp["Monto_PYG"].apply(formatear_pyg)
        st.dataframe(df_banco_disp, use_container_width=True)

# =============================================================================
# MÓDULO 6: CONFIGURAR SALDO INICIAL
# =============================================================================
elif menu == "⚙️ Configurar Saldo Inicial":
    st.header("⚙️ Configuración del Saldo Inicial - Banco Itaú")

    saldo_actual_conf = st.session_state.saldo_inicial
    st.write(f"**Saldo Inicial Configurado Activo:** {formatear_pyg(saldo_actual_conf)}")

    with st.form("form_saldo_inicial"):
        nuevo_saldo = st.number_input(
            "Establecer Saldo Inicial (en Guaraníes ₲):", 
            value=float(saldo_actual_conf), 
            step=1000000.0,
            min_value=0.0
        )
        btn_actualizar_saldo = st.form_submit_button("💾 Actualizar Saldo Inicial")

        if btn_actualizar_saldo:
            st.session_state.saldo_inicial = float(nuevo_saldo)
            guardar_datos()
            st.success(f"✅ Saldo Inicial actualizado a {formatear_pyg(nuevo_saldo)} y respaldado.")
            st.rerun()

# -----------------------------------------------------------------------------
# DESCARGA DE RESPALDO LOCAL EN BARRA LATERAL
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Copia de Seguridad")
if os.path.exists(EXCEL_FILE):
    with open(EXCEL_FILE, "rb") as f:
        st.sidebar.download_button(
            label="Descargar base_datos_itau.xlsx",
            data=f,
            file_name="base_datos_itau.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
