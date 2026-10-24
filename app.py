import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
import urllib.parse
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

# 🔑 ID DE TU GOOGLE SHEET NATIVO
SPREADSHEET_ID = "1yUoPjGAIvcDr08xMq0VhR6cOj2TP6c2eUfuPrLNkFy4"

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

# -----------------------------------------------------------------------------
# 2. ENCABEZADO GRAFIMASTER
# -----------------------------------------------------------------------------
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
# 3. CONEXIÓN Y OPERACIONES EN GOOGLE SHEETS
# -----------------------------------------------------------------------------
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def conectar_sheet():
    creds_dict = None
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
    elif "gcp_json" in st.secrets:
        try:
            creds_dict = json.loads(str(st.secrets["gcp_json"]).strip("'\""), strict=False)
        except Exception:
            pass

    if not creds_dict:
        return None, "Falta configurar las credenciales de Google en Secrets."

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

def obtener_o_crear_pestaña(sh, nombre_pestana, encabezados_default):
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
            ws = obtener_o_crear_pestaña(sh, pestana_nombre, encabezados_default)
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
            ws = obtener_o_crear_pestaña(sh, pestana_nombre, encabezados_default)
            ws.append_row([str(x) for x in fila_datos], value_input_option="USER_ENTERED")
            return True, None
        except Exception as e:
            return False, str(e)
    return False, f"Sin conexión: {err}"

def actualizar_fila(pestana_nombre, fila_num, datos_actualizados, encabezados_default):
    sh, err = conectar_sheet()
    if sh:
        try:
            ws = obtener_o_crear_pestaña(sh, pestana_nombre, encabezados_default)
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
            ws = obtener_o_crear_pestaña(sh, pestana_nombre, encabezados_default)
            ws.delete_rows(int(fila_num))
            return True, None
        except Exception as e:
            return False, str(e)
    return False, f"Sin conexión: {err}"

HEADERS_FACTURAS = ["Nº_Factura", "Cliente", "Monto_CLP", "Fecha_Emision", "Estado", "Monto_Pagado", "Saldo_Pendiente", "Estado_Timbrado"]
HEADERS_MOVIMIENTOS = ["ID_Movimiento", "Banco", "Tipo", "Monto_CLP", "Fecha", "Cliente_Asociado", "Detalle"]
HEADERS_CONFIG = ["Banco", "Saldo_Inicial_CLP"]

# -----------------------------------------------------------------------------
# 4. MENÚ PRINCIPAL
# -----------------------------------------------------------------------------
menu = st.radio(
    "Navegación:",
    ["📊 Resumen & Timbrados", "📄 Facturas Emitidas", "💳 Movimientos Bancarios", "🔄 Transferir Entre Bancos", "⚙️ Configurar Saldos Iniciales"],
    horizontal=True
)

st.markdown("---")

sh_test, err_test = conectar_sheet()
if not sh_test:
    st.warning(f"⚠️ **Atención:** No hay conexión con Google Sheets. Motivo: `{err_test}`")

