"""
League-specific scrapers for lineups and referee data.
Each scraper follows a cascade strategy: Elite Source → Official → Fallback.
"""
from src.data.scrapers.la_liga import LaLigaDataScraper
from src.data.scrapers.premier_league import PremierLeagueDataScraper
from src.data.scrapers.serie_a import SerieADataScraper
from src.data.scrapers.bundesliga import BundesligaDataScraper
from src.data.scrapers.ligue1 import Ligue1DataScraper

__all__ = [
    'LaLigaDataScraper',
    'PremierLeagueDataScraper',
    'SerieADataScraper',
    'BundesligaDataScraper',
    'Ligue1DataScraper',
]
