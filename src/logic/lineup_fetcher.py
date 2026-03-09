"""
LineupFetcher — Sistema de obtención de árbitros y alineaciones
================================================================
Usa la API pública de SofaScore (JSON, sin JS, funciona en Streamlit Cloud)
como fuente principal, con BeSoccer y fallback manual como respaldo.

Flujo para árbitro:
  1. SofaScore API → busca el partido → extrae árbitro del JSON
  2. BeSoccer → scraping simple requests
  3. Fallback pool (determinista por equipos)

Flujo para alineaciones:
  1. SofaScore API → busca el partido → extrae alineaciones del JSON
  2. BD interna (último partido conocido)
"""

from typing import List, Dict, Optional
import time
import requests
import re
from datetime import datetime, timedelta
from src.data.interface import DataProvider
from src.data.auto_lineup_fetcher import AutoLineupFetcher
from src.data.referee_source_mapper import RefereeSourceMapper
from src.data.multi_source_fetcher import MultiSourceFetcher

HEADERS_SOFA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Referer': 'https://www.sofascore.com/',
    'Origin': 'https://www.sofascore.com',
}

HEADERS_WEB = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

# Mapa de ligas a IDs de SofaScore
LEAGUE_TO_SOFASCORE = {
    'La Liga': {'id': 8, 'season': '58766'},
    'la liga': {'id': 8, 'season': '58766'},
    'Premier League': {'id': 17, 'season': '61627'},
    'Serie A': {'id': 23, 'season': '58587'},
    'Bundesliga': {'id': 35, 'season': '58558'},
    'Ligue 1': {'id': 34, 'season': '57051'},
    # Segunda División / Championship / etc
    'Segunda División': {'id': 54, 'season': '58856'},
    'Championship': {'id': 18, 'season': '61643'},
}

# Pools de árbitros por liga para fallback
REFEREE_POOLS = {
    'La Liga': [
        {'name': 'Jesús Gil Manzano', 'avg_cards': 5.8},
        {'name': 'Ricardo de Burgos Bengoechea', 'avg_cards': 4.1},
        {'name': 'Sánchez Martínez', 'avg_cards': 4.5},
        {'name': 'Hernández Hernández', 'avg_cards': 5.5},
        {'name': 'Munuera Montero', 'avg_cards': 4.2},
        {'name': 'Del Cerro Grande', 'avg_cards': 4.0},
        {'name': 'Cuadra Fernández', 'avg_cards': 3.9},
        {'name': 'Figueroa Vázquez', 'avg_cards': 4.3},
        {'name': 'Mateu Lahoz', 'avg_cards': 6.1},
        {'name': 'Trujillo Suárez', 'avg_cards': 4.1},
    ],
    'Premier League': [
        {'name': 'Michael Oliver', 'avg_cards': 4.2},
        {'name': 'Anthony Taylor', 'avg_cards': 4.8},
        {'name': 'Stuart Attwell', 'avg_cards': 3.9},
        {'name': 'Chris Kavanagh', 'avg_cards': 4.5},
    ],
    'Serie A': [
        {'name': 'Daniele Orsato', 'avg_cards': 4.5},
        {'name': 'Gianluca Rocchi', 'avg_cards': 3.8},
        {'name': 'Marco Guida', 'avg_cards': 4.1},
    ],
    'Bundesliga': [
        {'name': 'Felix Brych', 'avg_cards': 4.3},
        {'name': 'Daniel Siebert', 'avg_cards': 4.6},
        {'name': 'Tobias Welz', 'avg_cards': 3.9},
    ],
    'Ligue 1': [
        {'name': 'Clément Turpin', 'avg_cards': 4.4},
        {'name': 'François Letexier', 'avg_cards': 4.1},
        {'name': 'Benoît Bastien', 'avg_cards': 4.8},
    ],
}


def _normalize_team(name: str) -> str:
    """Normaliza nombre de equipo para comparación."""
    replacements = {
        'fc barcelona': 'barcelona', 'fc': '', 'cf': '', 'cd': '',
        'real madrid': 'real madrid', 'athletic bilbao': 'athletic club',
        'atletico': 'atlético', 'espanol': 'espanyol', 'español': 'espanyol',
    }
    n = name.lower().strip()
    for k, v in replacements.items():
        n = n.replace(k, v)
    return n.strip()