# =============================================================================
# MÓDULO 1: RESUMEN DE BANCOS, DISPONIBILIDAD Y ESTADÍSTICAS DE TIMBRADOS
# =============================================================================
if menu == "📊 Resumen & Timbrados":
    st.subheader("🏦 Estado Financiero y Estadísticas de Timbrados (CLP)")

    df_config = obtener_datos("Config_Bancos", HEADERS_CONFIG)
    df_mov = obtener_datos("Movimientos_Banco", HEADERS_MOVIMIENTOS)
    df_fac = obtener_datos("Facturas", HEADERS_FACTURAS)

    saldo_ini_bice = 0.0
    saldo_ini_fala = 0.0

    if not df_config.empty:
        for _, r in df_config.iterrows():
            b_nom = str(r.get("banco", r.get("col_0", ""))).strip().lower()
            try:
                m_val = float(r.get("saldo_inicial_clp", r.get("saldo_inicial_usd", r.get("col_1", 0))))
            except Exception:
                m_val = 0.0

            if "bice" in b_nom:
                saldo_ini_bice = m_val
            elif "falabella" in b_nom:
                saldo_ini_fala = m_val

    ingresos_bice, egresos_bice = 0.0, 0.0
    ingresos_fala, egresos_fala = 0.0, 0.0

    if not df_mov.empty:
        for _, r in df_mov.iterrows():
            b = str(r.get("banco", r.get("col_1", ""))).strip().lower()
            tipo = str(r.get("tipo", r.get("col_2", ""))).strip().lower()
            try:
                monto = float(r.get("monto_clp", r.get("monto_usd", r.get("col_3", 0))))
            except Exception:
                monto = 0.0

            if "bice" in b:
                if "ingreso" in tipo: ingresos_bice += monto
                else: egresos_bice += monto
            elif "falabella" in b:
                if "ingreso" in tipo: ingresos_fala += monto
                else: egresos_fala += monto

    saldo_fin_bice = saldo_ini_bice + ingresos_bice - egresos_bice
    saldo_fin_fala = saldo_ini_fala + ingresos_fala - egresos_fala

    total_cobrado = 0.0
    total_pendiente = 0.0
    timbrados_firmados = 0
    timbrados_pendientes = 0

    if not df_fac.empty:
        for _, r in df_fac.iterrows():
            try:
                m_tot = float(r.get("monto_clp", r.get("monto_usd", r.get("col_2", 0))))
            except Exception:
                m_tot = 0.0
            try:
                m_pag = float(r.get("monto_pagado", r.get("col_5", 0)))
            except Exception:
                m_pag = 0.0
            try:
                m_pend = float(r.get("saldo_pendiente", r.get("col_6", m_tot - m_pag)))
            except Exception:
                m_pend = max(0.0, m_tot - m_pag)

            t_estado = str(r.get("estado_timbrado", r.get("col_7", "Pendiente de Firma"))).strip().lower()
            if "firmado" in t_estado:
                timbrados_firmados += 1
            else:
                timbrados_pendientes += 1

            total_cobrado += m_pag
            total_pendiente += m_pend

    disponibilidad_total = saldo_fin_bice + saldo_fin_fala + total_pendiente

    # Métricas Financieras
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🏦 Banco BICE", f"${saldo_fin_bice:,.0f} CLP", delta=f"Inicial: ${saldo_ini_bice:,.0f}")
    with c2:
        st.metric("💳 Banco Falabella", f"${saldo_fin_fala:,.0f} CLP", delta=f"Inicial: ${saldo_ini_fala:,.0f}")
    with c3:
        st.metric("⏳ Facturas Pendientes", f"${total_pendiente:,.0f} CLP", delta=f"Cobrado: ${total_cobrado:,.0f}", delta_color="normal")
    with c4:
        st.metric("💰 Disponibilidad Total", f"${disponibilidad_total:,.0f} CLP", help="Suma de Bancos + Facturas Pendientes de Pago")

    st.markdown("---")
    
    # 📊 ESTADÍSTICAS DE TIMBRADOS / FIRMAS
    st.markdown("### ✍️ Estadísticas de Timbrados y Firmas")
    total_timbrados = timbrados_firmados + timbrados_pendientes
    pct_firmado = (timbrados_firmados / total_timbrados * 100) if total_timbrados > 0 else 0.0

    st1, st2, st3 = st.columns(3)
    with st1:
        st.metric("📄 Total Timbrados Registrados", f"{total_timbrados} Facturas")
    with st2:
        st.metric("✅ Timbrados Firmados", f"{timbrados_firmados}", delta=f"{pct_firmado:.1f}% Completado")
    with st3:
        st.metric("⏳ Faltan por Firmar", f"{timbrados_pendientes}", delta=f"{100-pct_firmado:.1f}% Pendiente", delta_color="inverse")

    st.markdown("---")
    st.markdown("### 📋 Historial de Movimientos Bancarios")
    if not df_mov.empty:
        st.dataframe(df_mov, use_container_width=True)
    else:
        st.info("No hay movimientos registrados en los bancos.")

