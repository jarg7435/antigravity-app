"""
MultiSourceFetcher — Cascada de fuentes para árbitros y alineaciones
=====================================================================
Árbitros  → 0.API-Football  1.Claude API  2.SofaScore  3.RSS  4.LigaScraper  5.BeSoccer  6.Manual
Alineaciones → 0.API-Football  1.SofaScore  2.LigaScraper  3.BeSoccer  4.BD interna

ACTUALIZACIÓN: API-Football es ahora FUENTE 0 (máxima prioridad) para árbitros y alineaciones.
Esto garantiza que los datos oficiales de la API se usen ANTES que cualquier scraper.
"""
from datetime import datetime
from typing import Dict, Optional


def _norm_league(league):
    n = league.lower().split("(")[0].strip().replace("ea sports","").replace("santander","").strip()
    if "la liga" in n or "primera" in n or "espa" in n: return "La Liga"
    if "premier" in n: return "Premier League"
    if "serie a" in n or "italia" in n: return "Serie A"
    if "bundesliga" in n or "german" in n: return "Bundesliga"
    if "ligue 1" in n or "france" in n: return "Ligue 1"
    if "champions" in n or "uefa" in n: return "Champions League"
    return n


def _get_liga_scraper(league):
    norm = _norm_league(league)
    try:
        if norm == "La Liga":
            from src.data.scrapers.la_liga import LaLigaDataScraper; return LaLigaDataScraper()
        if norm == "Premier League":
            from src.data.scrapers.premier_league import PremierLeagueDataScraper; return PremierLeagueDataScraper()
        if norm == "Serie A":
            from src.data.scrapers.serie_a import SerieADataScraper; return SerieADataScraper()
        if norm == "Bundesliga":
            from src.data.scrapers.bundesliga import BundesligaDataScraper; return BundesligaDataScraper()
        if norm == "Ligue 1":
            from src.data.scrapers.ligue1 import Ligue1DataScraper; return Ligue1DataScraper()
    except Exception as e:
        print(f"  [MSF] liga scraper error: {e}")
    return None


def _enrich(ref):
    try:
        from src.data.referee_database import enrich_referee
        ref = enrich_referee(ref)
    except Exception:
        from src.models.base import RefereeStrictness
        ref.setdefault("strictness", RefereeStrictness.MEDIUM)
        ref.setdefault("avg_cards", 4.0)
    ref.setdefault("_is_fallback", False)
    return ref


def _get_api_football_client():
    """Inicializa lazy del cliente API-Football."""
    try:
        from src.data.api_football import APIFootballClient
        client = APIFootballClient()
        if client.is_configured:
            return client
    except Exception as e:
        print(f"  [MSF] API-Football init error: {e}")
    return None


def _get_football_data_client():
    """Inicializa lazy del cliente Football-Data.org."""
    try:
        from src.data.football_data_org import FootballDataClient
        client = FootballDataClient()
        if client.is_configured:
            return client
    except Exception as e:
        print(f"  [MSF] Football-Data.org init error: {e}")
    return None


def _norm_team_name(name):
    """Normaliza nombre de equipo para comparación fuzzy."""
    if not name:
        return ""
    n = name.lower().strip()
    # Quitar prefijos comunes
    for prefix in ["fc ", "cf ", "cd ", "ud ", "rcd ", "real ", "athletic "]:
        n = n.replace(prefix, "")
    return n.strip()


