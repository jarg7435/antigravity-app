import sys
import os
import importlib
from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st

# LAGEMA JARG74 - VERSION 6.25 - EMERGENCY PATCH
SECRET_CODE = "1234"

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
def get_services(version: str = "6.25.3"):
    data_provider = MockDataProvider()
    db_manager = DataManager()
    bpa_engine = BPAEngine()
    predictor = Predictor(bpa_engine)
    validator = Validator()
    
    # Force reload of BankrollManager to avoid persistent AttributeError
    import src.data.bankroll_manager
    importlib.reload(src.data.bankroll_manager)
    from src.data.bankroll_manager import BankrollManager
    
    bankroll_manager = BankrollManager()
    report_engine = ReportEngine()
    return data_provider, db_manager, bpa_engine, predictor, validator, bankroll_manager, report_engine

data_provider, db_manager, bpa_engine, predictor, validator, bankroll_manager, report_engine = get_services()

# --- MAIN LAYOUT ---
render_header()

# 1. Match Configuration
st.markdown('<h3 style="color: #ffffff;">🛠️ Configuración Estratégica</h3>', unsafe_allow_html=True)

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        selected_league = render_league_selector()
        selected_date = render_date_selector()
    with col2:
        selected_time = render_time_selector()
        st.markdown('<p style="color: #fdffcc; font-size: 0.9rem;">🕒 La confirmación oficial de alineaciones se habilita 1h antes del inicio.</p>', unsafe_allow_html=True)

# Get Teams
available_teams = []
league_key = selected_league.split(" (")[0]
available_teams = data_provider.get_teams_by_league(league_key)

if not available_teams and selected_league != "Liga Extra (Manual)":
    st.warning(f"No hay equipos disponibles para {selected_league}.")
