"""
WebResultFetcher — Resultados REALES para LAGEMA JARG74
========================================================
Obtiene resultados verídicos de partidos finalizados usando
el APIManager (API-Football + Sportmonks + football-data.org).

ANTES: Generaba resultados aleatorios (random.randint) — INACEPTABLE
AHORA: Consulta APIs reales para obtener datos contrastados

Uso:
    from src.data.web_fetcher import WebResultFetcher
    wf = WebResultFetcher()
    outcome = wf.fetch_real_result("RM_BAR_20260512", "Real Madrid", "Barcelona")
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from src.models.base import MatchOutcome

logger = logging.getLogger("LAGEMA_WEB_FETCHER")


class WebResultFetcher:
    """
    Componente encargado de acceder a la red para obtener resultados reales.
    
    Estrategia de búsqueda en cascada:
      1. API-Football: buscar por fixture_id conocido → resultado completo
      2. API-Football: buscar por equipos+fecha → resultado completo
      3. football-data.org: buscar por competición+fecha → resultado básico
      4. Sportmonks: buscar por equipos+fecha → resultado
    
    Si el partido aún no ha terminado, retorna None.
    """
    
    def __init__(self):
        # Inicialización lazy del APIManager para evitar imports circulares
        self._api_manager = None
    
    @property
    def api(self):
        if self._api_manager is None:
            try:
                from src.data.api_manager import APIManager
                self._api_manager = APIManager()
            except ImportError:
                logger.error("[WebFetcher] No se pudo importar APIManager")
                return None
        return self._api_manager

    def fetch_real_result(self, match_id: str, home_team: str, 
                           away_team: str, date: str = None,
                           fixture_id: int = None) -> Optional[MatchOutcome]:
        """
        Obtiene el resultado REAL de un partido desde las APIs.
        
        Args:
            match_id: ID interno del partido (ej: "RM_BAR_20260512")
            home_team: Nombre del equipo local
            away_team: Nombre del equipo visitante
            date: Fecha del partido "YYYY-MM-DD" (opcional)
            fixture_id: ID de API-Football si se conoce (opcional)
        
        Returns:
            MatchOutcome con datos reales, o None si no se encuentra
        """
        api = self.api
        if not api:
            logger.error("[WebFetcher] APIManager no disponible")
            return None

        logger.info(f"[WebFetcher] Buscando resultado REAL: {home_team} vs {away_team}")

        # Intentar obtener resultado por fixture_id o por equipos+fecha
        result = api.get_match_result(
            fixture_id=fixture_id,
            home_team=home_team,
            away_team=away_team,
            date=date
        )

        if not result:
            logger.info(f"[WebFetcher] No se encontró resultado para {home_team} vs {away_team}")
            return None

        # Parsear estadísticas del resultado
        stats = result.get("stats", {})

        # Córners
        corners = stats.get("corners", {})
        home_corners = corners.get("home", 0) or 0
        away_corners = corners.get("away", 0) or 0

        # Tarjetas
        cards = stats.get("cards", {})
        home_cards = (cards.get("home_yellow", 0) or 0) + (cards.get("home_red", 0) or 0)
        away_cards = (cards.get("away_yellow", 0) or 0) + (cards.get("away_red", 0) or 0)

        # Remates
        shots = stats.get("shots", {})
        home_shots = shots.get("home", 0) or 0
        away_shots = shots.get("away", 0) or 0

        # Remates a puerta
        shots_on_target = stats.get("shots_on_target", {})
        home_shots_on_target = shots_on_target.get("home", 0) or 0
        away_shots_on_target = shots_on_target.get("away", 0) or 0

        return MatchOutcome(
            match_id=match_id,
            home_score=result["home_score"],
            away_score=result["away_score"],
            home_corners=int(home_corners),
            away_corners=int(away_corners),
            home_cards=int(home_cards),
            away_cards=int(away_cards),
            home_shots=int(home_shots),
            away_shots=int(away_shots),
            home_shots_on_target=int(home_shots_on_target),
            away_shots_on_target=int(away_shots_on_target),
            actual_winner=result["winner"]
        )

    def fetch_real_result_from_fixture(self, fixture_id: int,
                                        match_id: str) -> Optional[MatchOutcome]:
        """
        Obtiene resultado real usando el fixture_id de API-Football.
        Método más fiable cuando se conoce el ID.
        """
        api = self.api
        if not api:
            return None

        result = api.get_match_result(fixture_id=fixture_id)
        if not result:
            return None

        stats = result.get("stats", {})
        corners = stats.get("corners", {})
        cards = stats.get("cards", {})
        shots = stats.get("shots", {})
        shots_on_target = stats.get("shots_on_target", {})

        return MatchOutcome(
            match_id=match_id,
            home_score=result["home_score"],
            away_score=result["away_score"],
            home_corners=int(corners.get("home", 0) or 0),
            away_corners=int(corners.get("away", 0) or 0),
            home_cards=int((cards.get("home_yellow", 0) or 0) + (cards.get("home_red", 0) or 0)),
            away_cards=int((cards.get("away_yellow", 0) or 0) + (cards.get("away_red", 0) or 0)),
            home_shots=int(shots.get("home", 0) or 0),
            away_shots=int(shots.get("away", 0) or 0),
            home_shots_on_target=int(shots_on_target.get("home", 0) or 0),
            away_shots_on_target=int(shots_on_target.get("away", 0) or 0),
            actual_winner=result["winner"]
        )

    def get_flashscore_live_data(self, url: str):
        """
        Placeholder para lógica de scraping real si se proporciona una URL.
        No implementado — usar API-Football en su lugar.
        """
        logger.warning("[WebFetcher] get_flashscore_live_data no implementado. Usar API-Football.")
        return None

    def get_live_results(self, league_ids: list = None) -> list:
        """
        Obtiene resultados en vivo de las APIs.
        
        Args:
            league_ids: Lista de IDs de liga (ej: [140, 39, 78])
        
        Returns:
            Lista de partidos en vivo con datos actualizados
        """
        api = self.api
        if not api:
            return []

        return api.api_football.get_live_fixtures(league_ids=league_ids)

    def get_recent_results(self, league_name: str = None, 
                            days_back: int = 7) -> list:
        """
        Obtiene resultados de los últimos N días.
        Útil para actualizar el sistema de aprendizaje.
        """
        api = self.api
        if not api:
            return []

        results = []
        today = datetime.now()

        for i in range(days_back):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            fixtures = api.get_fixtures_for_date(date, league_name=league_name)
            for f in fixtures:
                if f.get("home_score") is not None and f.get("away_score") is not None:
                    results.append(f)

        return results