def _find_fixture_id(af_client, home, away, league, match_date):
    """
    Busca el fixture_id de un partido en API-Football buscando por equipos y fecha.
    Este ID es necesario para obtener árbitro y alineaciones oficiales.
    """
    if not af_client:
        return None

    from src.data.api_football import LEAGUE_IDS
    league_id = LEAGUE_IDS.get(_norm_league(league))

    # Estrategia 1: Buscar por fecha si tenemos liga
    if league_id and match_date:
        try:
            date_str = None
            if hasattr(match_date, 'strftime'):
                date_str = match_date.strftime("%Y-%m-%d")
            elif isinstance(match_date, str):
                date_str = match_date[:10]

            if date_str:
                fixtures = af_client.get_fixtures_by_date_range(
                    date_str, date_str, league_id
                )
                for f in fixtures:
                    fh = f.get("teams", {}).get("home", {}).get("name", "")
                    fa = f.get("teams", {}).get("away", {}).get("name", "")
                    if (_norm_team_name(fh) in _norm_team_name(home) or
                        _norm_team_name(home) in _norm_team_name(fh)):
                        if (_norm_team_name(fa) in _norm_team_name(away) or
                            _norm_team_name(away) in _norm_team_name(fa)):
                            return f.get("fixture", {}).get("id")
        except Exception as e:
            print(f"  [MSF] Buscar fixture por fecha falló: {e}")

    # Estrategia 2: Buscar próximos fixtures de la liga
    if league_id:
        try:
            next_fixtures = af_client.get_next_fixtures(league_id, next_n=20)
            for f in next_fixtures:
                fh = f.get("teams", {}).get("home", {}).get("name", "")
                fa = f.get("teams", {}).get("away", {}).get("name", "")
                if (_norm_team_name(fh) in _norm_team_name(home) or
                    _norm_team_name(home) in _norm_team_name(fh)):
                    if (_norm_team_name(fa) in _norm_team_name(away) or
                        _norm_team_name(away) in _norm_team_name(fa)):
                        return f.get("fixture", {}).get("id")
        except Exception as e:
            print(f"  [MSF] Buscar fixture próximos falló: {e}")

    # Estrategia 3: Buscar equipos por nombre y luego H2H
    try:
        home_teams = af_client.search_team(home)
        away_teams = af_client.search_team(away)
        if home_teams and away_teams:
            home_id = home_teams[0].get("team", {}).get("id")
            away_id = away_teams[0].get("team", {}).get("id")
            if home_id and away_id:
                h2h = af_client.get_h2h(home_id, away_id, last_n=5)
                for f in h2h:
                    status = f.get("fixture", {}).get("status", {}).get("short", "")
                    if status in ("NS", "TBD", "1H", "2H", "HT", "ET", "P", "BT", "LIVE"):
                        return f.get("fixture", {}).get("id")
                # Si no hay próximos, usar el último como referencia
                if h2h:
                    return h2h[0].get("fixture", {}).get("id")
    except Exception as e:
        print(f"  [MSF] Buscar fixture por H2H falló: {e}")

    return None