def _teams_match(sofa_name: str, query_name: str) -> bool:
    """Comprueba si dos nombres de equipos coinciden."""
    s = _normalize_team(sofa_name)
    q = _normalize_team(query_name)
    # Exact or contained match
    if s == q or q in s or s in q:
        return True
    # Word-level match: at least 1 significant word in common
    s_words = set(w for w in s.split() if len(w) > 3)
    q_words = set(w for w in q.split() if len(w) > 3)
    return bool(s_words & q_words)


def _get_sofascore_event_id(home: str, away: str, match_date: datetime, league: str) -> Optional[int]:
    """
    Busca el event_id de un partido en SofaScore usando la API pública.
    Intenta varios métodos: búsqueda por fecha de liga y búsqueda directa.
    """
    # Normalizar nombre de liga
    league_norm = league
    for key in LEAGUE_TO_SOFASCORE:
        if key.lower() in league.lower():
            league_norm = key
            break

    league_info = LEAGUE_TO_SOFASCORE.get(league_norm)

    # Método 1: Buscar partidos del día en la liga
    date_str = match_date.strftime('%Y-%m-%d')
    urls_to_try = []

    if league_info:
        urls_to_try.append(
            f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}"
        )
        # También probar con la liga específica
        urls_to_try.append(
            f"https://api.sofascore.com/api/v1/unique-tournament/{league_info['id']}/season/{league_info['season']}/events/round/last"
        )

    # Método 2: Búsqueda directa por equipos
    urls_to_try.append(
        f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}"
    )

    for url in urls_to_try:
        try:
            resp = requests.get(url, headers=HEADERS_SOFA, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            events = data.get('events', [])

            for event in events:
                h_name = event.get('homeTeam', {}).get('name', '')
                a_name = event.get('awayTeam', {}).get('name', '')
                if _teams_match(h_name, home) and _teams_match(a_name, away):
                    return event.get('id')
                # También probar al revés (por si los equipos están invertidos)
                if _teams_match(h_name, away) and _teams_match(a_name, home):
                    return event.get('id')

        except Exception as e:
            print(f"    [SofaScore] Error buscando evento {url}: {e}")

    # Método 3: Buscar en los próximos 3 días también
    for delta in [-1, 1, 2]:
        try:
            alt_date = (match_date + timedelta(days=delta)).strftime('%Y-%m-%d')
            url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{alt_date}"
            resp = requests.get(url, headers=HEADERS_SOFA, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for event in data.get('events', []):
                h_name = event.get('homeTeam', {}).get('name', '')
                a_name = event.get('awayTeam', {}).get('name', '')
                if _teams_match(h_name, home) and _teams_match(a_name, away):
                    return event.get('id')
        except Exception:
            pass

    return None


def fetch_referee_sofascore(home: str, away: str, match_date: datetime, league: str) -> Optional[Dict]:
    """
    Obtiene el árbitro de un partido vía API JSON de SofaScore.
    No necesita JavaScript ni scraping — funciona en Streamlit Cloud.
    """
    print(f"    [SofaScore] Buscando árbitro: {home} vs {away}")

    event_id = _get_sofascore_event_id(home, away, match_date, league)
    if not event_id:
        print(f"    [SofaScore] Partido no encontrado en la API")
        return None

    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}"
        resp = requests.get(url, headers=HEADERS_SOFA, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        event = data.get('event', {})
        referee = event.get('referee', {})
        ref_name = referee.get('name', '').strip()

        if ref_name and len(ref_name.split()) >= 2:
            print(f"    [SofaScore] ✅ Árbitro encontrado: {ref_name}")
            return {
                'name': ref_name,
                'source': 'SofaScore',
                'verification_link': f"https://www.sofascore.com/es/partido/{event_id}",
                '_is_fallback': False,
                '_event_id': event_id
            }
    except Exception as e:
        print(f"    [SofaScore] Error obteniendo detalles: {e}")

    return None


def fetch_lineups_sofascore(home: str, away: str, match_date: datetime, league: str, event_id: int = None) -> Optional[Dict]:
    """
    Obtiene las alineaciones confirmadas de un partido vía API JSON de SofaScore.
    """
    print(f"    [SofaScore] Buscando alineaciones: {home} vs {away}")

    if not event_id:
        event_id = _get_sofascore_event_id(home, away, match_date, league)
    if not event_id:
        print(f"    [SofaScore] Partido no encontrado para alineaciones")
        return None

    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/lineups"
        resp = requests.get(url, headers=HEADERS_SOFA, timeout=10)
        if resp.status_code != 200:
            print(f"    [SofaScore] Alineaciones no disponibles aún (HTTP {resp.status_code})")
            return None

        data = resp.json()
        home_lineup = data.get('home', {})
        away_lineup = data.get('away', {})

        home_players = []
        away_players = []
        bajas = []

        # Extraer titulares del equipo local
        for player in home_lineup.get('players', []):
            p = player.get('player', {})
            name = p.get('name', '') or p.get('shortName', '')
            position = player.get('position', '')
            if player.get('substitute', False) is False and name:
                home_players.append(name)
            elif name and player.get('substitute', True):
                pass  # suplente, ignorar por ahora

        # Extraer titulares del equipo visitante
        for player in away_lineup.get('players', []):
            p = player.get('player', {})
            name = p.get('name', '') or p.get('shortName', '')
            if player.get('substitute', False) is False and name:
                away_players.append(name)

        # Si no hay datos de substitute flag, usar los primeros 11
        if not home_players:
            all_home = [
                (pl.get('player', {}).get('name', '') or pl.get('player', {}).get('shortName', ''))
                for pl in home_lineup.get('players', [])
                if pl.get('player', {}).get('name', '')
            ]
            home_players = all_home[:11]

        if not away_players:
            all_away = [
                (pl.get('player', {}).get('name', '') or pl.get('player', {}).get('shortName', ''))
                for pl in away_lineup.get('players', [])
                if pl.get('player', {}).get('name', '')
            ]
            away_players = all_away[:11]

        if home_players or away_players:
            print(f"    [SofaScore] ✅ Alineaciones: {len(home_players)} local + {len(away_players)} visitante")
            return {
                'home': home_players[:11],
                'away': away_players[:11],
                'bajas': bajas,
                'source': f'SofaScore (confirmadas)',
                'verification_link': f"https://www.sofascore.com/es/partido/{event_id}",
                '_is_fallback': False
            }
    except Exception as e:
        print(f"    [SofaScore] Error obteniendo alineaciones: {e}")

    return None


def fetch_referee_besoccer(home: str, away: str) -> Optional[Dict]:
    """
    Intenta obtener árbitro de BeSoccer via requests simples.
    """
    import unicodedata

    def slugify(name):
        name = unicodedata.normalize('NFD', name)
        name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
        return name.lower().replace(' ', '-').replace('.', '').replace("'", '').replace('ñ', 'n')

    slugs_home = [slugify(home), slugify(home.split()[-1])]
    slugs_away = [slugify(away), slugify(away.split()[-1])]

    urls = []
    for sh in slugs_home:
        for sa in slugs_away:
            urls.append(f"https://es.besoccer.com/partido/{sh}-{sa}")

    from bs4 import BeautifulSoup

    for url in urls[:3]:
        try:
            resp = requests.get(url, headers=HEADERS_WEB, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Estrategia 1: clases específicas
            for el in soup.find_all(class_=re.compile(r'referee|arbitro|juez|ref-name', re.I)):
                name = el.get_text(separator=' ', strip=True)
                name = re.sub(r'[Áá]rbitro[:\s]*', '', name).strip()
                if 2 <= len(name.split()) <= 4 and not name[0].isdigit():
                    return {'name': name, 'source': 'BeSoccer', 'verification_link': url, '_is_fallback': False}

            # Estrategia 2: búsqueda en texto
            for line in soup.get_text(separator='\n').split('\n'):
                line = line.strip()
                if ('árbitro' in line.lower() or 'arbitro' in line.lower()) and len(line) < 80:
                    name = re.sub(r'[Áá]rbitro[:\s]*', '', line, flags=re.I).strip()
                    if 2 <= len(name.split()) <= 4:
                        return {'name': name, 'source': 'BeSoccer', 'verification_link': url, '_is_fallback': False}
        except Exception as e:
            print(f"    [BeSoccer] Error: {e}")

    return None


def _fallback_referee(home: str, away: str, match_date: datetime, league: str) -> Dict:
    """Devuelve un árbitro del pool de referencia (determinista por partido)."""
    import hashlib
    from src.models.base import RefereeStrictness

    # Normalizar liga
    pool = REFEREE_POOLS.get('La Liga')  # default
    for key in REFEREE_POOLS:
        if key.lower() in league.lower():
            pool = REFEREE_POOLS[key]
            break

    match_id = f"{home}-{away}-{match_date.strftime('%Y%m%d')}"
    idx = int(hashlib.md5(match_id.encode()).hexdigest(), 16) % len(pool)
    ref = pool[idx]

    return {
        'name': ref['name'],
        'avg_cards': ref['avg_cards'],
        'strictness': RefereeStrictness.MEDIUM,
        'source': 'Pool de referencia (introduce árbitro manualmente si lo conoces)',
        'verification_link': 'https://www.rfef.es/noticias/arbitros/designaciones',
        '_is_fallback': True
    }


def _enrich_referee(ref: Dict) -> Dict:
    """Añade strictness y avg_cards al dict de árbitro."""
    from src.models.base import RefereeStrictness
    name = ref.get('name', '').lower()

    strict = ['gil manzano', 'hernández hernández', 'mateu lahoz', 'taylor', 'brych']
    lenient = ['díaz de mera', 'munuera', 'del cerro', 'trujillo', 'oliver', 'turpin']

    if any(s in name for s in strict):
        ref['strictness'] = RefereeStrictness.HIGH
        ref['avg_cards'] = ref.get('avg_cards', 5.5)
    elif any(s in name for s in lenient):
        ref['strictness'] = RefereeStrictness.LOW
        ref['avg_cards'] = ref.get('avg_cards', 3.8)
    else:
        ref['strictness'] = RefereeStrictness.MEDIUM
        ref['avg_cards'] = ref.get('avg_cards', 4.3)

    ref.setdefault('_is_fallback', False)
    return ref


class LineupFetcher:
    """
    Obtiene alineaciones y árbitros para partidos de fútbol.
    Usa SofaScore API (JSON) como fuente principal — funciona en Streamlit Cloud.
    """

    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider
        try:
            self.auto_fetcher = AutoLineupFetcher(data_provider)
        except Exception:
            self.auto_fetcher = None
        try:
            self.ms_fetcher = MultiSourceFetcher()
        except Exception:
            self.ms_fetcher = None

    def fetch_confirmed_lineup(self, team_name: str, match_time: str) -> List[str]:
        """Devuelve lista de jugadores del último partido conocido."""
        try:
            team = self.data_provider.get_team_data(team_name)
            return [p.name for p in team.players[:11]]
        except Exception:
            return []

    def fetch_smart_lineup(self, home_team_name: str, away_team_name: str,
                           match_datetime: datetime, league: str) -> Dict:
        """
        Obtiene alineaciones usando SofaScore API primero, luego BD interna.
        Siempre devuelve un resultado válido — nunca lanza excepción.
        """
        def safe_db_fallback(msg: str) -> Dict:
            try:
                home_last = self.data_provider.get_last_match_lineup(home_team_name)
                away_last = self.data_provider.get_last_match_lineup(away_team_name)
            except Exception:
                home_last, away_last = [], []
            return {
                'home': home_last, 'away': away_last,
                'bajas_detectadas': [],
                'source': msg,
                'count': len(home_last) + len(away_last),
                'status': 'fallback',
                'is_official': False
            }

        try:
            # Asegurar que match_datetime es un objeto datetime válido
            if not isinstance(match_datetime, datetime):
                try:
                    match_datetime = datetime.combine(match_datetime, datetime.min.time())
                except Exception:
                    match_datetime = datetime.now()

            # 1. Intentar SofaScore API
            print(f"[LineupFetcher] Buscando alineaciones en SofaScore: {home_team_name} vs {away_team_name}")
            sofa_result = fetch_lineups_sofascore(home_team_name, away_team_name, match_datetime, league)

            if sofa_result and (sofa_result.get('home') or sofa_result.get('away')):
                return {
                    'home': sofa_result['home'],
                    'away': sofa_result['away'],
                    'bajas_detectadas': sofa_result.get('bajas', []),
                    'source': sofa_result.get('source', 'SofaScore'),
                    'count': len(sofa_result['home']) + len(sofa_result['away']),
                    'status': 'confirmed' if sofa_result['home'] else 'predicted',
                    'is_official': True,
                    'verification_link': sofa_result.get('verification_link')
                }

            # 2. Intentar MultiSourceFetcher si está disponible
            if self.ms_fetcher:
                try:
                    ms_result = self.ms_fetcher.fetch_lineup(
                        home_team_name, away_team_name, match_datetime, league
                    )
                    if ms_result.get('home') or ms_result.get('away'):
                        return {
                            'home': ms_result['home'],
                            'away': ms_result['away'],
                            'bajas_detectadas': ms_result.get('bajas', []),
                            'source': ms_result.get('source', 'MultiSource'),
                            'count': len(ms_result['home']) + len(ms_result['away']),
                            'status': 'predicted_multi_source',
                            'is_official': not ms_result.get('_is_fallback', True),
                            'verification_link': ms_result.get('verification_link')
                        }
                except Exception as e:
                    print(f"[LineupFetcher] MultiSource falló: {e}")

            # 3. BD interna
            print(f"[LineupFetcher] Usando BD interna para {home_team_name} vs {away_team_name}")
            return safe_db_fallback('BD Interna (alineación tipo del último partido)')

        except Exception as e:
            print(f"[LineupFetcher] Error general en fetch_smart_lineup: {e}")
            return safe_db_fallback(f'BD Interna (error recuperado)')

    def fetch_match_referee(self, home_team: str, away_team: str,
                            match_date: datetime, league: str) -> dict:
        """
        Obtiene el árbitro designado para el partido.
        Cascada: SofaScore API → BeSoccer → Pool de referencia
        Siempre devuelve un resultado válido.
        """
        if not isinstance(match_date, datetime):
            try:
                match_date = datetime.combine(match_date, datetime.min.time())
            except Exception:
                match_date = datetime.now()

        print(f"[LineupFetcher] Buscando árbitro para {league}: {home_team} vs {away_team}")

        # 1. SofaScore API
        try:
            ref = fetch_referee_sofascore(home_team, away_team, match_date, league)
            if ref:
                return _enrich_referee(ref)
        except Exception as e:
            print(f"[LineupFetcher] SofaScore referee falló: {e}")

        # 2. BeSoccer
        try:
            ref = fetch_referee_besoccer(home_team, away_team)
            if ref:
                return _enrich_referee(ref)
        except Exception as e:
            print(f"[LineupFetcher] BeSoccer falló: {e}")

        # 3. MultiSourceFetcher legacy
        if self.ms_fetcher:
            try:
                result = self.ms_fetcher.fetch_referee(home_team, away_team, match_date, league)
                if result and not result.get('_is_fallback'):
                    return _enrich_referee(result)
            except Exception as e:
                print(f"[LineupFetcher] MultiSource referee falló: {e}")

        # 4. Fallback pool
        print(f"[LineupFetcher] Usando pool de referencia para {home_team} vs {away_team}")
        return _fallback_referee(home_team, away_team, match_date, league)

    def fetch_injuries(self, league: str) -> Dict:
        """Obtiene informe de lesiones para una liga."""
        try:
            if self.auto_fetcher:
                return self.auto_fetcher.fetch_injuries_auto(league)
        except Exception:
            pass
        return {}

    def fetch_from_url(self, url: str, home_team_name: str, away_team_name: str) -> dict:
        """Scraping manual de una URL específica para alineaciones."""
        try:
            from bs4 import BeautifulSoup
            headers = HEADERS_WEB
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            extracted_names = set()

            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if 'jugadores/' in href or 'player/' in href:
                    name = a.get_text().strip()
                    if name and len(name.split()) > 1:
                        extracted_names.add(name)

            for img in soup.find_all('img', alt=True):
                alt = img['alt'].strip()
                if alt and len(alt.split()) > 1:
                    if not any(x in alt.lower() for x in ['escudo', 'logo', 'estadio']):
                        extracted_names.add(alt)

            for span in soup.find_all('span', class_='player-name'):
                name = span.get_text().strip()
                if name and len(name.split()) > 1:
                    extracted_names.add(name)

            if not extracted_names:
                return {'error': 'No se detectaron jugadores en el enlace.', 'home': [], 'away': []}

            return {
                'home': list(extracted_names)[:11],
                'away': list(extracted_names)[11:22] if len(extracted_names) > 11 else [],
                'source': url,
                'count': len(extracted_names)
            }
        except Exception as e:
            return {'error': f'Error al acceder al enlace: {str(e)}', 'home': [], 'away': []}

    def extract_from_image(self, image_bytes: bytes, home_team_name: str, away_team_name: str) -> dict:
        """Procesamiento de imagen para extraer jugadores (requiere tesseract)."""
        return {'error': 'OCR no disponible en esta versión.', 'home': [], 'away': []}

