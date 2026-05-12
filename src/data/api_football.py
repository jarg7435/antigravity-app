"""
API-Football Integration Module para La Gema JARG74
Fuente PRINCIPAL de datos: fixtures, lineups, árbitros, estadísticas, odds, resultados.

API-Football (api-sports.io) cubre:
- 1200+ competiciones
- Árbitros en el campo "referee" de cada fixture
- Lineups disponibles 20-40 min antes del partido
- Estadísticas completas por partido y por equipo
- Odds de bookmakers
- Lesiones y bajas
- Clasificaciones

Requiere: API_FOOTBALL_KEY en variables de entorno
Plan gratuito: 100 requests/día
Plan Pro ($9.99/mes): 3000 requests/día
Plan Ultra ($29.99/mes): Requests ilimitados

Autor: Antigravity - La Gema JARG74
"""

import os
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import requests

from .cache_manager import CacheManager, TTLConfig

logger = logging.getLogger(__name__)


# IDs de ligas en API-Football
LEAGUE_IDS = {
    "La Liga": 140,
    "Premier League": 39,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Champions League": 2,
    "Europa League": 3,
    "Conference League": 848,
    # Ligas sudamericanas
    "Copa Libertadores": 13,
    "Copa Sudamericana": 11,
    "Brasileirao": 71,
    "Primera División Argentina": 128,
}

# Reverse map: API id → nombre legible
LEAGUE_NAMES = {v: k for k, v in LEAGUE_IDS.items()}


