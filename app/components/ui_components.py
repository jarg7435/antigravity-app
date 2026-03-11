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
            <p style="margin-top: 5px; color: #fdffcc; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; font-size: 0.8rem;">Capa de Inteligencia Predictiva Avanzada • V6.70.0 (Global Generic)</p>
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
        # 5 Grandes Ligas
        "La Liga (España)", "Premier League (Inglaterra)", "Bundesliga (Alemania)", 
        "Serie A (Italia)", "Ligue 1 (Francia)",
        # Ligas Europeas
        "Eredivisie (Holanda)", "Primeira Liga (Portugal)", "Süper Lig (Turquía)",
        "Scottish Premiership (Escocia)", "Belgian Pro League (Bélgica)",
        "Austrian Bundesliga (Austria)", "Swiss Super League (Suiza)",
        "Ekstraklasa (Polonia)", "Czech First League (Rep. Checa)",
        "Superliga (Dinamarca)", "Allsvenskan (Suecia)", "Eliteserien (Noruega)",
        "Super League (Grecia)", "HNL (Croacia)", "SuperLiga (Serbia)",
        # Otras competiciones
        "Champions League", "Europa League", "Conference League",
        # Modo combinado y manual
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
            cols[i].markdown(f"""
                <div style="text-align: center; background: rgba(15, 23, 42, 0.4); padding: 10px; border-radius: 10px; border: 1px solid rgba(0, 212, 255, 0.1);">
                    <div style="color: #ffffff; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px;">{score}</div>
                    <div style="color: #fdffcc; font-size: 1.6rem; font-weight: 900; letter-spacing: -0.5px;">{prob*100:.1f}%</div>
                </div>
            """, unsafe_allow_html=True)

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
            markets = st.multiselect("Selecciones (Combinada/Simple)", 
                                   ["Opción 1 (Local)", "Opción X (Empate)", "Opción 2 (Visitante)", 
                                    "Opción 1X (Doble Oportunidad)", "Opción X2 (Doble Oportunidad)", 
                                    "Opción 12 (Doble Oportunidad)", "Goles (Total)", "Córners", 
                                    "Tarjetas", "Remates", "A Portería"],
                                   default=["Opción 1 (Local)"])
            
            c_odds, c_stake = st.columns(2)
            odds = c_odds.number_input("Cuota Total", min_value=1.01, value=2.00, step=0.1)
            stake = c_stake.number_input("Stake Total (€)", min_value=1.0, value=1.0, step=1.0)
            
            if st.form_submit_button("💾 Registrar Apuesta PENDIENTE"):
                if not markets:
                    st.error("Selecciona al menos una opción.")
                else:
                    # Join markets for storage
                    market_str = " + ".join(markets)
                    if len(markets) > 1:
                        market_str = f"📦 COMBINADA: {market_str}"
                    
                    st.session_state.pending_bet = {
                        "match_id": result.match_id if hasattr(result, "match_id") else "manual_bet",
                        "market": market_str,
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
        
        st.markdown("**Estadísticas Reales (Totales)**")
        stats_c1, stats_c2, stats_c3, stats_c4 = st.columns(4)
        corners = stats_c1.number_input("Córners", 0, 30, 8)
        cards = stats_c2.number_input("Tarjetas", 0, 20, 4)
        shots = stats_c3.number_input("Remates", 0, 50, 20)
        shots_on_target = stats_c4.number_input("Remates a Portería", 0, 30, 8)
        
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
                "shots_on_target": shots_on_target,
                "winner": winner
            }
    return None

