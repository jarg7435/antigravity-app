import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
import re
from src.data.interface import DataProvider


class AutoLineupFetcher:
    """
    Automatically fetches lineups from SportsGambler.com without manual URL input.
    Constructs match URLs based on team names and dates.
    """
    
    BASE_URL = "https://www.sportsgambler.com"
    
    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _normalize_team_name(self, team_name: str) -> str:
        """
        Normalize team name for URL construction.
        Examples: 'Real Madrid' -> 'real-madrid', 'FC Barcelona' -> 'barcelona'
        """
        # Remove common prefixes
        name = re.sub(r'^(FC|CF|CD|UD|SD|RCD|Athletic|Real)\s+', '', team_name, flags=re.IGNORECASE)
        # Convert to lowercase and replace spaces with hyphens
        name = name.lower().strip()
        name = re.sub(r'[^a-z0-9\s-]', '', name)  # Remove special chars
        name = re.sub(r'\s+', '-', name)  # Replace spaces with hyphens
        return name
    
    def build_match_url(self, home_team: str, away_team: str, match_date: datetime, league: str) -> List[str]:
        """
        Construct SportsGambler match URL.
        Pattern: /lineups/football/{league}/{home-team}-vs-{away-team}/
        """
        home_slug = self._normalize_team_name(home_team)
        away_slug = self._normalize_team_name(away_team)
        
        # Map league names to SportsGambler slugs
        league_map = {
            "La Liga": "la-liga",
            "Premier League": "premier-league",
            "Serie A": "serie-a",
            "Bundesliga": "bundesliga",
            "Ligue 1": "ligue-1",
            "Champions League": "champions-league",
            "Europa League": "europa-league"
        }
        
        league_slug = league_map.get(league, league.lower().replace(" ", "-"))
        
        # Try multiple URL patterns
        patterns = [
            f"/lineups/football/{league_slug}/{home_slug}-vs-{away_slug}/",
            f"/lineups/football/{home_slug}-vs-{away_slug}/",
            f"/lineups/{home_slug}-vs-{away_slug}/"
        ]
        
        return patterns
    
    def fetch_lineups_auto(self, home_team: str, away_team: str, match_date: datetime, league: str) -> Dict:
        """
        Automatically fetch lineups from SportsGambler without manual URL.
        
        Returns:
            {
                'home': List[str],
                'away': List[str],
                'source': str,
                'count': int,
                'status': 'confirmed' | 'predicted'
            }
        """
        print(f"🔍 Auto-fetching lineups for {home_team} vs {away_team}...")
        
        # Try different URL patterns
        url_patterns = self.build_match_url(home_team, away_team, match_date, league)
        
        for pattern in url_patterns:
            url = self.BASE_URL + pattern
            try:
                result = self._scrape_lineup_page(url, home_team, away_team)
                if result and not result.get('error'):
                    result['source'] = url
                    return result
            except Exception as e:
                print(f"  ⚠️ Pattern failed: {pattern} - {str(e)}")
                continue
        
        # If direct URL construction fails, try search
        print("  🔎 Direct URL failed, trying search...")
        return self._search_and_fetch(home_team, away_team, match_date)
    
    def _scrape_lineup_page(self, url: str, home_team: str, away_team: str) -> Optional[Dict]:
        """
        Scrape a specific lineup page from SportsGambler.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract player names
            extracted_names = set()
            
            # Strategy 1: Find player links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/players/' in href or '/player/' in href:
                    name = link.get_text().strip()
                    if name and len(name.split()) >= 2:
                        extracted_names.add(name)
            
            # Strategy 2: Find elements with player class names
            for elem in soup.find_all(class_=re.compile(r'player|lineup|squad', re.I)):
                text = elem.get_text().strip()
                # Extract names (2+ words starting with capital)
                names = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b', text)
                extracted_names.update(names)
            
            # Strategy 3: Look for structured lineup data
            for elem in soup.find_all(['div', 'li', 'span'], class_=re.compile(r'name', re.I)):
                text = elem.get_text().strip()
                if text and len(text.split()) >= 2:
                    extracted_names.add(text)
            
            if not extracted_names:
                return {'error': 'No players found on page'}
            
            # Map to team rosters
            return self._map_to_rosters(extracted_names, home_team, away_team)
            
        except requests.RequestException as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def _search_and_fetch(self, home_team: str, away_team: str, match_date: datetime) -> Dict:
        """
        Fallback: Search SportsGambler for the match.
        """
        try:
            # Search on main lineups page
            search_url = f"{self.BASE_URL}/lineups/football/"
            resp = requests.get(search_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Look for match links containing both team names
            home_keywords = self._normalize_team_name(home_team).split('-')
            away_keywords = self._normalize_team_name(away_team).split('-')
            
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                text = link.get_text().lower()
                
                # Check if both teams are mentioned
                home_match = any(kw in href or kw in text for kw in home_keywords)
                away_match = any(kw in href or kw in text for kw in away_keywords)
                
                if home_match and away_match and '/lineups/' in href:
                    full_url = self.BASE_URL + href if href.startswith('/') else href
                    result = self._scrape_lineup_page(full_url, home_team, away_team)
                    if result and not result.get('error'):
                        result['source'] = full_url
                        return result
            
            return {'error': 'Match not found on SportsGambler', 'home': [], 'away': []}
            
        except Exception as e:
            return {'error': f'Search failed: {str(e)}', 'home': [], 'away': []}
    
    def _map_to_rosters(self, extracted_names: set, home_team: str, away_team: str) -> Dict:
        """
        Map extracted names to team rosters using fuzzy matching.
        """
        found_home = []
        found_away = []
        
        team_home = self.data_provider.get_team_data(home_team)
        team_away = self.data_provider.get_team_data(away_team)
        
        def fuzzy_match(scraped_name, roster):
            scraped_tokens = set(scraped_name.lower().split())
            if not scraped_tokens:
                return None
            
            for player in roster:
                player_tokens = set(player.name.lower().split())
                # Match if tokens overlap significantly
                if player_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(player_tokens):
                    return player.name
                if len(scraped_tokens.intersection(player_tokens)) >= 1:
                    return player.name
            return None
        
        # Map to home team
        if team_home:
            for name in extracted_names:
                match = fuzzy_match(name, team_home.players)
                if match and match not in found_home:
                    found_home.append(match)
        
        # Map to away team
        if team_away:
            for name in extracted_names:
                match = fuzzy_match(name, team_away.players)
                if match and match not in found_away:
                    found_away.append(match)
        
        # Determine status (confirmed vs predicted)
        status = 'confirmed' if len(found_home) + len(found_away) >= 18 else 'predicted'
        
        return {
            'home': sorted(found_home),
            'away': sorted(found_away),
            'count': len(found_home) + len(found_away),
            'status': status
        }
