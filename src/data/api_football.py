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
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import requests

from .cache_manager import CacheManager, TTLConfig
from . import resiliencia_api as _resiliencia

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
    # Segundas divisiones y otras ligas europeas
    "Segunda División": 141,
    "Championship": 40,
    "Bundesliga 2": 79,
    "Serie B": 136,
    "Ligue 2": 62,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Süper Lig": 203,
    "Scottish Premiership": 179,
    "Belgian Pro League": 144,
}

# Reverse map: API id → nombre legible
LEAGUE_NAMES = {v: k for k, v in LEAGUE_IDS.items()}


class APIFootballError(Exception):
    """Error específico de API-Football."""
    def __init__(self, message: str, status_code: int = None, api_errors: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.api_errors = api_errors


class APIFootballNoDisponible(APIFootballError):
    """
    La API esta fuera de servicio y no se la vuelve a llamar todavia.

    Se lanza sin tocar la red, para que la cascada pase a las fuentes
    secundarias al instante en lugar de esperar el timeout de una API que ya
    sabemos que no va a contestar.
    """


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
        # La API declara x-ratelimit-limit: 10 peticiones por minuto en el plan
        # gratuito. Un intervalo fijo de 1s permitia hasta 60/min y provocaba
        # 403 en rafaga; se usa una ventana deslizante con margen.
        self._peticiones = []
        self._max_por_minuto = 9

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
        """Espera lo justo para no superar el limite por minuto de la API."""
        ahora = time.time()
        self._peticiones = [t for t in self._peticiones if ahora - t < 60]
        if len(self._peticiones) >= self._max_por_minuto:
            espera = 60 - (ahora - self._peticiones[0]) + 0.1
            if espera > 0:
                logger.info(f"Rate limit local: esperando {espera:.1f}s")
                time.sleep(espera)
                ahora = time.time()
                self._peticiones = [t for t in self._peticiones if ahora - t < 60]
        self._peticiones.append(time.time())

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

        # Cortacircuitos: si la suscripción está caducada o la cuota agotada, la
        # petición está condenada a fallar. Se corta aquí, antes de gastar los
        # 15 s de timeout que dejaban colgada la búsqueda del árbitro, para que
        # quien llama pase de inmediato a las fuentes secundarias.
        if not _resiliencia.disponible():
            raise APIFootballNoDisponible(
                f"API-Football fuera de servicio: {_resiliencia.texto_estado()}"
            )

        # Rate limiting
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"API-Football request: {endpoint} params={params}")

        try:
            response = self._session.get(url, params=params, timeout=15)
            try:
                data = response.json()
            except ValueError:
                # Cuerpo ilegible: casi siempre el HTML de un portal de error
                # o de RapidAPI rechazando una cuenta sin suscripción.
                data = {}

            # Verificar errores de la API.
            #
            # API-Football contesta con HTTP 200 y mete el problema real en
            # "errors", así que el estado por sí solo no dice si la llamada ha
            # ido bien. Antes se trataban todos igual: un plan caducado y una
            # consulta fuera de cobertura levantaban el mismo error, y la
            # siguiente llamada volvía a intentarlo. Ahora se clasifican, y las
            # que delatan la caída de la fuente abren el cortacircuitos.
            errors = data.get("errors", {}) if isinstance(data, dict) else {}
            averia = _resiliencia.clasificar_respuesta(
                status_code=response.status_code, errors=errors, cuerpo=data
            )
            if averia is not None:
                _resiliencia.registrar_averia(
                    averia,
                    f"{endpoint} → HTTP {response.status_code} {errors or data}"
                )
                raise APIFootballNoDisponible(
                    f"API-Football fuera de servicio ({averia.value}): "
                    f"{_resiliencia.texto_estado()}",
                    status_code=response.status_code,
                    api_errors=errors if isinstance(errors, dict) else None,
                )

            if errors:
                # Limitación de la consulta, no de la fuente: la cascada la
                # esquiva por su cuenta y la API sigue estando sana.
                logger.error(f"API-Football errors: {errors}")
                raise APIFootballError(
                    f"Errores en API-Football: {errors}",
                    status_code=response.status_code,
                    api_errors=errors
                )

            # Verificar rate limit de la API
            remaining = int(response.headers.get("x-ratelimit-requests-remaining", 999))
            limit = int(response.headers.get("x-ratelimit-requests-limit", 100))
            if remaining <= 5:
                logger.warning(
                    f"API-Football rate limit bajo: {remaining}/{limit} peticiones restantes"
                )

            # Respuesta buena: se cierra el circuito si estaba abierto, para que
            # una suscripción renovada vuelva a la cascada sin reiniciar la app.
            _resiliencia.registrar_exito()

            # Guardar en caché
            if cache_category and cache_id:
                self._cache.set(
                    cache_category, cache_id,
                    data, "api_football", cache_ttl
                )

            return data

        except APIFootballError:
            raise
        except requests.exceptions.Timeout as e:
            _resiliencia.registrar_averia_por_excepcion(e)
            raise APIFootballError(f"Timeout en petición a {endpoint}")
        except requests.exceptions.ConnectionError as e:
            _resiliencia.registrar_averia_por_excepcion(e)
            raise APIFootballError(f"Error de conexión a {endpoint}")
        except json.JSONDecodeError as e:
            _resiliencia.registrar_averia_por_excepcion(e)
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


