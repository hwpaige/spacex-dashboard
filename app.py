import sys
import requests
import os
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtProperty, QObject, QAbstractListModel, QModelIndex, QVariant, pyqtSlot, qInstallMessageHandler
from PyQt6.QtGui import QFontDatabase, QCursor
from PyQt6.QtQml import QQmlApplicationEngine, QQmlContext
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface
from PyQt6.QtWebEngineQuick import QtWebEngineQuick
from PyQt6.QtCharts import QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz
import pandas as pd
import time

# Environment variables for Qt and Chromium
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
    "--enable-logging --v=1 --log-level=0 --enable-touch-drag-drop "
    "--disable-web-security --allow-running-insecure-content"
)
os.environ["QT_LOGGING_RULES"] = "qt.webenginecontext=true;qt5ct.debug=false"  # Logs OpenGL context creation
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"  # Fallback for ARM sandbox crashes
os.environ["QSG_RHI_BACKEND"] = "gl"

# Set up logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'app_launch.log')),  # Banana Pi log path
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Qt message handler to surface QML / Qt internal messages (errors, warnings, info)
# Install as early as possible after logger initialization

def _qt_message_handler(mode, context, message):
    try:
        level_name = mode.name if hasattr(mode, 'name') else str(mode)
    except Exception:
        level_name = str(mode)
    # Compose location info if available
    location = ''
    if context and context.file and context.line:
        location = f" {context.file}:{context.line}"
    logger.error(f"[QT-{level_name}]{location} {message}")

# Install the handler only once
try:
    qInstallMessageHandler(_qt_message_handler)
except Exception as _e:  # Fallback (should not normally occur)
    logger.warning(f"Failed to install Qt message handler: {_e}")

# Cache for launch data
CACHE_REFRESH_INTERVAL = 720  # 12 minutes in seconds
CACHE_FILE_PREVIOUS = os.path.join(os.path.dirname(__file__), 'previous_launches_cache.json')
CACHE_FILE_UPCOMING = os.path.join(os.path.dirname(__file__), 'upcoming_launches_cache.json')

# Cache for F1 data
CACHE_FILE_F1 = os.path.join(os.path.dirname(__file__), 'f1_cache.json')
f1_cache = None

# Load cache from file
def load_cache_from_file(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_data['timestamp'] = datetime.fromisoformat(cache_data['timestamp'])
            return cache_data
    return None

# Save cache to file
def save_cache_to_file(cache_file, data, timestamp):
    cache_data = {'data': data, 'timestamp': timestamp.isoformat()}
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)

