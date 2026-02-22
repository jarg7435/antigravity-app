from abc import ABC, abstractmethod
from typing import Optional, List
from src.models.base import Match, Team

class DataProvider(ABC):
    """
    Interface for fetching match data from various sources (Scrapers, API, Mock).
    """

    @abstractmethod
    def get_upcoming_matches(self, league: str) -> List[Match]:
        """Fetch list of upcoming matches for a league."""
        pass

    @abstractmethod
    def get_team_data(self, team_name: str) -> Team:
        """Fetch detailed data for a team including players and recent form."""
        pass

    @abstractmethod
    def get_teams_by_league(self, league: str) -> List[str]:
        """Fetch list of team names for a specific league."""
        pass

    @abstractmethod
    def get_match_conditions(self, match_id: str, location: str, date_time: str) -> Optional[dict]:
        """Fetch weather and pitch conditions."""
        pass
    
    @abstractmethod
    def get_last_match_lineup(self, team_name: str) -> List[str]:
        """Fetch the lineup from the team's last match."""
        pass