# =============================================================================
# CLIENTE COMPARTIDO
# =============================================================================

_CLIENTE_COMPARTIDO = None


def cliente_compartido() -> "APIFootballClient":
    """
    Devuelve el cliente unico del proceso.

    Cada instancia nueva trae su propia CacheManager vacia y su propio contador
    de ritmo. Con varios consumidores creando clientes por llamada, la cache no
    llegaba a servir nada y el limite de 10 peticiones por minuto se podia
    superar entre ellos. Compartir la instancia arregla las dos cosas, que en un
    plan de 100 peticiones al dia no es un detalle menor.
    """
    global _CLIENTE_COMPARTIDO
    if _CLIENTE_COMPARTIDO is None:
        _CLIENTE_COMPARTIDO = APIFootballClient()
    return _CLIENTE_COMPARTIDO


# =============================================================================
# DIAGNÓSTICO DE LA CONEXIÓN
# =============================================================================

def _clasifica_intento(intento) -> Optional["_resiliencia.Averia"]:
    """Avería que delata un intento fallido de `diagnosticar`, o None."""
    if not intento:
        return None
    _, estado, detalle = intento
    if estado is None:
        return None
    return _resiliencia.clasificar_respuesta(
        status_code=estado,
        errors=detalle if isinstance(detalle, dict) else None,
        cuerpo=detalle if isinstance(detalle, dict) else None,
    )


