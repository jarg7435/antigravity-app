"""
Football-Data.org Integration Module para La Gema JARG74
Fuente oficial secundaria para verificación de árbitros y calendario.

Este módulo es una fachada fina sobre el FootballDataClient de api_manager,
que ya resuelve la autenticación, el rate limiting (10 req/min en el plan
gratuito) y el manejo de errores HTTP. Aquí solo se añaden los métodos con la
semántica que espera multi_source_fetcher.

NOTA: Football-Data.org solo publica árbitros en partidos FINALIZADOS. Para
próximos partidos la fuente válida es API-Football.

Requiere: FOOTBALL_DATA_API_KEY en variables de entorno

Autor: Antigravity - La Gema JARG74
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.data.api_manager import FootballDataClient as _BaseFootballDataClient

logger = logging.getLogger(__name__)


# Códigos de competición de Football-Data.org.
# Las claves coinciden con la salida de multi_source_fetcher._norm_league().
COMPETITION_CODES: Dict[str, str] = {
    "La Liga": "PD",
    "Premier League": "PL",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Ligue 1": "FL1",
    "Champions League": "CL",
    "Europa League": "EL",
    "Conference League": "EC",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
    "Championship": "ELC",
    "Brasileirao": "BSA",
}


class FootballDataClient(_BaseFootballDataClient):
    """Cliente de Football-Data.org con la interfaz que usa multi_source_fetcher."""

    @property
    def is_configured(self) -> bool:
        """True si hay API key disponible."""
        return bool(self.api_key)

    def get_upcoming_matches(self, competition_code: str,
                             days_ahead: int = 7) -> List[dict]:
        """Partidos programados desde hoy hasta days_ahead días vista."""
        hoy = datetime.now().date()
        return self.get_competition_matches(
            competition_code,
            date_from=hoy.isoformat(),
            date_to=(hoy + timedelta(days=days_ahead)).isoformat(),
            status="SCHEDULED",
        )

    def get_matches_today(self, competition_code: str) -> List[dict]:
        """Partidos de hoy, en cualquier estado."""
        hoy = datetime.now().date().isoformat()
        return self.get_competition_matches(
            competition_code, date_from=hoy, date_to=hoy
        )

    def get_match_with_referees(self, match_id: int) -> Optional[dict]:
        """
        Detalle de un partido incluyendo su lista de árbitros.

        Devuelve el partido con la clave "referees" siempre presente (lista
        vacía si la API no la trae, cosa habitual en partidos no finalizados).
        """
        detalle = self.get_match(match_id)
        if not detalle:
            return None

        # La v4 devuelve el partido directamente o envuelto en "match".
        partido = detalle.get("match", detalle)
        partido.setdefault("referees", [])
        if not partido["referees"]:
            logger.debug(f"Football-Data.org: partido {match_id} sin arbitro asignado")
        return partido
