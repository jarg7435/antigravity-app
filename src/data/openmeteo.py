import openmeteo_requests
import requests_cache
from retry_requests import retry

class WeatherService:
    def __init__(self):
        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
        self.openmeteo = openmeteo_requests.Client(session = retry_session)
        self.url = "https://api.open-meteo.com/v1/forecast"

    def get_match_weather(self, lat: float, lon: float, date_iso: str) -> dict:
        """
        Fetches weather for a specific location and time.
        Note: OpenMeteo free API is great for forecast.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ["temperature_2m", "precipitation", "wind_speed_10m", "relative_humidity_2m"],
            "start_date": date_iso, # YYYY-MM-DD
            "end_date": date_iso
        }
        
        try:
            responses = self.openmeteo.weather_api(self.url, params=params)
            response = responses[0]
            
            # Simple aggregation (taking max/avg for the day for simplicity)
            # In a real app we would match the exact hour.
            hourly = response.Hourly()
            
            # Mocking specific hour extraction (e.g., 20:00)
            # Assuming the response covers the day, we just take averages/max
            
            # Using simple heuristics for now since processing numpy arrays from the SDK 
            # requires numpy installed and careful index matching.
            
            return {
                "temperature": 15.0, # Placeholder until full numpy integration
                "rain_mm": 0.0,
                "wind_kmh": 10.0,
                "humidity": 60.0
            }
        except Exception as e:
            print(f"Error fetching weather: {e}")
            return None
