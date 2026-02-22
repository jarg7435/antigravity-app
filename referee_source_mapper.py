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
        "Premier League": "https://www.premierleague.com/news/referees",
        "Serie A": "https://www.aia-figc.it/designazioni",
        "Bundesliga": "https://datencenter.dfb.de/schiedsrichter",
        "Ligue 1": "https://www.lfp.fr/arbitres",
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


class FutbolFantasyRefereeScraper(BaseRefereeScraper):
    """
    Scraper for FutbolFantasy match pages which often list designated referees.
    """
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Optional[Dict]:
        """
        Fetches referee by finding the match page on FutbolFantasy.
        """
        try:
            # 1. Get the list of matches for the round
            lineups_url = "https://www.futbolfantasy.com/laliga/posibles-alineaciones"
            resp = requests.get(lineups_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 2. Find the match URL
            match_url = None
            home_slug = home_team.lower().replace(" ", "-") # Basic normalization for URL search
            away_slug = away_team.lower().replace(" ", "-")
            
            # Look for links containing both teams in the URL or text
            for a in soup.find_all('a', href=True):
                href = a['href']
                if "/partidos/" in href:
                    if (home_slug in href and away_slug in href) or \
                       (home_team.lower() in a.get_text().lower() and away_team.lower() in a.get_text().lower()):
                        match_url = href if href.startswith('http') else f"https://www.futbolfantasy.com{href}"
                        break
            
            if not match_url:
                print(f"  [!] Could not find match URL for {home_team} vs {away_team} on {lineups_url}")
                return None
                
            # 3. Fetch the match page
            print(f"  [>] Fetching referee from match page: {match_url}")
            resp_match = requests.get(match_url, headers=self.headers, timeout=10)
            resp_match.raise_for_status()
            soup_match = BeautifulSoup(resp_match.text, 'html.parser')
            
            # 4. Extract referee
            # Structure: <div class="arbitro">Árbitro: <span class="link">Jesús Gil Manzano</span></div>
            arbitro_div = soup_match.find('div', class_='arbitro')
            if arbitro_div:
                ref_span = arbitro_div.find('span', class_='link')
                if ref_span:
                    referee_name = ref_span.get_text().strip()
                    strictness = self._infer_strictness(referee_name)
                    avg_cards = 5.0 if strictness == RefereeStrictness.HIGH else 3.8
                    
                    return {
                        'name': referee_name,
                        'strictness': strictness,
                        'avg_cards': avg_cards,
                        'source': 'FutbolFantasy',
                        'verification_link': match_url
                    }
            
            return None
            
        except Exception as e:
            print(f"WARNING: FutbolFantasy scraping failed: {e}")
            return None


class LaLigaRefereeScraper(BaseRefereeScraper):
    """Scraper for La Liga referees, prioritizing FutbolFantasy then RFEF."""
    
    def __init__(self):
        super().__init__()
        self.ff_scraper = FutbolFantasyRefereeScraper()
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """
        Scrape referee appointments for La Liga.
        """
        # 1. Try FutbolFantasy (More reliable for specific match scraping)
        result = self.ff_scraper.fetch_referee(home_team, away_team, match_date)
        if result:
            return result
            
        # 2. Try RFEF Official (Backup)
        try:
            url = "https://www.rfef.es/noticias/arbitros/designaciones"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Pattern matching for RFEF
            home_keywords = home_team.lower().split()
            away_keywords = away_team.lower().split()
            
            pattern = rf'({"|".join(home_keywords)}).*?({"|".join(away_keywords)}).*?:?\s*([A-Z][a-z\u00C0-\u017F]+(?:\s[A-Z][a-z\u00C0-\u017F]+)+)'
            match = re.search(pattern, soup.get_text(), re.IGNORECASE)
            
            if match:
                referee_name = match.group(3).strip()
                strictness = self._infer_strictness(referee_name)
                avg_cards = 5.0 if strictness == RefereeStrictness.HIGH else 3.5
                
                return {
                    'name': referee_name,
                    'strictness': strictness,
                    'avg_cards': avg_cards,
                    'source': 'RFEF Official',
                    'verification_link': url
                }
            
        except Exception as e:
            print(f"⚠️ RFEF scraping failed: {e}")
            
        return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        """Return a realistic La Liga referee as fallback."""
        import random
        pool = [
            {'name': 'Gil Manzano', 'strictness': RefereeStrictness.HIGH, 'avg': 5.8},
            {'name': 'Sánchez Martínez', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.5},
            {'name': 'Hernández Hernández', 'strictness': RefereeStrictness.HIGH, 'avg': 5.5},
            {'name': 'Díaz de Mera', 'strictness': RefereeStrictness.LOW, 'avg': 3.8},
            {'name': 'Munuera Montero', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.2}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Fallback Pool'
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
                    'source': 'Premier League Official',
                    'verification_link': url
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ Premier League scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        import random
        pool = [
            {'name': 'Michael Oliver', 'strictness': RefereeStrictness.HIGH, 'avg': 4.9},
            {'name': 'Anthony Taylor', 'strictness': RefereeStrictness.HIGH, 'avg': 5.1},
            {'name': 'Craig Pawson', 'strictness': RefereeStrictness.LOW, 'avg': 3.4},
            {'name': 'Paul Tierney', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.0},
            {'name': 'Simon Hooper', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.2}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Fallback Pool'
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
                    'source': 'AIA-FIGC Official',
                    'verification_link': url
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ AIA scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        import random
        pool = [
            {'name': 'Daniele Orsato', 'strictness': RefereeStrictness.HIGH, 'avg': 5.3},
            {'name': 'Marco Guida', 'strictness': RefereeStrictness.LOW, 'avg': 3.6},
            {'name': 'Davide Massa', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.4},
            {'name': 'Maurizio Mariani', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.1}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Fallback Pool'
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
                    'source': 'DFB Official',
                    'verification_link': url
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ DFB scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        import random
        pool = [
            {'name': 'Felix Brych', 'strictness': RefereeStrictness.HIGH, 'avg': 4.8},
            {'name': 'Tobias Stieler', 'strictness': RefereeStrictness.LOW, 'avg': 3.3},
            {'name': 'Deniz Aytekin', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.0},
            {'name': 'Marco Fritz', 'strictness': RefereeStrictness.MEDIUM, 'avg': 3.9}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Fallback Pool'
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
                    'source': 'LFP/Arbitrez-Vous',
                    'verification_link': url
                }
            
            return self._fallback_referee()
            
        except Exception as e:
            print(f"⚠️ Arbitrez-Vous scraping failed: {e}")
            return self._fallback_referee()
    
    def _fallback_referee(self) -> Dict:
        import random
        pool = [
            {'name': 'Clément Turpin', 'strictness': RefereeStrictness.HIGH, 'avg': 4.7},
            {'name': 'Benoît Bastien', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.0},
            {'name': 'François Letexier', 'strictness': RefereeStrictness.MEDIUM, 'avg': 3.8},
            {'name': 'Jérôme Brisard', 'strictness': RefereeStrictness.LOW, 'avg': 3.3}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Fallback Pool'
        }


class InternationalRefereePoolScraper(BaseRefereeScraper):
    """Generic pool for international and other matches."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        return self._fallback_referee()
            
    def _fallback_referee(self) -> Dict:
        import random
        pool = [
            {'name': 'Glenn Nyberg', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.1},
            {'name': 'Sandro Schärer', 'strictness': RefereeStrictness.HIGH, 'avg': 4.8},
            {'name': 'Erik Lambrechts', 'strictness': RefereeStrictness.MEDIUM, 'avg': 3.9},
            {'name': 'Donatas Rumšas', 'strictness': RefereeStrictness.LOW, 'avg': 3.4},
            {'name': 'Irati Gallastegui', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.2}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'International Pool'
        }


class FallbackRefereeScraper(BaseRefereeScraper):
    """Fallback scraper for unsupported leagues."""
    
    def fetch_referee(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """Return a generic referee for unsupported leagues."""
        import random
        pool = [
            {'name': 'Referee A', 'strictness': RefereeStrictness.MEDIUM, 'avg': 4.0},
            {'name': 'Referee B', 'strictness': RefereeStrictness.HIGH, 'avg': 5.0},
            {'name': 'Referee C', 'strictness': RefereeStrictness.LOW, 'avg': 3.5}
        ]
        ref = random.choice(pool)
        return {
            'name': ref['name'],
            'strictness': ref['strictness'],
            'avg_cards': ref['avg'],
            'source': 'Generic Pool'
        }
