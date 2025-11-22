#!/usr/bin/env python3
import requests
import datetime
import pytz

def test_weather_api():
    # Test coordinates for all locations
    locations = {
        'Starbase': {'lat': 25.9975, 'lon': -97.1566},
        'Vandy': {'lat': 34.632, 'lon': -120.611},
        'Cape': {'lat': 28.392, 'lon': -80.605},
        'Hawthorne': {'lat': 33.916, 'lon': -118.352}
    }

    for location, coords in locations.items():
        lat, lon = coords['lat'], coords['lon']
        print(f"\n=== Testing weather API for {location} ===")
        print(f"Coordinates: {lat}, {lon}")

        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover&timezone=UTC"
            print(f"API URL: {url}")

            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            now = datetime.datetime.now(pytz.UTC)
            hourly = data['hourly']
            times = [datetime.datetime.strptime(t, '%Y-%m-%dT%H:%M').replace(tzinfo=pytz.UTC) for t in hourly['time']]
            closest_idx = min(range(len(times)), key=lambda i: abs((times[i] - now).total_seconds()))

            wind_speed_ms = hourly['wind_speed_10m'][closest_idx]
            wind_speed_kts = wind_speed_ms * 1.94384

            print(f"Current time: {now}")
            print(f"Closest forecast time: {times[closest_idx]}")
            print(f"Temperature: {hourly['temperature_2m'][closest_idx]}°C")
            print(f"Wind speed: {wind_speed_ms} m/s = {wind_speed_kts:.1f} knots")
            print(f"Wind direction: {hourly['wind_direction_10m'][closest_idx]}°")
            print(f"Cloud cover: {hourly['cloud_cover'][closest_idx]}%")

            # Check if wind speed seems reasonable (typical range 0-30 knots for coastal areas)
            if wind_speed_kts > 50:
                print("WARNING: Wind speed seems unusually high!")
            elif wind_speed_kts > 30:
                print("NOTE: Wind speed is elevated but possible.")
            elif wind_speed_kts < 0:
                print("ERROR: Negative wind speed!")
            else:
                print("Wind speed appears normal.")

        except Exception as e:
            print(f"Error fetching weather data: {e}")

if __name__ == "__main__":
    test_weather_api()