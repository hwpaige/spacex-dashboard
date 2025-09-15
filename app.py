import sys
import requests
import os
import json
import platform
from PyQt6.QtWidgets import QApplication, QStyleFactory, QGraphicsScene
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtProperty, QObject, QAbstractListModel, QModelIndex, QVariant, pyqtSlot, qInstallMessageHandler, QRectF, QPoint
from PyQt6.QtGui import QFontDatabase, QCursor, QRegion
from PyQt6.QtQml import QQmlApplicationEngine, QQmlContext, qmlRegisterType
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface, QQuickPaintedItem
from PyQt6.QtWebEngineQuick import QtWebEngineQuick
from PyQt6.QtCharts import QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz
import pandas as pd
import time
import pyqtgraph as pg
import subprocess
import re

# Set console encoding to UTF-8 to handle Unicode characters properly
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Environment variables for Qt and Chromium - Force Hardware Acceleration
if platform.system() == 'Windows':
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
        "--disable-web-security --allow-running-insecure-content "
        "--disable-gpu-sandbox --disable-software-rasterizer "
        "--disable-gpu-driver-bug-workarounds --no-sandbox"
    )
elif platform.system() == 'Linux':
    # Hardware acceleration for Raspberry Pi with WebGL support for radar
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu --ignore-gpu-blocklist --enable-webgl "
        "--disable-gpu-sandbox --no-sandbox --use-gl=egl "
        "--disable-web-security --allow-running-insecure-content "
        "--gpu-testing-vendor-id=0xFFFF --gpu-testing-device-id=0xFFFF "
        "--disable-gpu-driver-bug-workarounds"
    )
else:
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
        "--disable-web-security --allow-running-insecure-content "
        "--disable-gpu-sandbox"
    )
os.environ["QT_LOGGING_RULES"] = "qt.webenginecontext=true;qt5ct.debug=false"  # Logs OpenGL context creation
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"  # Fallback for ARM sandbox crashes
os.environ["QSG_RHI_BACKEND"] = "gl"

# Essential Mesa environment variables for Raspberry Pi hardware rendering
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "0"  # Force hardware rendering
os.environ["GALLIUM_DRIVER"] = "v3d"  # Use VideoCore driver
os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"  # Ensure OpenGL 3.3
os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"  # Ensure GLSL 3.30
os.environ["EGL_PLATFORM"] = "drm"  # Use DRM for EGL

# Set platform-specific Qt platform plugin
if platform.system() == 'Windows':
    os.environ["QT_QPA_PLATFORM"] = "windows"
    # Windows-specific GPU settings
    os.environ["QT_OPENGL"] = "desktop"  # Use desktop OpenGL on Windows
elif platform.system() == 'Linux':
    os.environ["QT_QPA_PLATFORM"] = "xcb"  # Force XCB platform for better hardware acceleration
    os.environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl"  # Force EGL for hardware acceleration
    os.environ["EGL_PLATFORM"] = "drm"  # Use DRM for EGL when available
    os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"  # Force OpenGL 3.3 compatibility
    os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"  # Force GLSL 3.30 compatibility
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "0"  # Force hardware rendering, never software

# Set up logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'app_launch.log'), encoding='utf-8'),  # Banana Pi log path
        logging.StreamHandler(sys.stdout)
    ]
)

# Configure console handler to handle Unicode properly
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# Handle encoding errors gracefully
if hasattr(console_handler.stream, 'reconfigure'):
    try:
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # Fallback if reconfigure fails

# Replace the default console handler with our custom one that handles encoding
root_logger = logging.getLogger()
# Remove existing StreamHandler
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        root_logger.removeHandler(handler)
# Add our custom handler
root_logger.addHandler(console_handler)

# Ensure file handler uses UTF-8
file_handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'app_launch.log'), encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
root_logger.addHandler(file_handler)

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

    # Sanitize message to handle Unicode issues
    try:
        sanitized_message = str(message).encode('utf-8', errors='replace').decode('utf-8')
        
        # Filter out style customization warnings as they're not critical
        if "current style does not support customization" in sanitized_message:
            return
            
        logger.error(f"[QT-{level_name}]{location} {sanitized_message}")
    except Exception:
        # If all else fails, log a generic message
        logger.error(f"[QT-{level_name}]{location} <message encoding failed>")

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