# =============================================================================
# MÓDULO 2: FACTURAS EMITIDAS (CON CAMPO Nº FACTURA, TIMBRADO Y RECIBO)
# =============================================================================
elif menu == "📄 Facturas Emitidas":
    st.subheader("📄 Registro y Gestión de Facturas Emitidas (CLP)")

    with st.expander("➕ Emitir Nueva Factura", expanded=True):
        with st.form("form_factura", clear_on_submit=True):
            f1, f2 = st.columns(2)
            with f1:
                f_num_custom = st.text_input("Nº de Factura *", placeholder="Ej: 1024 o FAC-00125")
                f_cli = st.text_input("Cliente *", placeholder="Ej: Empresa ABC SpA")
                f_monto = st.number_input("Monto Total (CLP) *", min_value=1.0, step=10000.0)
            with f2:
                f_fecha = st.date_input("Fecha de Emisión", value=date.today())
                f_estado = st.selectbox("Estado de Pago Inicial", ["Pendiente", "Pagado"])
                f_timbrado = st.selectbox("Estado de Timbrado / Firma", ["Pendiente de Firma", "Firmado"])
                banco_destino = st.selectbox("Si está Pagada, ¿a qué Banco ingresa?", ["Bice", "Falabella"])

            sub_fact = st.form_submit_button("💾 Guardar Factura")
            if sub_fact:
                if not f_num_custom.strip():
                    st.error("Debes ingresar el Nº de Factura.")
                elif not f_cli.strip():
                    st.error("Debes ingresar el nombre del cliente.")
                else:
                    new_id = f_num_custom.strip()
                    m_pagado = f_monto if f_estado == "Pagado" else 0.0
                    s_pendiente = 0.0 if f_estado == "Pagado" else f_monto
                    datos_fac = [new_id, f_cli.strip(), f_monto, str(f_fecha), f_estado, m_pagado, s_pendiente, f_timbrado]
                    ok, err = agregar_fila("Facturas", datos_fac, HEADERS_FACTURAS)
                    
                    if ok:
                        if f_estado == "Pagado":
                            id_m = f"MOV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            reg_mov = [id_m, banco_destino, "Ingreso", f_monto, str(f_fecha), f_cli.strip(), f"Pago de Factura Nº {new_id}"]
                            agregar_fila("Movimientos_Banco", reg_mov, HEADERS_MOVIMIENTOS)
                            
                            st.session_state["ultimo_recibo"] = {
                                "num_fac": new_id,
                                "cliente": f_cli.strip(),
                                "monto": f_monto,
                                "fecha": str(f_fecha),
                                "banco": banco_destino
                            }
                        st.success(f"Factura Nº {new_id} registrada correctamente.")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {err}")

    # Panel del Recibo de Dinero si fue generado
    if "ultimo_recibo" in st.session_state:
        rec = st.session_state["ultimo_recibo"]
        st.markdown(
            f"""
            <div class='recibo-box'>
                <h3 style='color: #15803d; margin-top: 0;'>🧾 RECIBO DE DINERO GENERADO</h3>
                <p><b>Recibimos de:</b> {rec['cliente']}<br>
                <b>Monto Pago:</b> ${rec['monto']:,.0f} CLP<br>
                <b>Concepto:</b> Pago de Factura Nº {rec['num_fac']}<br>
                <b>Fecha Pago:</b> {rec['fecha']} | <b>Banco Destino:</b> {rec['banco']}<br>
                <b>Emitido por:</b> Grafimaster</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        txt_recibo = f"🧾 *RECIBO DE DINERO - GRAFIMASTER*\n\nRecibimos de *{rec['cliente']}* la suma de *$ {rec['monto']:,.0f} CLP* en concepto de pago de Factura Nº *{rec['num_fac']}* con fecha *{rec['fecha']}* (Ingresado a {rec['banco']}).\n\n¡Muchas gracias por su preferencia!"
        url_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(txt_recibo)}"
        
        c_wa, c_close = st.columns([1, 1])
        with c_wa:
            st.markdown(f'<a href="{url_wa}" target="_blank" style="text-decoration:none;"><div style="background:#22c55e;color:white;padding:10px;border-radius:8px;text-align:center;font-weight:bold;">🟢 Enviar Recibo por WhatsApp</div></a>', unsafe_allow_html=True)
        with c_close:
            if st.button("❌ Cerrar Vista de Recibo"):
                del st.session_state["ultimo_recibo"]
                st.rerun()

    st.markdown("### 📚 Listado de Facturas Emitidas")
    df_fac = obtener_datos("Facturas", HEADERS_FACTURAS)

    if not df_fac.empty:
        for idx, r in df_fac.iterrows():
            id_f = str(r.get("nº_factura", r.get("n°_factura", r.get("id_factura", r.get("col_0", "")))))
            cli_f = str(r.get("cliente", r.get("col_1", "")))
            try:
                monto_f = float(r.get("monto_clp", r.get("monto_usd", r.get("col_2", 0))))
            except Exception:
                monto_f = 0.0
            fecha_f = str(r.get("fecha_emision", r.get("col_3", "")))
            estado_f = str(r.get("estado", r.get("col_4", "Pendiente")))
            try:
                pagado_f = float(r.get("monto_pagado", r.get("col_5", 0)))
            except Exception:
                pagado_f = 0.0
            try:
                saldo_f = float(r.get("saldo_pendiente", r.get("col_6", monto_f)))
            except Exception:
                saldo_f = monto_f
            timbrado_f = str(r.get("estado_timbrado", r.get("col_7", "Pendiente de Firma")))

            fila_num = r.get("_fila_num")

            col_info, col_acc = st.columns([0.8, 0.2])

            with col_info:
                st.markdown(
                    f"""
                    <div style="background: white; padding: 15px; border-radius: 10px; border-left: 5px solid {'#22c55e' if estado_f == 'Pagado' else '#f59e0b'}; margin-bottom: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);">
                        📄 <b>Nº Factura:</b> {id_f} | 👤 <b>Cliente:</b> {cli_f} | 📅 <b>Fecha:</b> {fecha_f}<br>
                        💵 <b>Monto Facturado:</b> ${monto_f:,.0f} CLP | 🟢 <b>Cobrado en Banco:</b> ${pagado_f:,.0f} CLP | ⏳ <b>Pendiente:</b> ${saldo_f:,.0f} CLP<br>
                        ✍️ <b>Estado Timbrado:</b> <span style="color: {'#16a34a' if timbrado_f == 'Firmado' else '#dc2626'}; font-weight: bold;">{timbrado_f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col_acc:
                ca1, ca2 = st.columns(2)
                with ca1:
                    if st.button("✏️", key=f"edit_fac_{fila_num}_{idx}", help="Editar / Cobrar / Firmar Factura"):
                        st.session_state[f"edit_fac_mode_{fila_num}"] = not st.session_state.get(f"edit_fac_mode_{fila_num}", False)
                with ca2:
                    if st.button("❌", key=f"del_fac_{fila_num}_{idx}", help="Eliminar Factura"):
                        ok_del, err_del = eliminar_fila("Facturas", fila_num, HEADERS_FACTURAS)
                        if ok_del:
                            st.success("Factura eliminada.")
                            st.rerun()
                        else:
                            st.error(f"Error borrando: {err_del}")

            if st.session_state.get(f"edit_fac_mode_{fila_num}", False):
                with st.container():
                    st.info(f"✏️ **Editando / Registrar Cobro de Factura Nº:** {id_f}")
                    with st.form(f"form_edit_fac_{fila_num}"):
                        fe1, fe2 = st.columns(2)
                        with fe1:
                            id_f_edit = st.text_input("Nº de Factura", value=id_f, key=f"num_e_{fila_num}")
                            cli_edit = st.text_input("Cliente", value=cli_f, key=f"cli_e_{fila_num}")
                            monto_edit = st.number_input("Monto Total (CLP)", value=monto_f, min_value=1.0, step=10000.0, key=f"m_e_{fila_num}")
                        with fe2:
                            try:
                                default_dt = pd.to_datetime(fecha_f).date()
                            except Exception:
                                default_dt = date.today()
                            fecha_edit = st.date_input("Fecha Emisión", value=default_dt, key=f"f_e_{fila_num}")
                            estado_edit = st.selectbox("Estado de Pago", ["Pendiente", "Pagado"], index=0 if estado_f == "Pendiente" else 1, key=f"est_e_{fila_num}")
                            timbrado_edit = st.selectbox("Estado Timbrado / Firma", ["Pendiente de Firma", "Firmado"], index=0 if "Pendiente" in timbrado_f else 1, key=f"timb_e_{fila_num}")

                        pagado_edit = st.number_input("Monto Cobrado que ingresa al Banco (CLP)", value=(monto_edit if estado_edit == "Pagado" else pagado_f), min_value=0.0, max_value=monto_edit, step=10000.0, key=f"pag_e_{fila_num}")
                        banco_cobro = st.selectbox("Banco donde se deposita el cobro", ["Bice", "Falabella"], key=f"bco_e_{fila_num}")

                        btn_save_fac = st.form_submit_button("💾 Guardar y Generar Recibo")

                        if btn_save_fac:
                            saldo_calc = max(0.0, monto_edit - pagado_edit)
                            estado_final = "Pagado" if saldo_calc == 0.0 else estado_edit
                            
                            datos_act = [
                                id_f_edit.strip(),
                                cli_edit.strip(),
                                monto_edit,
                                str(fecha_edit),
                                estado_final,
                                pagado_edit,
                                saldo_calc,
                                timbrado_edit
                            ]
                            ok_upd, err_upd = actualizar_fila("Facturas", fila_num, datos_act, HEADERS_FACTURAS)
                            
                            if ok_upd:
                                diferencia_cobrada = pagado_edit - pagado_f
                                if diferencia_cobrada > 0:
                                    id_m = f"MOV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                    reg_mov = [id_m, banco_cobro, "Ingreso", diferencia_cobrada, str(date.today()), cli_edit.strip(), f"Abono / Pago de Factura Nº {id_f_edit}"]
                                    agregar_fila("Movimientos_Banco", reg_mov, HEADERS_MOVIMIENTOS)

                                    st.session_state["ultimo_recibo"] = {
                                        "num_fac": id_f_edit.strip(),
                                        "cliente": cli_edit.strip(),
                                        "monto": diferencia_cobrada,
                                        "fecha": str(date.today()),
                                        "banco": banco_cobro
                                    }

                                st.success("Factura y banco actualizados correctamente.")
                                st.session_state[f"edit_fac_mode_{fila_num}"] = False
                                st.rerun()
                            else:
                                st.error(f"Error al actualizar: {err_upd}")
    else:
        st.info("No hay facturas emitidas.")

# =============================================================================
# MÓDULO 3: REGISTRO DE MOVIMIENTOS
# =============================================================================
elif menu == "💳 Movimientos Bancarios":
    st.subheader("💸 Registrar Movimiento Directo de Banco (CLP)")

    with st.form("form_movimiento", clear_on_submit=True):
        cm1, cm2, cm3 = st.columns(3)
        with cm1:
            banco_sel = st.selectbox("Banco *", ["Bice", "Falabella"])
        with cm2:
            tipo_mov = st.selectbox("Tipo *", ["Ingreso", "Egreso"])
        with cm3:
            monto_mov = st.number_input("Monto (CLP) *", min_value=1.0, step=10000.0)

        cm4, cm5 = st.columns(2)
        with cm4:
            fecha_mov = st.date_input("Fecha", value=date.today())
        with cm5:
            cliente_mov = st.text_input("Cliente / Proveedor / Detalle")

        detalle_mov = st.text_area("Observaciones")

        sub_mov = st.form_submit_button("💾 Registrar Movimiento")
        if sub_mov:
            id_m = f"MOV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            registro_mov = [id_m, banco_sel, tipo_mov, monto_mov, str(fecha_mov), cliente_mov.strip(), detalle_mov.strip()]
            ok, err = agregar_fila("Movimientos_Banco", registro_mov, HEADERS_MOVIMIENTOS)
            if ok:
                st.success("Movimiento registrado en el banco.")
                st.rerun()
            else:
                st.error(f"Error: {err}")

# =============================================================================
# MÓDULO 4: TRANSFERENCIAS ENTRE BANCOS
# =============================================================================
elif menu == "🔄 Transferir Entre Bancos":
    st.subheader("🔄 Traspaso de Fondos entre Bancos (CLP)")

    with st.form("form_traspaso", clear_on_submit=True):
        ct1, ct2 = st.columns(2)
        with ct1:
            banco_origen = st.selectbox("Banco de ORIGEN (Sale dinero) *", ["Bice", "Falabella"], index=0)
        with ct2:
            banco_destino = st.selectbox("Banco de DESTINO (Entra dinero) *", ["Falabella", "Bice"], index=0)

        ct3, ct4 = st.columns(2)
        with ct3:
            monto_traspaso = st.number_input("Monto a Transferir (CLP) *", min_value=1.0, step=50000.0)
        with ct4:
            fecha_traspaso = st.date_input("Fecha del Traspaso", value=date.today())

        glosa_traspaso = st.text_input("Motivo / Observaciones del Traspaso", value="Traspaso interno de fondos")

        sub_traspaso = st.form_submit_button("🔁 Ejecutar Transferencia")

        if sub_traspaso:
            if banco_origen == banco_destino:
                st.error("El banco de origen y destino deben ser diferentes.")
            else:
                id_egr = f"TRF-OUT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                reg_egr = [id_egr, banco_origen, "Egreso", monto_traspaso, str(fecha_traspaso), "Traspaso Interno", f"{glosa_traspaso} (Hacia {banco_destino})"]
                ok1, err1 = agregar_fila("Movimientos_Banco", reg_egr, HEADERS_MOVIMIENTOS)

                id_ing = f"TRF-IN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                reg_ing = [id_ing, banco_destino, "Ingreso", monto_traspaso, str(fecha_traspaso), "Traspaso Interno", f"{glosa_traspaso} (Desde {banco_origen})"]
                ok2, err2 = agregar_fila("Movimientos_Banco", reg_ing, HEADERS_MOVIMIENTOS)

                if ok1 and ok2:
                    st.success(f"✅ Transferencia realizada con éxito: ${monto_traspaso:,.0f} CLP transferidos de {banco_origen} a {banco_destino}.")
                    st.rerun()
                else:
                    st.error(f"Error registrando transferencia: {err1 or err2}")

# =============================================================================
# MÓDULO 5: SALDOS INICIALES
# =============================================================================
elif menu == "⚙️ Configurar Saldos Iniciales":
    st.subheader("⚙️ Definir Saldos Iniciales en Bancos (CLP)")

    with st.form("form_saldos_ini"):
        s_bice = st.number_input("Saldo Inicial BICE (CLP)", min_value=0.0, step=100000.0)
        s_fala = st.number_input("Saldo Inicial Falabella (CLP)", min_value=0.0, step=100000.0)

        sub_ini = st.form_submit_button("💾 Guardar Saldos Iniciales")
        if sub_ini:
            ok1, _ = agregar_fila("Config_Bancos", ["Bice", s_bice], HEADERS_CONFIG)
            ok2, _ = agregar_fila("Config_Bancos", ["Falabella", s_fala], HEADERS_CONFIG)
            if ok1 and ok2:
                st.success("Saldos iniciales guardados.")
                st.rerun()
            else:
                st.error("Error al guardar saldos iniciales.")
