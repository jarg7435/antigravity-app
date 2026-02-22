from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class PlayerPosition(str, Enum):
    GOALKEEPER = "Portero"
    DEFENDER = "Defensa"
    MIDFIELDER = "Centrocampista"
    FORWARD = "Delantero"
    MANAGER = "Entrenador"

class PlayerStatus(str, Enum):
    TITULAR = "Titular"
    DUDA = "Duda"
    BAJA = "Baja"
    SUPLENTE = "Suplente"

class NodeRole(str, Enum):
    FINALIZER = "Finalizador" # Delanteros/Extremos
    CREATOR = "Creador"       # Mediocentros ofensivos
    DEFENSIVE = "Defensivo"   # Centrales/Pivotes
    KEEPER = "Portero"        # Portero
    TACTICAL = "Tactico"      # Entrenador
    NONE = "Ninguno"

class Player(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    id: str
    name: str
    team_name: str
    position: PlayerPosition
    node_role: NodeRole = NodeRole.NONE
    status: PlayerStatus = PlayerStatus.TITULAR
    
    # Advanced Metrics (Wyscout/Opta)
    rating_last_5: float = Field(7.0, ge=0, le=10)
    xg_last_5: float = 0.0
    xa_last_5: float = 0.0
    ppda: float = 0.0
    aerial_duels_won_pct: float = 0.0
    progressive_passes: int = 0
    tracking_km_avg: float = 0.0

class Team(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    name: str
    league: str
    players: List[Player] = []
    tactical_style: str = "Equilibrado"
    
    # Advanced Team Metrics
    avg_xg_season: float = 0.0
    avg_xg_conceded_season: float = 0.0
    avg_possession: float = 50.0
    form_last_5: List[str] = []
    motivation_level: float = 1.0

class MatchConditions(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    temperature: float = 20.0
    rain_mm: float = 0.0
    wind_kmh: float = 10.0
    humidity_percent: float = 50.0
    pitch_quality: str = "Bueno" # Bueno, Medio, Malo

class RefereeStrictness(str, Enum):
    HIGH = "Alto (Riguroso)"    # Many cards
    MEDIUM = "Medio (Equilibrado)" 
    LOW = "Bajo (Permisivo)"   # Few cards

class Referee(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    name: str = "Árbitro Desconocido"
    strictness: RefereeStrictness = RefereeStrictness.MEDIUM
    avg_cards: float = 4.5

class Match(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    id: str
    home_team: Any # Flexible type for Team model
    away_team: Any # Flexible type for Team model
    date: Any # Can be datetime or date, handles Pydantic v2 quirks
    kickoff_time: str = "21:00"
    competition: str = "Unknown"
    conditions: Optional[Any] = None
    referee: Optional[Any] = None
    lineup_confirmed: bool = False
    referee_confirmed: bool = False
    
    # Professional Integration
    wyscout_id: Optional[str] = None
    opta_id: Optional[str] = None
    market_odds: Dict[str, float] = {} # e.g. {"1": 1.95, "X": 3.40, "2": 4.10}

class PredictionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    match_id: str
    bpa_home: float
    bpa_away: float
    
    # ML & Statistical Probabilities
    win_prob_home: float
    draw_prob: float
    win_prob_away: float
    
    # Poisson Matrix (Simplified for storage)
    poisson_matrix: Dict[str, float] = {} # e.g. {"1-0": 0.12, "2-0": 0.08}
    
    total_goals_expected: float
    both_teams_to_score_prob: float
    score_prediction: str = "0-0"
    
    # Value Search
    value_opportunities: List[Dict] = [] # [{"market": "1", "value": 0.05, "roi": 0.12}]
    
    # Comprehensive Markets
    predicted_cards: str = "0-0"
    predicted_corners: str = "0-0"
    predicted_shots: str = "0-0"
    predicted_shots_on_target: str = "0-0"
    
    confidence_score: float = 0.0 # 0-1 metrics
    external_analysis_summary: str = ""
    referee_name: str = "Autodetectado"

class MatchOutcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")
    
    match_id: str
    home_score: int
    away_score: int
    home_corners: int
    away_corners: int
    home_cards: int
    away_cards: int
    home_shots: int
    away_shots: int
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    actual_winner: str # "LOCAL", "VISITANTE", "EMPATE"
