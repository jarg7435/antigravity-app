"""Test del scraper de FutbolFantasy."""
import sys
sys.path.insert(0, '.')
from src.data.scrapers.futbolfantasy_scraper import fetch_lineup_and_referee, find_match_url

# Test La Liga
print('--- La Liga: Real Madrid vs Atletico ---')
data = fetch_lineup_and_referee('Real Madrid', 'Atletico Madrid', 'La Liga')
print('Arbitro:', data.get('referee'))
print('Local:', data.get('home', [])[:5])
print('Visitante:', data.get('away', [])[:5])
print('Link:', data.get('verification_link'))
print('Fallback:', data.get('_is_fallback'))

print()

# Test Serie A  
print('--- Serie A: Lazio vs Milan (manana) ---')
url = find_match_url('Lazio', 'Milan', 'Serie A')
print('URL encontrada:', url)

print()

# Test Premier League
print('--- Premier: Liverpool vs Tottenham ---')
url2 = find_match_url('Liverpool', 'Tottenham', 'Premier League')
print('URL encontrada:', url2)
