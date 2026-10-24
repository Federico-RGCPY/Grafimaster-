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
#
