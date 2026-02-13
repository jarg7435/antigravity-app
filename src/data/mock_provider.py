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

    def get_teams_by_league(self, league: str) -> List[str]:
        # Robust filtering: case-insensitive and stripped
        target = league.strip().lower()
        return [name for name, team in self.teams_db.items() if team.league.strip().lower() == target]

    def get_team_data(self, team_name: str) -> Team:
        return self.teams_db.get(team_name, self._create_dummy_team(team_name))

    def get_match_conditions(self, match_id: str, location: str, date_time: str) -> Optional[dict]:
        return {"temp": 20, "rain": 0}

    def _init_teams(self) -> Dict[str, Team]:
        teams = {}
        
        # --- LA LIGA (España) ---
        la_liga_teams = [
            "FC Barcelona", "Real Madrid", "Atletico Madrid", "Villarreal", "Real Betis", 
            "Espanyol", "Celta de Vigo", "Real Sociedad", "Osasuna", "Alavés", 
            "Athletic Club", "Girona", "Elche", "Mallorca", "Sevilla FC", 
            "Valencia", "Getafe", "Rayo Vallecano", "Levante", "Real Oviedo"
        ]
        for name in la_liga_teams:
            if name == "FC Barcelona":
                teams[name] = self._create_team(name, "La Liga", ["Ter Stegen", "Koundé", "Araujo", "Christensen", "Balde", "De Jong", "Pedri", "Gündogan", "Raphinha", "Lewandowski", "Gavi"], base_rating=8.8)
            elif name == "Real Madrid":
                teams[name] = self._create_team(name, "La Liga", ["Courtois", "Carvajal", "Rudiger", "Alaba", "Mendy", "Valverde", "Modric", "Bellingham", "Rodrygo", "Vinicius Jr", "Joselu"], base_rating=9.0)
            elif name == "Atletico Madrid":
                teams[name] = self._create_team(name, "La Liga", ["Oblak", "Molina", "Savic", "Gimenez", "Hermoso", "Koke", "De Paul", "Saul", "Llorente", "Griezmann", "Morata"], base_rating=8.5)
            elif name == "Villarreal":
                teams[name] = self._create_team(name, "La Liga", ["Jorgensen", "Foyth", "Albiol", "Bailly", "Pedraza", "Parejo", "Comesaña", "Pape Gueye", "Baena", "Gerard Moreno", "Sorloth"], base_rating=7.8)
            elif name == "Real Betis":
                teams[name] = self._create_team(name, "La Liga", ["Rui Silva", "Sabaly", "Pezzella", "Bartra", "Miranda", "Guido", "Carvalho", "Fekir", "Isco", "Ayoze", "Willian José"], base_rating=7.6)
            elif name == "Espanyol":
                teams[name] = self._create_team(name, "La Liga", ["Joan García", "El Hilali", "Kumbulla", "Cabrera", "Oliván", "Kral", "Lozano", "Tejero", "Jofre", "Puado", "Cheddira"], base_rating=7.0)
            elif name == "Real Sociedad":
                teams[name] = self._create_team(name, "La Liga", ["Remiro", "Aramburu", "Zubeldia", "Le Normand", "Muñoz", "Zubimendi", "Merino", "Brais", "Kubo", "Oyarzabal", "Cho"], base_rating=7.7)
            elif name == "Athletic Club":
                teams[name] = self._create_team(name, "La Liga", ["Unai Simón", "De Marcos", "Vivian", "Yeray", "Yuri", "Vesga", "Sancet", "Muniain", "Williams", "Guruzeta", "Williams"], base_rating=7.5)
            elif name == "Sevilla FC":
                teams[name] = self._create_team(name, "La Liga", ["Nyland", "Jesús Navas", "Badé", "Sergio Ramos", "Acuña", "Fernando", "Soumaré", "Suso", "Ocampos", "En-Nesyri", "Lukebakio"], base_rating=7.4)
            elif name == "Valencia":
                teams[name] = self._create_team(name, "La Liga", ["Mamardashvili", "Foulquier", "Mosquera", "Ozkacar", "Gayà", "Guillamón", "Pepelu", "Almeida", "López", "Duro", "Mari"], base_rating=7.2)
            else:
                teams[name] = self._create_dummy_team(name, "La Liga", base_rating=6.8)

        # --- PREMIER LEAGUE (Inglaterra) ---
        pl_teams = [
            "Arsenal", "Manchester City", "Aston Villa", "Manchester Utd", "Chelsea", 
            "Liverpool", "Brentford", "Sunderland", "Fulham", "Everton", 
            "Newcastle", "Bournemouth", "Brighton", "Tottenham", "Crystal Palace", 
            "Leeds Utd", "Nottingham Forest", "West Ham", "Burnley", "Wolves"
        ]
        for name in pl_teams:
            if name == "Manchester City":
                teams[name] = self._create_team(name, "Premier League", ["Ederson", "Walker", "Dias", "Akanji", "Gvardiol", "Rodri", "De Bruyne", "Bernardo", "Foden", "Haaland", "Grealish"], base_rating=9.2)
            elif name == "Arsenal":
                teams[name] = self._create_team(name, "Premier League", ["Raya", "White", "Saliba", "Gabriel", "Zinchenko", "Rice", "Odegaard", "Havertz", "Saka", "Jesus", "Martinelli"], base_rating=9.0)
            elif name == "Liverpool":
                teams[name] = self._create_team(name, "Premier League", ["Alisson", "Alexander-Arnold", "Van Dijk", "Konaté", "Robertson", "Mac Allister", "Szoboszlai", "Jones", "Salah", "Nunez", "Diaz"], base_rating=8.9)
            elif name == "Chelsea":
                teams[name] = self._create_team(name, "Premier League", ["Sánchez", "James", "Disasi", "Colwill", "Chilwell", "Caicedo", "Enzo", "Gallagher", "Palmer", "Jackson", "Sterling"], base_rating=7.8)
            elif name == "Manchester Utd":
                teams[name] = self._create_team(name, "Premier League", ["Onana", "Dalot", "Varane", "Martinez", "Shaw", "Casemiro", "Mainoo", "Bruno", "Rashford", "Højlund", "Garnacho"], base_rating=7.9)
            elif name == "Tottenham":
                teams[name] = self._create_team(name, "Premier League", ["Vicario", "Porro", "Romero", "Van de Ven", "Udogie", "Bissouma", "Sarr", "Maddison", "Kulusevski", "Son", "Richarlison"], base_rating=8.0)
            elif name == "Newcastle":
                teams[name] = self._create_team(name, "Premier League", ["Pope", "Trippier", "Schär", "Botman", "Burn", "Longstaff", "Guimarães", "Joelinton", "Gordon", "Isak", "Almirón"], base_rating=7.7)
            elif name == "Aston Villa":
                teams[name] = self._create_team(name, "Premier League", ["Martínez", "Cash", "Konsa", "Pau Torres", "Digne", "Douglas Luiz", "McGinn", "Bailey", "Diaby", "Watkins", "Tielemans"], base_rating=7.6)
            else:
                teams[name] = self._create_dummy_team(name, "Premier League", base_rating=7.0)

        # --- SERIE A (Italia) ---
        serie_a_teams = [
            "Inter Milan", "AC Milan", "Napoles", "Juventus", "AS Roma", 
            "Como", "Atalanta", "Lazio", "Udinese", "Bolonia", 
            "Sassuolo", "Cagliari", "Torino", "Genoa", "Fiorentina", 
            "Parma", "Verona", "Empoli", "Lecce", "Monza"
        ]
        for name in serie_a_teams:
            if name == "Inter Milan":
                teams[name] = self._create_team(name, "Serie A", ["Sommer", "Pavard", "Acerbi", "Bastoni", "Dumfries", "Barella", "Calhanoglu", "Mkhitaryan", "Dimarco", "Lautaro", "Thuram"], base_rating=8.7)
            elif name == "AC Milan":
                teams[name] = self._create_team(name, "Serie A", ["Maignan", "Calabria", "Tomori", "Thiaw", "Hernández", "Bennacer", "Reijnders", "Pulisic", "Loftus-Cheek", "Leão", "Giroud"], base_rating=8.3)
            elif name == "Juventus":
                teams[name] = self._create_team(name, "Serie A", ["Szczesny", "Danilo", "Bremer", "Gatti", "Cambiaso", "Locatelli", "Rabiot", "McKennie", "Chiesa", "Vlahovic", "Yildiz"], base_rating=8.2)
            elif name == "Napoles":
                teams[name] = self._create_team(name, "Serie A", ["Meret", "Di Lorenzo", "Rrahmani", "Juan Jesus", "Olivera", "Anguissa", "Lobotka", "Zielinski", "Politano", "Osimhen", "Kvaratskhelia"], base_rating=8.4)
            elif name == "AS Roma":
                teams[name] = self._create_team(name, "Serie A", ["Rui Patrício", "Mancini", "Smalling", "Llorente", "Spinazzola", "Cristante", "Paredes", "Pellegrini", "Dybala", "Lukaku", "El Shaarawy"], base_rating=7.9)
            elif name == "Atalanta":
                teams[name] = self._create_team(name, "Serie A", ["Carnesecchi", "Djimsiti", "Hien", "Kolasinac", "Zappacosta", "De Roon", "Ederson", "Koopmeiners", "Lookman", "Scamacca", "De Ketelaere"], base_rating=7.8)
            elif name == "Lazio":
                teams[name] = self._create_team(name, "Serie A", ["Provedel", "Lazzari", "Romagnoli", "Casale", "Marusic", "Guendouzi", "Cataldi", "Luis Alberto", "Felipe Anderson", "Immobile", "Zaccagni"], base_rating=7.6)
            else:
                teams[name] = self._create_dummy_team(name, "Serie A", base_rating=7.0)

        # --- BUNDESLIGA (Alemania) ---
        bundesliga_teams = [
            "Bayern Munich", "Bayer Leverkusen", "RB Leipzig", "Dortmund", "Stuttgart",
            "Frankfurt", "Hoffenheim", "Freiburg", "Heidenheim", "Augsburg",
            "Werder Bremen", "Wolfsburg", "Gladbach", "Union Berlin", "Bochum",
            "Mainz", "Koln", "Darmstadt" # 18 teams usually
        ]
        for name in bundesliga_teams:
            if name == "Bayern Munich":
                teams[name] = self._create_team(name, "Bundesliga", ["Neuer", "Mazraoui", "Upamecano", "De Ligt", "Davies", "Kimmich", "Goretzka", "Musiala", "Sané", "Kane", "Coman"], base_rating=9.1)
            elif name == "Bayer Leverkusen":
                teams[name] = self._create_team(name, "Bundesliga", ["Hrádecký", "Frimpong", "Tah", "Tapsoba", "Grimaldo", "Xhaka", "Palacios", "Wirtz", "Hofmann", "Boniface", "Adli"], base_rating=8.5)
            elif name == "Dortmund":
                teams[name] = self._create_team(name, "Bundesliga", ["Kobel", "Ryerson", "Hummels", "Schlotterbeck", "Bensebaini", "Can", "Sabitzer", "Brandt", "Adeyemi", "Füllkrug", "Malen"], base_rating=8.3)
            elif name == "RB Leipzig":
                teams[name] = self._create_team(name, "Bundesliga", ["Gulácsi", "Klostermann", "Orbán", "Simakan", "Raum", "Schlager", "Kampl", "Simons", "Olmo", "Openda", "Sesko"], base_rating=8.0)
            else:
                teams[name] = self._create_dummy_team(name, "Bundesliga", base_rating=7.0)

        # --- LIGUE 1 (Francia) ---
        ligue_1_teams = [
             "PSG", "Monaco", "Brest", "Lille", "Nice",
             "Lens", "Marseille", "Rennes", "Reims", "Lyon",
             "Toulouse", "Strasbourg", "Montpellier", "Lorient", "Nantes",
             "Metz", "Le Havre", "Clermont" # 18 teams
        ]
        for name in ligue_1_teams:
            if name == "PSG":
                teams[name] = self._create_team(name, "Ligue 1", ["Donnarumma", "Hakimi", "Marquinhos", "Skriniar", "Mendes", "Vitinha", "Zaïre-Emery", "Ruiz", "Dembélé", "Mbappé", "Asensio"], base_rating=9.0)
            elif name == "Monaco":
                teams[name] = self._create_team(name, "Ligue 1", ["Köhn", "Vanderson", "Singo", "Salisu", "Henrique", "Fofana", "Camara", "Golovin", "Minamino", "Ben Yedder", "Embolo"], base_rating=7.8)
            elif name == "Marseille":
                teams[name] = self._create_team(name, "Ligue 1", ["Pau López", "Clauss", "Mbemba", "Balerdi", "Merlin", "Rongier", "Veretout", "Harit", "Greenwood", "Aubameyang", "Vitinha"], base_rating=7.7)
            elif name == "Lille":
                teams[name] = self._create_team(name, "Ligue 1", ["Chevalier", "Meunier", "Diakité", "Alexsandro", "Gudmundsson", "André", "Gomes", "Cabella", "Zhegrova", "David", "Haraldsson"], base_rating=7.6)
            else:
                teams[name] = self._create_dummy_team(name, "Ligue 1", base_rating=7.0)

        return teams

    def _create_team(self, name, league, key_players, base_rating=8.0):
        # Create dummy players based on names
        import random
        players = []
        roles = [NodeRole.FINALIZER, NodeRole.CREATOR, NodeRole.DEFENSIVE, NodeRole.KEEPER, NodeRole.TACTICAL]
        positions = [PlayerPosition.FORWARD, PlayerPosition.MIDFIELDER, PlayerPosition.DEFENDER, PlayerPosition.GOALKEEPER, PlayerPosition.MIDFIELDER]
        
        for i, p_name in enumerate(key_players):
            role = roles[i] if i < len(roles) else NodeRole.NONE
            pos = positions[i] if i < len(positions) else PlayerPosition.MIDFIELDER
            
            # Add slight variance to individual players
            p_rating = base_rating + (random.uniform(-0.3, 0.4))
            
            players.append(Player(
                id=f"{name}_{i}", 
                name=p_name, 
                team_name=name, 
                position=pos, 
                node_role=role,
                rating_last_5=round(p_rating, 2), 
                xg_last_5=round(random.uniform(0.1, 0.6), 2),
                xa_last_5=round(random.uniform(0.05, 0.3), 2),
                ppda=round(random.uniform(8.0, 14.0), 2),
                aerial_duels_won_pct=round(random.uniform(0.4, 0.7), 2),
                progressive_passes=random.randint(5, 20),
                tracking_km_avg=round(random.uniform(9.5, 12.0), 2)
            ))
            
        return Team(name=name, league=league, players=players, motivation_level=1.0)
    
    def _create_dummy_team(self, name, league="Unknown", base_rating=7.0):
        # Generic fill for non-star teams
        return self._create_team(name, league, [f"{name} Fwd", f"{name} Mid", f"{name} Def", f"{name} GK", f"{name} Coach"], base_rating=base_rating)
    
    def get_last_match_lineup(self, team_name: str) -> List[str]:
        """
        Returns the lineup from the team's last match.
        In a real implementation, this would query match history.
        For now, returns the team's roster as a simulation.
        """
        team = self.get_team_data(team_name)
        if not team or not team.players:
            return []
        
        # Return all players as "last match lineup"
        # In production, this would filter to only the 11 starters from last match
        return [p.name for p in team.players[:11] if p.status == PlayerStatus.TITULAR]

