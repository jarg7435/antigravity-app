import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
from datetime import datetime
import re
from src.models.base import Referee, RefereeStrictness


class RefereeSourceMapper:
    """
    Maps leagues to their official referee appointment sources.
    """
    
    LEAGUE_SOURCES = {
        "La Liga": "https://www.rfef.es/noticias/arbitros/designaciones",
        "Premier League": "https://www.premierleague.com/referees/overview",
        "Serie A": "https://www.aia-figc.it/designazioni/cana/",
        "Bundesliga": "https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/",
        "Ligue 1": "http://arbitrezvous.blogspot.com/",
    }
    
    @classmethod
    def _normalize_league(cls, league: str) -> str:
        """
        Normalizes league name for robust matching.
        """
        if not league:
            return ""
        
        # Lowercase, strip whitespace, remove common suffixes/prefixes
        norm = league.lower().strip()
        
        # Remove parenthetical info: "La Liga (España)" -> "la liga"
        if "(" in norm:
            norm = norm.split("(")[0].strip()
            
        # Handle "EA Sports", "Santander", etc.
        norm = norm.replace("ea sports", "").replace("santander", "").strip()
        
        # Map aliases to canonical names
        if "la liga" in norm or "primera division" in norm or "espana" in norm:
            return "La Liga"
        if "premier" in norm or "england" in norm:
            return "Premier League"
        if "serie a" in norm or "italy" in norm:
            return "Serie A"
        if "bundesliga" in norm or "germany" in norm:
            return "Bundesliga"
        if "ligue 1" in norm or "france" in norm:
            return "Ligue 1"
            
        return norm

    @classmethod
    def get_scraper(cls, league: str):
        """
        Returns appropriate referee scraper for the league.
        """
        norm_league = cls._normalize_league(league)
        
        if norm_league == "La Liga":
            return LaLigaRefereeScraper()
        elif norm_league == "Premier League":
            return PremierLeagueRefereeScraper()
        elif norm_league == "Serie A":
            return SerieARefereeScraper()
        elif norm_league == "Bundesliga":
            return BundesligaRefereeScraper()
        elif norm_league == "Ligue 1":
            return Ligue1RefereeScraper()
        else:
            # Generic international pool for all other matches (UEFA, Extra, Mixta)
            return InternationalRefereePoolScraper()


class BaseRefereeScraper:
    """Base class for referee scrapers."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """
        Fetch referee for a specific match.
        Returns: {'name': str, 'strictness': RefereeStrictness, 'avg_cards': float}
        """
        raise NotImplementedError
    
    def _infer_strictness(self, referee_name: str) -> RefereeStrictness:
        """
        Infer strictness based on known referee profiles.
        This is a heuristic - in production, use a database.
        """
        # Known strict referees
        strict_refs = ['gil manzano', 'mateu lahoz', 'hernández hernández', 'michael oliver', 
                       'anthony taylor', 'daniele orsato', 'felix brych']
        
        # Known lenient referees
        lenient_refs = ['díaz de mera', 'munuera montero', 'craig pawson', 
                        'marco guida', 'tobias stieler']
        
        name_lower = referee_name.lower()
        
        if any(ref in name_lower for ref in strict_refs):
            return RefereeStrictness.HIGH
        elif any(ref in name_lower for ref in lenient_refs):
            return RefereeStrictness.LOW
        else:
            return RefereeStrictness.MEDIUM


class LaLigaRefereeScraper(BaseRefereeScraper):
    """Scraper for La Liga referees from RFEF."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """
        Scrape RFEF website for La Liga referee appointments.
        """
        try:
            url = "https://www.rfef.es/noticias/arbitros/designaciones"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Look for match containing both team names
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            # Search in text content
            text = soup.get_text().lower()
            
            # Find referee name near team mentions
            # Pattern: "Team A - Team B: Referee Name"
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)'
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 5.0 if strictness == RefereeStrictness.HIGH else 3.5
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'RFEF'
                }
            
            # Fallback: return a common La Liga referee
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ RFEF scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found.
        NEVER returns a random referee — that causes incorrect data."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Fallback — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class PremierLeagueRefereeScraper(BaseRefereeScraper):
    """Scraper for Premier League referees."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """
        Scrape Premier League official site for referee appointments.
        """
        try:
            url = "https://www.premierleague.com/referees/overview"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Similar pattern matching as La Liga
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            text = soup.get_text()
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 4.8 if strictness == RefereeStrictness.HIGH else 3.2
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'Premier League Official'
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ Premier League scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Fallback — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class SerieARefereeScraper(BaseRefereeScraper):
    """Scraper for Serie A referees from AIA."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        try:
            url = "https://www.aia-figc.it/designazioni/cana/"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Pattern matching
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            text = soup.get_text()
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 5.2 if strictness == RefereeStrictness.HIGH else 3.8
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'AIA-FIGC'
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ AIA scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Fallback — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class BundesligaRefereeScraper(BaseRefereeScraper):
    """Scraper for Bundesliga referees from DFB."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        try:
            url = "https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            text = soup.get_text()
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 4.6 if strictness == RefereeStrictness.HIGH else 3.4
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'DFB'
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ DFB scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Fallback — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class Ligue1RefereeScraper(BaseRefereeScraper):
    """Scraper for Ligue 1 referees from Arbitrez-Vous blog."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        try:
            url = "http://arbitrezvous.blogspot.com/"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            text = soup.get_text()
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)'
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 4.4 if strictness == RefereeStrictness.HIGH else 3.2
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'Arbitrez-Vous'
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ Arbitrez-Vous scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Fallback — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class InternationalRefereePoolScraper(BaseRefereeScraper):
    """Generic pool for international and other matches."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        return self._fallback_referee()
            
    def _fallback_referee(self) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'International Pool — introduce el árbitro manualmente',
            '_is_fallback': True
        }


class FallbackRefereeScraper(BaseRefereeScraper):
    """Fallback scraper for unsupported leagues."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """Return fallback when referee cannot be found."""
        return {
            'name': 'No Detectado',
            'strictness': RefereeStrictness.MEDIUM,
            'avg_cards': 4.0,
            'source': 'Generic Pool — introduce el árbitro manualmente',
            '_is_fallback': True
        }
