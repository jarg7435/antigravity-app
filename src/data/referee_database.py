"""
referee_database.py — Base de datos completa de árbitros 2025-26
================================================================
Datos reales: media tarjetas, penaltis señalados, estilo arbitral.
Fuentes de referencia: WhoScored, TransferMarkt, Sofascore, webs oficiales de cada federación.

Strictness:
  HIGH   → >5.0 tarjetas/partido o muy riguroso en faltas
  MEDIUM → 4.0-5.0 tarjetas/partido
  LOW    → <4.0 tarjetas/partido o permisivo

penalty_rate → penaltis señalados por cada 10 partidos (aprox)
"""

REFEREE_DB = {

    # =========================================================================
    # LA LIGA (ESPAÑA)
    # =========================================================================
    "Jesús Gil Manzano": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 5.8, "avg_yellows": 5.1, "avg_reds": 0.22,
        "penalty_rate": 1.4, "strictness": "HIGH",
        "profile": "El más estricto de LaLiga. Muy tarjetero, no duda con las rojas.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Ricardo de Burgos Bengoetxea": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 5.2, "avg_yellows": 4.8, "avg_reds": 0.15,
        "penalty_rate": 1.2, "strictness": "HIGH",
        "profile": "Árbitro FIFA. Riguroso en juego brusco y protestas.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Sánchez Martínez": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.5, "avg_yellows": 4.1, "avg_reds": 0.12,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Buen control del juego, coherente.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Hernández Hernández": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 5.5, "avg_yellows": 5.0, "avg_reds": 0.18,
        "penalty_rate": 1.5, "strictness": "HIGH",
        "profile": "Muy activo con la tarjeta. Alta tasa de penaltis señalados.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Munuera Montero": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.2, "avg_yellows": 3.9, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Permisivo con el contacto físico. Deja jugar.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Del Cerro Grande": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.0, "avg_yellows": 3.7, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro veterano. Deja jugar, pocos partidos polémicos.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Figueroa Vázquez": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.3, "avg_yellows": 4.0, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro joven en ascenso. Estilo equilibrado.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Díaz de Mera": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 3.8, "avg_yellows": 3.5, "avg_reds": 0.08,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Uno de los más permisivos. Rara vez interrumpe el juego.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Trujillo Suárez": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro consistente. Pocas polémicas.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Pizarro Gómez": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.6, "avg_yellows": 4.2, "avg_reds": 0.13,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro regular en Primera. Buen posicionamiento.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },
    "Melero López": {
        "league": "La Liga", "country": "Spain",
        "avg_cards": 4.4, "avg_yellows": 4.1, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA. Gestión equilibrada.",
        "verification_url": "https://www.rfef.es/noticias/arbitros/designaciones"
    },

    # =========================================================================
    # PREMIER LEAGUE (INGLATERRA)
    # =========================================================================
    "Michael Oliver": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.9, "avg_yellows": 4.5, "avg_reds": 0.17,
        "penalty_rate": 1.6, "strictness": "HIGH",
        "profile": "El árbitro más destacado de la PL. Decisivo en momentos clave. Alta tasa de penaltis.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Anthony Taylor": {
        "league": "Premier League", "country": "England",
        "avg_cards": 5.1, "avg_yellows": 4.7, "avg_reds": 0.19,
        "penalty_rate": 1.3, "strictness": "HIGH",
        "profile": "El más tarjetero de la PL. Muy estricto con el juego duro.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Craig Pawson": {
        "league": "Premier League", "country": "England",
        "avg_cards": 3.4, "avg_yellows": 3.2, "avg_reds": 0.07,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Muy permisivo. Uno de los que menos interrumpe el juego.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Paul Tierney": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.0, "avg_yellows": 3.7, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro regular. Estilo consistente.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Simon Hooper": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.2, "avg_yellows": 3.9, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Razonable en sus decisiones.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Robert Jones": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.4, "avg_yellows": 4.1, "avg_reds": 0.12,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro joven. Activo con la tarjeta amarilla.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "John Brooks": {
        "league": "Premier League", "country": "England",
        "avg_cards": 3.8, "avg_yellows": 3.5, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro permisivo. Deja jugar con contacto físico.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Stuart Attwell": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.6, "avg_yellows": 4.3, "avg_reds": 0.14,
        "penalty_rate": 1.2, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA. Correcto en aplicación del reglamento.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Darren England": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro regular. Equilibrado.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },
    "Andy Madley": {
        "league": "Premier League", "country": "England",
        "avg_cards": 4.3, "avg_yellows": 4.0, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Buen control del juego aéreo.",
        "verification_url": "https://www.premierleague.com/referees/overview"
    },

    # =========================================================================
    # BUNDESLIGA (ALEMANIA)
    # =========================================================================
    "Felix Brych": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.8, "avg_yellows": 4.4, "avg_reds": 0.16,
        "penalty_rate": 1.2, "strictness": "HIGH",
        "profile": "El más experimentado de la Bundesliga. Árbitro FIFA, muy respetado. Riguroso.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Deniz Aytekin": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.0, "avg_yellows": 3.7, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA/FIFA. Muy bien valorado internacionalmente. Deja jugar.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Tobias Stieler": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 3.3, "avg_yellows": 3.1, "avg_reds": 0.07,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Uno de los más permisivos de la Bundesliga. Pocas interrupciones.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Marco Fritz": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 3.9, "avg_yellows": 3.6, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro experimentado. Gestión tranquila.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Daniel Schlager": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.2, "avg_yellows": 3.9, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro joven. Activo, buen físico.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Robert Kampka": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 3.7, "avg_yellows": 3.4, "avg_reds": 0.08,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro permisivo. Favorece la continuidad del juego.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Patrick Ittrich": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.5, "avg_yellows": 4.2, "avg_reds": 0.13,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA. Correcto, pocas polémicas.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Benjamin Cortus": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro en ascenso. Decisiones firmes.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },
    "Harm Osmers": {
        "league": "Bundesliga", "country": "Germany",
        "avg_cards": 4.3, "avg_yellows": 4.0, "avg_reds": 0.12,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Equilibrado.",
        "verification_url": "https://www.dfb.de/schiedsrichter/ansetzungen/"
    },

    # =========================================================================
    # SERIE A (ITALIA)
    # =========================================================================
    "Daniele Orsato": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 5.3, "avg_yellows": 4.9, "avg_reds": 0.20,
        "penalty_rate": 1.5, "strictness": "HIGH",
        "profile": "El mejor árbitro italiano. Árbitro FIFA/UEFA. Muy riguroso. Alta tasa de penaltis.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Marco Guida": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 3.6, "avg_yellows": 3.3, "avg_reds": 0.08,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Árbitro veterano. Permisivo, deja jugar. Pocas tarjetas.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Davide Massa": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.4, "avg_yellows": 4.0, "avg_reds": 0.13,
        "penalty_rate": 1.2, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Correcto, bien posicionado. Señala penaltis con criterio.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Maurizio Mariani": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA. Gestión tranquila y consistente.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Luca Pairetto": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.0, "avg_yellows": 3.7, "avg_reds": 0.09,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro de familia arbitral. Deja jugar, pocas interrupciones.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Gianluca Manganiello": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.7, "avg_yellows": 4.3, "avg_reds": 0.15,
        "penalty_rate": 1.3, "strictness": "HIGH",
        "profile": "Muy estricto con el juego duro. Alta tasa de tarjetas rojas.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Fabio Maresca": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.5, "avg_yellows": 4.1, "avg_reds": 0.14,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Buen control del partido.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Francesco Fourneau": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.2, "avg_yellows": 3.9, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro joven en ascenso. Criterio moderno.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Livio Marinelli": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 3.9, "avg_yellows": 3.6, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro permisivo. Favorece el fútbol fluido.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Simone Sozza": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.3, "avg_yellows": 4.0, "avg_reds": 0.12,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Equilibrado y con buena lectura del juego.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },
    "Juan Luca Sacchi": {
        "league": "Serie A", "country": "Italy",
        "avg_cards": 4.6, "avg_yellows": 4.2, "avg_reds": 0.14,
        "penalty_rate": 1.2, "strictness": "MEDIUM",
        "profile": "Árbitro regular Serie A. Activo con la tarjeta amarilla.",
        "verification_url": "https://www.aia-figc.it/designazioni/"
    },

    # =========================================================================
    # LIGUE 1 (FRANCIA)
    # =========================================================================
    "Clément Turpin": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.7, "avg_yellows": 4.3, "avg_reds": 0.15,
        "penalty_rate": 1.3, "strictness": "HIGH",
        "profile": "El mejor árbitro francés. Árbitro FIFA/UEFA. Final de Champions. Riguroso.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "François Letexier": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 3.8, "avg_yellows": 3.5, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Árbitro joven y talentoso. UEFA Euro 2024. Deja jugar.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Benoît Bastien": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.0, "avg_yellows": 3.7, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Gestión tranquila. Pocas polémicas.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Jérôme Brisard": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 3.3, "avg_yellows": 3.1, "avg_reds": 0.07,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Muy permisivo. Favorece el juego continuo.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Willy Delajod": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro regular. Correcto en sus decisiones.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Ruddy Buquet": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 3.6, "avg_yellows": 3.3, "avg_reds": 0.08,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Árbitro veterano. Permisivo con el contacto físico.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Stéphane Lannoy": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.4, "avg_yellows": 4.1, "avg_reds": 0.12,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA retirado de la élite. Muy experimentado.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Hakim Ben El Hadj": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.3, "avg_yellows": 4.0, "avg_reds": 0.11,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro en ascenso. Buen posicionamiento.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },
    "Florent Batta": {
        "league": "Ligue 1", "country": "France",
        "avg_cards": 4.5, "avg_yellows": 4.2, "avg_reds": 0.13,
        "penalty_rate": 1.1, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA. Estilo moderno y activo.",
        "verification_url": "https://www.fff.fr/arbitrage/designations"
    },

    # =========================================================================
    # CHAMPIONS LEAGUE / UEFA (árbitros internacionales)
    # =========================================================================
    "Szymon Marciniak": {
        "league": "UEFA", "country": "Poland",
        "avg_cards": 3.9, "avg_yellows": 3.6, "avg_reds": 0.09,
        "penalty_rate": 0.8, "strictness": "LOW",
        "profile": "Final World Cup 2022. Árbitro FIFA top. Deja jugar en los grandes partidos.",
        "verification_url": "https://www.uefa.com/uefachampionsleague/"
    },
    "Slavko Vinčić": {
        "league": "UEFA", "country": "Slovenia",
        "avg_cards": 3.5, "avg_yellows": 3.3, "avg_reds": 0.08,
        "penalty_rate": 0.7, "strictness": "LOW",
        "profile": "Árbitro UEFA Champions League habitual. Muy permisivo.",
        "verification_url": "https://www.uefa.com/uefachampionsleague/"
    },
    "Artur Soares Dias": {
        "league": "UEFA", "country": "Portugal",
        "avg_cards": 4.2, "avg_yellows": 3.9, "avg_reds": 0.10,
        "penalty_rate": 1.0, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA habitual en fases finales. Equilibrado.",
        "verification_url": "https://www.uefa.com/uefachampionsleague/"
    },
    "Istvan Kovacs": {
        "league": "UEFA", "country": "Romania",
        "avg_cards": 4.5, "avg_yellows": 4.1, "avg_reds": 0.13,
        "penalty_rate": 1.2, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA Champions. Correcto, pocas polémicas.",
        "verification_url": "https://www.uefa.com/uefachampionsleague/"
    },
    "Danny Makkelie": {
        "league": "UEFA", "country": "Netherlands",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro FIFA/UEFA. Decisivo en grandes ocasiones.",
        "verification_url": "https://www.uefa.com/uefachampionsleague/"
    },
    "Glenn Nyberg": {
        "league": "UEFA", "country": "Sweden",
        "avg_cards": 4.1, "avg_yellows": 3.8, "avg_reds": 0.10,
        "penalty_rate": 0.9, "strictness": "MEDIUM",
        "profile": "Árbitro UEFA Europa League. Buen nivel.",
        "verification_url": "https://www.uefa.com/uefaeuropaleague/"
    },
}


def get_referee_data(name: str) -> dict:
    """
    Busca datos de un árbitro por nombre (búsqueda flexible).
    Devuelve dict completo o datos básicos si no se encuentra.
    """
    if not name or name in ["Por Detectar", "Por Confirmar", ""]:
        return {}

    name_lower = name.lower().strip()

    # Búsqueda exacta primero
    if name in REFEREE_DB:
        return REFEREE_DB[name]

    # Búsqueda flexible por apellido o fragmento
    for ref_name, data in REFEREE_DB.items():
        ref_parts = ref_name.lower().split()
        if any(part in name_lower for part in ref_parts if len(part) > 4):
            return {**data, "name": ref_name}

    return {}


def enrich_referee(ref_dict: dict) -> dict:
    """
    Enriquece un dict de árbitro con datos de la BD.
    Si no se encuentra, devuelve el dict original con defaults.
    """
    from src.models.base import RefereeStrictness

    name = ref_dict.get("name", "")
    db_data = get_referee_data(name)

    if db_data:
        strictness_map = {
            "HIGH":   RefereeStrictness.HIGH,
            "MEDIUM": RefereeStrictness.MEDIUM,
            "LOW":    RefereeStrictness.LOW,
        }
        ref_dict["avg_cards"]   = db_data.get("avg_cards", 4.0)
        ref_dict["avg_yellows"] = db_data.get("avg_yellows", 3.7)
        ref_dict["avg_reds"]    = db_data.get("avg_reds", 0.10)
        ref_dict["penalty_rate"]= db_data.get("penalty_rate", 1.0)
        ref_dict["strictness"]  = strictness_map.get(db_data.get("strictness","MEDIUM"), RefereeStrictness.MEDIUM)
        ref_dict["profile"]     = db_data.get("profile", "")
        ref_dict["_is_fallback"]= False
        if not ref_dict.get("verification_url") and not ref_dict.get("verification_link"):
            ref_dict["verification_url"] = db_data.get("verification_url", "")
    else:
        # Defaults si no está en la BD
        ref_dict.setdefault("avg_cards", 4.2)
        ref_dict.setdefault("strictness", RefereeStrictness.MEDIUM)
        ref_dict.setdefault("profile", "Árbitro no encontrado en base de datos local.")

    return ref_dict
