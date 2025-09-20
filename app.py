import sys
import requests
import os
import json
import platform
from PyQt6.QtWidgets import QApplication, QStyleFactory, QGraphicsScene
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtProperty, QObject, QAbstractListModel, QModelIndex, QVariant, pyqtSlot, qInstallMessageHandler, QRectF, QPoint, QDir, QThread
from PyQt6.QtGui import QFontDatabase, QCursor, QRegion, QPainter, QPen, QBrush, QColor
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
import subprocess
import re
import calendar
# DBus imports are now conditional and imported only on Linux
# import dbus
# import dbus.mainloop.glib
# from gi.repository import GLib

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
CACHE_REFRESH_INTERVAL_PREVIOUS = 86400  # 24 hours for historical data
CACHE_REFRESH_INTERVAL_UPCOMING = 3600   # 1 hour for upcoming launches
CACHE_REFRESH_INTERVAL_F1 = 3600         # 1 hour for F1 data
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
    if previous_cache and (current_time - previous_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_PREVIOUS:
        previous_launches = previous_cache['data']
        logger.info("Using persistent cached previous launches")
    else:
        try:
            url = f'https://ll.thespacedevs.com/2.0.0/launch/previous/?lsp__name=SpaceX&net__gte={current_year}-01-01&net__lte={current_year}-12-31&limit=100'
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
    if upcoming_cache and (current_time - upcoming_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_UPCOMING:
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
    if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1:
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
                    grouped.append({'group': "Today's Launches 🚀"})
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
                    grouped.append({'group': "Today's Launches 🚀"})
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
                    grouped.append({'group': "Today's Races 🏎️"})
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

class DataLoader(QObject):
    finished = pyqtSignal(dict, dict, dict)

    def run(self):
        launch_data = fetch_launches()
        f1_data = fetch_f1_data()
        weather_data = {}
        for location, settings in location_settings.items():
            try:
                weather = fetch_weather(settings['lat'], settings['lon'], location)
                weather_data[location] = weather
            except Exception as e:
                weather_data[location] = {
                    'temperature_c': 25,
                    'temperature_f': 77,
                    'wind_speed_ms': 5,
                    'wind_speed_kts': 9.7,
                    'wind_direction': 90,
                    'cloud_cover': 50
                }
        self.finished.emit(launch_data, f1_data, weather_data)

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
    loadingFinished = pyqtSignal()

    def __init__(self):
        super().__init__()
        logger.info("Backend initializing...")
        self._mode = 'spacex'
        self._event_type = 'upcoming'
        self._theme = 'dark'
        self._location = 'Starbase'
        self._chart_view_mode = 'actual'  # 'actual' or 'cumulative'
        self._chart_type = 'bar'  # 'bar' or 'line'
        self._f1_chart_stat = 'points'  # 'points', 'wins', etc.
        self._isLoading = True
        self._launch_data = {'previous': [], 'upcoming': []}
        self._f1_data = {'schedule': [], 'driver_standings': [], 'constructor_standings': []}
        self._weather_data = {}
        self._tz = pytz.timezone(location_settings[self._location]['timezone'])
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self._launch_trends_cache = {}  # Cache for launch trends series
        
        # WiFi properties
        self._wifi_networks = []
        self._wifi_connected = False
        self._wifi_connecting = False
        self._current_wifi_ssid = ""

        # Start loading data in background
        self.loader = DataLoader()
        self.thread = QThread()
        self.loader.moveToThread(self.thread)
        self.loader.finished.connect(self.on_data_loaded)
        self.thread.started.connect(self.loader.run)
        self.thread.start()

        logger.info("Setting up timers...")
        # Timers
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(300000)

        self.launch_timer = QTimer(self)
        self.launch_timer.timeout.connect(self.update_launches_periodic)
        self.launch_timer.start(CACHE_REFRESH_INTERVAL_UPCOMING * 1000)

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

        # WiFi timer for status updates
        self.wifi_timer = QTimer(self)
        self.wifi_timer.timeout.connect(self.update_wifi_status)
        # Don't start timer automatically - only when WiFi popup is open
        
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

    @pyqtProperty(bool, notify=loadingFinished)
    def isLoading(self):
        return self._isLoading

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
        if df.empty:
            return {'months': [], 'series': []}
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
        launches = self._launch_data['previous']
        df = pd.DataFrame(launches)
        if df.empty:
            return []
        df['date'] = pd.to_datetime(df['date'])
        current_year = datetime.now(pytz.UTC).year
        df = df[df['date'].dt.year == current_year]
        rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
        df = df[df['rocket'].isin(rocket_types)]
        df['month'] = df['date'].dt.to_period('M').astype(str)
        df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
        df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)
        months = df_pivot.index.tolist()
        return months

    @pyqtProperty(int, notify=launchesChanged)
    def launchTrendsMaxValue(self):
        launches = self._launch_data['previous']
        df = pd.DataFrame(launches)
        if df.empty:
            return 0
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
        if self._chart_view_mode == 'cumulative':
            for col in rocket_types:
                df_pivot[col] = df_pivot[col].cumsum()
        # Return the maximum value across all series
        return int(df_pivot.max().max())

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
        launches = self._launch_data['previous']
        df = pd.DataFrame(launches)
        if df.empty:
            return []
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
        if self._chart_view_mode == 'cumulative':
            for col in rocket_types:
                df_pivot[col] = df_pivot[col].cumsum()
        data = []
        for rocket in rocket_types:
            data.append({
                'label': rocket,
                'values': df_pivot[rocket].tolist()
            })
        return data

    @pyqtProperty(list, notify=f1Changed)
    def driverStandings(self):
        return self._f1_data['driver_standings']

    @pyqtProperty(list, notify=f1Changed)
    def raceCalendar(self):
        return sorted(self._f1_data['schedule'], key=lambda x: parse(x['date_start']))

    @pyqtProperty(list, notify=f1Changed)
    def constructorStandings(self):
        return self._f1_data['constructor_standings']

    @pyqtProperty(QVariant, notify=f1Changed)
    def driverPointsChart(self):
        standings = self._f1_data['driver_standings']
        if not standings:
            return []
        
        # Get top 10 drivers
        top_drivers = standings[:10]
        data = []
        for driver in top_drivers:
            data.append({
                'label': f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}",
                'value': float(driver['points'])
            })
        return data

    @pyqtProperty(QVariant, notify=f1Changed)
    def constructorPointsChart(self):
        standings = self._f1_data['constructor_standings']
        if not standings:
            return []
        
        # Get top 10 constructors
        top_constructors = standings[:10]
        data = []
        for constructor in top_constructors:
            data.append({
                'label': constructor['Constructor']['name'],
                'value': float(constructor['points'])
            })
        return data

    @pyqtProperty(QVariant, notify=f1Changed)
    def driverPointsSeries(self):
        standings = self._f1_data['driver_standings']
        if not standings:
            return []
        
        # Get top 10 drivers
        top_drivers = standings[:10]
        stat_key = getattr(self, '_f1_chart_stat', 'points')
        values = [float(driver.get(stat_key, 0)) for driver in top_drivers]
        return [{'label': stat_key.title(), 'values': values}]

    @pyqtProperty(QVariant, notify=f1Changed)
    def constructorPointsSeries(self):
        standings = self._f1_data['constructor_standings']
        if not standings:
            return []
        
        # Get top 10 constructors
        top_constructors = standings[:10]
        stat_key = getattr(self, '_f1_chart_stat', 'points')
        values = [float(constructor.get(stat_key, 0)) for constructor in top_constructors]
        return [{'label': stat_key.title(), 'values': values}]

    @pyqtProperty(list, notify=f1Changed)
    def driverNames(self):
        standings = self._f1_data['driver_standings']
        if not standings:
            return []
        
        # Get top 10 drivers
        top_drivers = standings[:10]
        return [f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}" for driver in top_drivers]

    @pyqtProperty(list, notify=f1Changed)
    def constructorNames(self):
        standings = self._f1_data['constructor_standings']
        if not standings:
            return []
        
        # Get top 10 constructors
        top_constructors = standings[:10]
        return [constructor['Constructor']['name'] for constructor in top_constructors]

    @pyqtProperty(float, notify=f1Changed)
    def driverPointsMaxValue(self):
        standings = self._f1_data['driver_standings']
        if not standings:
            return 0
        
        # Get top 10 drivers
        top_drivers = standings[:10]
        stat_key = getattr(self, '_f1_chart_stat', 'points')
        max_value = max([float(driver.get(stat_key, 0)) for driver in top_drivers]) if top_drivers else 0
        return max_value

    @pyqtProperty(float, notify=f1Changed)
    def constructorPointsMaxValue(self):
        standings = self._f1_data['constructor_standings']
        if not standings:
            return 0
        
        # Get top 10 constructors
        top_constructors = standings[:10]
        stat_key = getattr(self, '_f1_chart_stat', 'points')
        max_value = max([float(constructor.get(stat_key, 0)) for constructor in top_constructors]) if top_constructors else 0
        return max_value

    @pyqtProperty(str, notify=f1Changed)
    def f1ChartStat(self):
        return getattr(self, '_f1_chart_stat', 'points')

    @f1ChartStat.setter
    def f1ChartStat(self, value):
        if self._f1_chart_stat != value:
            self._f1_chart_stat = value
            self.f1Changed.emit()

    @pyqtProperty(list, notify=launchesChanged)
    def launchDescriptions(self):
        return [
            "7/1 2104: Falcon 9 hoists MTG-S1/Sentinel-4A to geosync from LC-39A; Ariane's loss is our nominal gain, booster recovered without drama.",
            "7/2 0425: 500th Falcon 9 ignites with 27 Starlinks from SLC-40; B1067 clocks 29th flight, orbit insertion as predictable as gravity.",
            "7/8 0545: Another 28 Starlinks flung to LEO via Falcon 9 at SLC-40; deployment flawless, booster sticks the landing like it's bored.",
            "7/13 0504: Dror-1 comsat dispatched to GTO by Falcon 9 from SLC-40; 500th success tallied, technical specs holding steady.",
            "7/16 0230: Falcon 9 from SLC-4E deploys 26 Starlinks to LEO; trajectory spot-on, recovery droneship reports no complaints.",
            "7/16 0610: 24 KuiperSats for Amazon lofted by Falcon 9 at SLC-40; ironic assist to rivals, payloads separate cleanly in orbit.",
            "7/19 0352: 24 Starlinks to SSO courtesy of Falcon 9 from SLC-4E; booster separation nominal, landing pad greets old friend.",
            "7/22 2112: O3b mPOWER duo boosted to MEO by Falcon 9 at SLC-40; fairing jettisoned, engines perform without a hitch.",
            "7/23 1813: TRACERS twins and cubesat tag-alongs reach SSO on Falcon 9 from SLC-4E; NASA science in orbit, booster touchdown precise.",
            "7/26 0901: 28 Starlinks added to the constellation from SLC-40 Falcon 9; delta-v expended, satellites phoning home.",
            "7/27 0431: 24 Starlinks parked in SSO by Vandenberg Falcon 9; staging sequence textbook, droneship claims another.",
            "7/30 0337: B1085 hits 10 flights in year one with 28 Starlinks from SLC-40; Falcon efficiency borders on monotonous.",
            "7/31 1835: Falcon 9 SLC-4E sends 24 Starlinks to SSO; payload fairings pop, orbit achieved with kerbal-like precision.",
            "8/1 1543: Crew-11 Endeavour ferries four to ISS via Falcon 9 from LC-39A; docking smooth, human-rated reliability endures.",
            "8/4 0757: 28 Starlinks flung to LEO via Falcon 9 at SLC-40; deployment flawless, booster sticks the landing like it's bored.",
            "8/11 1235: 24 KuiperSats for Amazon lofted by Falcon 9 at SLC-4E; ironic assist to rivals, payloads separate cleanly in orbit.",
            "8/14 1200: 24 Starlinks to SSO courtesy of Falcon 9 from SLC-4E; booster separation nominal, landing pad greets old friend.",
            "8/14 1600: 28 Starlinks added to the constellation from SLC-40 Falcon 9; delta-v expended, satellites phoning home.",
            "8/18 1300: Falcon 9 SLC-4E sends 24 Starlinks to SSO; payload fairings pop, orbit achieved with kerbal-like precision.",
            "8/22 1800: X-37B OTV-8 secretly orbited by Falcon 9 from LC-39A; USSF-36 mission opaque, but booster recovery transparent.",
            "8/22 2200: Closing double-header: 24 Starlinks to SSO on Falcon 9 from SLC-4E; rapid cadence, flawless execution.",
            "8/26 1855: Falcon 9 from SLC-4E launches NAOS to orbit; booster nails LZ-4, parameters held steady.",
            "8/26 2331: Starship Flight 10 ignites from Starbase; hot-staging clean, ship splashes precisely in Indian Ocean, Super Heavy boosts back nominally.",
            "8/27 1104: 28 Starlinks flung to LEO via Falcon 9 at SLC-40; deployment flawless, booster sticks the landing like it's bored.",
            "8/28 0812: Falcon 9 from LC-39A deploys 28 Starlinks to LEO; booster on 30th reuse lands ASOG, reusability milestone dryly noted.",
            "8/30 0452: 24 Starlinks parked in SSO by Vandenberg Falcon 9; staging sequence textbook, droneship claims another.",
            "8/31 1142: Another 28 Starlinks flung to LEO via Falcon 9 at SLC-40; deployment flawless, booster sticks the landing like it's bored.",
            "9/3 0344: Falcon 9 from SLC-4E deploys 24 Starlinks to LEO; trajectory spot-on, recovery droneship reports no complaints.",
            "9/3 1149: 28 Starlinks added to the constellation from SLC-40 Falcon 9; delta-v expended, satellites phoning home.",
            "9/5 1225: 500th Falcon 9 ignites with 28 Starlinks from SLC-40; booster hits 10 flights, JRTI touchdown, efficiency reigns.",
            "9/6 1759: Falcon 9 from SLC-4E deploys 24 Starlinks to LEO; trajectory spot-on, recovery droneship reports no complaints.",
            "9/10 1412: Falcon 9 from SLC-4E boosts Space Force Tranche 1 to LEO; SDA payloads separate cleanly, OCISLY catches booster again.",
            "9/12 0203: Falcon 9 from SLC-40 dispatches Nusantara Lima comsat to GTO; booster settles on ASOG, insertion as planned.",
            "9/13 1748: Falcon 9 from SLC-4E completes 300th Starlink mission with 24 satellites to LEO; deployment spot-on, recovery droneship unfazed.",
            "9/14 2213: Falcon 9 from SLC-40 propels Northrop Grumman Cygnus XL to ISS; booster lands at LZ-2, cargo en route without incident.",
            "9/18 0930: Falcon 9 from SLC-40 flings 28 Starlinks to LEO; delta-v spotless, booster recovery monotonous."
        ]

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

    @pyqtSlot(dict, dict, dict)
    def on_data_loaded(self, launch_data, f1_data, weather_data):
        self._launch_data = launch_data
        self._f1_data = f1_data
        self._weather_data = weather_data
        # Update the EventModel's data reference
        self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
        self._event_model.update_data()
        self._isLoading = False
        self.loadingFinished.emit()
        self.launchesChanged.emit()
        self.f1Changed.emit()
        self.weatherChanged.emit()
        self.eventModelChanged.emit()
        self.thread.quit()
        self.thread.wait()

    @pyqtSlot()
    def scanWifiNetworks(self):
        """Scan for available WiFi networks using NetworkManager DBus API with robust error handling"""
        try:
            logger.info("Starting WiFi network scan...")
            is_windows = platform.system() == 'Windows'

            if is_windows:
                # Use Windows netsh command to scan for WiFi networks
                logger.info("Scanning WiFi networks using Windows netsh...")
                try:
                    result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                                          capture_output=True, text=True, timeout=15)

                    if result.returncode != 0:
                        logger.warning(f"netsh command failed: {result.stderr}")
                        raise Exception(f"netsh failed with return code {result.returncode}")

                    networks = []
                    current_ssid = None
                    current_network = None
                    network_map = {}  # Track networks by SSID to handle multiple BSSIDs
                    logger.debug(f"netsh output length: {len(result.stdout)}")

                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        logger.debug(f"Processing line: {line}")

                        # Look for SSID (new network)
                        if line.startswith('SSID') and ':' in line:
                            ssid_match = re.search(r'SSID\s*\d*\s*:\s*(.+)', line)
                            if ssid_match:
                                ssid = ssid_match.group(1).strip()
                                if ssid and ssid != '<disconnected>':
                                    current_ssid = ssid
                                    if current_ssid not in network_map:
                                        network_map[current_ssid] = {'ssid': current_ssid, 'signal': -100, 'encrypted': False}
                                    current_network = network_map[current_ssid]
                                    logger.debug(f"Processing network: {ssid}")
                                else:
                                    current_ssid = None
                                    current_network = None
                            else:
                                current_ssid = None
                                current_network = None

                        # Look for signal strength (take the strongest signal for each SSID)
                        elif line.startswith('Signal') and ':' in line and current_network:
                            signal_match = re.search(r'Signal\s*:\s*(\d+)%', line)
                            if signal_match:
                                percentage = int(signal_match.group(1))
                                # More accurate conversion from percentage to dBm
                                # Typical range: 0% = -100dBm, 100% = -30dBm
                                if percentage >= 0 and percentage <= 100:
                                    dbm = -100 + (percentage * 0.7)  # -100 to -30 range
                                    # Keep the strongest signal for this SSID
                                    if dbm > current_network['signal']:
                                        current_network['signal'] = int(dbm)
                                        logger.debug(f"Updated signal for {current_network['ssid']}: {percentage}% = {dbm}dBm")

                        # Look for authentication (encryption) - only set once per SSID
                        elif line.startswith('Authentication') and ':' in line and current_network and not current_network['encrypted']:
                            if 'WPA' in line or 'WPA2' in line or 'WPA3' in line or 'WEP' in line:
                                current_network['encrypted'] = True
                                logger.debug(f"Network {current_network['ssid']} is encrypted")

                    # Convert network_map to networks list
                    networks = list(network_map.values())
                    logger.info(f"Windows netsh scan found {len(networks)} unique networks")

                except subprocess.TimeoutExpired:
                    logger.error("Windows WiFi scan timed out")
                    networks = []
                except FileNotFoundError:
                    logger.error("netsh command not found - WiFi scanning not available on this Windows system")
                    networks = []
                except Exception as e:
                    logger.error(f"Windows WiFi scan failed: {e}")
                    networks = []
            else:
                # Use NetworkManager DBus API for proper Linux WiFi scanning
                logger.info("Scanning WiFi networks using NetworkManager DBus...")
                networks = []
                
                try:
                    # Import DBus modules only on Linux
                    import dbus
                    import dbus.mainloop.glib
                    from gi.repository import GLib
                    
                    # Initialize DBus main loop for Qt integration
                    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

                    # Get system bus
                    bus = dbus.SystemBus()

                    # Get NetworkManager object
                    nm = bus.get_object('org.freedesktop.NetworkManager', '/org/freedesktop/NetworkManager')
                    nm_interface = dbus.Interface(nm, 'org.freedesktop.NetworkManager')

                    # Get all devices
                    devices = nm_interface.GetDevices()
                    wifi_device = None

                    # Find the first wireless device
                    for device_path in devices:
                        try:
                            device = bus.get_object('org.freedesktop.NetworkManager', device_path)
                            device_interface = dbus.Interface(device, 'org.freedesktop.DBus.Properties')

                            device_type = device_interface.Get('org.freedesktop.NetworkManager.Device', 'DeviceType')
                            if device_type == 2:  # NM_DEVICE_TYPE_WIFI
                                wifi_device = device_path
                                break
                        except Exception as device_e:
                            logger.debug(f"Error checking device {device_path}: {device_e}")
                            continue

                    # Check device state before scanning
                    device_state = device_interface.Get('org.freedesktop.NetworkManager.Device', 'State')
                    logger.info(f"WiFi device state: {device_state}")

                    # Get additional device info for debugging
                    try:
                        device_managed = device_interface.Get('org.freedesktop.NetworkManager.Device', 'Managed')
                        logger.info(f"WiFi device managed: {device_managed}")
                    except Exception as info_e:
                        logger.debug(f"Could not get device managed status: {info_e}")

                    # Device states: 0=unknown, 10=unmanaged, 20=unavailable, 30=disconnected, 40=prepare, 50=config, 60=need auth, 70=ip config, 80=ip check, 90=secondaries, 100=activated, 110=deactivating, 120=failed
                    if device_state in [20, 120]:  # unavailable or failed
                        logger.warning(f"WiFi device is in state {device_state} (unavailable/failed), attempting to make it managed")
                        # Try to manage the device - this often happens when wpa_supplicant is controlling it
                        try:
                            # Check if device is in managed list
                            nm_props = dbus.Interface(nm, 'org.freedesktop.DBus.Properties')
                            managed_devices = nm_props.Get('org.freedesktop.NetworkManager', 'Devices')

                            if wifi_device not in managed_devices:
                                logger.info("Device not in managed list, attempting to manage it")
                                # Try to add device to managed list (this may require admin privileges)
                                # Note: This is a best-effort attempt
                            else:
                                logger.info("Device is in managed list but still unavailable - may be controlled by wpa_supplicant")

                                # Try more aggressive management takeover
                                logger.info("Attempting to force NetworkManager control...")
                                try:
                                    # Try to disconnect and reconnect the device
                                    device_interface.Disconnect()
                                    time.sleep(1)
                                    device_interface.Connect()
                                    time.sleep(2)

                                    # Check if state changed
                                    new_state = device_interface.Get('org.freedesktop.NetworkManager.Device', 'State')
                                    logger.info(f"Device state after reconnect attempt: {new_state}")

                                    if new_state != 20:
                                        logger.info("Device state improved after reconnect!")
                                        device_state = new_state
                                    else:
                                        logger.info("Device still unavailable after reconnect")

                                except Exception as reconnect_e:
                                    logger.debug(f"Reconnect attempt failed: {reconnect_e}")

                            # Try to request scan anyway - sometimes it works even in unavailable state
                            logger.info("Attempting scan despite unavailable state...")
                            wifi_device_obj = bus.get_object('org.freedesktop.NetworkManager', wifi_device)
                            wifi_interface = dbus.Interface(wifi_device_obj, 'org.freedesktop.NetworkManager.Device.Wireless')

                        except Exception as manage_e:
                            logger.warning(f"Could not manage unavailable device: {manage_e}")
                            # Continue anyway and try to scan
                            logger.info("Continuing with scan attempt despite management issues...")
                            wifi_device_obj = bus.get_object('org.freedesktop.NetworkManager', wifi_device)
                            wifi_interface = dbus.Interface(wifi_device_obj, 'org.freedesktop.NetworkManager.Device.Wireless')
                            # Continue anyway and try to scan - sometimes it works
                            wifi_device_obj = bus.get_object('org.freedesktop.NetworkManager', wifi_device)
                            wifi_interface = dbus.Interface(wifi_device_obj, 'org.freedesktop.NetworkManager.Device.Wireless')
                    elif device_state in [0, 10]:  # unknown or unmanaged
                        logger.warning(f"WiFi device is in state {device_state} (unknown/unmanaged), attempting to make it managed")
                        # Try to set device as managed
                        try:
                            nm_interface_props = dbus.Interface(nm, 'org.freedesktop.DBus.Properties')
                            managed_devices = nm_interface_props.Get('org.freedesktop.NetworkManager', 'Devices')
                            if wifi_device not in managed_devices:
                                logger.info("Device not in managed list, attempting to manage it")
                                # Note: This might require admin privileges
                        except Exception as manage_e:
                            logger.warning(f"Could not manage device: {manage_e}")

                    # At this point, we should have wifi_device_obj and wifi_interface set up
                    # (either from the unavailable case or the normal case)
                    if 'wifi_device_obj' not in locals():
                        wifi_device_obj = bus.get_object('org.freedesktop.NetworkManager', wifi_device)
                    if 'wifi_interface' not in locals():
                        wifi_interface = dbus.Interface(wifi_device_obj, 'org.freedesktop.NetworkManager.Device.Wireless')

                    # Request a scan
                    logger.info("Requesting WiFi scan via DBus...")
                    try:
                        wifi_interface.RequestScan({})  # Empty options dict
                    except Exception as scan_e:
                        logger.error(f"Scan request failed: {scan_e}")
                        raise Exception(f"Failed to request scan: {scan_e}")

                    # Wait a bit for scan to complete (NetworkManager handles this asynchronously)
                    time.sleep(3)

                    # Get access points
                    try:
                        access_points = wifi_interface.GetAllAccessPoints()
                        logger.info(f"Found {len(access_points)} access points")
                    except Exception as ap_e:
                        logger.error(f"Failed to get access points: {ap_e}")
                        raise Exception(f"Failed to get access points: {ap_e}")

                    for ap_path in access_points:
                        try:
                            ap_obj = bus.get_object('org.freedesktop.NetworkManager', ap_path)
                            ap_props = dbus.Interface(ap_obj, 'org.freedesktop.DBus.Properties')

                            # Get SSID
                            ssid_bytes = ap_props.Get('org.freedesktop.NetworkManager.AccessPoint', 'Ssid')
                            ssid = ''.join(chr(b) for b in ssid_bytes) if ssid_bytes else ''

                            if not ssid:
                                continue

                            # Get signal strength
                            strength = ap_props.Get('org.freedesktop.NetworkManager.AccessPoint', 'Strength')

                            # Get security flags
                            flags = ap_props.Get('org.freedesktop.NetworkManager.AccessPoint', 'Flags')
                            wpa_flags = ap_props.Get('org.freedesktop.NetworkManager.AccessPoint', 'WpaFlags')
                            rsn_flags = ap_props.Get('org.freedesktop.NetworkManager.AccessPoint', 'RsnFlags')

                            # Determine if encrypted
                            encrypted = bool(flags & 0x1) or bool(wpa_flags) or bool(rsn_flags)

                            networks.append({
                                'ssid': ssid,
                                'signal': strength,  # Already in 0-100 range
                                'encrypted': encrypted
                            })

                            logger.debug(f"Found network: {ssid}, signal: {strength}, encrypted: {encrypted}")

                        except Exception as e:
                            logger.debug(f"Error processing access point {ap_path}: {e}")
                            continue
                        
                except Exception as e:
                    logger.error(f"NetworkManager DBus scan failed: {e}")
                    logger.info("WiFi device is controlled by wpa_supplicant - attempting direct wpa_supplicant scan...")

                    # Try to scan directly via wpa_supplicant/wpa_cli
                    try:
                        # Check if wpa_cli is available
                        wpa_check = subprocess.run(['which', 'wpa_cli'], capture_output=True, timeout=3)
                        if wpa_check.returncode == 0:
                            logger.info("wpa_cli found, attempting direct wpa_supplicant scan")

                            # Try to scan using wpa_cli
                            scan_result = subprocess.run(['wpa_cli', '-i', 'wlan0', 'scan'],
                                                       capture_output=True, text=True, timeout=5)

                            if scan_result.returncode == 0:
                                logger.info("wpa_cli scan initiated successfully")

                                # Wait for scan results
                                time.sleep(3)

                                # Get scan results
                                results_result = subprocess.run(['wpa_cli', '-i', 'wlan0', 'scan_results'],
                                                              capture_output=True, text=True, timeout=5)

                                if results_result.returncode == 0 and results_result.stdout.strip():
                                    logger.info("wpa_cli scan results retrieved successfully")
                                    networks = []

                                    lines = results_result.stdout.strip().split('\n')
                                    # Skip header line
                                    for line in lines[1:]:
                                        logger.debug(f"Processing wpa_cli line: {line}")
                                        parts = line.split('\t')
                                        if len(parts) >= 5:
                                            # Format: bssid, frequency, signal, flags, ssid
                                            bssid = parts[0]
                                            frequency = parts[1]
                                            signal_level = int(parts[2]) if parts[2].isdigit() else -100
                                            flags = parts[3]
                                            ssid = parts[4] if len(parts) > 4 else ''

                                            if ssid and ssid != '<hidden>':
                                                # Convert signal level to percentage (rough approximation)
                                                # wpa_supplicant signal is in dBm, convert to 0-100 scale
                                                signal_percent = min(100, max(0, 100 + signal_level))

                                                encrypted = 'WPA' in flags or 'WEP' in flags

                                                networks.append({
                                                    'ssid': ssid,
                                                    'signal': signal_percent,
                                                    'encrypted': encrypted
                                                })
                                                logger.debug(f"Found network via wpa_cli: {ssid}, signal: {signal_percent}, encrypted: {encrypted}")

                                    logger.info(f"wpa_cli scan found {len(networks)} networks")
                                else:
                                    logger.warning("wpa_cli scan_results failed or returned empty")
                                    networks = []
                            else:
                                logger.warning(f"wpa_cli scan failed: {scan_result.stderr}")
                                networks = []
                        else:
                            logger.info("wpa_cli not found, trying nmcli fallback")
                            networks = []

                    except subprocess.TimeoutExpired:
                        logger.warning("wpa_cli scan timed out")
                        networks = []
                    except Exception as wpa_e:
                        logger.warning(f"wpa_cli scan failed: {wpa_e}")
                        networks = []

                    # If wpa_cli also failed, fall back to nmcli
                    if not networks:
                        logger.info("wpa_cli failed, trying nmcli fallback...")
                        try:
                            # nmcli fallback code here...
                            device_check = subprocess.run(['nmcli', 'device', 'show', 'wlan0'],
                                                        capture_output=True, text=True, timeout=5)

                            if device_check.returncode == 0:
                                logger.info("nmcli can access wlan0 device")

                                rescan_result = subprocess.run(['nmcli', 'device', 'wifi', 'rescan'],
                                                             capture_output=True, text=True, timeout=10)

                                if rescan_result.returncode == 0:
                                    logger.info("nmcli rescan completed successfully")
                                    time.sleep(2)

                                    list_result = subprocess.run(['nmcli', 'device', 'wifi', 'list'],
                                                               capture_output=True, text=True, timeout=10)

                                    if list_result.returncode == 0 and list_result.stdout.strip():
                                        logger.info("nmcli network list successful")
                                        networks = []

                                        lines = list_result.stdout.strip().split('\n')
                                        logger.debug(f"nmcli returned {len(lines)} lines")

                                        for line in lines[1:]:
                                            logger.debug(f"Processing nmcli line: {line}")
                                            parts = line.split()
                                            if len(parts) >= 7:
                                                ssid = parts[0] if parts[0] != '*' else (parts[1] if len(parts) > 1 else '')
                                                if ssid and ssid != '--':
                                                    signal_str = parts[4] if len(parts) > 4 else '0'
                                                    signal = int(signal_str) if signal_str.isdigit() else 0
                                                    security = parts[6] if len(parts) > 6 else ''
                                                    encrypted = 'WPA' in security or 'WEP' in security

                                                    networks.append({
                                                        'ssid': ssid,
                                                        'signal': signal,
                                                        'encrypted': encrypted
                                                    })
                                                    logger.debug(f"Found network via nmcli: {ssid}, signal: {signal}, encrypted: {encrypted}")

                                        logger.info(f"nmcli fallback found {len(networks)} networks")
                                    else:
                                        logger.warning(f"nmcli list failed: {list_result.stderr}")
                                        networks = []
                                else:
                                    logger.warning(f"nmcli rescan failed: {rescan_result.stderr}")
                                    networks = []
                            else:
                                logger.warning(f"nmcli cannot access wlan0: {device_check.stderr}")
                                networks = []

                        except Exception as nmcli_e:
                            logger.warning(f"nmcli fallback failed: {nmcli_e}")
                            networks = []

                    # Final fallback to iw current network
                    if not networks:
                        logger.info("All methods failed, trying simple iw fallback...")
                        try:
                            result = subprocess.run(['iw', 'dev', 'wlan0', 'link'],
                                                  capture_output=True, text=True, timeout=5)

                            if result.returncode == 0 and 'Connected' in result.stdout:
                                lines = result.stdout.split('\n')
                                current_ssid = None
                                current_signal = -50

                                for line in lines:
                                    line = line.strip()
                                    if line.startswith('SSID:'):
                                        ssid_match = re.search(r'SSID:\s*(.+)', line)
                                        if ssid_match:
                                            current_ssid = ssid_match.group(1).strip()
                                    elif line.startswith('signal:'):
                                        signal_match = re.search(r'signal:\s*(-?\d+)', line)
                                        if signal_match:
                                            current_signal = int(signal_match.group(1))

                                if current_ssid:
                                    networks = [{
                                        'ssid': current_ssid,
                                        'signal': current_signal,
                                        'encrypted': True
                                    }]
                                    logger.info(f"Found current network via iw fallback: {current_ssid}")
                                else:
                                    networks = []
                            else:
                                networks = []

                        except Exception as iw_e:
                            logger.warning(f"iw fallback also failed: {iw_e}")
                            networks = []

            # Remove duplicates and sort by signal strength
            seen_ssids = set()
            unique_networks = []
            for network in networks:
                if network['ssid'] not in seen_ssids and network['ssid']:
                    seen_ssids.add(network['ssid'])
                    unique_networks.append(network)

            self._wifi_networks = sorted(unique_networks, key=lambda x: x['signal'], reverse=True)
            logger.info(f"WiFi scan completed, found {len(self._wifi_networks)} networks")
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

                    # Find the WiFi device
                    device_result = subprocess.run(['nmcli', 'device', 'status'], capture_output=True, text=True, timeout=5)
                    wifi_device = None
                    if device_result.returncode == 0:
                        for line in device_result.stdout.split('\n'):
                            parts = line.split()
                            if len(parts) >= 2 and parts[1].lower() == 'wifi':
                                wifi_device = parts[0]
                                break
                    
                    if not wifi_device:
                        logger.error("No WiFi device found for connection")
                        self._wifi_connecting = False
                        self.wifiConnectingChanged.emit()
                        return

                    # First, disconnect from current network if connected
                    try:
                        disconnect_result = subprocess.run(['nmcli', 'device', 'disconnect', wifi_device],
                                                         capture_output=True, text=True, timeout=10)
                        logger.info(f"Disconnect result: {disconnect_result.returncode}")
                    except Exception as e:
                        logger.warning(f"Disconnect failed: {e}")

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

    @pyqtSlot()
    def startWifiTimer(self):
        """Start WiFi status checking timer"""
        if not self.wifi_timer.isActive():
            self.wifi_timer.start(5000)  # Check every 5 seconds when popup is open
            logger.info("WiFi status timer started")
            # Update status immediately when starting
            self.update_wifi_status()

    @pyqtSlot()
    def stopWifiTimer(self):
        """Stop WiFi status checking timer"""
        if self.wifi_timer.isActive():
            self.wifi_timer.stop()
            logger.info("WiFi status timer stopped")

    def update_wifi_status(self):
        """Update WiFi connection status with enhanced fallback methods"""
        try:
            logger.debug("Updating WiFi status...")
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
                # Enhanced Linux WiFi status checking with multiple methods
                logger.debug("Checking WiFi status on Linux...")
                connected = False
                current_ssid = ""

                # Method 1: Try nmcli first
                try:
                    result = subprocess.run(['nmcli', 'device', 'status'],
                                          capture_output=True, text=True, timeout=5)
                    logger.debug(f"nmcli device status return code: {result.returncode}")
                    
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 4:
                                device_type = parts[1].lower()
                                state = parts[2].lower()
                                if device_type == 'wifi' and state == 'connected':
                                    connected = True
                                    logger.info("WiFi connection detected via nmcli")
                                    break

                    # Get current SSID if connected via nmcli
                    if connected:
                        connected_device = None
                        for line in result.stdout.split('\n'):
                            parts = line.split()
                            if len(parts) >= 4 and parts[1].lower() == 'wifi' and parts[2].lower() == 'connected':
                                connected_device = parts[0]
                                break
                        
                        if connected_device:
                            ssid_result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'device', connected_device],
                                                       capture_output=True, text=True, timeout=5)
                            if ssid_result.returncode == 0:
                                for line in ssid_result.stdout.split('\n'):
                                    if line.startswith('yes:'):
                                        current_ssid = line.split(':', 1)[1].strip()
                                        logger.info(f"Current SSID via nmcli: {current_ssid}")
                                        break
                        else:
                            # Fallback to active connections
                            ssid_result = subprocess.run(['nmcli', '-t', '-f', 'name', 'connection', 'show', '--active'],
                                                       capture_output=True, text=True, timeout=5)
                            if ssid_result.returncode == 0:
                                connections = ssid_result.stdout.strip().split('\n')
                                if connections and connections[0]:
                                    current_ssid = connections[0]
                                    logger.info(f"Current SSID (fallback): {current_ssid}")

                except Exception as e:
                    logger.warning(f"nmcli status check failed: {e}, trying fallback methods...")
                
                # Method 2: Check IP address and interface status
                if not connected:
                    logger.debug("Checking IP address and interface status...")
                    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                    has_ip = False
                    active_interface = None

                    for interface in interfaces:
                        try:
                            # Check if interface has an IP address
                            result = subprocess.run(['ip', 'addr', 'show', interface],
                                                  capture_output=True, text=True, timeout=5)

                            if 'inet ' in result.stdout and 'UP' in result.stdout:
                                has_ip = True
                                active_interface = interface
                                logger.info(f"WiFi interface {interface} has IP address and is UP")
                                break
                        except Exception as e:
                            logger.debug(f"Error checking {interface}: {e}")
                            continue

                    if has_ip:
                        connected = True
                        
                        # Method 3: Try iw to get SSID
                        if active_interface:
                            try:
                                iw_result = subprocess.run(['iw', 'dev', active_interface, 'link'],
                                                         capture_output=True, text=True, timeout=5)
                                if iw_result.returncode == 0 and 'SSID:' in iw_result.stdout:
                                    ssid_match = re.search(r'SSID:\s*(.+)', iw_result.stdout)
                                    if ssid_match:
                                        current_ssid = ssid_match.group(1).strip()
                                        logger.info(f"Current SSID via iw: {current_ssid}")
                            except Exception as e:
                                logger.debug(f"iw link check failed: {e}")
                            
                            # Method 4: Try iwgetid as fallback
                            if not current_ssid:
                                try:
                                    ssid_result = subprocess.run(['iwgetid', '-r'],
                                                               capture_output=True, text=True, timeout=5)
                                    if ssid_result.returncode == 0:
                                        current_ssid = ssid_result.stdout.strip()
                                        logger.info(f"Current SSID via iwgetid: {current_ssid}")
                                except Exception as e:
                                    logger.debug(f"iwgetid failed: {e}")
            
            # Update properties
            wifi_changed = (self._wifi_connected != connected) or (self._current_wifi_ssid != current_ssid)
            
            self._wifi_connected = connected
            self._current_wifi_ssid = current_ssid
            
            if wifi_changed:
                logger.info(f"WiFi status updated - Connected: {connected}, SSID: {current_ssid}")
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
                                info_lines.append("Wireless Info: iwconfig not available")
                                
                            # Get NetworkManager info
                            try:
                                nm_result = subprocess.run(['nmcli', 'device', 'show', interface], 
                                                         capture_output=True, text=True, timeout=5)
                                info_lines.append("NetworkManager Info:")
                                info_lines.append(nm_result.stdout.strip())
                            except:
                                info_lines.append("NetworkManager Info: nmcli not available")
                    except:
                        continue
                
                if len(info_lines) == 1:
                    info_lines.append("No wireless interfaces found")
                
                return "\n".join(info_lines)
        except Exception as e:
            return f"Error getting WiFi interface info: {e}"

    @pyqtSlot(result=str)
    def getWifiDebugInfo(self):
        """Get comprehensive WiFi debugging information"""
        try:
            debug_info = ["=== WiFi Debug Information ==="]
            
            # System info
            debug_info.append(f"Platform: {platform.system()} {platform.release()}")
            
            # NetworkManager status
            try:
                nm_status = subprocess.run(['systemctl', 'status', 'NetworkManager'], 
                                         capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nNetworkManager Status:\n{nm_status.stdout}")
            except:
                debug_info.append("\nNetworkManager Status: Unable to check")
            
            # wpa_supplicant status
            try:
                wp_status = subprocess.run(['systemctl', 'status', 'wpa_supplicant'], 
                                         capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nwpa_supplicant Status:\n{wp_status.stdout}")
            except:
                debug_info.append("\nwpa_supplicant Status: Unable to check")
            
            # Device status
            try:
                dev_status = subprocess.run(['nmcli', 'device', 'status'], 
                                          capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nDevice Status:\n{dev_status.stdout}")
            except:
                debug_info.append("\nDevice Status: nmcli not available")
            
            # WiFi list
            try:
                wifi_list = subprocess.run(['nmcli', 'device', 'wifi', 'list'], 
                                         capture_output=True, text=True, timeout=10)
                debug_info.append(f"\nWiFi Networks:\n{wifi_list.stdout}")
            except:
                debug_info.append("\nWiFi Networks: Unable to scan")
            
            # Current connection
            try:
                conn_show = subprocess.run(['nmcli', 'connection', 'show', '--active'], 
                                         capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nActive Connections:\n{conn_show.stdout}")
            except:
                debug_info.append("\nActive Connections: Unable to check")
            
            return "\n".join(debug_info)
        except Exception as e:
            return f"Error getting WiFi debug info: {e}"

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

class ChartItem(QQuickPaintedItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart_type = "bar"
        self._view_mode = "actual"
        self._series = []
        self._months = []
        self._max_value = 0
        self._theme = "dark"
        self._show_animated = 0

    @pyqtProperty(str)
    def chartType(self):
        return self._chart_type

    @chartType.setter
    def chartType(self, value):
        if self._chart_type != value:
            self._chart_type = value
            self.update()

    @pyqtProperty(str)
    def viewMode(self):
        return self._view_mode

    @viewMode.setter
    def viewMode(self, value):
        if self._view_mode != value:
            self._view_mode = value
            self.update()

    @pyqtProperty(list)
    def series(self):
        return self._series

    @series.setter
    def series(self, value):
        self._series = value
        self.update()

    @pyqtProperty(list)
    def months(self):
        return self._months

    @months.setter
    def months(self, value):
        self._months = value
        self.update()

    @pyqtProperty(float)
    def maxValue(self):
        return self._max_value

    @maxValue.setter
    def maxValue(self, value):
        self._max_value = value
        self.update()

    @pyqtProperty(str)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        if self._theme != value:
            self._theme = value
            self.update()

    @pyqtProperty(float)
    def showAnimated(self):
        return self._show_animated

    @showAnimated.setter
    def showAnimated(self, value):
        if self._show_animated != value:
            self._show_animated = value
            self.update()

    def paint(self, painter):
        if not self._series:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 25  # Reduced margin for closer fit to container

        # Colors - Tesla-inspired dark theme
        if self._theme == "dark":
            bg_color = QColor("#2a2e2e")  # Match card background
            text_color = QColor("#ffffff")
            grid_color = QColor("#333333")  # Finer grid
            axis_color = QColor("#666666")
            colors = [QColor("#00D4FF"), QColor("#FF6B6B"), QColor("#4ECDC4")]
        else:
            bg_color = QColor("#f0f0f0")
            text_color = QColor("black")
            grid_color = QColor("#ccc")
            axis_color = QColor("#999")
            colors = [QColor("#0066CC"), QColor("#FF4444"), QColor("#00AA88")]

        painter.fillRect(0, 0, int(width), int(height), bg_color)

        # Draw finer grid lines
        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DotLine))
        for i in range(0, 11):
            y = margin + (height - 2 * margin) * i / 10
            painter.drawLine(int(margin), int(y), int(width - margin), int(y))

        # Draw vertical grid lines for x-axis
        if self._months:
            for i in range(len(self._months)):
                x = margin + (width - 2 * margin) * i / (len(self._months) - 1) if len(self._months) > 1 else margin
                painter.drawLine(int(x), int(margin), int(x), int(height - margin))

        # Draw y-axis labels
        painter.setPen(QPen(text_color))
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        for i in range(0, 11):
            value = self._max_value * (10 - i) / 10
            y = margin + (height - 2 * margin) * i / 10
            painter.drawText(int(5), int(y + 4), f"{int(value)}")

        # Draw x-axis labels
        if self._months:
            for i, month in enumerate(self._months):
                x = margin + (width - 2 * margin) * i / (len(self._months) - 1) if len(self._months) > 1 else margin
                month_letter = month[6:7] if len(month) >= 7 else month
                painter.drawText(int(x - 10), int(height - 5), month_letter)

        # Draw legend
        legend_x = width - margin - 100
        legend_y = margin + 10
        legend_spacing = 20
        for s, series_data in enumerate(self._series):
            color = colors[s % len(colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color))
            painter.drawRect(int(legend_x), int(legend_y + s * legend_spacing), 12, 12)
            painter.setPen(QPen(text_color))
            painter.drawText(int(legend_x + 16), int(legend_y + s * legend_spacing + 10), series_data['label'])

        # Draw chart
        if self._chart_type == "bar":
            self._draw_bar_chart(painter, width, height, margin, colors)
        elif self._chart_type == "line":
            self._draw_line_chart(painter, width, height, margin, colors)
        elif self._chart_type == "area":
            self._draw_area_chart(painter, width, height, margin, colors)

    def _draw_bar_chart(self, painter, width, height, margin, colors):
        if not self._months:
            return
        bar_width = (width - 2 * margin) / len(self._months) / len(self._series)
        for s, series_data in enumerate(self._series):
            color = colors[s % len(colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            for i, value in enumerate(series_data['values']):
                x = margin + i * (width - 2 * margin) / len(self._months) + s * bar_width
                bar_height = (height - 2 * margin) * value / self._max_value if self._max_value > 0 else 0
                y = height - margin - bar_height
                painter.drawRect(QRectF(x, y, bar_width, bar_height))

    def _draw_line_chart(self, painter, width, height, margin, colors):
        for s, series_data in enumerate(self._series):
            color = colors[s % len(colors)]
            painter.setPen(QPen(color, 3))
            points = []
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / self._max_value if self._max_value > 0 else height - margin
                points.append(QPoint(int(x), int(y)))
            if len(points) > 1:
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

    def _draw_area_chart(self, painter, width, height, margin, colors):
        for s, series_data in enumerate(self._series):
            color = colors[s % len(colors)]
            painter.setPen(QPen(color, 3))
            painter.setBrush(QBrush(color.lighter(150)))
            points = [QPoint(margin, height - margin)]
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / self._max_value if self._max_value > 0 else height - margin
                points.append(QPoint(int(x), int(y)))
            points.append(QPoint(width - margin, height - margin))
            painter.drawPolygon(points)

qmlRegisterType(ChartItem, 'Charts', 1, 0, 'ChartItem')

engine = QQmlApplicationEngine()
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
context.setContextProperty("spacexLogoPath", os.path.join(os.path.dirname(__file__), 'spacex_logo.png').replace('\\', '/'))
context.setContextProperty("f1LogoPath", os.path.join(os.path.dirname(__file__), 'assets', 'f1-logo.png').replace('\\', '/'))
context.setContextProperty("videoUrl", 'https://www.youtube.com/embed/videoseries?list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY&autoplay=1&mute=1&loop=1&controls=0&color=white&modestbranding=1&rel=0&enablejsapi=1&preload=none&iv_load_policy=3&disablekb=1&fs=0')

# Embedded QML for completeness (main.qml content)
qml_code = """
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Charts 1.0
import QtWebEngine

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

    Rectangle {
        id: loadingScreen
        anchors.fill: parent
        color: backend.theme === "dark" ? "#1c2526" : "#ffffff"
        visible: backend.isLoading
        z: 1

        Image {
            source: "file:///" + spacexLogoPath
            anchors.centerIn: parent
            width: 300
            height: 300
            fillMode: Image.PreserveAspectFit
        }

        // Loading animation with bouncing dots
        Row {
            anchors.top: parent.verticalCenter
            anchors.topMargin: 180
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8

            Repeater {
                model: 3
                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    color: backend.theme === "dark" ? "white" : "#333333"
                    
                    SequentialAnimation on y {
                        loops: Animation.Infinite
                        PropertyAnimation { to: -10; duration: 300; easing.type: Easing.InOutQuad }
                        PropertyAnimation { to: 0; duration: 300; easing.type: Easing.InOutQuad }
                        PauseAnimation { duration: 400 }
                    }
                    
                    // Stagger the animations
                    Component.onCompleted: {
                        animationDelay.start()
                    }
                    
                    Timer {
                        id: animationDelay
                        interval: index * 200
                        running: true
                        repeat: false
                        onTriggered: parent.SequentialAnimation.running = true
                    }
                }
            }
        }
    }

    // Cache expensive / repeated lookups
    property var nextRace: backend.get_next_race()
    Timer { interval: 60000; running: true; repeat: true; onTriggered: nextRace = backend.get_next_race() }

    Connections {
        target: backend
        function onModeChanged() {
            if (backend.mode === "f1") {
                nextRace = backend.get_next_race()
            }
        }
        function onF1Changed() {
            if (backend.mode === "f1") {
                nextRace = backend.get_next_race()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 5
        spacing: 5
        visible: !backend.isLoading

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

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "spacex"

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 5

                            ChartItem {
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                chartType: backend.chartType
                                viewMode: backend.chartViewMode
                                series: backend.launchTrendsSeries
                                months: backend.launchTrendsMonths
                                maxValue: backend.launchTrendsMaxValue
                                theme: backend.theme

                                opacity: showAnimated

                                property real showAnimated: 0

                                Component.onCompleted: showAnimated = 1

                                Behavior on showAnimated {
                                    NumberAnimation {
                                        duration: 500
                                        easing.type: Easing.InOutQuad
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

                    // F1 Driver Points Chart
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "f1"

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 5

                            Text {
                                text: "F1 Driver Performance"
                                font.pixelSize: 14
                                font.bold: true
                                color: backend.theme === "dark" ? "white" : "black"
                                Layout.alignment: Qt.AlignHCenter
                                Layout.margins: 5
                            }

                            ChartItem {
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                chartType: "area"  // Creative area chart for F1
                                viewMode: "actual"
                                series: backend.driverPointsSeries
                                months: backend.driverNames
                                maxValue: backend.driverPointsMaxValue
                                theme: backend.theme

                                opacity: showAnimated

                                property real showAnimated: 0

                                Component.onCompleted: showAnimated = 1

                                Behavior on showAnimated {
                                    NumberAnimation {
                                        duration: 500
                                        easing.type: Easing.InOutQuad
                                    }
                                }
                            }

                            // F1 Stat selector buttons
                            RowLayout {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.margins: 5
                                spacing: 10

                                // Chart type buttons
                                RowLayout {
                                    spacing: 3
                                    Repeater {
                                        model: [
                                            {"type": "area", "icon": "\uf1fe", "tooltip": "Area Chart"},
                                            {"type": "line", "icon": "\uf201", "tooltip": "Line Chart"},
                                            {"type": "bar", "icon": "\uf080", "tooltip": "Bar Chart"}
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

                                // Stat type buttons
                                RowLayout {
                                    spacing: 3
                                    Repeater {
                                        model: [
                                            {"type": "points", "icon": "\uf091", "tooltip": "Points"},
                                            {"type": "wins", "icon": "\uf005", "tooltip": "Wins"}
                                        ]
                                        Button {
                                            property var statData: modelData
                                            Layout.preferredWidth: 35
                                            Layout.preferredHeight: 25
                                            font.pixelSize: 12
                                            font.family: "Font Awesome 5 Free"
                                            text: statData.icon
                                            onClicked: {
                                                backend.f1ChartStat = statData.type
                                            }
                                            background: Rectangle {
                                                color: backend.f1ChartStat === statData.type ? 
                                                       (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0") : 
                                                       (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                                                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                                border.width: 1
                                                radius: 3
                                            }
                                            contentItem: Text {
                                                text: parent.statData.icon
                                                font: parent.font
                                                color: backend.theme === "dark" ? "white" : "black"
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            ToolTip {
                                                text: parent.statData.tooltip
                                                visible: parent.hovered
                                                delay: 500
                                            }
                                        }
                                    }
                                }
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

                    // F1 Leaderboards
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.mode === "f1"
                        spacing: 5

                        Text {
                            text: "F1 Standings"
                            font.pixelSize: 14
                            font.bold: true
                            color: backend.theme === "dark" ? "white" : "black"
                            Layout.alignment: Qt.AlignHCenter
                            Layout.margins: 5
                        }

                        // Driver Standings
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            radius: 6

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 2

                                Text {
                                    text: "Driver Standings"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: backend.theme === "dark" ? "white" : "black"
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.margins: 5
                                }

                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    model: backend.driverStandings.slice(0, 10)
                                    clip: true
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 35
                                        color: "transparent"

                                        Row {
                                            spacing: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.left: parent.left
                                            anchors.leftMargin: 10

                                            Text { 
                                                text: modelData.position; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 20
                                            }
                                            Text { 
                                                text: modelData.Driver.givenName + " " + modelData.Driver.familyName; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 120
                                            }
                                            Text { 
                                                text: modelData.points; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 40
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Constructor Standings
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            radius: 6

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 2

                                Text {
                                    text: "Constructor Standings"
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: backend.theme === "dark" ? "white" : "black"
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.margins: 5
                                }

                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    model: backend.constructorStandings.slice(0, 10)
                                    clip: true
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 35
                                        color: "transparent"

                                        Row {
                                            spacing: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.left: parent.left
                                            anchors.leftMargin: 10

                                            Text { 
                                                text: modelData.position; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 20
                                            }
                                            Text { 
                                                text: modelData.Constructor.name; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 120
                                            }
                                            Text { 
                                                text: modelData.points; 
                                                font.pixelSize: 12; 
                                                color: backend.theme === "dark" ? "white" : "black";
                                                width: 40
                                            }
                                        }
                                    }
                                }
                            }
                        }
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
                        url: backend.mode === "spacex" ? videoUrl : (nextRace ? "https://www.openstreetmap.org/export/embed.html?bbox=" + (circuitCoords[nextRace.circuit_short_name].lon - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lon + 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat + 0.01) + "&layer=mapnik&marker=" + circuitCoords[nextRace.circuit_short_name].lat + "," + circuitCoords[nextRace.circuit_short_name].lon + "&t=" + new Date().getTime() : "")
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
                    Layout.preferredWidth: 200
                    Layout.maximumWidth: 200
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
                            font.pixelSize: 14
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
                            font.pixelSize: 14
                            font.family: "D-DIN"
                        }
                    }
                }

                // Scrolling launch ticker
                Rectangle {
                    id: tickerRect
                    Layout.preferredWidth: 600
                    Layout.maximumWidth: 600
                    height: 30
                    radius: 15
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1
                    clip: true

                    Text {
                        id: tickerText
                        anchors.verticalCenter: parent.verticalCenter
                        text: backend.launchDescriptions.join(" \\ ")
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 13
                        font.family: "D-DIN"

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: tickerRect.width
                                to: -tickerText.width + 400  // Pause with text still visible
                                duration: 1600000
                            }
                            PauseAnimation { duration: 4000 }  // 4 second pause
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
            width: 500
            height: 300
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            onOpened: backend.startWifiTimer()
            onClosed: backend.stopWifiTimer()

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 5

                Text {
                    text: "WiFi Networks"
                    font.pixelSize: 16
                    font.bold: true
                    color: backend.theme === "dark" ? "white" : "black"
                    Layout.alignment: Qt.AlignHCenter
                }

                // Current connection status - compact
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                    radius: 4

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 5
                        spacing: 5

                        Text {
                            text: backend.wifiConnected ? "\uf1eb" : "\uf6ab"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.wifiConnected ? "#4CAF50" : "#F44336"
                        }

                        Text {
                            text: backend.wifiConnected ? ("Connected: " + backend.currentWifiSsid) : "Not connected"
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Button {
                            text: "Disconnect"
                            visible: backend.wifiConnected
                            Layout.preferredWidth: 60
                            Layout.preferredHeight: 20
                            onClicked: {
                                backend.disconnectWifi()
                                wifiPopup.close()
                            }
                            background: Rectangle {
                                color: "#F44336"
                                radius: 3
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                font.pixelSize: 9
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // Scan button - compact
                Button {
                    text: backend.wifiConnecting ? "Connecting..." : "Scan Networks"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 25
                    enabled: !backend.wifiConnecting
                    onClicked: backend.scanWifiNetworks()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Debug info button - compact
                Button {
                    text: "Interface Info"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 22
                    onClicked: debugDialog.open()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                        font.pixelSize: 9
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Networks list - compact single line layout
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backend.wifiNetworks
                    clip: true
                    spacing: 2

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 32
                        color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                        radius: 3

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 5
                            spacing: 8

                            // Network icon
                            Text {
                                text: modelData.encrypted ? "\uf023" : "\uf09c"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 12
                                color: modelData.encrypted ? "#FF9800" : "#4CAF50"
                                Layout.preferredWidth: 16
                            }

                            // Network info in one line
                            Text {
                                text: modelData.ssid + " (" + modelData.signal + " dBm)"
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 12
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            // Connect button - compact
                            Button {
                                text: "Connect"
                                Layout.preferredWidth: 55
                                Layout.preferredHeight: 22
                                onClicked: {
                                    selectedNetwork = modelData.ssid
                                    passwordDialog.open()
                                }

                                background: Rectangle {
                                    color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                                    radius: 3
                                }

                                contentItem: Text {
                                    text: parent.text
                                    color: backend.theme === "dark" ? "white" : "black"
                                    font.pixelSize: 9
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
            width: 320
            height: 140
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
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "Password for " + passwordDialog.selectedNetwork
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 13
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                TextField {
                    id: passwordField
                    placeholderText: "Enter password"
                    echoMode: TextField.Password
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#1a1e1e" : "#ffffff"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#cccccc"
                        border.width: 1
                        radius: 3
                    }
                }

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Cancel"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 24
                        onClicked: {
                            passwordField.text = ""
                            passwordDialog.close()
                        }

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Connect"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 24
                        onClicked: {
                            backend.connectToWifi(passwordDialog.selectedNetwork, passwordField.text)
                            passwordField.text = ""
                            passwordDialog.close()
                            wifiPopup.close()
                        }

                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 3
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
        }

        // Debug info dialog
        Popup {
            id: debugDialog
            width: 450
            height: 250
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
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "WiFi Interface Information"
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 14
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
                            radius: 3
                        }
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 9
                        font.family: "Courier New"
                    }
                }

                Button {
                    text: "Refresh"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 24
                    onClicked: debugText.text = backend.getWifiInterfaceInfo()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
                        radius: 3
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
"""

# Load QML from string (for complete single file)
engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
if not engine.rootObjects():
    logger.error("QML root object creation failed (see earlier QML errors above).")
    print("QML load failed. Check console for Qt errors.")
    sys.exit(-1)
sys.exit(app.exec())