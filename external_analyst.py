"""
ExternalAnalyst — Análisis Real de Prensa e Inteligencia de Partido
====================================================================
Usa la API de Claude con búsqueda web integrada para obtener noticias
REALES y actualizadas de cada equipo: lesiones, estado del vestuario,
rendimiento reciente, relación con prensa, ambiente, etc.
"""

import os
import re
import json
import requests
from src.models.base import Match, Team


PRESS_ANALYSIS_PROMPT = """Eres un analista de fútbol experto. Busca noticias REALES y actualizadas sobre el equipo "{team_name}" para su partido del {match_date} en {league}.

BUSCA específicamente en prensa deportiva local y nacional:
1. Lesiones o bajas confirmadas para este partido
2. Jugadores en duda o con problemas físicos
3. Estado del vestuario: tensiones internas, ambiente, relación entrenador-plantilla
4. Relación del club con la prensa local esta semana
5. Últimos 3 resultados y sensaciones (¿vienen bien? ¿mal?)
6. Noticias relevantes de esta semana (presión por clasificación, escándalos, motivación especial)

Responde ÚNICAMENTE con este JSON (sin markdown, sin texto extra):
{{"bajas_confirmadas":[],"dudas":[],"estado_vestuario":"positivo|neutro|negativo","descripcion_vestuario":"texto","relacion_prensa":"buena|normal|tensa","sensaciones_recientes":"positivas|neutras|negativas","descripcion_reciente":"texto","noticias_clave":[],"impacto_partido":"positivo|neutro|negativo","resumen":"texto","puntuacion_moral":0.0}}

puntuacion_moral: de -0.15 (muy negativo) a +0.15 (muy positivo)."""


