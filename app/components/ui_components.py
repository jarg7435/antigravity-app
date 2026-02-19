import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from src.models.base import Match, PredictionResult, Player
try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    px = None
    go = None

def format_stat_range(val: str) -> str:
    if not val or "🏠" in val:
        return val
    # Si viene en formato antiguo "Hmin-Hmax-Amin-Amax" (ej. 5-9-1-5)
    parts = val.split('-')
    if len(parts) == 4:
        return f"🏠 {parts[0]}-{parts[1]} | ✈️ {parts[2]}-{parts[3]}"
    return val

def render_header():
    st.markdown("""
        <div style="text-align: center; padding: 40px 0; background: linear-gradient(90deg, rgba(0,212,255,0.05) 0%, rgba(0,86,179,0.05) 100%); border-radius: 20px; margin-bottom: 30px; border: 1px solid rgba(255,255,255,0.05);">
            <h1 style="margin-bottom: 0; font-family: 'Outfit', sans-serif; font-weight: 900; letter-spacing: -1px; background: linear-gradient(90deg, #fff, #00d4ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">🛡️ LAGEMA JARG74</h1>
            <p style="margin-top: 5px; color: #fdffcc; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; font-size: 0.8rem;">Capa de Inteligencia Predictiva Avanzada • V6.35.0 (Referee Independence)</p>
        </div>
    """, unsafe_allow_html=True)

def render_player_selector(label: str, team_players: list, default_name: str = None, key: str = None):
    """
    Renders a selectbox for a specific position/role, populated with the team's roster.
    """
    # Extract names if team_players are Player objects
    player_names = [p.name for p in team_players]
    
    # Try to find the index of the default player
    index = 0
    if default_name and default_name in player_names:
        index = player_names.index(default_name)
    elif default_name is None and len(player_names) > 0:
        index = 0
        
    selected_name = st.selectbox(label, player_names, index=index, key=key)
    return selected_name

def render_league_selector():
    leagues = [
        "La Liga (España)", "Premier League (Inglaterra)", "Bundesliga (Alemania)", 
        "Serie A (Italia)", "Ligue 1 (Francia)", 
        "Liga Mixta (Combinada)", "Liga Extra (Manual)"
    ]
    return st.selectbox("Seleccionar Competición:", options=leagues)

def render_date_selector():
    return st.date_input("Fecha del Encuentro:", value=pd.to_datetime("today"))

def render_time_selector():
    times = []
    for h in range(24):
        for m in [0, 15, 30, 45]:
            times.append(f"{h:02d}:{m:02d}")
    
    # Default to 21:00 if found
    default_index = times.index("21:00") if "21:00" in times else 0
    return st.selectbox("Hora del Encuentro:", options=times, index=default_index)

def render_team_selector(label: str, teams: list[str], key: str):
    return st.selectbox(label, options=teams, key=key)

def render_bpa_display(result: PredictionResult):
    st.markdown(f"""
        <div class="bpa-container">
            <div class="bpa-label">Probabilidades de Victoria (Consenso IA/Poisson)</div>
            <div style="display: flex; justify-content: space-around; align-items: center; padding: 20px 0;">
                <div>
                    <div style="font-size: 0.9rem; color: #fdffcc;">LOCAL</div>
                    <div class="bpa-score" style="font-size: 2.5rem; color: #fff;">{result.win_prob_home*100:.1f}%</div>
                </div>
                <div>
                    <div style="font-size: 0.9rem; color: #fdffcc;">EMPATE</div>
                    <div class="bpa-score" style="font-size: 2rem; color: #fff; opacity: 0.8;">{result.draw_prob*100:.1f}%</div>
                </div>
                <div>
                    <div style="font-size: 0.9rem; color: #fdffcc;">VISITANTE</div>
                    <div class="bpa-score" style="font-size: 2.5rem; color: #fff;">{result.win_prob_away*100:.1f}%</div>
                </div>
            </div>
            <div class="bpa-label" style="font-size: 0.7rem; color: #38bdf8;">Fusión de Modelos: XGBoost + Poisson + BPA</div>
        </div>
    """, unsafe_allow_html=True)

