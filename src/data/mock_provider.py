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
        if not league:
            return []
            
        # Handle Liga Mixta (Combinada) - Return all available teams
        # We check for 'mixta' or 'combinada' to be very robust
        search_term = str(league).lower()
        if "mixta" in search_term or "combinada" in search_term:
            return sorted(list(self.teams_db.keys()))
            
        # Robust filtering: case-insensitive and stripped
        target = league.strip().lower()
        if "(" in target:
            target = target.split("(")[0].strip()
            
        return [name for name, team in self.teams_db.items() if (team.league.strip().lower() == target or target in team.league.strip().lower())]

    def get_team_data(self, team_name: str) -> Team:
        if not team_name:
            team_name = "Equipo Desconocido"
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
                teams[name] = self._create_team(name, "La Liga", ["Conde", "Femenía", "Albiol", "Bailly", "Sergi Cardona", "Parejo", "Comesaña", "Baena", "Yeremy", "Barry", "Ayoze"], base_rating=7.9)
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
                teams[name] = self._create_team(name, "La Liga", ["Mamardashvili", "Foulquier", "Mosquera", "Tárrega", "Vázquez", "Pepelu", "Barrenechea", "Almeida", "Diego López", "Hugo Duro", "Rioja"], base_rating=7.3)
            else:
                teams[name] = self._create_dummy_team(name, "La Liga", base_rating=6.9)

        # --- PREMIER LEAGUE (Inglaterra) ---
        pl_teams = [
            "Arsenal", "Manchester City", "Aston Villa", "Manchester Utd", "Chelsea", 
            "Liverpool", "Brentford", "Sunderland", "Fulham", "Everton", 
            "Newcastle", "Bournemouth", "Brighton", "Tottenham", "Crystal Palace", 
            "Leeds Utd", "Nottingham Forest", "West Ham", "Burnley", "Wolves"
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
            else:
                teams[name] = self._create_dummy_team(name, "Premier League", base_rating=7.1)

        # --- SERIE A (Italia) ---
        serie_a_teams = [
            "Inter Milan", "AC Milan", "Napoles", "Juventus", "AS Roma", 
            "Como", "Atalanta", "Lazio", "Udinese", "Bolonia", 
            "Sassuolo", "Cagliari", "Torino", "Genoa", "Fiorentina", 
            "Parma", "Verona", "Empoli", "Lecce", "Monza"
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
                teams[name] = self._create_team(name, "Bundesliga", ["Neuer", "Guerreiro", "Upamecano", "Kim", "Davies", "Kimmich", "Palhinha", "Olise", "Musiala", "Gnabry", "Kane"], base_rating=9.2, avg_xg=2.4)
            elif name == "Bayer Leverkusen":
                teams[name] = self._create_team(name, "Bundesliga", ["Hrádecký", "Tapsoba", "Tah", "Hincapié", "Frimpong", "Xhaka", "Andrich", "Grimaldo", "Terrier", "Wirtz", "Boniface"], base_rating=8.9, avg_xg=2.2)
            elif name == "Dortmund":
                teams[name] = self._create_team(name, "Bundesliga", ["Kobel", "Ryerson", "Anton", "Schlotterbeck", "Couto", "Can", "Gross", "Sabitzer", "Brandt", "Guirassy", "Gittens"], base_rating=8.4)
            elif name == "RB Leipzig":
                teams[name] = self._create_team(name, "Bundesliga", ["Gulácsi", "Geertruida", "Orbán", "Lukeba", "Raum", "Haidara", "Seiwald", "Simons", "Sesko", "Openda", "Nusa"], base_rating=8.3)
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
                teams[name] = self._create_team(name, "Ligue 1", ["Donnarumma", "Hakimi", "Marquinhos", "Pacho", "Mendes", "Vitinha", "Neves", "Zaïre-Emery", "Dembélé", "Bradley Barcola", "Kolo Muani"], base_rating=8.9, avg_xg=2.6, avg_xg_c=0.8)
            elif name == "Monaco":
                teams[name] = self._create_team(name, "Ligue 1", ["Köhn", "Vanderson", "Kehrer", "Salisu", "Caio Henrique", "Zakaria", "Camara", "Akliouche", "Minamino", "Ben Seghir", "Embolo"], base_rating=8.1)
            elif name == "Marseille":
                teams[name] = self._create_team(name, "Ligue 1", ["Rulli", "Murillo", "Balerdi", "Cornelius", "Merlin", "Hojbjerg", "Rabiot", "Greenwood", "Harit", "Henrique", "Wahi"], base_rating=8.2)
            elif name == "Lille":
                teams[name] = self._create_team(name, "Ligue 1", ["Chevalier", "Tiago Santos", "Diakité", "Alexsandro", "Gudmundsson", "André", "Angel Gomes", "Zhegrova", "Cabella", "Sahraoui", "David"], base_rating=7.8)
            else:
                teams[name] = self._create_dummy_team(name, "Ligue 1", base_rating=7.0)

        return teams

    def _create_team(self, name, league, key_players, base_rating=8.0, avg_xg=0.0, avg_xg_c=0.0):
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
            
            # Ensure rating stays within Pydantic bounds (0-10)
            p_rating = max(0.0, min(10.0, p_rating))
            
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
            
        return Team(
            name=name, 
            league=league, 
            players=players, 
            motivation_level=1.0,
            avg_xg_season=avg_xg if avg_xg > 0 else (base_rating - 6.0) * 0.5, # Fallback estimate
            avg_xg_conceded_season=avg_xg_c if avg_xg_c > 0 else max(0.5, 2.0 - (base_rating - 6.0) * 0.4) # Fallback estimate
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
        
        # Return all players as "last match lineup"
        # In production, this would filter to only the 11 starters from last match
        return [p.name for p in team.players[:11] if p.status == PlayerStatus.TITULAR]