class ExternalAnalyst:

    TEAM_CONTEXT = {

        # =====================================================================
        # LA LIGA (ESPAÑA) — Temporada 2025/26
        # =====================================================================
        "Real Madrid":          {"city": "Madrid",          "papers": ["Marca", "AS", "Defensa Central"]},
        "FC Barcelona":         {"city": "Barcelona",       "papers": ["Sport", "Mundo Deportivo", "El Periódico"]},
        "Atletico Madrid":      {"city": "Madrid",          "papers": ["Marca", "AS", "El Español"]},
        "Athletic Club":        {"city": "Bilbao",          "papers": ["Deia", "El Correo", "Marca Athletic"]},
        "Real Sociedad":        {"city": "San Sebastián",   "papers": ["Diario Vasco", "Noticias de Gipuzkoa"]},
        "Villarreal":           {"city": "Villarreal",      "papers": ["El Periódico Mediterráneo", "Superdeporte"]},
        "Real Betis":           {"city": "Sevilla",         "papers": ["Estadio Deportivo", "El Desmarque Sevilla"]},
        "Sevilla FC":           {"city": "Sevilla",         "papers": ["Estadio Deportivo", "Diario de Sevilla"]},
        "Osasuna":              {"city": "Pamplona",        "papers": ["Diario de Navarra", "Noticias de Navarra"]},
        "Valencia":             {"city": "Valencia",        "papers": ["Superdeporte", "Las Provincias"]},
        "Celta":                {"city": "Vigo",            "papers": ["Faro de Vigo", "La Voz de Galicia"]},
        "Espanyol":             {"city": "Barcelona",       "papers": ["Sport", "Mundo Deportivo", "El Periódico"]},
        "Girona":               {"city": "Girona",          "papers": ["El Punt Avui", "Diari de Girona", "Marca"]},
        "Getafe":               {"city": "Getafe",          "papers": ["Marca", "AS", "El Español"]},
        "Rayo Vallecano":       {"city": "Madrid",          "papers": ["Marca", "AS", "El Español"]},
        "Leganés":              {"city": "Leganés",         "papers": ["Marca", "AS", "El Español"]},
        "Las Palmas":           {"city": "Las Palmas",      "papers": ["Canarias7", "La Provincia", "El Día"]},
        "Mallorca":             {"city": "Palma",           "papers": ["Última Hora", "Diario de Mallorca"]},
        "Alavés":               {"city": "Vitoria",         "papers": ["El Correo", "Noticias de Álava"]},
        "Real Valladolid":      {"city": "Valladolid",      "papers": ["El Norte de Castilla", "La Voz de Valladolid"]},
        # Segunda División (ascendidos/posibles)
        "Real Oviedo":          {"city": "Oviedo",          "papers": ["El Comercio", "La Nueva España", "La Voz de Asturias"]},
        "Sporting de Gijón":    {"city": "Gijón",           "papers": ["El Comercio", "La Nueva España"]},
        "Real Zaragoza":        {"city": "Zaragoza",        "papers": ["Heraldo de Aragón", "El Periódico de Aragón"]},
        "SD Eibar":             {"city": "Eibar",           "papers": ["El Diario Vasco", "El Correo"]},
        "Elche":                {"city": "Elche",           "papers": ["Información", "Superdeporte"]},
        "Almería":              {"city": "Almería",         "papers": ["La Voz de Almería", "Ideal"]},
        "Cádiz":                {"city": "Cádiz",           "papers": ["Diario de Cádiz", "La Voz de Cádiz"]},
        "Granada":              {"city": "Granada",         "papers": ["Ideal", "Granada Hoy"]},
        "Levante":              {"city": "Valencia",        "papers": ["Superdeporte", "Las Provincias"]},
        "Deportivo":            {"city": "A Coruña",        "papers": ["La Voz de Galicia", "El Ideal Gallego"]},
        "Tenerife":             {"city": "Tenerife",        "papers": ["El Día", "Canarias7"]},
        "Burgos CF":            {"city": "Burgos",          "papers": ["Diario de Burgos", "El Mundo de Burgos"]},
        "Huesca":               {"city": "Huesca",          "papers": ["Diario del Alto Aragón", "Heraldo de Aragón"]},
        "Mirandés":             {"city": "Miranda de Ebro", "papers": ["El Correo", "Diario de Burgos"]},
        "Albacete":             {"city": "Albacete",        "papers": ["La Tribuna de Albacete", "ABC"]},
        "Cartagena":            {"city": "Cartagena",       "papers": ["La Verdad", "ABC Murcia"]},
        "Córdoba":              {"city": "Córdoba",         "papers": ["Diario Córdoba", "ABC Córdoba"]},
        "Numancia":             {"city": "Soria",           "papers": ["Heraldo de Soria", "Soria Noticias"]},
        "Racing Santander":     {"city": "Santander",       "papers": ["El Diario Montañés", "Alerta"]},
        "Ponferradina":         {"city": "Ponferrada",      "papers": ["El Bierzo", "La Crónica de León"]},

        # =====================================================================
        # PREMIER LEAGUE (INGLATERRA) — Temporada 2025/26
        # =====================================================================
        "Manchester City":      {"city": "Manchester",      "papers": ["Manchester Evening News", "The Guardian", "Sky Sports"]},
        "Arsenal":              {"city": "Londres",         "papers": ["Football.London", "The Guardian", "Evening Standard"]},
        "Liverpool":            {"city": "Liverpool",       "papers": ["Liverpool Echo", "The Guardian", "Sky Sports"]},
        "Chelsea":              {"city": "Londres",         "papers": ["Football.London", "Evening Standard", "The Telegraph"]},
        "Manchester Utd":       {"city": "Manchester",      "papers": ["Manchester Evening News", "The Telegraph", "Sky Sports"]},
        "Tottenham":            {"city": "Londres",         "papers": ["Football.London", "The Guardian", "Sky Sports"]},
        "Newcastle":            {"city": "Newcastle",       "papers": ["The Chronicle", "Chronicle Live", "BBC Sport"]},
        "Aston Villa":          {"city": "Birmingham",      "papers": ["Birmingham Mail", "The Guardian", "Sky Sports"]},
        "West Ham":             {"city": "Londres",         "papers": ["Football.London", "Evening Standard", "Sky Sports"]},
        "Brighton":             {"city": "Brighton",        "papers": ["The Argus", "BBC Sport", "Sky Sports"]},
        "Wolves":               {"city": "Wolverhampton",   "papers": ["Express & Star", "Sky Sports", "BBC Sport"]},
        "Everton":              {"city": "Liverpool",       "papers": ["Liverpool Echo", "Sky Sports", "BBC Sport"]},
        "Nottingham Forest":    {"city": "Nottingham",      "papers": ["Nottingham Post", "BBC Sport", "Sky Sports"]},
        "Crystal Palace":       {"city": "Londres",         "papers": ["South London Press", "Football.London", "Sky Sports"]},
        "Brentford":            {"city": "Londres",         "papers": ["Football.London", "Sky Sports", "BBC Sport"]},
        "Fulham":               {"city": "Londres",         "papers": ["Football.London", "Evening Standard", "Sky Sports"]},
        "Bournemouth":          {"city": "Bournemouth",     "papers": ["Bournemouth Echo", "Sky Sports", "BBC Sport"]},
        "Leicester":            {"city": "Leicester",       "papers": ["Leicester Mercury", "Sky Sports", "BBC Sport"]},
        "Southampton":          {"city": "Southampton",     "papers": ["Daily Echo", "Sky Sports", "BBC Sport"]},
        "Ipswich":              {"city": "Ipswich",         "papers": ["East Anglian Daily Times", "Sky Sports", "BBC Sport"]},

        # =====================================================================
        # SERIE A (ITALIA) — Temporada 2025/26
        # =====================================================================
        "Inter Milan":          {"city": "Milán",           "papers": ["Gazzetta dello Sport", "Corriere della Sera", "La Repubblica"]},
        "AC Milan":             {"city": "Milán",           "papers": ["Gazzetta dello Sport", "Corriere della Sera", "MilanNews"]},
        "Juventus":             {"city": "Turín",           "papers": ["Tuttosport", "Gazzetta dello Sport", "La Stampa"]},
        "Napoli":               {"city": "Nápoles",         "papers": ["Il Mattino", "Corriere del Mezzogiorno", "TuttoNapoli"]},
        "AS Roma":              {"city": "Roma",            "papers": ["Corriere dello Sport", "La Repubblica", "RomaPress"]},
        "Lazio":                {"city": "Roma",            "papers": ["Corriere dello Sport", "La Repubblica", "Lazionews24"]},
        "Atalanta":             {"city": "Bérgamo",         "papers": ["L'Eco di Bergamo", "Gazzetta dello Sport"]},
        "Fiorentina":           {"city": "Florencia",       "papers": ["La Nazione", "Corriere Fiorentino", "Violanews"]},
        "Bologna":              {"city": "Bolonia",         "papers": ["Corriere di Bologna", "Il Resto del Carlino"]},
        "Torino":               {"city": "Turín",           "papers": ["Tuttosport", "La Stampa", "Toro News"]},
        "Udinese":              {"city": "Udine",           "papers": ["Il Messaggero Veneto", "Gazzetta dello Sport"]},
        "Sampdoria":            {"city": "Génova",          "papers": ["Il Secolo XIX", "Gazzetta dello Sport"]},
        "Genoa":                {"city": "Génova",          "papers": ["Il Secolo XIX", "Gazzetta dello Sport"]},
        "Sassuolo":             {"city": "Sassuolo",        "papers": ["Gazzetta di Modena", "Gazzetta dello Sport"]},
        "Hellas Verona":        {"city": "Verona",          "papers": ["L'Arena", "Gazzetta dello Sport"]},
        "Cagliari":             {"city": "Cagliari",        "papers": ["L'Unione Sarda", "La Nuova Sardegna"]},
        "Empoli":               {"city": "Empoli",          "papers": ["Il Tirreno", "La Nazione"]},
        "Parma":                {"city": "Parma",           "papers": ["Gazzetta di Parma", "Gazzetta dello Sport"]},
        "Como":                 {"city": "Como",            "papers": ["La Provincia di Como", "Gazzetta dello Sport"]},
        "Venezia":              {"city": "Venecia",         "papers": ["La Nuova Venezia", "Gazzetta dello Sport"]},
        "Monza":                {"city": "Monza",           "papers": ["Il Cittadino", "Gazzetta dello Sport"]},
        "Lecce":                {"city": "Lecce",           "papers": ["Quotidiano di Puglia", "Gazzetta dello Sport"]},

        # =====================================================================
        # BUNDESLIGA (ALEMANIA) — Temporada 2025/26
        # =====================================================================
        "Bayern Munich":        {"city": "Múnich",          "papers": ["Kicker", "Bild Sport", "Münchner Merkur"]},
        "Bayer Leverkusen":     {"city": "Leverkusen",      "papers": ["Kicker", "Bild Sport", "Rheinische Post"]},
        "Dortmund":             {"city": "Dortmund",        "papers": ["Ruhr Nachrichten", "Kicker", "WAZ"]},
        "RB Leipzig":           {"city": "Leipzig",         "papers": ["Kicker", "Bild Sport", "Leipziger Volkszeitung"]},
        "Stuttgart":            {"city": "Stuttgart",       "papers": ["Stuttgarter Zeitung", "Kicker", "Stuttgarter Nachrichten"]},
        "Frankfurt":            {"city": "Frankfurt",       "papers": ["Frankfurter Allgemeine", "Kicker", "Bild"]},
        "Eintracht Frankfurt":  {"city": "Frankfurt",       "papers": ["Frankfurter Allgemeine", "Kicker", "Bild"]},
        "Wolfsburg":            {"city": "Wolfsburg",       "papers": ["Wolfsburger Allgemeine", "Kicker", "Bild"]},
        "Freiburg":             {"city": "Friburgo",        "papers": ["Badische Zeitung", "Kicker", "Bild"]},
        "Werder Bremen":        {"city": "Bremen",          "papers": ["Weser-Kurier", "Kicker", "Bild"]},
        "Mönchengladbach":      {"city": "Mönchengladbach", "papers": ["Rheinische Post", "Kicker", "Bild"]},
        "Union Berlin":         {"city": "Berlín",          "papers": ["Berliner Zeitung", "Kicker", "BZ Berlin"]},
        "Hoffenheim":           {"city": "Hoffenheim",      "papers": ["Rhein-Neckar-Zeitung", "Kicker", "Bild"]},
        "Mainz":                {"city": "Maguncia",        "papers": ["Allgemeine Zeitung", "Kicker", "Bild"]},
        "Augsburg":             {"city": "Augsburgo",       "papers": ["Augsburger Allgemeine", "Kicker", "Bild"]},
        "Schalke":              {"city": "Gelsenkirchen",   "papers": ["WAZ", "Kicker", "Bild"]},
        "Hamburgo":             {"city": "Hamburgo",        "papers": ["Hamburger Abendblatt", "Kicker", "Bild"]},
        "Heidenheim":           {"city": "Heidenheim",      "papers": ["Heidenheimer Zeitung", "Kicker", "Bild"]},
        "Bochum":               {"city": "Bochum",          "papers": ["WAZ", "Kicker", "Bild"]},
        "Darmstadt":            {"city": "Darmstadt",       "papers": ["Darmstädter Echo", "Kicker", "Bild"]},
        "Holstein Kiel":        {"city": "Kiel",            "papers": ["Kieler Nachrichten", "Kicker", "Bild"]},
        "St. Pauli":            {"city": "Hamburgo",        "papers": ["Hamburger Abendblatt", "Kicker", "Bild"]},

        # =====================================================================
        # LIGUE 1 (FRANCIA) — Temporada 2025/26
        # =====================================================================
        "PSG":                  {"city": "París",           "papers": ["L'Équipe", "Le Parisien", "France Football"]},
        "Marseille":            {"city": "Marsella",        "papers": ["La Provence", "L'Équipe", "France Football"]},
        "Monaco":               {"city": "Mónaco",          "papers": ["L'Équipe", "Nice-Matin", "France Football"]},
        "Lyon":                 {"city": "Lyon",            "papers": ["Le Progrès", "L'Équipe", "France Football"]},
        "Lille":                {"city": "Lille",           "papers": ["La Voix du Nord", "L'Équipe", "France Football"]},
        "Rennes":               {"city": "Rennes",          "papers": ["Ouest-France", "L'Équipe", "France Football"]},
        "Nice":                 {"city": "Niza",            "papers": ["Nice-Matin", "L'Équipe", "France Football"]},
        "Lens":                 {"city": "Lens",            "papers": ["La Voix du Nord", "L'Équipe", "France Football"]},
        "Strasbourg":           {"city": "Estrasburgo",     "papers": ["Les Dernières Nouvelles d'Alsace", "L'Équipe"]},
        "Nantes":               {"city": "Nantes",          "papers": ["Ouest-France", "L'Équipe", "France Football"]},
        "Montpellier":          {"city": "Montpellier",     "papers": ["Midi Libre", "L'Équipe", "France Football"]},
        "Toulouse":             {"city": "Toulouse",        "papers": ["La Dépêche du Midi", "L'Équipe"]},
        "Reims":                {"city": "Reims",           "papers": ["L'Union", "L'Équipe", "France Football"]},
        "Brest":                {"city": "Brest",           "papers": ["Ouest-France", "Le Télégramme", "L'Équipe"]},
        "Le Havre":             {"city": "El Havre",        "papers": ["Paris-Normandie", "L'Équipe", "France Football"]},
        "Metz":                 {"city": "Metz",            "papers": ["Le Républicain Lorrain", "L'Équipe"]},
        "Lorient":              {"city": "Lorient",         "papers": ["Le Télégramme", "Ouest-France", "L'Équipe"]},
        "Angers":               {"city": "Angers",          "papers": ["Ouest-France", "L'Équipe", "France Football"]},
        "Clermont":             {"city": "Clermont",        "papers": ["La Montagne", "L'Équipe", "France Football"]},
        "Auxerre":              {"city": "Auxerre",         "papers": ["L'Yonne Républicaine", "L'Équipe"]},
        "Bordeaux":             {"city": "Burdeos",         "papers": ["Sud Ouest", "L'Équipe", "France Football"]},
        "Saint-Étienne":        {"city": "Saint-Étienne",   "papers": ["Le Progrès", "L'Équipe", "France Football"]},
    }

    def _get_context(self, team_name):
        if team_name in self.TEAM_CONTEXT:
            return self.TEAM_CONTEXT[team_name]
        # Búsqueda parcial
        for key, val in self.TEAM_CONTEXT.items():
            if key.lower() in team_name.lower() or team_name.lower() in key.lower():
                return val
        # Inferencia por país
        name_l = team_name.lower()
        if any(x in name_l for x in ["united", "city", "town", "hotspur", "villa", "albion", "wanderers"]):
            return {"city": "Reino Unido", "papers": ["BBC Sport", "Sky Sports", "The Guardian"]}
        if any(x in name_l for x in ["münchen", "borussia", "schalke", "frankfurt", "werder", "rb "]):
            return {"city": "Alemania", "papers": ["Kicker", "Bild Sport"]}
        if any(x in name_l for x in ["milan", "inter", "juve", "roma", "lazio", "napoli", "fior"]):
            return {"city": "Italia", "papers": ["Gazzetta dello Sport", "Corriere dello Sport"]}
        if any(x in name_l for x in ["paris", "marseille", "lyon", "monaco", "lille", "nice"]):
            return {"city": "Francia", "papers": ["L'Équipe", "France Football"]}
        return {"city": f"Ciudad de {team_name}", "papers": [f"Prensa de {team_name}", "Marca"]}

    def _call_claude_with_search(self, team_name, league, match_date_str):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        prompt = PRESS_ANALYSIS_PROMPT.format(
            team_name=team_name, league=league, match_date=match_date_str
        )
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=35
            )
            if resp.status_code != 200:
                print(f"[ExternalAnalyst] API error {resp.status_code}")
                return None
            data = resp.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            text = re.sub(r"```json|```", "", text).strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"[ExternalAnalyst] Error llamada Claude: {e}")
        return None

    def _fallback_analysis(self, team):
        bajas = [p.name for p in team.players if p.status.value == "Baja"]
        dudas = [p.name for p in team.players if p.status.value == "Duda"]
        moral = -(len(bajas) * 0.02) - (len(dudas) * 0.01)
        estado = "negativo" if moral < -0.04 else ("positivo" if moral > 0.02 else "neutro")
        return {
            "bajas_confirmadas": bajas, "dudas": dudas,
            "estado_vestuario": estado,
            "descripcion_vestuario": "Sin información directa de prensa disponible.",
            "relacion_prensa": "normal", "sensaciones_recientes": "neutras",
            "descripcion_reciente": "Sin datos de rendimiento reciente disponibles.",
            "noticias_clave": [],
            "impacto_partido": "neutro" if moral >= -0.02 else "negativo",
            "resumen": f"{len(bajas)} bajas confirmadas, {len(dudas)} dudas en el equipo.",
            "puntuacion_moral": round(moral, 3)
        }

    def _format_team_report(self, analysis, team_name, papers):
        lines = [f"*Fuentes: {', '.join(papers[:2])}*"]
        if analysis.get("bajas_confirmadas"):
            lines.append(f"🚨 **Bajas:** {', '.join(analysis['bajas_confirmadas'])}")
        if analysis.get("dudas"):
            lines.append(f"⏳ **Dudas:** {', '.join(analysis['dudas'])}")
        if not analysis.get("bajas_confirmadas") and not analysis.get("dudas"):
            lines.append("✅ **Sin Bajas Relevantes:** Plantilla disponible al completo")
        vest = analysis.get("estado_vestuario", "neutro")
        vest_icon = {"positivo": "💚", "neutro": "🟡", "negativo": "🔴"}.get(vest, "🟡")
        desc_vest = analysis.get("descripcion_vestuario", "")
        if desc_vest:
            lines.append(f"{vest_icon} **Vestuario:** {desc_vest}")
        prensa = analysis.get("relacion_prensa", "normal")
        if prensa == "tensa":
            lines.append("📰 **Prensa local:** Relación tensa con el club esta semana")
        elif prensa == "buena":
            lines.append("📰 **Prensa local:** Tono positivo y apoyo al equipo")
        sens = analysis.get("sensaciones_recientes", "neutras")
        desc_rec = analysis.get("descripcion_reciente", "")
        if desc_rec:
            s_icon = {"positivas": "📈", "neutras": "➡️", "negativas": "📉"}.get(sens, "➡️")
            lines.append(f"{s_icon} **Forma:** {desc_rec}")
        for noticia in analysis.get("noticias_clave", [])[:2]:
            lines.append(f"🔹 {noticia}")
        moral = analysis.get("puntuacion_moral", 0.0)
        impacto = analysis.get("impacto_partido", "neutro")
        i_map = {
            "positivo": f"✅ **Impacto POSITIVO** en el partido (moral: +{abs(moral):.2f})",
            "neutro":   "⚪ **Impacto NEUTRO** en el partido",
            "negativo": f"⚠️ **Impacto NEGATIVO** en el partido (lastre: -{abs(moral):.2f})"
        }
        lines.append(i_map.get(impacto, "⚪ **Impacto NEUTRO**"))
        return "\n".join(lines)

    def get_detailed_intelligence(self, match: Match) -> dict:
        match_date_str = match.date.strftime("%d/%m/%Y") if match.date else "hoy"
        league = match.competition or "Liga"
        print(f"[ExternalAnalyst] Analizando prensa real: {match.home_team.name}")
        home_analysis = self._call_claude_with_search(match.home_team.name, league, match_date_str)
        if not home_analysis:
            home_analysis = self._fallback_analysis(match.home_team)
        print(f"[ExternalAnalyst] Analizando prensa real: {match.away_team.name}")
        away_analysis = self._call_claude_with_search(match.away_team.name, league, match_date_str)
        if not away_analysis:
            away_analysis = self._fallback_analysis(match.away_team)
        h_ctx = self._get_context(match.home_team.name)
        a_ctx = self._get_context(match.away_team.name)
        h_report = self._format_team_report(home_analysis, match.home_team.name, h_ctx["papers"])
        a_report = self._format_team_report(away_analysis, match.away_team.name, a_ctx["papers"])
        weather = self._analyze_weather(match)
        report = f"""### PRENSA LOCAL Y ENTORNO

**🏠 {match.home_team.name} ({h_ctx['city']}):**
{h_report}

**✈️ {match.away_team.name} ({a_ctx['city']}):**
{a_report}

### 🌤️ CONDICIONES
{weather}"""
        return {
            "report": report,
            "impact": {
                "home": home_analysis.get("puntuacion_moral", 0.0),
                "away": away_analysis.get("puntuacion_moral", 0.0)
            },
            "home_analysis": home_analysis,
            "away_analysis": away_analysis
        }

    def analyze_match(self, match: Match) -> str:
        return self.get_detailed_intelligence(match)["report"]

    def _analyze_weather(self, match: Match) -> str:
        cond = match.conditions
        if not cond:
            return "☀️ **Clima estable**. Sin datos críticos."
        if cond.rain_mm > 5:
            return f"☔ **Lluvia intensa** ({cond.rain_mm}mm). Puede afectar el juego en corto."
        elif cond.wind_kmh > 20:
            return f"💨 **Viento fuerte** ({cond.wind_kmh}km/h). Dificulta el juego aéreo."
        return "☀️ **Clima perfecto**. Sin factores meteorológicos condicionantes."

    def calculate_stat_markets(self, match: Match, bpa_home: float, bpa_away: float):
        from src.models.base import RefereeStrictness
        dominance = max(-0.25, min(0.25, bpa_home - bpa_away))
        corners_h = max(2.0, round(5.0 + (dominance * 7), 1))
        corners_a = max(1.5, round(4.5 - (dominance * 5), 1))
        ref_factor = 0.0
        if match.referee:
            if match.referee.strictness == RefereeStrictness.HIGH: ref_factor = 1.5
            elif match.referee.strictness == RefereeStrictness.LOW: ref_factor = -1.0
        cards_h = max(0.5, 1.8 + ref_factor + (-0.8 if dominance > 0.05 else 0.8))
        cards_a = max(0.5, 2.2 + ref_factor + (1.0 if dominance > 0.05 else -0.3))
        shots_h = max(4.0, round(11.0 + (dominance * 18), 1))
        shots_a = max(3.0, round(9.0  - (dominance * 14), 1))
        sot_h = round(shots_h * 0.33, 1)
        sot_a = round(shots_a * 0.33, 1)
        return {
            "corners": (f"{max(2,int(corners_h-1))}-{int(corners_h+2)}", f"{max(1,int(corners_a-1))}-{int(corners_a+2)}"),
            "cards":   (f"{max(0,int(cards_h-1))}-{int(cards_h+1)}", f"{max(0,int(cards_a-1))}-{int(cards_a+1)}"),
            "shots":   (f"{max(4,int(shots_h-3))}-{int(shots_h+3)}", f"{max(3,int(shots_a-2))}-{int(shots_a+3)}"),
            "shots_on_target": (f"{max(1,int(sot_h-1))}-{int(sot_h+2)}", f"{max(1,int(sot_a-1))}-{int(sot_a+2)}")
        }

