"""
mock_provider.py — LAGEMA JARG74 Ecosistema 4.0
================================================
Proveedor de datos con equipos OFICIALES temporada 2025/2026.
Actualización: 18 equipos en La Liga, 20 en Premier, 18 en Bundesliga, etc.

Prioridad: P0-Crítico. Datos de temporada incorrectos invalidan análisis.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import logging

from src.models.base import Team, Player, PlayerPosition, PlayerStatus, Match

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# MAPEO OFICIAL DE EQUIPOS TEMPORADA 2025/2026
# =============================================================================

OFFICIAL_TEAMS = {
    # --- LA LIGA ESPAÑA (18 equipos desde 2024/25) ---
    "La Liga": [
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta",
        "Espanyol", "Getafe", "Girona", "Leganes", "Mallorca",
        "Osasuna", "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad",
        "Sevilla", "Valencia", "Villarreal"
    ],
    
    # --- PREMIER LEAGUE INGLATERRA (20 equipos) ---
    "Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
        "Liverpool", "Luton Town", "Manchester City", "Manchester Utd",
        "Newcastle", "Nottingham Forest", "Sheffield Utd", "Tottenham",
        "West Ham", "Wolves"
    ],
    
    # --- BUNDESLIGA ALEMANIA (18 equipos) ---
    "Bundesliga": [
        "Augsburg", "Bayer Leverkusen", "Bayern Munich", "Bochum", "Darmstadt",
        "Dortmund", "Ein Frankfurt", "Freiburg", "Heidenheim", "Hoffenheim",
        "Koln", "Mainz", "Mgladbach", "RB Leipzig", "Stuttgart",
        "Union Berlin", "Werder Bremen", "Wolfsburg"
    ],
    
    # --- SERIE A ITALIA (20 equipos) ---
    "Serie A": [
        "AC Milan", "Atalanta", "Bologna", "Cagliari", "Empoli",
        "Fiorentina", "Frosinone", "Genoa", "Inter Milan", "Juventus",
        "Lazio", "Lecce", "Monza", "Napoli", "Roma",
        "Salernitana", "Sassuolo", "Torino", "Udinese", "Verona"
    ],
    
    # --- LIGUE 1 FRANCIA (18 equipos desde 2024/25) ---
    "Ligue 1": [
        "Angers", "Auxerre", "Brest", "Havre", "Lens",
        "Lille", "Lyon", "Marseille", "Monaco", "Montpellier",
        "Nantes", "Nice", "PSG", "Reims", "Rennes",
        "Strasbourg", "Toulouse", "Saint-Etienne"
    ],
    
    # --- EREDIVISIE HOLANDA (18 equipos) ---
    "Eredivisie": [
        "Ajax", "Almere City", "AZ Alkmaar", "Excelsior", "Feyenoord",
        "Fortuna Sittard", "Go Ahead Eagles", "Heerenveen", "Heracles",
        "NEC Nijmegen", "PEC Zwolle", "PSV", "RKC Waalwijk", "Sparta Rotterdam",
        "Twente", "Utrecht", "Vitesse", "Volendam"
    ],
    
    # --- PRIMEIRA LIGA PORTUGAL (18 equipos) ---
    "Primeira Liga": [
        "Arouca", "Benfica", "Boavista", "Braga", "Casa Pia",
        "Chaves", "Estoril", "Famalicao", "Farense", "Gil Vicente",
        "Moreirense", "Portimonense", "Porto", "Rio Ave", "Sporting CP",
        "Vitoria Guimaraes", "Vizela", "Estrela Amadora"
    ],
    
    # --- CHAMPIONS LEAGUE (nuevo formato 2024/25+) ---
    "Champions League": [
        "Arsenal", "Aston Villa", "Atalanta", "Barcelona", "Bayern Munich",
        "Benfica", "Bologna", "Borussia Dortmund", "Brest", "Celtic",
        "Club Brugge", "Crvena Zvezda", "Feyenoord", "Girona", "Inter Milan",
        "Juventus", "Leipzig", "Leverkusen", "Lille", "Liverpool",
        "Manchester City", "Milan", "Monaco", "Paris Saint-Germain", "PSV",
        "Real Madrid", "Salzburg", "Shakhtar Donetsk", "Slovan Bratislava",
        "Sparta Prague", "Sporting CP", "Sturm Graz", "VfB Stuttgart", "Young Boys"
    ],
    
    # --- EUROPA LEAGUE ---
    "Europa League": [
        "Ajax", "Athletic Club", "AZ Alkmaar", "Besiktas", "Bodø/Glimt",
        "Braga", "Dinamo Zagreb", "Eintracht Frankfurt", "Fenerbahce", "Galatasaray",
        "Lazio", "Lyon", "Malmö FF", "Manchester Utd", "Midtjylland",
        "Nice", "Olympiacos", "PAOK", "Porto", "Qarabağ",
        "Rangers", "Real Sociedad", "Roma", "RFS", "Slavia Prague",
        "Tottenham", "Twente", "Union Saint-Gilloise"
    ],
    
    # --- CONFERENCE LEAGUE ---
    "Conference League": [
        "Anderlecht", "Astana", "Basel", "Celje", "Copenhagen",
        "Dynamo Kyiv", "Fiorentina", "Gent", "Hearts", "HJK Helsinki",
        "Istanbul Basaksehir", "Jagiellonia Bialystok", "Larne", "LASK", "Legia Warsaw",
        "Lugano", "Maccabi Tel Aviv", "Molde", "Olimpija Ljubljana", "PAOK",
        "Petrocub Hincesti", "Real Betis", "Rijeka", "Silkeborg", "St. Gallen",
        "The New Saints", "Viktoria Plzen", "Zira"
    ],
    
    # --- SCOTTISH PREMIERSHIP ---
    "Scottish Premiership": [
        "Aberdeen", "Celtic", "Dundee", "Dundee Utd", "Hearts",
        "Hibernian", "Kilmarnock", "Motherwell", "Rangers", "Ross County",
        "St Johnstone", "St Mirren"
    ],
    
    # --- BELGIAN PRO LEAGUE ---
    "Belgian Pro League": [
        "Anderlecht", "Antwerp", "Cercle Brugge", "Charleroi", "Club Brugge",
        "Dender", "Genk", "Gent", "Kortrijk", "Mechelen",
        "OHL", "Sint-Truiden", "Standard Liege", "Union SG", "Westerlo"
    ],
    
    # --- AUSTRIAN BUNDESLIGA ---
    "Austrian Bundesliga": [
        "Austria Klagenfurt", "Austria Wien", "BW Linz", "LASK", "Rapid Wien",
        "Red Bull Salzburg", "Sturm Graz", "Tirol", "Wolfsberger AC", "WSG Swarovski Tirol"
    ],
    
    # --- SWISS SUPER LEAGUE ---
    "Swiss Super League": [
        "Basel", "Grasshoppers", "Lausanne-Sport", "Lugano", "Luzern",
        "Servette", "Sion", "St. Gallen", "Young Boys", "Zurich"
    ],
    
    # --- POLISH EKSTRAKLASA ---
    "Ekstraklasa": [
        "Cracovia", "Gornik Zabrze", "Jagiellonia Bialystok", "Korona Kielce", "Lech Poznan",
        "Legia Warsaw", "LKS Lodz", "Piast Gliwice", "Pogon Szczecin", "Puszcza Niepolomice",
        "Radomiak Radom", "Rakow Czestochowa", "Slask Wroclaw", "Stal Mielec", "Warta Poznan",
        "Widzew Lodz", "Zaglebie Lubin", "Lechia Gdansk"
    ],
    
    # --- CZECH FIRST LEAGUE ---
    "Czech First League": [
        "Banik Ostrava", "Bohemians 1905", "Dynamo Ceske Budejovice", "Hradec Kralove", "Jablonec",
        "MFK Karvina", "Mlada Boleslav", "Pardubice", "Slovacko", "Slovan Liberec",
        "Sparta Prague", "Sigma Olomouc", "Teplice", "Viktoria Plzen", "Zlin",
        "Bohemians Prague", "Dukla Prague", "Vysocina Jihlava"
    ],
    
    # --- DANISH SUPERLIGA ---
    "Superliga": [
        "Aarhus GF", "Brondby", "FC Copenhagen", "Lyngby", "Midtjylland",
        "Nordsjaelland", "OB", "Randers", "Silkeborg", "Sonderjyske",
        "Vejle", "Viborg"
    ],
    
    # --- SWEDISH ALLSVENSKAN ---
    "Allsvenskan": [
        "AIK", "BK Hacken", "Djurgardens", "Elfsborg", "GAIS",
        "Goteborg", "Hammarby", "Halmstads", "IFK Norrkoping", "IFK Varnamo",
        "Kalmar", "Malmo FF", "Mjallby", "Sirius", "Varbergs",
        "Degerfors", "Orebro", "Sundsvall"
    ],
    
    # --- NORWEGIAN ELITESERIEN ---
    "Eliteserien": [
        "Aalesund", "Bodo/Glimt", "Brann", "Fredrikstad", "Haugesund",
        "KFUM Oslo", "Kristiansund", "Lillestrom", "Molde", "Odd",
        "Rosenborg", "Sandefjord", "Sarpsborg 08", "Stromsgodset", "Tromso",
        "Viking", "HamKam", "Sogndal"
    ],
    
    # --- GREEK SUPER LEAGUE ---
    "Super League": [
        "AEK Athens", "Aris", "Asteras Tripolis", "Atromitos", "Lamia",
        "Levadiakos", "OFI", "Olympiacos", "Panathinaikos", "Panetolikos",
        "PAOK", "PAS Giannina", "Panserraikos", "Volos", "Kifisia"
    ],
    
    # --- CROATIAN HNL ---
    "HNL": [
        "Dinamo Zagreb", "Hajduk Split", "HNK Gorica", "Istra 1961", "Lokomotiva Zagreb",
        "NK Osijek", "Rijeka", "Slaven Belupo", "Varazdin", "Sibenik"
    ],
    
    # --- SERBIAN SUPERLIGA ---
    "SuperLiga": [
        "Crvena Zvezda", "Cukaricki", "IMT", "Javor", "Mladost Lucani",
        "Napredak", "Novi Pazar", "Partizan", "Radnicki 1923", "Radnicki Nis",
        "Spartak Subotica", "TSC", "Vojvodina", "Zeleznicar Pancevo", "Zemun",
        "Tekstilac", "Sloga Meridian", "OFK Beograd"
    ],
    
    # --- UKRAINIAN PREMIER LEAGUE ---
    "Ukrainian Premier League": [
        "Chornomorets Odesa", "Dnipro-1", "Dynamo Kyiv", "Karpaty Lviv", "Kolos Kovalivka",
        "Kryvbas Kryvyi Rih", "LNZ Cherkasy", "Metalist 1925", "Obolon Kyiv", "Oleksandriya",
        "Polissya Zhytomyr", "Rukh Lviv", "Shakhtar Donetsk", "Veres Rivne", "Vorskla Poltava",
        "Zorya Luhansk"
    ],
    
    # --- ISRAELI PREMIER LEAGUE ---
    "Israeli Premier League": [
        "Beitar Jerusalem", "Bnei Sakhnin", "F.C. Ashdod", "Hapoel Be'er Sheva", "Hapoel Hadera",
        "Hapoel Haifa", "Hapoel Jerusalem", "Hapoel Petah Tikva", "Hapoel Tel Aviv", "Ironi Kiryat Shmona",
        "Maccabi Bnei Reineh", "Maccabi Haifa", "Maccabi Netanya", "Maccabi Petah Tikva", "Maccabi Tel Aviv"
    ],
    
    # --- ARGENTINE LIGA PROFESIONAL ---
    "Liga Profesional": [
        "Argentinos Juniors", "Atletico Tucuman", "Banfield", "Barracas Central", "Belgrano",
        "Boca Juniors", "Central Cordoba", "Defensa y Justicia", "Deportivo Riestra", "Estudiantes",
        "Gimnasia La Plata", "Godoy Cruz", "Huracan", "Independiente", "Independiente Rivadavia",
        "Instituto", "Lanus", "Newell's Old Boys", "Platense", "Racing Club",
        "River Plate", "Rosario Central", "San Lorenzo", "Sarmiento", "Talleres",
        "Tigre", "Union", "Velez Sarsfield"
    ],
    
    # --- BRAZILIAN BRASILEIRAO ---
    "Brasileirao": [
        "Athletico Paranaense", "Atletico Goianiense", "Atletico Mineiro", "Bahia", "Botafogo",
        "Corinthians", "Criciuma", "Cruzeiro", "Cuiaba", "Flamengo",
        "Fluminense", "Fortaleza", "Gremio", "Internacional", "Juventude",
        "Palmeiras", "Red Bull Bragantino", "Sao Paulo", "Vasco da Gama", "Vitoria"
    ]
}

# Mapeo de nombres alternativos/normalizados
TEAM_NAME_ALIASES = {
    # Premier League
    "Manchester United": "Manchester Utd",
    "Man United": "Manchester Utd",
    "Man Utd": "Manchester Utd",
    "Newcastle United": "Newcastle",
    "Newcastle Utd": "Newcastle",
    "Nottingham Forest": "Nottingham Forest",
    "Sheffield United": "Sheffield Utd",
    "Sheffield Utd": "Sheffield Utd",
    "Tottenham Hotspur": "Tottenham",
    "Spurs": "Tottenham",
    "West Ham United": "West Ham",
    "West Ham Utd": "West Ham",
    "Wolverhampton": "Wolves",
    "Wolverhampton Wanderers": "Wolves",
    "Brighton & Hove Albion": "Brighton",
    "Brighton and Hove Albion": "Brighton",
    
    # La Liga
    "Barcelona": "Barcelona",
    "FC Barcelona": "Barcelona",
    "Real Betis": "Real Betis",
    "Betis": "Real Betis",
    "Atletico": "Atletico Madrid",
    "Atlético Madrid": "Atletico Madrid",
    "Atletico de Madrid": "Atletico Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Athletic Club de Bilbao": "Athletic Club",
    "Celta Vigo": "Celta",
    "RC Celta": "Celta",
    "Deportivo Alaves": "Alaves",
    "Alavés": "Alaves",
    "Espanyol": "Espanyol",
    "RCD Espanyol": "Espanyol",
    "Girona FC": "Girona",
    "CD Leganes": "Leganes",
    "Leganés": "Leganes",
    "RCD Mallorca": "Mallorca",
    "Osasuna": "Osasuna",
    "CA Osasuna": "Osasuna",
    "Rayo Vallecano": "Rayo Vallecano",
    "Real Madrid CF": "Real Madrid",
    "Real Sociedad": "Real Sociedad",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    
    # Bundesliga
    "Borussia Dortmund": "Dortmund",
    "Borussia Mgladbach": "Mgladbach",
    "Borussia Monchengladbach": "Mgladbach",
    "Borussia Mönchengladbach": "Mgladbach",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "FC Bayern Munich": "Bayern Munich",
    "Bayern München": "Bayern Munich",
    "FC Bayern München": "Bayern Munich",
    "RB Leipzig": "Leipzig",
    "RasenBallsport Leipzig": "Leipzig",
    "Bayer 04 Leverkusen": "Bayer Leverkusen",
    "TSG Hoffenheim": "Hoffenheim",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "Werder Bremen": "Werder Bremen",
    "1. FC Union Berlin": "Union Berlin",
    "SC Freiburg": "Freiburg",
    "1. FC Heidenheim": "Heidenheim",
    "1. FC Köln": "Koln",
    "FSV Mainz 05": "Mainz",
    "VfL Bochum": "Bochum",
    "SV Darmstadt 98": "Darmstadt",
    
    # Serie A
    "Milan": "AC Milan",
    "Internazionale": "Inter Milan",
    "Inter": "Inter Milan",
    "FC Internazionale Milano": "Inter Milan",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "SSC Napoli": "Napoli",
    "Juventus FC": "Juventus",
    "Atalanta BC": "Atalanta",
    "Bologna FC 1909": "Bologna",
    "Cagliari Calcio": "Cagliari",
    "Empoli FC": "Empoli",
    "ACF Fiorentina": "Fiorentina",
    "Frosinone Calcio": "Frosinone",
    "Genoa CFC": "Genoa",
    "US Lecce": "Lecce",
    "AC Monza": "Monza",
    "US Salernitana 1919": "Salernitana",
    "US Sassuolo": "Sassuolo",
    "Torino FC": "Torino",
    "Udinese Calcio": "Udinese",
    "Hellas Verona": "Verona",
    
    # Ligue 1
    "Paris Saint-Germain": "PSG",
    "Paris SG": "PSG",
    "Paris Saint-Germain FC": "PSG",
    "Olympique Marseille": "Marseille",
    "OM": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "OL": "Lyon",
    "OGC Nice": "Nice",
    "AS Monaco": "Monaco",
    "AS Monaco FC": "Monaco",
    "Stade Brestois 29": "Brest",
    "RC Lens": "Lens",
    "Lille OSC": "Lille",
    "LOSC Lille": "Lille",
    "Montpellier HSC": "Montpellier",
    "FC Nantes": "Nantes",
    "Stade de Reims": "Reims",
    "Stade Rennais FC": "Rennes",
    "RC Strasbourg Alsace": "Strasbourg",
    "Toulouse FC": "Toulouse",
    "Le Havre AC": "Havre",
    "AC Ajaccio": "Ajaccio",
    "Angers SCO": "Angers",
    "AJ Auxerre": "Auxerre",
    "AS Saint-Étienne": "Saint-Etienne",
    
    # Otras ligas europeas
    "Sporting Lisbon": "Sporting CP",
    "Sporting Clube de Portugal": "Sporting CP",
    "FC Porto": "Porto",
    "Futebol Clube do Porto": "Porto",
    "Benfica": "Benfica",
    "SL Benfica": "Benfica",
    "Sport Lisboa e Benfica": "Benfica",
    "Club Brugge KV": "Club Brugge",
    "RSC Anderlecht": "Anderlecht",
    "Celtic FC": "Celtic",
    "Rangers FC": "Rangers",
    "Feyenoord": "Feyenoord",
    "AFC Ajax": "Ajax",
    "PSV Eindhoven": "PSV",
    "Besiktas JK": "Besiktas",
    "Galatasaray SK": "Galatasaray",
    "Fenerbahce SK": "Fenerbahce",
    
    # Champions League
    "Manchester City": "Manchester City",
    "Paris Saint-Germain FC": "Paris Saint-Germain",
    "PSV Eindhoven": "PSV",
    "BSC Young Boys": "Young Boys",
    "FK Crvena Zvezda": "Crvena Zvezda",
    "Red Star Belgrade": "Crvena Zvezda",
    "SK Sturm Graz": "Sturm Graz",
    "Slovan Bratislava": "Slovan Bratislava",
    "AC Sparta Prague": "Sparta Prague",
    "FC Salzburg": "Salzburg",
    "Red Bull Salzburg": "Salzburg",
    "Shakhtar Donetsk": "Shakhtar Donetsk",
    "FC Shakhtar Donetsk": "Shakhtar Donetsk",
}


@dataclass
class TeamData:
    """Estructura interna para almacenar datos de equipo con metadatos."""
    name: str
    league: str
    players: List[Player] = field(default_factory=list)
    tactical_style: str = "Equilibrado"
    avg_xg_season: float = 1.35
    avg_xg_conceded_season: float = 1.35
    last_updated: datetime = field(default_factory=datetime.now)


class MockDataProvider:
    """
    Proveedor de datos con validación estricta de equipos por competición.
    Temporada 2025/2026: 18 equipos en La Liga, 20 en Premier, etc.
    """
    
    def __init__(self):
        self._teams_db: Dict[str, TeamData] = {}
        self._last_lineups: Dict[str, List[str]] = {}
        self._initialize_database()
        logger.info(f"MockDataProvider inicializado con {len(self._teams_db)} equipos validados")
    
    def _normalize_team_name(self, name: str) -> str:
        """Normaliza nombres de equipos usando aliases."""
        name_clean = name.strip()
        return TEAM_NAME_ALIASES.get(name_clean, name_clean)
    
    def _validate_league_membership(self, team_name: str, league: str) -> bool:
        """
        Valida que un equipo realmente pertenezca a una liga.
        """
        normalized_name = self._normalize_team_name(team_name)
        
        # Obtener lista oficial de la liga
        official_teams = OFFICIAL_TEAMS.get(league, [])
        
        # Verificar coincidencia exacta o parcial
        for official in official_teams:
            if normalized_name.lower() == official.lower():
                return True
            # Permitir coincidencia parcial para nombres largos
            if normalized_name.lower() in official.lower() or official.lower() in normalized_name.lower():
                return True
        
        logger.warning(f"VALIDACIÓN FALLIDA: '{team_name}' (normalizado: '{normalized_name}') "
                      f"no pertenece a '{league}'")
        return False
    
    def _generate_players(self, team_name: str, count: int = 25) -> List[Player]:
        """Genera plantilla realista de jugadores."""
        positions = [
            (PlayerPosition.GOALKEEPER, 3),
            (PlayerPosition.DEFENDER, 8),
            (PlayerPosition.MIDFIELDER, 8),
            (PlayerPosition.FORWARD, 6)
        ]
        
        players = []
        player_id = 0
        
        for pos, num in positions:
            for i in range(num):
                if len(players) >= count:
                    break
                
                # Generar nombre realista
                if pos == PlayerPosition.GOALKEEPER:
                    name = f"Portero {i+1}"
                elif pos == PlayerPosition.DEFENDER:
                    name = f"Defensa {i+1}"
                elif pos == PlayerPosition.MIDFIELDER:
                    name = f"Centrocampista {i+1}"
                else:
                    name = f"Delantero {i+1}"
                
                player = Player(
                    id=f"{team_name}_{player_id}",
                    name=name,
                    team_name=team_name,
                    position=pos,
                    status=PlayerStatus.TITULAR if i < (11 if pos != PlayerPosition.GOALKEEPER else 1) else PlayerStatus.SUPLENTE,
                    rating_last_5=round(random.uniform(6.0, 8.5), 2),
                    goals_season=random.randint(0, 15) if pos == PlayerPosition.FORWARD else random.randint(0, 5),
                    assists_season=random.randint(0, 10),
                    minutes_played=random.randint(500, 2500)
                )
                players.append(player)
                player_id += 1
        
        return players
    
    def _initialize_database(self):
        """Inicializa la base de datos con equipos validados por liga."""
        logger.info("Inicializando base de datos TEMPORADA 2025/2026...")
        
        for league, teams in OFFICIAL_TEAMS.items():
            # Configurar estadísticas base según la liga
            if league == "Premier League":
                base_xg_range = (1.4, 1.8)
                defense_range = (1.0, 1.4)
            elif league == "La Liga":
                base_xg_range = (1.2, 1.6)
                defense_range = (0.9, 1.3)
            elif league == "Bundesliga":
                base_xg_range = (1.5, 1.9)
                defense_range = (1.1, 1.5)
            elif league == "Serie A":
                base_xg_range = (1.3, 1.7)
                defense_range = (1.0, 1.4)
            elif league == "Ligue 1":
                base_xg_range = (1.2, 1.6)
                defense_range = (0.9, 1.3)
            elif league == "Champions League":
                base_xg_range = (1.4, 1.9)
                defense_range = (0.9, 1.3)
            else:
                base_xg_range = (1.2, 1.6)
                defense_range = (1.0, 1.4)
            
            for team_name in teams:
                team_data = TeamData(
                    name=team_name,
                    league=league,
                    players=self._generate_players(team_name),
                    tactical_style=random.choice(["Posesión", "Contragolpe", "Equilibrado", "Presión alta"]),
                    avg_xg_season=round(random.uniform(*base_xg_range), 2),
                    avg_xg_conceded_season=round(random.uniform(*defense_range), 2)
                )
                
                self._teams_db[team_name] = team_data
                logger.debug(f"Equipo registrado: {team_name} ({league})")
        
        # Log resumen por liga
        for league in OFFICIAL_TEAMS.keys():
            count = len([t for t in self._teams_db.values() if t.league == league])
            logger.info(f"  {league}: {count} equipos")
        
        logger.info(f"Base de datos inicializada: {len(self._teams_db)} equipos en {len(OFFICIAL_TEAMS)} competiciones")
    
    def get_teams_by_league(self, league: str) -> List[str]:
        """
        Retorna lista de equipos para una liga específica con validación estricta.
        Temporada 2025/2026.
        """
        # Normalizar nombre de liga
        league_normalized = league.replace(" (España)", "").replace(" (Inglaterra)", "")\
                                  .replace(" (Alemania)", "").replace(" (Italia)", "")\
                                  .replace(" (Francia)", "").replace(" (Holanda)", "")\
                                  .replace(" (Portugal)", "").replace(" (Escocia)", "")\
                                  .replace(" (Bélgica)", "").replace(" (Austria)", "")\
                                  .replace(" (Suiza)", "").replace(" (Polonia)", "")\
                                  .replace(" (Rep. Checa)", "").replace(" (Dinamarca)", "")\
                                  .replace(" (Suecia)", "").replace(" (Noruega)", "")\
                                  .replace(" (Grecia)", "").replace(" (Croacia)", "")\
                                  .replace(" (Serbia)", "").replace(" (Ucrania)", "")\
                                  .replace(" (Israel)", "").replace(" (Argentina)", "")\
                                  .replace(" (Brasil)", "").strip()
        
        logger.info(f"Solicitando equipos para liga: '{league}' (normalizado: '{league_normalized}')")
        
        # Obtener equipos oficiales de la liga
        official_teams = OFFICIAL_TEAMS.get(league_normalized, [])
        
        if not official_teams:
            logger.error(f"Liga no encontrada en catálogo oficial: '{league_normalized}'")
            return []
        
        # Validar que todos los equipos estén en nuestra BD
        available_teams = []
        for team_name in official_teams:
            if team_name in self._teams_db:
                # Verificar que el equipo tenga la liga correcta asignada
                team_data = self._teams_db[team_name]
                if team_data.league == league_normalized:
                    available_teams.append(team_name)
                else:
                    logger.warning(f"Desajuste de liga: {team_name} está en BD como '{team_data.league}' "
                                  f"pero se solicitó '{league_normalized}'")
            else:
                logger.warning(f"Equipo oficial no encontrado en BD: {team_name}")
        
        # Ordenar alfabéticamente
        available_teams.sort()
        
        logger.info(f"Retornando {len(available_teams)} equipos para '{league_normalized}'")
        
        # Si no hay equipos disponibles, retornar lista vacía (no fallback)
        if not available_teams:
            logger.error(f"Ningún equipo disponible para '{league_normalized}'. "
                        f"Verificar inicialización de BD.")
        
        return available_teams
    
    def get_team_data(self, team_name: str) -> Optional[Team]:
        """
        Obtiene datos completos de un equipo con validación de existencia.
        """
        # Normalizar nombre
        normalized_name = self._normalize_team_name(team_name)
        
        # Buscar en BD
        if normalized_name in self._teams_db:
            team_data = self._teams_db[normalized_name]
            return Team(
                name=team_data.name,
                league=team_data.league,
                players=team_data.players,
                tactical_style=team_data.tactical_style,
                avg_xg_season=team_data.avg_xg_season,
                avg_xg_conceded_season=team_data.avg_xg_conceded_season
            )
        
        # Intentar búsqueda flexible
        for db_name, db_data in self._teams_db.items():
            if normalized_name.lower() in db_name.lower() or db_name.lower() in normalized_name.lower():
                logger.info(f"Equipo encontrado por coincidencia parcial: '{team_name}' -> '{db_name}'")
                return Team(
                    name=db_data.name,
                    league=db_data.league,
                    players=db_data.players,
                    tactical_style=db_data.tactical_style,
                    avg_xg_season=db_data.avg_xg_season,
                    avg_xg_conceded_season=db_data.avg_xg_conceded_season
                )
        
        logger.error(f"Equipo no encontrado: '{team_name}' (normalizado: '{normalized_name}')")
        return None
    
    def get_last_match_lineup(self, team_name: str) -> List[str]:
        """
        Retorna última alineación conocida con validación.
        """
        if team_name in self._last_lineups:
            return self._last_lineups[team_name]
        
        # Si no hay histórico, retornar titulares del equipo
        team = self.get_team_data(team_name)
        if team and team.players:
            titulares = [p.name for p in team.players if str(p.status) == "TITULAR"][:11]
            return titulares
        
        logger.warning(f"No se encontró alineación histórica ni plantilla para: {team_name}")
        return []
    
    def save_last_lineup(self, team_name: str, lineup: List[str]):
        """Guarda alineación para uso futuro."""
        self._last_lineups[team_name] = lineup
        logger.info(f"Alineación guardada para {team_name}: {len(lineup)} jugadores")
    
    def get_last_match_date(self, team_name: str) -> Optional[datetime]:
        """Retorna fecha del último partido registrado (simulado)."""
        # Simular último partido hace 3-7 días
        days_ago = random.randint(3, 7)
        return datetime.now() - timedelta(days=days_ago)
    
    def get_all_leagues(self) -> List[str]:
        """Retorna lista de todas las ligas disponibles."""
        return list(OFFICIAL_TEAMS.keys())
    
    def validate_database_integrity(self) -> Dict:
        """
        Valida la integridad de toda la base de datos.
        Útil para diagnóstico.
        """
        issues = []
        stats = {
            "total_teams": len(self._teams_db),
            "teams_by_league": {},
            "orphan_teams": []
        }
        
        for team_name, team_data in self._teams_db.items():
            # Contar por liga
            league = team_data.league
            stats["teams_by_league"][league] = stats["teams_by_league"].get(league, 0) + 1
            
            # Validar que la liga existe
            if league not in OFFICIAL_TEAMS:
                issues.append(f"Equipo '{team_name}' tiene liga inválida: '{league}'")
                stats["orphan_teams"].append(team_name)
                continue
            
            # Validar que el equipo está en la lista oficial de su liga
            if team_name not in OFFICIAL_TEAMS[league]:
                issues.append(f"Equipo '{team_name}' no está en lista oficial de '{league}'")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "stats": stats
        }


# Singleton para uso en toda la aplicación
_data_provider_instance: Optional[MockDataProvider] = None

def get_data_provider() -> MockDataProvider:
    """Retorna instancia singleton del proveedor de datos."""
    global _data_provider_instance
    if _data_provider_instance is None:
        _data_provider_instance = MockDataProvider()
    return _data_provider_instance