def render_prediction_cards(result: PredictionResult):
    st.markdown("### 📊 Mercados y Análisis Profundo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.5); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="color: #fdffcc; font-size: 0.8rem; text-transform: uppercase;">Expected Goals (xG)</div>
                <div style="font-size: 1.8rem; font-weight: 800; color: #fff;">{result.total_goals_expected:.2f}</div>
                <div style="font-size: 0.8rem; color: #10b981;">BTTS: {result.both_teams_to_score_prob*100:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
         st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.5); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);">
                <div style="color: #fdffcc; font-size: 0.8rem; text-transform: uppercase;">Estado y Árbitro</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #38bdf8;">{result.confidence_score*100:.1f}% Confianza</div>
                <div style="font-size: 0.9rem; color: #fdffcc;">👨‍⚖️ {getattr(result, "referee_name", "No asignado")}</div>
            </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # 2. Score Matrix (Poisson)
    with st.expander("🎲 Matriz de Resultados Probables (Poisson)"):
        # Sort matrix and show top 5
        sorted_matrix = sorted(result.poisson_matrix.items(), key=lambda x: x[1], reverse=True)[:5]
        cols = st.columns(len(sorted_matrix))
        for i, (score, prob) in enumerate(sorted_matrix):
            cols[i].metric(score, f"{prob*100:.1f}%")

    # 3. Secondary Markets
    st.markdown("#### 📈 Mercados Secundarios")
    col_a, col_b, col_c, col_d, col_e = st.columns(5)
    
    with col_a:
        st.write(f"**🥅 Goles**: {result.total_goals_expected:.2f}")
        st.markdown(f'<p style="color: #fdffcc; font-size: 0.8rem; font-weight: bold;">Tendencia: {"Over 2.5" if result.total_goals_expected > 2.5 else "Under 2.5"}</p>', unsafe_allow_html=True)

    with col_b:
        st.write(f"**🏁 Córners**")
        st.markdown(f'<p style="font-size: 0.9rem; font-weight: 700; color: #fff;">{format_stat_range(getattr(result, "predicted_corners", "0-0"))}</p>', unsafe_allow_html=True)

    with col_c:
        st.write(f"**🟨 Tarjetas**")
        st.markdown(f'<p style="font-size: 0.9rem; font-weight: 700; color: #fff;">{format_stat_range(getattr(result, "predicted_cards", "0-0"))}</p>', unsafe_allow_html=True)

    with col_d:
        st.write(f"**🎯 Remates**")
        st.markdown(f'<p style="font-size: 0.9rem; font-weight: 700; color: #fff;">{format_stat_range(getattr(result, "predicted_shots", "0-0"))}</p>', unsafe_allow_html=True)

    with col_e:
        st.write(f"**🥅 A Portería**")
        st.markdown(f'<p style="font-size: 0.9rem; font-weight: 700; color: #fff;">{format_stat_range(getattr(result, "predicted_shots_on_target", "🏠 0 | ✈️ 0"))}</p>', unsafe_allow_html=True)

    st.divider()
    # 4. Quick Bet
    st.markdown("#### 🎫 Registro Rápido de Apuesta")
    with st.expander("Abrir Cupón de Apuesta"):
        with st.form("quick_bet_form"):
            market = st.selectbox("Mercado", ["Opción 1 (Local)", "Opción X (Empate)", "Opción 2 (Visitante)", "Opción 1X (Doble Oportunidad)", "Opción X2 (Doble Oportunidad)", "Opción 12 (Doble Oportunidad)", "Goles (Total)", "Córners", "Tarjetas", "Remates", "A Portería"])
            c_odds, c_stake = st.columns(2)
            odds = c_odds.number_input("Cuota", min_value=1.01, value=2.00, step=0.1)
            stake = c_stake.number_input("Stake (€)", min_value=1.0, value=1.0, step=1.0)
            
            if st.form_submit_button("💾 Registrar Apuesta PENDIENTE"):
                # Handle registration in main.py via session_state flag
                st.session_state.pending_bet = {
                    "match_id": result.match_id if hasattr(result, "match_id") else "manual_bet",
                    "market": market,
                    "odds": odds,
                    "stake": stake
                }
                st.rerun()

    st.divider()
    # 5. External Analysis Summary
    if result.external_analysis_summary:
        st.markdown("#### 📰 Informe de Capa de Inteligencia")
        st.info(result.external_analysis_summary)

    # 5. Value Betting Alerts
    if result.value_opportunities:
        st.markdown("#### 💎 Oportunidades de VALOR Detectadas")
        for opp in result.value_opportunities:
            st.success(f"**Mercado {opp['market']}**: Valor del {opp['value_pct']}% | Cuota: {opp['odds']} | Stake Kelly: {opp['suggested_stake_pct']}%")

