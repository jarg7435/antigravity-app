"""
APIManager — Orquestador de APIs REALES para LAGEMA JARG74
==========================================================
VERSIÓN 5.1 — Correcciones basadas en test real

CORRECCIONES v5.1:
  - API-Football: Soporta Direct (v3.api-football.com) y RapidAPI
    Auto-detecta y prueba ambos modos
  - Sportmonks: Corregido — search endpoints usan query parameter correcto
    No se puede pasar ID a endpoints de search
  - football-data.org: Árbitros disponibles en partidos FINALIZADOS
  - Singleton APIManager para reutilizar conexión
  - Logging mejorado para diagnóstico

Uso:
  from src.data.api_manager import get_api_manager
  api = get_api_manager()
  fixtures = api.get_fixtures_for_date("2026-05-12", league_name="La Liga")
"""

import os
import time
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("LAGEMA_API")
logging.basicConfig(level=logging.INFO)


class RateLimiter:
    """Controla las llamadas por minuto a cada API."""

    def __init__(self, calls_per_minute: int = 30):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    def wait_if_needed(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0]) + 0.1
            if sleep_time > 0:
                logger.info(f"[RateLimiter] Esperando {sleep_time:.1f}s...")
                time.sleep(sleep_time)
        self.calls.append(time.time())


def _detect_api_key_type(api_key: str) -> str:
    """
    Auto-detecta el tipo de API key de API-Football.
    
    Retorna:
      "rapidapi"  — Clave de RapidAPI (contiene 'ms' y 'jsn')
      "direct"    — Clave directa de api-football.com (32 chars hex)
      "unknown"   — No se pudo determinar
    """
    if not api_key:
        return "unknown"
    
    key = api_key.strip()
    
    # RapidAPI keys tienen formato: XXXXmsXXXXjsnXXXX
    if "ms" in key and "jsn" in key:
        return "rapidapi"
    
    # Direct keys son hexadecimales de 32 caracteres
    if re.match(r'^[a-f0-9]{32}$', key, re.IGNORECASE):
        return "direct"
    
    # Si tiene 30+ chars y parece hex, probablemente direct
    if len(key) >= 30 and re.match(r'^[a-f0-9]+$', key, re.IGNORECASE):
        return "direct"
    
    return "unknown"