# Radar URLs - Enable for all platforms including Raspberry Pi
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
    wifiNetworksChanged = pyqtSignal()
    wifiConnectedChanged = pyqtSignal()
    wifiConnectingChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        logger.info("Backend initializing...")
        self._mode = 'spacex'
        self._event_type = 'upcoming'
        self._theme = 'dark'
        self._location = 'Starbase'
        self._chart_view_mode = 'actual'  # 'actual' or 'cumulative'
        self._chart_type = 'bar'  # 'bar' or 'line'
        logger.info("Fetching initial data...")
        self._launch_data = fetch_launches()
        self._f1_data = fetch_f1_data()
        self._weather_data = self.initialize_weather()
        self._tz = pytz.timezone(location_settings[self._location]['timezone'])
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self._launch_trends_cache = {}  # Cache for launch trends series
        
        # WiFi properties
        self._wifi_networks = []
        self._wifi_connected = False
        self._wifi_connecting = False
        self._current_wifi_ssid = ""

        logger.info("Setting up timers...")
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

        # WiFi timer for status updates
        self.wifi_timer = QTimer(self)
        self.wifi_timer.timeout.connect(self.update_wifi_status)
        self.wifi_timer.start(5000)  # Check every 5 seconds
        
        # Check WiFi interface availability on startup
        self.check_wifi_interface()
        
        logger.info("Backend initialization complete")
        logger.info(f"Initial theme: {self._theme}")
        logger.info(f"Initial location: {self._location}")
        logger.info(f"Initial time: {self.currentTime}")
        logger.info(f"Initial countdown: {self.countdown}")

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

    @pyqtProperty(list, notify=wifiNetworksChanged)
    def wifiNetworks(self):
        return self._wifi_networks

    @pyqtProperty(bool, notify=wifiConnectedChanged)
    def wifiConnected(self):
        return self._wifi_connected

    @pyqtProperty(bool, notify=wifiConnectingChanged)
    def wifiConnecting(self):
        return self._wifi_connecting

    @pyqtProperty(str, notify=wifiConnectedChanged)
    def currentWifiSsid(self):
        return self._current_wifi_ssid

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
        cache_key = (self._chart_type, self._chart_view_mode, len(self._launch_data['previous']))
        if cache_key in self._launch_trends_cache:
            return self._launch_trends_cache[cache_key]
        
        try:
            launches = self._launch_data['previous']
            if not launches:
                default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
                data = [
                    {'label': 'Starship', 'values': default_values},
                    {'label': 'Falcon 9', 'values': default_values},
                    {'label': 'Falcon Heavy', 'values': default_values}
                ]
                self._launch_trends_cache[cache_key] = data
                return data
            df = pd.DataFrame(launches)
            df['date'] = pd.to_datetime(df['date'])
            current_year = datetime.now(pytz.UTC).year
            df = df[df['date'].dt.year == current_year]
            rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
            df = df[df['rocket'].isin(rocket_types)]
            if df.empty:
                default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
                data = [
                    {'label': 'Starship', 'values': default_values},
                    {'label': 'Falcon 9', 'values': default_values},
                    {'label': 'Falcon Heavy', 'values': default_values}
                ]
                self._launch_trends_cache[cache_key] = data
                return data
            
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
            self._launch_trends_cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"Error in launchTrendsSeries: {e}")
            default_values = [0] * 12 if self._chart_type == 'bar' else [0] * 365
            data = [
                {'label': 'Starship', 'values': default_values},
                {'label': 'Falcon 9', 'values': default_values},
                {'label': 'Falcon Heavy', 'values': default_values}
            ]
            self._launch_trends_cache[cache_key] = data
            return data

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
            try:
                weather = fetch_weather(settings['lat'], settings['lon'], location)
                weather_data[location] = weather
                logger.info(f"Weather initialized for {location}: {weather}")
            except Exception as e:
                logger.error(f"Failed to initialize weather for {location}: {e}")
                # Provide fallback data
                weather_data[location] = {
                    'temperature_c': 25,
                    'temperature_f': 77,
                    'wind_speed_ms': 5,
                    'wind_speed_kts': 9.7,
                    'wind_direction': 90,
                    'cloud_cover': 50
                }
        return weather_data

    def update_weather(self):
        self._weather_data = self.initialize_weather()
        self.weatherChanged.emit()

    def update_launches_periodic(self):
        self._launch_data = fetch_launches()
        self._launch_trends_cache.clear()  # Clear cache when data updates
        self.launchesChanged.emit()
        self.update_event_model()

    def update_time(self):
        self.timeChanged.emit()

    def update_countdown(self):
        self.countdownChanged.emit()

    def update_event_model(self):
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self.eventModelChanged.emit()

    @pyqtSlot()
    def scanWifiNetworks(self):
        """Scan for available WiFi networks using nmcli (Ubuntu standard)"""
        try:
            is_windows = platform.system() == 'Windows'

            if is_windows:
                # Use Windows netsh command to scan for WiFi networks
                result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                                      capture_output=True, text=True, timeout=10)

                networks = []
                current_network = {}

                for line in result.stdout.split('\n'):
                    line = line.strip()

                    # Look for SSID
                    if line.startswith('SSID'):
                        if current_network and current_network.get('ssid'):
                            networks.append(current_network)
                        ssid_match = re.search(r'SSID\s+\d+\s*:\s*(.+)', line)
                        if ssid_match:
                            current_network = {'ssid': ssid_match.group(1).strip(), 'signal': 0, 'encrypted': False}

                    # Look for signal strength
                    elif 'Signal' in line and current_network:
                        signal_match = re.search(r'Signal\s*:\s*(\d+)%', line)
                        if signal_match:
                            # Convert percentage to dBm (rough approximation)
                            percentage = int(signal_match.group(1))
                            # Convert percentage to dBm (rough approximation: 100% = -30dBm, 0% = -100dBm)
                            dbm = -30 - ((100 - percentage) * 0.7)
                            current_network['signal'] = int(dbm)

                    # Look for authentication
                    elif 'Authentication' in line and current_network:
                        if 'WPA' in line or 'WPA2' in line or 'WPA3' in line:
                            current_network['encrypted'] = True

                # Add the last network
                if current_network and current_network.get('ssid'):
                    networks.append(current_network)
            else:
                # Use nmcli for Ubuntu/Linux (much more reliable than iwlist)
                try:
                    # First check if nmcli is available
                    nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=5)
                    if nmcli_check.returncode != 0:
                        logger.error("nmcli not found. Please install network-manager: sudo apt install network-manager")
                        self._wifi_networks = []
                        self.wifiNetworksChanged.emit()
                        return

                    # Scan for networks using nmcli
                    result = subprocess.run(['nmcli', 'device', 'wifi', 'list'],
                                          capture_output=True, text=True, timeout=15)

                    if result.returncode != 0:
                        logger.error(f"nmcli scan failed: {result.stderr}")
                        self._wifi_networks = []
                        self.wifiNetworksChanged.emit()
                        return

                    networks = []
                    lines = result.stdout.strip().split('\n')

                    # Skip header line
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 8:
                            ssid = parts[1] if parts[1] != '--' else parts[0]
                            if ssid and ssid != '*':
                                # Extract signal strength (usually in parts)
                                signal = 0
                                for part in parts:
                                    if part.endswith('*'):
                                        signal = int(part[:-1]) if part[:-1].isdigit() else 0
                                        break

                                # Check for security
                                security = ' '.join(parts[6:]) if len(parts) > 6 else ''
                                encrypted = 'WPA' in security or 'WEP' in security

                                networks.append({
                                    'ssid': ssid,
                                    'signal': signal,
                                    'encrypted': encrypted
                                })

                except Exception as e:
                    logger.error(f"nmcli scan failed: {e}")
                    self._wifi_networks = []
                    self.wifiNetworksChanged.emit()
                    return

            # Remove duplicates and sort by signal strength
            seen_ssids = set()
            unique_networks = []
            for network in networks:
                if network['ssid'] not in seen_ssids and network['ssid']:
                    seen_ssids.add(network['ssid'])
                    unique_networks.append(network)

            self._wifi_networks = sorted(unique_networks, key=lambda x: x['signal'], reverse=True)
            self.wifiNetworksChanged.emit()

        except Exception as e:
            logger.error(f"Error scanning WiFi networks: {e}")
            self._wifi_networks = []
            self.wifiNetworksChanged.emit()

    @pyqtSlot(str, str)
    def connectToWifi(self, ssid, password):
        """Connect to a WiFi network using nmcli"""
        try:
            self._wifi_connecting = True
            self.wifiConnectingChanged.emit()

            is_windows = platform.system() == 'Windows'

            if is_windows:
                # Create a temporary XML profile for Windows WiFi connection
                profile_xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>'''

                # Write profile to temp file
                profile_path = f'C:\\temp\\wifi_profile_{ssid}.xml'
                os.makedirs('C:\\temp', exist_ok=True)
                with open(profile_path, 'w') as f:
                    f.write(profile_xml)

                # Add the profile
                subprocess.run(['netsh', 'wlan', 'add', 'profile', f'filename={profile_path}'],
                             capture_output=True, timeout=10)

                # Connect to the network
                subprocess.run(['netsh', 'wlan', 'connect', f'name={ssid}'],
                             capture_output=True, timeout=10)

                # Clean up
                try:
                    os.remove(profile_path)
                except:
                    pass
            else:
                # Use nmcli for Ubuntu/Linux (much simpler and more reliable)
                try:
                    # Check if nmcli is available
                    nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=5)
                    if nmcli_check.returncode != 0:
                        logger.error("nmcli not found. Please install network-manager: sudo apt install network-manager")
                        self._wifi_connecting = False
                        self.wifiConnectingChanged.emit()
                        return

                    logger.info(f"Connecting to WiFi network: {ssid}")

                    # First, disconnect from current network if connected
                    try:
                        subprocess.run(['nmcli', 'device', 'disconnect', 'wlan0'],
                                     capture_output=True, timeout=10)
                    except:
                        pass  # Ignore if no current connection

                    # Connect to the new network
                    if password:
                        # For networks with password
                        result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
                                              capture_output=True, text=True, timeout=30)
                    else:
                        # For open networks
                        result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid],
                                              capture_output=True, text=True, timeout=30)

                    if result.returncode == 0:
                        logger.info(f"Successfully connected to {ssid}")
                    else:
                        logger.error(f"Failed to connect to {ssid}: {result.stderr}")
                        self._wifi_connecting = False
                        self.wifiConnectingChanged.emit()
                        return

                except Exception as e:
                    logger.error(f"nmcli connection failed: {e}")
                    self._wifi_connecting = False
                    self.wifiConnectingChanged.emit()
                    return

            self._wifi_connecting = False
            self.wifiConnectingChanged.emit()

            # Check if connected
            self.update_wifi_status()

        except Exception as e:
            logger.error(f"Error connecting to WiFi: {e}")
            self._wifi_connecting = False
            self.wifiConnectingChanged.emit()
            
        except Exception as e:
            logger.error(f"Error connecting to WiFi: {e}")
            self._wifi_connecting = False
            self.wifiConnectingChanged.emit()

    @pyqtSlot()
    def disconnectWifi(self):
        """Disconnect from current WiFi network"""
        try:
            is_windows = platform.system() == 'Windows'

            if is_windows:
                subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True)
            else:
                # For Linux, use nmcli to disconnect (preferred method)
                try:
                    # First try to disconnect using nmcli
                    result = subprocess.run(['nmcli', 'device', 'disconnect', 'wifi'],
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info("Successfully disconnected WiFi using nmcli")
                    else:
                        logger.warning(f"nmcli disconnect failed: {result.stderr}")
                        # Fallback to killing wpa_supplicant and releasing DHCP
                        try:
                            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], capture_output=True)
                            subprocess.run(['sudo', 'dhclient', '-r', 'wlan0'], capture_output=True)
                        except:
                            # Try without sudo
                            try:
                                subprocess.run(['killall', 'wpa_supplicant'], capture_output=True)
                                subprocess.run(['dhclient', '-r', 'wlan0'], capture_output=True)
                            except Exception as e:
                                logger.error(f"Error disconnecting WiFi: {e}")
                except Exception as e:
                    logger.error(f"Error disconnecting WiFi: {e}")

            self._wifi_connected = False
            self._current_wifi_ssid = ""
            self.wifiConnectedChanged.emit()
        except Exception as e:
            logger.error(f"Error disconnecting WiFi: {e}")

    def update_wifi_status(self):
        """Update WiFi connection status"""
        try:
            is_windows = platform.system() == 'Windows'
            
            if is_windows:
                # Check WiFi interface status using Windows commands
                result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                                      capture_output=True, text=True, timeout=5)
                
                connected = False
                current_ssid = ""
                
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    if 'State' in line and 'connected' in line.lower():
                        connected = True
                    
                    if 'SSID' in line and 'BSSID' not in line:
                        ssid_match = re.search(r'SSID\s*:\s*(.+)', line)
                        if ssid_match:
                            current_ssid = ssid_match.group(1).strip()
            else:
                # Check WiFi status using nmcli (preferred for Ubuntu/Linux)
                connected = False
                current_ssid = ""

                try:
                    # Use nmcli to get device status
                    result = subprocess.run(['nmcli', 'device', 'status'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'wifi' in line.lower() and 'connected' in line.lower():
                                connected = True
                                break

                    # Get current SSID if connected
                    if connected:
                        ssid_result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'device', 'wifi'],
                                                   capture_output=True, text=True, timeout=5)
                        if ssid_result.returncode == 0:
                            for line in ssid_result.stdout.split('\n'):
                                if line.startswith('yes:'):
                                    current_ssid = line.split(':', 1)[1].strip()
                                    break

                except Exception as e:
                    logger.warning(f"nmcli not available, falling back to legacy methods: {e}")
                    # Fallback to legacy methods
                    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                    has_ip = False

                    for interface in interfaces:
                        try:
                            # Check if interface has an IP address
                            result = subprocess.run(['ip', 'addr', 'show', interface],
                                                  capture_output=True, text=True, timeout=5)

                            if 'inet ' in result.stdout:
                                has_ip = True
                                break
                        except:
                            continue

                    # Get current SSID using legacy tools
                    if has_ip:
                        # Try iw first
                        try:
                            for interface in interfaces:
                                iw_result = subprocess.run(['iw', 'dev', interface, 'link'],
                                                         capture_output=True, text=True, timeout=5)
                                if iw_result.returncode == 0 and 'SSID:' in iw_result.stdout:
                                    ssid_match = re.search(r'SSID:\s*(.+)', iw_result.stdout)
                                    if ssid_match:
                                        current_ssid = ssid_match.group(1).strip()
                                        break
                        except:
                            pass

                        # If iw failed, try iwgetid
                        if not current_ssid:
                            try:
                                ssid_result = subprocess.run(['iwgetid', '-r'],
                                                           capture_output=True, text=True, timeout=5)
                                current_ssid = ssid_result.stdout.strip() if ssid_result.returncode == 0 else ""
                            except:
                                pass

                    connected = has_ip
            
            # Update properties
            wifi_changed = (self._wifi_connected != connected) or (self._current_wifi_ssid != current_ssid)
            
            self._wifi_connected = connected
            self._current_wifi_ssid = current_ssid
            
            if wifi_changed:
                self.wifiConnectedChanged.emit()
                
        except Exception as e:
            logger.error(f"Error updating WiFi status: {e}")
            self._wifi_connected = False
            self._current_wifi_ssid = ""
            self.wifiConnectedChanged.emit()

    def check_wifi_interface(self):
        """Check if WiFi interface is available and log status"""
        try:
            is_windows = platform.system() == 'Windows'

            if is_windows:
                # Check if WLAN interface exists on Windows
                result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                      capture_output=True, text=True, timeout=5)
                if 'wlan' in result.stdout.lower() or 'wireless' in result.stdout.lower():
                    logger.info("WiFi interface detected on Windows")
                else:
                    logger.warning("No WiFi interface detected on Windows")
            else:
                # Check wireless interfaces on Linux using nmcli
                try:
                    result = subprocess.run(['nmcli', 'device', 'status'],
                                          capture_output=True, text=True, timeout=5)
                    if 'wifi' in result.stdout.lower():
                        logger.info("WiFi interface detected on Linux via nmcli")
                    else:
                        logger.warning("No WiFi interface detected via nmcli")
                except:
                    # Fallback to ip command
                    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                    wifi_found = False

                    for interface in interfaces:
                        try:
                            result = subprocess.run(['ip', 'link', 'show', interface],
                                                 capture_output=True, text=True, timeout=5)
                            if result.returncode == 0:
                                logger.info(f"WiFi interface {interface} detected on Linux")
                                wifi_found = True
                                break
                        except:
                            continue

                    if not wifi_found:
                        logger.warning("No WiFi interface detected on Linux")

                # Check if nmcli is available (preferred for Ubuntu)
                try:
                    nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=2)
                    if nmcli_check.returncode == 0:
                        logger.info("nmcli available - full WiFi functionality supported")
                    else:
                        logger.warning("nmcli not available - limited WiFi functionality. Install with: sudo apt install network-manager")
                except:
                    logger.warning("Error checking nmcli availability")

        except Exception as e:
            logger.error(f"Error checking WiFi interface: {e}")

    @pyqtSlot(result=str)
    def getWifiInterfaceInfo(self):
        """Get information about the WiFi interface for debugging"""
        try:
            is_windows = platform.system() == 'Windows'
            
            if is_windows:
                result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], 
                                      capture_output=True, text=True, timeout=5)
                return f"Windows WiFi Interfaces:\n{result.stdout}"
            else:
                # Get interface info for all wireless interfaces
                interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                info_lines = ["Linux Wireless Interfaces:"]
                
                for interface in interfaces:
                    try:
                        # Get interface info
                        ip_result = subprocess.run(['ip', 'addr', 'show', interface], 
                                                 capture_output=True, text=True, timeout=5)
                        
                        if ip_result.returncode == 0:
                            info_lines.append(f"\n--- {interface} ---")
                            info_lines.append(ip_result.stdout.strip())
                            
                            # Get wireless info
                            try:
                                iw_result = subprocess.run(['iwconfig', interface], 
                                                         capture_output=True, text=True, timeout=5)
                                info_lines.append("Wireless Info:")
                                info_lines.append(iw_result.stdout.strip())
                            except:
                                info_lines.append("Wireless Info: Not available (iwconfig not found)")
                    except:
                        continue
                
                if len(info_lines) == 1:
                    info_lines.append("No wireless interfaces found")
                
                return "\n".join(info_lines)
        except Exception as e:
            return f"Error getting WiFi interface info: {e}"

class PyQtGraphItem(QQuickPaintedItem):
    dataChanged = pyqtSignal()
    chartTypeChanged = pyqtSignal()
    monthsChanged = pyqtSignal()
    themeChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._chart_type = 'bar'
        self._months = []
        self._theme = 'dark'
        self.widget = pg.PlotWidget()
        self.plot_item = self.widget.plotItem

        # Enhanced styling setup
        self.setup_enhanced_styling()

        self.bar_items = []
        self.line_items = []
        self.area_items = []

        # Set initial view range
        self.update_view_range(10)

    def geometryChanged(self, newGeometry, oldGeometry):
        """Handle geometry changes to ensure proper sizing"""
        super().geometryChanged(newGeometry, oldGeometry)
        if self.widget:
            self.widget.resize(int(newGeometry.width()), int(newGeometry.height()))
            # Update the plot item's view box to match the new geometry
            view_box = self.plot_item.getViewBox()
            view_box.setGeometry(QRectF(0, 0, newGeometry.width(), newGeometry.height()))
            view_box.updateViewRange()
            
            # Also set the plot item geometry
            self.plot_item.setGeometry(QRectF(0, 0, newGeometry.width(), newGeometry.height()))
            
            self.widget.updateGeometry()
            self.plot_item.updateGeometry()
            self.update_plot()
            self.update()

    def setup_enhanced_styling(self):
        """Setup modern, Tesla-inspired chart styling"""
        # Configure plot appearance
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        # Set transparent background for theme integration
        self.widget.setBackground('transparent')
        
        # Remove any margins from the widget and ensure it fills the entire area
        self.widget.setContentsMargins(0, 0, 0, 0)
        if self.widget.layout():
            self.widget.layout().setContentsMargins(0, 0, 0, 0)
            self.widget.layout().setSpacing(0)
        
        # Ensure the plot item fills the entire widget
        self.plot_item.setContentsMargins(0, 0, 0, 0)
        self.plot_item.getViewBox().setContentsMargins(0, 0, 0, 0)

        # Enhanced grid styling
        grid_pen = pg.mkPen(color=(255, 255, 255, 50) if self._theme == 'dark' else (0, 0, 0, 30), width=1, style=Qt.PenStyle.DotLine)
        self.plot_item.getAxis('left').setGrid(50)
        self.plot_item.getAxis('bottom').setGrid(50)
        self.plot_item.getAxis('left').setPen(grid_pen)
        self.plot_item.getAxis('bottom').setPen(grid_pen)

        # Keep axis lines visible for better chart readability
        # self.plot_item.getAxis('left').setPen(None)
        # self.plot_item.getAxis('bottom').setPen(None)

        # Enhanced legend
        legend = self.plot_item.addLegend(offset=(-10, 10))
        legend.setBrush(pg.mkBrush(color=(0, 0, 0, 180) if self._theme == 'dark' else (255, 255, 255, 220)))
        # Note: LegendItem doesn't have setBorder method in this version of PyQtGraph

        # Disable auto range for precise control
        self.plot_item.getViewBox().enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        self.plot_item.getViewBox().enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)
        self.plot_item.getViewBox().clipToView = False

        # Add subtle background pattern
        self.add_background_pattern()

    def add_background_pattern(self):
        """Add subtle background pattern for depth"""
        # Create a subtle gradient background
        gradient = pg.LinearRegionItem([0, 1], orientation=pg.LinearRegionItem.Horizontal)
        gradient.setBrush(pg.mkBrush(color=(255, 255, 255, 10) if self._theme == 'dark' else (0, 0, 0, 5)))
        gradient.setMovable(False)
        gradient.setBounds([0, 1])
        self.plot_item.addItem(gradient, ignoreBounds=True)

    @pyqtProperty('QVariantList', notify=dataChanged)
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self.update_plot()
        self.update()  # Force repaint

    @pyqtProperty(str, notify=chartTypeChanged)
    def chartType(self):
        return self._chart_type

    @chartType.setter
    def chartType(self, value):
        self._chart_type = value
        self.update_plot()
        self.update()  # Force repaint

    @pyqtProperty('QVariantList', notify=monthsChanged)
    def months(self):
        return self._months

    @months.setter
    def months(self, value):
        self._months = value
        self.update_plot()
        self.update()  # Force repaint

    @pyqtProperty(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        self._theme = value
        self.update_theme()
        self.update_plot()
        self.update()  # Force repaint

    def update_theme(self):
        """Update chart colors based on theme"""
        # Update grid colors
        grid_alpha = 50 if self._theme == 'dark' else 30
        grid_pen = pg.mkPen(color=(255, 255, 255, grid_alpha) if self._theme == 'dark' else (0, 0, 0, grid_alpha), width=1, style=Qt.PenStyle.DotLine)
        self.plot_item.getAxis('left').setGrid(grid_alpha)
        self.plot_item.getAxis('bottom').setGrid(grid_alpha)

        # Update legend
        legend_brush = pg.mkBrush(color=(0, 0, 0, 180) if self._theme == 'dark' else (255, 255, 255, 220))
        legend_border = pg.mkPen(color=(255, 255, 255, 100) if self._theme == 'dark' else (0, 0, 0, 100))
        if hasattr(self.plot_item, 'legend'):
            self.plot_item.legend.setBrush(legend_brush)
            # Note: LegendItem doesn't have setBorder method in this version of PyQtGraph
            # self.plot_item.legend.setBorder(legend_border)

    def update_plot(self):
        self.plot_item.clear()

        # Re-setup styling after clear
        self.setup_enhanced_styling()

        if not self._data:
            return

        max_y = 0
        for series in self._data:
            if isinstance(series, dict) and 'values' in series and series['values']:
                max_y = max(max_y, max(series['values']))

        if max_y == 0:
            max_y = 10

        # Enhanced color palette inspired by Tesla's design
        colors = self.get_enhanced_colors()

        if self._chart_type == 'bar':
            self.render_enhanced_bar_chart(colors, max_y)
        elif self._chart_type == 'area':
            self.render_enhanced_area_chart(colors, max_y)
        else:  # line chart
            self.render_enhanced_line_chart(colors, max_y)

        # Enhanced axis labels
        self.setup_enhanced_axes()

        # Update view range with smooth animation
        self.update_view_range(max_y)

    def get_enhanced_colors(self):
        """Get Tesla-inspired color palette"""
        if self._theme == 'dark':
            return [
                {'primary': '#00D4FF', 'secondary': '#0088CC', 'gradient': [('#00D4FF', 0.8), ('#0088CC', 0.3)]},  # Electric blue
                {'primary': '#FF6B6B', 'secondary': '#CC4444', 'gradient': [('#FF6B6B', 0.8), ('#CC4444', 0.3)]},  # Energy red
                {'primary': '#4ECDC4', 'secondary': '#26A69A', 'gradient': [('#4ECDC4', 0.8), ('#26A69A', 0.3)]}   # Cool teal
            ]
        else:
            return [
                {'primary': '#0066CC', 'secondary': '#004499', 'gradient': [('#0066CC', 0.9), ('#004499', 0.4)]},  # Deep blue
                {'primary': '#FF4444', 'secondary': '#CC2222', 'gradient': [('#FF4444', 0.9), ('#CC2222', 0.4)]},  # Bright red
                {'primary': '#00AA88', 'secondary': '#008866', 'gradient': [('#00AA88', 0.9), ('#008866', 0.4)]}   # Ocean green
            ]

    def render_enhanced_bar_chart(self, colors, max_y):
        """Render modern bar chart with gradients and effects"""
        bar_width = 0.8 / len(self._data) if len(self._data) > 1 else 0.6

        for i, series in enumerate(self._data):
            if not (isinstance(series, dict) and 'values' in series and series['values']):
                continue

            color_scheme = colors[i % len(colors)]
            x_positions = []

            for j, value in enumerate(series['values']):
                if len(self._data) > 1:
                    x_pos = j + (i - len(self._data)/2 + 0.5) * bar_width
                else:
                    x_pos = j

                x_positions.append(x_pos)

                # Create gradient brush for 3D effect
                gradient = pg.mkBrush(color=pg.mkColor(color_scheme['primary']))
                bar = pg.BarGraphItem(
                    x=[x_pos], height=[value], width=bar_width,
                    brush=gradient, pen=pg.mkPen(color=pg.mkColor(color_scheme['secondary']), width=1)
                )

                # Add glow effect
                glow_color = pg.mkColor(color_scheme['primary'])
                glow_color.setAlphaF(0.3)
                glow_bar = pg.BarGraphItem(
                    x=[x_pos], height=[value], width=bar_width * 1.1,
                    brush=pg.mkBrush(color=glow_color),
                    pen=None
                )
                self.plot_item.addItem(glow_bar)
                self.plot_item.addItem(bar)

                # Add value labels on top of bars
                if value > 0:
                    label = pg.TextItem(text=str(int(value)), color=pg.mkColor(color_scheme['secondary']), anchor=(0.5, -0.5))
                    label.setPos(x_pos, value + max_y * 0.02)
                    self.plot_item.addItem(label)

        # Enhanced x-axis ticks
        if self._months and self._chart_type == 'bar':
            ticks = [[(i, month) for i, month in enumerate(self._months)]]
            axis = self.plot_item.getAxis('bottom')
            axis.setTicks(ticks)
            axis.setStyle(tickTextOffset=10)

    def render_enhanced_area_chart(self, colors, max_y):
        """Render modern area chart with smooth gradients"""
        for i, series in enumerate(self._data):
            if not (isinstance(series, dict) and 'values' in series and series['values']):
                continue

            color_scheme = colors[i % len(colors)]
            x = list(range(len(series['values'])))
            y = series['values']

            # Create smooth curve for area chart
            if len(x) > 2:
                try:
                    from scipy import interpolate
                    f = interpolate.interp1d(x, y, kind='cubic')
                    x_smooth = [i/10.0 for i in range(len(x)*10)]
                    y_smooth = f(x_smooth)
                    x, y = x_smooth, y_smooth
                except ImportError:
                    pass  # Fall back to original data if scipy not available

            # Create gradient fill for area
            area_color = pg.mkColor(color_scheme['primary'])
            area_color.setAlphaF(0.47)  # Semi-transparent for area effect (120/255 ≈ 0.47)

            # Create area fill
            fill_x = x + x[::-1]
            fill_y = y + [0] * len(y)

            area_brush = pg.mkBrush(color=area_color)
            fill_curve = pg.PlotCurveItem(x=fill_x, y=fill_y, brush=area_brush, pen=None)
            self.plot_item.addItem(fill_curve)

            # Add gradient overlay for depth
            gradient_color = pg.mkColor(color_scheme['secondary'])
            gradient_color.setAlphaF(0.235)  # Semi-transparent for gradient effect (60/255 ≈ 0.235)
            gradient_fill = pg.PlotCurveItem(
                x=fill_x, y=fill_y,
                brush=pg.mkBrush(color=gradient_color),
                pen=None
            )
            self.plot_item.addItem(gradient_fill)

            # Main line on top
            pen = pg.mkPen(
                color=pg.mkColor(color_scheme['primary']),
                width=2,
                style=Qt.PenStyle.SolidLine,
                cap=Qt.PenCapStyle.RoundCap,
                join=Qt.PenJoinStyle.RoundJoin
            )

            line_curve = pg.PlotCurveItem(x=x, y=y, pen=pen)
            self.plot_item.addItem(line_curve)

            # Add subtle data points
            for px, py in zip(x[::20], y[::20]):  # Every 20th point for area chart
                point = pg.ScatterPlotItem(
                    x=[px], y=[py], size=4,
                    brush=pg.mkBrush(color=color_scheme['secondary']),
                    pen=pg.mkPen(color=color_scheme['primary'], width=1)
                )
                self.plot_item.addItem(point)

    def render_enhanced_line_chart(self, colors, max_y):
        """Render modern line chart with smooth curves and data points"""
        for i, series in enumerate(self._data):
            if not (isinstance(series, dict) and 'values' in series and series['values']):
                continue

            color_scheme = colors[i % len(colors)]
            x = list(range(len(series['values'])))
            y = series['values']

            # Smooth the line using interpolation
            if len(x) > 2:
                try:
                    from scipy import interpolate
                    f = interpolate.interp1d(x, y, kind='cubic')
                    x_smooth = [i/10.0 for i in range(len(x)*10)]
                    y_smooth = f(x_smooth)
                    x, y = x_smooth, y_smooth
                except ImportError:
                    pass  # Fall back to original data if interpolation fails

            # Main line with enhanced styling
            pen = pg.mkPen(
                color=color_scheme['primary'],
                width=3,
                style=Qt.PenStyle.SolidLine,
                cap=Qt.PenCapStyle.RoundCap,
                join=Qt.PenJoinStyle.RoundJoin
            )

            line_curve = pg.PlotCurveItem(x=x, y=y, pen=pen)
            self.plot_item.addItem(line_curve)

            # Add data points with glow effect
            for px, py in zip(x[::10], y[::10]):  # Every 10th point to avoid overcrowding
                # Glow point
                glow_color = pg.mkColor(color_scheme['primary'])
                glow_color.setAlphaF(0.3)
                glow_point = pg.ScatterPlotItem(
                    x=[px], y=[py], size=12,
                    brush=pg.mkBrush(color=glow_color),
                    pen=None
                )
                self.plot_item.addItem(glow_point)

                # Main point
                point = pg.ScatterPlotItem(
                    x=[px], y=[py], size=6,
                    brush=pg.mkBrush(color=pg.mkColor(color_scheme['secondary'])),
                    pen=pg.mkPen(color=pg.mkColor(color_scheme['primary']), width=2)
                )
                self.plot_item.addItem(point)

    def setup_enhanced_axes(self):
        """Setup enhanced axis styling"""
        # Enhanced axis labels
        font_color = (255, 255, 255) if self._theme == 'dark' else (0, 0, 0)

        left_axis = self.plot_item.getAxis('left')
        left_axis.setLabel('Launches', color=font_color, size='12pt', bold=True)
        left_axis.setStyle(tickTextHeight=12, tickTextWidth=50)
        left_axis.show()  # Ensure axis is visible
        left_axis.setVisible(True)  # Make sure axis is visible

        bottom_axis = self.plot_item.getAxis('bottom')
        bottom_label = 'Months' if self._chart_type == 'bar' else 'Day of Year'
        bottom_axis.setLabel(bottom_label, color=font_color, size='12pt', bold=True)
        bottom_axis.setStyle(tickTextHeight=12, tickTextWidth=50)
        bottom_axis.show()  # Ensure axis is visible
        bottom_axis.setVisible(True)  # Make sure axis is visible

        # Rotate bottom labels for better readability
        if self._chart_type == 'bar' and len(self._months) > 6:
            bottom_axis.setStyle(tickTextOffset=15)

    def update_view_range(self, max_y):
        """Update view range with smooth padding"""
        # Get the maximum length across all data series
        x_len = 12  # default
        if self._data:
            x_len = max(len(series.get('values', [])) for series in self._data if isinstance(series, dict) and 'values' in series)

        y_padding = max_y * 0.1  # 10% padding

        if self._chart_type == 'bar':
            x_range = (-0.5, x_len - 0.5)
        else:
            x_range = (-0.1 * x_len, x_len * 1.1)  # Extra padding for line chart

        y_range = (0, max_y + y_padding)  # Start from 0 instead of negative padding

        # Set range directly and ensure it's applied
        view_box = self.plot_item.getViewBox()
        
        # Enable auto range temporarily to ensure proper initialization
        view_box.enableAutoRange(axis=pg.ViewBox.XAxis, enable=True)
        view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        
        # Set the ranges
        view_box.setXRange(x_range[0], x_range[1], padding=0)
        view_box.setYRange(y_range[0], y_range[1], padding=0)

        # Disable auto range
        view_box.enableAutoRange(axis=pg.ViewBox.XAxis, enable=False)
        view_box.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        # Also set axis ranges directly for better control
        self.plot_item.getAxis('left').setRange(y_range[0], y_range[1])
        self.plot_item.getAxis('bottom').setRange(x_range[0], x_range[1])

        # Force view box to update its internal state
        view_box.updateViewRange()

        # Force update to ensure changes are visible
        self.plot_item.update()
        self.widget.update()
        self.update()

    def paint(self, painter):
        rect = QRectF(0, 0, self.width(), self.height())
        if self.width() > 0 and self.height() > 0:
            # Ensure widget is properly sized
            self.widget.resize(int(self.width()), int(self.height()))
            
            # Force layout update if layout exists
            if self.widget.layout():
                self.widget.layout().update()
            self.widget.updateGeometry()
            self.widget.update()
            
            # Render the entire widget directly
            self.widget.render(painter, rect, rect.toRect())
        else:
            # Fallback for zero size
            painter.fillRect(rect, Qt.GlobalColor.white if self._theme == 'light' else Qt.GlobalColor.black)

if __name__ == '__main__':
    # Set console encoding to UTF-8 to handle Unicode characters properly
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    
    logger.info("Starting SpaceX Dashboard application...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Qt version available: {QApplication.instance() is None}")
    
    # Force hardware acceleration for Qt and Chromium
    if platform.system() == 'Windows':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
            "--disable-web-security --allow-running-insecure-content "
            "--disable-gpu-sandbox --disable-software-rasterizer "
            "--disable-gpu-driver-bug-workarounds --no-sandbox"
        )
    elif platform.system() == 'Linux':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-webgl "
            "--disable-gpu-sandbox --no-sandbox --use-gl=egl "
            "--disable-web-security --allow-running-insecure-content "
            "--gpu-testing-vendor-id=0xFFFF --gpu-testing-device-id=0xFFFF "
            "--disable-gpu-driver-bug-workarounds"
        )
    else:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
            "--disable-web-security --allow-running-insecure-content "
            "--disable-gpu-sandbox"
        )
    os.environ["QT_LOGGING_RULES"] = "qt5ct.debug=false;qt.webenginecontext=true"
    
    # Set platform-specific Qt platform plugin
    if platform.system() == 'Windows':
        os.environ["QT_QPA_PLATFORM"] = "windows"
        os.environ["QT_OPENGL"] = "desktop"  # Use desktop OpenGL on Windows
    elif platform.system() == 'Linux':
        # Raspberry Pi / Linux settings - use hardware acceleration with Mesa
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        # Remove QSG_RHI_BACKEND override - let Qt choose best backend (GL with Mesa)
        os.environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl" # Use EGL for hardware acceleration
        # LIBGL_ALWAYS_SOFTWARE is already set to "0" earlier for hardware rendering
        print("Linux platform detected - using hardware acceleration with Mesa drivers")
    else:
        os.environ["QSG_RHI_BACKEND"] = "gl"  # Default to OpenGL for other platforms
    
    # # Set QML style to Fusion
    # os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"
    
    QtWebEngineQuick.initialize()
    # Set style to Material before creating QApplication to support QML control customization
    material_style = QStyleFactory.create("Material")
    if material_style:
        QApplication.setStyle(material_style)
    else:
        # Fallback to Fusion if Material is not available
        fusion_style = QStyleFactory.create("Fusion")
        if fusion_style:
            QApplication.setStyle(fusion_style)
    
    app = QApplication(sys.argv)
    app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))  # Blank cursor globally

    # Load fonts
    font_path = os.path.join(os.path.dirname(__file__), "assets", "D-DIN.ttf")
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    # Load Font Awesome (assuming you place 'Font-Awesome.otf' in assets; download from fontawesome.com if needed)
    fa_path = os.path.join(os.path.dirname(__file__), "assets", "Font Awesome 5 Free-Solid-900.otf")
    if os.path.exists(fa_path):
        font_id = QFontDatabase.addApplicationFont(fa_path)
        if font_id == -1:
            logger.error("Failed to load Font Awesome font")
        else:
            logger.info(f"Font Awesome loaded successfully with ID: {font_id}")
            families = QFontDatabase.applicationFontFamilies(font_id)
            logger.info(f"Available font families: {families}")
    else:
        logger.error(f"Font Awesome font not found at: {fa_path}")

    engine = QQmlApplicationEngine()
    qmlRegisterType(PyQtGraphItem, 'MyModule', 1, 0, 'PyQtGraphItem')
    # Connect QML warnings signal (list of QQmlError objects)
    def _log_qml_warnings(errors):
        for e in errors:
            try:
                # Sanitize message to handle Unicode issues
                message = str(e.toString()).encode('utf-8', errors='replace').decode('utf-8')
                
                # Filter out style customization warnings as they're not critical
                if "current style does not support customization" in message:
                    continue
                    
                logger.error(f"QML warning: {message}")
            except Exception:
                logger.error("QML warning: <message encoding failed>")
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
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtCharts
import QtWebEngine
import MyModule 1.0

Window {
    id: root
    visible: true
    width: 1480
    height: 320
    title: "SpaceX/F1 Dashboard"
    color: backend.theme === "dark" ? "#1c2526" : "#ffffff"
    Behavior on color { ColorAnimation { duration: 300 } }

    Component.onCompleted: {
        console.log("Window created - bottom bar should be visible")
    }

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
                clip: false

                ColumnLayout {
                    anchors.fill: parent

                    Text {
                        text: backend.mode === "spacex" ? 
                               (backend.chartViewMode === "cumulative" ? 
                                (backend.chartType === "bar" ? "Cumulative Launch Trends (Bar)" : 
                                 backend.chartType === "line" ? "Cumulative Launch Trends (Line)" : "Cumulative Launch Trends (Area)") : 
                                (backend.chartType === "bar" ? "Monthly Launch Trends (Bar)" : 
                                 backend.chartType === "line" ? "Monthly Launch Trends (Line)" : "Monthly Launch Trends (Area)")) : 
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

                            PyQtGraphItem {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: false
                                data: backend.launchTrendsSeries
                                chartType: backend.chartType
                                months: backend.launchTrendsMonths
                                theme: backend.theme
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
                                            {"type": "line", "icon": "\uf201", "tooltip": "Line Chart"},
                                            {"type": "area", "icon": "\uf1fe", "tooltip": "Area Chart"}
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

        // Bottom bar - FIXED VERSION
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 10

                // Left pill (time and weather) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 400
                    Layout.maximumWidth: 400
                    height: 30
                    radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 10

                        Text {
                            text: backend.currentTime
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 12
                            font.family: "D-DIN"
                        }
                        Text {
                            text: {
                                var weather = backend.weather;
                                if (weather && weather.temperature_f !== undefined) {
                                    return "Wind " + (weather.wind_speed_kts || 0).toFixed(1) + " kts | " +
                                           (weather.temperature_f || 0).toFixed(1) + "°F";
                                }
                                return "Weather loading...";
                            }
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 12
                            font.family: "D-DIN"
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // WiFi icon - SIMPLIFIED
                Rectangle {
                    width: 30
                    height: 30
                    radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: backend.wifiConnected ? "W" : "w"  // Simplified, no Font Awesome
                        font.pixelSize: 12
                        font.bold: true
                        color: backend.wifiConnected ? "#4CAF50" : (backend.theme === "dark" ? "white" : "black")
                        font.family: "D-DIN"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            console.log("WiFi clicked - opening popup")
                            wifiPopup.open()
                            console.log("WiFi popup opened, visible:", wifiPopup.visible)
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Logo toggle - SIMPLIFIED
                Rectangle {
                    width: 80
                    height: 30
                    radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: backend.mode === "f1" ? "F1" : "SX"
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 12
                        font.bold: true
                        font.family: "D-DIN"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: backend.mode = backend.mode === "spacex" ? "f1" : "spacex"
                    }
                }

                Item { Layout.fillWidth: true }

                // Right pill (countdown, location, theme) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 450
                    Layout.maximumWidth: 450
                    height: 30
                    radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: backend.countdown
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 12
                            font.family: "D-DIN"
                        }

                        // Location selector
                        Row {
                            spacing: 2
                            Repeater {
                                model: ["Starbase", "Vandy", "Cape", "Hawthorne"]
                                Rectangle {
                                    width: 45
                                    height: 20
                                    color: backend.location === modelData ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    radius: 4
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.substring(0, 4)  // Abbreviate: Star, Vand, Cape, Hawt
                                        color: backend.theme === "dark" ? "white" : "black"
                                        font.pixelSize: 12
                                        font.family: "D-DIN"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: backend.location = modelData
                                    }
                                }
                            }
                        }

                        // Theme selector
                        Row {
                            spacing: 2
                            Repeater {
                                model: ["Light", "Dark"]
                                Rectangle {
                                    width: 35
                                    height: 20
                                    color: backend.theme === modelData.toLowerCase() ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                    radius: 4
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.substring(0, 1)  // L or D
                                        color: backend.theme === "dark" ? "white" : "black"
                                        font.pixelSize: 12
                                        font.bold: true
                                        font.family: "D-DIN"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: backend.theme = modelData.toLowerCase()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // WiFi popup
        Popup {
            id: wifiPopup
            width: 300
            height: 400
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                Text {
                    text: "WiFi Networks"
                    font.pixelSize: 18
                    font.bold: true
                    color: backend.theme === "dark" ? "white" : "black"
                    Layout.alignment: Qt.AlignHCenter
                }

                // Current connection status
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                    radius: 4
                    
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        
                        Text {
                            text: backend.wifiConnected ? "\uf1eb" : "\uf6ab"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 16
                            color: backend.wifiConnected ? "#4CAF50" : "#F44336"
                        }
                        
                        Text {
                            text: backend.wifiConnected ? ("Connected to " + backend.currentWifiSsid) : "Not connected"
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 12
                            Layout.fillWidth: true
                        }
                        
                        Button {
                            text: "Disconnect"
                            visible: backend.wifiConnected
                            onClicked: {
                                backend.disconnectWifi()
                                wifiPopup.close()
                            }
                            background: Rectangle {
                                color: "#F44336"
                                radius: 4
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                font.pixelSize: 10
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // Scan button
                Button {
                    text: backend.wifiConnecting ? "Connecting..." : "Scan Networks"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 35
                    enabled: !backend.wifiConnecting
                    onClicked: backend.scanWifiNetworks()
                    
                    background: Rectangle {
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                        radius: 4
                    }
                    
                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Debug info button (for troubleshooting)
                Button {
                    text: "Interface Info"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    onClicked: debugDialog.open()
                    
                    background: Rectangle {
                        color: backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0"
                        radius: 4
                    }
                    
                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                        font.pixelSize: 10
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Networks list
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backend.wifiNetworks
                    clip: true
                    spacing: 5
                    
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 50
                        color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                        radius: 4
                        
                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                
                                Text {
                                    text: modelData.ssid
                                    color: backend.theme === "dark" ? "white" : "black"
                                    font.pixelSize: 14
                                    font.bold: true
                                }
                                
                                RowLayout {
                                    spacing: 5
                                    
                                    Text {
                                        text: modelData.encrypted ? "\uf023" : "\uf09c"
                                        font.family: "Font Awesome 5 Free"
                                        font.pixelSize: 10
                                        color: modelData.encrypted ? "#FF9800" : "#4CAF50"
                                    }
                                    
                                    Text {
                                        text: "Signal: " + modelData.signal + " dBm"
                                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                                        font.pixelSize: 10
                                    }
                                }
                            }
                            
                            Button {
                                text: "Connect"
                                Layout.preferredWidth: 70
                                Layout.preferredHeight: 30
                                onClicked: {
                                    selectedNetwork = modelData.ssid
                                    passwordDialog.open()
                                }
                                
                                background: Rectangle {
                                    color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                                    radius: 4
                                }
                                
                                contentItem: Text {
                                    text: parent.text
                                    color: backend.theme === "dark" ? "white" : "black"
                                    font.pixelSize: 10
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        // Password dialog
        Popup {
            id: passwordDialog
            width: 280
            height: 180
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            property string selectedNetwork: ""

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 15

                Text {
                    text: "Enter password for " + passwordDialog.selectedNetwork
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }

                TextField {
                    id: passwordField
                    placeholderText: "Password"
                    echoMode: TextField.Password
                    Layout.fillWidth: true
                    Layout.preferredHeight: 35
                    
                    background: Rectangle {
                        color: backend.theme === "dark" ? "#1a1e1e" : "#ffffff"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#cccccc"
                        border.width: 1
                        radius: 4
                    }
                }

                RowLayout {
                    spacing: 10
                    
                    Button {
                        text: "Cancel"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 35
                        onClicked: {
                            passwordField.text = ""
                            passwordDialog.close()
                        }
                        
                        background: Rectangle {
                            color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                            radius: 4
                        }
                        
                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                    
                    Button {
                        text: "Connect"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 35
                        onClicked: {
                            backend.connectToWifi(passwordDialog.selectedNetwork, passwordField.text)
                            passwordField.text = ""
                            passwordDialog.close()
                            wifiPopup.close()
                        }
                        
                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 4
                        }
                        
                        contentItem: Text {
                            text: parent.text
                            color: "white"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // Debug info dialog
        Popup {
            id: debugDialog
            width: 400
            height: 300
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 15

                Text {
                    text: "WiFi Interface Information"
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 16
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    
                    TextArea {
                        id: debugText
                        text: backend.getWifiInterfaceInfo()
                        readOnly: true
                        wrapMode: TextArea.Wrap
                        background: Rectangle {
                            color: backend.theme === "dark" ? "#1a1e1e" : "#ffffff"
                            border.color: backend.theme === "dark" ? "#3a3e3e" : "#cccccc"
                            border.width: 1
                            radius: 4
                        }
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 10
                        font.family: "Courier New"
                    }
                }

                Button {
                    text: "Refresh"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 35
                    onClicked: debugText.text = backend.getWifiInterfaceInfo()
                    
                    background: Rectangle {
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                        radius: 4
                    }
                    
                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
    }
}
    """

    # Load QML from string (for complete single file)
    engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
    if not engine.rootObjects():
        logger.error("QML root object creation failed (see earlier QML errors above).")
        print("QML load failed. Check console for Qt errors.")
        sys.exit(-1)
    sys.exit(app.exec())