import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="Sistema de Facturación y Bancos", layout="wide")

# Inicializar bases de datos simples en sesión (para pruebas)
if 'facturas' not in st.session_state:
    st.session_state.facturas = pd.DataFrame(columns=[
        "ID", "Cliente", "Contador", "Monto", "Fecha", "Timbrado", "Estado"
    ])

if 'banco' not in st.session_state:
    st.session_state.banco = pd.DataFrame(columns=[
        "Fecha", "Tipo", "Concepto", "Monto"
    ])

# Menú lateral
menu = st.sidebar.radio("Navegación", ["Registrar Factura", "Cobranzas", "Movimientos Bancarios", "Estado de Cuenta"])

# --- MÓDULO 1: REGISTRAR FACTURA ---
if menu == "Registrar Factura":
    st.header("📋 Registrar Nueva Factura Emitida")
    
    with st.form("form_factura"):
        col1, col2 = st.columns(2)
        with col1:
            cliente = st.text_input("Cliente")
            contador = st.text_input("Contador Asociado")
            monto = st.number_input("Monto", min_value=0.0, step=1000.0)
        with col2:
            fecha = st.date_input("Fecha de Emisión", date.today())
            timbrado = st.checkbox("¿Tiene Timbrado?")
            
        submitted = st.form_submit_button("Guardar Factura")
        if submitted:
            nuevo_id = len(st.session_state.facturas) + 1
            nueva_fila = {
                "ID": nuevo_id, "Cliente": cliente, "Contador": contador, 
                "Monto": monto, "Fecha": fecha, "Timbrado": timbrado, "Estado": "Pendiente"
            }
            st.session_state.facturas = pd.concat([st.session_state.facturas, pd.DataFrame([nueva_fila])], ignore_index=True)
            st.success(f"Factura #{nuevo_id} registrada con éxito.")

    st.subheader("Facturas Registradas")
    st.dataframe(st.session_state.facturas)

# --- MÓDULO 3: MOVIMIENTOS BANCO ---
elif menu == "Movimientos Bancarios":
    st.header("🏦 Movimientos Bancarios (Ingresos / Egresos)")
    
    with st.form("form_banco"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de Movimiento", ["Ingreso", "Egreso"])
            concepto = st.text_input("Concepto / Descripción")
        with col2:
            monto_banco = st.number_input("Monto", min_value=0.0, step=1000.0)
            fecha_banco = st.date_input("Fecha", date.today())
            
        submitted_banco = st.form_submit_button("Registrar Movimiento")
        if submitted_banco:
            monto_final = monto_banco if tipo == "Ingreso" else -monto_banco
            movimiento = {"Fecha": fecha_banco, "Tipo": tipo, "Concepto": concepto, "Monto": monto_final}
            st.session_state.banco = pd.concat([st.session_state.banco, pd.DataFrame([movimiento])], ignore_index=True)
            st.success("Movimiento bancario registrado.")

    st.dataframe(st.session_state.banco)

# --- MÓDULO 4: ESTADO DE CUENTA ---
elif menu == "Estado de Cuenta":
    st.header("📊 Estado de Cuenta Consolidado")
    
    saldo_banco = st.session_state.banco["Monto"].sum() if not st.session_state.banco.empty else 0.0
    total_facturado = st.session_state.facturas["Monto"].sum() if not st.session_state.facturas.empty else 0.0
    
    col1, col2 = st.columns(2)
    col1.metric("Saldo Actual en Banco", f"$ {saldo_banco:,.2f}")
    col2.metric("Total Facturado", f"$ {total_facturado:,.2f}")