class APIFootballClient:
    """
    Cliente para API-Football — AUTO-DETECTA formato de key.
    
    Soporta 2 configuraciones:
      1. RapidAPI: api-football-v1.p.rapidapi.com + X-RapidAPI-Key
      2. Direct (v3): v3.api-football.com + x-apisports-key
    
    Prueba automáticamente ambos modos y usa el que funciona.
    """

    # Mapping de ligas principales
    LEAGUE_IDS = {
        "La Liga": 140,
        "Premier League": 39,
        "Bundesliga": 78,
        "Serie A": 135,
        "Ligue 1": 61,
        "Champions League": 2,
        "Europa League": 3,
        "Conference League": 848,
        "Copa Libertadores": 13,
        "Copa Sudamericana": 14,
        "Eredivisie": 88,
        "Primeira Liga": 94,
        "Süper Lig": 203,
        "Scottish Premiership": 179,
        "Belgian Pro League": 144,
        "Segunda División": 141,
        "Championship": 40,
        "Bundesliga 2": 79,
        "Serie B": 136,
        "Ligue 2": 62,
    }

    LEAGUE_NAME_BY_ID = {v: k for k, v in LEAGUE_IDS.items()}

    # Configuraciones de conexión para cada modo
    MODES = {
        "rapidapi": {
            "base_url": "https://api-football-v1.p.rapidapi.com/v3",
            "headers": lambda key: {
                "X-RapidAPI-Key": key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
            }
        },
        "direct": {
            "base_url": "https://v3.api-football.com",
            "headers": lambda key: {
                "x-apisports-key": key
            }
        }
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("API_FOOTBALL_KEY", "")
        if not self.api_key:
            logger.warning("[API-Football] Sin API key configurada")
        
        self.rate_limiter = RateLimiter(calls_per_minute=28)
        self.detected_type = _detect_api_key_type(self.api_key)
        self.session = requests.Session()
        
        # Estado de probe
        self._probed = False
        self._working_mode = None  # 'rapidapi' or 'direct'
        self._working_base_url = None
        self._working_headers = None
        
        # Configurar modo inicial (el detectado)
        self._apply_mode(self.detected_type if self.detected_type != "unknown" else "rapidapi")
        
        logger.info(f"[API-Football] Key detectada como: {self.detected_type} (...{self.api_key[-8:]})")

    def _apply_mode(self, mode: str):
        """Aplica una configuración de conexión."""
        config = self.MODES.get(mode)
        if config:
            self._current_mode = mode
            self._current_base_url = config["base_url"]
            self._current_headers = config["headers"](self.api_key)

    def _probe_connection(self) -> str:
        """
        Prueba la conexión en ambos modos y determina cuál funciona.
        Retorna el modo que funciona: 'rapidapi' o 'direct' o 'failed'
        """
        if self._probed and self._working_mode:
            return self._working_mode
            
        logger.info("[API-Football] Probando conexión...")
        
        # Orden de prueba: primero el detectado, luego el alternativo
        modes_to_try = []
        if self.detected_type in ("rapidapi", "unknown"):
            modes_to_try = ["rapidapi", "direct"]
        elif self.detected_type == "direct":
            modes_to_try = ["direct", "rapidapi"]
        else:
            modes_to_try = ["rapidapi", "direct"]
        
        for mode in modes_to_try:
            config = self.MODES[mode]
            base_url = config["base_url"]
            headers = config["headers"](self.api_key)
            
            try:
                logger.info(f"[API-Football] Probando modo {mode}: {base_url}")
                resp = requests.get(
                    f"{base_url}/status",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    req = data.get("response", {}).get("requests", {})
                    account = data.get("response", {}).get("account", {})
                    current = req.get("current", "?")
                    limit = req.get("limit_day", "?")
                    
                    logger.info(f"[API-Football] ✅ CONECTADO en modo {mode} — "
                              f"Account: {account.get('firstname','?')}, "
                              f"Requests: {current}/{limit}")
                    
                    self._working_mode = mode
                    self._working_base_url = base_url
                    self._working_headers = headers
                    
                    # Actualizar sesión
                    self.session.headers.clear()
                    for k, v in headers.items():
                        self.session.headers[k] = v
                    
                    self._probed = True
                    return self._working_mode
                elif resp.status_code in (401, 403):
                    logger.warning(f"[API-Football] Modo {mode}: AUTH ERROR ({resp.status_code})")
                else:
                    logger.warning(f"[API-Football] Modo {mode}: HTTP {resp.status_code}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[API-Football] Modo {mode}: Sin conexión — {str(e)[:80]}")
            except Exception as e:
                logger.warning(f"[API-Football] Modo {mode}: Error — {str(e)[:80]}")
        
        logger.error("[API-Football] ❌ No se pudo conectar en NINGÚN modo")
        self._probed = True
        self._working_mode = "failed"
        return "failed"

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Petición GET con rate limiting, probe automático y manejo de errores."""
        self.rate_limiter.wait_if_needed()
        
        # Probe en la primera petición
        if not self._probed:
            mode = self._probe_connection()
            if mode == "failed":
                return None
        
        base_url = self._working_base_url or self._current_base_url
        url = f"{base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", 0)
                logger.info(f"[API-Football] {endpoint} -> {results} resultados")
                return data
            elif response.status_code in (401, 403):
                logger.error(f"[API-Football] ❌ AUTH ERROR {response.status_code}")
                # Re-probar con modo alternativo
                if self._working_mode != "failed":
                    old_mode = self._working_mode
                    self._probed = False
                    new_mode = self._probe_connection()
                    if new_mode != "failed" and new_mode != old_mode:
                        return self._get(endpoint, params)
                return None
            elif response.status_code == 429:
                logger.warning("[API-Football] Rate limit alcanzado, esperando 60s...")
                time.sleep(60)
                return self._get(endpoint, params)
            else:
                logger.error(f"[API-Football] Error {response.status_code}: {response.text[:200]}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"[API-Football] Timeout en {endpoint}")
            return None
        except Exception as e:
            logger.error(f"[API-Football] Error: {e}")
            return None

    # =========================================================================
    # FIXTURES (Partidos)
    # =========================================================================

    def get_fixtures(self, date: str = None, league_id: int = None,
                     season: int = None, team_id: int = None,
                     live: str = None, fixture_id: int = None) -> List[dict]:
        """Obtiene partidos por fecha, liga, equipo o en vivo."""
        params = {}
        if date: params["date"] = date
        if league_id: params["league"] = league_id
        if season: params["season"] = season
        if team_id: params["team"] = team_id
        if live: params["live"] = live
        if fixture_id: params["id"] = fixture_id

        if league_id and not season:
            now = datetime.now()
            params["season"] = now.year if now.month >= 8 else now.year - 1

        data = self._get("fixtures", params)
        if not data:
            return []
        return data.get("response", [])

    def get_fixture_by_id(self, fixture_id: int) -> Optional[dict]:
        """Obtiene un partido específico por su ID."""
        fixtures = self.get_fixtures(fixture_id=fixture_id)
        return fixtures[0] if fixtures else None

    def get_head_to_head(self, team1_id: int, team2_id: int,
                         last: int = 10) -> List[dict]:
        """Obtiene historial de enfrentamientos directos."""
        params = {"h2h": f"{team1_id}-{team2_id}", "last": last}
        data = self._get("fixtures/headtohead", params)
        if not data:
            return []
        return data.get("response", [])

    # =========================================================================
    # EQUIPOS Y ESTADÍSTICAS
    # =========================================================================

    def get_team_info(self, team_id: int) -> Optional[dict]:
        """Información detallada de un equipo."""
        data = self._get("teams", {"id": team_id})
        if data and data.get("response"):
            return data["response"][0]
        return None

    def get_team_statistics(self, team_id: int, league_id: int,
                            season: int = None) -> Optional[dict]:
        """Estadísticas completas de un equipo en una liga/temporada."""
        if not season:
            now = datetime.now()
            season = now.year if now.month >= 8 else now.year - 1
        data = self._get("teams/statistics", {
            "team": team_id, "league": league_id, "season": season
        })
        if data:
            return data.get("response", {})
        return None

    def get_team_form(self, team_id: int, league_id: int,
                      season: int = None) -> List[str]:
        """Obtiene la forma reciente del equipo (W/D/L)."""
        stats = self.get_team_statistics(team_id, league_id, season)
        if stats:
            form_str = stats.get("form", "")
            return list(form_str) if form_str else []
        return []

    def search_team(self, name: str) -> List[dict]:
        """Busca equipos por nombre."""
        data = self._get("teams", {"search": name})
        return data.get("response", []) if data else []

    # =========================================================================
    # ALINEACIONES
    # =========================================================================

    def get_lineups(self, fixture_id: int) -> List[dict]:
        """Alineaciones confirmadas de un partido."""
        data = self._get("fixtures/lineups", {"fixture": fixture_id})
        return data.get("response", []) if data else []

    # =========================================================================
    # ÁRBITROS
    # =========================================================================

    def get_referees(self, league_id: int = None, season: int = None) -> List[dict]:
        """Lista de árbitros disponibles."""
        params = {}
        if league_id: params["league"] = league_id
        if season: params["season"] = season
        data = self._get("referees", params)
        return data.get("response", []) if data else []

    # =========================================================================
    # ESTADÍSTICAS DE PARTIDO
    # =========================================================================

    def get_fixture_stats(self, fixture_id: int) -> List[dict]:
        """Estadísticas en tiempo real de un partido."""
        data = self._get("fixtures/statistics", {"fixture": fixture_id})
        return data.get("response", []) if data else []

    def get_fixture_events(self, fixture_id: int) -> List[dict]:
        """Eventos del partido (goles, tarjetas, sustituciones)."""
        data = self._get("fixtures/events", {"fixture": fixture_id})
        return data.get("response", []) if data else []

    # =========================================================================
    # JUGADORES LESIONADOS
    # =========================================================================

    def get_injuries(self, team_id: int = None, league_id: int = None,
                     season: int = None) -> List[dict]:
        """Lista de jugadores lesionados o dudosos."""
        params = {}
        if team_id: params["team"] = team_id
        if league_id: params["league"] = league_id
        if season: params["season"] = season
        data = self._get("injuries", params)
        return data.get("response", []) if data else []

    # =========================================================================
    # CLASIFICACIÓN
    # =========================================================================

    def get_standings(self, league_id: int, season: int = None) -> List[dict]:
        """Tabla de clasificación de una liga."""
        if not season:
            now = datetime.now()
            season = now.year if now.month >= 8 else now.year - 1
        data = self._get("standings", {"league": league_id, "season": season})
        return data.get("response", []) if data else []

    # =========================================================================
    # PREDICCIONES
    # =========================================================================

    def get_predictions(self, fixture_id: int) -> Optional[dict]:
        """Predicciones de API-Football para comparar con nuestro modelo."""
        data = self._get("predictions", {"fixture": fixture_id})
        if data and data.get("response"):
            return data["response"][0]
        return None

    # =========================================================================
    # RESULTADOS EN VIVO
    # =========================================================================

    def get_live_fixtures(self, league_ids: List[int] = None) -> List[dict]:
        """Partidos en vivo actualmente."""
        if league_ids:
            live_str = "-".join(str(lid) for lid in league_ids)
            return self.get_fixtures(live=live_str)
        data = self._get("fixtures", {"live": "all"})
        return data.get("response", []) if data else []


class SportmonksClient:
    """
    Cliente para Sportmonks Football API.
    
    NOTA IMPORTANTE: Los endpoints de search en Sportmonks v3 usan 
    parámetros de query diferentes. Para buscar por nombre se usa
    el endpoint /search con query parameter.
    
    Documentación: https://docs.sportmonks.com/football/
    """

    BASE_URL = "https://api.sportmonks.com/v3/football"

    def __init__(self, api_token: str = None):
        self.api_token = api_token or os.environ.get("SPORTMONKS_API_TOKEN", "")
        if not self.api_token:
            logger.warning("[Sportmonks] Sin API token configurado")
        self.rate_limiter = RateLimiter(calls_per_minute=28)
        self.session = requests.Session()

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        self.rate_limiter.wait_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params["api_token"] = self.api_token
        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get("data", data)
            elif response.status_code == 429:
                logger.warning("[Sportmonks] Rate limit, esperando...")
                time.sleep(60)
                return self._get(endpoint, params)
            else:
                logger.error(f"[Sportmonks] Error {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"[Sportmonks] Error: {e}")
            return None

    def get_team_by_name(self, name: str) -> Optional[dict]:
        """
        Busca un equipo por nombre.
        Usa /teams/search/{name} — el nombre va en la URL, no como query param.
        """
        # Codificar nombre para URL
        encoded_name = requests.utils.quote(name)
        data = self._get(f"teams/search/{encoded_name}")
        if isinstance(data, list) and data:
            return data[0]
        return None

    def get_team_by_id(self, team_id: int) -> Optional[dict]:
        """Obtiene equipo por ID."""
        return self._get(f"teams/{team_id}")

    def get_team_season_stats(self, team_id: int, season_id: int) -> Optional[dict]:
        """Estadísticas de equipo en una temporada."""
        return self._get(f"teams/{team_id}/seasons/{season_id}")

    def get_player_by_name(self, name: str) -> Optional[dict]:
        """Busca un jugador por nombre."""
        encoded_name = requests.utils.quote(name)
        data = self._get(f"players/search/{encoded_name}")
        if isinstance(data, list) and data:
            return data[0]
        return None

    def get_season_standings(self, season_id: int) -> List[dict]:
        """Clasificación de una temporada."""
        data = self._get(f"standings/seasons/{season_id}")
        return data if isinstance(data, list) else []

    def get_referee_by_name(self, name: str) -> Optional[dict]:
        """
        Busca árbitro por nombre.
        Usa /referees/search/{name} — el nombre va en la URL.
        """
        encoded_name = requests.utils.quote(name)
        data = self._get(f"referees/search/{encoded_name}")
        if isinstance(data, list) and data:
            return data[0]
        return None
    
    def get_fixture_by_id(self, fixture_id: int) -> Optional[dict]:
        """Obtiene detalles de un fixture con include de árbitro."""
        return self._get(f"fixtures/{fixture_id}", {"include": "referee"})
    
    def get_fixtures_between(self, date_from: str, date_to: str,
                              league_id: int = None) -> List[dict]:
        """Obtiene fixtures entre fechas."""
        params = {}
        if league_id:
            params["filters"] = f"leagueIds:{league_id}"
        data = self._get(f"fixtures/between/{date_from}/{date_to}", params)
        return data if isinstance(data, list) else []


class FootballDataClient:
    """
    Cliente para football-data.org API.
    
    NOTA IMPORTANTE: Los árbitros solo están disponibles en partidos
    FINALIZADOS (status=FINISHED). Para próximos partidos, usar
    API-Football o Sportmonks.
    
    Documentación: https://www.football-data.org/documentation/api
    """

    BASE_URL = "https://api.football-data.org/v4"

    COMPETITION_IDS = {
        "PD": "La Liga",
        "PL": "Premier League",
        "BL1": "Bundesliga",
        "SA": "Serie A",
        "FL1": "Ligue 1",
        "CL": "Champions League",
        "EL": "Europa League",
        "EC": "Conference League",
        "DED": "Eredivisie",
        "PPL": "Primeira Liga",
        "BSA": "Serie A Brasil",
        "WC": "World Cup",
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY", "")
        if not self.api_key:
            logger.warning("[football-data.org] Sin API key configurada")
        self.rate_limiter = RateLimiter(calls_per_minute=9)
        self.session = requests.Session()
        self.session.headers.update({
            "X-Auth-Token": self.api_key
        })

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        self.rate_limiter.wait_if_needed()
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("[football-data.org] Rate limit, esperando 60s...")
                time.sleep(60)
                return self._get(endpoint, params)
            else:
                logger.error(f"[football-data.org] Error {response.status_code}: {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"[football-data.org] Error: {e}")
            return None

    def get_competition_matches(self, competition_code: str,
                                 date_from: str = None,
                                 date_to: str = None,
                                 matchday: int = None,
                                 status: str = None) -> List[dict]:
        """
        Partidos de una competición.
        
        Args:
            competition_code: "PD", "PL", "BL1", "SA", "FL1", "CL", etc.
            date_from: "YYYY-MM-DD"
            date_to: "YYYY-MM-DD"
            matchday: Jornada específica
            status: Filtrar por estado ("FINISHED", "SCHEDULED", etc.)
        """
        params = {}
        if date_from: params["dateFrom"] = date_from
        if date_to: params["dateTo"] = date_to
        if matchday: params["matchday"] = matchday
        if status: params["status"] = status
        data = self._get(f"competitions/{competition_code}/matches", params)
        if data:
            return data.get("matches", [])
        return []

    def get_match(self, match_id: int) -> Optional[dict]:
        """Detalle de un partido específico."""
        return self._get(f"matches/{match_id}")

    def get_team_matches(self, team_id: int,
                          date_from: str = None,
                          date_to: str = None) -> List[dict]:
        """Partidos de un equipo en un rango de fechas."""
        params = {}
        if date_from: params["dateFrom"] = date_from
        if date_to: params["dateTo"] = date_to
        data = self._get(f"teams/{team_id}/matches", params)
        if data:
            return data.get("matches", [])
        return []

    def get_standings(self, competition_code: str) -> List[dict]:
        """Clasificación de una competición."""
        data = self._get(f"competitions/{competition_code}/standings")
        if data:
            return data.get("standings", [])
        return []

    def get_team(self, team_id: int) -> Optional[dict]:
        """Información de un equipo."""
        return self._get(f"teams/{team_id}")
    
    def get_finished_matches_with_referees(self, competition_code: str,
                                            limit: int = 10) -> List[dict]:
        """
        Obtiene partidos FINALIZADOS que tienen árbitros asignados.
        Útil para obtener datos de árbitros históricos.
        """
        data = self._get(f"competitions/{competition_code}/matches", 
                        {"status": "FINISHED", "limit": limit})
        if data:
            matches = data.get("matches", [])
            return [m for m in matches if m.get("referees")]
        return []


# =============================================================================
# SINGLETON — Evita crear múltiples instancias de APIManager
# =============================================================================

_api_manager_instance = None

def get_api_manager() -> "APIManager":
    """Retorna la instancia singleton de APIManager."""
    global _api_manager_instance
    if _api_manager_instance is None:
        _api_manager_instance = APIManager()
    return _api_manager_instance


class APIManager:
    """
    Orquestador central de todas las APIs.
    Implementa cascada de fuentes con fallback automático.
    
    Estrategia:
      - API-Football: fuente primaria (datos más completos)
      - Sportmonks: enriquecimiento (datos de jugadores, estadísticas avanzadas)
      - football-data.org: backup y competiciones europeas
    """

    def __init__(self):
        self.api_football = APIFootballClient()
        self.sportmonks = SportmonksClient()
        self.football_data = FootballDataClient()
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300

    def _cache_key(self, method: str, **kwargs) -> str:
        return f"{method}:" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["ts"] < self._cache_ttl:
                return entry["data"]
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: Any):
        self._cache[key] = {"ts": time.time(), "data": data}

    # =========================================================================
    # MÉTODOS PRINCIPALES
    # =========================================================================

    def get_fixtures_for_date(self, date: str,
                               league_name: str = None) -> List[dict]:
        """Obtiene todos los partidos de una fecha."""
        cache_key = self._cache_key("fixtures", date=date, league=league_name)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        results = []

        # 1. Intentar API-Football
        league_id = APIFootballClient.LEAGUE_IDS.get(league_name) if league_name else None
        fixtures = self.api_football.get_fixtures(date=date, league_id=league_id)

        if fixtures:
            for f in fixtures:
                league_info = f.get("league", {})
                home = f.get("teams", {}).get("home", {})
                away = f.get("teams", {}).get("away", {})
                goals = f.get("goals", {})
                score = f.get("score", {})

                results.append({
                    "fixture_id": f.get("fixture", {}).get("id"),
                    "date": f.get("fixture", {}).get("date", ""),
                    "league": league_info.get("name", ""),
                    "league_id": league_info.get("id"),
                    "league_country": league_info.get("country", ""),
                    "home_team": home.get("name", ""),
                    "away_team": away.get("name", ""),
                    "home_team_id": home.get("id"),
                    "away_team_id": away.get("id"),
                    "home_logo": home.get("logo", ""),
                    "away_logo": away.get("logo", ""),
                    "status": f.get("fixture", {}).get("status", {}).get("short", ""),
                    "home_score": goals.get("home"),
                    "away_score": goals.get("away"),
                    "ht_score": score.get("halftime", {}),
                    "ft_score": score.get("fulltime", {}),
                    "referee": f.get("fixture", {}).get("referee", ""),
                    "venue": f.get("fixture", {}).get("venue", {}).get("name", ""),
                    "source": "api-football"
                })
            self._set_cached(cache_key, results)
            return results

        # 2. Fallback a football-data.org
        if league_name:
            comp_code = self._get_competition_code(league_name)
            if comp_code:
                matches = self.football_data.get_competition_matches(
                    comp_code, date_from=date, date_to=date
                )
                for m in matches:
                    results.append(self._normalize_fd_match(m))
                if results:
                    self._set_cached(cache_key, results)
                    return results

        # 3. Último intento: football-data.org todas las competiciones
        for comp_code in ["PD", "PL", "BL1", "SA", "FL1"]:
            matches = self.football_data.get_competition_matches(
                comp_code, date_from=date, date_to=date
            )
            for m in matches:
                results.append(self._normalize_fd_match(m))

        self._set_cached(cache_key, results)
        return results

    def get_team_stats(self, team_name: str, league_name: str,
                        season: int = None) -> Optional[dict]:
        """Estadísticas completas de un equipo en una liga."""
        cache_key = self._cache_key("team_stats", team=team_name,
                                      league=league_name, season=season)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        teams = self.api_football.search_team(team_name)
        if not teams:
            sm_team = self.sportmonks.get_team_by_name(team_name)
            if sm_team:
                teams = [{"team": sm_team}]

        if not teams:
            return None

        team_id = teams[0].get("team", teams[0]).get("id")
        league_id = APIFootballClient.LEAGUE_IDS.get(league_name)

        if not league_id:
            return None

        stats = self.api_football.get_team_statistics(team_id, league_id, season)
        if stats:
            normalized = self._normalize_team_stats(stats, team_name)
            self._set_cached(cache_key, normalized)
            return normalized

        return None

    def get_match_result(self, fixture_id: int = None,
                          home_team: str = None, away_team: str = None,
                          date: str = None) -> Optional[dict]:
        """Obtiene el resultado REAL de un partido finalizado."""
        if fixture_id:
            fixture = self.api_football.get_fixture_by_id(fixture_id)
        elif home_team and away_team and date:
            fixtures = self.api_football.get_fixtures(date=date)
            fixture = None
            for f in fixtures:
                ht = f.get("teams", {}).get("home", {}).get("name", "")
                at = f.get("teams", {}).get("away", {}).get("name", "")
                if (home_team.lower() in ht.lower() or 
                    away_team.lower() in at.lower()):
                    fixture = f
                    break
        else:
            return None

        if not fixture:
            return None

        goals = fixture.get("goals", {})
        home_score = goals.get("home")
        away_score = goals.get("away")

        if home_score is None:
            return None

        winner = "EMPATE"
        if home_score > away_score:
            winner = "LOCAL"
        elif away_score > home_score:
            winner = "VISITANTE"

        fid = fixture.get("fixture", {}).get("id", 0)
        stats_data = self.api_football.get_fixture_stats(fid)
        events = self.api_football.get_fixture_events(fid)

        match_stats = self._parse_match_stats(stats_data, events)

        return {
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
            "stats": match_stats,
            "events": events[:20] if events else [],
            "source": "api-football"
        }

    def get_h2h(self, team1_name: str, team2_name: str,
                last: int = 10) -> List[dict]:
        """Historial de enfrentamientos directos."""
        teams1 = self.api_football.search_team(team1_name)
        teams2 = self.api_football.search_team(team2_name)

        if not teams1 or not teams2:
            return []

        id1 = teams1[0].get("team", teams1[0]).get("id")
        id2 = teams2[0].get("team", teams2[0]).get("id")

        if not id1 or not id2:
            return []

        h2h = self.api_football.get_head_to_head(id1, id2, last)
        results = []

        for match in h2h:
            goals = match.get("goals", {})
            results.append({
                "date": match.get("fixture", {}).get("date", ""),
                "home_team": match.get("teams", {}).get("home", {}).get("name", ""),
                "away_team": match.get("teams", {}).get("away", {}).get("name", ""),
                "home_score": goals.get("home"),
                "away_score": goals.get("away"),
                "league": match.get("league", {}).get("name", ""),
            })

        return results

    def get_lineups_real(self, fixture_id: int) -> Optional[dict]:
        """Alineaciones confirmadas de un partido."""
        lineups = self.api_football.get_lineups(fixture_id)
        if not lineups:
            return None

        result = {"home": {}, "away": {}, "confirmed": False}

        for idx, lineup in enumerate(lineups):
            team = lineup.get("team", {}).get("name", "")
            formation = lineup.get("formation", "")
            start_xi = [p.get("player", {}).get("name", "") 
                        for p in lineup.get("startXI", [])]
            subs = [p.get("player", {}).get("name", "") 
                    for p in lineup.get("substitutes", [])]

            side = "home" if idx == 0 else "away"

            result[side] = {
                "team": team,
                "formation": formation,
                "start_xi": start_xi,
                "substitutes": subs
            }
            result["confirmed"] = True

        result["source"] = "api-football"
        return result

    def get_injured_players(self, team_name: str = None,
                             league_name: str = None) -> List[dict]:
        """Jugadores lesionados o dudosos."""
        league_id = APIFootballClient.LEAGUE_IDS.get(league_name) if league_name else None
        team_id = None

        if team_name:
            teams = self.api_football.search_team(team_name)
            if teams:
                team_id = teams[0].get("team", teams[0]).get("id")

        injuries = self.api_football.get_injuries(
            team_id=team_id, league_id=league_id
        )

        results = []
        for inj in injuries[:30]:
            player = inj.get("player", {})
            team = inj.get("team", {})
            results.append({
                "player_name": player.get("name", ""),
                "player_id": player.get("id"),
                "team": team.get("name", ""),
                "reason": inj.get("player", {}).get("reason", ""),
                "type": inj.get("player", {}).get("type", ""),
            })

        return results

    def get_referee_data(self, referee_name: str) -> Optional[dict]:
        """Datos de un árbitro desde APIs."""
        # Intentar Sportmonks primero
        ref = self.sportmonks.get_referee_by_name(referee_name)
        if ref:
            return {
                "name": ref.get("name", referee_name),
                "common_name": ref.get("common_name", ""),
                "nationality": ref.get("nationality", ""),
                "birth_date": ref.get("birth_date", ""),
                "games": ref.get("games", 0),
                "cards": ref.get("cards", {}),
                "source": "sportmonks"
            }

        # Fallback: buscar en lista de API-Football
        referees = self.api_football.get_referees()
        for ref in referees:
            if referee_name.lower() in ref.get("name", "").lower():
                return {
                    "name": ref.get("name", referee_name),
                    "nationality": ref.get("nationality", ""),
                    "source": "api-football"
                }

        return None

    def get_standings(self, league_name: str, season: int = None) -> List[dict]:
        """Clasificación de una liga."""
        league_id = APIFootballClient.LEAGUE_IDS.get(league_name)
        if not league_id:
            return []

        standings = self.api_football.get_standings(league_id, season)
        results = []

        for entry in standings:
            for standing_group in entry.get("league", {}).get("standings", [[]]):
                if not isinstance(standing_group, list):
                    standing_group = [standing_group]
                for team_data in standing_group:
                    results.append({
                        "position": team_data.get("rank"),
                        "team": team_data.get("team", {}).get("name", ""),
                        "team_id": team_data.get("team", {}).get("id"),
                        "points": team_data.get("points"),
                        "played": team_data.get("all", {}).get("played"),
                        "won": team_data.get("all", {}).get("win"),
                        "draw": team_data.get("all", {}).get("draw"),
                        "lost": team_data.get("all", {}).get("lose"),
                        "goals_for": team_data.get("all", {}).get("goals", {}).get("for"),
                        "goals_against": team_data.get("all", {}).get("goals", {}).get("against"),
                        "form": team_data.get("form", ""),
                        "description": team_data.get("description", ""),
                    })

        return results

    # =========================================================================
    # HELPERS DE NORMALIZACIÓN
    # =========================================================================

    def _normalize_fd_match(self, match: dict) -> dict:
        """Normaliza un partido de football-data.org al formato estándar."""
        home = match.get("homeTeam", {})
        away = match.get("awayTeam", {})
        score = match.get("score", {})

        return {
            "fixture_id": match.get("id"),
            "date": match.get("utcDate", ""),
            "league": match.get("competition", {}).get("name", ""),
            "league_id": None,
            "league_country": "",
            "home_team": home.get("shortName", home.get("name", "")),
            "away_team": away.get("shortName", away.get("name", "")),
            "home_team_id": home.get("id"),
            "away_team_id": away.get("id"),
            "status": match.get("status", ""),
            "home_score": score.get("fullTime", {}).get("home"),
            "away_score": score.get("fullTime", {}).get("away"),
            "referee": match.get("referees", [{}])[0].get("name", "") if match.get("referees") else "",
            "venue": "",
            "source": "football-data.org"
        }

    def _normalize_team_stats(self, stats: dict, team_name: str) -> dict:
        """Normaliza estadísticas de equipo de API-Football."""
        return {
            "team": team_name,
            "league": stats.get("league", {}).get("name", ""),
            "season": stats.get("league", {}).get("season", ""),
            "form": stats.get("form", ""),
            "fixtures_played": stats.get("fixtures", {}).get("played", {}).get("total", 0),
            "wins": stats.get("fixtures", {}).get("wins", {}).get("total", 0),
            "draws": stats.get("fixtures", {}).get("draws", {}).get("total", 0),
            "losses": stats.get("fixtures", {}).get("loses", {}).get("total", 0),
            "goals_total": stats.get("goals", {}).get("for", {}).get("total", {}).get("total", 0),
            "goals_against": stats.get("goals", {}).get("against", {}).get("total", {}).get("total", 0),
            "avg_goals_for": stats.get("goals", {}).get("for", {}).get("average", {}).get("total", 0),
            "avg_goals_against": stats.get("goals", {}).get("against", {}).get("average", {}).get("total", 0),
            "clean_sheets": stats.get("clean_sheet", {}).get("total", 0),
            "failed_to_score": stats.get("failed_to_score", {}).get("total", 0),
            "lineup_most_used": stats.get("lineups", [{}])[0].get("formation", "") if stats.get("lineups") else "",
            "penalty_stats": stats.get("penalty", {}),
        }

    def _parse_match_stats(self, stats_data: list, events: list) -> dict:
        """Parsea estadísticas y eventos de un partido."""
        result = {
            "corners": {"home": 0, "away": 0},
            "cards": {"home_yellow": 0, "home_red": 0, "away_yellow": 0, "away_red": 0},
            "shots": {"home": 0, "away": 0},
            "shots_on_target": {"home": 0, "away": 0},
            "possession": {"home": 50, "away": 50},
        }

        if stats_data:
            for team_stats in stats_data:
                for stat in team_stats.get("statistics", []):
                    stat_type = stat.get("type", "")
                    value = stat.get("value", 0)

                    if isinstance(value, str):
                        value = value.replace("%", "").strip()
                        try:
                            value = float(value)
                        except ValueError:
                            value = 0

                    if "Corner" in stat_type and value:
                        result["corners"]["home"] = int(value)
                    elif "Total Shots" in stat_type and value:
                        result["shots"]["home"] = int(value)
                    elif "Shots on Goal" in stat_type and value:
                        result["shots_on_target"]["home"] = int(value)
                    elif "Ball Possession" in stat_type and value:
                        result["possession"]["home"] = int(value)
                        result["possession"]["away"] = 100 - int(value)

        if events:
            for event in events:
                e_type = event.get("type", "")
                detail = event.get("detail", "")
                if e_type == "Card":
                    if "Yellow" in detail:
                        result["cards"]["home_yellow"] += 1
                    elif "Red" in detail:
                        result["cards"]["home_red"] += 1

        return result

    def _get_competition_code(self, league_name: str) -> Optional[str]:
        """Convierte nombre de liga a código de football-data.org."""
        mapping = {
            "La Liga": "PD", "La Liga (España)": "PD",
            "Premier League": "PL", "Premier League (Inglaterra)": "PL",
            "Bundesliga": "BL1", "Bundesliga (Alemania)": "BL1",
            "Serie A": "SA", "Serie A (Italia)": "SA",
            "Ligue 1": "FL1", "Ligue 1 (Francia)": "FL1",
            "Champions League": "CL",
            "Europa League": "EL",
            "Conference League": "EC",
        }
        return mapping.get(league_name)

    # =========================================================================
    # DIAGNÓSTICO
    # =========================================================================

    def diagnose(self) -> dict:
        """Verifica la conectividad con todas las APIs."""
        results = {}

        # API-Football
        try:
            data = self.api_football._get("status")
            if data:
                req_info = data.get("response", {}).get("requests", {})
                results["api_football"] = {
                    "status": "OK",
                    "mode": self.api_football._working_mode or self.api_football.detected_type,
                    "requests_limit": req_info.get("limit_day", "?"),
                    "requests_current": req_info.get("current", "?"),
                }
            else:
                results["api_football"] = {
                    "status": "ERROR", 
                    "mode": self.api_football._working_mode or "not probed",
                    "detail": "Sin respuesta — verificar API key y suscripción"
                }
        except Exception as e:
            results["api_football"] = {"status": "ERROR", "detail": str(e)[:100]}

        # football-data.org
        try:
            data = self.football_data._get("competitions", {"plan": "TIER_ONE"})
            if data:
                results["football_data_org"] = {
                    "status": "OK",
                    "competitions": len(data.get("competitions", []))
                }
            else:
                results["football_data_org"] = {"status": "ERROR", "detail": "Sin respuesta"}
        except Exception as e:
            results["football_data_org"] = {"status": "ERROR", "detail": str(e)[:100]}

        # Sportmonks
        try:
            data = self.sportmonks._get("leagues", {"limit": 1})
            if data:
                results["sportmonks"] = {"status": "OK"}
            else:
                results["sportmonks"] = {"status": "ERROR", "detail": "Sin respuesta"}
        except Exception as e:
            results["sportmonks"] = {"status": "ERROR", "detail": str(e)[:100]}

        return results