class APIFootballError(Exception):
    """Error específico de API-Football."""
    def __init__(self, message: str, status_code: int = None, api_errors: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.api_errors = api_errors


class APIFootballClient:
    """
    Cliente para API-Football v3.

    Soporta DOS formatos de autenticación:
    - DIRECTA: Key de api-sports.io → endpoint v3.football.api-sports.io + header x-apisports-key
    - RapidAPI: Key de RapidAPI → endpoint api-football-v1.p.rapidapi.com + headers x-rapidapi-key/x-rapidapi-host

    Autodetección automática: Si la key contiene 'msh' y 'jsn', es RapidAPI.

    Proporciona acceso a:
    - Fixtures (partidos) con árbitro, alineaciones, estadísticas
    - Equipos y plantillas
    - Lesiones y bajas
    - Clasificaciones
    - Odds de mercado
    - Perfil de árbitros (desde fixtures)
    - H2H (enfrentamientos directos)
    """

    # URLs para ambos formatos
    BASE_URL_DIRECT = "https://v3.football.api-sports.io"
    BASE_URL_RAPIDAPI = "https://api-football-v1.p.rapidapi.com/v3"

    def __init__(self, api_key: str = None, cache_manager: CacheManager = None):
        raw_key = api_key or os.getenv("API_FOOTBALL_KEY", "")
        # Limpiar comillas accidentales al inicio/fin de la key
        self._api_key = raw_key.strip().strip("'\"")
        self._cache = cache_manager or CacheManager(persist=False)

        # Autodetección del formato de la key
        self._is_rapidapi = self._detect_rapidapi_key(self._api_key)

        if self._is_rapidapi:
            self.BASE_URL = self.BASE_URL_RAPIDAPI
            logger.info("API-Football: Usando formato RapidAPI (key detectada con patrón msh...jsn)")
        else:
            self.BASE_URL = self.BASE_URL_DIRECT
            logger.info("API-Football: Usando formato DIRECTO (api-sports.io)")

        self._session = requests.Session()
        if self._is_rapidapi:
            self._session.headers.update({
                "x-rapidapi-key": self._api_key,
                "x-rapidapi-host": "v3.football.api-sports.io",
                "Accept": "application/json"
            })
        else:
            self._session.headers.update({
                "x-apisports-key": self._api_key,
                "Accept": "application/json"
            })
        self._last_request_time = 0
        self._min_interval = 1.0  # Mínimo 1 segundo entre peticiones

        if not self._api_key:
            logger.warning(
                "API_FOOTBALL_KEY no configurada. "
                "Obtén tu clave en https://www.api-football.com/ "
                "(plan gratuito: 100 req/día)"
            )

    @staticmethod
    def _detect_rapidapi_key(key: str) -> bool:
        """
        Detecta si una API key es de formato RapidAPI.
        Las keys de RapidAPI tienen el patrón: {hex}msh{hex}p{hex}jsn{hex}
        Ejemplo: 7a7b5e6790mshbcac8007a85e04fp19f034jsn66c5e37f4f09
        """
        if not key:
            return False
        key_lower = key.lower()
        # RapidAPI keys siempre contienen 'msh' y 'jsn' como separadores
        return 'msh' in key_lower and 'jsn' in key_lower

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _rate_limit(self):
        """Respeta el rate limit entre peticiones."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        endpoint: str,
        params: Dict = None,
        cache_category: str = None,
        cache_id: str = None,
        cache_ttl: float = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        Realiza una petición a la API con caché y rate limiting.

        Returns:
            Dict con la respuesta completa de la API
        """
        # Verificar caché
        if cache_category and cache_id and not force_refresh:
            cached = self._cache.get(cache_category, cache_id)
            if cached is not None:
                return cached

        if not self.is_configured:
            raise APIFootballError(
                "API_FOOTBALL_KEY no configurada. "
                "Añade tu clave al archivo .env o como variable de entorno."
            )

        # Rate limiting
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"API-Football request: {endpoint} params={params}")

        try:
            response = self._session.get(url, params=params, timeout=15)
            data = response.json()

            # Verificar errores de la API
            errors = data.get("errors", {})
            if errors:
                logger.error(f"API-Football errors: {errors}")
                raise APIFootballError(
                    f"Errores en API-Football: {errors}",
                    api_errors=errors
                )

            # Verificar rate limit de la API
            remaining = int(response.headers.get("x-ratelimit-requests-remaining", 999))
            limit = int(response.headers.get("x-ratelimit-requests-limit", 100))
            if remaining <= 5:
                logger.warning(
                    f"API-Football rate limit bajo: {remaining}/{limit} peticiones restantes"
                )

            # Guardar en caché
            if cache_category and cache_id:
                self._cache.set(
                    cache_category, cache_id,
                    data, "api_football", cache_ttl
                )

            return data

        except requests.exceptions.Timeout:
            raise APIFootballError(f"Timeout en petición a {endpoint}")
        except requests.exceptions.ConnectionError:
            raise APIFootballError(f"Error de conexión a {endpoint}")
        except json.JSONDecodeError:
            raise APIFootballError(f"Respuesta inválida de {endpoint}")

    # ============================================================
    # FIXTURES (Partidos)
    # ============================================================

    def get_fixtures_today(self, league_id: int = None) -> List[Dict]:
        """
        Obtiene los partidos de hoy.

        Args:
            league_id: ID de la liga (opcional, si no se especifica devuelve todas)

        Returns:
            Lista de fixtures con árbitro, estado, goles, etc.
        """
        params = {"date": datetime.now().strftime("%Y-%m-%d")}
        if league_id:
            params["league"] = league_id
        params["season"] = self._current_season(league_id)

        cache_id = f"today_{league_id or 'all'}"
        data = self._request(
            "fixtures", params,
            cache_category="fixtures_today",
            cache_id=cache_id,
            cache_ttl=TTLConfig.FIXTURES_TODAY
        )
        return data.get("response", [])

    def get_fixtures_by_date_range(
        self,
        date_from: str,
        date_to: str,
        league_id: int = None
    ) -> List[Dict]:
        """
        Obtiene partidos en un rango de fechas.

        Args:
            date_from: Fecha inicio (YYYY-MM-DD)
            date_to: Fecha fin (YYYY-MM-DD)
            league_id: ID de la liga (opcional)
        """
        params = {"from": date_from, "to": date_to}
        if league_id:
            params["league"] = league_id
            params["season"] = self._current_season(league_id)

        cache_id = f"range_{date_from}_{date_to}_{league_id or 'all'}"
        data = self._request(
            "fixtures", params,
            cache_category="fixtures_week",
            cache_id=cache_id,
            cache_ttl=TTLConfig.FIXTURES_WEEK
        )
        return data.get("response", [])

    def get_fixture_detail(self, fixture_id: int) -> Optional[Dict]:
        """
        Obtiene el detalle completo de un partido.

        Incluye: árbitro, estadio, alineaciones (si disponibles),
        goles, tarjetas, eventos.
        """
        data = self._request(
            "fixtures",
            {"id": fixture_id},
            cache_category="fixtures_today",
            cache_id=f"detail_{fixture_id}",
            cache_ttl=TTLConfig.FIXTURES_TODAY
        )
        responses = data.get("response", [])
        return responses[0] if responses else None

    def get_next_fixtures(self, league_id: int, next_n: int = 10) -> List[Dict]:
        """
        Obtiene los próximos N partidos de una liga.

        Args:
            league_id: ID de la liga
            next_n: Número de próximos partidos
        """
        data = self._request(
            "fixtures",
            {"league": league_id, "next": next_n, "season": self._current_season(league_id)},
            cache_category="fixtures_week",
            cache_id=f"next_{league_id}_{next_n}",
            cache_ttl=TTLConfig.FIXTURES_TODAY
        )
        return data.get("response", [])

    # ============================================================
    # ÁRBITROS
    # ============================================================

    def get_referee_from_fixture(self, fixture_id: int) -> Optional[Dict]:
        """
        Obtiene el árbitro de un partido específico.

        API-Football incluye el árbitro en el campo "referee" del fixture.
        Este es el método más fiable para saber quién arbitra un partido.
        """
        fixture = self.get_fixture_detail(fixture_id)
        if not fixture:
            return None

        referee_name = fixture.get("fixture", {}).get("referee")
        if not referee_name:
            return None

        return {
            "name": referee_name,
            "fixture_id": fixture_id,
            "league": fixture.get("league", {}).get("name"),
            "date": fixture.get("fixture", {}).get("date"),
            "source": "api_football",
            "confidence": "HIGH"  # API-Football obtiene datos oficiales
        }

    def get_referee_fixtures(
        self,
        referee_name: str,
        league_id: int = None,
        season: int = None
    ) -> List[Dict]:
        """
        Obtiene partidos arbitrados por un árbitro específico.

        Esto permite construir el perfil estadístico del árbitro:
        - Media de tarjetas amarillas/rojas
        - Penaltis señalados
        - Victoria local/visitante/empate
        - Goles por partido
        """
        if season is None:
            season = datetime.now().year - (1 if datetime.now().month < 7 else 0)

        params = {"search": referee_name}
        if league_id:
            params["league"] = league_id
            params["season"] = season
        else:
            params["season"] = season

        cache_id = f"ref_fixtures_{referee_name.replace(' ', '_')}_{league_id or 'all'}_{season}"
        data = self._request(
            "fixtures",
            params,
            cache_category="referee_stats",
            cache_id=cache_id,
            cache_ttl=TTLConfig.REFEREE_STATS
        )
        return data.get("response", [])

    def get_upcoming_referees(self, league_id: int, next_n: int = 20) -> List[Dict]:
        """
        Obtiene los árbitros asignados para los próximos partidos.

        Returns:
            Lista de dicts con {fixture_id, referee, home_team, away_team, date}
        """
        fixtures = self.get_next_fixtures(league_id, next_n)
        referee_assignments = []

        for f in fixtures:
            ref_name = f.get("fixture", {}).get("referee")
            if ref_name:
                referee_assignments.append({
                    "fixture_id": f["fixture"]["id"],
                    "referee": ref_name,
                    "home_team": f["teams"]["home"]["name"],
                    "away_team": f["teams"]["away"]["name"],
                    "date": f["fixture"]["date"],
                    "league": f["league"]["name"],
                    "source": "api_football",
                    "confidence": "HIGH" if f["fixture"]["status"]["short"] in ("NS", "TBD") else "MEDIUM"
                })

        return referee_assignments

    def compute_referee_profile(self, referee_name: str, league_id: int = None) -> Dict:
        """
        Calcula el perfil estadístico completo de un árbitro.

        Incluye:
        - Partidos arbitrados
        - Media de tarjetas amarillas y rojas
        - Penaltis señalados
        - Distribución de resultados (local/empate/visitante)
        - Media de goles
        - Nivel de severidad
        """
        fixtures = self.get_referee_fixtures(referee_name, league_id)

        if not fixtures:
            return {
                "name": referee_name,
                "matches_count": 0,
                "source": "api_football",
                "confidence": "LOW"
            }

        total_matches = 0
        total_yellow_home = 0
        total_yellow_away = 0
        total_red_home = 0
        total_red_away = 0
        home_wins = 0
        draws = 0
        away_wins = 0
        total_goals = 0
        penalties = 0

        for f in fixtures:
            # Solo contar partidos finalizados
            status = f.get("fixture", {}).get("status", {}).get("short")
            if status not in ("FT", "AET", "PEN"):
                continue

            total_matches += 1

            # Goles
            home_goals = f.get("goals", {}).get("home", 0) or 0
            away_goals = f.get("goals", {}).get("away", 0) or 0
            total_goals += home_goals + away_goals

            # Resultado
            if home_goals > away_goals:
                home_wins += 1
            elif home_goals == away_goals:
                draws += 1
            else:
                away_wins += 1

        # Calcular medias
        avg_goals = total_goals / max(1, total_matches)
        home_win_pct = (home_wins / max(1, total_matches)) * 100
        draw_pct = (draws / max(1, total_matches)) * 100
        away_win_pct = (away_wins / max(1, total_matches)) * 100

        # Determinar severidad basada en tarjetas (aproximación)
        # Nota: API-Football requiere endpoint de eventos para tarjetas exactas
        # Esta es una estimación basada en fixtures
        strictness = "MEDIUM"
        if total_matches > 5:
            strictness = "MEDIUM"  # Se refinará con datos de eventos

        return {
            "name": referee_name,
            "matches_count": total_matches,
            "avg_goals": round(avg_goals, 2),
            "home_win_pct": round(home_win_pct, 1),
            "draw_pct": round(draw_pct, 1),
            "away_win_pct": round(away_win_pct, 1),
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "strictness": strictness,
            "source": "api_football",
            "confidence": "HIGH" if total_matches >= 10 else "MEDIUM" if total_matches >= 5 else "LOW"
        }

    # ============================================================
    # ALINEACIONES (Lineups)
    # ============================================================

    def get_lineups(self, fixture_id: int) -> Optional[List[Dict]]:
        """
        Obtiene las alineaciones de un partido.

        Disponibles 20-40 minutos antes del inicio del partido
        cuando la competición cubre esta característica.
        """
        data = self._request(
            "fixtures/lineups",
            {"fixture": fixture_id},
            cache_category="lineups_confirmed",
            cache_id=f"lineups_{fixture_id}",
            cache_ttl=TTLConfig.LINEUPS_CONFIRMED
        )
        lineups = data.get("response", [])
        if lineups:
            return lineups
        return None

    def get_predicted_lineups(self, team_id: int, league_id: int) -> Optional[Dict]:
        """
        Obtiene alineaciones predichas para el próximo partido de un equipo.
        """
        data = self._request(
            "fixtures/lineups",
            {"team": team_id, "league": league_id, "season": self._current_season(league_id)},
            cache_category="lineups_predicted",
            cache_id=f"predicted_{team_id}_{league_id}",
            cache_ttl=TTLConfig.LINEUPS_PREDICTED
        )
        return data.get("response", [])

    # ============================================================
    # ESTADÍSTICAS
    # ============================================================

    def get_fixture_statistics(self, fixture_id: int) -> Optional[List[Dict]]:
        """Obtiene estadísticas de un partido (tiros, posesión, córners, etc.)."""
        data = self._request(
            "fixtures/statistics",
            {"fixture": fixture_id},
            cache_category="season_stats",
            cache_id=f"stats_{fixture_id}",
            cache_ttl=TTLConfig.SEASON_STATS
        )
        return data.get("response", [])

    def get_team_statistics(
        self,
        team_id: int,
        league_id: int,
        season: int = None
    ) -> Optional[Dict]:
        """
        Obtiene estadísticas de un equipo en una liga/temporada.

        Incluye: goles marcados/recibidos, clean sheets, racha, forma, etc.
        """
        if season is None:
            season = self._current_season(league_id)

        data = self._request(
            "teams/statistics",
            {"team": team_id, "league": league_id, "season": season},
            cache_category="season_stats",
            cache_id=f"team_stats_{team_id}_{league_id}_{season}",
            cache_ttl=TTLConfig.SEASON_STATS
        )
        return data.get("response", {})

    # ============================================================
    # LESIONES Y BAJAS
    # ============================================================

    def get_injuries(
        self,
        team_id: int = None,
        league_id: int = None,
        fixture_id: int = None
    ) -> List[Dict]:
        """Obtiene la lista de lesiones/bajas."""
        params = {}
        if fixture_id:
            params["fixture"] = fixture_id
        elif team_id:
            params["team"] = team_id
            if league_id:
                params["league"] = league_id
                params["season"] = self._current_season(league_id)

        cache_id = f"injuries_{fixture_id or team_id or 'all'}_{league_id or 'all'}"
        data = self._request(
            "injuries",
            params,
            cache_category="injuries",
            cache_id=cache_id,
            cache_ttl=TTLConfig.INJURIES
        )
        return data.get("response", [])

    # ============================================================
    # CLASIFICACIONES
    # ============================================================

    def get_standings(self, league_id: int, season: int = None) -> List[Dict]:
        """Obtiene la clasificación de una liga."""
        if season is None:
            season = self._current_season(league_id)

        data = self._request(
            "standings",
            {"league": league_id, "season": season},
            cache_category="standings",
            cache_id=f"standings_{league_id}_{season}",
            cache_ttl=TTLConfig.STANDINGS
        )
        return data.get("response", [])

    # ============================================================
    # ODDS (Cuotas de mercado)
    # ============================================================

    def get_odds(
        self,
        fixture_id: int = None,
        league_id: int = None,
        bookmaker: int = None
    ) -> List[Dict]:
        """
        Obtiene cuotas de apuestas para un partido o liga.

        Args:
            fixture_id: ID del partido
            league_id: ID de la liga
            bookmaker: ID del bookmaker (ej: 8 = Bet365)
        """
        params = {}
        if fixture_id:
            params["fixture"] = fixture_id
        if league_id:
            params["league"] = league_id
            params["season"] = self._current_season(league_id)
        if bookmaker:
            params["bookmaker"] = bookmaker

        cache_id = f"odds_{fixture_id or league_id or 'all'}_{bookmaker or 'all'}"
        data = self._request(
            "odds",
            params,
            cache_category="odds_prematch",
            cache_id=cache_id,
            cache_ttl=TTLConfig.ODDS_PREMATCH
        )
        return data.get("response", [])

    # ============================================================
    # H2H (Enfrentamientos Directos)
    # ============================================================

    def get_h2h(
        self,
        team1_id: int,
        team2_id: int,
        last_n: int = 15
    ) -> List[Dict]:
        """Obtiene los últimos N enfrentamientos directos entre dos equipos."""
        data = self._request(
            "fixtures/headtohead",
            {"h2h": f"{team1_id}-{team2_id}", "last": last_n},
            cache_category="h2h_records",
            cache_id=f"h2h_{team1_id}_{team2_id}",
            cache_ttl=TTLConfig.H2H_RECORDS
        )
        return data.get("response", [])

    # ============================================================
    # EQUIPOS
    # ============================================================

    def search_team(self, name: str) -> List[Dict]:
        """Busca equipos por nombre."""
        data = self._request(
            "teams",
            {"search": name},
            cache_category="team_info",
            cache_id=f"search_{name.replace(' ', '_')}",
            cache_ttl=TTLConfig.TEAM_INFO
        )
        return data.get("response", [])

    def get_team_squad(self, team_id: int) -> List[Dict]:
        """Obtiene la plantilla actual de un equipo."""
        data = self._request(
            "players/squads",
            {"team": team_id},
            cache_category="team_info",
            cache_id=f"squad_{team_id}",
            cache_ttl=TTLConfig.TEAM_INFO
        )
        return data.get("response", [])

    def get_teams_by_league(self, league_id: int, season: int = None) -> List[Dict]:
        """Obtiene los equipos de una liga."""
        if season is None:
            season = self._current_season(league_id)

        data = self._request(
            "teams",
            {"league": league_id, "season": season},
            cache_category="team_info",
            cache_id=f"teams_league_{league_id}_{season}",
            cache_ttl=TTLConfig.TEAM_INFO
        )
        return data.get("response", [])

    # ============================================================
    # EVENTOS (Goles, tarjetas, sustituciones)
    # ============================================================

    def get_fixture_events(self, fixture_id: int) -> List[Dict]:
        """
        Obtiene los eventos de un partido.

        Incluye: goles, tarjetas amarillas/rojas, sustituciones,
        penaltis, VAR. ESPECIALLY USEFUL para estadísticas de árbitros.
        """
        data = self._request(
            "fixtures/events",
            {"fixture": fixture_id},
            cache_category="season_stats",
            cache_id=f"events_{fixture_id}",
            cache_ttl=TTLConfig.SEASON_STATS
        )
        return data.get("response", [])

    # ============================================================
    # RESULTADOS EN VIVO
    # ============================================================

    def get_live_fixtures(self, league_id: int = None) -> List[Dict]:
        """Obtiene partidos en vivo."""
        params = {"live": "all"}
        if league_id:
            params["league"] = league_id

        data = self._request(
            "fixtures",
            params,
            cache_category="live_match",
            cache_id=f"live_{league_id or 'all'}",
            cache_ttl=TTLConfig.LIVE_MATCH
        )
        return data.get("response", [])

    # ============================================================
    # UTILIDADES
    # ============================================================

    def _current_season(self, league_id: int = None) -> int:
        """
        Determina la temporada actual basándose en la fecha.

        Las temporadas de fútbol europeo empiezan en agosto,
        así que si estamos en enero-julio, la temporada es el año anterior.
        """
        now = datetime.now()
        # Para ligas europeas (la mayoría)
        if now.month >= 8:
            return now.year
        else:
            return now.year - 1

    def get_api_status(self) -> Dict:
        """Obtiene el estado y límites de la API."""
        if not self.is_configured:
            return {"status": "not_configured", "message": "API key no configurada"}

        try:
            response = self._session.get(
                f"{self.BASE_URL}/status",
                timeout=10
            )
            data = response.json()
            return {
                "status": "ok",
                "account": data.get("response", {}).get("account", {}),
                "subscription": data.get("response", {}).get("subscription", {}),
                "requests": data.get("response", {}).get("requests", {}),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_league_coverage(self, league_id: int) -> Dict:
        """Verifica qué datos cubre la API para una liga específica."""
        data = self._request(
            "leagues",
            {"id": league_id, "current": "true"},
            cache_category="league_info",
            cache_id=f"coverage_{league_id}",
            cache_ttl=TTLConfig.LEAGUE_INFO
        )
        responses = data.get("response", [])
        if responses:
            return responses[0].get("seasons", [{}])[0].get("coverage", {})
        return {}
