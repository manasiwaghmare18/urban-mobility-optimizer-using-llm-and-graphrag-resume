# agents/weather_agent.py
from data_ingestion.weather_scraper import fetch_realtime_weather


class WeatherAgent:
    def __init__(self, fetch_fn=None):
        # fetch_fn is injectable so tests never touch the network
        self._fetch = fetch_fn or fetch_realtime_weather

    def analyze(self, lat, lon):
        weather = self._fetch(lat, lon)

        if not weather:
            return {"avg_temperature": None, "avg_windspeed": None}

        return {
            "avg_temperature": weather["temperature"],
            "avg_windspeed": weather["windspeed"],
        }
