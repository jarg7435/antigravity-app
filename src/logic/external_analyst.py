import random
from src.models.base import Match, Team

class ExternalAnalyst:
    """
    Simulates the aggregation of external intelligence from:
    1. Local Press (City/Region specific) - Focused on Injuries & Signings.
    2. National Press (Country specific) - Context & Sentiment.
    3. Weather Reports.
    4. Expert Consensus.
    """
    
    # Simulation Data: Mapping Teams to Context
    # Simulation Data: Expanded European Context
    TEAM_CONTEXT = {
        # --- La Liga (Spain) ---
        "Real Madrid": {"city": "Madrid", "country": "Spain", "papers": ["Marca", "Defensa Central"]},
        "Atletico Madrid": {"city": "Madrid", "country": "Spain", "papers": ["Marca", "Mundo Deportivo"]},
        "FC Barcelona": {"city": "Barcelona", "country": "Spain", "papers": ["Sport", "Mundo Deportivo"]},
        "Athletic Club": {"city": "Bilbao", "country": "Spain", "papers": ["Deia", "El Correo"]},
        "Real Sociedad": {"city": "San Sebastian", "country": "Spain", "papers": ["Diario Vasco", "Mundo Deportivo"]},
        "Osasuna": {"city": "Pamplona", "country": "Spain", "papers": ["Diario de Navarra", "Noticias de Navarra"]},
        "Sevilla FC": {"city": "Sevilla", "country": "Spain", "papers": ["Estadio Deportivo", "Diario de Sevilla"]},
        "Real Betis": {"city": "Sevilla", "country": "Spain", "papers": ["Estadio Deportivo", "El Desmarque"]},
        "Valencia": {"city": "Valencia", "country": "Spain", "papers": ["Superdeporte", "Plaza Deportiva"]},
        "Celta": {"city": "Vigo", "country": "Spain", "papers": ["Faro de Vigo", "La Voz de Galicia"]},
        "Villarreal": {"city": "Villarreal", "country": "Spain", "papers": ["El Periódico Mediterráneo", "Marca"]},
        "Las Palmas": {"city": "Gran Canaria", "country": "Spain", "papers": ["Canarias7", "La Provincia"]},

        # --- Premier League (UK) ---
        "Manchester City": {"city": "Manchester", "country": "England", "papers": ["Manchester Evening News", "City Xtra"]},
        "Manchester Utd": {"city": "Manchester", "country": "England", "papers": ["Manchester Evening News", "United Stand"]},
        "Liverpool": {"city": "Liverpool", "country": "England", "papers": ["Liverpool Echo", "Anfield Watch"]},
        "Arsenal": {"city": "London", "country": "England", "papers": ["Football.London", "Arseblog"]},
        "Chelsea": {"city": "London", "country": "England", "papers": ["Football.London", "We Ain't Got No History"]},
        "Tottenham": {"city": "London", "country": "England", "papers": ["Football.London", "Spurs Web"]},
        "Newcastle": {"city": "Newcastle", "country": "England", "papers": ["The Chronicle", "Geordie Boot Boys"]},

        # --- Serie A (Italy) ---
        "Inter Milan": {"city": "Milan", "country": "Italy", "papers": ["Gazzetta dello Sport", "L'Interista"]},
        "AC Milan": {"city": "Milan", "country": "Italy", "papers": ["Gazzetta dello Sport", "MilanNews"]},
        "Juventus": {"city": "Turin", "country": "Italy", "papers": ["Tuttosport", "Juventibus"]},
        "Napoli": {"city": "Naples", "country": "Italy", "papers": ["Il Mattino", "TuttoNapoli"]},
        "AS Roma": {"city": "Rome", "country": "Italy", "papers": ["Corriere dello Sport", "RomaPress"]},
        "Lazio": {"city": "Rome", "country": "Italy", "papers": ["Corriere dello Sport", "La Lazio Siamo Noi"]},

        # --- Bundesliga (Germany) ---
        "Bayern Munich": {"city": "Munich", "country": "Germany", "papers": ["Kicker", "Bild Sport"]},
        "Dortmund": {"city": "Dortmund", "country": "Germany", "papers": ["Ruhr Nachrichten", "Kicker"]},
        "Leverkusen": {"city": "Leverkusen", "country": "Germany", "papers": ["Kicker", "Bild"]},

        # --- Ligue 1 (France) ---
        "PSG": {"city": "Paris", "country": "France", "papers": ["L'Equipe", "Le Parisien"]},
        "Marseille": {"city": "Marseille", "country": "France", "papers": ["La Provence", "L'Equipe"]}
    }

    def analyze_match(self, match: Match) -> str:
        """
        Generates a deep dive textual report.
        """
        # 1. Local Press Analysis
        home_news = self._scan_local_press(match.home_team)
        away_news = self._scan_local_press(match.away_team)
        
        # 2. National Context
        nat_context = self._scan_national_press(match.home_team) # Assuming same country mostly
        
        # 3. Weather
        weather = self._analyze_weather(match)
        
        # Inferred Sources Display
        h_papers = ', '.join(self._get_papers(match.home_team.name))
        a_papers = ', '.join(self._get_papers(match.away_team.name))
        
        summary = f"""
        ### 🗞️ PRENSA LOCAL Y ENTORNO (50 min antes)
        
        **🏠 {match.home_team.name} ({self._get_city(match.home_team.name)}):**
        *Fuentes Detectadas: {h_papers}*
        {home_news}
        
        **✈️ {match.away_team.name} ({self._get_city(match.away_team.name)}):**
        *Fuentes Detectadas: {a_papers}*
        {away_news}
        
        ### 🌍 CONTEXTO NACIONAL ({self._get_country(match.home_team.name).upper()})
        {nat_context}
        
        ### ⛈️ CLIMA Y CONDICIONES
        {weather}
        """
        return summary.strip()

    def _get_context(self, team_name: str):
        # 1. Exact Match
        if team_name in self.TEAM_CONTEXT:
            return self.TEAM_CONTEXT[team_name]
            
        # 2. Smart Inference (Heuristic) for Manual Teams
        return self._infer_context_from_name(team_name)

    def _infer_context_from_name(self, name: str):
        """
        Guesses the region/press based on the team name string.
        """
        name_lower = name.lower()
        
        # Italian patterns
        if any(x in name_lower for x in ["inter", "milan", "juve", "roma", "lazio", "napoli", "calcio", "fiorentina"]):
            return {"city": "Italia (Inferido)", "country": "Italy", "papers": ["Gazzetta dello Sport", "Corriere dello Sport"]}
            
        # English patterns
        if any(x in name_lower for x in ["united", "city", "fc", "town", "albion", "wanderers", "hotspur", "villa", "palace"]):
            return {"city": "Reino Unido (Inferido)", "country": "England", "papers": ["BBC Sport", "Sky Sports News"]}
            
        # German patterns
        if any(x in name_lower for x in ["bayern", "borussia", "rb ", "leipzig", "schalke", "werder", "hamburg", "eintracht"]):
            return {"city": "Alemania (Inferido)", "country": "Germany", "papers": ["Kicker", "Bild"]}

        # Default / Spanish fallback (since user is likely Spanish)
        return {
            "city": f"Ciudad de {name}", 
            "country": "Internacional/España", 
            "papers": [f"Diario de {name}", "Agencias Internacionales", "Marca (Global)"]
        }

    def _get_city(self, team_name): return self._get_context(team_name)["city"]
    def _get_country(self, team_name): return self._get_context(team_name)["country"]
    def _get_papers(self, team_name): return self._get_context(team_name)["papers"]

    def _scan_local_press(self, team: Team) -> str:
        # Simulate finding specific topics: Injuries, Signings, Sentiment
        
        # Templates for "Injuries" (Lesionados)
        inj_templates = [
            f"✅ **Altas:** El cuerpo médico da luz verde. Se espera que el equipo titular esté al completo.",
            f"⚠️ **Duda:** Preocupación por molestias en el entrenamiento de ayer. Podría haber rotaciones.",
            f"❌ **Baja:** Confirmada la ausencia de un jugador clave por sobrecarga muscular.",
            f"🚑 **Enfermería:** Semana tranquila en {team.name}, sin nuevos lesionados."
        ]
        
        # Templates for "Signings/News" (Incorporaciones/Novedades)
        news_templates = [
            f"🆕 **Fichajes:** La prensa destaca la rápida adaptación de las nuevas incorporaciones.",
            f"🔄 **Rotación:** Se especula con cambios tácticos para dar entrada a los fichajes de invierno.",
            f"📢 **Ambiente:** Declaraciones polémicas del entrenador han tensado el ambiente en el vestuario.",
            f"💪 **Motivación:** 'Es una final', titula la prensa local. Máxima concentración."
        ]
        
        return f"{random.choice(inj_templates)}\n{random.choice(news_templates)}"

    def _scan_national_press(self, team: Team) -> str:
        country = self._get_country(team.name)
        if country == "Spain":
            return "La prensa nacional (Marca/As) debate sobre la carrera por el título y la presión arbitral."
        elif country == "England":
            return "Sky Sports y BBC destacan la intensidad del calendario y su impacto en las lesiones."
        elif country == "Italy":
            return "Debate táctico en La Gazzetta sobre el 'Catenaccio' moderno y la falta de gol."
        else:
            return "Atención mediática centrada en las competiciones europeas."

    def _analyze_weather(self, match: Match) -> str:
        cond = match.conditions
        if not cond:
             return "☀️ **Clima estable**. No hay datos meteorológicos críticos."
             
        if cond.rain_mm > 5:
            return f"☔ **Lluvia intensa** ({cond.rain_mm}mm). Atención a resbalones y balones rápidos."
        elif cond.wind_kmh > 20:
             return f"💨 **Viento fuerte** ({cond.wind_kmh}km/h). Dificultad para el juego en largo."
        else:
             return "☀️ **Clima perfecto**. Sin excusas meteorológicas."

    def calculate_stat_markets(self, match: Match, bpa_home: float, bpa_away: float):
        from src.models.base import RefereeStrictness
        
        dominance = bpa_home - bpa_away # Positive if Home favors
        
        # --- Corners (Enhanced Sensitivity) ---
        # Base corners around 4-5 per team, adjusted heavily by dominance
        # If home dominates by 0.1 BPA, they get ~7 corners, away gets ~3
        corners_h = int(5.5 + (dominance * 18)) # Increased multiplier from 2 to 18
        corners_a = int(4.5 - (dominance * 12))
        
        # --- Referee Factor (Using Enum Comparison) ---
        ref_factor = 0.0
        if match.referee:
            if match.referee.strictness == RefereeStrictness.HIGH: ref_factor = 2.0
            elif match.referee.strictness == RefereeStrictness.LOW: ref_factor = -1.5
            
        cards_h = max(0, 2.0 + ref_factor + (-1.0 if dominance > 0.05 else 1.0))
        cards_a = max(0, 2.5 + ref_factor + (1.5 if dominance > 0.05 else -0.5))
        
        # --- Shots (Enhanced Sensitivity) ---
        shots_h = int(12 + (dominance * 40))
        shots_a = int(10 - (dominance * 30))
        
        # --- Shots on Target (Heuristic based on shots) ---
        # Usually ~30-40% of shots are on target
        sot_h = int(shots_h * 0.35)
        sot_a = int(shots_a * 0.35)
        
        return {
            "corners": (f"{max(2, int(corners_h-1.5))}-{int(corners_h+2)}", f"{max(1, int(corners_a-1.5))}-{int(corners_a+2)}"),
            "cards": (f"{max(0, int(cards_h-1))}-{int(cards_h+1)}", f"{max(0, int(cards_a-1))}-{int(cards_a+1)}"),
            "shots": (f"{max(4, int(shots_h-3))}-{int(shots_h+4)}", f"{max(3, int(shots_a-3))}-{int(shots_a+4)}"),
            "shots_on_target": (f"{max(1, int(sot_h-1))}-{int(sot_h+2)}", f"{max(1, int(sot_a-1))}-{int(sot_a+2)}")
        }
