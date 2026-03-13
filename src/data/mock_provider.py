from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.data.interface import DataProvider
from src.models.base import Match, Team, Player, PlayerPosition, PlayerStatus, NodeRole, MatchConditions

class MockDataProvider(DataProvider):
    """
    Provides dummy data for testing the UI and Logic flow.
    Expanded for 5 Major Leagues.
    """
    
    def __init__(self):
        self.teams_db = self._init_teams()

    def get_upcoming_matches(self, league: str) -> List[Match]:
        # Legacy support, though UI is moving to builder
        return []

    # Alias map: selector label → internal league name
    LEAGUE_ALIASES = {
        "süper lig":            "super lig",
        "primera liga":         "la liga",
        "premier league":       "premier league",
        "bundesliga":           "bundesliga",
        "serie a":              "serie a",
        "ligue 1":              "ligue 1",
        "eredivisie":           "eredivisie",
        "primeira liga":        "primeira liga",
        "scottish premiership": "scottish premiership",
        "belgian pro league":   "belgian pro league",
        "austrian bundesliga":  "austrian bundesliga",
        "swiss super league":   "swiss super league",
        "ekstraklasa":          "ekstraklasa",
        "czech first league":   "czech first league",
        "superliga":            "superliga",
        "allsvenskan":          "allsvenskan",
        "eliteserien":          "eliteserien",
        "super league":         "super league",
        "hnl":                  "hnl",
        "superliga":            "superliga",
        "ukrainian premier league": "ukrainian premier league",
        "israeli premier league":   "israeli premier league",
        "liga profesional":     "liga profesional",
        "brasileirao":          "brasileirao",
    }

    def get_teams_by_league(self, league: str) -> List[str]:
        if not league:
            return []

        search_term = str(league).lower()
        if "mixta" in search_term or "combinada" in search_term:
            return sorted(list(self.teams_db.keys()))

        # Normalize: strip parenthetical and apply alias
        target = league.strip().lower()
        if "(" in target:
            target = target.split("(")[0].strip()
        target = self.LEAGUE_ALIASES.get(target, target)

        return sorted([
            name for name, team in self.teams_db.items()
            if self.LEAGUE_ALIASES.get(team.league.strip().lower(), team.league.strip().lower()) == target
            or target in team.league.strip().lower()
        ])

    def get_team_data(self, team_name: str) -> Team:
        if not team_name:
            team_name = "Equipo Desconocido"
        return self.teams_db.get(team_name, self._create_dummy_team(team_name))

    def get_match_conditions(self, match_id: str, location: str, date_time: str) -> Optional[dict]:
        return {"temp": 20, "rain": 0}

    def _init_teams(self) -> Dict[str, Team]:
        teams = {}
        
        # --- LA LIGA (España) 2025-26 (20 equipos) ---
        # Promovidos: Levante, Elche, Real Oviedo | Descendidos: Valladolid, Las Palmas, Leganés
        la_liga_teams = [
            "FC Barcelona", "Real Madrid", "Atletico Madrid", "Villarreal", "Real Betis",
            "Espanyol", "Celta de Vigo", "Real Sociedad", "Osasuna", "Alavés",
            "Athletic Club", "Girona", "Mallorca", "Sevilla FC",
            "Valencia", "Getafe", "Rayo Vallecano",
            "Levante", "Elche", "Real Oviedo"
        ]
        for name in la_liga_teams:
            if name == "Elche":
                teams[name] = self._create_team(name, "La Liga", ["Dituro", "Mario Gaspar", "Bigas", "Barzic", "Salinas", "Febas", "Nico Castro", "Nico Fernández", "Josan", "Mourad", "Oscar Plano"], base_rating=7.4)
            elif name == "FC Barcelona":
                teams[name] = self._create_team(name, "La Liga", ["Ter Stegen", "Koundé", "Cubarsí", "Iñigo Martínez", "Balde", "Casadó", "Pedri", "Dani Olmo", "Lamine Yamal", "Lewandowski", "Raphinha"], base_rating=9.5, avg_xg=2.5, avg_xg_c=0.8)
            elif name == "Real Madrid":
                teams[name] = self._create_team(name, "La Liga", ["Courtois", "Carvajal", "Rudiger", "Militao", "Mendy", "Valverde", "Tchouameni", "Bellingham", "Vinicius Jr", "Mbappé", "Rodrygo"], base_rating=9.4, avg_xg=2.6, avg_xg_c=0.75)
            elif name == "Atletico Madrid":
                # ADDED: Ademola Lookman (Winter 2026)
                teams[name] = self._create_team(name, "La Liga", ["Oblak", "Molina", "Le Normand", "Gimenez", "Reinildo", "Koke", "De Paul", "Gallagher", "Griezmann", "Julián Álvarez", "Ademola Lookman"], base_rating=8.8, avg_xg=1.9, avg_xg_c=0.85)
            elif name == "Villarreal":
                # Alineación confirmada 22/02/2026 (sin Parejo ni Gerard Moreno - bajas)
                teams[name] = self._create_team(name, "La Liga", ["Luiz Junior", "Femenía", "Albiol", "Bailly", "Sergi Cardona", "Comesaña", "Baena", "Yeremy", "Barry", "Mikautadze", "Ayoze"], base_rating=7.9)
            elif name == "Real Betis":
                teams[name] = self._create_team(name, "La Liga", ["Rui Silva", "Sabaly", "Llorente", "Natan", "Perraud", "Marc Roca", "Johnny", "Fornals", "Lo Celso", "Abde", "Vitor Roque"], base_rating=7.7)
            elif name == "Espanyol":
                teams[name] = self._create_team(name, "La Liga", ["Joan García", "El Hilali", "Kumbulla", "Cabrera", "Romero", "Kral", "Lozano", "Tejero", "Jofre", "Puado", "Veliz"], base_rating=7.1)
            elif name == "Real Sociedad":
                teams[name] = self._create_team(name, "La Liga", ["Remiro", "Aramburu", "Zubeldia", "Aguerd", "Javi López", "Zubimendi", "Sucic", "Brais", "Kubo", "Oyarzabal", "Sergio Gómez"], base_rating=7.8)
            elif name == "Athletic Club":
                teams[name] = self._create_team(name, "La Liga", ["Agirrezabala", "De Marcos", "Vivian", "Paredes", "Yuri", "Ruiz de Galarreta", "Prados", "Sancet", "I. Williams", "Guruzeta", "N. Williams"], base_rating=7.9)
            elif name == "Sevilla FC":
                teams[name] = self._create_team(name, "La Liga", ["Nyland", "Carmona", "Badé", "Marcao", "Pedrosa", "Gudelj", "Agoumé", "Saúl", "Lukebakio", "Isaac Romero", "Ejuke"], base_rating=7.5)
            elif name == "Valencia":
                # Alineación confirmada 22/02/2026 (Dimitrievski titular, Beltrán como finalizador)
                teams[name] = self._create_team(name, "La Liga", ["Dimitrievski", "Foulquier", "Mosquera", "Tárrega", "Vázquez", "Pepelu", "Barrenechea", "Almeida", "Diego López", "Hugo Duro", "Beltrán"], base_rating=7.3)
            elif name == "Getafe":
                teams[name] = self._create_team(name, "La Liga", ["David Soria", "Iglesias", "Djené", "Alderete", "Diego Rico", "Milla", "Arambarri", "Uche", "Carles Pérez", "Mayoral", "Álex Sola"], base_rating=7.4)
            elif name == "Girona":
                teams[name] = self._create_team(name, "La Liga", ["Gazzaniga", "Arnau", "David López", "Blind", "Miguel", "Herrera", "Iván Martín", "Asprilla", "Bryan Gil", "Abel Ruiz", "Danjuma"], base_rating=8.2, avg_xg=1.8, avg_xg_c=1.1)
            elif name == "Osasuna":
                teams[name] = self._create_team(name, "La Liga", ["Sergio Herrera", "Areso", "Catena", "Boyomo", "Abel Bretones", "Torró", "Moncayola", "Aimar Oroz", "Rubén García", "Budimir", "Bryan Zaragoza"], base_rating=7.6)
            elif name == "Alavés":
                teams[name] = self._create_team(name, "La Liga", ["Sivera", "Tenaglia", "Abqar", "Sedlar", "Manu Sánchez", "Blanco", "Guevara", "Guridi", "Carlos Vicente", "Kike García", "Conechny"], base_rating=7.3)
            elif name == "Levante":
                teams[name] = self._create_team(name, "La Liga", ["Andrés Fernández", "Andrés García", "Elgezabal", "Cabello", "Marcos Navarro", "Oriol Rey", "Kochorashvili", "Pablo Martínez", "Carlos Álvarez", "Brugué", "Morales"], base_rating=7.1)
            elif name == "Celta de Vigo":
                teams[name] = self._create_team(name, "La Liga", ["Guaita", "Mingueza", "Starfelt", "Marcos Alonso", "Hugo Álvarez", "Beltrán", "Hugo Sotelo", "Bamba", "Swedberg", "Iago Aspas", "Borja Iglesias"], base_rating=7.6)
            elif name == "Rayo Vallecano":
                teams[name] = self._create_team(name, "La Liga", ["Batalla", "Ratiu", "Lejeune", "Mumin", "Chavarría", "Valentín", "Unai López", "Isi Palazón", "De Frutos", "Álvaro García", "Camello"], base_rating=7.4)
            elif name == "Mallorca":
                teams[name] = self._create_team(name, "La Liga", ["Greif", "Maffeo", "Valjent", "Raíllo", "Mojica", "Samu Costa", "Morlanes", "Robert Navarro", "Dani Rodríguez", "Larin", "Muriqi"], base_rating=7.6)
            elif name == "Real Oviedo":
                teams[name] = self._create_team(name, "La Liga", ["Escandell", "Luengo", "Dani Calvo", "David Costas", "Rahim", "Sibo", "Colombatto", "Cazorla", "Ilyas Chaira", "Sebas Moyano", "Alemao"], base_rating=7.0)
            elif name == "Elche":
                teams[name] = self._create_team(name, "La Liga", ["Edgar Badía", "Bigas", "Barragán", "Verdú", "Gragera", "Clerc", "Collado", "Domingos", "Boyé", "Guti", "Nico Castro"], base_rating=7.0)
            else:
                teams[name] = self._create_dummy_team(name, "La Liga", base_rating=6.9)

        # --- PREMIER LEAGUE (Inglaterra) 2025-26 (20 equipos) ---
        # Promovidos: Leeds Utd, Burnley, Sunderland | Descendidos: Southampton, Leicester City, Ipswich Town
        pl_teams = [
            "Arsenal", "Manchester City", "Liverpool", "Chelsea", "Aston Villa",
            "Newcastle", "Manchester Utd", "West Ham", "Tottenham", "Brighton",
            "Wolves", "Brentford", "Fulham", "Crystal Palace", "Nottingham Forest",
            "Everton", "Bournemouth", "Leeds Utd", "Burnley", "Sunderland"
        ]
        for name in pl_teams:
            if name == "Manchester City":
                # ADDED: Antoine Semenyo (Winter 2026)
                teams[name] = self._create_team(name, "Premier League", ["Ederson", "Lewis", "Dias", "Akanji", "Gvardiol", "Rodri", "Kovacic", "De Bruyne", "Phil Foden", "Haaland", "Antoine Semenyo"], base_rating=9.3, avg_xg=2.6, avg_xg_c=0.85)
            elif name == "Arsenal":
                teams[name] = self._create_team(name, "Premier League", ["Raya", "White", "Saliba", "Gabriel", "Timber", "Rice", "Merino", "Odegaard", "Saka", "Havertz", "Martinelli"], base_rating=9.1, avg_xg=2.3, avg_xg_c=0.8)
            elif name == "Liverpool":
                # ADDED: Jérémy Jacquet (Winter 2026)
                teams[name] = self._create_team(name, "Premier League", ["Alisson", "Alexander-Arnold", "Van Dijk", "Konaté", "Jérémy Jacquet", "Gravenberch", "Mac Allister", "Szoboszlai", "Salah", "Jota", "Diaz"], base_rating=9.0, avg_xg=2.4, avg_xg_c=0.95)
            elif name == "Chelsea":
                teams[name] = self._create_team(name, "Premier League", ["Sánchez", "Gusto", "Fofana", "Colwill", "Cucurella", "Caicedo", "Enzo", "Palmer", "Madueke", "Jackson", "Neto"], base_rating=8.2)
            elif name == "Manchester Utd":
                teams[name] = self._create_team(name, "Premier League", ["Onana", "Mazraoui", "De Ligt", "Martinez", "Dalot", "Casemiro", "Mainoo", "Bruno", "Garnacho", "Zirkzee", "Rashford"], base_rating=7.9)
            elif name == "Tottenham":
                # ADDED: Conor Gallagher (Winter 2026 return to PL)
                teams[name] = self._create_team(name, "Premier League", ["Vicario", "Porro", "Romero", "Van de Ven", "Udogie", "Bissouma", "Conor Gallagher", "Maddison", "Kulusevski", "Solanke", "Son"], base_rating=8.2)
            elif name == "Newcastle":
                teams[name] = self._create_team(name, "Premier League", ["Pope", "Livramento", "Schär", "Burn", "Hall", "Guimarães", "Joelinton", "Tonali", "Gordon", "Isak", "Barnes"], base_rating=7.8)
            elif name == "Aston Villa":
                teams[name] = self._create_team(name, "Premier League", ["Martínez", "Konsa", "Diego Carlos", "Pau Torres", "Digne", "Onana", "Tielemans", "McGinn", "Rogers", "Watkins", "Bailey"], base_rating=8.0)
            elif name == "Crystal Palace":
                # ADDED: Strand Larsen & Brennan Johnson (Winter 2026)
                teams[name] = self._create_team(name, "Premier League", ["Henderson", "Munoz", "Guehi", "Lacroix", "Mitchell", "Wharton", "Lerma", "Brennan Johnson", "Eze", "Kamada", "Strand Larsen"], base_rating=7.7)
            elif name == "Leeds Utd":
                teams[name] = self._create_team(name, "Premier League", ["Meslier", "Bogle", "Rodon", "Byram", "Firpo", "Ampadu", "Wharton", "Gnonto", "Summerville", "Bamford", "Piroe"], base_rating=7.2)
            elif name == "Burnley":
                teams[name] = self._create_team(name, "Premier League", ["Flekken", "Roberts", "Beyer", "O'Shea", "Maatsen", "Brownhill", "Cork", "Cullen", "Benson", "Zeki Amdouni", "Rodriguez"], base_rating=7.1)
            elif name == "Sunderland":
                teams[name] = self._create_team(name, "Premier League", ["Patterson", "Hume", "Ballard", "O'Nien", "Cirkin", "Neil", "Ojo", "Ekwah", "Clarke", "Mayenda", "Roberts"], base_rating=7.0)
            else:
                teams[name] = self._create_dummy_team(name, "Premier League", base_rating=7.1)

        # --- SERIE A (Italia) 2025-26 (20 equipos) ---
        # Promovidos: Sassuolo, Pisa, Cremonese | Descendidos: Venezia, Empoli, Monza
        serie_a_teams = [
            "Inter Milan", "Napoles", "Atalanta", "Juventus", "AC Milan",
            "Lazio", "Fiorentina", "Bolonia", "AS Roma", "Torino",
            "Como", "Udinese", "Cagliari", "Genoa", "Parma",
            "Verona", "Lecce", "Sassuolo", "Pisa", "Cremonese"
        ]
        for name in serie_a_teams:
            if name == "Inter Milan":
                teams[name] = self._create_team(name, "Serie A", ["Sommer", "Pavard", "Acerbi", "Bastoni", "Dumfries", "Barella", "Calhanoglu", "Mkhitaryan", "Dimarco", "Lautaro", "Thuram"], base_rating=8.9)
            elif name == "AC Milan":
                # ADDED: Nicolas Fullkrug (Winter 2026 Loan)
                teams[name] = self._create_team(name, "Serie A", ["Maignan", "Emerson Royal", "Tomori", "Pavlovic", "Hernández", "Fofana", "Reijnders", "Pulisic", "Leão", "Morata", "Nicolas Fullkrug"], base_rating=8.4)
            elif name == "Juventus":
                teams[name] = self._create_team(name, "Serie A", ["Di Gregorio", "Savona", "Gatti", "Bremer", "Cabal", "Locatelli", "Thuram", "Koopmeiners", "Yildiz", "Vlahovic", "Kalulu"], base_rating=8.3)
            elif name == "Napoles":
                # ADDED: Lorenzo Lucca (Winter 2026)
                teams[name] = self._create_team(name, "Serie A", ["Meret", "Di Lorenzo", "Rrahmani", "Buongiorno", "Olivera", "Anguissa", "Lobotka", "McTominay", "Kvaratskhelia", "Lukaku", "Lorenzo Lucca"], base_rating=8.6)
            elif name == "AS Roma":
                teams[name] = self._create_team(name, "Serie A", ["Svilar", "Celik", "Mancini", "Ndicka", "Angelino", "Cristante", "Koné", "Pellegrini", "Dybala", "Dovbyk", "Soulé"], base_rating=8.0)
            elif name == "Atalanta":
                teams[name] = self._create_team(name, "Serie A", ["Carnesecchi", "Djimsiti", "Hien", "Kolasinac", "Bellanova", "De Roon", "Ederson", "Ruggeri", "De Ketelaere", "Retegui", "Samardzic"], base_rating=8.1)
            elif name == "Lazio":
                teams[name] = self._create_team(name, "Serie A", ["Provedel", "Lazzari", "Gila", "Romagnoli", "Tavares", "Guendouzi", "Rovella", "Isaksen", "Dia", "Zaccagni", "Castellanos"], base_rating=7.7)
            elif name == "Sassuolo":
                teams[name] = self._create_team(name, "Serie A", ["Moldovan", "Toljan", "Erlic", "Lovato", "Kyriakopoulos", "Mateus Henrique", "Obiang", "Boloca", "Berardi", "Pinamonti", "Laurienté"], base_rating=7.2)
            elif name == "Pisa":
                teams[name] = self._create_team(name, "Serie A", ["Nicolas", "Touré", "Caracciolo", "Rus", "Angori", "Marin", "Arena", "Piccinini", "Tramoni", "Moreo", "Lind"], base_rating=6.9)
            elif name == "Cremonese":
                teams[name] = self._create_team(name, "Serie A", ["Sarr", "Sernicola", "Bianchetti", "Antov", "Quagliata", "Collocolo", "Castagnetti", "Zanimacchia", "Buonaiuto", "Coda", "Vazquez"], base_rating=6.9)
            else:
                teams[name] = self._create_dummy_team(name, "Serie A", base_rating=7.0)

        # --- BUNDESLIGA (Alemania) 2025-26 (18 equipos) ---
        # Promovidos: Hamburgo, Koln | Descendidos: Holstein Kiel, Bochum
        bundesliga_teams = [
            "Bayern Munich", "Bayer Leverkusen", "RB Leipzig", "Dortmund", "Stuttgart",
            "Frankfurt", "Freiburg", "Hoffenheim", "Werder Bremen", "Heidenheim",
            "Augsburg", "Wolfsburg", "Gladbach", "Union Berlin", "Mainz 05",
            "St. Pauli", "Hamburgo", "Koln"
        ]
        for name in bundesliga_teams:
            if name == "Bayern Munich":
                teams[name] = self._create_team(name, "Bundesliga", ["Neuer", "Guerreiro", "Upamecano", "Kim", "Davies", "Kimmich", "Palhinha", "Olise", "Musiala", "Gnabry", "Kane"], base_rating=9.2, avg_xg=2.4)
            elif name == "Bayer Leverkusen":
                teams[name] = self._create_team(name, "Bundesliga", ["Hrádecký", "Tapsoba", "Tah", "Hincapié", "Frimpong", "Xhaka", "Andrich", "Grimaldo", "Terrier", "Wirtz", "Boniface"], base_rating=8.9, avg_xg=2.2)
            elif name == "Dortmund":
                teams[name] = self._create_team(name, "Bundesliga", ["Kobel", "Ryerson", "Anton", "Schlotterbeck", "Couto", "Can", "Gross", "Sabitzer", "Brandt", "Guirassy", "Gittens"], base_rating=8.4)
            elif name == "RB Leipzig":
                teams[name] = self._create_team(name, "Bundesliga", ["Gulácsi", "Geertruida", "Orbán", "Lukeba", "Raum", "Haidara", "Seiwald", "Simons", "Sesko", "Openda", "Nusa"], base_rating=8.3)
            elif name == "Mainz 05":
                teams[name] = self._create_team(name, "Bundesliga", ["Zentner", "Kohr", "Jenz", "Leitsch", "Caci", "Sano", "Amiri", "Mwene", "Hong", "Lee", "Burkardt"], base_rating=7.4)
            elif name == "Hamburgo":
                teams[name] = self._create_team(name, "Bundesliga", ["Heuer Fernandes", "Hadzikadunic", "Schonlau", "Muheim", "Reis", "Meffert", "Elfadli", "Dompe", "Richter", "Glatzel", "Selke"], base_rating=7.2)
            else:
                teams[name] = self._create_dummy_team(name, "Bundesliga", base_rating=7.0)

        # --- LIGUE 1 (Francia) 2025-26 (18 equipos) ---
        # Promovidos: Lorient, Paris FC, Metz | Descendidos: Montpellier, Saint-Etienne, Reims
        ligue_1_teams = [
            "PSG", "Monaco", "Marseille", "Lille", "Nice",
            "Lens", "Rennes", "Lyon", "Toulouse", "Strasbourg",
            "Nantes", "Le Havre", "Auxerre", "Angers", "Brest",
            "Lorient", "Paris FC", "Metz"
        ]
        for name in ligue_1_teams:
            if name == "PSG":
                teams[name] = self._create_team(name, "Ligue 1", ["Donnarumma", "Hakimi", "Marquinhos", "Pacho", "Mendes", "Vitinha", "Neves", "Zaïre-Emery", "Dembélé", "Bradley Barcola", "Kolo Muani"], base_rating=8.9, avg_xg=2.6, avg_xg_c=0.8)
            elif name == "Monaco":
                teams[name] = self._create_team(name, "Ligue 1", ["Köhn", "Vanderson", "Kehrer", "Salisu", "Caio Henrique", "Zakaria", "Camara", "Akliouche", "Minamino", "Ben Seghir", "Embolo"], base_rating=8.1)
            elif name == "Marseille":
                teams[name] = self._create_team(name, "Ligue 1", ["Rulli", "Murillo", "Balerdi", "Cornelius", "Merlin", "Hojbjerg", "Rabiot", "Greenwood", "Harit", "Henrique", "Wahi"], base_rating=8.2)
            elif name == "Lille":
                teams[name] = self._create_team(name, "Ligue 1", ["Chevalier", "Tiago Santos", "Diakité", "Alexsandro", "Gudmundsson", "André", "Angel Gomes", "Zhegrova", "Cabella", "Sahraoui", "David"], base_rating=7.8)
            elif name == "Auxerre":
                teams[name] = self._create_team(name, "Ligue 1", ["Léon", "Jubal", "Zedadka", "Sciard", "Nkounkou", "Autret", "Sakamoto", "Gboho", "Sinayoko", "Pellenard", "Traoré"], base_rating=7.0)
            elif name == "Angers":
                teams[name] = self._create_team(name, "Ligue 1", ["Fofana", "Manceau", "Mendy", "Doumbia", "Colin", "Bentaleb", "Abdelli", "Doucouré", "Niane", "Batubinsika", "Kanga"], base_rating=7.0)
            elif name == "Lorient":
                teams[name] = self._create_team(name, "Ligue 1", ["Nardi", "Peda", "Laporte", "Talbi", "Le Goff", "Abergel", "Monconduit", "Innocent", "Fofana", "Hamel", "Kalulu"], base_rating=7.1)
            elif name == "Paris FC":
                teams[name] = self._create_team(name, "Ligue 1", ["Letellier", "Dramé", "Laporte", "Pape", "Bakwa", "Camara", "Zigi", "Selnaes", "Lopy", "Cardona", "Lebeau"], base_rating=6.9)
            elif name == "Metz":
                teams[name] = self._create_team(name, "Ligue 1", ["Oukidja", "Centonze", "Bronn", "Kouyaté", "Udol", "Diallo", "Thill", "Camara", "Gueye", "Boulaya", "Adli"], base_rating=7.0)
            else:
                teams[name] = self._create_dummy_team(name, "Ligue 1", base_rating=7.0)

        # --- SUPER LIG (Turquia) ---
        super_lig_teams = [
            "Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor",
            "Basaksehir", "Sivasspor", "Konyaspor", "Kayserispor",
            "Rizespor", "Antalyaspor", "Gaziantep", "Alanyaspor",
            "Kasimpasa", "Samsunspor", "Adana Demirspor", "Hatayspor",
        ]
        for name in super_lig_teams:
            if name == "Galatasaray":
                teams[name] = self._create_team(name, "Super Lig", ["Muslera", "Boey", "Davinson Sanchez", "Bardakci", "Angelino", "Demirbay", "Torreira", "Zaha", "Mertens", "Icardi", "Ziyech"], base_rating=8.5, avg_xg=2.1, avg_xg_c=0.9)
            elif name == "Fenerbahce":
                teams[name] = self._create_team(name, "Super Lig", ["Livakovic", "Osayi-Samuel", "Djiku", "Oosterwolde", "Crespo", "Fred", "Ismail Yuksek", "Szymanski", "Tadic", "Dzeko", "Batshuayi"], base_rating=8.4, avg_xg=2.0, avg_xg_c=0.95)
            elif name == "Besiktas":
                teams[name] = self._create_team(name, "Super Lig", ["Mert Gunok", "Nkoudou", "Vida", "Hadziahmetovic", "Al-Musrati", "Rafa Silva", "Mitrovic", "Salih Ucan", "Gedson", "Immobile", "Rashica"], base_rating=7.9, avg_xg=1.8, avg_xg_c=1.1)
            elif name == "Trabzonspor":
                teams[name] = self._create_team(name, "Super Lig", ["Ugurcan Cakir", "Vitor Hugo", "Cornelius", "Peres", "Gervinho", "Bakasetas", "Hamsik", "Berat Ozdemir", "Nwakaeme", "Djaniny", "Denswil"], base_rating=7.6)
            elif name == "Basaksehir":
                teams[name] = self._create_team(name, "Super Lig", ["Gunok", "Rafael", "Ponck", "Epureanu", "Clichy", "Topal", "Visca", "Tekdemir", "Giuliano", "Crivelli", "Robinho"], base_rating=7.4)
            else:
                teams[name] = self._create_dummy_team(name, "Super Lig", base_rating=7.0)

        # --- EREDIVISIE (Holanda) ---
        eredivisie_teams = [
            "Ajax", "PSV", "Feyenoord", "AZ Alkmaar", "Utrecht",
            "Twente", "Vitesse", "Groningen", "Heerenveen", "Sparta Rotterdam",
            "Go Ahead Eagles", "Almere City", "NEC Nijmegen", "Heracles",
        ]
        for name in eredivisie_teams:
            if name == "Ajax":
                teams[name] = self._create_team(name, "Eredivisie", ["Pasveer", "Rensch", "Timber", "Hato", "Gaaei", "Berghuis", "Henderson", "Taylor", "Bergwijn", "Brobbey", "Godts"], base_rating=8.2, avg_xg=2.0, avg_xg_c=1.0)
            elif name == "PSV":
                teams[name] = self._create_team(name, "Eredivisie", ["Benitez", "Karsdorp", "Flamingo", "Boscagli", "Dest", "Schouten", "Veerman", "Tillman", "Bakayoko", "De Jong", "Lang"], base_rating=8.6, avg_xg=2.3, avg_xg_c=0.8)
            elif name == "Feyenoord":
                teams[name] = self._create_team(name, "Eredivisie", ["Wellenreuther", "Geertruida", "Trauner", "Hancko", "Hartman", "Timber", "Zerrouki", "Stengs", "Paixao", "Gimenez", "Ivanusec"], base_rating=8.3, avg_xg=2.1, avg_xg_c=0.95)
            elif name == "AZ Alkmaar":
                teams[name] = self._create_team(name, "Eredivisie", ["Owusu", "Sugawara", "Penetra", "Martins Indi", "Mijnans", "De Wit", "Clasie", "Odgaard", "Evjen", "Pavlidis", "van Brederode"], base_rating=7.8)
            elif name == "Twente":
                teams[name] = self._create_team(name, "Eredivisie", ["Unnerstall", "Salah-Eddine", "Hilgers", "Vlap", "Oosterwolde", "Sadilek", "Bruns", "Steijn", "Rots", "Van Wolfswinkel", "Sem Steijn"], base_rating=7.7)
            else:
                teams[name] = self._create_dummy_team(name, "Eredivisie", base_rating=7.2)

        # --- PRIMEIRA LIGA (Portugal) ---
        primeira_liga_teams = [
            "Benfica", "FC Porto", "Sporting CP", "Braga", "Vitoria SC",
            "Boavista", "Gil Vicente", "Casa Pia", "Famalicao", "Rio Ave",
            "Moreirense", "Arouca", "Vizela", "Portimonense", "Estoril",
        ]
        for name in primeira_liga_teams:
            if name == "Benfica":
                teams[name] = self._create_team(name, "Primeira Liga", ["Trubin", "Bah", "Otamendi", "Silva", "Carreras", "Florentino", "Kokcü", "Di Maria", "Aursnes", "Rafa Silva", "Arthur Cabral"], base_rating=8.7, avg_xg=2.2, avg_xg_c=0.8)
            elif name == "FC Porto":
                teams[name] = self._create_team(name, "Primeira Liga", ["Diogo Costa", "Joao Mario", "Pepe", "Cardoso", "Wendell", "Uribe", "Grujic", "Galeno", "Pepe", "Evanilson", "Toni Martinez"], base_rating=8.5, avg_xg=2.1, avg_xg_c=0.85)
            elif name == "Sporting CP":
                teams[name] = self._create_team(name, "Primeira Liga", ["Israel", "Fresneda", "Coates", "Goncalo Inacio", "Nuno Santos", "Hjulmand", "Morita", "Trincao", "Edwards", "Gyokeres", "Pedro Goncalves"], base_rating=8.6, avg_xg=2.2, avg_xg_c=0.85)
            elif name == "Braga":
                teams[name] = self._create_team(name, "Primeira Liga", ["Matheus", "Yan Couto", "Carmo", "Oliveira", "Grimaldo", "Al Musrati", "Gorby", "Zalazar", "Rodrigues", "Banza", "Horta"], base_rating=7.8)
            else:
                teams[name] = self._create_dummy_team(name, "Primeira Liga", base_rating=7.2)

        # =====================================================================
        # LIGAS EUROPEAS — cargadas desde european_teams.py
        # =====================================================================
        try:
            from src.logic.european_teams import EUROPEAN_TEAMS
            country_league = {
                "Netherlands":    "Eredivisie",
                "Portugal":       "Primeira Liga",
                "Turkey":         "Süper Lig",
                "Scotland":       "Scottish Premiership",
                "Belgium":        "Belgian Pro League",
                "Austria":        "Austrian Bundesliga",
                "Switzerland":    "Swiss Super League",
                "Poland":         "Ekstraklasa",
                "Czech Republic": "Czech First League",
                "Denmark":        "Superliga",
                "Sweden":         "Allsvenskan",
                "Norway":         "Eliteserien",
                "Greece":         "Super League",
                "Croatia":        "HNL",
                "Serbia":         "SuperLiga",
                "Ukraine":        "Ukrainian Premier League",
                "Israel":         "Israeli Premier League",
                "N.Ireland":      "Irish League",
                "Argentina":      "Liga Profesional",
                "Brazil":         "Brasileirao",
            }
            for team_name, ctx in EUROPEAN_TEAMS.items():
                if team_name not in teams:
                    league_name = country_league.get(ctx.get("country", ""), "Europa")
                    teams[team_name] = self._create_dummy_team(team_name, league_name, base_rating=7.5)
        except ImportError:
            pass

        return teams

    def _create_team(self, name, league, key_players, base_rating=8.0, avg_xg=0.0, avg_xg_c=0.0):
        # Create players with DETERMINISTIC ratings (reproducible, sin random puro)
        import hashlib
        players = []
        # Standard 4-3-3 mapping template for rosters [GK, 4xDEF, 3xMID, 3xFWD]
        positions = [
            PlayerPosition.GOALKEEPER,
            PlayerPosition.DEFENDER, PlayerPosition.DEFENDER,
            PlayerPosition.DEFENDER, PlayerPosition.DEFENDER,
            PlayerPosition.MIDFIELDER, PlayerPosition.MIDFIELDER,
            PlayerPosition.MIDFIELDER,
            PlayerPosition.FORWARD, PlayerPosition.FORWARD,
            PlayerPosition.FORWARD
        ]
        roles = [
            NodeRole.KEEPER,
            NodeRole.DEFENSIVE, NodeRole.DEFENSIVE,
            NodeRole.DEFENSIVE, NodeRole.DEFENSIVE,
            NodeRole.CREATOR, NodeRole.CREATOR,
            NodeRole.CREATOR,
            NodeRole.FINALIZER, NodeRole.FINALIZER,
            NodeRole.FINALIZER
        ]
        
        for i, p_name in enumerate(key_players[:11]):
            role = roles[i] if i < len(roles) else NodeRole.NONE
            pos = positions[i] if i < len(positions) else PlayerPosition.MIDFIELDER
            
            # Seed determinista basado en nombre del jugador → siempre el mismo resultado
            seed_val = int(hashlib.md5(p_name.encode()).hexdigest()[:8], 16)
            variance = ((seed_val % 100) / 100.0) * 0.7 - 0.3  # Rango fijo: -0.3 a +0.4
            p_rating = max(0.0, min(10.0, round(base_rating + variance, 2)))
            
            # Métricas derivadas también deterministas
            xg_val    = round(0.1 + ((seed_val % 50) / 100.0) * 0.5, 2)
            xa_val    = round(0.05 + ((seed_val % 25) / 100.0) * 0.25, 2)
            ppda_val  = round(8.0 + ((seed_val % 60) / 10.0), 2)
            aerial    = round(0.4 + ((seed_val % 30) / 100.0), 2)
            prog_pass = 5 + (seed_val % 15)
            km_avg    = round(9.5 + ((seed_val % 25) / 10.0), 2)
            
            players.append(Player(
                id=f"{name}_{i}", 
                name=p_name, 
                team_name=name, 
                position=pos, 
                node_role=role,
                rating_last_5=p_rating, 
                xg_last_5=xg_val,
                xa_last_5=xa_val,
                ppda=ppda_val,
                aerial_duels_won_pct=aerial,
                progressive_passes=prog_pass,
                tracking_km_avg=km_avg
            ))
            
        return Team(
            name=name, 
            league=league, 
            players=players, 
            motivation_level=1.0,
            avg_xg_season=avg_xg if avg_xg > 0 else round((base_rating - 6.0) * 0.5, 2),
            avg_xg_conceded_season=avg_xg_c if avg_xg_c > 0 else round(max(0.5, 2.0 - (base_rating - 6.0) * 0.4), 2)
        )
    
    def _create_dummy_team(self, name, league="Unknown", base_rating=7.0):
        # Generic fill for non-star teams - Always 11 players for a "coherent study"
        key_players = [
            f"{name} GK", 
            f"{name} LD", f"{name} CT1", f"{name} CT2", f"{name} LI",
            f"{name} MC1", f"{name} MC2", f"{name} MO",
            f"{name} ED", f"{name} DC", f"{name} EI"
        ]
        return self._create_team(name, league, key_players, base_rating=base_rating, avg_xg=1.2, avg_xg_c=1.4)
    
    def get_last_match_lineup(self, team_name: str) -> List[str]:
        """
        Returns the lineup from the team's last match.
        In a real implementation, this would query match history.
        For now, returns the team's roster as a simulation.
        """
        team = self.get_team_data(team_name)
        if not team or not team.players:
            return []
        
        # Return first 11 players as "last match lineup"
        # In production, this would filter to only the 11 starters from last match
        return [p.name for p in team.players[:11]]

