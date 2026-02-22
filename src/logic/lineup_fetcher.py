from typing import List, Dict
import time
from datetime import datetime
from src.data.interface import DataProvider
from src.data.auto_lineup_fetcher import AutoLineupFetcher
from src.data.referee_source_mapper import RefereeSourceMapper

class LineupFetcher:
    """
    Simulates fetching official lineups from an external source (e.g., Flashscore).
    In a real implementation, this would use Selenium/Soup to parse the match page.
    For this 'Auto-Blindaje' demo, it queries the internal reliable data provider
    Assuming the 'Internal DB' has the ground truth.
    """
    
    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider
        self.auto_fetcher = AutoLineupFetcher(data_provider)

    def fetch_confirmed_lineup(self, team_name: str, match_time: str) -> List[str]:
        """
        Simulates network call to get confirmed lineup 1 hour before match_time.
        Returns list of player names.
        """
        print(f"[*] Checking lineups 1 hour before {match_time}...")
        # Simulate Network Latency
        time.sleep(1.0) 
        
        # In this demo, we assume our internal DB has the ground truth for confirmed lineups
        team = self.data_provider.get_team_data(team_name)
        return [p.name for p in team.players]

    def fetch_match_referee(self, home_team: str, away_team: str, match_date: datetime, league: str) -> dict:
        """
        Fetches the assigned referee from official league sources.
        Falls back to realistic pool if scraping fails.
        """
        print(f"🔍 Auto-fetching referee for {league}...")
        
        # Get league-specific scraper
        scraper = RefereeSourceMapper.get_scraper(league)
        
        # Fetch referee
        result = scraper.fetch_referee(home_team, away_team, match_date)
        
        print(f"  ✅ Referee: {result['name']} (Source: {result.get('source', 'Unknown')})")
        
        return result

    def fetch_injuries(self, league: str) -> Dict:
        """Fetch injury report for a league."""
        return self.auto_fetcher.fetch_injuries_auto(league)

    def fetch_from_url(self, url: str, home_team_name: str, away_team_name: str) -> dict:
        """
        Scrapes a sports site for lineups using requests and BeautifulSoup.
        """
        import requests
        from bs4 import BeautifulSoup
        import re
        
        print(f"📡 Accessing: {url} ...")
        
        extracted_names = set()
        
        try:
            # 1. Fetch Content
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # --- FIX: Handle Redirect to Main Page / Multiple Matches ---
            # If we are on the main lineups page, we need to find the specific match ID and fetch via AJAX
            page_title = soup.title.string if soup.title else ""
            if "Football Lineups" in page_title or len(soup.find_all(class_='lineup-row')) > 5:
                print(f"  ⚠️ Redirected to main page. Searching for match: {home_team_name} vs {away_team_name}...")
                
                # Normalize names for search (simple check)
                home_simple = home_team_name.split()[0] if home_team_name else ""
                away_simple = away_team_name.split()[0] if away_team_name else ""
                
                # Find the match container
                # We look for a container that has both team names
                found_id = None
                
                # Regex search in HTML to be robust
                # Look for home team, then away team (or vice-versa), then reply_click
                # This is a bit expensive but robust
                import re
                
                # Pattern: Team1 ... Team2 ... reply_click(ID) (or Team2 ... Team1)
                # We limit the distance to avoid false positives from different matches
                
                # Try finding the row first
                rows = soup.find_all(class_='lineup-row')
                for row in rows:
                    row_text = row.get_text()
                    if home_simple in row_text and away_simple in row_text:
                        # Found the row, now get the ID
                        link = row.find('a', class_='view-lineups')
                        if link and link.get('id'):
                            found_id = link.get('id')
                            print(f"  ✅ Found match ID: {found_id}")
                            break
                            
                if found_id:
                    ajax_url = f"https://www.sportsgambler.com/lineups/lineups-load2.php?id={found_id}"
                    print(f"  🔄 Fetching AJAX content: {ajax_url}")
                    resp_ajax = requests.get(ajax_url, headers=headers, timeout=10)
                    if resp_ajax.status_code == 200:
                        html = resp_ajax.text
                        soup = BeautifulSoup(html, 'html.parser')
                    else:
                        print(f"  ❌ AJAX fetch failed: {resp_ajax.status_code}")
                else:
                    print("  ❌ Could not find match on main page.")
            
            # 2. Extract Names (Multiple Strategies)
            
            # Strategy A: Links containing 'jugadores/' or 'player/' (Updated for AJAX content)
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if 'jugadores/' in href or 'player/' in href:
                    # Try text first, then slug
                    name = a.get_text().strip()
                    if name and len(name.split()) > 1:
                        extracted_names.add(name)
                    else:
                        slug = href.split('/')[-1].replace("-", " ").title()
                        if len(slug) > 3:
                            extracted_names.add(slug)

            # Strategy B: Images with alt tags (common in lineup grids)
            for img in soup.find_all('img', alt=True):
                alt = img['alt'].strip()
                if alt and len(alt.split()) > 1:
                    # Filter out non-player info
                    if not any(x in alt.lower() for x in ["escudo", "logo", "estadio", "entrenador"]):
                        extracted_names.add(alt)

            # Strategy C: Raw text with regex (Fallback)
            # Find names like "Iago Aspas", "L. Messi"
            # This is risky but can work if scraping fails
            raw_regex = re.findall(r'>\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)\s*<', html)
            for name in raw_regex:
                extracted_names.add(name)

            # Strategy D: Spans with class 'player-name' (Common in AJAX loaded lineups)
            for span in soup.find_all('span', class_='player-name'):
                name = span.get_text().strip()
                if name and len(name.split()) > 1:
                    extracted_names.add(name)

        except Exception as e:
            return {"error": f"Scraping failed: {str(e)}", "home": [], "away": []}

        # 3. Smart Sorting (Map found names to Rosters)
        found_home = []
        found_away = []
        
        team_home = self.data_provider.get_team_data(home_team_name)
        team_away = self.data_provider.get_team_data(away_team_name)
        
        def fuzzy_match(scraped_name, roster):
            # Token-based match with high precision
            scraped_tokens = set(scraped_name.lower().split())
            if not scraped_tokens: return None
            
            for p in roster:
                p_tokens = set(p.name.lower().split())
                # If all tokens of the roster name are in the scraped name, or vice versa
                if p_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(p_tokens):
                    return p.name
                # Partial match (e.g. "Aspas" match "Iago Aspas")
                if len(scraped_tokens.intersection(p_tokens)) >= 1:
                    # Extra check for common surnames
                    return p.name
            return None

        # Process Home
        if team_home:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_home.players)
                if match and match not in found_home:
                    found_home.append(match)
                    
        # Process Away
        if team_away:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_away.players)
                if match and match not in found_away:
                    found_away.append(match)
        
        # 4. Result Verification
        if not found_home and not found_away:

             
             return {"error": "No se detectaron jugadores conocidos en el enlace.", "home": [], "away": []}
             
        return {
            "home": sorted(found_home),
            "away": sorted(found_away),
            "source": url,
            "count": len(found_home) + len(found_away)
        }

    def extract_from_image(self, image_bytes: bytes, home_team_name: str, away_team_name: str) -> dict:
        """
        Processes an image (bytes) to extract player names using OCR.
        """
        import pytesseract
        from PIL import Image
        import io
        import re
        
        print(f"📸 Processing image for {home_team_name} vs {away_team_name}...")
        
        try:
            # 1. Load Image
            img = Image.open(io.BytesIO(image_bytes))
            
            # 2. OCR Extraction
            text = pytesseract.image_to_string(img, lang='spa+eng')
            
            # 3. Text Cleaning & Name Extraction
            lines = text.split('\n')
            extracted_names = set()
            
            for line in lines:
                clean = line.strip()
                # Basic name filter: at least 2 words, no numbers/symbols
                if len(clean.split()) >= 2 and re.match(r'^[A-Z][a-z\u00C0-\u017F]+(?:\s[A-Z][a-z\u00C0-\u017F]+)+$', clean):
                    extracted_names.add(clean)
                else:
                    # Fallback: look for names within line
                    matches = re.findall(r'([A-Z][a-z\u00C0-\u017F]+(?:\s[A-Z][a-z\u00C0-\u017F]+)+)', clean)
                    for m in matches:
                        extracted_names.add(m)

            if not extracted_names:
                # Last resort: just get all words and try fuzzy matching later
                words = re.findall(r'\b[A-Z][a-z\u00C0-\u017F]+\b', text)
                extracted_names = set(words)

        except Exception as e:
            return {"error": f"OCR failed: {str(e)}. Asegúrate de que Tesseract está instalado.", "home": [], "away": []}

        # 4. Sorting with Existing Logic
        found_home = []
        found_away = []
        
        team_home = self.data_provider.get_team_data(home_team_name)
        team_away = self.data_provider.get_team_data(away_team_name)
        
        def fuzzy_match(scraped_name, roster):
            scraped_tokens = set(scraped_name.lower().split())
            if not scraped_tokens: return None
            for p in roster:
                p_tokens = set(p.name.lower().split())
                if p_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(p_tokens):
                    return p.name
                if len(scraped_tokens.intersection(p_tokens)) >= 1:
                    return p.name
            return None

        if team_home:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_home.players)
                if match and match not in found_home:
                    found_home.append(match)
                    
        if team_away:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_away.players)
                if match and match not in found_away:
                    found_away.append(match)
        
        if not found_home and not found_away:
             return {"error": "No se reconocieron nombres de jugadores conocidos en la imagen.", "home": [], "away": []}
             
        return {
            "home": sorted(found_home),
            "away": sorted(found_away),
            "count": len(found_home) + len(found_away),
            "method": "OCR"
        }