# Fetch SpaceX launch data
def fetch_launches():
    logger.info("Fetching SpaceX launch data")
    current_time = datetime.now(pytz.UTC)
    current_date_str = current_time.strftime('%Y-%m-%d')
    current_year = current_time.year

    # Load previous launches cache
    previous_cache = load_cache_from_file(CACHE_FILE_PREVIOUS)
    if previous_cache and (current_time - previous_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL:
        previous_launches = previous_cache['data']
        logger.info("Using persistent cached previous launches")
    else:
        try:
            url = f'https://ll.thespacedevs.com/2.0.0/launch/previous/?lsp__name=SpaceX&net__gte={current_year}-01-01&net__lte={current_date_str}&limit=50'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            previous_launches = [
                {
                    'mission': launch['name'],
                    'date': launch['net'].split('T')[0],
                    'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
                    'net': launch['net'],
                    'status': launch['status']['name'],
                    'rocket': launch['rocket']['configuration']['name'],
                    'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                    'pad': launch['pad']['name'],
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')
                } for launch in data['results']
            ]
            save_cache_to_file(CACHE_FILE_PREVIOUS, previous_launches, current_time)
            logger.info("Successfully fetched and saved previous launches")
            time.sleep(1)  # Avoid rate limiting
        except Exception as e:
            logger.error(f"LL2 API error: {e}")
            previous_launches = [
                {'mission': 'Starship Flight 7', 'date': '2025-01-15', 'time': '12:00:00', 'net': '2025-01-15T12:00:00Z', 'status': 'Success', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': 'https://www.youtube.com/embed/videoseries?list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY&autoplay=1&mute=1&loop=1&controls=1&rel=0&enablejsapi=1'},
                {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
            ]

    # Load upcoming launches cache
    upcoming_cache = load_cache_from_file(CACHE_FILE_UPCOMING)
    if upcoming_cache and (current_time - upcoming_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL:
        upcoming_launches = upcoming_cache['data']
        logger.info("Using persistent cached upcoming launches")
    else:
        try:
            url = 'https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=50'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            upcoming_launches = [
                {
                    'mission': launch['name'],
                    'date': launch['net'].split('T')[0],
                    'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
                    'net': launch['net'],
                    'status': launch['status']['name'],
                    'rocket': launch['rocket']['configuration']['name'],
                    'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                    'pad': launch['pad']['name'],
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')
                } for launch in data['results']
            ]
            save_cache_to_file(CACHE_FILE_UPCOMING, upcoming_launches, current_time)
            logger.info("Successfully fetched and saved upcoming launches")
        except Exception as e:
            logger.error(f"LL2 API error: {e}")
            upcoming_launches = []

    return {'previous': previous_launches, 'upcoming': upcoming_launches}

# Fetch F1 data
def fetch_f1_data():
    logger.info("Fetching F1 data")
    global f1_cache
    if f1_cache:
        return f1_cache
    current_time = datetime.now(pytz.UTC)
    cache = load_cache_from_file(CACHE_FILE_F1)
    if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL:
        f1_cache = cache['data']
        logger.info("Using persistent cached F1 data")
        return f1_cache
    else:
        try:
            current_year = current_time.year
            # Fetch schedule
            url = f"https://api.jolpi.ca/ergast/f1/{current_year}.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            races = data['MRData']['RaceTable']['Races']
            meetings = []
            short_name_map = {
                'albert_park': 'Melbourne', 'shanghai': 'Shanghai', 'suzuka': 'Suzuka', 'bahrain': 'Sakhir',
                'jeddah': 'Jeddah', 'miami': 'Miami', 'imola': 'Imola', 'monaco': 'Monte Carlo',
                'catalunya': 'Catalunya', 'villeneuve': 'Montreal', 'red_bull_ring': 'Spielberg',
                'silverstone': 'Silverstone', 'spa': 'Spa', 'hungaroring': 'Hungaroring', 'zandvoort': 'Zandvoort',
                'monza': 'Monza', 'baku': 'Baku', 'marina_bay': 'Singapore', 'americas': 'Austin',
                'rodriguez': 'Mexico City', 'interlagos': 'Sao Paulo', 'vegas': 'Las Vegas',
                'losail': 'Lusail', 'yas_marina': 'Abu Dhabi'
            }
            for race in races:
                meeting = {
                    "circuit_short_name": short_name_map.get(race['Circuit']['circuitId'], race['Circuit']['circuitName']),
                    "location": race['Circuit']['Location']['locality'],
                    "country_name": race['Circuit']['Location']['country'],
                    "meeting_name": race['raceName'],
                    "year": current_year
                }
                # Parse sessions
                sessions = []
                if 'FirstPractice' in race:
                    date_start = f"{race['FirstPractice']['date']}T{race['FirstPractice']['time']}"
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": date_start,
                        "session_type": "Practice",
                        "session_name": "Practice 1",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                    meeting['date_start'] = date_start  # Set meeting start to FP1
                if 'SecondPractice' in race:
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": f"{race['SecondPractice']['date']}T{race['SecondPractice']['time']}",
                        "session_type": "Practice",
                        "session_name": "Practice 2",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                if 'ThirdPractice' in race:
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": f"{race['ThirdPractice']['date']}T{race['ThirdPractice']['time']}",
                        "session_type": "Practice",
                        "session_name": "Practice 3",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                if 'SprintQualifying' in race:
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": f"{race['SprintQualifying']['date']}T{race['SprintQualifying']['time']}",
                        "session_type": "Qualifying",
                        "session_name": "Sprint Qualifying",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                if 'Sprint' in race:
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": f"{race['Sprint']['date']}T{race['Sprint']['time']}",
                        "session_type": "Race",
                        "session_name": "Sprint",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                if 'Qualifying' in race:
                    sessions.append({
                        "location": meeting['location'],
                        "date_start": f"{race['Qualifying']['date']}T{race['Qualifying']['time']}",
                        "session_type": "Qualifying",
                        "session_name": "Qualifying",
                        "country_name": meeting['country_name'],
                        "circuit_short_name": meeting['circuit_short_name'],
                        "year": current_year
                    })
                # Always add Race
                sessions.append({
                    "location": meeting['location'],
                    "date_start": f"{race['date']}T{race['time']}",
                    "session_type": "Race",
                    "session_name": "Race",
                    "country_name": meeting['country_name'],
                    "circuit_short_name": meeting['circuit_short_name'],
                    "year": current_year
                })
                meeting['sessions'] = sessions
                meetings.append(meeting)

            # Fetch driver standings
            url = f"https://api.jolpi.ca/ergast/f1/{current_year}/driverStandings.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            standings_lists = data['MRData']['StandingsTable']['StandingsLists']
            driver_standings = standings_lists[0]['DriverStandings'] if standings_lists else []

            # Fetch constructor standings
            url = f"https://api.jolpi.ca/ergast/f1/{current_year}/constructorStandings.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            standings_lists = data['MRData']['StandingsTable']['StandingsLists']
            constructor_standings = standings_lists[0]['ConstructorStandings'] if standings_lists else []

            f1_data = {'schedule': meetings, 'driver_standings': driver_standings, 'constructor_standings': constructor_standings}
            save_cache_to_file(CACHE_FILE_F1, f1_data, current_time)
            f1_cache = f1_data
            logger.info("Successfully fetched and saved F1 data")
            time.sleep(1)  # Avoid rate limiting
            return f1_cache
        except Exception as e:
            logger.error(f"Ergast API error: {e}")
            f1_cache = {'schedule': [], 'driver_standings': [], 'constructor_standings': []}
            return f1_cache

# Fetch weather data
def fetch_weather(lat, lon, location):
    logger.info(f"Fetching weather data for {location}")
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover&timezone=UTC"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        now = datetime.now(pytz.UTC)
        hourly = data['hourly']
        times = [datetime.strptime(t, '%Y-%m-%dT%H:%M').replace(tzinfo=pytz.UTC) for t in hourly['time']]
        closest_idx = min(range(len(times)), key=lambda i: abs((times[i] - now).total_seconds()))
        logger.info(f"Successfully fetched weather data for {location}")
        time.sleep(1)  # Avoid rate limiting
        return {
            'temperature_c': hourly['temperature_2m'][closest_idx],
            'temperature_f': hourly['temperature_2m'][closest_idx] * 9 / 5 + 32,
            'wind_speed_ms': hourly['wind_speed_10m'][closest_idx],
            'wind_speed_kts': hourly['wind_speed_10m'][closest_idx] * 1.94384,
            'wind_direction': hourly['wind_direction_10m'][closest_idx],
            'cloud_cover': hourly['cloud_cover'][closest_idx]
        }
    except Exception as e:
        logger.error(f"Open-Meteo API error for {location}: {e}")
        return {
            'temperature_c': 25,
            'temperature_f': 77,
            'wind_speed_ms': 5,
            'wind_speed_kts': 9.7,
            'wind_direction': 90,
            'cloud_cover': 50
        }

# Location settings
location_settings = {
    'Starbase': {'lat': 25.997, 'lon': -97.155, 'timezone': 'America/Chicago'},
    'Vandy': {'lat': 34.632, 'lon': -120.611, 'timezone': 'America/Los_Angeles'},
    'Cape': {'lat': 28.392, 'lon': -80.605, 'timezone': 'America/New_York'},
    'Hawthorne': {'lat': 33.916, 'lon': -118.352, 'timezone': 'America/Los_Angeles'}
}

# Radar URLs (simplified to avoid WebGL issues)
radar_locations = {
    'Starbase': 'https://embed.windy.com/embed2.html?lat=25.997&lon=-97.155&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=25.997&detailLon=-97.155&metricWind=mph&metricTemp=%C2%B0F',
    'Vandy': 'https://embed.windy.com/embed2.html?lat=34.632&lon=-120.611&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=34.632&detailLon=-120.611&metricWind=mph&metricTemp=%C2%B0F',
    'Cape': 'https://embed.windy.com/embed2.html?lat=28.392&lon=-80.605&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=28.392&detailLon=-80.605&metricWind=mph&metricTemp=%C2%B0F',
    'Hawthorne': 'https://embed.windy.com/embed2.html?lat=33.916&lon=-118.352&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=33.916&detailLon=-118.352&metricWind=mph&metricTemp=%C2%B0F'
}

# Circuit coordinates for F1
circuit_coords = {
    'Melbourne': {'lat': -37.8497, 'lon': 144.968},
    'Shanghai': {'lat': 31.3389, 'lon': 121.2200},
    'Suzuka': {'lat': 34.8431, 'lon': 136.5411},
    'Sakhir': {'lat': 26.0325, 'lon': 50.5106},
    'Jeddah': {'lat': 21.6319, 'lon': 39.1044},
    'Miami': {'lat': 25.9581, 'lon': -80.2389},
    'Imola': {'lat': 44.3439, 'lon': 11.7167},
    'Monte Carlo': {'lat': 43.7347, 'lon': 7.4206},
    'Catalunya': {'lat': 41.5700, 'lon': 2.2611},
    'Montreal': {'lat': 45.5000, 'lon': -73.5228},
    'Spielberg': {'lat': 47.2197, 'lon': 14.7647},
    'Silverstone': {'lat': 52.0786, 'lon': -1.0169},
    'Spa': {'lat': 50.4372, 'lon': 5.9714},
    'Hungaroring': {'lat': 47.5839, 'lon': 19.2486},
    'Zandvoort': {'lat': 52.3888, 'lon': 4.5409},
    'Monza': {'lat': 45.6156, 'lon': 9.2811},
    'Baku': {'lat': 40.3725, 'lon': 49.8533},
    'Singapore': {'lat': 1.2914, 'lon': 103.8642},
    'Austin': {'lat': 30.1328, 'lon': -97.6411},
    'Mexico City': {'lat': 19.4042, 'lon': -99.0907},
    'Sao Paulo': {'lat': -23.7036, 'lon': -46.6997},
    'Las Vegas': {'lat': 36.1147, 'lon': -115.1728},
    'Lusail': {'lat': 25.4900, 'lon': 51.4542},
    'Abu Dhabi': {'lat': 24.4672, 'lon': 54.6031}
}

class EventModel(QAbstractListModel):
    MissionRole = Qt.ItemDataRole.UserRole + 1
    DateRole = Qt.ItemDataRole.UserRole + 2
    TimeRole = Qt.ItemDataRole.UserRole + 3
    NetRole = Qt.ItemDataRole.UserRole + 4
    StatusRole = Qt.ItemDataRole.UserRole + 5
    RocketRole = Qt.ItemDataRole.UserRole + 6
    OrbitRole = Qt.ItemDataRole.UserRole + 7
    PadRole = Qt.ItemDataRole.UserRole + 8
    VideoUrlRole = Qt.ItemDataRole.UserRole + 9
    MeetingNameRole = Qt.ItemDataRole.UserRole + 10
    CircuitShortNameRole = Qt.ItemDataRole.UserRole + 11
    LocationRole = Qt.ItemDataRole.UserRole + 12
    CountryNameRole = Qt.ItemDataRole.UserRole + 13
    SessionsRole = Qt.ItemDataRole.UserRole + 14
    DateStartRole = Qt.ItemDataRole.UserRole + 15
    IsGroupRole = Qt.ItemDataRole.UserRole + 16
    GroupNameRole = Qt.ItemDataRole.UserRole + 17
    LocalTimeRole = Qt.ItemDataRole.UserRole + 18

    def __init__(self, data, mode, event_type, tz, parent=None):
        super().__init__(parent)
        self._data = data
        self._mode = mode
        self._event_type = event_type
        self._tz = tz
        self._grouped_data = []
        self.update_data()

    def rowCount(self, parent=QModelIndex()):
        return len(self._grouped_data)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if 0 <= index.row() < self.rowCount():
            item = self._grouped_data[index.row()]
            if role == self.IsGroupRole:
                return 'group' in item
            if 'group' in item:
                if role == self.GroupNameRole:
                    return item['group']
                return None
            else:
                if role == self.MissionRole:
                    return item.get('mission', '')
                elif role == self.DateRole:
                    return item.get('date', '')
                elif role == self.TimeRole:
                    return item.get('time', '')
                elif role == self.NetRole:
                    return item.get('net', '')
                elif role == self.StatusRole:
                    return item.get('status', '')
                elif role == self.RocketRole:
                    return item.get('rocket', '')
                elif role == self.OrbitRole:
                    return item.get('orbit', '')
                elif role == self.PadRole:
                    return item.get('pad', '')
                elif role == self.VideoUrlRole:
                    return item.get('video_url', '')
                elif role == self.MeetingNameRole:
                    return item.get('meeting_name', '')
                elif role == self.CircuitShortNameRole:
                    return item.get('circuit_short_name', '')
                elif role == self.LocationRole:
                    return item.get('location', '')
                elif role == self.CountryNameRole:
                    return item.get('country_name', '')
                elif role == self.SessionsRole:
                    return item.get('sessions', [])
                elif role == self.DateStartRole:
                    return item.get('date_start', '')
                elif role == self.LocalTimeRole:
                    net = item.get('net', '') or item.get('date_start', '')
                    time_str = item.get('time', '') or ''
                    if time_str != 'TBD' and net:
                        return parse(net).astimezone(self._tz).strftime('%Y-%m-%d %H:%M:%S')
                    return 'TBD'
            return None

    def roleNames(self):
        roles = super().roleNames()
        roles[self.MissionRole] = b"mission"
        roles[self.DateRole] = b"date"
        roles[self.TimeRole] = b"time"
        roles[self.NetRole] = b"net"
        roles[self.StatusRole] = b"status"
        roles[self.RocketRole] = b"rocket"
        roles[self.OrbitRole] = b"orbit"
        roles[self.PadRole] = b"pad"
        roles[self.VideoUrlRole] = b"videoUrl"
        roles[self.MeetingNameRole] = b"meetingName"
        roles[self.CircuitShortNameRole] = b"circuitShortName"
        roles[self.LocationRole] = b"location"
        roles[self.CountryNameRole] = b"countryName"
        roles[self.SessionsRole] = b"sessions"
        roles[self.DateStartRole] = b"dateStart"
        roles[self.IsGroupRole] = b"isGroup"
        roles[self.GroupNameRole] = b"groupName"
        roles[self.LocalTimeRole] = b"localTime"
        return roles

    def update_data(self):
        self.beginResetModel()
        today = datetime.now(pytz.UTC).date()
        this_week_end = today + timedelta(days=7)
        last_week_start = today - timedelta(days=7)
        grouped = []
        if self._mode == 'spacex':
            launches = self._data['upcoming'] if self._event_type == 'upcoming' else self._data['previous']
            if self._event_type == 'upcoming':
                launches = sorted(launches, key=lambda x: parse(x['net']))
                today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
                this_week_launches = [l for l in launches if today < parse(l['net']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
                later_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() > this_week_end]
                if today_launches:
                    grouped.append({'group': 'Today'})
                    grouped.extend(today_launches)
                if this_week_launches:
                    grouped.append({'group': 'This Week'})
                    grouped.extend(this_week_launches)
                if later_launches:
                    grouped.append({'group': 'Later'})
                    grouped.extend(later_launches)
            else:
                launches = sorted(launches, key=lambda x: parse(x['net']), reverse=True)
                today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
                last_week_launches = [l for l in launches if last_week_start <= parse(l['net']).replace(tzinfo=pytz.UTC).date() < today]
                earlier_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() < last_week_start]
                if today_launches:
                    grouped.append({'group': 'Today'})
                    grouped.extend(today_launches)
                if last_week_launches:
                    grouped.append({'group': 'Last Week'})
                    grouped.extend(last_week_launches)
                if earlier_launches:
                    grouped.append({'group': 'Earlier'})
                    grouped.extend(earlier_launches)
        else:
            data = fetch_f1_data()
            races = data['schedule']
            if self._event_type == 'upcoming':
                races = sorted(races, key=lambda x: parse(x['date_start']))
                today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
                this_week_races = [r for r in races if today < parse(r['date_start']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
                later_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() > this_week_end]
                if today_races:
                    grouped.append({'group': 'Today'})
                    grouped.extend(today_races)
                if this_week_races:
                    grouped.append({'group': 'This Week'})
                    grouped.extend(this_week_races)
                if later_races:
                    grouped.append({'group': 'Later'})
                    grouped.extend(later_races)
            else:
                races = sorted(races, key=lambda x: parse(x['date_start']), reverse=True)
                today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
                last_week_races = [r for r in races if last_week_start <= parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < today]
                earlier_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < last_week_start]
                if today_races:
                    grouped.append({'group': 'Today'})
                    grouped.extend(today_races)
                if last_week_races:
                    grouped.append({'group': 'Last Week'})
                    grouped.extend(last_week_races)
                if earlier_races:
                    grouped.append({'group': 'Earlier'})
                    grouped.extend(earlier_races)
        self._grouped_data = grouped
        self.endResetModel()

class Backend(QObject):
    modeChanged = pyqtSignal()
    eventTypeChanged = pyqtSignal()
    countdownChanged = pyqtSignal()
    timeChanged = pyqtSignal()
    weatherChanged = pyqtSignal()
    launchesChanged = pyqtSignal()
    chartViewModeChanged = pyqtSignal()
    chartTypeChanged = pyqtSignal()
    f1Changed = pyqtSignal()
    themeChanged = pyqtSignal()
    locationChanged = pyqtSignal()
    eventModelChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._mode = 'spacex'
        self._event_type = 'upcoming'
        self._theme = 'dark'
        self._location = 'Starbase'
        self._chart_view_mode = 'actual'  # 'actual' or 'cumulative'
        self._chart_type = 'bar'  # 'bar' or 'line'
        self._launch_data = fetch_launches()
        self._f1_data = fetch_f1_data()
        self._weather_data = self.initialize_weather()
        self._tz = pytz.timezone(location_settings[self._location]['timezone'])
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)

        # Timers
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(300000)

        self.launch_timer = QTimer(self)
        self.launch_timer.timeout.connect(self.update_launches_periodic)
        self.launch_timer.start(CACHE_REFRESH_INTERVAL * 1000)

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

    @pyqtProperty(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if self._mode != value:
            self._mode = value
            self.modeChanged.emit()
            self.update_event_model()

    @pyqtProperty(str, notify=eventTypeChanged)
    def eventType(self):
        return self._event_type

    @eventType.setter
    def eventType(self, value):
        if self._event_type != value:
            self._event_type = value
            self.eventTypeChanged.emit()
            self.update_event_model()

    @pyqtProperty(str, notify=chartViewModeChanged)
    def chartViewMode(self):
        return self._chart_view_mode

    @chartViewMode.setter
    def chartViewMode(self, value):
        if self._chart_view_mode != value:
            self._chart_view_mode = value
            self.chartViewModeChanged.emit()
            # Also emit launchesChanged to refresh the chart
            self.launchesChanged.emit()

    @pyqtProperty(str, notify=chartTypeChanged)
    def chartType(self):
        return self._chart_type

    @chartType.setter
    def chartType(self, value):
        if self._chart_type != value:
            self._chart_type = value
            self.chartTypeChanged.emit()
            # Also emit launchesChanged to refresh the chart
            self.launchesChanged.emit()

    @pyqtProperty(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        if self._theme != value:
            self._theme = value
            self.themeChanged.emit()

    @pyqtProperty(str, notify=locationChanged)
    def location(self):
        return self._location

    @location.setter
    def location(self, value):
        if self._location != value:
            self._location = value
            self._tz = pytz.timezone(location_settings[self._location]['timezone'])
            self.locationChanged.emit()
            self.weatherChanged.emit()
            self.update_event_model()

    @pyqtProperty(EventModel, notify=eventModelChanged)
    def eventModel(self):
        return self._event_model

    @pyqtProperty(str, notify=timeChanged)
    def currentTime(self):
        return datetime.now(self._tz).strftime('%H:%M:%S')

    @pyqtProperty(QVariant, notify=weatherChanged)
    def weather(self):
        return self._weather_data.get(self._location, {})

    @pyqtProperty(str, notify=countdownChanged)
    def countdown(self):
        if self._mode == 'spacex':
            next_launch = self.get_next_launch()
            if not next_launch:
                return "No upcoming launches"
            launch_time = parse(next_launch['net']).replace(tzinfo=pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            if launch_time <= current_time:
                return "Launch in progress"
            delta = launch_time - current_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        else:
            next_race = self.get_next_race()
            if not next_race:
                return "No upcoming races"
            race_time = parse(next_race['date_start']).replace(tzinfo=pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            if race_time <= current_time:
                return "Race in progress"
            delta = race_time - current_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s to {next_race['meeting_name']}"

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrends(self):
        launches = self._launch_data['previous']
        df = pd.DataFrame(launches)
        df['date'] = pd.to_datetime(df['date'])
        current_year = datetime.now(pytz.UTC).year
        df = df[df['date'].dt.year == current_year]
        rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
        df = df[df['rocket'].isin(rocket_types)]
        df['month'] = df['date'].dt.to_period('M').astype(str)
        df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
        df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)
        for col in rocket_types:
            if col not in df_pivot.columns:
                df_pivot[col] = 0
        months = df_pivot.index.tolist()
        data = []
        for rocket in rocket_types:
            data.append({
                'label': rocket,
                'values': df_pivot[rocket].tolist()
            })
        return {'months': months, 'series': data}

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsMonths(self):
        try:
            launches = self._launch_data['previous']
            if not launches:
                return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] if self._chart_type == 'bar' else self._generate_month_labels_for_days()
            
            df = pd.DataFrame(launches)
            df['date'] = pd.to_datetime(df['date'])
            current_year = datetime.now(pytz.UTC).year
            df = df[df['date'].dt.year == current_year]
            rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
            df = df[df['rocket'].isin(rocket_types)]
            
            if df.empty:
                return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] if self._chart_type == 'bar' else self._generate_month_labels_for_days()
            
            if self._chart_type == 'bar':
                # Monthly labels for bar chart
                df['period'] = df['date'].dt.to_period('M').astype(str)
                unique_periods = sorted(df['period'].unique())
                month_names = []
                for period in unique_periods:
                    year_month = period.split('-')
                    if len(year_month) == 2:
                        year, month_num = int(year_month[0]), int(year_month[1])
                        month_name = datetime(year, month_num, 1).strftime('%b')
                        month_names.append(month_name)
                    else:
                        month_names.append(period)
                return month_names
            else:
                # For line chart, return month labels for daily data
                return self._generate_month_labels_for_days()
                
        except Exception as e:
            logger.error(f"Error in launchTrendsMonths: {e}")
            return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] if self._chart_type == 'bar' else self._generate_month_labels_for_days()

    @pyqtProperty(int, notify=launchesChanged)
    def launchTrendsMaxValue(self):
        try:
            launches = self._launch_data['previous']
            if not launches:
                return 5
            df = pd.DataFrame(launches)
            df['date'] = pd.to_datetime(df['date'])
            current_year = datetime.now(pytz.UTC).year
            df = df[df['date'].dt.year == current_year]
            rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
            df = df[df['rocket'].isin(rocket_types)]
            if df.empty:
                return 5
            
            if self._chart_type == 'bar':
                # Monthly aggregation for bar chart
                df['period'] = df['date'].dt.to_period('M').astype(str)
                df_grouped = df.groupby(['period', 'rocket']).size().reset_index(name='Launches')
                df_pivot = df_grouped.pivot(index='period', columns='rocket', values='Launches').fillna(0)
            else:
                # Daily aggregation for line chart
                df['period'] = df['date'].dt.date.astype(str)
                df_grouped = df.groupby(['period', 'rocket']).size().reset_index(name='Launches')
                df_pivot = df_grouped.pivot(index='period', columns='rocket', values='Launches').fillna(0)
                # Reindex to include all days of the year
                start_date = datetime(current_year, 1, 1).date()
                end_date = datetime(current_year, 12, 31).date()
                all_dates = [str(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]
                df_pivot = df_pivot.reindex(all_dates, fill_value=0)
            
            for col in rocket_types:
                if col not in df_pivot.columns:
                    df_pivot[col] = 0
            
            # Apply cumulative view if selected
            if self._chart_view_mode == 'cumulative':
                df_pivot = df_pivot.cumsum()
            
            max_value = df_pivot.values.max()
            # Round up to nearest 5, with minimum of 5
            return max(5, int((max_value + 4) // 5 * 5))
        except Exception as e:
            logger.error(f"Error in launchTrendsMaxValue: {e}")
            return 5

    def _generate_month_labels_for_days(self):
        """Generate month labels for daily data points - show month name on first day of month, empty otherwise"""
        current_year = datetime.now(pytz.UTC).year
        labels = []
        for day in range(1, 366):  # 365 days in a year
            try:
                date = datetime(current_year, 1, 1) + timedelta(days=day-1)
                if date.day == 1:  # First day of month
                    labels.append(date.strftime('%b'))
                else:
                    labels.append('')
            except ValueError:
                # Handle leap year case where day 366 doesn't exist
                break
        return labels

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsSeries(self):
        try:
            launches = self._launch_data['previous']
            if not launches:
                default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
                return [
                    {'label': 'Starship', 'values': default_values},
                    {'label': 'Falcon 9', 'values': default_values},
                    {'label': 'Falcon Heavy', 'values': default_values}
                ]
            df = pd.DataFrame(launches)
            df['date'] = pd.to_datetime(df['date'])
            current_year = datetime.now(pytz.UTC).year
            df = df[df['date'].dt.year == current_year]
            rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
            df = df[df['rocket'].isin(rocket_types)]
            if df.empty:
                default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
                return [
                    {'label': 'Starship', 'values': default_values},
                    {'label': 'Falcon 9', 'values': default_values},
                    {'label': 'Falcon Heavy', 'values': default_values}
                ]
            
            if self._chart_type == 'bar':
                # Monthly aggregation for bar chart
                df['period'] = df['date'].dt.to_period('M').astype(str)
                df_grouped = df.groupby(['period', 'rocket']).size().reset_index(name='Launches')
                df_pivot = df_grouped.pivot(index='period', columns='rocket', values='Launches').fillna(0)
            else:
                # Daily aggregation for line chart
                df['period'] = df['date'].dt.date.astype(str)
                df_grouped = df.groupby(['period', 'rocket']).size().reset_index(name='Launches')
                df_pivot = df_grouped.pivot(index='period', columns='rocket', values='Launches').fillna(0)
                # Reindex to include all days of the year
                start_date = datetime(current_year, 1, 1).date()
                end_date = datetime(current_year, 12, 31).date()
                all_dates = [str(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]
                df_pivot = df_pivot.reindex(all_dates, fill_value=0)
            
            for col in rocket_types:
                if col not in df_pivot.columns:
                    df_pivot[col] = 0
            
            # Apply cumulative view if selected
            if self._chart_view_mode == 'cumulative':
                df_pivot = df_pivot.cumsum()
            
            data = []
            for rocket in rocket_types:
                values = df_pivot[rocket].tolist()
                data.append({
                    'label': rocket,
                    'values': values
                })
            return data
        except Exception as e:
            logger.error(f"Error in launchTrendsSeries: {e}")
            default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
            return [
                {'label': 'Starship', 'values': default_values},
                {'label': 'Falcon 9', 'values': default_values},
                {'label': 'Falcon Heavy', 'values': default_values}
            ]

    @pyqtProperty(list, notify=f1Changed)
    def driverStandings(self):
        return self._f1_data['driver_standings']

    @pyqtProperty(list, notify=f1Changed)
    def raceCalendar(self):
        return sorted(self._f1_data['schedule'], key=lambda x: parse(x['date_start']))

    def get_next_launch(self):
        current_time = datetime.now(pytz.UTC)
        valid_launches = [l for l in self._launch_data['upcoming'] if l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
        if valid_launches:
            return min(valid_launches, key=lambda x: parse(x['net']))
        return None

    @pyqtSlot(result=QVariant)
    def get_next_race(self):
        races = self._f1_data['schedule']
        current = datetime.now(pytz.UTC)
        upcoming = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC) > current]
        if upcoming:
            return min(upcoming, key=lambda r: parse(r['date_start']))
        return None

    def initialize_weather(self):
        weather_data = {}
        for location, settings in location_settings.items():
            weather_data[location] = fetch_weather(settings['lat'], settings['lon'], location)
        return weather_data

    def update_weather(self):
        self._weather_data = self.initialize_weather()
        self.weatherChanged.emit()

    def update_launches_periodic(self):
        self._launch_data = fetch_launches()
        self.launchesChanged.emit()
        self.update_event_model()

    def update_time(self):
        self.timeChanged.emit()

    def update_countdown(self):
        self.countdownChanged.emit()

    def update_event_model(self):
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self.eventModelChanged.emit()

if __name__ == '__main__':
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu --ignore-gpu-blacklist"
    os.environ["QT_LOGGING_RULES"] = "qt5ct.debug=false;qt.webenginecontext=true"
    QtWebEngineQuick.initialize()
    app = QApplication(sys.argv)
    app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))  # Blank cursor globally

    # Load fonts
    font_path = os.path.join(os.path.dirname(__file__), "assets", "D-DIN.ttf")
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    # Load Font Awesome (assuming you place 'Font-Awesome.otf' in assets; download from fontawesome.com if needed)
    fa_path = os.path.join(os.path.dirname(__file__), "assets", "Font Awesome 5 Free-Solid-900.otf")
    if os.path.exists(fa_path):
        QFontDatabase.addApplicationFont(fa_path)

    engine = QQmlApplicationEngine()
    # Connect QML warnings signal (list of QQmlError objects)
    def _log_qml_warnings(errors):
        for e in errors:
            try:
                logger.error(f"QML warning: {e.toString()}")
            except Exception:
                logger.error(f"QML warning (unformatted): {e}")
    try:
        engine.warnings.connect(_log_qml_warnings)
    except Exception as _e:
        logger.warning(f"Could not connect engine warnings signal: {_e}")
    backend = Backend()
    context = engine.rootContext()
    context.setContextProperty("backend", backend)
    context.setContextProperty("radarLocations", radar_locations)
    context.setContextProperty("circuitCoords", circuit_coords)
    context.setContextProperty("spacexLogoPath", f"file://{os.path.join(os.path.dirname(__file__), 'spacex_logo.png')}")
    context.setContextProperty("f1LogoPath", f"file://{os.path.join(os.path.dirname(__file__), 'assets', 'f1-logo.png')}")
    context.setContextProperty("videoUrl", 'https://www.youtube.com/embed/videoseries?list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY&autoplay=1&mute=1&loop=1&controls=0&color=white&modestbranding=1&rel=0&enablejsapi=1')

    # Embedded QML for completeness (main.qml content)
    qml_code = """
import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtCharts 2.15
import QtWebEngine 1.10

Window {
    id: root
    visible: true
    width: 1480
    height: 320
    title: "SpaceX/F1 Dashboard"
    color: backend.theme === "dark" ? "#1c2526" : "#ffffff"
    Behavior on color { ColorAnimation { duration: 300 } }

    // Cache expensive / repeated lookups
    property var nextRace: backend.get_next_race()
    Timer { interval: 60000; running: true; repeat: true; onTriggered: nextRace = backend.get_next_race() }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 5

            // Column 1: Launch Trends or Driver Standings
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true

                ColumnLayout {
                    anchors.fill: parent

                    Text {
                        text: backend.mode === "spacex" ? 
                               (backend.chartViewMode === "cumulative" ? 
                                (backend.chartType === "bar" ? "Cumulative Launch Trends (Bar)" : "Cumulative Launch Trends (Line)") : 
                                (backend.chartType === "bar" ? "Monthly Launch Trends (Bar)" : "Monthly Launch Trends (Line)")) : 
                               "Driver Standings"
                        font.pixelSize: 14
                        color: "#999999"
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "spacex"

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 5

                            ChartView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                antialiasing: true
                                legend.visible: true
                                legend.alignment: Qt.AlignBottom
                                backgroundColor: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"

                                BarCategoryAxis {
                                    id: sharedAxisX
                                    categories: backend.launchTrendsMonths
                                    labelsColor: backend.theme === "dark" ? "white" : "black"
                                    gridVisible: false
                                }

                                ValueAxis {
                                    id: sharedAxisY
                                    min: 0
                                    max: backend.launchTrendsMaxValue
                                    labelsColor: backend.theme === "dark" ? "white" : "black"
                                    gridVisible: true
                                    titleText: "Number of Launches"
                                }

                                BarSeries {
                                    visible: backend.chartType === "bar"
                                    axisX: sharedAxisX
                                    axisY: sharedAxisY

                                    BarSet {
                                        label: "Starship"
                                        values: (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 0 && backend.launchTrendsSeries[0]) ? backend.launchTrendsSeries[0].values : [0, 0, 0, 0]
                                        color: "#ff6b6b"
                                        borderColor: "#ff5252"
                                    }
                                    BarSet {
                                        label: "Falcon 9"
                                        values: (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 1 && backend.launchTrendsSeries[1]) ? backend.launchTrendsSeries[1].values : [0, 0, 0, 0]
                                        color: "#4ecdc4"
                                        borderColor: "#45b7aa"
                                    }
                                    BarSet {
                                        label: "Falcon Heavy"
                                        values: (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 2 && backend.launchTrendsSeries[2]) ? backend.launchTrendsSeries[2].values : [0, 0, 0, 0]
                                        color: "#ffe66d"
                                        borderColor: "#ffd93d"
                                    }
                                }

                                LineSeries {
                                    id: starshipLine
                                    visible: backend.chartType === "line"
                                    axisX: sharedAxisX
                                    axisY: sharedAxisY
                                    name: "Starship"
                                    color: "#ff6b6b"
                                    pointsVisible: false
                                    Component.onCompleted: {
                                        updateStarshipLine()
                                    }
                                    Connections {
                                        target: backend
                                        function onLaunchesChanged() {
                                            updateStarshipLine()
                                        }
                                    }
                                    function updateStarshipLine() {
                                        starshipLine.clear()
                                        if (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 0 && backend.launchTrendsSeries[0]) {
                                            for (var i = 0; i < backend.launchTrendsSeries[0].values.length; i++) {
                                                starshipLine.append(i, backend.launchTrendsSeries[0].values[i])
                                            }
                                        }
                                    }
                                }

                                LineSeries {
                                    id: falcon9Line
                                    visible: backend.chartType === "line"
                                    axisX: sharedAxisX
                                    axisY: sharedAxisY
                                    name: "Falcon 9"
                                    color: "#4ecdc4"
                                    pointsVisible: false
                                    Component.onCompleted: {
                                        updateFalcon9Line()
                                    }
                                    Connections {
                                        target: backend
                                        function onLaunchesChanged() {
                                            updateFalcon9Line()
                                        }
                                    }
                                    function updateFalcon9Line() {
                                        falcon9Line.clear()
                                        if (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 1 && backend.launchTrendsSeries[1]) {
                                            for (var i = 0; i < backend.launchTrendsSeries[1].values.length; i++) {
                                                falcon9Line.append(i, backend.launchTrendsSeries[1].values[i])
                                            }
                                        }
                                    }
                                }

                                LineSeries {
                                    id: falconHeavyLine
                                    visible: backend.chartType === "line"
                                    axisX: sharedAxisX
                                    axisY: sharedAxisY
                                    name: "Falcon Heavy"
                                    color: "#ffe66d"
                                    pointsVisible: false
                                    Component.onCompleted: {
                                        updateFalconHeavyLine()
                                    }
                                    Connections {
                                        target: backend
                                        function onLaunchesChanged() {
                                            updateFalconHeavyLine()
                                        }
                                    }
                                    function updateFalconHeavyLine() {
                                        falconHeavyLine.clear()
                                        if (backend.launchTrendsSeries && backend.launchTrendsSeries.length > 2 && backend.launchTrendsSeries[2]) {
                                            for (var i = 0; i < backend.launchTrendsSeries[2].values.length; i++) {
                                                falconHeavyLine.append(i, backend.launchTrendsSeries[2].values[i])
                                            }
                                        }
                                    }
                                }
                            }

                            // Chart control buttons
                            RowLayout {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.margins: 5
                                spacing: 10

                                // Chart type buttons
                                RowLayout {
                                    spacing: 3
                                    Repeater {
                                        model: [
                                            {"type": "bar", "icon": "\uf080", "tooltip": "Bar Chart"},
                                            {"type": "line", "icon": "\uf201", "tooltip": "Line Chart"}
                                        ]
                                        Button {
                                            property var chartData: modelData
                                            Layout.preferredWidth: 35
                                            Layout.preferredHeight: 25
                                            font.pixelSize: 12
                                            font.family: "Font Awesome 5 Free"
                                            text: chartData.icon
                                            onClicked: {
                                                backend.chartType = chartData.type
                                            }
                                            background: Rectangle {
                                                color: backend.chartType === chartData.type ? 
                                                       (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : 
                                                       (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                                border.width: 1
                                                radius: 3
                                            }
                                            contentItem: Text {
                                                text: parent.chartData.icon
                                                font: parent.font
                                                color: backend.theme === "dark" ? "white" : "black"
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            ToolTip {
                                                text: parent.chartData.tooltip
                                                visible: parent.hovered
                                                delay: 500
                                            }
                                        }
                                    }
                                }

                                // Chart view mode buttons
                                RowLayout {
                                    spacing: 3
                                    Repeater {
                                        model: [
                                            {"type": "actual", "icon": "\uf201", "tooltip": "Monthly View"},
                                            {"type": "cumulative", "icon": "\uf0cb", "tooltip": "Cumulative View"}
                                        ]
                                        Button {
                                            property var chartData: modelData
                                            Layout.preferredWidth: 35
                                            Layout.preferredHeight: 25
                                            font.pixelSize: 12
                                            font.family: "Font Awesome 5 Free"
                                            text: chartData.icon
                                            onClicked: {
                                                backend.chartViewMode = chartData.type
                                            }
                                            background: Rectangle {
                                                color: backend.chartViewMode === chartData.type ? 
                                                       (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : 
                                                       (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                                border.width: 1
                                                radius: 3
                                            }
                                            contentItem: Text {
                                                text: parent.chartData.icon
                                                font: parent.font
                                                color: backend.theme === "dark" ? "white" : "black"
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            ToolTip {
                                                text: parent.chartData.tooltip
                                                visible: parent.hovered
                                                delay: 500
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "f1"
                        model: backend.driverStandings
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 40
                            color: "transparent"

                            Row {
                                Text { text: modelData.position; color: backend.theme === "dark" ? "white" : "black" }
                                Text { text: modelData.Driver.givenName + " " + modelData.Driver.familyName; color: backend.theme === "dark" ? "white" : "black" }
                                Text { text: modelData.points; color: backend.theme === "dark" ? "white" : "black" }
                            }
                        }
                    }
                }
            }

            // Column 2: Radar or Race Calendar
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    SwipeView {
                        id: weatherSwipe
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "spacex"
                        orientation: Qt.Vertical
                        clip: true
                        interactive: true
                        currentIndex: 0

                        Component.onCompleted: {
                            console.log("SwipeView completed, count:", count);
                        }

                        Repeater {
                            model: ["radar", "wind", "gust", "clouds", "temp", "pressure"]

                            Item {
                                WebEngineView {
                                    id: webView
                                    objectName: "webView"
                                    anchors.fill: parent
                                    url: radarLocations[backend.location].replace("radar", modelData) + "&rand=" + new Date().getTime()
                                    settings {
                                        webGLEnabled: true
                                        accelerated2dCanvasEnabled: true
                                        allowRunningInsecureContent: true
                                        javascriptEnabled: true
                                        localContentCanAccessRemoteUrls: true
                                    }
                                    onFullScreenRequested: function(request) {
                                        request.accept();
                                        root.visibility = Window.FullScreen
                                    }
                                    onLoadingChanged: function(loadRequest) {
                                        if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                            console.log("WebEngineView load failed for", modelData, ":", loadRequest.errorString);
                                        } else if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                            console.log("WebEngineView loaded successfully for", modelData);
                                        }
                                    }
                                }

                                Text {
                                    anchors.top: parent.top
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: {
                                        var icons = {
                                            "radar": "\uf7c0",
                                            "wind": "\uf72e", 
                                            "gust": "\uf72e",
                                            "clouds": "\uf0c2",
                                            "temp": "\uf2c7",
                                            "pressure": "\uf6c4"
                                        };
                                        return icons[modelData] || modelData.charAt(0).toUpperCase() + modelData.slice(1);
                                    }
                                    font.pixelSize: 14
                                    font.family: "Font Awesome 5 Free"
                                    color: "#ffffff"
                                    style: Text.Outline
                                    styleColor: "#000000"
                                }
                            }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "f1"
                        model: backend.raceCalendar
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 40
                            color: "transparent"

                            Column {
                                Text { text: modelData.meeting_name; color: backend.theme === "dark" ? "white" : "black" }
                                Text { text: modelData.circuit_short_name; color: backend.theme === "dark" ? "white" : "black" }
                                Text { text: modelData.date_start; color: backend.theme === "dark" ? "white" : "black" }
                            }
                        }
                        Behavior on opacity { NumberAnimation { duration: 200 } }
                    }

                    // Weather view buttons
                    RowLayout {
                        Layout.alignment: Qt.AlignTop | Qt.AlignHCenter
                        Layout.margins: 2
                        visible: backend.mode === "spacex"
                        spacing: 3

                        Repeater {
                            model: [
                                {"type": "radar", "icon": "\uf7c0"},
                                {"type": "wind", "icon": "\uf72e"},
                                {"type": "gust", "icon": "\uf72e"},
                                {"type": "clouds", "icon": "\uf0c2"},
                                {"type": "temp", "icon": "\uf2c7"},
                                {"type": "pressure", "icon": "\uf6c4"}
                            ]
                            Button {
                                property var weatherData: modelData
                                Layout.preferredWidth: 35
                                Layout.preferredHeight: 25
                                font.pixelSize: 12
                                font.family: "Font Awesome 5 Free"
                                text: weatherData.icon
                                onClicked: {
                                    weatherSwipe.currentIndex = index
                                }
                                background: Rectangle {
                                    color: weatherSwipe.currentIndex === index ? 
                                           (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : 
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                    border.width: 1
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.weatherData.icon
                                    font: parent.font
                                    color: backend.theme === "dark" ? "white" : "black"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }

            }

            // Column 3: Launches or Races
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true

                ColumnLayout {
                    anchors.fill: parent

                    Text {
                        text: backend.mode === "spacex" ? "Launches" : "Races"
                        font.pixelSize: 14
                        color: "#999999"
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: backend.eventModel
                        clip: true
                        spacing: 5

                        delegate: Item {
                            width: ListView.view.width
                            height: model.isGroup ? 30 : (backend.mode === "spacex" ? launchColumn.height + 20 : 40)

                            Rectangle { anchors.fill: parent; color: model.isGroup ? "transparent" : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"); radius: model.isGroup ? 0 : 6 }

                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 15
                                anchors.verticalCenter: parent.verticalCenter
                                text: model.isGroup ? model.groupName : ""
                                font.pixelSize: 14; font.bold: true; color: "#999999"; visible: model.isGroup
                            }

                            Column {
                                id: launchColumn
                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                                spacing: 5
                                visible: !model.isGroup && backend.mode === "spacex"

                                Text { text: model.mission ? model.mission : ""; font.pixelSize: 14; color: backend.theme === "dark" ? "white" : "black" }
                                Row { spacing: 5
                                    Text { text: "\uf135"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Rocket: " + (model.rocket ? model.rocket : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf0ac"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Orbit: " + (model.orbit ? model.orbit : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf3c5"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Pad: " + (model.pad ? model.pad : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Text { text: "Date: " + (model.date ? model.date : "") + (model.time ? (" " + model.time) : "") + " UTC"; font.pixelSize: 12; color: "#999999" }
                                Text { text: backend.location + ": " + (model.localTime ? model.localTime : "TBD"); font.pixelSize: 12; color: "#999999" }
                                Text { text: "Status: " + (model.status ? model.status : ""); font.pixelSize: 12; color: (model.status === "Success" || model.status === "Go" || model.status === "TBD" || model.status === "Go for Launch") ? "#4CAF50" : "#F44336" }
                            }

                            Column {
                                anchors.fill: parent; anchors.margins: 10
                                visible: !model.isGroup && backend.mode === "f1"
                                Text { text: model.meetingName ? model.meetingName : ""; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 12 }
                                Text { text: model.dateStart ? ("Date: " + model.dateStart) : ""; color: "#999999"; font.pixelSize: 12 }
                                Text { text: model.circuitShortName ? model.circuitShortName : ""; color: "#999999"; font.pixelSize: 12 }
                                Text { text: model.location ? model.location : ""; color: "#999999"; font.pixelSize: 12 }
                            }
                        }
                    }

                    // Launch view buttons
                    RowLayout {
                        Layout.alignment: Qt.AlignBottom | Qt.AlignHCenter
                        Layout.margins: 2
                        visible: backend.mode === "spacex"
                        spacing: 3

                        Repeater {
                            model: [
                                {"type": "upcoming", "icon": "\uf135"},
                                {"type": "past", "icon": "\uf1da"}
                            ]
                            Button {
                                property var launchData: modelData
                                Layout.preferredWidth: 35
                                Layout.preferredHeight: 25
                                font.pixelSize: 12
                                font.family: "Font Awesome 5 Free"
                                text: launchData.icon
                                onClicked: {
                                    backend.eventType = launchData.type
                                }
                                background: Rectangle {
                                    color: backend.eventType === launchData.type ? 
                                           (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : 
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                    border.width: 1
                                    radius: 3
                                }
                                contentItem: Text {
                                    text: parent.launchData.icon
                                    font: parent.font
                                    color: backend.theme === "dark" ? "white" : "black"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }

            // Column 4: Videos or Next Race Location
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    WebEngineView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        url: backend.mode === "spacex" ? videoUrl : (nextRace ? "https://www.openstreetmap.org/export/embed.html?bbox=" + (circuitCoords[nextRace.circuit_short_name].lon - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lon + 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat + 0.01) + "&layer=mapnik&marker=" + circuitCoords[nextRace.circuit_short_name].lat + "," + circuitCoords[nextRace.circuit_short_name].lon : "")
                        onFullScreenRequested: function(request) { request.accept(); root.visibility = Window.FullScreen }
                    }
                }
            }
        }

        // Bottom bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10

                // Left pill (time and weather)
                Rectangle {
                    id: leftPill
                    implicitWidth: leftRow.implicitWidth + 20
                    height: 30; radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"

                    Row {
                        id: leftRow
                        anchors.centerIn: parent
                        spacing: 10

                        Text { text: backend.currentTime; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 12 }
                        Text { text: "Wind " + backend.weather.wind_speed_kts.toFixed(1) + " kts | " + backend.weather.wind_speed_ms.toFixed(1) + " m/s, " + backend.weather.wind_direction + "° | Temp " + backend.weather.temperature_f.toFixed(1) + "°F | " + backend.weather.temperature_c.toFixed(1) + "°C | Clouds " + backend.weather.cloud_cover + "%"; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 12 }
                    }
                }

                Item { Layout.fillWidth: true }

                // Logo toggle
                Image {
                    source: backend.mode === "f1" ? f1LogoPath : spacexLogoPath
                    width: 80
                    height: 30

                    MouseArea {
                        anchors.fill: parent
                        onClicked: backend.mode = backend.mode === "spacex" ? "f1" : "spacex"
                    }
                }

                Item { Layout.fillWidth: true }

                // Right pill (countdown, location, theme)
                Rectangle {
                    id: rightPill
                    implicitWidth: rightRow.implicitWidth + 20
                    height: 30; radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"

                    Row {
                        id: rightRow
                        anchors.centerIn: parent
                        spacing: 10

                        Text { text: backend.countdown; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 12 }

                        Row {
                            spacing: 2
                            Repeater {
                                model: ["Starbase", "Vandy", "Cape", "Hawthorne"]
                                Rectangle {
                                    width: (locationText ? locationText.paintedWidth + 10 : 50)
                                    height: 20
                                    color: backend.location === modelData ? (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    radius: 4; border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"; border.width: 1
                                    Text { id: locationText; anchors.centerIn: parent; text: modelData; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 10 }
                                    MouseArea { anchors.fill: parent; onClicked: backend.location = modelData }
                                }
                            }
                        }
                        Row {
                            spacing: 2
                            Repeater {
                                model: ["Light", "Dark"]
                                Rectangle {
                                    width: (themeText ? themeText.paintedWidth + 10 : 50)
                                    height: 20
                                    color: backend.theme === modelData.toLowerCase() ? (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    radius: 4; border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"; border.width: 1
                                    Text { id: themeText; anchors.centerIn: parent; text: modelData; color: backend.theme === "dark" ? "white" : "black"; font.pixelSize: 10 }
                                    MouseArea { anchors.fill: parent; onClicked: backend.theme = modelData.toLowerCase() }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
    """

    # Load QML from string (for complete single file)
    qml_code = qml_code.replace('PointerHandler {', 'DragHandler {\n    target: null')
    engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
    if not engine.rootObjects():
        logger.error("QML root object creation failed (see earlier QML errors above).")
        print("QML load failed. Check console for Qt errors.")
        sys.exit(-1)
    sys.exit(app.exec())
