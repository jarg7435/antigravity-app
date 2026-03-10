"""
ExternalAnalyst v2 — Análisis de Prensa con 3 capas
=====================================================
Capa 1 (mejor): Claude API + búsqueda web    → requiere ANTHROPIC_API_KEY
Capa 2 (buena): Google News RSS              → gratuito, sin API key
Capa 3 (básica): Fallback con datos internos → siempre disponible
"""

import os
import re
import json
import requests
from src.models.base import Match, Team


PRESS_ANALYSIS_PROMPT = """Eres un analista de fútbol experto. Busca noticias REALES y actualizadas sobre el equipo "{team_name}" para su partido del {match_date} en {league}.

BUSCA específicamente en prensa deportiva española/local:
1. Lesiones o bajas confirmadas para este partido
2. Jugadores en duda o con problemas físicos
3. Estado del vestuario: tensiones internas, ambiente, relación entrenador-plantilla
4. Relación del club con la prensa local esta semana
5. Últimos 3 resultados y sensaciones
6. Noticias relevantes de esta semana

Responde ÚNICAMENTE con este JSON (sin markdown, sin texto extra):
{{"bajas_confirmadas":[],"dudas":[],"estado_vestuario":"positivo|neutro|negativo","descripcion_vestuario":"texto","relacion_prensa":"buena|normal|tensa","sensaciones_recientes":"positivas|neutras|negativas","descripcion_reciente":"texto","noticias_clave":[],"impacto_partido":"positivo|neutro|negativo","resumen":"texto","puntuacion_moral":0.0}}

puntuacion_moral: de -0.15 (muy negativo) a +0.15 (muy positivo)."""