def render_historical_dashboard(db_manager=None, kb=None):
    st.markdown("### 📊 Dashboard de Aprendizaje Profundo")

    # Soporte tanto para db_manager nuevo como kb legacy
    if db_manager is None and kb is not None:
        # Fallback al sistema legacy
        stats = kb.get_stats()
        factors = kb.get_factors()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Predicciones", stats.get("total", 0))
        c2.metric("Aciertos", stats.get("hits", 0))
        c3.metric("Fallos", stats.get("misses", 0))
        if stats.get("total", 0) > 0:
            acc = stats["hits"] / stats["total"] * 100
            st.progress(acc / 100, text=f"Precisión Global: {acc:.1f}%")
        return

    # Dashboard completo con db_manager
    try:
        stats = db_manager.get_total_stats()
        team_factors = db_manager.get_all_team_factors()
        mercados = stats.get("mercados", {})
        total = stats.get("total_partidos", 0)
        modo = db_manager.modo
    except Exception as e:
        st.warning(f"Error cargando estadísticas: {e}")
        return

    # --- Modo de persistencia ---
    st.caption(f"🗄️ Base de datos: **{modo}**")
    if "SQLite" in modo:
        st.warning("⚠️ Los datos se perderán al redesplegar la app. Configura **SUPABASE_URL** y **SUPABASE_KEY** en los Secrets de Streamlit para persistencia permanente.")

    if total == 0:
        st.info("💡 Aún no hay partidos validados. Usa la Zona de Aprendizaje tras cada partido para entrenar al sistema.")
        return

    # --- KPIs globales ---
    st.markdown("#### 🎯 Precisión por Mercado")
    cols = st.columns(4)
    mercado_config = [
        ("1X2",       "🏆 Ganador",    "#00d4ff"),
        ("Córners",   "🚩 Córners",    "#ffd700"),
        ("Tarjetas",  "🟨 Tarjetas",   "#ff6b6b"),
        ("Remates",   "⚽ Remates",    "#51cf66"),
    ]
    for i, (key, label, color) in enumerate(mercado_config):
        m = mercados.get(key, {})
        prec = m.get("precision", 0)
        tot = m.get("total", 0)
        err = m.get("error_medio", 0)
        with cols[i]:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.05); border-radius: 10px;
                        padding: 12px; text-align: center; border-left: 3px solid {color};">
                <div style="color: {color}; font-size: 1.1rem; font-weight: bold;">{label}</div>
                <div style="color: white; font-size: 2rem; font-weight: 900;">{prec}%</div>
                <div style="color: #aaa; font-size: 0.75rem;">{tot} partidos | Error medio: {err}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # --- Factores de equipo aprendidos ---
    st.markdown("#### 🧠 Factores de Corrección Aprendidos por Equipo")
    st.caption("El sistema ajusta automáticamente las probabilidades de cada equipo basándose en sus errores históricos.")

    if team_factors:
        table_data = []
        for t in team_factors:
            sl = float(t.get("sesgo_local", 0))
            sv = float(t.get("sesgo_visitante", 0))
            se = float(t.get("sesgo_empate", 0))
            tp = int(t.get("total_partidos", 0))
            if tp == 0:
                continue
            # Interpretación del sesgo
            def interpret(val):
                if val > 0.03: return f"+{val:.3f} ⬆️ subestimado históricamente"
                if val < -0.03: return f"{val:.3f} ⬇️ sobreestimado históricamente"
                return f"{val:+.3f} ✅ calibrado"

            table_data.append({
                "Equipo": t.get("equipo", ""),
                "Partidos": tp,
                "Factor Local": interpret(sl),
                "Factor Visitante": interpret(sv),
                "Factor Empate": f"{se:+.3f}",
            })

        if table_data:
            st.dataframe(
                pd.DataFrame(table_data),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("Valida más partidos para que el sistema genere factores de corrección específicos.")

    st.divider()

    # --- Alertas de sesgo sistemático ---
    st.markdown("#### ⚠️ Alertas de Sesgo Sistemático")
    alertas = [
        t for t in team_factors
        if abs(float(t.get("sesgo_local", 0))) > 0.06
        or abs(float(t.get("sesgo_visitante", 0))) > 0.06
    ]
    if alertas:
        for t in alertas[:5]:
            sl = float(t.get("sesgo_local", 0))
            sv = float(t.get("sesgo_visitante", 0))
            equipo = t.get("equipo", "")
            if abs(sl) > 0.06:
                tipo = "subestimado" if sl > 0 else "sobreestimado"
                st.error(f"🔴 **{equipo} (Local):** {tipo} sistemáticamente (sesgo: {sl:+.3f})")
            if abs(sv) > 0.06:
                tipo = "subestimado" if sv > 0 else "sobreestimado"
                st.error(f"🔴 **{equipo} (Visitante):** {tipo} sistemáticamente (sesgo: {sv:+.3f})")
    else:
        st.success("✅ No se detectan sesgos sistemáticos graves. El modelo está bien calibrado.")

def render_semaforo_history(db_manager):
    """
    Página completa de historial de semáforos y evolución de aciertos.
    """
    st.markdown("## 🚦 Historial de Semáforos y Evolución")

    try:
        history = db_manager.get_semaforo_history(limit=50)
        stats = db_manager.get_total_stats()
        mercados_stats = stats.get("mercados", {})
        total = stats.get("total_partidos", 0)
    except Exception as e:
        st.error(f"Error cargando historial: {e}")
        return

    if not history:
        st.info("💡 Aún no hay partidos validados. Introduce resultados reales en la Zona de Aprendizaje para ver el historial.")
        return

    # KPIs globales
    st.markdown("### 🎯 Precisión Global Acumulada")
    MERCADOS = [
        ("1X2",      "🏆 Ganador",  "#00d4ff"),
        ("Córners",  "🚩 Córners",  "#ffd700"),
        ("Tarjetas", "🟨 Tarjetas", "#ff6b6b"),
        ("Remates",  "⚽ Remates",  "#51cf66"),
    ]
    cols = st.columns(4)
    for i, (key, label, color) in enumerate(MERCADOS):
        m = mercados_stats.get(key, {})
        prec = m.get("precision", 0)
        hits = m.get("aciertos", 0)
        tot  = m.get("total", 0)
        with cols[i]:
            bg = "#1a3a1a" if prec >= 60 else ("#3a2a1a" if prec >= 45 else "#3a1a1a")
            st.markdown(
                f'<div style="background:{bg};border-radius:10px;padding:12px;'
                f'text-align:center;border-left:4px solid {color};">'
                f'<div style="color:{color};font-size:0.95rem;font-weight:bold;">{label}</div>'
                f'<div style="color:white;font-size:2rem;font-weight:900;">{prec}%</div>'
                f'<div style="color:#aaa;font-size:0.72rem;">{hits}/{tot} aciertos</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()

    # Evolución temporal
    st.markdown("### 📈 Evolución de Aciertos (últimos partidos)")

    running = {"1X2": [], "Córners": [], "Tarjetas": [], "Remates": []}
    hits_acc  = {"1X2": 0, "Córners": 0, "Tarjetas": 0, "Remates": 0}
    total_acc = {"1X2": 0, "Córners": 0, "Tarjetas": 0, "Remates": 0}

    for partido in reversed(history):
        for key in running.keys():
            m = partido["mercados"].get(key)
            if m:
                total_acc[key] += 1
                if m["acierto"]:
                    hits_acc[key] += 1
                pct = round(hits_acc[key] / total_acc[key] * 100, 1) if total_acc[key] else 0
                running[key].append(pct)
            else:
                prev = running[key][-1] if running[key] else 0
                running[key].append(prev)

    if total > 0:
        try:
            chart_data = pd.DataFrame(running)
            chart_data.index = [f"P{i+1}" for i in range(len(chart_data))]
            st.line_chart(chart_data, height=220)
            st.caption("Cada punto = un partido validado. La línea sube cuando aciertas, baja cuando fallas.")
        except Exception:
            pass

    st.divider()

    # Tabla semáforos por partido
    st.markdown("### 🚦 Semáforos por Partido")

    mercado_labels = [("1X2","1X2"), ("Córners","COR"), ("Tarjetas","TAR"), ("Remates","REM")]

    for partido in history:
        home  = partido.get("home_team", "?")
        away  = partido.get("away_team", "?")
        fecha = partido.get("created_at", "")
        comp  = partido.get("competition", "")[:20]
        merc  = partido.get("mercados", {})

        total_m = len(merc)
        hits_m  = sum(1 for m in merc.values() if m.get("acierto"))
        all_hit = hits_m == total_m and total_m > 0
        border  = "#4ade80" if all_hit else ("#f59e0b" if hits_m >= total_m / 2 else "#f87171")
        icon    = "🟢" if all_hit else ("🟡" if hits_m >= total_m / 2 else "🔴")

        # Cabecera del partido
        st.markdown(
            f'<div style="background:#0f172a;border-radius:10px;padding:10px 14px;'
            f'margin-bottom:4px;border-left:4px solid {border};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div><span style="color:#f5f0e0;font-size:0.9rem;font-weight:bold;">'
            f'{icon} {home} vs {away}</span>'
            f'<span style="color:#64748b;font-size:0.75rem;margin-left:8px;">'
            f'{fecha} · {comp}</span></div>'
            f'<span style="color:{border};font-size:0.85rem;font-weight:bold;">'
            f'{hits_m}/{total_m} aciertos</span></div></div>',
            unsafe_allow_html=True
        )

        # Badges de mercado
        badge_cols = st.columns(4)
        for col_i, (key, label_short) in enumerate(mercado_labels):
            m = merc.get(key)
            with badge_cols[col_i]:
                if m:
                    color_b = "#4ade80" if m["acierto"] else "#f87171"
                    icon_b  = "✅" if m["acierto"] else "❌"
                    pred_b  = m.get("predicho", "?")
                    real_b  = m.get("real", "?")
                    st.markdown(
                        f'<div style="background:#1e293b;border:1px solid {color_b};'
                        f'border-radius:6px;padding:5px 8px;text-align:center;">'
                        f'<div style="color:{color_b};font-size:0.75rem;font-weight:bold;">'
                        f'{icon_b} {label_short}</div>'
                        f'<div style="color:#f5f0e0;font-size:0.7rem;">Pred: {pred_b}</div>'
                        f'<div style="color:#94a3b8;font-size:0.7rem;">Real: {real_b}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div style="background:#1e293b;border:1px solid #334155;'
                        f'border-radius:6px;padding:5px 8px;text-align:center;">'
                        f'<div style="color:#475569;font-size:0.75rem;">{label_short}</div>'
                        f'<div style="color:#334155;font-size:0.7rem;">N/A</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)

    st.caption(f"Mostrando los últimos {len(history)} partidos validados.")


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
