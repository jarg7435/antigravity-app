"""
MultiSourceFetcher — Orquestador central de datos de partido
============================================================
Estrategia:
  1. SofaScore API (universal, sin JS) — SIEMPRE primero
  2. Scraper específico de liga como respaldo
  3. Pool de fallback solo como último recurso
"""
import re
from datetime import datetime
from typing import Dict, Optional


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


def _get_scraper(league: str):
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
        print(f"[MSF] Error cargando scraper de {league}: {e}")
    return _FallbackScraper()


class _FallbackScraper:
    """Scraper de emergencia cuando todo lo demás falla."""

    def fetch_lineup(self, home, away, match_date):
        return {
            "home": [], "away": [], "bajas": [],
            "source": "Sin datos disponibles",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }

    def fetch_referee(self, home, away, match_date):
        from src.models.base import RefereeStrictness
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Sin datos — introduce el árbitro manualmente",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }


class MultiSourceFetcher:

    def fetch_lineup(self, home: str, away: str,
                     match_date: datetime, league: str) -> Dict:
        print(f"\n[MSF] LINEUP: {home} vs {away} | {league}")

        # 1. SofaScore — fuente primaria universal
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away)
            if sf and (sf.get("home") or sf.get("away")):
                sf.setdefault("bajas", [])
                print(f"  [SofaScore] ✅ {len(sf.get('home',[]))} + {len(sf.get('away',[]))} jugadores")
                return sf
            elif sf and sf.get("not_available_yet"):
                # Aún no publicadas pero sabemos el link
                print(f"  [SofaScore] Alineaciones no publicadas aún")
                return {
                    "home": [], "away": [], "bajas": [],
                    "source": "SofaScore (no publicadas aún)",
                    "verification_link": sf.get("verification_link", "https://www.sofascore.com"),
                    "_is_fallback": True
                }
        except Exception as e:
            print(f"  [SofaScore] lineup error: {e}")

        # 2. Scraper específico de liga
        try:
            scraper = _get_scraper(league)
            safe_date = match_date if match_date else datetime.now()
            result = scraper.fetch_lineup(home, away, safe_date)
            result.setdefault("home", [])
            result.setdefault("away", [])
            result.setdefault("bajas", [])
            result.setdefault("source", "Liga scraper")
            result.setdefault("verification_link", None)
            result.setdefault("_is_fallback", False)
            if result.get("home") or result.get("away"):
                print(f"  [LigaScraper] ✅ {len(result['home'])} + {len(result['away'])}")
                return result
        except Exception as e:
            print(f"  [LigaScraper] error: {e}")

        # 3. Sin datos
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }

    def fetch_referee(self, home: str, away: str,
                      match_date: datetime, league: str) -> Dict:
        print(f"\n[MSF] REFEREE: {home} vs {away} | {league}")

        # 1. SofaScore — fuente primaria universal
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf and sf.get("name") and sf["name"] not in ["Por confirmar", ""]:
                print(f"  [SofaScore] ✅ Árbitro: {sf['name']}")
                # Enriquecer con BD local
                try:
                    from src.data.referee_database import enrich_referee
                    sf = enrich_referee(sf)
                except Exception:
                    pass
                return sf
            elif sf and sf.get("verification_link"):
                # Partido encontrado pero árbitro no asignado — devolver link
                print(f"  [SofaScore] Árbitro no asignado aún, link disponible")
                return {
                    "name": "Por confirmar",
                    "source": "SofaScore (árbitro no asignado aún)",
                    "verification_link": sf["verification_link"],
                    "_is_fallback": True
                }
        except Exception as e:
            print(f"  [SofaScore] referee error: {e}")

        # 2. Scraper específico de liga
        try:
            scraper = _get_scraper(league)
            safe_date = match_date if match_date else datetime.now()
            result = scraper.fetch_referee(home, away, safe_date)
            result.setdefault("source", "Liga scraper")
            result.setdefault("verification_link", None)
            result.setdefault("_is_fallback", False)
            # Enriquecer siempre con BD local
            try:
                from src.data.referee_database import enrich_referee
                result = enrich_referee(result)
            except Exception:
                pass
            print(f"  [LigaScraper] Árbitro: {result.get('name','?')} | fallback: {result.get('_is_fallback')}")
            return result
        except Exception as e:
            print(f"  [LigaScraper] error: {e}")

        # 3. Fallback total
        from src.models.base import RefereeStrictness
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Sin datos — introduce el árbitro manualmente",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }
