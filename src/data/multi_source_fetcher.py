"""
MultiSourceFetcher — Cascada completa de fuentes de datos
==========================================================
Orden de prioridad árbitros:
  1. SofaScore API (universal, JSON, sin JS)
  2. FutbolFantasy / Liga-specific scrapers
  3. BeSoccer
  4. WorldFootball.net
  5. Google News RSS (detección en noticias)
  6. Fallback manual

Orden de prioridad alineaciones:
  1. SofaScore API (universal)
  2. FutbolFantasy / Liga-specific scrapers
  3. BeSoccer
  4. BD interna (último partido conocido)
"""
import re
from datetime import datetime
from typing import Dict, Optional

# Filtro anti-falsos positivos: palabras que NO son árbitros
NOT_REFEREE_WORDS = {
    'crystal palace', 'real madrid', 'barcelona', 'atletico', 'sevilla',
    'manchester', 'liverpool', 'arsenal', 'chelsea', 'tottenham',
    'juventus', 'milan', 'napoli', 'roma', 'inter',
    'champions', 'league', 'primera', 'division', 'bundesliga',
    'premier', 'serie', 'ligue', 'copa', 'cup', 'final',
}


def _is_valid_referee_name(name: str) -> bool:
    """Verifica que el nombre detectado es un árbitro y no un equipo/competición."""
    if not name or len(name.split()) < 2:
        return False
    name_lower = name.lower()
    if any(word in name_lower for word in NOT_REFEREE_WORDS):
        return False
    if any(c.isdigit() for c in name):
        return False
    if len(name) > 40:
        return False
    return True


def _normalize_league(league: str) -> str:
    if not league:
        return ""
    norm = league.lower().strip()
    if "(" in norm:
        norm = norm.split("(")[0].strip()
    norm = norm.replace("ea sports", "").replace("santander", "").strip()
    if "la liga" in norm or "primera" in norm or "españa" in norm or "espana" in norm:
        return "La Liga"
    if "premier" in norm or "england" in norm:
        return "Premier League"
    if "serie a" in norm or "italy" in norm or "italia" in norm:
        return "Serie A"
    if "bundesliga" in norm or "germany" in norm or "german" in norm:
        return "Bundesliga"
    if "ligue 1" in norm or "france" in norm:
        return "Ligue 1"
    if "champions" in norm or "uefa" in norm:
        return "Champions League"
    return norm


def _get_liga_scraper(league: str):
    norm = _normalize_league(league)
    try:
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
    except Exception as e:
        print(f"[MSF] Liga scraper error ({league}): {e}")
    return None


class MultiSourceFetcher:

    # =========================================================================
    # ALINEACIONES
    # =========================================================================
    def fetch_lineup(self, home: str, away: str,
                     match_date: datetime, league: str) -> Dict:
        print(f"\n[MSF] LINEUP: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # 1. SofaScore API (universal)
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away)
            if sf and (sf.get("home") or sf.get("away")):
                sf.setdefault("bajas", [])
                print(f"  [SofaScore] ✅ {len(sf.get('home',[]))}+{len(sf.get('away',[]))} jugadores")
                return sf
            elif sf and sf.get("not_available_yet"):
                print(f"  [SofaScore] Alineaciones no publicadas aún — continuando cascada")
        except Exception as e:
            print(f"  [SofaScore] lineup error: {e}")

        # 2. Scraper específico de liga (FutbolFantasy, PremierInjuries, etc.)
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                result = scraper.fetch_lineup(home, away, safe_date)
                if result.get("home") or result.get("away"):
                    result.setdefault("bajas", [])
                    result.setdefault("_is_fallback", False)
                    print(f"  [LigaScraper] ✅ {len(result.get('home',[]))}+{len(result.get('away',[]))}")
                    return result
        except Exception as e:
            print(f"  [LigaScraper] lineup error: {e}")

        # 3. BeSoccer
        try:
            from src.data.scrapers.besoccer_scraper import fetch_lineup as bs_lu
            bs = bs_lu(home, away)
            if bs.get("home") or bs.get("away"):
                print(f"  [BeSoccer] ✅ {len(bs.get('home',[]))}+{len(bs.get('away',[]))} jugadores")
                return bs
        except Exception as e:
            print(f"  [BeSoccer] lineup error: {e}")

        # 4. Sin datos de web — indicar para BD interna
        print(f"  [MSF] Sin alineaciones en fuentes web")
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible en fuentes web",
            "verification_link": f"https://www.sofascore.com",
            "_is_fallback": True
        }

    # =========================================================================
    # ÁRBITROS — cascada completa
    # =========================================================================
    def fetch_referee(self, home: str, away: str,
                      match_date: datetime, league: str) -> Dict:
        print(f"\n[MSF] REFEREE: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None

        # 0. Claude API con web_search (si API key disponible — más fiable que scrapers)
        #    Prioridad cuando el partido es en <48h (árbitro ya publicado)
        try:
            hours_to_match = 999
            try:
                hours_to_match = (safe_date - datetime.now()).total_seconds() / 3600
            except Exception:
                pass
            if hours_to_match < 48:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                claude_name = fetch_referee_via_claude(home, away, league)
                if claude_name and _is_valid_referee_name(claude_name):
                    print(f"  [Claude API] ✅ {claude_name}")
                    result = {
                        "name": claude_name,
                        "source": "Claude API (búsqueda web)",
                        "verification_link": f"https://www.sofascore.com",
                        "_is_fallback": False
                    }
                    return self._enrich_and_return(result)
        except Exception as e:
            print(f"  [Claude API] referee error: {e}")

        # 1. SofaScore API (más fiable cuando tiene el dato)
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and sf["name"] not in ["Por confirmar", ""]:
                    if _is_valid_referee_name(sf["name"]):
                        print(f"  [SofaScore] ✅ {sf['name']}")
                        return self._enrich_and_return(sf)
                    else:
                        print(f"  [SofaScore] Nombre inválido: {sf['name']}")
        except Exception as e:
            print(f"  [SofaScore] referee error: {e}")

        # 2. Scraper específico de liga
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                result = scraper.fetch_referee(home, away, safe_date)
                name = result.get("name", "")
                if name and name not in ["Por Detectar","Por confirmar",""] \
                        and _is_valid_referee_name(name) \
                        and not result.get("_is_fallback"):
                    print(f"  [LigaScraper] ✅ {name}")
                    if sofa_link:
                        result.setdefault("verification_link", sofa_link)
                    return self._enrich_and_return(result)
        except Exception as e:
            print(f"  [LigaScraper] referee error: {e}")

        # 3. BeSoccer
        try:
            from src.data.scrapers.besoccer_scraper import fetch_referee as bs_ref
            bs = bs_ref(home, away)
            if bs and _is_valid_referee_name(bs.get("name", "")):
                print(f"  [BeSoccer] ✅ {bs['name']}")
                if sofa_link:
                    bs.setdefault("verification_link", sofa_link)
                return self._enrich_and_return(bs)
        except Exception as e:
            print(f"  [BeSoccer] referee error: {e}")

        # 4. WorldFootball.net
        try:
            from src.data.scrapers.worldfootball_scraper import fetch_referee as wf_ref
            wf = wf_ref(home, away, league)
            if wf and _is_valid_referee_name(wf.get("name", "")):
                print(f"  [WorldFootball] ✅ {wf['name']}")
                # Intentar enriquecer con estadísticas de WorldFootball
                try:
                    from src.data.scrapers.worldfootball_scraper import fetch_referee_stats
                    stats = fetch_referee_stats(wf["name"])
                    if stats:
                        wf.update(stats)
                except Exception:
                    pass
                if sofa_link:
                    wf.setdefault("verification_link", sofa_link)
                return self._enrich_and_return(wf)
        except Exception as e:
            print(f"  [WorldFootball] referee error: {e}")

        # 5. Google News RSS (detección en noticias — siempre funciona)
        try:
            from src.data.scrapers.sofascore_api import _extract_referee_from_rss
            rss_name = _extract_referee_from_rss(home, away)
            if rss_name and _is_valid_referee_name(rss_name):
                print(f"  [RSS] ✅ {rss_name}")
                result = {
                    "name": rss_name,
                    "source": "Google News RSS",
                    "verification_link": sofa_link or f"https://www.sofascore.com",
                    "_is_fallback": False
                }
                return self._enrich_and_return(result)
        except Exception as e:
            print(f"  [RSS] referee error: {e}")

        # 6. Fallback total
        from src.models.base import RefereeStrictness
        print(f"  [MSF] ❌ Árbitro no encontrado en ninguna fuente")
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Sin datos — introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.sofascore.com",
            "_is_fallback": True
        }

    def _enrich_and_return(self, ref: dict) -> dict:
        """Enriquece con BD local de árbitros y valida strictness."""
        try:
            from src.data.referee_database import enrich_referee
            ref = enrich_referee(ref)
        except Exception:
            from src.models.base import RefereeStrictness
            ref.setdefault("strictness", RefereeStrictness.MEDIUM)
            ref.setdefault("avg_cards", 4.0)
        ref.setdefault("_is_fallback", False)
        return ref
