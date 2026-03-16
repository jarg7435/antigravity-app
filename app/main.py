import sys
import os
import importlib
from dotenv import load_dotenv
import streamlit as st

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# LAGEMA JARG74 - VERSION 6.70.2 - CORRECCIÓN ALINEACIONES
try:
    SECRET_CODE = st.secrets["ACCESS_CODE"]
except Exception:
    SECRET_CODE = os.getenv("ACCESS_CODE", "1234")

load_dotenv()

# --- AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.get("password_input") == SECRET_CODE:
        st.session_state.authenticated = True
        st.toast("🚀 Sistema Antigravity V6.70 Accedido", icon="✅")
    else:
        st.error("❌ Código de acceso incorrecto")

if not st.session_state.authenticated:
    st.set_page_config(page_title="Acceso Restringido", page_icon="🔒")
    st.title("🔐 Acceso LAGEMA")
    st.text_input("Introduce el código de acceso:", type="password", key="password_input", on_change=check_password)
    st.stop()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LAGEMA - Análisis de Fútbol", page_icon="⚽", layout="wide")

# Inicialización de Servicios (Asumiendo que existen en tu estructura)
from src.database.db_manager import DatabaseManager
from src.services.data_provider import DataProvider
from src.models.predictor import Predictor

db_manager = DatabaseManager()
data_provider = DataProvider()
predictor = Predictor()

# --- LÓGICA DE INTERFAZ ---
st.title("⚽ Panel de Análisis Predictivo")

# (Aquí va el resto de tu lógica de carga de partidos, filtros, etc.)
# Para efectos de la corrección, nos centramos en la sección del botón:

if "review_study" in st.session_state:
    rs = st.session_state.review_study
    
    st.subheader(f"Análisis: {rs.get('home_team')} vs {rs.get('away_team')}")
    
    col_a, col_b, col_c = st.columns(3)

    # ── Botón 1: Alineación (CORRECCIÓN INTEGRADA) ───────────────────────────────────────────────
    with col_a:
        # Determinar si ya es oficial para cambiar el estilo del botón
        can_reanalyze_rs = True
        if isinstance(rs.get("prediction"), dict):
            can_reanalyze_rs = not rs["prediction"].get("is_official", False)
        elif hasattr(rs.get("prediction"), "is_official"):
            can_reanalyze_rs = not rs["prediction"].is_official

        btn_label = "🔄 Alineación Oficial" if can_reanalyze_rs else "🔄 Alineación (Confirmada)"
        
        if st.button(btn_label, use_container_width=True,
                     type="primary" if can_reanalyze_rs else "secondary", key="rv_lineup"):
            with st.spinner("Buscando alineación..."):
                try:
                    from src.services.lineup_service import LineupFetcher as _LF
                    from src.models.base import Match
                    from src.utils.helpers import build_players as _build_players
                    
                    lf_rv = _LF(data_provider)
                    home_name_rs = rs.get("home_team")
                    away_name_rs = rs.get("away_team")
                    _match_date = rs.get("date")
                    _match_comp = rs.get("competition")

                    new_lu = lf_rv.fetch_smart_lineup(
                        home_name_rs, away_name_rs, _match_date, _match_comp
                    )
                    
                    # Fallback si no hay datos en web
                    if not new_lu.get("home") and not new_lu.get("away"):
                        upd_h = data_provider.get_team_data(home_name_rs)
                        upd_a = data_provider.get_team_data(away_name_rs)
                        new_lu = {
                            "home": [p.name for p in upd_h.players[:11]] if upd_h and upd_h.players else [],
                            "away": [p.name for p in upd_a.players[:11]] if upd_a and upd_a.players else [],
                            "is_official": False,
                            "source": "BD Interna",
                            "freshness": "fallback",
                            "uncertainty_penalty": 0.25
                        }

                    if new_lu.get("home") or new_lu.get("away"):
                        upd_h = data_provider.get_team_data(home_name_rs)
                        upd_a = data_provider.get_team_data(away_name_rs)
                        
                        if new_lu.get("home"):
                            upd_h.players = _build_players(new_lu["home"], home_name_rs)
                        if new_lu.get("away"):
                            upd_a.players = _build_players(new_lu["away"], away_name_rs)
                        
                        # Crear objeto Match para re-predicción
                        match_rs_obj = Match(
                            home_team=upd_h, 
                            away_team=upd_a, 
                            competition=_match_comp, 
                            date=_match_date
                        )
                        
                        # Extraer calidad para el Predictor
                        lineup_freshness = new_lu.get('freshness', 'fallback')
                        lineup_quality = {
                            'is_official': new_lu.get('is_official', False),
                            'uncertainty_penalty': new_lu.get('uncertainty_penalty', 0.25),
                            'integrity_issues': [] 
                        }
                        
                        # Ejecutar predicción con los nuevos datos
                        new_pred_rs = predictor.predict_match(
                            match_rs_obj, 
                            lineup_freshness=lineup_freshness,
                            lineup_quality=lineup_quality
                        )
                        
                        new_pred_rs.match_id = rs.get("match_id")
                        db_manager.save_prediction(new_pred_rs)
                        db_manager.save_match(match_rs_obj)
                        
                        # Actualizar estado de sesión
                        rs["prediction"] = new_pred_rs
                        st.session_state.review_study = rs
                        
                        st.success(f"✅ Alineación cargada correctamente.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error en alineación: {str(e)}")

    with col_b:
        if st.button("📊 Ver Estadísticas", use_container_width=True):
            st.info("Cargando detalles estadísticos...")

    with col_c:
        if st.button("❌ Cerrar", use_container_width=True):
            del st.session_state.review_study
            st.rerun()

# Resto del código de main.py (Footers, etc.)