else:
    # --- TEAM SELECTION ---
    with st.container():
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown('<h3 style="color: #ffffff;">🏠 Local</h3>', unsafe_allow_html=True)
            mode_h = st.radio("Modo", ["Búsqueda BD", "Manual"], horizontal=True, key="mh")
            if mode_h == "Búsqueda BD":
                h_name = render_team_selector("Seleccionar Equipo", available_teams, key="hts")
                home_team = data_provider.get_team_data(h_name)
            else:
                h_name = st.text_input("Nombre", "Equipo Local FC", key="hnm")
                from src.models.base import Team, Player, PlayerPosition, PlayerStatus
                p_list = [Player(id=f"h{i}", name=f"Jugador {i}", team_name=h_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
                home_team = Team(name=h_name, league="Manual", players=p_list, tactical_style="Equilibrado")

        with c2:
            st.markdown('<h3 style="color: #ffffff;">✈️ Visitante</h3>', unsafe_allow_html=True)
            mode_a = st.radio("Modo", ["Búsqueda BD", "Manual"], horizontal=True, key="ma")
            if mode_a == "Búsqueda BD":
                a_name = render_team_selector("Seleccionar Equipo", available_teams, key="ats")
                away_team = data_provider.get_team_data(a_name)
            else:
                a_name = st.text_input("Nombre", "Rival FC", key="anm")
                from src.models.base import Team, Player, PlayerPosition, PlayerStatus
                p_list = [Player(id=f"a{i}", name=f"Jugador {i}", team_name=a_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
                away_team = Team(name=a_name, league="Manual", players=p_list, tactical_style="Contragolpe")

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
        # Display current referee and lineup source
        current_ref_name = st.session_state.fetched_ref["name"] if st.session_state.fetched_ref else "Pendiente..."
        ref_source = st.session_state.fetched_ref.get("source", "Automático") if st.session_state.fetched_ref else "Automático"
        
        st.markdown(f'<h4 style="color: #fdffcc;">👨‍⚖️ Árbitro: {current_ref_name} <span style="font-size: 0.8rem; color: #888;">({ref_source})</span></h4>', unsafe_allow_html=True)
        st.markdown('<p style="color: #fdffcc; font-size: 0.9rem;">🤖 El sistema accederá automáticamente a SportsGambler para alineaciones y fuentes oficiales para árbitros.</p>', unsafe_allow_html=True)

        # Build referee object with auto-fetched data
        if st.session_state.fetched_ref:
            selected_ref = Referee(
                name=st.session_state.fetched_ref["name"], 
                strictness=st.session_state.fetched_ref["strictness"]
            )
        else:
            selected_ref = Referee(name="Por Detectar", strictness=RefereeStrictness.MEDIUM)
        
        selected_match = Match(
            id=m_id, home_team=home_team, away_team=away_team, 
            date=selected_date, kickoff_time=selected_time, competition=selected_league,
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
            button_label = "🔄 CONFIRMAR OFICIAL" if can_fetch_official else "📋 USAR ÚLTIMO PARTIDO"
            if st.button(button_label, type="primary", use_container_width=True):
                if can_fetch_official:
                    # Official fetching (1 hour before)
                    with st.spinner("🤖 Accediendo a fuentes oficiales..."):
                        l_fetcher = LineupFetcher(data_provider)
                        
                        # 1. Auto-fetch lineups from SportsGambler
                        res = l_fetcher.auto_fetcher.fetch_lineups_auto(
                            home_team.name, 
                            away_team.name, 
                            selected_date, 
                            selected_league
                        )
                        
                        if "error" not in res:
                            st.session_state.fetched_lineups = res
                            status_emoji = "✅" if res.get('status') == 'confirmed' else "🔮"
                            st.toast(f"{status_emoji} Detectados {res['count']} jugadores ({res.get('status', 'predicted')})", icon="📡")
                        else:
                            st.warning(f"⚠️ Alineaciones: {res['error']}. Usando base de datos interna.")
                            # Fallback to internal DB
                            st.session_state.fetched_lineups = {
                                'home': [p.name for p in home_team.players],
                                'away': [p.name for p in away_team.players],
                                'source': 'Base de Datos Interna',
                                'count': len(home_team.players) + len(away_team.players)
                            }
                        
                        # 2. Auto-fetch referee from official league source
                        ref_data = l_fetcher.fetch_match_referee(
                            home_team.name,
                            away_team.name,
                            selected_date,
                            selected_league
                        )
                        st.session_state.fetched_ref = ref_data
                        st.toast(f"👨‍⚖️ Árbitro: {ref_data['name']} ({ref_data.get('source', 'Unknown')})", icon="⚖️")
                else:
                    # Use last match lineups (before 1 hour)
                    with st.spinner("📋 Cargando alineaciones del último partido..."):
                        home_last = data_provider.get_last_match_lineup(home_team.name)
                        away_last = data_provider.get_last_match_lineup(away_team.name)
                        
                        st.session_state.fetched_lineups = {
                            'home': home_last if home_last else [p.name for p in home_team.players],
                            'away': away_last if away_last else [p.name for p in away_team.players],
                            'source': 'Último Partido Jugado',
                            'count': len(home_last) + len(away_last) if home_last and away_last else 0
                        }
                        
                        # Use generic referee
                        st.session_state.fetched_ref = {
                            'name': 'Por Confirmar (1h antes)',
                            'strictness': RefereeStrictness.MEDIUM,
                            'source': 'Pendiente'
                        }
                        
                        st.toast(f"📋 Usando alineaciones del último partido ({len(home_last) + len(away_last)} jugadores)", icon="📊")
                
                st.session_state.lineups_confirmed = True
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
        with v1: c_home = render_lineup_check_ui(home_team.name, home_team.players, side="home")
        with v2: c_away = render_lineup_check_ui(away_team.name, away_team.players, side="away")

        # --- PREDICTION ---
        st.divider()
        if st.button("🚀 CALCULAR PREDICCIÓN FINAL", type="primary", use_container_width=True):
            with st.spinner("Analizando..."):
                val_h = validator.validate_lineup(home_team, c_home)
                val_a = validator.validate_lineup(away_team, c_away)
                pred = predictor.predict_match(selected_match)
                st.session_state.last_pred = pred
                st.session_state.last_val = (val_h, val_a)

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
                report_md = report_engine.generate_markdown_report(selected_match, st.session_state.last_pred)
                st.download_button(
                    label="📄 Descargar Reporte Técnico (.md)",
                    data=report_md,
                    file_name=f"report_{selected_match.id}.md",
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
                
                le = LearningEngine(bpa_engine)
                wf = WebResultFetcher()
                act = render_result_validation_form()
                
                if act:
                    if act.get("action") == "auto_fetch":
                        with st.spinner("IA Accediendo a la red (FlashScore)..."):
                            outcome = wf.fetch_real_result(selected_match.id, home_team.name, away_team.name)
                            if outcome:
                                # Show visual comparison report
                                st.markdown("### 📊 Informe Comparativo IA (Semáforo)")
                                comp_data = le.generate_comparison_report(st.session_state.last_pred, outcome)
                                st.table(comp_data)
                                
                                # Process learning
                                rep = le.process_result(st.session_state.last_pred, outcome, home_team.name, away_team.name)
                                st.success("IA Re-calibrada con éxito (Acceso Real)")
                                st.info(rep)
                            else:
                                st.error("No se pudo obtener el resultado real de la red.")
                    
                    elif act.get("action") == "manual_save":
                        out = MatchOutcome(
                            match_id=selected_match.id, home_score=act['home_score'], away_score=act['away_score'],
                            home_corners=act['corners']//2, away_corners=act['corners']//2,
                            home_cards=act['cards']//2, away_cards=act['cards']//2,
                            home_shots=act['shots']//2, away_shots=act['shots']//2, actual_winner=act['winner']
                        )
                        
                        # Robust prediction retrieval (Session or DB)
                        saved_pred = st.session_state.get("last_pred")
                        if not saved_pred or saved_pred.match_id != out.match_id:
                            saved_pred = db_manager.get_prediction(out.match_id)
                        
                        if saved_pred:
                            rep = le.process_result(saved_pred, out, home_team.name, away_team.name)
                            st.success("IA Re-calibrada con éxito")
                            st.info(rep)
                        else:
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
    render_historical_dashboard(bpa_engine.kb)
