"""
MultiSourceFetcher — Central Orchestrator for Data Verification
=================================================================
Applies the same multi-source validation protocol for any match
across all 5 major European leagues.

Strategy per request:
  1. Identify league → load correct scraper
  2. Try elite/unofficial source first (fastest, most specific)
  3. Fall back to official committee source
  4. Use fallback pool ONLY as last resort, with clear warning flag

Result always includes:
  - 'source': which source actually provided data
  - 'verification_link': URL the user can click to verify
  - '_is_fallback': True if using random pool (warn user)
  - 'bajas': list of detected unavailable players (lineups only)
"""
import re
from datetime import datetime
from typing import Dict, Optional


def _normalize_league(league: str) -> str:
    """Normalize league name to canonical form."""
    if not league:
        return ""
    norm = league.lower().strip()
    if "(" in norm:
        norm = norm.split("(")[0].strip()
    norm = norm.replace("ea sports", "").replace("santander", "").strip()

    if "la liga" in norm or "primera" in norm or "espana" in norm or "españa" in norm:
        return "La Liga"
    if "premier" in norm or "england" in norm:
        return "Premier League"
    if "serie a" in norm or "italy" in norm or "italia" in norm:
        return "Serie A"
    if "bundesliga" in norm or "germany" in norm or "german" in norm:
        return "Bundesliga"
    if "ligue 1" in norm or "france" in norm or "liga 1" in norm:
        return "Ligue 1"
    return norm


def _get_scraper(league: str):
    """Factory: returns appropriate scraper for the league."""
    norm = _normalize_league(league)
    if norm == "La Liga":
        from src.data.scrapers.la_liga import LaLigaDataScraper
        return LaLigaDataScraper()
    elif norm == "Premier League":
        from src.data.scrapers.premier_league import PremierLeagueDataScraper
        return PremierLeagueDataScraper()
    elif norm == "Serie A":
        from src.data.scrapers.serie_a import SerieADataScraper
        return SerieADataScraper()
    elif norm == "Bundesliga":
        from src.data.scrapers.bundesliga import BundesligaDataScraper
        return BundesligaDataScraper()
    elif norm == "Ligue 1":
        from src.data.scrapers.ligue1 import Ligue1DataScraper
        return Ligue1DataScraper()
    else:
        # For Liga Mixta, Liga Extra, international: try La Liga scraper as base
        # then fall back to generic pool
        return _GenericScraper()


class _GenericScraper:
    """Fallback for international / mixta matches."""

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        return {
            'home': [], 'away': [], 'bajas': [],
            'source': 'Sin datos (Liga no soportada en scraping automático)',
            'verification_link': None,
            '_is_fallback': True
        }

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        from src.models.base import RefereeStrictness
        pool = [
            {'name': 'Glenn Nyberg', 'avg_cards': 4.1},
            {'name': 'Sandro Schärer', 'avg_cards': 4.8},
            {'name': 'Irati Gallastegui', 'avg_cards': 4.2},
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': ref['avg_cards'],
            'source': 'Pool Internacional (fuente automática no disponible)',
            'verification_link': None,
            '_is_fallback': True
        }


class MultiSourceFetcher:
    """
    Central data fetcher that picks the correct league scraper
    and runs its cascade pipeline.
    
    Usage:
        fetcher = MultiSourceFetcher()
        lineup = fetcher.fetch_lineup("Villarreal", "Valencia", date, "La Liga")
        referee = fetcher.fetch_referee("Villarreal", "Valencia", date, "La Liga")
    """

    def fetch_lineup(self, home: str, away: str, match_date: datetime, league: str) -> Dict:
        """
        Fetches probable lineup for a match.
        
        Returns:
            {
                'home': List[str],       # Home team probable XI
                'away': List[str],       # Away team probable XI
                'bajas': List[str],      # Detected unavailable players
                'source': str,           # Which source provided this
                'verification_link': str # URL to verify manually
                '_is_fallback': bool     # True = random pool, warn user
            }
        """
        print(f"\n[MultiSourceFetcher] LINEUP: {home} vs {away} | {league}")
        scraper = _get_scraper(league)
        result = scraper.fetch_lineup(home, away, match_date)
        
        # Ensure all expected keys exist
        result.setdefault('home', [])
        result.setdefault('away', [])
        result.setdefault('bajas', [])
        result.setdefault('source', 'Desconocida')
        result.setdefault('verification_link', None)
        result.setdefault('_is_fallback', False)
        
        # Log result
        detected = len(result['home']) + len(result['away'])
        bajas_n = len(result['bajas'])
        print(f"  -> Resultado: {detected} jugadores detectados, {bajas_n} bajas | Fuente: {result['source']}")
        if result['_is_fallback']:
            print(f"  !! AVISO: Usando datos de pool fallback — verificar manualmente")
        
        return result

    def fetch_referee(self, home: str, away: str, match_date: datetime, league: str) -> Dict:
        """
        Fetches assigned referee for a match.
        
        Returns:
            {
                'name': str,                    # Referee full name
                'strictness': RefereeStrictness,
                'avg_cards': float,
                'source': str,
                'verification_link': str,
                '_is_fallback': bool            # True = random pool, warn user
            }
        """
        print(f"\n[MultiSourceFetcher] REFEREE: {home} vs {away} | {league}")
        scraper = _get_scraper(league)
        result = scraper.fetch_referee(home, away, match_date)
        
        result.setdefault('source', 'Desconocida')
        result.setdefault('verification_link', None)
        result.setdefault('_is_fallback', False)
        
        flag = "[POOL]" if result.get('_is_fallback') else "[OK]"
        print(f"  -> {flag} Árbitro: {result['name']} | Fuente: {result['source']}")
        
        return result