class ExternalAnalyst:

    TEAM_CONTEXT = {
        # =====================================================================
        # LA LIGA (ESPAÑA)
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
        "Espanyol":             {"city": "Barcelona",       "papers": ["Sport", "Mundo Deportivo"]},
        "Girona":               {"city": "Girona",          "papers": ["El Punt Avui", "Diari de Girona"]},
        "Getafe":               {"city": "Getafe",          "papers": ["Marca", "AS"]},
        "Rayo Vallecano":       {"city": "Madrid",          "papers": ["Marca", "AS"]},
        "Leganés":              {"city": "Leganés",         "papers": ["Marca", "AS"]},
        "Las Palmas":           {"city": "Las Palmas",      "papers": ["Canarias7", "La Provincia"]},
        "Mallorca":             {"city": "Palma",           "papers": ["Última Hora", "Diario de Mallorca"]},
        "Alavés":               {"city": "Vitoria",         "papers": ["El Correo", "Noticias de Álava"]},
        "Real Valladolid":      {"city": "Valladolid",      "papers": ["El Norte de Castilla", "La Voz"]},
        "Real Oviedo":          {"city": "Oviedo",          "papers": ["El Comercio", "La Nueva España"]},
        "Sporting de Gijón":    {"city": "Gijón",           "papers": ["El Comercio", "La Nueva España"]},
        "Real Zaragoza":        {"city": "Zaragoza",        "papers": ["Heraldo de Aragón", "El Periódico de Aragón"]},
        "Cádiz":                {"city": "Cádiz",           "papers": ["Diario de Cádiz", "La Voz de Cádiz"]},
        "Granada":              {"city": "Granada",         "papers": ["Ideal", "Granada Hoy"]},
        "Levante":              {"city": "Valencia",        "papers": ["Superdeporte", "Las Provincias"]},
        "Tenerife":             {"city": "Tenerife",        "papers": ["El Día", "Canarias7"]},
        "Racing Santander":     {"city": "Santander",       "papers": ["El Diario Montañés", "Alerta"]},
        "Deportivo":            {"city": "A Coruña",        "papers": ["La Voz de Galicia", "El Ideal Gallego"]},
        "Almería":              {"city": "Almería",         "papers": ["La Voz de Almería", "Ideal"]},
        "Burgos CF":            {"city": "Burgos",          "papers": ["Diario de Burgos", "El Mundo de Burgos"]},
        "Córdoba":              {"city": "Córdoba",         "papers": ["Diario Córdoba", "ABC Córdoba"]},
        "Elche":                {"city": "Elche",           "papers": ["Información", "Superdeporte"]},
        "Huesca":               {"city": "Huesca",          "papers": ["Diario del Alto Aragón", "Heraldo"]},
        "Albacete":             {"city": "Albacete",        "papers": ["La Tribuna de Albacete", "ABC"]},
        "Cartagena":            {"city": "Cartagena",       "papers": ["La Verdad", "ABC Murcia"]},
        # =====================================================================
        # PREMIER LEAGUE
        # =====================================================================
        "Manchester City":      {"city": "Manchester",      "papers": ["Manchester Evening News", "The Guardian"]},
        "Arsenal":              {"city": "Londres",         "papers": ["Football.London", "The Guardian"]},
        "Liverpool":            {"city": "Liverpool",       "papers": ["Liverpool Echo", "The Guardian"]},
        "Chelsea":              {"city": "Londres",         "papers": ["Football.London", "Evening Standard"]},
        "Manchester Utd":       {"city": "Manchester",      "papers": ["Manchester Evening News", "The Telegraph"]},
        "Tottenham":            {"city": "Londres",         "papers": ["Football.London", "The Guardian"]},
        "Newcastle":            {"city": "Newcastle",       "papers": ["The Chronicle", "BBC Sport"]},
        "Aston Villa":          {"city": "Birmingham",      "papers": ["Birmingham Mail", "Sky Sports"]},
        "West Ham":             {"city": "Londres",         "papers": ["Football.London", "Evening Standard"]},
        "Brighton":             {"city": "Brighton",        "papers": ["The Argus", "BBC Sport"]},
        "Wolves":               {"city": "Wolverhampton",   "papers": ["Express & Star", "Sky Sports"]},
        "Everton":              {"city": "Liverpool",       "papers": ["Liverpool Echo", "Sky Sports"]},
        "Nottingham Forest":    {"city": "Nottingham",      "papers": ["Nottingham Post", "BBC Sport"]},
        "Crystal Palace":       {"city": "Londres",         "papers": ["South London Press", "Football.London"]},
        "Brentford":            {"city": "Londres",         "papers": ["Football.London", "Sky Sports"]},
        "Fulham":               {"city": "Londres",         "papers": ["Football.London", "Evening Standard"]},
        "Bournemouth":          {"city": "Bournemouth",     "papers": ["Bournemouth Echo", "Sky Sports"]},
        "Leicester":            {"city": "Leicester",       "papers": ["Leicester Mercury", "Sky Sports"]},
        "Southampton":          {"city": "Southampton",     "papers": ["Daily Echo", "Sky Sports"]},
        "Ipswich":              {"city": "Ipswich",         "papers": ["East Anglian Daily Times", "Sky Sports"]},
        # =====================================================================
        # SERIE A
        # =====================================================================
        "Inter Milan":          {"city": "Milán",           "papers": ["Gazzetta dello Sport", "Corriere della Sera"]},
        "AC Milan":             {"city": "Milán",           "papers": ["Gazzetta dello Sport", "La Repubblica"]},
        "Juventus":             {"city": "Turín",           "papers": ["Tuttosport", "Gazzetta dello Sport"]},
        "Napoli":               {"city": "Nápoles",         "papers": ["Il Mattino", "Corriere del Mezzogiorno"]},
        "AS Roma":              {"city": "Roma",            "papers": ["Corriere dello Sport", "La Repubblica"]},
        "Lazio":                {"city": "Roma",            "papers": ["Corriere dello Sport", "Lazionews24"]},
        "Atalanta":             {"city": "Bérgamo",         "papers": ["L'Eco di Bergamo", "Gazzetta dello Sport"]},
        "Fiorentina":           {"city": "Florencia",       "papers": ["La Nazione", "Corriere Fiorentino"]},
        "Bologna":              {"city": "Bolonia",         "papers": ["Corriere di Bologna", "Il Resto del Carlino"]},
        "Torino":               {"city": "Turín",           "papers": ["Tuttosport", "La Stampa"]},
        "Udinese":              {"city": "Udine",           "papers": ["Il Messaggero Veneto", "Gazzetta dello Sport"]},
        "Genoa":                {"city": "Génova",          "papers": ["Il Secolo XIX", "Gazzetta dello Sport"]},
        "Cagliari":             {"city": "Cagliari",        "papers": ["L'Unione Sarda", "La Nuova Sardegna"]},
        "Empoli":               {"city": "Empoli",          "papers": ["Il Tirreno", "La Nazione"]},
        "Parma":                {"city": "Parma",           "papers": ["Gazzetta di Parma", "Gazzetta dello Sport"]},
        "Como":                 {"city": "Como",            "papers": ["La Provincia di Como", "Gazzetta dello Sport"]},
        "Venezia":              {"city": "Venecia",         "papers": ["La Nuova Venezia", "Gazzetta dello Sport"]},
        "Monza":                {"city": "Monza",           "papers": ["Il Cittadino", "Gazzetta dello Sport"]},
        "Lecce":                {"city": "Lecce",           "papers": ["Quotidiano di Puglia", "Gazzetta dello Sport"]},
        "Hellas Verona":        {"city": "Verona",          "papers": ["L'Arena", "Gazzetta dello Sport"]},
        # =====================================================================
        # BUNDESLIGA
        # =====================================================================
        "Bayern Munich":        {"city": "Múnich",          "papers": ["Kicker", "Bild Sport", "Münchner Merkur"]},
        "Bayer Leverkusen":     {"city": "Leverkusen",      "papers": ["Kicker", "Rheinische Post"]},
        "Dortmund":             {"city": "Dortmund",        "papers": ["Ruhr Nachrichten", "Kicker"]},
        "RB Leipzig":           {"city": "Leipzig",         "papers": ["Kicker", "Leipziger Volkszeitung"]},
        "Stuttgart":            {"city": "Stuttgart",       "papers": ["Stuttgarter Zeitung", "Kicker"]},
        "Eintracht Frankfurt":  {"city": "Frankfurt",       "papers": ["Frankfurter Allgemeine", "Kicker"]},
        "Wolfsburg":            {"city": "Wolfsburg",       "papers": ["Wolfsburger Allgemeine", "Kicker"]},
        "Freiburg":             {"city": "Friburgo",        "papers": ["Badische Zeitung", "Kicker"]},
        "Werder Bremen":        {"city": "Bremen",          "papers": ["Weser-Kurier", "Kicker"]},
        "Mönchengladbach":      {"city": "Mönchengladbach", "papers": ["Rheinische Post", "Kicker"]},
        "Union Berlin":         {"city": "Berlín",          "papers": ["Berliner Zeitung", "Kicker"]},
        "Hoffenheim":           {"city": "Hoffenheim",      "papers": ["Rhein-Neckar-Zeitung", "Kicker"]},
        "Mainz":                {"city": "Maguncia",        "papers": ["Allgemeine Zeitung", "Kicker"]},
        "Augsburg":             {"city": "Augsburgo",       "papers": ["Augsburger Allgemeine", "Kicker"]},
        "Heidenheim":           {"city": "Heidenheim",      "papers": ["Heidenheimer Zeitung", "Kicker"]},
        "Bochum":               {"city": "Bochum",          "papers": ["WAZ", "Kicker"]},
        "Holstein Kiel":        {"city": "Kiel",            "papers": ["Kieler Nachrichten", "Kicker"]},
        "St. Pauli":            {"city": "Hamburgo",        "papers": ["Hamburger Abendblatt", "Kicker"]},
        # =====================================================================
        # LIGUE 1
        # =====================================================================
        "PSG":                  {"city": "París",           "papers": ["L'Équipe", "Le Parisien"]},
        "Marseille":            {"city": "Marsella",        "papers": ["La Provence", "L'Équipe"]},
        "Monaco":               {"city": "Mónaco",          "papers": ["L'Équipe", "Nice-Matin"]},
        "Lyon":                 {"city": "Lyon",            "papers": ["Le Progrès", "L'Équipe"]},
        "Lille":                {"city": "Lille",           "papers": ["La Voix du Nord", "L'Équipe"]},
        "Rennes":               {"city": "Rennes",          "papers": ["Ouest-France", "L'Équipe"]},
        "Nice":                 {"city": "Niza",            "papers": ["Nice-Matin", "L'Équipe"]},
        "Lens":                 {"city": "Lens",            "papers": ["La Voix du Nord", "L'Équipe"]},
        "Strasbourg":           {"city": "Estrasburgo",     "papers": ["Dernières Nouvelles d'Alsace", "L'Équipe"]},
        "Nantes":               {"city": "Nantes",          "papers": ["Ouest-France", "L'Équipe"]},
        "Montpellier":          {"city": "Montpellier",     "papers": ["Midi Libre", "L'Équipe"]},
        "Toulouse":             {"city": "Toulouse",        "papers": ["La Dépêche du Midi", "L'Équipe"]},
        "Reims":                {"city": "Reims",           "papers": ["L'Union", "L'Équipe"]},
        "Brest":                {"city": "Brest",           "papers": ["Ouest-France", "Le Télégramme"]},
        "Le Havre":             {"city": "El Havre",        "papers": ["Paris-Normandie", "L'Équipe"]},
        "Auxerre":              {"city": "Auxerre",         "papers": ["L'Yonne Républicaine", "L'Équipe"]},
        "Saint-Étienne":        {"city": "Saint-Étienne",   "papers": ["Le Progrès", "L'Équipe"]},
        "Angers":               {"city": "Angers",          "papers": ["Ouest-France", "L'Équipe"]},
        "Bordeaux":             {"city": "Burdeos",         "papers": ["Sud Ouest", "L'Équipe"]},
        "Lorient":              {"city": "Lorient",         "papers": ["Le Télégramme", "Ouest-France"]},
    }

    def _get_context(self, team_name):
        # 1. Buscar en equipos de las 5 grandes ligas
        if team_name in self.TEAM_CONTEXT:
            return self.TEAM_CONTEXT[team_name]
        # 2. Buscar en equipos europeos y resto del mundo
        try:
            from src.logic.european_teams import EUROPEAN_TEAMS
            if team_name in EUROPEAN_TEAMS:
                return EUROPEAN_TEAMS[team_name]
            # Búsqueda parcial en europeos
            for key, val in EUROPEAN_TEAMS.items():
                if key.lower() in team_name.lower() or team_name.lower() in key.lower():
                    return val
        except ImportError:
            pass
        # 3. Búsqueda parcial en 5 grandes ligas
        for key, val in self.TEAM_CONTEXT.items():
            if key.lower() in team_name.lower() or team_name.lower() in key.lower():
                return val
        # 4. Inferencia por nombre
        name_l = team_name.lower()
        if any(x in name_l for x in ["united", "city", "town", "hotspur", "villa"]):
            return {"city": "Reino Unido", "papers": ["BBC Sport", "Sky Sports"]}
        if any(x in name_l for x in ["münchen", "borussia", "schalke", "frankfurt"]):
            return {"city": "Alemania", "papers": ["Kicker", "Bild"]}
        if any(x in name_l for x in ["milan", "juve", "roma", "lazio", "napoli"]):
            return {"city": "Italia", "papers": ["Gazzetta dello Sport", "Corriere"]}
        if any(x in name_l for x in ["paris", "marseille", "lyon", "monaco"]):
            return {"city": "Francia", "papers": ["L'Équipe", "France Football"]}
        if any(x in name_l for x in ["ajax", "psv", "feyenoord", "eredivisie"]):
            return {"city": "Holanda", "papers": ["De Telegraaf", "AD Sportwereld"]}
        if any(x in name_l for x in ["benfica", "porto", "sporting", "braga"]):
            return {"city": "Portugal", "papers": ["Record", "A Bola"]}
        if any(x in name_l for x in ["galatasaray", "fenerbahce", "besiktas"]):
            return {"city": "Turquía", "papers": ["Fanatik", "Fotomaç"]}
        if any(x in name_l for x in ["celtic", "rangers", "glasgow"]):
            return {"city": "Escocia", "papers": ["Daily Record", "The Herald"]}
        if any(x in name_l for x in ["dinamo", "zagreb", "hajduk", "split"]):
            return {"city": "Croacia", "papers": ["Sportske novosti", "Večernji list"]}
        if any(x in name_l for x in ["red star", "partizan", "belgrado"]):
            return {"city": "Serbia", "papers": ["Sportski žurnal", "Večernje novosti"]}
        if any(x in name_l for x in ["slavia", "sparta", "plzen", "praga"]):
            return {"city": "República Checa", "papers": ["Sport.cz", "iSport.cz"]}
        if any(x in name_l for x in ["salzburg", "rapid", "sturm", "lask"]):
            return {"city": "Austria", "papers": ["Kronen Zeitung", "Der Standard"]}
        if any(x in name_l for x in ["young boys", "basel", "zürich", "zurich"]):
            return {"city": "Suiza", "papers": ["Blick", "Tages-Anzeiger"]}
        if any(x in name_l for x in ["legia", "lech", "wisla", "rakow"]):
            return {"city": "Polonia", "papers": ["Przegląd Sportowy", "Gazeta Wyborcza"]}
        if any(x in name_l for x in ["olympiakos", "panathinaikos", "aek", "paok"]):
            return {"city": "Grecia", "papers": ["Sport24", "Sportime"]}
        if any(x in name_l for x in ["shakhtar", "dynamo kyiv", "dynamo kiev"]):
            return {"city": "Ucrania", "papers": ["Football.ua", "Sportarena"]}
        if any(x in name_l for x in ["copenhagen", "brondby", "midtjylland"]):
            return {"city": "Dinamarca", "papers": ["BT Sport", "Ekstra Bladet"]}
        if any(x in name_l for x in ["malmö", "malmo", "aik", "djurgarden", "hammarby"]):
            return {"city": "Suecia", "papers": ["Aftonbladet", "Expressen"]}
        if any(x in name_l for x in ["rosenborg", "molde", "bodo", "glimt"]):
            return {"city": "Noruega", "papers": ["VG Sport", "Aftenposten"]}
        if any(x in name_l for x in ["flamengo", "palmeiras", "corinthians", "fluminense"]):
            return {"city": "Brasil", "papers": ["Lance!", "O Globo Esporte"]}
        if any(x in name_l for x in ["river plate", "boca juniors", "racing", "independiente"]):
            return {"city": "Argentina", "papers": ["Olé", "La Nación Deportes"]}
        # Fallback genérico
        return {"city": f"Ciudad de {team_name}", "papers": [f"Prensa de {team_name}", "SofaScore"]}

    # =========================================================================
    # CAPA 1: Claude API con búsqueda web
    # =========================================================================
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
                return None
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            text = re.sub(r"```json|```", "", text).strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"[ExternalAnalyst] Error Claude API: {e}")
        return None

    # =========================================================================
    # CAPA 2: Google News RSS (sin API key)
    # =========================================================================
    def _call_rss_analysis(self, team_name, papers):
        try:
            from src.logic.rss_analyst import RSSAnalyst
            rss = RSSAnalyst()
            return rss.analyze_team(team_name, papers)
        except Exception as e:
            print(f"[ExternalAnalyst] Error RSS: {e}")
        return None

    # =========================================================================
    # CAPA 3: Fallback básico con datos internos
    # =========================================================================
    def _fallback_analysis(self, team):
        bajas = [p.name for p in team.players if p.status.value == "Baja"]
        dudas = [p.name for p in team.players if p.status.value == "Duda"]
        moral = -(len(bajas) * 0.02) - (len(dudas) * 0.01)
        estado = "negativo" if moral < -0.04 else ("positivo" if moral > 0.02 else "neutro")
        return {
            "bajas_confirmadas": bajas, "dudas": dudas,
            "estado_vestuario": estado,
            "descripcion_vestuario": "Sin acceso a prensa local en este momento.",
            "relacion_prensa": "normal", "sensaciones_recientes": "neutras",
            "descripcion_reciente": "Sin datos de prensa disponibles.",
            "noticias_clave": [],
            "impacto_partido": "neutro" if moral >= -0.02 else "negativo",
            "resumen": f"{len(bajas)} bajas en BD interna.",
            "puntuacion_moral": round(moral, 3)
        }

    # =========================================================================
    # FORMATO DEL INFORME
    # =========================================================================
    def _format_team_report(self, analysis, team_name, papers):
        via_rss = analysis.get("_via_rss", False)
        fuentes_rss = analysis.get("fuentes_rss", [])

        if via_rss and fuentes_rss:
            fuentes_str = ", ".join(fuentes_rss[:2])
            lines = [f"*Fuentes RSS: {fuentes_str}*"]
        else:
            lines = [f"*Fuentes: {', '.join(papers[:2])}*"]

        if analysis.get("bajas_confirmadas"):
            lines.append(f"🚨 **Bajas:** {', '.join(analysis['bajas_confirmadas'])}")
        if analysis.get("dudas"):
            lines.append(f"⏳ **Dudas:** {', '.join(analysis['dudas'])}")
        if not analysis.get("bajas_confirmadas") and not analysis.get("dudas"):
            lines.append("✅ **Sin Bajas Relevantes** detectadas en prensa")

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
            "positivo": f"✅ **Impacto POSITIVO** (moral: +{abs(moral):.2f})",
            "neutro":   "⚪ **Impacto NEUTRO**",
            "negativo": f"⚠️ **Impacto NEGATIVO** (lastre: -{abs(moral):.2f})"
        }
        lines.append(i_map.get(impacto, "⚪ **Impacto NEUTRO**"))
        return "\n".join(lines)

    # =========================================================================
    # MÉTODO PRINCIPAL
    # =========================================================================
    def get_detailed_intelligence(self, match: Match) -> dict:
        match_date_str = match.date.strftime("%d/%m/%Y") if match.date else "hoy"
        league = match.competition or "Liga"
        has_api = bool(os.environ.get("ANTHROPIC_API_KEY", ""))

        def analyze_team(team):
            ctx = self._get_context(team.name)
            # Capa 1: Claude API
            if has_api:
                print(f"[ExternalAnalyst] 🤖 Claude API: {team.name}")
                result = self._call_claude_with_search(team.name, league, match_date_str)
                if result:
                    return result, ctx, "Claude API"
            # Capa 2: RSS
            print(f"[ExternalAnalyst] 📰 RSS: {team.name}")
            result = self._call_rss_analysis(team.name, ctx["papers"])
            if result and result.get("noticias_clave") or result and result.get("bajas_confirmadas"):
                return result, ctx, "Google News RSS"
            # Capa 3: Fallback
            print(f"[ExternalAnalyst] ⚪ Fallback: {team.name}")
            return self._fallback_analysis(team), ctx, "BD Interna"

        h_analysis, h_ctx, h_source = analyze_team(match.home_team)
        a_analysis, a_ctx, a_source = analyze_team(match.away_team)

        h_report = self._format_team_report(h_analysis, match.home_team.name, h_ctx["papers"])
        a_report = self._format_team_report(a_analysis, match.away_team.name, a_ctx["papers"])
        weather = self._analyze_weather(match)

        # Indicador de fuente
        source_indicator = ""
        if not has_api:
            source_indicator = "\n> 💡 *Análisis via Google News RSS. Activa ANTHROPIC_API_KEY para análisis más profundo.*"

        report = f"""### PRENSA LOCAL Y ENTORNO{source_indicator}

**🏠 {match.home_team.name} ({h_ctx['city']}):**
{h_report}

**✈️ {match.away_team.name} ({a_ctx['city']}):**
{a_report}

### 🌤️ CONDICIONES
{weather}"""

        return {
            "report": report,
            "impact": {
                "home": h_analysis.get("puntuacion_moral", 0.0),
                "away": a_analysis.get("puntuacion_moral", 0.0)
            },
            "home_analysis": h_analysis,
            "away_analysis": a_analysis,
            "source": f"Local:{h_source} | Visitante:{a_source}"
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