class MultiSourceFetcher:

    # =========================================================================
    # ÁRBITROS — cascada de 7 fuentes (API-Football es FUENTE 0)
    # =========================================================================
    def fetch_referee(self, home, away, match_date, league):
        print(f"\n[MSF] ÁRBITRO: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None

        # Calcular horas para el partido
        try:
            hours = (safe_date - datetime.now()).total_seconds() / 3600
        except Exception:
            hours = 999

        # ── FUENTE 0: API-Football (DATOS OFICIALES — MÁXIMA PRIORIDAD) ──────
        # API-Football incluye el árbitro en el campo "referee" de cada fixture.
        # Esta es la fuente más fiable: datos oficiales directamente de la API.
        af_client = _get_api_football_client()
        if af_client:
            try:
                fixture_id = _find_fixture_id(af_client, home, away, league, safe_date)
                if fixture_id:
                    ref_data = af_client.get_referee_from_fixture(fixture_id)
                    if ref_data and ref_data.get("name"):
                        ref_name = ref_data["name"]
                        print(f"  [0-API-Football] ✅ {ref_name} (fixture_id={fixture_id})")
                        # Obtener perfil estadístico del árbitro
                        try:
                            profile = af_client.compute_referee_profile(ref_name)
                            avg_cards = profile.get("avg_cards", "?")
                            strictness = profile.get("strictness", "MEDIUM")
                            matches_count = profile.get("matches_count", 0)
                        except Exception:
                            avg_cards = "?"
                            strictness = "MEDIUM"
                            matches_count = 0

                        # Mapear strictness al formato de la app
                        from src.models.base import RefereeStrictness
                        strict_map = {
                            "HIGH": RefereeStrictness.HIGH,
                            "LOW": RefereeStrictness.LOW,
                            "MEDIUM": RefereeStrictness.MEDIUM,
                        }
                        ref_result = {
                            "name": ref_name,
                            "strictness": strict_map.get(strictness, RefereeStrictness.MEDIUM),
                            "avg_cards": avg_cards if avg_cards != "?" else 4.0,
                            "source": f"API-Football (oficial)",
                            "verification_link": f"https://www.sofascore.com",
                            "_is_fallback": False,
                            "fixture_id": fixture_id,
                            "profile": profile if 'profile' in dir() else {},
                            "confidence": ref_data.get("confidence", "HIGH"),
                        }
                        return _enrich(ref_result)
                else:
                    print(f"  [0-API-Football] No se encontró fixture_id para {home} vs {away}")
            except Exception as e:
                print(f"  [0-API-Football] Error: {e}")

        # ── FUENTE 0b: Football-Data.org (verificación adicional) ─────────────
        fd_client = _get_football_data_client()
        if fd_client:
            try:
                from src.data.football_data_org import COMPETITION_CODES
                comp_code = COMPETITION_CODES.get(_norm_league(league))
                if comp_code:
                    # Buscar partido con árbitro en Football-Data.org
                    matches = fd_client.get_upcoming_matches(comp_code)
                    if not matches:
                        matches = fd_client.get_matches_today(comp_code)
                    for m in (matches or []):
                        mh = m.get("homeTeam", {}).get("shortName", "") or m.get("homeTeam", {}).get("name", "")
                        ma = m.get("awayTeam", {}).get("shortName", "") or m.get("awayTeam", {}).get("name", "")
                        if (_norm_team_name(mh) in _norm_team_name(home) or
                            _norm_team_name(home) in _norm_team_name(mh)):
                            if (_norm_team_name(ma) in _norm_team_name(away) or
                                _norm_team_name(away) in _norm_team_name(ma)):
                                # Obtener árbitros del partido
                                match_id = m.get("id")
                                if match_id:
                                    try:
                                        match_detail = fd_client.get_match_with_referees(match_id)
                                        if match_detail and match_detail.get("referees"):
                                            for ref_info in match_detail["referees"]:
                                                if ref_info.get("role") in ("REFEREE", None, ""):
                                                    ref_name = ref_info.get("name", "")
                                                    if ref_name:
                                                        print(f"  [0b-FootballData] ✅ {ref_name}")
                                                        from src.models.base import RefereeStrictness
                                                        return _enrich({
                                                            "name": ref_name,
                                                            "strictness": RefereeStrictness.MEDIUM,
                                                            "avg_cards": 4.0,
                                                            "source": "Football-Data.org (oficial)",
                                                            "verification_link": f"https://www.sofascore.com",
                                                            "_is_fallback": False,
                                                            "confidence": "HIGH",
                                                        })
                                    except Exception as e2:
                                        print(f"  [0b-FootballData] match detail error: {e2}")
                                break
            except Exception as e:
                print(f"  [0b-FootballData] Error: {e}")

        # ── FUENTE 1: Claude API con web_search ──────────────────────────────
        if hours < 48:
            try:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                r = fetch_referee_via_claude(home, away, league)
                if r and r.get("name"):
                    print(f"  [1-Claude] ✅ {r['name']}")
                    return _enrich(r)
            except Exception as e:
                print(f"  [1-Claude] {e}")

        # ── FUENTE 2: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and not sf.get("_is_fallback"):
                    print(f"  [2-SofaScore] ✅ {sf['name']}")
                    return _enrich(sf)
        except Exception as e:
            print(f"  [2-SofaScore] {e}")

        # ── FUENTE 3: Google News RSS ─────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            rss = fetch_referee_rss(home, away)
            if rss and rss.get("name"):
                print(f"  [3-RSS] ✅ {rss['name']}")
                if sofa_link: rss.setdefault("verification_link", sofa_link)
                return _enrich(rss)
        except Exception as e:
            print(f"  [3-RSS] {e}")

        # ── FUENTE 4: Scraper específico de liga ─────────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_referee(home, away, safe_date)
                name = r.get("name","")
                if name and name not in ["Por Detectar",""] and not r.get("_is_fallback"):
                    print(f"  [4-LigaScraper] ✅ {name}")
                    if sofa_link: r.setdefault("verification_link", sofa_link)
                    return _enrich(r)
        except Exception as e:
            print(f"  [4-LigaScraper] {e}")

        # ── FUENTE 5: BeSoccer ────────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_referee as bs_ref
            bs = bs_ref(home, away)
            if bs and bs.get("name"):
                print(f"  [5-BeSoccer] ✅ {bs['name']}")
                if sofa_link: bs.setdefault("verification_link", sofa_link)
                return _enrich(bs)
        except Exception as e:
            print(f"  [5-BeSoccer] {e}")

        # ── FALLBACK: pedir al usuario ────────────────────────────────────────
        from src.models.base import RefereeStrictness
        print(f"  [MSF] ❌ No encontrado en ninguna fuente")
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.sofascore.com",
            "_is_fallback": True
        }

    # =========================================================================
    # ALINEACIONES — cascada de 5 fuentes (API-Football es FUENTE 0)
    # =========================================================================
    def fetch_lineup(self, home, away, match_date, league):
        print(f"\n[MSF] ALINEACIÓN: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # ── FUENTE 0: API-Football (DATOS OFICIALES — MÁXIMA PRIORIDAD) ──────
        # API-Football proporciona alineaciones oficiales 20-40 min antes del partido
        af_client = _get_api_football_client()
        if af_client:
            try:
                fixture_id = _find_fixture_id(af_client, home, away, league, safe_date)
                if fixture_id:
                    lineups = af_client.get_lineups(fixture_id)
                    if lineups and len(lineups) >= 2:
                        home_players = []
                        away_players = []
                        home_formation = ""
                        away_formation = ""

                        for team_lu in lineups:
                            team_name = team_lu.get("team", {}).get("name", "")
                            formation = team_lu.get("formation", "")
                            starters = []
                            for p in team_lu.get("startXI", []):
                                pname = p.get("player", {}).get("name", "")
                                if pname:
                                    starters.append(pname)

                            if (_norm_team_name(team_name) in _norm_team_name(home) or
                                _norm_team_name(home) in _norm_team_name(team_name)):
                                home_players = starters
                                home_formation = formation
                            else:
                                away_players = starters
                                away_formation = formation

                        if home_players or away_players:
                            print(f"  [0-API-Football] ✅ {len(home_players)}+{len(away_players)} jugadores (formaciones: {home_formation}/{away_formation})")
                            return {
                                "home": home_players,
                                "away": away_players,
                                "bajas": [],
                                "source": f"API-Football (oficial) — {home_formation} vs {away_formation}",
                                "is_official": True,
                                "verification_link": "https://www.sofascore.com",
                                "_is_fallback": False,
                                "formation_home": home_formation,
                                "formation_away": away_formation,
                            }

                    # Si solo hay alineaciones predichas
                    if lineups and len(lineups) == 1:
                        team_lu = lineups[0]
                        starters = [p.get("player", {}).get("name", "") for p in team_lu.get("startXI", [])]
                        starters = [s for s in starters if s]
                        team_name = team_lu.get("team", {}).get("name", "")
                        formation = team_lu.get("formation", "")
                        if starters:
                            is_home = (_norm_team_name(team_name) in _norm_team_name(home) or
                                      _norm_team_name(home) in _norm_team_name(team_name))
                            result = {
                                "bajas": [],
                                "source": f"API-Football (parcial) — {formation}",
                                "is_official": True,
                                "verification_link": "https://www.sofascore.com",
                                "_is_fallback": False,
                            }
                            if is_home:
                                result["home"] = starters
                                result["away"] = []
                            else:
                                result["home"] = []
                                result["away"] = starters
                            print(f"  [0-API-Football] ✅ Parcial: {len(starters)} jugadores de {team_name}")
                            return result
            except Exception as e:
                print(f"  [0-API-Football] Error: {e}")

        # ── FUENTE 1: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away)
            if sf and (sf.get("home") or sf.get("away")):
                sf.setdefault("bajas", [])
                print(f"  [1-SofaScore] ✅ {len(sf.get('home',[]))}+{len(sf.get('away',[]))}")
                return sf
        except Exception as e:
            print(f"  [1-SofaScore] {e}")

        # ── FUENTE 2: Scraper específico de liga ─────────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_lineup(home, away, safe_date)
                if r.get("home") or r.get("away"):
                    r.setdefault("bajas", [])
                    print(f"  [2-LigaScraper] ✅ {len(r.get('home',[]))}+{len(r.get('away',[]))}")
                    return r
        except Exception as e:
            print(f"  [2-LigaScraper] {e}")

        # ── FUENTE 3: BeSoccer ────────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_lineup as bs_lu
            bs = bs_lu(home, away)
            if bs.get("home") or bs.get("away"):
                print(f"  [3-BeSoccer] ✅ {len(bs.get('home',[]))}+{len(bs.get('away',[]))}")
                return bs
        except Exception as e:
            print(f"  [3-BeSoccer] {e}")

        # ── FUENTE 4: Sin datos web ───────────────────────────────────────────
        print(f"  [MSF] Sin alineaciones disponibles en fuentes web")
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible — se usará BD interna",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }
