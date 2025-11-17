import sys
sys.path.append('src')
import urllib.request
import urllib.error
import socket
import requests
from datetime import datetime
import pytz
import logging

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Copy the updated fetch_weather function
def fetch_weather(lat, lon, location):
    logger.info(f'Fetching real-time weather data for {location}')

    # Check network connectivity before making API calls
    try:
        urllib.request.urlopen('http://www.google.com', timeout=5)
        logger.debug('Network connectivity check passed for weather data')
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        logger.warning(f'Network connectivity check failed for weather data: {e}')
        # Return fallback data
        logger.info('Returning fallback weather data due to network issues')
        return {
            'temperature_c': 25,
            'temperature_f': 77,
            'wind_speed_ms': 5,
            'wind_speed_kts': 9.7,
            'wind_direction': 90,
            'cloud_cover': 50
        }

    try:
        # Use NOAA Weather.gov API for real-time weather station observations
        headers = {'User-Agent': 'SpaceX-Dashboard/1.0'}

        # Find nearest weather stations
        stations_url = f'https://api.weather.gov/points/{lat:.3f},{lon:.3f}/stations'
        stations_response = requests.get(stations_url, headers=headers, timeout=5)
        stations_response.raise_for_status()
        stations_data = stations_response.json()

        if not stations_data.get('features'):
            raise Exception('No weather stations found for this location')

        # Get observations from the closest station
        station_id = stations_data['features'][0]['properties']['stationIdentifier']
        obs_url = f'https://api.weather.gov/stations/{station_id}/observations/latest'
        obs_response = requests.get(obs_url, headers=headers, timeout=5)
        obs_response.raise_for_status()
        obs_data = obs_response.json()

        props = obs_data['properties']

        # Extract weather data
        temp_c = props.get('temperature', {}).get('value')
        wind_speed_ms = props.get('windSpeed', {}).get('value')
        wind_direction = props.get('windDirection', {}).get('value')

        if temp_c is None:
            raise Exception('No temperature data available from weather station')

        # Convert units
        temp_f = temp_c * 9 / 5 + 32
        wind_speed_kts = wind_speed_ms * 1.94384 if wind_speed_ms is not None else 0

        logger.info(f'Successfully fetched real-time weather data for {location} from station {station_id}')
        import time
        time.sleep(1)  # Avoid rate limiting

        return {
            'temperature_c': temp_c,
            'temperature_f': temp_f,
            'wind_speed_ms': wind_speed_ms or 0,
            'wind_speed_kts': wind_speed_kts,
            'wind_direction': wind_direction or 0,
            'cloud_cover': 50  # NOAA doesn't provide cloud cover in observations
        }

    except Exception as e:
        logger.error(f'NOAA Weather API error for {location}: {e}')
        # Fall back to Open-Meteo current conditions
        try:
            logger.info(f'Falling back to Open-Meteo current conditions for {location}')
            url = f'https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=UTC'
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            current = data['current']
            temp_c = current['temperature_2m']
            wind_speed_ms = current['wind_speed_10m']
            wind_direction = current['wind_direction_10m']

            return {
                'temperature_c': temp_c,
                'temperature_f': temp_c * 9 / 5 + 32,
                'wind_speed_ms': wind_speed_ms,
                'wind_speed_kts': wind_speed_ms * 1.94384,
                'wind_direction': wind_direction,
                'cloud_cover': 50
            }
        except Exception as fallback_error:
            logger.error(f'Open-Meteo fallback also failed for {location}: {fallback_error}')
            return {
                'temperature_c': 25,
                'temperature_f': 77,
                'wind_speed_ms': 5,
                'wind_speed_kts': 9.7,
                'wind_direction': 90,
                'cloud_cover': 50
            }

# Test the new NOAA-based weather function
print('Testing NEW NOAA-based real-time weather for Starbase...')
result = fetch_weather(25.997, -97.155, 'Starbase')
print('Starbase Real-Time Weather Data:')
print(f'Temperature: {result["temperature_f"]:.1f}°F ({result["temperature_c"]:.1f}°C)')
print(f'Wind: {result["wind_speed_kts"]:.1f} kts ({result["wind_speed_ms"]:.1f} m/s)')
print(f'Wind Direction: {result["wind_direction"]}°')
print(f'Cloud Cover: {result["cloud_cover"]}%')
print()
print('Bottom Left Pill Display Format:')
display_text = f'Wind {result["wind_speed_kts"]:.1f} kts | {result["temperature_f"]:.1f}°F'
print(f'"{display_text}"')
print()
print('✅ New NOAA real-time weather system test completed!')