def render_value_analysis_chart(opportunities: List[Dict]):
    if not px or not opportunities: return
    
    st.markdown("#### 📊 Distribución de Valor por Mercado")
    df = pd.DataFrame(opportunities)
    fig = px.bar(df, x='market', y='value_pct', color='value_pct',
                 color_continuous_scale="Viridis",
                 labels={'market': 'Mercado', 'value_pct': 'Valor %'},
                 title="Valor Detectado")
    fig.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

def render_value_analysis_chart(opportunities: List[Dict]):
    if not px or not opportunities: return
    
    st.markdown("#### 📊 Distribución de Valor por Mercado")
    df = pd.DataFrame(opportunities)
    fig = px.bar(df, x='market', y='value_pct', color='value_pct',
                 color_continuous_scale="Viridis",
                 labels={'market': 'Mercado', 'value_pct': 'Valor %'},
                 title="Análisis de Valor Detectado")
    fig.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, use_container_width=True)

def render_bankroll_ui(manager):
    st.markdown("### 💰 Gestión de Bankroll y ROI")
    summary = manager.get_summary()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Balance Actual", f"{summary['balance']}€")
    c2.metric("Profit Total", f"{summary['profit']}€", delta=f"{summary['roi']}% (ROI)")
    c3.metric("Invertido", f"{summary['invested']}€")
    c4.metric("ROI Global", f"{summary['roi']}%")
    
    # Advanced Analytics (Phase 4)
    if px and summary['roi'] != 0:
        st.markdown("#### 📈 Evolución del Capital")
        # Generate dummy equity curve from balance history
        history = manager.data.get("history", [max(0, summary['balance'] - summary['profit']), summary['balance']])
        fig = px.line(x=list(range(len(history))), y=history, 
                      labels={'x': 'Apuesta #', 'y': 'Balance (€)'},
                      title="Curva de Equity")
        fig.update_layout(template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- PENDING BETS SETTLEMENT ---
    pending = [t for t in manager.data["transactions"] if t["status"] == "PENDING"]
    if pending:
        st.markdown("#### ⏳ Liquidar Apuestas Pendientes")
        for p in pending:
            col_info, col_won, col_lost = st.columns([3, 1, 1])
            col_info.markdown(f"**{p['market']}** @ {p['odds']} | Stake: {p['stake']}€")
            if col_won.button("✅ GANADA", key=f"won_{p['id']}", use_container_width=True):
                manager.settle_bet(p['id'], True)
                st.rerun()
            if col_lost.button("❌ FALLADA", key=f"lost_{p['id']}", use_container_width=True):
                manager.settle_bet(p['id'], False)
                st.rerun()
        st.divider()

    # --- BANKROLL SETTINGS ---
    with st.expander("⚙️ Ajustes de Bankroll (Reset)"):
        col_reset, col_btn = st.columns([3, 1])
        new_cap = col_reset.number_input("Nuevo Capital Inicial (€)", min_value=1.0, value=10.0, step=10.0)
        if col_btn.button("♻️ RESETEAR", type="secondary", use_container_width=True):
            if hasattr(manager, "reset_bankroll"):
                manager.reset_bankroll(new_cap)
                st.success(f"Bankroll reseteado a {new_cap}€")
                st.rerun()
            else:
                st.error("⚠️ Error de Memoria: El sistema necesita un 'RESETEO NUCLEAR' (en la barra lateral) para activar esta función.")

    # Simple table of recent transactions
    if manager.data["transactions"]:
        st.markdown("#### 📝 Historial de Apuestas")
        df_trans = pd.DataFrame(manager.data["transactions"]).tail(10)
        # Select relevant columns for display
        display_df = df_trans[["date", "market", "odds", "stake", "status"]]
        st.dataframe(display_df, use_container_width=True)
        
        if st.button("🗑️ Limpiar Historial Total", type="secondary"):
            manager.data["transactions"] = []
            manager._save_data()
            st.rerun()
    else:
        st.markdown('<p style="color: #fdffcc; font-size: 0.9rem; font-weight: bold;">No hay apuestas registradas aún. Comienza a gestionar tu bankroll hoy.</p>', unsafe_allow_html=True)

def render_result_validation_form():
    st.markdown("### 📝 Validar Resultados y Entrenar IA")
    
    with st.form("validation_form"):
        # Inputs for actual result
        c1, c2 = st.columns(2)
        home_score = c1.number_input("Goles Local", min_value=0, value=0)
        away_score = c2.number_input("Goles Visitante", min_value=0, value=0)
        
        st.markdown("**Estadísticas Reales**")
        stats_c1, stats_c2, stats_c3 = st.columns(3)
        corners = stats_c1.number_input("Córners Totales", 0, 20, 5)
        cards = stats_c2.number_input("Tarjetas Totales", 0, 15, 3)
        shots = stats_c3.number_input("Remates Totales", 0, 40, 10)
        
        # Determine Winner
        winner = "EMPATE"
        if home_score > away_score: winner = "LOCAL"
        elif away_score > home_score: winner = "VISITANTE"
        
        c_btn1, c_btn2 = st.columns(2)
        
        # New "Auto-Fetch / Review" button
        if c_btn1.form_submit_button("🔍 REVISAR RESULTADO (IA Web Access)", use_container_width=True):
            return {"action": "auto_fetch"}
            
        submitted = c_btn2.form_submit_button("💾 Guardar y Re-Calibrar IA", use_container_width=True)
        
        if submitted:
            return {
                "action": "manual_save",
                "home_score": home_score,
                "away_score": away_score,
                "corners": corners,
                "cards": cards,
                "shots": shots,
                "winner": winner
            }
    return None

def render_historical_dashboard(kb):
    st.markdown("### 📊 Tablero de Evolución y Análisis")
    
    stats = kb.get_stats()
    factors = kb.get_factors()
    
    # Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Predicciones", stats["total"])
    c2.metric("Aciertos (Hits)", stats["hits"])
    c3.metric("Fallos (Misses)", stats["misses"])
    
    if stats["total"] > 0:
        accuracy = (stats["hits"] / stats["total"]) * 100
        st.progress(accuracy / 100, text=f"Precisión Global del Modelo: {accuracy:.1f}%")
    else:
        st.markdown('<p style="color: #fdffcc; font-size: 1rem; font-weight: bold;">⚠️ Sin datos históricos suficientes. Valida partidos para entrenar a la IA.</p>', unsafe_allow_html=True)
        
    st.divider()
    
    st.markdown("#### 🧠 Factores Aprendidos (Team Bias)")
    st.markdown('<p style="color: #fdffcc; font-size: 0.8rem; font-weight: bold;">Ajustes permanentes que la IA aplica a equipos específicos basados en el rendimiento histórico.</p>', unsafe_allow_html=True)
    
    if factors:
        # Convert nested dict to flat list for dataframe
        flat_data = []
        for team, biases in factors.items():
            flat_data.append({
                "Equipo": team, 
                "Factor Local (+Bias)": biases.get("home_bias", 0),
                "Factor Visitante (+Bias)": biases.get("away_bias", 0)
            })
        st.dataframe(pd.DataFrame(flat_data))
    else:
        st.markdown('<p style="color: #fdffcc; font-size: 1rem; font-weight: bold;">💡 La IA aún no ha generado factores de corrección específicos. Valida más partidos para iniciar el aprendizaje profundo.</p>', unsafe_allow_html=True)

def render_lineup_check_ui(team_name: str, players: list[Player], side: str = "home"):
    st.markdown(f'<h3 style="color: #ffffff; text-decoration: underline; text-decoration-color: #00d4ff;">Alineación: {team_name}</h3>', unsafe_allow_html=True)
    
    confirmed_players = []
    
    # Use columns to save space
    cols = st.columns(2)
    for i, player in enumerate(players):
        with cols[i % 2]:
            # Robust ID generation with side-specific prefix
            is_confirmed = st.checkbox(
                f"({player.position.value}): {player.name}",
                value=(player.status.value == "Titular"),
                key=f"cb_{side}_{team_name}_{player.name}".replace(" ", "_").lower()
            )
            if is_confirmed:
                confirmed_players.append(player.name)
    
    return confirmed_players
