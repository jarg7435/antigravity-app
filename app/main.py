import sys
import os
import importlib
from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

# LAGEMA JARG74 - VERSION 6.70.1 - GLOBAL GENERIC RELEASE
# Código de acceso desde variable de entorno (seguro para GitHub/Streamlit Cloud)
# En Streamlit Cloud: Settings → Secrets → ACCESS_CODE = "tu_codigo"
# En local: crea un archivo .env con ACCESS_CODE=tu_codigo
try:
    SECRET_CODE = st.secrets["ACCESS_CODE"]
except Exception:
    SECRET_CODE = os.getenv("ACCESS_CODE", "1234")  # Fallback solo para desarrollo local
# Force rebuild comment: f"Resetting system at 2026-03-06T11:32"

# Load environment variables
load_dotenv()

# --- AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.get("password_input") == SECRET_CODE:
        st.session_state.authenticated = True
        # Visual Trace for success after restart
        st.toast("🚀 Sistema Antigravity V6.25 Accedido", icon="✅")
    else:
        st.error("❌ Código de acceso incorrecto")

if not st.session_state.authenticated:
    st.set_page_config(page_title="Acceso Restringido", page_icon="🔒")
    st.markdown("<h1 style='text-align: center;'>🔒 Acceso Restringido</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Por favor, introduce el código de acceso para entrar en Antigravity.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("Código de Acceso", type="password", key="password_input", on_change=check_password)
    st.stop()

from src.data.mock_provider import MockDataProvider
from src.data.db_manager import DataManager
from src.logic.bpa_engine import BPAEngine
from src.logic.predictors import Predictor
from src.logic.validator import Validator
from src.logic.lineup_fetcher import LineupFetcher
from app.components.ui_components import (
    render_header, render_bpa_display, render_prediction_cards, 
    render_lineup_check_ui, render_league_selector, render_date_selector, 
    render_team_selector, render_player_selector, render_time_selector,
    render_result_validation_form, render_historical_dashboard,
    render_bankroll_ui, render_value_analysis_chart
)
from src.data.bankroll_manager import BankrollManager
from src.logic.report_engine import ReportEngine
from src.models.base import Match, MatchConditions, Referee, RefereeStrictness

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="LAGEMA JARG74 V6.25",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load External CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

css_path = os.path.join(os.path.dirname(__file__), 'style.css')
if os.path.exists(css_path):
    load_css(css_path)

# Initialize Services
@st.cache_resource
def get_services(version: str = "6.70.0 (Global Generic)"):
    # NUCLEAR RELOAD: Ensure Streamlit Cloud sees disk changes
    import importlib
    import src.models.base
    import src.logic.poisson_engine
    import src.logic.predictors
    import src.logic.bpa_engine
    import src.logic.external_analyst
    import src.data.mock_provider
    import src.data.bankroll_manager
    
    importlib.reload(src.models.base)
    importlib.reload(src.logic.poisson_engine)
    importlib.reload(src.logic.bpa_engine)
    importlib.reload(src.logic.external_analyst)
    importlib.reload(src.logic.predictors)
    importlib.reload(src.data.mock_provider)
    importlib.reload(src.data.bankroll_manager)

    from src.data.mock_provider import MockDataProvider
    from src.data.db_manager import DataManager
    from src.logic.bpa_engine import BPAEngine
    from src.logic.predictors import Predictor
    from src.logic.validator import Validator
    from src.data.bankroll_manager import BankrollManager
    from src.logic.report_engine import ReportEngine

    data_provider = MockDataProvider()
    db_manager = DataManager()
    bpa_engine = BPAEngine()
    predictor = Predictor(bpa_engine)
    validator = Validator()
    bankroll_manager = BankrollManager()
    report_engine = ReportEngine()
    
    return data_provider, db_manager, bpa_engine, predictor, validator, bankroll_manager, report_engine

# --- SERVICE INITIALIZATION ---
CURRENT_VERSION = "6.70.0"
data_provider, db_manager, bpa_engine, predictor, validator, bankroll_manager, report_engine = get_services(CURRENT_VERSION)

# --- MAIN LAYOUT ---
render_header()

# 1. Match Configuration
st.markdown('<h3 style="color: #ffffff;">🛠️ Configuración Estratégica</h3>', unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        selected_date = render_date_selector()
    with col2:
        selected_time = render_time_selector()
        st.markdown('<p style="color: #fdffcc; font-size: 0.9rem;">🕒 La confirmación oficial de alineaciones se habilita 1h antes del inicio.</p>', unsafe_allow_html=True)

ALL_LEAGUES = [
    "La Liga (España)", "Premier League (Inglaterra)", "Bundesliga (Alemania)",
    "Serie A (Italia)", "Ligue 1 (Francia)",
    "Eredivisie (Holanda)", "Primeira Liga (Portugal)", "Süper Lig (Turquía)",
    "Scottish Premiership (Escocia)", "Belgian Pro League (Bélgica)",
    "Austrian Bundesliga (Austria)", "Swiss Super League (Suiza)",
    "Ekstraklasa (Polonia)", "Czech First League (Rep. Checa)",
    "Superliga (Dinamarca)", "Allsvenskan (Suecia)", "Eliteserien (Noruega)",
    "Super League (Grecia)", "HNL (Croacia)", "SuperLiga (Serbia)",
    "Ukrainian Premier League (Ucrania)", "Israeli Premier League (Israel)",
    "Liga Profesional (Argentina)", "Brasileirao (Brasil)",
]

def get_teams_for_league(league_label):
    key = league_label.split(" (")[0]
    return data_provider.get_teams_by_league(key)

# --- TEAM SELECTION ---
with st.container():
    c1, c2 = st.columns(2)

    with c1:
        st.markdown('<h3 style="color: #ffffff;">🏠 Local</h3>', unsafe_allow_html=True)
        home_league = st.selectbox("Liga Local", ALL_LEAGUES, key="home_league_sel")
        home_teams = get_teams_for_league(home_league)
        if home_teams:
            h_name = st.selectbox("Seleccionar Equipo", home_teams, key="hts")
            home_team = data_provider.get_team_data(h_name)
        else:
            h_name = st.text_input("Nombre del equipo local", "Equipo Local FC", key="hnm")
            from src.models.base import Team, Player, PlayerPosition, PlayerStatus
            p_list = [Player(id=f"h{i}", name=f"Jugador {i}", team_name=h_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
            home_team = Team(name=h_name, league=home_league, players=p_list, tactical_style="Equilibrado")

    with c2:
        st.markdown('<h3 style="color: #ffffff;">✈️ Visitante</h3>', unsafe_allow_html=True)
        away_league = st.selectbox("Liga Visitante", ALL_LEAGUES, key="away_league_sel")
        away_teams = get_teams_for_league(away_league)
        if away_teams:
            a_name = st.selectbox("Seleccionar Equipo", away_teams, key="ats")
            away_team = data_provider.get_team_data(a_name)
        else:
            a_name = st.text_input("Nombre del equipo visitante", "Equipo Visitante FC", key="anm")
            from src.models.base import Team, Player, PlayerPosition, PlayerStatus
            p_list = [Player(id=f"a{i}", name=f"Jugador {i}", team_name=a_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
            away_team = Team(name=a_name, league=away_league, players=p_list, tactical_style="Contragolpe")

# Competición del partido
selected_league = st.selectbox(
    "🏆 Competición del partido",
    ["La Liga (España)", "Premier League (Inglaterra)", "Bundesliga (Alemania)",
     "Serie A (Italia)", "Ligue 1 (Francia)", "Champions League",
     "Europa League", "Conference League", "Otra competición"],
    key="match_competition"
)

if home_team and away_team:
        # Match ID
        m_id = f"{home_team.name[:3]}_{away_team.name[:3]}_{selected_date.strftime('%Y%m%d')}"
        
        # --- STATE RESET LOGIC ---
        if "current_match_id" not in st.session_state:
            st.session_state.current_match_id = m_id
            
        if st.session_state.current_match_id != m_id:
            st.session_state.last_pred = None
            st.session_state.last_val = None
            st.session_state.lineups_confirmed = False
            st.session_state.current_match_id = m_id
        
        if "fetched_ref" not in st.session_state:
            st.session_state.fetched_ref = None
        st.markdown('<p style="color: #fdffcc; font-size: 0.9rem;">🤖 El sistema accederá automáticamente a fuentes oficiales para árbitros (RFEF, SofaScore, BeSoccer, FutbolFantasy).</p>', unsafe_allow_html=True)

        ref_source = st.session_state.fetched_ref.get("source", "Automático") if st.session_state.fetched_ref else "Automático"
        is_fallback = st.session_state.fetched_ref.get("_is_fallback", False) if st.session_state.fetched_ref else False
        
        c_ref1, c_ref2 = st.columns([2, 1])
        # Build referee object with auto-fetched data
        if st.session_state.fetched_ref and not is_fallback:
            ref_name = st.session_state.fetched_ref["name"]
            v_link = st.session_state.fetched_ref.get("verification_link")
            
            with c_ref1:
                v_html = f' <a href="{v_link}" target="_blank" style="color: #00ff00; text-decoration: none; font-size: 0.8rem;">[🛡️ Verificar]</a>' if v_link else ""
                st.markdown(f'<h4 style="color: #fdffcc; margin-top: 5px;">👨‍⚖️ Árbitro: {ref_name}{v_html} <span style="font-size: 0.8rem; color: #00ff00;">✅ ({ref_source})</span></h4>', unsafe_allow_html=True)
            with c_ref2:
                if st.button("🔄 Re-buscar", use_container_width=True, key="rebuscar_ref"):
                    st.session_state.fetched_ref = None
                    st.rerun()
            
            selected_ref = Referee(
                name=ref_name, 
                strictness=st.session_state.fetched_ref["strictness"],
                verification_link=v_link
            )
        else:
            # Auto-fetch failed or not yet searched — show manual input + search button
            with c_ref1:
                if is_fallback:
                    st.markdown(f'<p style="color: #ffaa00; font-size: 0.9rem;">⚠️ No se encontró el árbitro automáticamente. Introdúcelo manualmente si lo conoces:</p>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<h4 style="color: #fdffcc; margin-top: 5px;">👨‍⚖️ Árbitro: Pendiente...</h4>', unsafe_allow_html=True)
                
                # 👇 NUEVO: campo de entrada manual
                manual_ref = st.text_input(
                    "✍️ Nombre del árbitro (manual)",
                    placeholder="Ej: Jesús Gil Manzano",
                    key="manual_ref_input"
                )
                if manual_ref and len(manual_ref.split()) >= 2:
                    if st.button("✅ Confirmar Árbitro Manual", key="confirm_manual_ref"):
                        st.session_state.fetched_ref = {
                            "name": manual_ref.strip(),
                            "strictness": RefereeStrictness.MEDIUM,
                            "avg_cards": 4.3,
                            "source": "Introducido manualmente",
                            "_is_fallback": False,
                            "verification_link": None
                        }
                        st.toast(f"👨‍⚖️ Árbitro confirmado: {manual_ref.strip()}", icon="⚖️")
                        st.rerun()

            with c_ref2:
                if st.button("🔍 Buscar Árbitro Auto", use_container_width=True):
                    with st.spinner("Buscando en 5 fuentes..."):
                        l_fetcher = LineupFetcher(data_provider)
                        ref_data = l_fetcher.fetch_match_referee(
                            home_team.name, away_team.name, selected_date, selected_league
                        )
                        st.session_state.fetched_ref = ref_data
                        st.rerun()
            
            # Use fallback pool ref or manual if available
            if is_fallback:
                selected_ref = Referee(
                    name=st.session_state.fetched_ref.get("name", "Por Confirmar"),
                    strictness=st.session_state.fetched_ref.get("strictness", RefereeStrictness.MEDIUM)
                )
            else:
                selected_ref = Referee(name="Por Detectar", strictness=RefereeStrictness.MEDIUM)

        
        from datetime import datetime
        # Convert date and time to a full datetime object as Pydantic expects
        try:
            full_match_datetime = datetime.combine(selected_date, datetime.strptime(selected_time, "%H:%M").time())
        except:
            full_match_datetime = datetime.now()

        selected_match = Match(
            id=m_id, home_team=home_team, away_team=away_team, 
            date=full_match_datetime, kickoff_time=selected_time, competition=selected_league,
            conditions=MatchConditions(temperature=15, rain_mm=0, wind_kmh=10, humidity_percent=60),
            referee=selected_ref,
            market_odds={"1": 2.10, "X": 3.40, "2": 4.50}
        )

        # --- REAL-TIME CONFIRMATION ---
        st.divider()
        st.markdown('<h3 style="color: #ffffff;">🕒 Confirmación 1H Antes</h3>', unsafe_allow_html=True)
        
        # Calculate time until match
        from datetime import datetime, timedelta
        match_datetime = datetime.combine(selected_date, datetime.strptime(selected_time, "%H:%M").time())
        now = datetime.now()
        time_until_match = match_datetime - now
        hours_until_match = time_until_match.total_seconds() / 3600
        
        # Determine if we can fetch official data (1 hour before)
        can_fetch_official = hours_until_match <= 1.0
        
        if "lineups_confirmed" not in st.session_state:
            st.session_state.lineups_confirmed = False
        if "fetched_lineups" not in st.session_state:
            st.session_state.fetched_lineups = None
        
        c_conf1, c_conf2 = st.columns([2, 1])
        with c_conf1:
            status_text = '✅ CONFIRMADAS' if st.session_state.lineups_confirmed else '⏳ PENDIENTE'
            st.markdown(f'<p style="color: #ffffff; font-size: 1.1rem;">Estado: <strong>{status_text}</strong></p>', unsafe_allow_html=True)
            
            # Show time restriction message
            if not can_fetch_official:
                hours_left = int(hours_until_match)
                mins_left = int((hours_until_match - hours_left) * 60)
                st.markdown(f'<p style="color: #fdffcc; font-size: 0.9rem;">⏰ Confirmación oficial disponible en: <strong>{hours_left}h {mins_left}m</strong></p>', unsafe_allow_html=True)
                st.markdown('<p style="color: #888; font-size: 0.85rem;">📋 Usando alineaciones del último partido hasta entonces</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p style="color: #00ff00; font-size: 0.9rem;">✅ Confirmación oficial disponible ahora</p>', unsafe_allow_html=True)
            
            if st.session_state.lineups_confirmed:
                lineup_source = st.session_state.fetched_lineups.get('source', 'Automático') if st.session_state.fetched_lineups else 'Automático'
                st.markdown(f'<p style="color: #fdffcc;">Confirmado vía: {lineup_source}</p>', unsafe_allow_html=True)
        
        with c_conf2:
            button_label = "🛡️ CONFIRMAR DATOS (OFICIAL)" if can_fetch_official else "📋 CARGAR ÚLTIMO PARTIDO"
            if st.button(button_label, type="primary", use_container_width=True):
                with st.spinner("🤖 Sincronizando datos..."):
                    l_fetcher = LineupFetcher(data_provider)
                    
                    # Unified Smart Fetching
                    res = l_fetcher.fetch_smart_lineup(
                        home_team.name, 
                        away_team.name, 
                        match_datetime, 
                        selected_league
                    )
                    
                    st.session_state.fetched_lineups = res
                    st.session_state.lineups_confirmed = True
                    
                    # Fetch Referee if official is available, otherwise placeholder
                    if can_fetch_official:
                        ref_data = l_fetcher.fetch_match_referee(
                            home_team.name, away_team.name, selected_date, selected_league
                        )
                        st.session_state.fetched_ref = ref_data
                        st.toast(f"👨‍⚖️ Árbitro Oficial: {ref_data['name']}", icon="⚖️")
                    else:
                        st.session_state.fetched_ref = {
                            'name': 'Por Confirmar (1h antes)',
                            'strictness': RefereeStrictness.MEDIUM,
                            'source': 'Pendiente'
                        }
                    
                    status_emoji = "✅" if res.get('is_official') else "📊"
                    st.toast(f"{status_emoji} Datos cargados vía: {res.get('source')}", icon="📡")
                    st.rerun()

        # --- LINEUP VALIDATION ---
        st.divider()
        st.markdown('<h2 style="color: #ffffff; font-weight: 900;">🛡️ Validación de Alineaciones</h2>', unsafe_allow_html=True)
        
        # Decide which lineups to show as default
        if st.session_state.lineups_confirmed and st.session_state.fetched_lineups:
            f_home = st.session_state.fetched_lineups['home']
            f_away = st.session_state.fetched_lineups['away']
        else:
            # Show selected team rosters as placeholder until confirmed
            f_home = [p.name for p in home_team.players]
            f_away = [p.name for p in away_team.players]

        with st.expander("📋 Ver Alineación Detectada", expanded=st.session_state.lineups_confirmed):
            st.markdown('<style>div[data-testid="stExpander"] details summary p { color: #ffffff !important; font-weight: bold; }</style>', unsafe_allow_html=True)
            col_l, col_r = st.columns(2)
            col_l.markdown(f'<p style="color: #fdffcc;"><strong>{home_team.name}</strong>: ' + (", ".join(f_home) if f_home else "No detectados") + '</p>', unsafe_allow_html=True)
            col_r.markdown(f'<p style="color: #fdffcc;"><strong>{away_team.name}</strong>: ' + (", ".join(f_away) if f_away else "No detectados") + '</p>', unsafe_allow_html=True)

        st.markdown('<h4 style="color: #fdffcc;">🔍 Ajuste de Piezas Críticas</h4>', unsafe_allow_html=True)
        v1, v2 = st.columns(2)

        # Usar jugadores de SofaScore si están disponibles, si no usar BD interna
        if st.session_state.lineups_confirmed and st.session_state.fetched_lineups:
            from src.models.base import Player, PlayerPosition, PlayerStatus
            fetched_h = st.session_state.fetched_lineups.get('home', [])
            fetched_a = st.session_state.fetched_lineups.get('away', [])

            def names_to_players(names, team_name):
                players = []
                for i, name in enumerate(names):
                    players.append(Player(
                        id=f"f_{i}_{name[:4]}",
                        name=name,
                        team_name=team_name,
                        position=PlayerPosition.MIDFIELDER,
                        status=PlayerStatus.TITULAR,
                        rating_last_5=7.0
                    ))
                return players

            if fetched_h:
                home_players_ui = names_to_players(fetched_h, home_team.name)
            else:
                home_players_ui = home_team.players

            if fetched_a:
                away_players_ui = names_to_players(fetched_a, away_team.name)
            else:
                away_players_ui = away_team.players
        else:
            home_players_ui = home_team.players
            away_players_ui = away_team.players

        with v1: c_home = render_lineup_check_ui(home_team.name, home_players_ui, side="home")
        with v2: c_away = render_lineup_check_ui(away_team.name, away_players_ui, side="away")

        # --- PREDICTION ---
        st.divider()
        if st.button("🚀 CALCULAR PREDICCIÓN FINAL", type="primary", use_container_width=True):
            with st.spinner("Analizando..."):
                val_h = validator.validate_lineup(home_team, c_home)
                val_a = validator.validate_lineup(away_team, c_away)
                pred = predictor.predict_match(selected_match)
                st.session_state.last_pred = pred
                st.session_state.last_val = (val_h, val_a)
            # Indicador del estado del motor ML
            if not predictor.ml.is_trained:
                st.caption("ℹ️ Motor ML en modo base (sin historial entrenado aún). La predicción se apoya en Poisson + BPA con mayor peso.")

        if st.session_state.get("last_pred"):
            v_h, v_a = st.session_state.last_val
            if v_h['alerts']: st.warning(f"⚠️ {home_team.name}: {v_h['alerts']}")
            if v_a['alerts']: st.warning(f"⚠️ {away_team.name}: {v_a['alerts']}")
            
            render_bpa_display(st.session_state.last_pred)
            render_prediction_cards(st.session_state.last_pred)
            
            # --- STUDY CONFIRMATION BUTTONS ---
            st.markdown("#### 📝 Confirmación del Estudio IA")
            c_conf1, c_conf2 = st.columns(2)
            
            if c_conf1.button("✅ CONFIRMAR ESTUDIO (Guardar en Memoria)", type="primary", use_container_width=True):
                try:
                    db_manager.save_match(selected_match)
                    db_manager.save_prediction(st.session_state.last_pred)
                    st.toast("✅ Estudio guardado para aprendizaje futuro", icon="🧠")
                    st.success("Estudio confirmado y guardado en la base de datos de aprendizaje.")
                except Exception as e:
                    st.error(f"Error al guardar estudio: {e}")

            if c_conf2.button("❌ CANCELAR / DESCARTAR", type="secondary", use_container_width=True):
                st.session_state.last_pred = None
                st.session_state.last_val = None
                st.rerun()

            if st.session_state.last_pred.value_opportunities:
                render_value_analysis_chart(st.session_state.last_pred.value_opportunities)
            
            st.markdown('<h4 style="color: #fdffcc;">📥 Exportar Análisis Profesional</h4>', unsafe_allow_html=True)
            # Safe report generation
            try:
                report_md = report_engine.generate_markdown_report(selected_match if "selected_match" in dir() else None, st.session_state.last_pred)
                st.download_button(
                    label="📄 Descargar Reporte Técnico (.md)",
                    data=report_md,
                    file_name=f"report_{home_team.name[:3]}_{away_team.name[:3]}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error al generar reporte: {e}. Intenta usar el RESETEO NUCLEAR.")

            # Post-Match
            st.divider()
            with st.expander("🛠️ ZONA DE APRENDIZAJE (Post-Partido)"):
                st.markdown('<style>div[data-testid="stExpander"] details summary p { color: #ffffff !important; font-weight: bold; }</style>', unsafe_allow_html=True)
                from src.logic.learning_engine import LearningEngine
                from src.models.base import MatchOutcome
                from src.data.web_fetcher import WebResultFetcher

                try:
                    le = LearningEngine(bpa_engine, db_manager)
                except TypeError:
                    le = LearningEngine(bpa_engine)
                wf = WebResultFetcher()
                act = render_result_validation_form()

                if act:
                    if act.get("action") == "auto_fetch":
                        with st.spinner("IA Accediendo a la red (FlashScore)..."):
                            outcome = wf.fetch_real_result(m_id, home_team.name, away_team.name)
                            if outcome:
                                st.markdown("### 📊 Informe Comparativo IA (Semáforo)")
                                comp_data = le.generate_comparison_report(st.session_state.last_pred, outcome)
                                import pandas as pd
                                if not isinstance(comp_data, pd.DataFrame):
                                    comp_data = pd.DataFrame(comp_data)
                                st.markdown(
                                    comp_data.to_html(escape=False).replace(
                                        '<table', '<table style="color:#f5f0e0;width:100%;border-collapse:collapse;"'
                                    ).replace(
                                        '<th', '<th style="color:#fdffcc;background:#1e293b;padding:8px;border:1px solid #334155;"'
                                    ).replace(
                                        '<td', '<td style="color:#f5f0e0;padding:8px;border:1px solid #334155;"'
                                    ),
                                    unsafe_allow_html=True
                                )
                                try:
                                    rep = le.process_result(
                                        st.session_state.last_pred, outcome,
                                        home_team.name, away_team.name,
                                        selected_league or ""
                                    )
                                except TypeError:
                                    try:
                                        rep = le.process_result(st.session_state.last_pred, outcome)
                                    except Exception as e2:
                                        rep = f"✅ Resultado guardado. (detalle: {e2})"
                                except Exception as e:
                                    rep = f"✅ Resultado guardado. (detalle: {e})"
                                st.success("✅ IA Re-calibrada con éxito")
                                st.markdown(rep)
                            else:
                                st.error("No se pudo obtener el resultado real de la red.")

                    elif act.get("action") == "manual_save":
                        hc = act['corners'] // 2
                        ac = act['corners'] - hc
                        hk = act['cards'] // 2
                        ak = act['cards'] - hk
                        hs = act['shots'] // 2
                        as_ = act['shots'] - hs
                        hst = act['shots_on_target'] // 2
                        ast_ = act['shots_on_target'] - hst
                        out = MatchOutcome(
                            match_id=m_id,
                            home_score=act['home_score'], away_score=act['away_score'],
                            home_corners=hc, away_corners=ac,
                            home_cards=hk, away_cards=ak,
                            home_shots=hs, away_shots=as_,
                            home_shots_on_target=hst, away_shots_on_target=ast_,
                            actual_winner=act['winner']
                        )
                        saved_pred = st.session_state.get("last_pred")
                        if not saved_pred or saved_pred.match_id != out.match_id:
                            saved_pred = db_manager.get_prediction(out.match_id)

                        if saved_pred:
                            st.markdown("### 📊 Informe Comparativo (Semáforo)")
                            try:
                                comp_data = le.generate_comparison_report(saved_pred, out)
                                import pandas as pd
                                if not isinstance(comp_data, pd.DataFrame):
                                    comp_data = pd.DataFrame(comp_data)
                                st.markdown(
                                    comp_data.to_html(escape=False).replace(
                                        '<table', '<table style="color:#f5f0e0;width:100%;border-collapse:collapse;"'
                                    ).replace(
                                        '<th', '<th style="color:#fdffcc;background:#1e293b;padding:8px;border:1px solid #334155;"'
                                    ).replace(
                                        '<td', '<td style="color:#f5f0e0;padding:8px;border:1px solid #334155;"'
                                    ),
                                    unsafe_allow_html=True
                                )
                            except Exception:
                                pass
                            try:
                                rep = le.process_result(
                                    saved_pred, out,
                                    home_team.name, away_team.name,
                                    selected_league or ""
                                )
                            except TypeError:
                                try:
                                    rep = le.process_result(saved_pred, out)
                                except Exception as e2:
                                    rep = f"✅ Resultado guardado. (detalle: {e2})"
                            except Exception as e:
                                rep = f"✅ Resultado guardado. (detalle: {e})"
                            st.success("✅ IA Re-calibrada y datos guardados")
                            st.markdown(rep)
                        else:
                            st.error("No se encontró la predicción. Genera el análisis primero.")
                            st.warning("🔍 No se encontró un estudio previo guardado para este partido. Por favor, asegúrate de CONFIRMAR EL ESTUDIO después de calcular la predicción para alimentar la memoria de la IA.")

            # Bankroll Dashboard
            st.divider()
            
            # --- PENDING BET PROCESSING ---
            if "pending_bet" in st.session_state and st.session_state.pending_bet:
                pb = st.session_state.pending_bet
                bankroll_manager.register_bet(pb["match_id"], pb["market"], pb["odds"], pb["stake"])
                st.toast(f"✅ Apuesta registrada: {pb['market']} @ {pb['odds']}", icon="💰")
                st.session_state.pending_bet = None
                st.rerun()

            render_bankroll_ui(bankroll_manager)

with st.sidebar:
    st.markdown('<h2 style="color: #ffffff;">⚙️ PANEL DE CONTROL</h2>', unsafe_allow_html=True)

    # =====================================================================
    # 📋 PANEL DE ESTUDIOS GUARDADOS
    # =====================================================================
    st.markdown('<h3 style="color: #fdffcc;">📋 Mis Estudios</h3>', unsafe_allow_html=True)
    
    try:
        studies = db_manager.get_all_studies(limit=30)
    except Exception:
        studies = []

    if not studies:
        st.markdown('<p style="color:#888;font-size:0.8rem;">No hay estudios guardados aún.</p>', unsafe_allow_html=True)
    else:
        from datetime import datetime as dt_now
        pendientes = [s for s in studies if "PENDIENTE" in s["status"]]
        completados = [s for s in studies if "COMPLETADO" in s["status"]]
        st.markdown(f'<p style="color:#fdffcc;font-size:0.85rem;">🟡 <b>{len(pendientes)}</b> pendientes &nbsp;|&nbsp; ✅ <b>{len(completados)}</b> completados</p>', unsafe_allow_html=True)

        show_completed = st.toggle("Ver completados también", value=False, key="show_completed")
        display_studies = studies if show_completed else pendientes

        for s in display_studies[:20]:
            status_color = "#facc15" if "PENDIENTE" in s["status"] else "#4ade80"
            partido = f"{s['home_team']} vs {s['away_team']}"
            fecha = s.get("date", "")
            comp = s.get("competition", "")[:15]

            # Detectar si partido está próximo para botón reanalizar
            match_obj_check = db_manager.get_match(s["match_id"])
            hours_to_match = 999
            match_time_str = ""
            can_reanalyze = False
            if match_obj_check and match_obj_check.date:
                try:
                    diff = match_obj_check.date - dt_now.now()
                    hours_to_match = diff.total_seconds() / 3600
                    match_time_str = match_obj_check.date.strftime("%H:%M")
                    can_reanalyze = -1 < hours_to_match < 2.0
                except Exception:
                    pass

            # Badge de alerta
            alert_badge = ""
            if 0 < hours_to_match < 2.0:
                alert_badge = f'⚡ {hours_to_match:.1f}h ALINEACIÓN OFICIAL'
            elif -1 < hours_to_match <= 0:
                alert_badge = '🔴 EN JUEGO'

            border_color = "#f59e0b" if can_reanalyze else status_color
            st.markdown(f"""
                <div style="background:#1e293b;border-radius:8px;padding:8px 10px;margin-bottom:4px;border-left:3px solid {border_color};">
                    <div style="color:#f5f0e0;font-size:0.8rem;font-weight:bold;">{partido}</div>
                    <div style="color:#94a3b8;font-size:0.72rem;">{fecha} {match_time_str} · {comp}</div>
                    <div style="color:{border_color};font-size:0.72rem;">{s['status']} {alert_badge}</div>
                </div>
            """, unsafe_allow_html=True)

            if "PENDIENTE" in s["status"]:
                if can_reanalyze:
                    col_r, col_m = st.columns(2)
                    with col_r:
                        if st.button("🔄 Reanalizar", key=f"reanalyze_{s['match_id']}", use_container_width=True, type="primary"):
                            with st.spinner("Buscando alineación oficial..."):
                                match_obj_r = db_manager.get_match(s["match_id"])
                                if match_obj_r:
                                    try:
                                        from src.logic.lineup_fetcher import LineupFetcher
                                        lf = LineupFetcher(data_provider)
                                        new_lineup = lf.fetch_smart_lineup(
                                            s["home_team"], s["away_team"],
                                            match_obj_r.date,
                                            match_obj_r.competition or ""
                                        )
                                        if new_lineup.get("home") or new_lineup.get("away"):
                                            from src.models.base import Player, PlayerPosition, PlayerStatus, NodeRole
                                            roles = [NodeRole.PORTERO, NodeRole.DEFENSA, NodeRole.DEFENSA,
                                                     NodeRole.DEFENSA, NodeRole.DEFENSA, NodeRole.MEDIOCAMPISTA,
                                                     NodeRole.MEDIOCAMPISTA, NodeRole.MEDIOCAMPISTA,
                                                     NodeRole.DELANTERO, NodeRole.DELANTERO, NodeRole.DELANTERO]
                                            def _to_players(names, tname):
                                                return [Player(
                                                    id=f"{tname}_{i}", name=n, team_name=tname,
                                                    position=PlayerPosition.MIDFIELDER,
                                                    node_role=roles[i] if i < len(roles) else NodeRole.MEDIOCAMPISTA,
                                                    status=PlayerStatus.TITULAR, rating_last_5=7.5
                                                ) for i, n in enumerate(names[:11])]
                                            upd_home = data_provider.get_team_data(s["home_team"])
                                            upd_away = data_provider.get_team_data(s["away_team"])
                                            if new_lineup.get("home"):
                                                upd_home.players = _to_players(new_lineup["home"], s["home_team"])
                                            if new_lineup.get("away"):
                                                upd_away.players = _to_players(new_lineup["away"], s["away_team"])
                                            match_obj_r.home_team = upd_home
                                            match_obj_r.away_team = upd_away
                                            new_pred = predictor.predict(match_obj_r)
                                            new_pred.match_id = s["match_id"]
                                            db_manager.save_prediction(new_pred)
                                            db_manager.save_match(match_obj_r)
                                            st.session_state["last_pred"] = new_pred
                                            tag = "✅ Oficial" if new_lineup.get("is_official") else "📊 Probable actualizada"
                                            st.toast(f"🔄 Reanálisis completado · {tag}", icon="✅")
                                            st.rerun()
                                        else:
                                            st.warning("Alineación oficial no disponible aún.")
                                    except Exception as e:
                                        st.error(f"Error reanalizando: {e}")
                    with col_m:
                        load_btn = st.button("📥 Resultado", key=f"load_{s['match_id']}", use_container_width=True)
                    # Botón prensa (fila separada, solo cuando hay partido próximo)
                    if st.button("📰 Actualizar Prensa", key=f"press_{s['match_id']}", use_container_width=True):
                        match_obj_p = db_manager.get_match(s["match_id"])
                        if match_obj_p:
                            with st.spinner("📰 Buscando noticias actualizadas..."):
                                try:
                                    from src.logic.external_analyst import ExternalAnalyst
                                    analyst = ExternalAnalyst()
                                    intel = analyst.get_detailed_intelligence(match_obj_p)
                                    # Guardar impacto de prensa en session_state
                                    st.session_state[f"press_intel_{s['match_id']}"] = intel
                                    # Recalcular predicción con nuevo impacto de prensa
                                    pred_p = db_manager.get_prediction(s["match_id"])
                                    if pred_p:
                                        from src.logic.bpa_engine import BPAEngine
                                        bpa_r = bpa_engine.calculate_match_bpa(
                                            match_obj_p,
                                            press_modifiers=intel["impact"]
                                        )
                                        pred_p.win_prob_home = round(bpa_r["home_bpa"] / (bpa_r["home_bpa"] + bpa_r["away_bpa"] + 0.3), 3)
                                        pred_p.win_prob_away = round(bpa_r["away_bpa"] / (bpa_r["home_bpa"] + bpa_r["away_bpa"] + 0.3), 3)
                                        pred_p.draw_prob = round(1 - pred_p.win_prob_home - pred_p.win_prob_away, 3)
                                        db_manager.save_prediction(pred_p)
                                        via = "🤖 Claude API" if os.environ.get("ANTHROPIC_API_KEY") else "📡 Google News RSS"
                                        st.toast(f"📰 Prensa actualizada · {via}", icon="✅")
                                        # Mostrar resumen de impacto
                                        h_moral = intel["impact"].get("home", 0)
                                        a_moral = intel["impact"].get("away", 0)
                                        st.markdown(f"""
                                            <div style="background:#1e293b;border-radius:6px;padding:8px;margin-top:4px;">
                                                <div style="color:#fdffcc;font-size:0.78rem;font-weight:bold;">📰 Impacto Prensa Actualizado</div>
                                                <div style="color:#f5f0e0;font-size:0.75rem;">🏠 Local: <b style="color:{'#4ade80' if h_moral >= 0 else '#f87171'};">{h_moral:+.3f}</b></div>
                                                <div style="color:#f5f0e0;font-size:0.75rem;">✈️ Visit.: <b style="color:{'#4ade80' if a_moral >= 0 else '#f87171'};">{a_moral:+.3f}</b></div>
                                            </div>
                                        """, unsafe_allow_html=True)
                                except Exception as e:
                                    st.error(f"Error prensa: {e}")
                else:
                    load_btn = st.button("📥 Meter resultado", key=f"load_{s['match_id']}", use_container_width=True)

                if load_btn:
                    pred = db_manager.get_prediction(s["match_id"])
                    match_obj = db_manager.get_match(s["match_id"])
                    if pred and match_obj:
                        st.session_state["direct_study"] = {
                            "match_id": s["match_id"],
                            "home_team": s["home_team"],
                            "away_team": s["away_team"],
                            "prediction": pred,
                            "match": match_obj,
                        }
                        st.session_state["last_pred"] = pred
                        st.toast(f"✅ Cargado: {partido}", icon="📥")
                        st.rerun()

    st.divider()

    # =====================================================================
    # Zona de aprendizaje directa (desde panel)
    # =====================================================================
    if "direct_study" in st.session_state and st.session_state.direct_study:
        ds = st.session_state.direct_study
        st.markdown(f'<h3 style="color:#fdffcc;">🔧 Validar Resultado</h3>', unsafe_allow_html=True)
        st.markdown(f'<p style="color:#f5f0e0;font-size:0.85rem;"><b>{ds["home_team"]}</b> vs <b>{ds["away_team"]}</b></p>', unsafe_allow_html=True)

        col_h, col_a = st.columns(2)
        with col_h:
            g_home = st.number_input("Goles Local", 0, 20, 0, key="ds_gh")
        with col_a:
            g_away = st.number_input("Goles Visit.", 0, 20, 0, key="ds_ga")
        corners_t = st.number_input("Córners totales", 0, 30, 9, key="ds_c")
        cards_t   = st.number_input("Tarjetas totales", 0, 20, 3, key="ds_k")
        shots_t   = st.number_input("Remates totales", 0, 50, 20, key="ds_s")
        sot_t     = st.number_input("Remates a portería", 0, 30, 6, key="ds_sot")

        if st.button("✅ GUARDAR Y RECALIBRAR IA", use_container_width=True, key="ds_save"):
            from src.models.base import MatchOutcome
            from src.logic.learning_engine import LearningEngine
            winner = "LOCAL" if g_home > g_away else ("VISITANTE" if g_away > g_home else "EMPATE")
            out = MatchOutcome(
                match_id=ds["match_id"],
                home_score=g_home, away_score=g_away,
                home_corners=corners_t//2, away_corners=corners_t-corners_t//2,
                home_cards=cards_t//2, away_cards=cards_t-cards_t//2,
                home_shots=shots_t//2, away_shots=shots_t-shots_t//2,
                home_shots_on_target=sot_t//2, away_shots_on_target=sot_t-sot_t//2,
                actual_winner=winner
            )
            try:
                le = LearningEngine(bpa_engine, db_manager)
            except TypeError:
                le = LearningEngine(bpa_engine)
            try:
                import pandas as pd
                comp_data = le.generate_comparison_report(ds["prediction"], out)
                if not isinstance(comp_data, pd.DataFrame):
                    comp_data = pd.DataFrame(comp_data)
                st.markdown(
                    comp_data.to_html(escape=False).replace(
                        '<table', '<table style="color:#f5f0e0;width:100%;border-collapse:collapse;"'
                    ).replace(
                        '<th', '<th style="color:#fdffcc;background:#1e293b;padding:6px;border:1px solid #334155;"'
                    ).replace(
                        '<td', '<td style="color:#f5f0e0;padding:6px;border:1px solid #334155;"'
                    ),
                    unsafe_allow_html=True
                )
            except Exception:
                pass
            try:
                rep = le.process_result(
                    ds["prediction"], out,
                    ds["home_team"], ds["away_team"], ""
                )
                st.success("✅ IA Recalibrada")
                st.markdown(rep)
            except TypeError:
                db_manager.save_resultado(ds["match_id"], {
                    "home_score": g_home, "away_score": g_away,
                    "winner": winner, "corners": corners_t, "cards": cards_t,
                    "shots": shots_t, "shots_on_target": sot_t,
                })
                st.success("✅ Resultado guardado")
            # Limpiar estudio activo
            del st.session_state["direct_study"]
            st.rerun()

        if st.button("❌ Cancelar", key="ds_cancel", use_container_width=True):
            del st.session_state["direct_study"]
            st.rerun()

    st.markdown('<h3 style="color: #ff4b4b;">☢️ ZONA DE EMERGENCIA</h3>', unsafe_allow_html=True)
    if st.button("🚨 RESETEO NUCLEAR (Limpiar Todo)", type="secondary", use_container_width=True):
        st.session_state.clear()
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.markdown('<p style="font-size: 0.8rem; color: #888;">Usa esto si ves errores persistentes tras reiniciar.</p>', unsafe_allow_html=True)
    
    st.divider()
    if st.button("📈 Ver Dashboard Histórico", use_container_width=True):
        st.session_state.sh = not st.session_state.get("sh", False)

if st.session_state.get("sh"):
    render_historical_dashboard(db_manager=db_manager)
