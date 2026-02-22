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
            "Liga Mixta (Combinada)": "la-liga" # Default to La Liga for Mixta search as a starting point
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
        print(f"FETCH: Auto-fetching lineups for {home_team} vs {away_team}...")
        
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
                print(f"  Pattern failed: {pattern} - {str(e)}")
                continue
        
        # If direct URL construction fails, try search
        print("  Direct URL failed, trying search...")
        return self._search_and_fetch(home_team, away_team, match_date)
    
    def _scrape_lineup_page(self, url: str, home_team: str, away_team: str) -> Optional[Dict]:
        """
        Scrape a specific lineup page from SportsGambler.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Strategy: Separate home and away containers
            # SportsGambler uses columns or separate divs for home/away
            containers = soup.find_all(['div', 'table'], class_=re.compile(r'lineup|squad|column', re.I))
            
            home_scraped = set()
            away_scraped = set()
            
            if len(containers) >= 2:
                # Assuming first container is home, second is away
                for i, container in enumerate(containers[:2]):
                    target_set = home_scraped if i == 0 else away_scraped
                    for link in container.find_all('a', href=True):
                        if '/players/' in link['href'] or '/player/' in link['href']:
                            name = link.get_text().strip()
                            if name and len(name.split()) >= 2:
                                target_set.add(name)
            
            # Fallback if container separation failed
            if not home_scraped and not away_scraped:
                extracted_names = set()
                for link in soup.find_all('a', href=True):
                    if '/players/' in link['href'] or '/player/' in link['href']:
                        name = link.get_text().strip()
                        if name and len(name.split()) >= 2:
                            extracted_names.add(name)
                return self._map_to_rosters(extracted_names, home_team, away_team)
            
            # Map specifically to rosters
            return self._map_to_specific_rosters(home_scraped, away_scraped, home_team, away_team)
            
        except requests.RequestException as e:
            return {'error': f'Request failed: {str(e)}'}
            
    def _map_to_specific_rosters(self, home_scraped: set, away_scraped: set, home_team: str, away_team: str) -> Dict:
        """
        Map specifically identified home/away names to rosters.
        """
        found_home = []
        found_away = []
        
        team_home = self.data_provider.get_team_data(home_team)
        team_away = self.data_provider.get_team_data(away_team)
        
        def fuzzy_match(scraped_name, roster):
            scraped_tokens = set(scraped_name.lower().split())
            for player in roster:
                player_tokens = set(player.name.lower().split())
                if player_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(player_tokens):
                    return player.name
                if len(scraped_tokens.intersection(player_tokens)) >= 1:
                    return player.name
            return None

        # Process Home
        for name in home_scraped:
            match = fuzzy_match(name, team_home.players)
            if match: found_home.append(match)
            else: found_home.append(name) # Keep raw name if no match (important for new teams)
            
        # Process Away
        for name in away_scraped:
            match = fuzzy_match(name, team_away.players)
            if match: found_away.append(match)
            else: found_away.append(name) # Keep raw name if no match
            
        return {
            'home': sorted(list(set(found_home))),
            'away': sorted(list(set(found_away))),
            'count': len(found_home) + len(found_away),
            'status': 'confirmed' if len(found_home) + len(found_away) >= 20 else 'predicted',
            'note': 'Nuevos jugadores detectados' if any(n not in [p.name for p in team_home.players + team_away.players] for n in found_home + found_away) else ''
        }
    
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
                
                # Check if both teams are mentioned (normalized)
                home_norm = self._normalize_team_name(home_team).replace('-', ' ')
                away_norm = self._normalize_team_name(away_team).replace('-', ' ')
                
                home_match = home_norm in text or home_norm in href.replace('-', ' ')
                away_match = away_norm in text or away_norm in href.replace('-', ' ')
                
                if (home_match or away_match) and '/lineups/' in href:
                    full_url = self.BASE_URL + href if href.startswith('/') else href
                    # If we found a link for either, try it
                    result = self._scrape_lineup_page(full_url, home_team, away_team)
                    if result and not result.get('error') and result.get('count', 0) > 10:
                        result['source'] = full_url
                        return result
            
            return {'error': 'Match not found on SportsGambler', 'home': [], 'away': []}
            
        except Exception as e:
            return {'error': f'Search failed: {str(e)}', 'home': [], 'away': []}

    def fetch_injuries_auto(self, league: str) -> Dict[str, List[Dict]]:
        """
        Scrapes the injury report for a specific league from SportsGambler.
        """
        league_map = {
            "La Liga": "spain-la-liga",
            "Premier League": "england-premier-league",
            "Serie A": "italy-serie-a",
            "Bundesliga": "germany-bundesliga",
            "Ligue 1": "france-ligue-1"
        }
        
        league_slug = league_map.get(league)
        if not league_slug:
            # Fallback: Try a generic football injury search page or scan all
            return self._scan_all_injuries()
            
        url = f"{self.BASE_URL}/injuries/football/{league_slug}/"
        print(f"🔍 Fetching injuries from: {url}")
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            injuries_db = {}
            # SportsGambler structure: h3 with team name, followed by table of injuries
            current_team = None
            
            for elem in soup.find_all(['h3', 'tr']):
                if elem.name == 'h3':
                    current_team = elem.get_text().strip()
                    injuries_db[current_team] = []
                elif elem.name == 'tr' and current_team:
                    cells = elem.find_all('td')
                    if len(cells) >= 3:
                        player = cells[0].get_text().strip()
                        reason = cells[1].get_text().strip()
                        status = cells[2].get_text().strip()
                        if player and player != "Player":
                            injuries_db[current_team].append({
                                'player': player,
                                'reason': reason,
                                'status': status
                            })
            return injuries_db
        except Exception as e:
            print(f"  ❌ Injury fetch failed: {e}")
            return {}

    def _scan_all_injuries(self) -> Dict[str, List[Dict]]:
        """
        Scan a more global injury page for matches.
        """
        try:
            url = f"{self.BASE_URL}/injuries/football/"
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            injuries_db = {}
            current_team = None
            for elem in soup.find_all(['h3', 'tr']):
                if elem.name == 'h3':
                    current_team = elem.get_text().strip()
                    injuries_db[current_team] = []
                elif elem.name == 'tr' and current_team:
                    cells = elem.find_all('td')
                    if len(cells) >= 3:
                        injuries_db[current_team].append({
                            'player': cells[0].get_text().strip(),
                            'reason': cells[1].get_text().strip(),
                            'status': cells[2].get_text().strip(),
                            'source': url
                        })
            return injuries_db
        except:
            return {}
    
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
