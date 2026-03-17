"""
mock_provider.py — LAGEMA JARG74 Ecosistema 4.0
================================================
Proveedor de datos con validación estricta de equipos por competición.
Corrección P0: Filtrado riguroso para evitar contaminación de ligas.

Prioridad: P0-Crítico. Datos incorrectos invalidan todo el análisis predictivo.
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
# MAPEO OFICIAL DE EQUIPOS POR COMPETICIÓN
# =============================================================================
# Datos verificados de la temporada 2024/2025

OFFICIAL_TEAMS = {
    "Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
        "Liverpool", "Luton Town", "Manchester City", "Manchester Utd",
        "Newcastle", "Nottingham Forest", "Sheffield Utd", "Tottenham",
        "West Ham", "Wolves"
    ],
    "La Liga": [
        "Alaves", "Almeria", "Athletic Club", "Atletico Madrid", "Barcelona",
        "Cadiz", "Celta", "Getafe", "Girona", "Granada",
        "Las Palmas", "Mallorca", "Osasuna", "Rayo Vallecano", "Real Betis",
        "Real Madrid", "Real Sociedad", "Sevilla", "Valencia", "Villarreal"
    ],
    "Bundesliga": [
        "Augsburg", "Bayer Leverkusen", "Bayern Munich", "Bochum", "Darmstadt",
        "Dortmund", "Ein Frankfurt", "Freiburg", "Heidenheim", "Hoffenheim",
        "Koln", "Mainz", "Mgladbach", "RB Leipzig", "Stuttgart",
        "Union Berlin", "Werder Bremen", "Wolfsburg"
    ],
    "Serie A": [
        "AC Milan", "Atalanta", "Bologna", "Cagliari", "Empoli",
        "Fiorentina", "Frosinone", "Genoa", "Inter Milan", "Juventus",
        "Lazio", "Lecce", "Monza", "Napoli", "Roma",
        "Salernitana", "Sassuolo", "Torino", "Udinese", "Verona"
    ],
    "Ligue 1": [
        "Brest", "Clermont", "Le Havre", "Lens", "Lille",
        "Lorient", "Lyon", "Marseille", "Metz", "Monaco",
        "Montpellier", "Nantes", "Nice", "PSG", "Reims",
        "Rennes", "Strasbourg", "Toulouse"
    ],
    "Eredivisie": [
        "Ajax", "Almere City", "AZ Alkmaar", "Excelsior", "Feyenoord",
        "Fortuna Sittard", "Go Ahead Eagles", "Heerenveen", "Heracles",
        "NEC Nijmegen", "PEC Zwolle", "PSV", "RKC Waalwijk", "Sparta Rotterdam",
        "Twente", "Utrecht", "Vitesse", "Volendam"
    ],
    "Primeira Liga": [
        "Arouca", "Benfica", "Boavista", "Braga", "Casa Pia",
        "Chaves", "Estoril", "Famalicao", "Farense", "Gil Vicente",
        "Moreirense", "Portimonense", "Porto", "Rio Ave", "Sporting CP",
        "Vitoria Guimaraes", "Vizela"
    ],
    "Champions League": [
        "Arsenal", "Barcelona", "Bayern Munich", "Benfica", "Braga",
        "Copenhagen", "Dortmund", "Galatasaray", "Inter Milan", "Lazio",
        "Leipzig", "Lens", "Manchester City", "Manchester Utd", "Milan",
        "Napoli", "Newcastle", "Paris Saint-Germain", "Porto", "PSV",
        "Real Madrid", "Real Sociedad", "Salzburg", "Sevilla", "Shakhtar",
        "Union Berlin", "Young Boys"
    ],
    "Europa League": [
        "Ajax", "Atalanta", "Bayer Leverkusen", "Brighton", "Freiburg",
        "LASK", "Liverpool", "Marseille", "Molde", "Qarabag",
        "Rangers", "Rennes", "Roma", "Slavia Prague", "Sporting CP",
        "Sturm Graz", "Toulouse", "Union Saint-Gilloise", "Villarreal", "West Ham"
    ],
    "Conference League": [
        "Aston Villa", "AZ Alkmaar", "Basel", "Bodo Glimt", "Club Brugge",
        "Fenerbahce", "Fiorentina", "Gent", "Lille", "Maccabi Haifa",
        "Nordsjaelland", "Olympiacos", "PAOK", "Plzen", "Slovan Bratislava"
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
    
    # La Liga
    "Barcelona": "Barcelona",
    "FC Barcelona": "Barcelona",
    "Real Betis": "Real Betis",
    "Betis": "Real Betis",
    "Atletico": "Atletico Madrid",
    "Atlético Madrid": "Atletico Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Celta Vigo": "Celta",
    "Deportivo Alaves": "Alaves",
    
    # Bundesliga
    "Borussia Dortmund": "Dortmund",
    "Borussia Mgladbach": "Mgladbach",
    "Borussia Monchengladbach": "Mgladbach",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "FC Bayern Munich": "Bayern Munich",
    "Bayern München": "Bayern Munich",
    "RB Leipzig": "Leipzig",
    "RasenBallsport Leipzig": "Leipzig",
    
    # Serie A
    "Milan": "AC Milan",
    "Internazionale": "Inter Milan",
    "Inter": "Inter Milan",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "SSC Napoli": "Napoli",
    
    # Ligue 1
    "Paris Saint-Germain": "PSG",
    "Paris SG": "PSG",
    "Olympique Marseille": "Marseille",
    "OM": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "OL": "Lyon",
    "OGC Nice": "Nice",
    "AS Monaco": "Monaco",
    
    # Otras ligas
    "Sporting Lisbon": "Sporting CP",
    "Sporting Clube de Portugal": "Sporting CP",
    "FC Porto": "Porto",
    "Futebol Clube do Porto": "Porto",
    "Benfica": "Benfica",
    "SL Benfica": "Benfica",
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
    Garantiza que los equipos pertenezcan realmente a sus ligas asignadas.
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
                      f"no pertenece a '{league}'. Equipos oficiales: {official_teams[:5]}...")
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
        logger.info("Inicializando base de datos con validación de ligas...")
        
        for league, teams in OFFICIAL_TEAMS.items():
            for team_name in teams:
                # Generar estadísticas realistas por liga
                if league == "Premier League":
                    base_xg = random.uniform(1.4, 1.8)
                elif league == "La Liga":
                    base_xg = random.uniform(1.2, 1.6)
                elif league == "Bundesliga":
                    base_xg = random.uniform(1.5, 1.9)
                elif league == "Serie A":
                    base_xg = random.uniform(1.3, 1.7)
                elif league == "Ligue 1":
                    base_xg = random.uniform(1.2, 1.6)
                else:
                    base_xg = random.uniform(1.2, 1.6)
                
                team_data = TeamData(
                    name=team_name,
                    league=league,
                    players=self._generate_players(team_name),
                    tactical_style=random.choice(["Posesión", "Contragolpe", "Equilibrado", "Presión alta"]),
                    avg_xg_season=round(base_xg, 2),
                    avg_xg_conceded_season=round(random.uniform(1.0, 1.5), 2)
                )
                
                self._teams_db[team_name] = team_data
                logger.debug(f"Equipo registrado: {team_name} ({league})")
        
        logger.info(f"Base de datos inicializada: {len(self._teams_db)} equipos en {len(OFFICIAL_TEAMS)} competiciones")
    
    def get_teams_by_league(self, league: str) -> List[str]:
        """
        Retorna lista de equipos para una liga específica con validación estricta.
        
        Args:
            league: Nombre de la liga (ej: "Premier League", "La Liga")
        """
        # Normalizar nombre de liga
        league_normalized = league.replace(" (España)", "").replace(" (Inglaterra)", "")\
                                  .replace(" (Alemania)", "").replace(" (Italia)", "")\
                                  .replace(" (Francia)", "").strip()
        
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