def diagnosticar(api_key: str = None) -> Dict[str, Any]:
    """
    Averigua por qué API-Football no responde, sin quedarse en "sin respuesta".

    El panel decía "❌ Sin respuesta (¿suscripción expirada?)" ante cualquier
    fallo, y esa pregunta tapaba cinco causas muy distintas que se arreglan de
    formas muy distintas: que no haya llave en los secrets, que la llave del
    despliegue no sea la buena, que la suscripción esté caducada de verdad, que
    la cuota del día esté agotada, o que el servidor no llegue a la API. Esta
    función las separa preguntándoselo a la propia API.

    Va directa a la red a propósito: ignora la caché y el cortacircuitos, porque
    es justo la comprobación con la que se decide si el circuito debe cerrarse.

    Devuelve siempre las mismas claves; `causa` es la que resume el veredicto.
    """
    raw = api_key if api_key is not None else os.getenv("API_FOOTBALL_KEY", "")
    clave = (raw or "").strip().strip("'\"")

    informe: Dict[str, Any] = {
        "ok": False,
        "causa": None,
        "mensaje": "",
        "clave_presente": bool(clave),
        "clave_longitud": len(clave),
        "clave_final": f"...{clave[-4:]}" if len(clave) >= 4 else "",
        "endpoint": None,
        "http": None,
        "plan": None,
        "suscripcion_activa": None,
        "suscripcion_hasta": None,
        "peticiones": None,
    }

    if not clave:
        informe["causa"] = "sin_llave"
        informe["mensaje"] = (
            "No hay API_FOOTBALL_KEY configurada. En Streamlit Cloud se pone en "
            "Settings → Secrets; en local, en el archivo .env."
        )
        return informe

    es_rapidapi = APIFootballClient._detect_rapidapi_key(clave)
    intentos = [
        ("directo", f"{APIFootballClient.BASE_URL_DIRECT}/status",
         {"x-apisports-key": clave, "Accept": "application/json"}),
        ("rapidapi", f"{APIFootballClient.BASE_URL_RAPIDAPI}/status",
         {"x-rapidapi-key": clave, "x-rapidapi-host": "v3.football.api-sports.io",
          "Accept": "application/json"}),
    ]
    if es_rapidapi:
        intentos.reverse()

    ultimo = None
    for nombre, url, cabeceras in intentos:
        try:
            r = requests.get(url, headers=cabeceras, timeout=15)
        except Exception as e:
            ultimo = ("red", None, f"{type(e).__name__}: {str(e)[:120]}")
            continue

        try:
            cuerpo = r.json()
        except ValueError:
            cuerpo = {}

        errores = cuerpo.get("errors", {}) if isinstance(cuerpo, dict) else {}
        respuesta = cuerpo.get("response") if isinstance(cuerpo, dict) else None

        # Una respuesta con cuenta y suscripción es la única prueba de que la
        # llave sirve; el 200 por sí solo no lo es, porque la API contesta 200
        # con el problema dentro de "errors".
        if r.status_code == 200 and isinstance(respuesta, dict) and respuesta.get("subscription"):
            sub = respuesta.get("subscription", {})
            req = respuesta.get("requests", {})
            actual = req.get("current")
            tope = req.get("limit_day")

            informe.update({
                "endpoint": nombre,
                "http": r.status_code,
                "plan": sub.get("plan"),
                "suscripcion_activa": sub.get("active"),
                "suscripcion_hasta": sub.get("end"),
                "peticiones": f"{actual}/{tope}",
            })

            if not sub.get("active"):
                informe["causa"] = "suscripcion_inactiva"
                informe["mensaje"] = (
                    f"La suscripción del plan {sub.get('plan')} figura como "
                    f"inactiva (fin: {sub.get('end')}). Renuévala en "
                    f"api-football.com."
                )
                return informe

            if isinstance(actual, int) and isinstance(tope, int) and actual >= tope:
                informe["causa"] = "cuota_agotada"
                informe["mensaje"] = (
                    f"Cuota del día agotada ({actual}/{tope}). Se repone en el "
                    f"reset diario; hasta entonces se opera con las fuentes "
                    f"secundarias."
                )
                return informe

            informe["ok"] = True
            informe["causa"] = "ok"
            informe["mensaje"] = (
                f"Conectada por el endpoint {nombre}. Plan {sub.get('plan')}, "
                f"activa hasta {sub.get('end')}, {actual}/{tope} peticiones hoy."
            )
            return informe

        intento = (nombre, r.status_code, errores or (cuerpo if isinstance(cuerpo, dict) else {}))
        # Se guarda el intento MÁS informativo, no el último. El endpoint que no
        # corresponde a la llave contesta un 404 genérico ("API doesn't exists")
        # que tapaba el veredicto bueno del otro, que sí dice si el problema es
        # la llave o la cuota.
        if ultimo is None or _clasifica_intento(ultimo) is None:
            ultimo = intento

    # Ningún endpoint devolvió una cuenta válida.
    nombre, estado, detalle = ultimo if ultimo else (None, None, "")
    informe["endpoint"] = nombre
    informe["http"] = estado

    if nombre == "red":
        informe["causa"] = "sin_red"
        informe["mensaje"] = (
            f"No se alcanza api-sports.io desde este servidor ({detalle}). "
            f"No es la suscripción: es la salida a Internet del despliegue."
        )
        return informe

    averia = _resiliencia.clasificar_respuesta(
        status_code=estado, errors=detalle if isinstance(detalle, dict) else None,
        cuerpo=detalle if isinstance(detalle, dict) else None
    )
    if averia is _resiliencia.Averia.CUOTA:
        informe["causa"] = "cuota_agotada"
        informe["mensaje"] = f"Cuota de peticiones agotada (HTTP {estado}): {detalle}"
    elif averia is _resiliencia.Averia.SUSCRIPCION:
        informe["causa"] = "llave_rechazada"
        informe["mensaje"] = (
            f"La API rechaza la llave (HTTP {estado}). Es la llave que hay "
            f"cargada en los secrets, no necesariamente la de tu cuenta: "
            f"comprueba que API_FOOTBALL_KEY en el despliegue sea la misma que "
            f"aparece en tu panel de api-football.com. Detalle: {detalle}"
        )
    else:
        informe["causa"] = "sin_respuesta"
        informe["mensaje"] = (
            f"La API no devuelve una cuenta válida (HTTP {estado}): {detalle}"
        )
    return informe
