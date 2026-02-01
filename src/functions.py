"""
Shared helper functions extracted from app.py.

This module intentionally contains only UI-agnostic utilities so it can be
imported from both production code and tests without pulling in Qt.
"""

from __future__ import annotations

import json
import logging
import math
import platform
IS_WINDOWS = platform.system() == 'Windows'
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytz
import requests
import concurrent.futures
from dateutil.parser import parse
from cryptography.fernet import Fernet
import http.server
import socketserver
import threading

logger = logging.getLogger(__name__)

class BootProfiler:
    """Helper to track performance of boot operations."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BootProfiler, cls).__new__(cls)
            cls._instance.events = []
            cls._instance.start_time = time.time()
        return cls._instance
    
    def mark(self, event_name):
        """Mark a point in time with a name."""
        elapsed = time.time() - self.start_time
        thread_name = threading.current_thread().name
        self.events.append((event_name, elapsed, thread_name))
        logger.info(f"PROFILER: [{thread_name}] {event_name} at {elapsed:.3f}s")
        
    def get_summary(self):
        """Get a formatted summary of all tracked events."""
        summary = ["--- Boot Performance Summary ---"]
        prev_time = 0
        for name, timestamp, thread_name in self.events:
            duration = timestamp - prev_time
            summary.append(f"[{thread_name:^12}] {name:.<40} {timestamp:>6.3f}s (step: {duration:>6.3f}s)")
            prev_time = timestamp
        summary.append(f"{'Total Boot Time':.<55} {prev_time:>6.3f}s")
        return "\n".join(summary)

    def log_summary(self):
        """Log the summary to the application log."""
        logger.info("\n" + self.get_summary())

profiler = BootProfiler()

__all__ = [
    # status helpers
    "BootProfiler",
    "set_loader_status_callback",
    "emit_loader_status",
    # cache io
    "load_cache_from_file",
    "save_cache_to_file",
    # launch cache helpers
    "load_launch_cache",
    "save_launch_cache",
    # network/system helpers
    "check_wifi_status",
    "fetch_launches",
    "fetch_weather",
    # parsing/math helpers
    # exported constants
    "CACHE_REFRESH_INTERVAL_PREVIOUS",
    "CACHE_REFRESH_INTERVAL_UPCOMING",
    "CACHE_REFRESH_INTERVAL_F1",
    "CACHE_REFRESH_INTERVAL_F1_SCHEDULE",
    "CACHE_REFRESH_INTERVAL_F1_STANDINGS",
    "TRAJECTORY_CACHE_FILE",
    "CACHE_DIR_F1",
    "CACHE_FILE_F1_SCHEDULE",
    "CACHE_FILE_F1_DRIVERS",
    "CACHE_FILE_F1_CONSTRUCTORS",
    "RUNTIME_CACHE_FILE_LAUNCHES",
    "RUNTIME_CACHE_FILE_NARRATIVES",
    "WIFI_KEY_FILE",
    "REMEMBERED_NETWORKS_FILE",
    "LAST_CONNECTED_NETWORK_FILE",
    "F1_TEAM_COLORS",
    "location_settings",
    "radar_locations",
    "circuit_coords",
    "get_encryption_key",
    "encrypt_password",
    "decrypt_password",
    "get_wifi_interface",
    "load_remembered_networks",
    "save_remembered_networks",
    "load_last_connected_network",
    "save_last_connected_network",
    "start_http_server",
    "perform_wifi_scan",
    "manage_nm_autoconnect",
    "test_network_connectivity",
    "get_git_version_info",
    "check_github_for_updates",
    "connect_to_wifi_worker",
    "get_launch_trends_series",
    "get_launch_trajectory_data",
    "group_event_data",
    "LAUNCH_DESCRIPTIONS",
    "check_wifi_interface",
    "get_wifi_interface_info",
    "get_wifi_debug_info",
    "start_update_script",
    "generate_month_labels_for_days",
    "connect_to_wifi_nmcli",
    "get_max_value_from_series",
    "get_next_launch_info",
    "get_upcoming_launches_list",
    "initialize_all_weather",
    "get_best_wifi_reconnection_candidate",
    "calculate_chart_interval",
    "filter_and_sort_wifi_networks",
    "get_nmcli_profiles",
    "fetch_weather_for_all_locations",
    "perform_full_dashboard_data_load",
    "setup_dashboard_environment",
    "setup_dashboard_logging",
    "format_qt_message",
    "get_launch_tray_visibility_state",
    "get_countdown_string",
    "get_update_progress_summary",
    "perform_bootstrap_diagnostics",
    "disconnect_from_wifi",
    "bring_up_nm_connection",
    "sync_remembered_networks",
    "remove_nm_connection",
    "fetch_narratives",
    "load_theme_settings",
    "save_theme_settings",
    "get_rpi_config_resolution",
    "check_touch_calibration_exists",
    "remove_touch_calibration",
]


# --- Lightweight loader status hook so non-Qt functions can report splash updates ---
_loader_status_cb = None  # set by DataLoader during run()


def set_loader_status_callback(cb):
    """Set a callable that receives status text for splash/loader updates.
    The DataLoader installs a callback; helpers in this module can emit with emit_loader_status().
    """
    global _loader_status_cb
    _loader_status_cb = cb


def emit_loader_status(message: str):
    """Emit a loader status message if a callback has been registered."""
    try:
        cb = _loader_status_cb
        if cb:
            cb(str(message))
    except Exception as _e:
        # Avoid crashing during startup due to UI disposal races
        logging.getLogger(__name__).debug(f"emit_loader_status skipped: {_e}")


# --- Cache paths and constants (UI-agnostic) ---
LAUNCH_API_BASE_URL = "https://launch-narrative-api-dafccc521fb8.herokuapp.com"
CACHE_REFRESH_INTERVAL_PREVIOUS = 600  # 10 minutes (increased to avoid API limits)
CACHE_REFRESH_INTERVAL_UPCOMING = 600  # 10 minutes (increased to avoid API limits)
CACHE_REFRESH_INTERVAL_F1 = 3600       # 1 hour for F1 data
CACHE_REFRESH_INTERVAL_WEATHER = 300     # 5 minutes (matches API)
CACHE_REFRESH_INTERVAL_NARRATIVES = 900 # 15 minutes
TRAJECTORY_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'cache', 'trajectory_cache.json')
SEED_CACHE_FILE_PREVIOUS = os.path.join(os.path.dirname(__file__), '..', 'cache', 'previous_launches_cache.json')
SEED_CACHE_FILE_UPCOMING = os.path.join(os.path.dirname(__file__), '..', 'cache', 'upcoming_launches_cache.json')

# Cache for F1 data - persistent location outside git repo
CACHE_DIR_F1 = os.path.expanduser('~/.cache/spacex-dashboard')  # Persistent cache directory
os.makedirs(CACHE_DIR_F1, exist_ok=True)
CACHE_FILE_F1_SCHEDULE = os.path.join(CACHE_DIR_F1, 'f1_schedule_cache.json')
CACHE_FILE_F1_DRIVERS = os.path.join(CACHE_DIR_F1, 'f1_drivers_cache.json')
CACHE_FILE_F1_CONSTRUCTORS = os.path.join(CACHE_DIR_F1, 'f1_constructors_cache.json')
CACHE_FILE_F1_OPENF1_SESSION = os.path.join(CACHE_DIR_F1, 'f1_openf1_session.json')
CACHE_FILE_F1_WEATHER = os.path.join(CACHE_DIR_F1, 'f1_weather.json')
CACHE_FILE_F1_POSITIONS = os.path.join(CACHE_DIR_F1, 'f1_positions.json')
CACHE_FILE_F1_LAPS = os.path.join(CACHE_DIR_F1, 'f1_laps.json')
CACHE_FILE_F1_STINTS = os.path.join(CACHE_DIR_F1, 'f1_stints.json')
CACHE_FILE_F1_PITS = os.path.join(CACHE_DIR_F1, 'f1_pits.json')
CACHE_FILE_F1_TELEMETRY = os.path.join(CACHE_DIR_F1, 'f1_telemetry.json')
CACHE_FILE_F1_LOCATION = os.path.join(CACHE_DIR_F1, 'f1_location.json')
CACHE_FILE_F1_TRACK_LAYOUT = os.path.join(CACHE_DIR_F1, 'f1_track_layout.json')

# Runtime (user) cache paths for SpaceX launches. Keep the git-seeded repo cache intact
# and write incremental updates to the persistent user cache.
RUNTIME_CACHE_FILE_LAUNCHES = os.path.join(CACHE_DIR_F1, 'launches_cache.json')
RUNTIME_CACHE_FILE_CALENDAR = os.path.join(CACHE_DIR_F1, 'calendar_cache.json')
RUNTIME_CACHE_FILE_CHART_TRENDS = os.path.join(CACHE_DIR_F1, 'chart_trends_cache.json')
RUNTIME_CACHE_FILE_PARSED_DATES = os.path.join(CACHE_DIR_F1, 'parsed_dates_cache.json')
RUNTIME_CACHE_FILE_NARRATIVES = os.path.join(CACHE_DIR_F1, 'narratives_cache.json')
CACHE_FILE_WEATHER = os.path.join(CACHE_DIR_F1, 'weather_cache.json')

# Different refresh intervals for different F1 data types
CACHE_REFRESH_INTERVAL_F1_SCHEDULE = 86400  # 24 hours for race schedule (rarely changes)
CACHE_REFRESH_INTERVAL_F1_STANDINGS = 3600  # 1 hour for standings (updates frequently)
CACHE_REFRESH_INTERVAL_F1_OPENF1 = 300      # 5 minutes for live session data
CACHE_REFRESH_INTERVAL_NARRATIVES = 3600    # 1 hour for narratives

# WiFi and Encryption paths
# WiFi and Encryption paths - Updated to use persistent cache directory
WIFI_KEY_FILE = os.path.join(CACHE_DIR_F1, 'wifi_key.bin')
REMEMBERED_NETWORKS_FILE = os.path.join(CACHE_DIR_F1, 'remembered_networks.json')
LAST_CONNECTED_NETWORK_FILE = os.path.join(CACHE_DIR_F1, 'last_connected_network.json')
THEME_SETTINGS_FILE = os.path.join(CACHE_DIR_F1, 'theme_settings.json')
BRANCH_SETTINGS_FILE = os.path.join(CACHE_DIR_F1, 'branch_settings.json')
TOUCH_CALIBRATION_FILE = "/etc/X11/xorg.conf.d/99-calibration.conf"

def check_touch_calibration_exists():
    """Check if a touchscreen calibration file exists."""
    if platform.system() == 'Windows':
        return False
    return os.path.exists(TOUCH_CALIBRATION_FILE)

def remove_touch_calibration():
    """Remove the touchscreen calibration file and reload udev rules."""
    if platform.system() == 'Windows':
        return True, "Simulation: Calibration removed"
    
    try:
        if os.path.exists(TOUCH_CALIBRATION_FILE):
            subprocess.run(['sudo', 'rm', TOUCH_CALIBRATION_FILE], check=True)
            subprocess.run(['sudo', 'udevadm', 'control', '--reload-rules'], check=True)
            subprocess.run(['sudo', 'udevadm', 'trigger'], check=True)
            return True, "Calibration removed successfully"
        return False, "No calibration file found"
    except Exception as e:
        return False, f"Failed to remove calibration: {e}"

def load_theme_settings():
    """Load theme settings from file."""
    try:
        data = load_cache_from_file(THEME_SETTINGS_FILE)
        if data and 'theme' in data['data']:
            return data['data']['theme']
    except Exception as e:
        logger.warning(f"Failed to load theme settings: {e}")
    return 'dark'  # Default fallback

def save_theme_settings(new_theme):
    """Save theme settings to file."""
    try:
        data = {'theme': new_theme}
        save_cache_to_file(THEME_SETTINGS_FILE, data, datetime.now(pytz.UTC))
    except Exception as e:
        logger.error(f"Failed to save theme settings: {e}")

def load_branch_setting():
    """Load the target update branch from file."""
    try:
        data = load_cache_from_file(BRANCH_SETTINGS_FILE)
        if data and 'branch' in data['data']:
            return data['data']['branch']
    except Exception as e:
        logger.warning(f"Failed to load branch setting: {e}")
    return 'master'  # Default fallback

def save_branch_setting(branch):
    """Save the target update branch to file."""
    try:
        data = {'branch': branch}
        save_cache_to_file(BRANCH_SETTINGS_FILE, data, datetime.now(pytz.UTC))
    except Exception as e:
        logger.error(f"Failed to save branch setting: {e}")

# F1 Team colors for visualization
F1_TEAM_COLORS = {
    'red_bull': '#3671C6',      # Red Bull blue
    'mercedes': '#6CD3BF',     # Mercedes teal
    'ferrari': '#E8002D',      # Ferrari red
    'mclaren': '#FF8000',      # McLaren orange
    'alpine': '#0093CC',       # Alpine blue
    'aston_martin': '#2D826D', # Aston Martin green
    'williams': '#37BEDD',     # Williams blue
    'rb': '#6692FF',           # RB blue
    'sauber': '#52E252',       # Sauber green
    'haas': '#B6BABD'          # Haas grey
}

# Location settings
location_settings = {
    'Starbase': {'lat': 25.9975, 'lon': -97.1566, 'timezone': 'America/Chicago'},
    'Vandy': {'lat': 34.632, 'lon': -120.611, 'timezone': 'America/Los_Angeles'},
    'Cape': {'lat': 28.392, 'lon': -80.605, 'timezone': 'America/New_York'},
    'Hawthorne': {'lat': 33.916, 'lon': -118.352, 'timezone': 'America/Los_Angeles'}
}

# Radar URLs
radar_locations = {
    'Starbase': 'https://embed.windy.com/embed2.html?lat=25.9975&lon=-97.1566&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=25.9975&detailLon=-97.1566&metricWind=mph&metricTemp=%C2%B0F',
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
    'Abu Dhabi': {'lat': 24.4672, 'lon': 54.6031},
    # F1 circuit names
    'Albert Park Circuit': {'lat': -37.8497, 'lon': 144.968},
    'Shangai International Circuit': {'lat': 31.3389, 'lon': 121.2200},
    'Suzuka International Circuit': {'lat': 34.8431, 'lon': 136.5411},
    'Bahrain International Circuit': {'lat': 26.0325, 'lon': 50.5106},
    'Jeddah Corniche Circuit': {'lat': 21.6319, 'lon': 39.1044},
    'Miami International Autodrome': {'lat': 25.9581, 'lon': -80.2389},
    'Imola Autodromo Internazionale Enzo e Dino Ferrari': {'lat': 44.3439, 'lon': 11.7167},
    'Circuit de Monaco': {'lat': 43.7347, 'lon': 7.4206},
    'Circuit de Barcelona-Catalunya': {'lat': 41.5700, 'lon': 2.2611},
    'Circuit Gilles Villeneuve': {'lat': 45.5000, 'lon': -73.5228},
    'Red Bull Ring': {'lat': 47.2197, 'lon': 14.7647},
    'Silverstone Circuit': {'lat': 52.0786, 'lon': -1.0169},
    'Circuit de Spa-Francorchamps': {'lat': 50.4372, 'lon': 5.9714},
    'Hungaroring': {'lat': 47.5839, 'lon': 19.2486},
    'Circuit Zandvoort': {'lat': 52.3888, 'lon': 4.5409},
    'Autodromo Nazionale Monza': {'lat': 45.6156, 'lon': 9.2811},
    'Baku City Circuit': {'lat': 40.3725, 'lon': 49.8533},
    'Marina Bay Street Circuit': {'lat': 1.2914, 'lon': 103.8642},
    'Circuit of The Americas': {'lat': 30.1328, 'lon': -97.6411},
    'Autódromo Hermanos Rodríguez': {'lat': 19.4042, 'lon': -99.0907},
    'Autodromo José Carlos Pace | Interlagos': {'lat': -23.7036, 'lon': -46.6997},
    'Las Vegas Strip Circuit': {'lat': 36.1147, 'lon': -115.1728},
    'Lusail International Circuit': {'lat': 25.4900, 'lon': 51.4542},
    'Yas Marina Circuit': {'lat': 24.4672, 'lon': 54.6031}
}

# In-memory cache for F1 data
f1_cache = None


def load_cache_from_file(cache_file):
    """Load structured cache from a JSON file.

    Returns a dict with keys {"data", "timestamp"} where timestamp is
    converted to timezone-aware UTC datetime, or None on failure.
    """
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                
                # Check for mandatory 'data' key
                if 'data' not in cache_data:
                    logger.warning(f"Cache file {cache_file} missing 'data' key")
                    return None
                
                # Handle timestamp (standard dashboard cache format)
                if 'timestamp' in cache_data:
                    try:
                        cache_data['timestamp'] = datetime.fromisoformat(cache_data['timestamp'])
                        if cache_data['timestamp'].tzinfo is None:
                            cache_data['timestamp'] = cache_data['timestamp'].replace(tzinfo=pytz.UTC)
                    except (ValueError, TypeError):
                        cache_data['timestamp'] = datetime.fromtimestamp(os.path.getmtime(cache_file), pytz.UTC)
                else:
                    # Fallback for seed files (use file modification time)
                    cache_data['timestamp'] = datetime.fromtimestamp(os.path.getmtime(cache_file), pytz.UTC)
                
                return cache_data
    except (OSError, PermissionError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load cache from {cache_file}: {e}")
    return None


def save_cache_to_file(cache_file, data, timestamp):
    """Persist structured cache to a JSON file with ISO timestamp."""
    try:
        cache_data = {'data': data, 'timestamp': timestamp.isoformat()}
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except (OSError, PermissionError) as e:
        logger.warning(f"Failed to save cache to {cache_file}: {e}")


# Helpers for launch caches that use a single combined runtime cache
def load_launch_cache(kind: str):
    """Load a launch cache for kind in {'previous','upcoming'} from the combined cache.
    Falls back to kind-specific seed files in the project root if combined cache is missing.
    Returns a dict: {'data': list, 'timestamp': datetime} or None.
    """
    profiler.mark(f"load_launch_cache Start ({kind})")
    try:
        if kind not in ('previous', 'upcoming'):
            raise ValueError("kind must be 'previous' or 'upcoming'")
        
        # Try combined runtime cache first
        data = load_cache_from_file(RUNTIME_CACHE_FILE_LAUNCHES)
        if data and isinstance(data.get('data'), dict):
            kind_data = data['data'].get(kind)
            if isinstance(kind_data, list) and len(kind_data) > 0:
                profiler.mark(f"load_launch_cache End ({kind}: Success from runtime)")
                return {'data': kind_data, 'timestamp': data['timestamp']}
        
        # Fallback to seed files
        logger.info(f"Runtime {kind} cache unavailable or invalid; falling back to seed...")
        seed_path = SEED_CACHE_FILE_PREVIOUS if kind == 'previous' else SEED_CACHE_FILE_UPCOMING
        seed_data = load_cache_from_file(seed_path)
        if seed_data and isinstance(seed_data.get('data'), list):
            profiler.mark(f"load_launch_cache End ({kind}: Success from seed)")
            return {'data': seed_data['data'], 'timestamp': seed_data['timestamp']}
        
        profiler.mark(f"load_launch_cache End ({kind}: Empty/Fail)")
        return None
    except Exception as e:
        logger.warning(f"Failed to load {kind} launch cache: {e}")
        profiler.mark(f"load_launch_cache End ({kind}: Exception)")
        return None


def save_launch_cache(kind: str, data_list: list, timestamp=None):
    """Save kind-specific launches into the combined runtime cache."""
    profiler.mark(f"save_launch_cache Start ({kind})")
    try:
        if kind not in ('previous', 'upcoming'):
            raise ValueError("kind must be 'previous' or 'upcoming'")
        
        # Load existing combined cache or create new
        combined = load_cache_from_file(RUNTIME_CACHE_FILE_LAUNCHES)
        if combined and isinstance(combined.get('data'), dict):
            launch_data = combined['data']
            combined_ts = combined['timestamp']
        else:
            launch_data = {'upcoming': [], 'previous': []}
            combined_ts = timestamp or datetime.now(pytz.UTC)
            
        launch_data[kind] = data_list
        ts = timestamp or combined_ts
        save_cache_to_file(RUNTIME_CACHE_FILE_LAUNCHES, launch_data, ts)
        profiler.mark(f"save_launch_cache End ({kind})")
    except Exception as e:
        logger.warning(f"Failed to save {kind} launch cache: {e}")
        profiler.mark(f"save_launch_cache End ({kind}: Exception)")



def _ang_dist_deg(a, b):
    """Calculate the angular distance between two points in degrees."""
    lat1 = math.radians(a['lat']); lon1 = math.radians(a['lon'])
    lat2 = math.radians(b['lat']); lon2 = math.radians(b['lon'])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return math.degrees(2 * math.atan2(math.sqrt(h), math.sqrt(max(1e-12, 1-h))))

def _bearing_deg(lat1, lon1, lat2, lon2):
    """Calculate the initial bearing from point 1 to point 2 in degrees."""
    phi1 = math.radians(lat1); phi2 = math.radians(lat2); dlon = math.radians(lon2-lon1)
    return (math.degrees(math.atan2(math.sin(dlon)*math.cos(phi2), math.cos(phi1)*math.sin(phi2)-math.sin(phi1)*math.cos(phi2)*math.cos(dlon))) + 360) % 360

def choose_orbit_alt_km(orbit_label):
    """Estimate a physically sensible visual altitude for a given orbit type."""
    o = (orbit_label or '').lower()
    if 'suborbital' in o: return 150            # SpaceX boosters go to ~150km
    if 'sso' in o or 'sun-synchronous' in o: return 550
    if 'polar' in o: return 600
    if 'leo' in o or 'low earth orbit' in o: return 400
    if 'gto' in o or 'geostationary transfer' in o: return 20000
    if 'geo' in o or 'geostationary' in o: return 35786
    if 'meo' in o or 'gps' in o: return 20200
    if 'heeo' in o or 'molniya' in o: return 40000
    return 800

def compute_orbit_radius(orbit_label):
    """Compute the visual radius (1.0 = surface) for a given orbit type."""
    EARTH_RADIUS_KM = 6371.0
    alt_km = choose_orbit_alt_km(orbit_label)
    # Visual compression: add relative altitude, capped to +8%
    r = 1.0 + min(alt_km / EARTH_RADIUS_KM, 0.08)
    # Keep above clouds layer (1.01) with a small margin
    if r < 1.012: r = 1.012
    # Hard safety clamp to avoid drawing too far from globe
    if r > 1.08: r = 1.08
    return r


# --- System/network helpers moved from app.py ---
# Global Wi-Fi status cache to avoid frequent expensive subprocess calls
_WIFI_STATUS_CACHE = {'connected': False, 'ssid': '', 'timestamp': 0}
WIFI_STATUS_TTL = 30  # seconds

def check_wifi_status():
    """Check WiFi connection status and return (connected, ssid) tuple"""
    global _WIFI_STATUS_CACHE
    
    # Return cached result if fresh
    now = time.time()
    if now - _WIFI_STATUS_CACHE['timestamp'] < WIFI_STATUS_TTL:
        logger.debug(f"Returning cached WiFi status: {_WIFI_STATUS_CACHE['connected']} ({_WIFI_STATUS_CACHE['ssid']})")
        return _WIFI_STATUS_CACHE['connected'], _WIFI_STATUS_CACHE['ssid']

    profiler.mark("check_wifi_status Start")
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
            
            _WIFI_STATUS_CACHE = {'connected': connected, 'ssid': current_ssid, 'timestamp': now}
            profiler.mark(f"check_wifi_status End (Windows: {connected})")
            return connected, current_ssid
        else:
            # Enhanced Linux WiFi status checking
            connected = False
            current_ssid = ""

            # Method 1: Try nmcli (active connection) - usually very fast
            try:
                nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=3)
                if nmcli_check.returncode == 0:
                    result = subprocess.run(['nmcli', '-t', '-f', 'TYPE,SSID,DEVICE', 'connection', 'show', '--active'],
                                          capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            if not line: continue
                            parts = line.split(':')
                            if len(parts) >= 3 and parts[0].lower() == '802-11-wireless':
                                connected = True
                                current_ssid = parts[1]
                                break
            except Exception: pass

            # Method 2: iwgetid fallback - very fast
            if not connected:
                try:
                    iw_res = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=3)
                    if iw_res.returncode == 0:
                        current_ssid = iw_res.stdout.strip()
                        if current_ssid:
                            connected = True
                except: pass

            # Method 3: nmcli device status fallback
            if not connected:
                try:
                    result = subprocess.run(['nmcli', 'device', 'status'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            parts = line.split()
                            if len(parts) >= 4 and parts[1].lower() == 'wifi' and parts[2].lower() == 'connected':
                                connected = True
                                dev = parts[0]
                                ssid_res = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'device', 'wifi', 'list', 'ifname', dev],
                                                        capture_output=True, text=True, timeout=5)
                                if ssid_res.returncode == 0:
                                    for sline in ssid_res.stdout.split('\n'):
                                        if sline.startswith('yes:'):
                                            current_ssid = sline.split(':', 1)[1].strip()
                                            break
                                break
                except Exception: pass

            _WIFI_STATUS_CACHE = {'connected': connected, 'ssid': current_ssid, 'timestamp': now}
            profiler.mark(f"check_wifi_status End (Linux: {connected})")
            return connected, current_ssid
    except Exception as e:
        logger.error(f"Error in check_wifi_status: {e}")
        profiler.mark("check_wifi_status End (Error)")
        return False, ""

def fetch_launch_details(launch_id):
    """Fetch detailed information for a single launch to get full data (v2.3.0) via proxy."""
    if not launch_id:
        return None
    url = f"{LAUNCH_API_BASE_URL}/launch_details/{launch_id}"
    logger.info(f"Fetching details for launch {launch_id} via proxy")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch launch details for {launch_id}: {e}")
        return None

def parse_launch_data(launch: dict, is_detailed: bool = False) -> dict:
    """Helper to parse raw API launch data into the dashboard's internal format."""
    # If already parsed (indicated by presence of 'mission' and 'video_url' and absence of 'vidURLs')
    if 'mission' in launch and 'video_url' in launch and 'vidURLs' not in launch:
        return launch.copy()

    launcher_stage = launch.get('rocket', {}).get('launcher_stage', [])
    landing_type = None
    landing_location = None
    if isinstance(launcher_stage, list) and len(launcher_stage) > 0:
        landing = launcher_stage[0].get('landing')
        if landing:
            landing_type = landing.get('type', {}).get('name')
            # In v2.3.0 mode=detailed, the key is often 'landing_location' instead of 'location'
            landing_location = landing.get('landing_location', {}).get('name')
            if not landing_location:
                landing_location = landing.get('location', {}).get('name')
    
    return {
        'id': launch.get('id'),
        'mission': launch.get('name', 'Unknown'),
        'date': launch.get('net').split('T')[0] if launch.get('net') else 'TBD',
        'time': launch.get('net').split('T')[1].split('Z')[0] if launch.get('net') and 'T' in launch.get('net') else 'TBD',
        'net': launch.get('net'),
        'status': launch.get('status', {}).get('name', 'Unknown'),
        'rocket': launch.get('rocket', {}).get('configuration', {}).get('name', 'Unknown'),
        'orbit': launch.get('mission', {}).get('orbit', {}).get('name', 'Unknown') if launch.get('mission') else 'Unknown',
        'pad': launch.get('pad', {}).get('name', 'Unknown'),
        'video_url': next((v.get('url', '') for v in launch.get('vidURLs', []) if v.get('url')), ''),
        'x_video_url': next((v.get('url', '') for v in launch.get('vidURLs', []) if v.get('url') and ('x.com' in v['url'].lower() or 'twitter.com' in v['url'].lower())), ''),
        'landing_type': landing_type,
        'landing_location': landing_location,
        'is_detailed': is_detailed
    }

# --- Data fetchers moved from app.py ---
def fetch_launches():
    """Fetch SpaceX launch data (upcoming and previous) from the new API."""
    logger.info("Fetching SpaceX launch data from new API")
    
    # Try loading from combined cache first
    try:
        cache = load_cache_from_file(RUNTIME_CACHE_FILE_LAUNCHES)
        current_time = datetime.now(pytz.UTC)
        if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_UPCOMING:
            logger.info("Using fresh combined launch cache")
            return cache['data']
    except Exception as e:
        logger.warning(f"Failed to load combined launch cache: {e}")

    # Check network connectivity
    network_available = test_network_connectivity()
    if not network_available:
        if cache and cache.get('data'):
            logger.info("Using stale combined launch cache (offline)")
            return cache['data']
        # Deep fallback to kind-specific caches
        prev = load_launch_cache('previous')
        up = load_launch_cache('upcoming')
        return {
            'previous': prev['data'] if prev else [],
            'upcoming': up['data'] if up else []
        }

    try:
        emit_loader_status("Fetching SpaceX launch data…")
        url = f"{LAUNCH_API_BASE_URL}/launches"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        api_upcoming = [parse_launch_data(l) for l in data.get('upcoming', [])]
        api_previous = [parse_launch_data(l) for l in data.get('previous', [])]
        
        # Merge with existing history to avoid losing data due to API window limits
        # Load current state (falls back to seed files if runtime is missing)
        prev_cache = load_launch_cache('previous')
        existing_previous = prev_cache['data'] if prev_cache else []
        
        # Use a map for deduplication, preferring API data for latest status
        merged_prev_map = {l.get('id'): l for l in existing_previous if l.get('id')}
        for l in api_previous:
            launch_id = l.get('id')
            if launch_id:
                merged_prev_map[launch_id] = l
        
        # Sort merged previous launches by date descending
        profiler.mark("fetch_launches: Sorting and Deduplicating Start")
        def _parse_net(l):
            dt = _get_parsed_dt(l.get('net', ''))
            return dt if dt else datetime.min.replace(tzinfo=pytz.UTC)

        merged_previous = sorted(merged_prev_map.values(), key=_parse_net, reverse=True)
        
        # For upcoming, we trust the API's current schedule
        # but remove any that have moved into the previous list
        # SPECIAL CASE: if a launch is in 'previous' but is NOT finished (e.g. 'In Flight'),
        # we treat it as an active/upcoming launch so it stays in the banner and next launch slot.
        prev_ids = {l.get('id') for l in merged_previous if l.get('id')}
        
        # Find unfinished launches in the previous list
        active_launches = [l for l in merged_previous if not is_launch_finished(l.get('status'))]
        active_ids = {l.get('id') for l in active_launches}
        
        # Remove truly finished previous launches from the upcoming list
        merged_upcoming = [l for l in api_upcoming if l.get('id') not in prev_ids or l.get('id') in active_ids]
        
        # Add any active launches from 'previous' back to 'upcoming' if they are missing
        upcoming_ids = {l.get('id') for l in merged_upcoming if l.get('id')}
        for al in active_launches:
            if al.get('id') not in upcoming_ids:
                merged_upcoming.append(al)
                
        # To avoid showing them in "Past Launches" group while they are "In Flight",
        # we remove active launches from the merged_previous list
        merged_previous = [l for l in merged_previous if l.get('id') not in active_ids]
        
        # Sort both lists by date (upcoming ascending, previous descending)
        merged_upcoming = sorted(merged_upcoming, key=_parse_net)
        merged_previous = sorted(merged_previous, key=_parse_net, reverse=True)
        
        launch_data = {
            'upcoming': merged_upcoming,
            'previous': merged_previous
        }
        profiler.mark("fetch_launches: Sorting and Deduplicating End")
        
        save_cache_to_file(RUNTIME_CACHE_FILE_LAUNCHES, launch_data, datetime.now(pytz.UTC))
        logger.info(f"Fetched {len(api_upcoming)} upcoming and {len(api_previous)} previous launches from API")
        logger.info(f"Combined with history: total {len(launch_data['upcoming'])} upcoming and {len(launch_data['previous'])} previous")
        return launch_data
    except Exception as e:
        logger.error(f"Failed to fetch launches from new API: {e}")
        if cache and cache.get('data'):
            return cache['data']
        return {'previous': [], 'upcoming': []}


def fetch_narratives(launch_data=None):
    """Fetch witty launch narratives from the new API and optionally enrich with launch metadata."""
    profiler.mark("fetch_narratives Start")
    logger.info("Fetching narratives from new API")
    
    def parse_narratives(raw_list):
        """Parse list of strings into list of dicts {date, text}."""
        parsed = []
        for item in raw_list:
            if isinstance(item, dict):
                parsed.append(item)
                continue
            if not isinstance(item, str):
                continue
            
            match = re.match(r'^(\d{1,2}/\d{1,2}\s+\d{4}):\s*(.*)', item)
            if match:
                parsed.append({'date': match.group(1), 'text': match.group(2), 'full': item})
            else:
                parsed.append({'date': '', 'text': item, 'full': item})
        return parsed

    def enrich_narratives(narratives_list, launches):
        if not launches:
            return narratives_list
        
        # Combine upcoming and previous
        all_launches = launches.get('upcoming', []) + launches.get('previous', [])
        
        for narr in narratives_list:
            # Try to match narrative to a launch
            # Narrative dates are usually M/D HHMM, e.g. "7/1 2104"
            # Launch 'net' is "2024-07-01T21:04:00Z"
            
            narr_date_str = narr.get('date', '')
            if not narr_date_str:
                continue
                
            try:
                # Narratives usually have M/D HHMM. Net has YYYY-MM-DDTHH:MM:SSZ
                # We'll try to match by month, day, and hour/minute if possible.
                # Example: "7/1 2104" -> month 7, day 1, hour 21, minute 04
                parts = narr_date_str.split(' ')
                md = parts[0].split('/')
                month = int(md[0])
                day = int(md[1])
                
                hour = -1
                minute = -1
                if len(parts) > 1 and len(parts[1]) == 4:
                    hour = int(parts[1][:2])
                    minute = int(parts[1][2:])
                
                best_match = None
                for l in all_launches:
                    l_net = l.get('net')
                    if not l_net: continue
                    
                    l_dt = _get_parsed_dt(l_net)
                    if not l_dt: continue
                    
                    # Match month and day
                    if l_dt.month == month and l_dt.day == day:
                        # If we have time, check it too (allowing small delta due to TBD changes)
                        if hour != -1:
                            if l_dt.hour == hour and abs(l_dt.minute - minute) <= 5:
                                best_match = l
                                break
                        else:
                            best_match = l
                            # Don't break, keep looking for better time match if possible? 
                            # Usually one launch per day per pad, but let's be safe.
                
                if best_match:
                    narr['status'] = best_match.get('status')
                    narr['landing_location'] = best_match.get('landing_location')
                    narr['landing_type'] = best_match.get('landing_type')
                    narr['orbit'] = best_match.get('orbit')
                    narr['rocket'] = best_match.get('rocket')
                    narr['pad'] = best_match.get('pad')
                    narr['mission'] = best_match.get('mission')
                    
                    # Add day of week (abbreviated, e.g. "Wed")
                    try:
                        l_dt = _get_parsed_dt(best_match.get('net'))
                        if l_dt:
                            narr['day_of_week'] = l_dt.strftime('%a')
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Failed to match narrative to launch: {e}")
                
        return narratives_list

    # Try loading from cache first
    cache = None
    try:
        cache = load_cache_from_file(RUNTIME_CACHE_FILE_NARRATIVES)
        current_time = datetime.now(pytz.UTC)
        if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_NARRATIVES:
            logger.info("Using cached narratives")
            # If we don't have launch_data, we can't re-enrich, but we might have cached enriched data
            return enrich_narratives(cache['data'], launch_data)
    except Exception as e:
        logger.warning(f"Failed to load narratives cache: {e}")

    # Check network
    if not test_network_connectivity():
        if cache and cache.get('data'):
            return enrich_narratives(cache['data'], launch_data)
        return enrich_narratives(parse_narratives(LAUNCH_DESCRIPTIONS), launch_data)

    try:
        url = f"{LAUNCH_API_BASE_URL}/recent_launches_narratives"
        profiler.mark("fetch_narratives: API Request Start")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        profiler.mark("fetch_narratives: API Request End")

        raw_narratives = data.get('descriptions', [])
        if raw_narratives:
            narratives = parse_narratives(raw_narratives)
            save_cache_to_file(RUNTIME_CACHE_FILE_NARRATIVES, narratives, datetime.now(pytz.UTC))
            profiler.mark("fetch_narratives End (Success)")
            return enrich_narratives(narratives, launch_data)

    except Exception as e:
        logger.warning(f"Failed to fetch narratives from API: {e}")
        profiler.mark("fetch_narratives End (Error)")

    if cache and cache.get('data'):
        return enrich_narratives(cache['data'], launch_data)
    return enrich_narratives(parse_narratives(LAUNCH_DESCRIPTIONS), launch_data)

# Weather condition codes mapping (WMO Weather interpretation codes)
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def c_to_f(c):
    """Convert Celsius to Fahrenheit."""
    try:
        return (float(c) * 9/5) + 32
    except (ValueError, TypeError):
        return c

def fetch_weather(lat, lon, location):
    """Fetch weather for a single location from the new API."""
    profiler.mark(f"fetch_weather Start ({location})")
    logger.info(f"Fetching weather for {location} via new API")
    try:
        url = f"{LAUNCH_API_BASE_URL}/weather/{location}"
        profiler.mark(f"fetch_weather: Request Start ({location})")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        res_json = response.json()
        
        # Post-process forecast data to include condition strings and day names
        if 'forecast' in res_json and 'daily' in res_json['forecast']:
            daily = res_json['forecast']['daily']
            hourly = res_json['forecast'].get('hourly', {})
            forecast_list = []
            
            times = daily.get('time', [])
            max_temps_c = daily.get('temperature_2m_max', [])
            min_temps_c = daily.get('temperature_2m_min', [])
            codes = daily.get('weathercode', [])
            
            # Convert to Fahrenheit
            max_temps = [c_to_f(c) for c in max_temps_c]
            min_temps = [c_to_f(c) for c in min_temps_c]
            
            # Map hourly temps and wind to days for sparklines
            hourly_times = hourly.get('time', [])
            hourly_temps_c = hourly.get('temperature_2m', [])
            hourly_temps = [c_to_f(c) for c in hourly_temps_c]
            # API documentation says windspeed_10m, but we'll check both for robustness
            hourly_winds = hourly.get('windspeed_10m', hourly.get('wind_speed_10m', []))
            
            for i in range(len(times)):
                try:
                    dt = datetime.strptime(times[i], "%Y-%m-%d")
                    day_name = dt.strftime("%a")
                    
                    # Extract 24h of hourly data for this day for sparklines
                    day_hourly_temps = []
                    day_hourly_winds = []
                    day_str = times[i]
                    for h_idx, h_time in enumerate(hourly_times):
                        if h_time.startswith(day_str):
                            day_hourly_temps.append(hourly_temps[h_idx])
                            if h_idx < len(hourly_winds):
                                day_hourly_winds.append(hourly_winds[h_idx])
                    
                    # If no hourly data for this day, fallback to [min, max] or [0, 0]
                    if not day_hourly_temps:
                        day_hourly_temps = [min_temps[i], max_temps[i]]
                    
                    # Calculate a representative wind for the day (average speed and direction)
                    if day_hourly_winds:
                        avg_wind = sum(day_hourly_winds) / len(day_hourly_winds)
                        # Find the corresponding wind directions for this day
                        day_hourly_dirs = []
                        hourly_dirs = hourly.get('winddirection_10m', [])
                        for h_idx, h_time in enumerate(hourly_times):
                            if h_time.startswith(day_str) and h_idx < len(hourly_dirs):
                                day_hourly_dirs.append(hourly_dirs[h_idx])
                        
                        avg_dir = sum(day_hourly_dirs) / len(day_hourly_dirs) if day_hourly_dirs else 0
                        wind_str = f"{int(avg_wind)}kt {int(avg_dir)}°"
                    else:
                        day_hourly_winds = [0, 0]
                        wind_str = "N/A"
                    
                    forecast_list.append({
                        'day': day_name,
                        'temp_low': f"{int(min_temps[i])}°",
                        'temp_high': f"{int(max_temps[i])}°",
                        'condition': WEATHER_CODE_MAP.get(codes[i], "Unknown"),
                        'wind': wind_str,
                        'temps': day_hourly_temps,
                        'winds': day_hourly_winds
                    })
                except Exception as ex:
                    logger.debug(f"Error parsing forecast day {i}: {ex}")
            
            res_json['forecast_processed'] = forecast_list
            
        profiler.mark(f"fetch_weather End ({location}: Success)")
        return res_json
    except Exception as e:
        logger.warning(f"Failed to fetch weather for {location}: {e}")
        profiler.mark(f"fetch_weather End ({location}: Error)")
        return {
            'temperature_c': (77 - 32) * 5/9, 'temperature_f': 77,
            'wind_speed_ms': 5, 'wind_speed_kts': 9.7,
            'wind_direction': 90, 'cloud_cover': 50
        }


# --- WiFi and Encryption Helpers ---

def get_encryption_key():
    """Get or create encryption key for WiFi passwords"""
    # Ensure cache directory exists so key persists across runs
    try:
        os.makedirs(os.path.dirname(WIFI_KEY_FILE), exist_ok=True)
    except Exception as _e:
        logger.debug(f"Failed to ensure cache directory for key: {_e}")
    if os.path.exists(WIFI_KEY_FILE):
        with open(WIFI_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        # Generate a new key
        key = Fernet.generate_key()
        with open(WIFI_KEY_FILE, 'wb') as f:
            f.write(key)
        # Set restrictive permissions on Linux
        if platform.system() != 'Windows':
            try:
                os.chmod(WIFI_KEY_FILE, 0o600)
            except:
                pass
        return key


def encrypt_password(password, key=None):
    """Encrypt a password"""
    if not password:
        return None
    if key is None:
        key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password, key=None):
    """Decrypt a password"""
    if not encrypted_password:
        return None
    try:
        if key is None:
            key = get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_password.encode()).decode()
    except:
        return None


def get_wifi_interface():
    """Get the WiFi interface name with robust detection"""
    try:
        # 1. Try nmcli first (most reliable on Pi/Modern Linux)
        device_result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device', 'status'], 
                                     capture_output=True, text=True, timeout=5)
        if device_result.returncode == 0:
            for line in device_result.stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 2 and parts[1].lower() == 'wifi':
                    return parts[0]

        # 2. Try common patterns in /sys/class/net
        if os.path.exists('/sys/class/net/'):
            ifaces = os.listdir('/sys/class/net/')
            for iface in ifaces:
                if iface.startswith(('wlan', 'wlp', 'wlx')):
                    return iface
                
    except Exception as e:
        logger.debug(f"Error detecting WiFi interface: {e}")

    return 'wlan0'  # PI Default


def load_remembered_networks(key=None):
    """Load remembered WiFi networks from file"""
    profiler.mark("load_remembered_networks Start")
    try:
        if os.path.exists(REMEMBERED_NETWORKS_FILE):
            if key is None:
                key = get_encryption_key()
            with open(REMEMBERED_NETWORKS_FILE, 'r', encoding='utf-8') as f:
                networks = json.load(f)
                # Decrypt passwords and ensure last_connected key exists
                for network in networks:
                    if 'password' in network and network['password']:
                        network['password'] = decrypt_password(network['password'], key)
                    if 'last_connected' not in network:
                        network['last_connected'] = 0
                # Sort by most recent first (desc)
                networks.sort(key=lambda n: n.get('last_connected', 0), reverse=True)
                profiler.mark("load_remembered_networks End (Success)")
                return networks
        profiler.mark("load_remembered_networks End (Not Found)")
        return []
    except Exception as e:
        logger.error(f"Error loading remembered networks: {e}")
        profiler.mark("load_remembered_networks End (Error)")
        return []


def save_remembered_networks(remembered_networks, key=None):
    """Save remembered WiFi networks to file"""
    try:
        # Ensure cache directory exists before writing
        try:
            os.makedirs(os.path.dirname(REMEMBERED_NETWORKS_FILE), exist_ok=True)
        except Exception as _e:
            logger.debug(f"Failed to ensure cache directory for remembered networks: {_e}")
        
        if key is None:
            key = get_encryption_key()
            
        # Encrypt passwords before saving
        networks_to_save = []
        for network in remembered_networks:
            network_copy = network.copy()
            if 'password' in network_copy and network_copy['password']:
                network_copy['password'] = encrypt_password(network_copy['password'], key)
            networks_to_save.append(network_copy)
            
        with open(REMEMBERED_NETWORKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(networks_to_save, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving remembered networks: {e}")


def load_last_connected_network():
    """Load the last connected network from file"""
    profiler.mark("load_last_connected_network Start")
    try:
        if os.path.exists(LAST_CONNECTED_NETWORK_FILE):
            with open(LAST_CONNECTED_NETWORK_FILE, 'r', encoding='utf-8') as f:
                res = json.load(f)
                profiler.mark("load_last_connected_network End (Success)")
                return res
        profiler.mark("load_last_connected_network End (Not Found)")
    except Exception as e:
        logger.error(f"Error loading last connected network: {e}")
        profiler.mark("load_last_connected_network End (Error)")
    return None


def save_last_connected_network(ssid):
    """Save the last connected network to file"""
    try:
        # Ensure cache directory exists before writing
        try:
            os.makedirs(os.path.dirname(LAST_CONNECTED_NETWORK_FILE), exist_ok=True)
        except Exception as _e:
            logger.debug(f"Failed to ensure cache directory for last connected network: {_e}")
        
        ts = time.time()
        with open(LAST_CONNECTED_NETWORK_FILE, 'w', encoding='utf-8') as f:
            json.dump({'ssid': ssid, 'timestamp': ts}, f, indent=2, ensure_ascii=False)
            
        return ts
    except Exception as e:
        logger.error(f"Error saving last connected network: {e}")
        return time.time()


# --- HTTP Server Helper ---

HTTP_SERVER_PORT = 8080
HTTP_SERVER_READY = threading.Event()

def start_http_server():
    """Start a simple HTTP server for the globe and other web content"""
    global HTTP_SERVER_PORT
    # Set directory to serve from (src directory where app.py / functions.py live)
    src_dir = os.path.dirname(__file__)

    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=src_dir, **kwargs)

        def do_GET(self):
            # Handle favicon requests to avoid noisy 404s
            if self.path in ("/favicon.ico", "/_favicon.ico"):
                try:
                    # Try to serve project favicon if present
                    icon_path = os.path.join(src_dir, '..', 'assets', 'images', 'favicon.ico')
                    if os.path.exists(icon_path):
                        self.send_response(200)
                        self.send_header("Content-Type", "image/x-icon")
                        self.end_headers()
                        with open(icon_path, 'rb') as f:
                            self.wfile.write(f.read())
                        return
                except Exception:
                    pass
                # Otherwise reply 204 No Content
                self.send_response(204)
                self.end_headers()
                return
            return super().do_GET()

    handler = CustomHTTPRequestHandler

    # Try to start server on port 8080, then try alternative ports if busy
    for attempt_port in [8080, 8081, 8082, 8083, 8084]:
        try:
            # Note: We use "" to bind to all interfaces, but 127.0.0.1 is used for local access
            with socketserver.TCPServer(("", attempt_port), handler) as httpd:
                # Allow address reuse to prevent "address already in use" errors
                httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                HTTP_SERVER_PORT = attempt_port
                HTTP_SERVER_READY.set()
                logger.info(f"Serving HTTP on port {attempt_port} from {src_dir}")
                httpd.serve_forever()
        except OSError as e:
            if platform.system() == 'Windows' and e.errno == 10048:  # Address already in use
                logger.warning(f"Port {attempt_port} already in use, trying next port...")
                continue
            elif platform.system() != 'Windows' and e.errno == 98:  # Address already in use on Linux
                logger.warning(f"Port {attempt_port} already in use, trying next port...")
                continue
            else:
                logger.error(f"Failed to start HTTP server on port {attempt_port}: {e}")
                break
        except Exception as e:
            logger.error(f"Unexpected error starting HTTP server: {e}")
            break
    else:
        logger.error("Failed to start HTTP server on any available port (8080-8084)")


def perform_wifi_scan(wifi_interface):
    """Perform a WiFi scan using platform-specific commands."""
    networks = []
    try:
        if platform.system() == 'Windows':
            # Simplified Windows scan polling
            seen = {}
            start_time = time.time()
            # Poll for up to 8 seconds to get a stable list
            while time.time() - start_time < 8.0:
                result = subprocess.run(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    current_seen = {}
                    current_network = None
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if line.startswith('SSID') and ':' in line:
                            ssid_match = re.search(r'SSID\s*\d*\s*:\s*(.+)', line)
                            if ssid_match:
                                ssid = ssid_match.group(1).strip()
                                if ssid and ssid != '<disconnected>':
                                    if ssid not in current_seen:
                                        current_seen[ssid] = {'ssid': ssid, 'signal': 0, 'encrypted': False}
                                    current_network = current_seen[ssid]
                                else: current_network = None
                            else: current_network = None
                        elif line.startswith('Signal') and ':' in line and current_network:
                            sig_match = re.search(r'Signal\s*:\s*(\d+)%', line)
                            if sig_match:
                                sig = int(sig_match.group(1))
                                if sig > current_network['signal']: current_network['signal'] = sig
                        elif 'Authentication' in line and current_network:
                            if 'Open' not in line:
                                current_network['encrypted'] = True

                    for s, data in current_seen.items():
                        if s not in seen or data['signal'] > seen[s]['signal']:
                            seen[s] = data
                time.sleep(0.6)
            return list(seen.values())

        else:
            # Check if nmcli exists and use it if available
            nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=3)
            if nmcli_check.returncode == 0:
                logger.debug("Scanning for WiFi networks using nmcli...")
                subprocess.run(['nmcli', 'device', 'wifi', 'rescan'], capture_output=True, timeout=10)
                time.sleep(1.5)
                nm_list = subprocess.run(['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,CHAN,BARS', 'device', 'wifi', 'list'],
                                         capture_output=True, text=True, timeout=10)
                if nm_list.returncode == 0:
                    networks = []
                    for line in nm_list.stdout.strip().split('\n'):
                        if not line: continue
                        parts = line.split(':')
                        if len(parts) >= 2:
                            ssid = parts[0].strip()
                            if not ssid: continue
                            if '\\x' in ssid:
                                try:
                                    ssid = ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                except Exception: pass
                            try:
                                signal_percent = int(parts[1]) if parts[1].isdigit() else 0
                            except Exception: signal_percent = 0
                            security = parts[2] if len(parts) > 2 else ''
                            encrypted = bool(security) and security.upper() not in ('--', 'NONE')
                            networks.append({'ssid': ssid, 'signal': signal_percent, 'encrypted': encrypted})
                    logger.info(f"nmcli scan found {len(networks)} networks")
                    return networks

            # Fallback for Linux without nmcli (wpa_cli)
            wpa_check = subprocess.run(['which', 'wpa_cli'], capture_output=True, timeout=3)
            if wpa_check.returncode == 0:
                logger.debug("Scanning for WiFi networks using wpa_cli loop...")
                subprocess.run(['wpa_cli', '-i', wifi_interface, 'scan'], capture_output=True, timeout=5)
                
                start_time = time.time()
                last_count = -1
                last_increase_ts = start_time
                last_rescan_ts = start_time
                rescan_interval = 3.5
                stabilize_no_growth = 3.5
                max_window = 18.0
                seen = {}
                current_seen = {}
                
                while time.time() - start_time < max_window:
                    now = time.time()
                    if now - last_rescan_ts >= rescan_interval:
                        try: subprocess.run(['wpa_cli', '-i', wifi_interface, 'scan'], capture_output=True, timeout=5)
                        except: pass
                        last_rescan_ts = now

                    results_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'scan_results'], capture_output=True, text=True, timeout=5)
                    if results_result.returncode != 0:
                        time.sleep(0.3)
                        continue

                    raw_output = results_result.stdout.strip()
                    if not raw_output:
                        time.sleep(0.3)
                        continue

                    current_seen = {}
                    lines = raw_output.split('\n')
                    for line in lines[1:]:
                        parts = line.split('\t')
                        if len(parts) >= 5:
                            signal_level = int(parts[2]) if parts[2].lstrip('-').isdigit() else -100
                            flags = parts[3]
                            ssid = parts[4] if len(parts) > 4 else ''
                            if ssid and '\\x' in ssid:
                                try:
                                    ssid = ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                except Exception: pass
                            if ssid and ssid != '<hidden>':
                                signal_percent = min(100, max(0, 100 + signal_level))
                                encrypted = 'WPA' in flags or 'WEP' in flags
                                if ssid not in current_seen or signal_percent > current_seen[ssid]['signal']:
                                    current_seen[ssid] = {'ssid': ssid, 'signal': signal_percent, 'encrypted': encrypted}
                    
                    for s, data in current_seen.items():
                        if s not in seen or data['signal'] > seen[s]['signal']:
                            seen[s] = data
                    
                    count = len(seen)
                    if count > last_count:
                        last_count = count
                        last_increase_ts = now
                    else:
                        if (now - start_time) >= 8.0 and (now - last_increase_ts) >= stabilize_no_growth and count > 0:
                            break
                    time.sleep(0.45)
                
                return list(seen.values())

    except Exception as e:
        logger.error(f"Error performing WiFi scan: {e}")
    return networks


def manage_nm_autoconnect(ssid):
    """Manage NetworkManager autoconnect settings for a specific SSID"""
    try:
        if platform.system() != 'Linux' or not ssid:
            return

        nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=5)
        if nmcli_check.returncode != 0: return

        result = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,802-11-wireless.ssid,AUTOCONNECT', 'connection', 'show'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode != 0: return

        target_names = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip(): continue
            parts = line.split(':')
            if len(parts) >= 4:
                name, ctype, ssid_field, autoconnect = parts[0], parts[1], parts[2], parts[3]
                if ctype.lower() == 'wifi' and ssid_field == ssid:
                    target_names.append((name, autoconnect.lower() == 'yes'))

        if not target_names:
            target_names.append((ssid, False))

        for name, is_auto in target_names:
            if not is_auto:
                subprocess.run(['nmcli', 'connection', 'modify', name, 'connection.autoconnect', 'yes'], capture_output=True, timeout=5)
            subprocess.run(['nmcli', 'connection', 'modify', name, 'connection.autoconnect-priority', '100'], capture_output=True, timeout=5)
            subprocess.run(['nmcli', 'connection', 'modify', name, 'connection.autoconnect-retries', '-1'], capture_output=True, timeout=5)
            subprocess.run(['nmcli', 'connection', 'modify', name, 'connection.permissions', ''], capture_output=True, timeout=5)
    except Exception as e:
        logger.error(f"Error managing NM autoconnect: {e}")


# --- Network connectivity state cache to avoid repeated slow tests during boot ---
_network_last_result = None
_network_last_check_time = 0
NETWORK_CHECK_TTL = 30  # seconds
_network_check_lock = threading.Lock()

def test_network_connectivity():
    """Check for active network connectivity (beyond just WiFi connection)"""
    global _network_last_result, _network_last_check_time
    
    with _network_check_lock:
        now = time.time()
        if _network_last_result is not None and (now - _network_last_check_time) < NETWORK_CHECK_TTL:
            logger.debug(f"Returning cached network connectivity result: {_network_last_result}")
            return _network_last_result

        profiler.mark("test_network_connectivity Start")
        test_urls = [
            'http://www.google.com',
            'http://www.cloudflare.com',
            'http://1.1.1.1'
        ]

        logger.debug("Testing network connectivity with multiple endpoints...")

        result = False
        for url in test_urls:
            try:
                logger.debug(f"Testing connectivity to {url}")
                urllib.request.urlopen(url, timeout=3)  # Reduced timeout for faster boot
                logger.info(f"Network connectivity confirmed via {url}")
                result = True
                break
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                logger.debug(f"Failed to connect to {url}: {e}")
                continue

        if not result:
            # Fallback DNS test
            try:
                logger.debug("Testing DNS resolution...")
                socket.gethostbyname('google.com')
                logger.info("Network connectivity confirmed via DNS")
                result = True
            except socket.gaierror as e:
                logger.debug(f"DNS resolution failed: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error during DNS test: {e}")

        _network_last_result = result
        _network_last_check_time = now
        profiler.mark(f"test_network_connectivity End (Result: {result})")
        
        if not result:
            logger.warning("All network connectivity tests failed")
        
        return result


def get_git_version_info(src_dir):
    """Get summarized git version info (hash and message)"""
    profiler.mark("get_git_version_info Start")
    try:
        res_hash = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=src_dir)
        if res_hash.returncode != 0:
            profiler.mark("get_git_version_info End (Fail: git rev-parse)")
            return None
        commit_hash = res_hash.stdout.strip()

        res_msg = subprocess.run(['git', 'log', '-1', '--pretty=format:%s', commit_hash], capture_output=True, text=True, cwd=src_dir)
        commit_message = res_msg.stdout.strip() if res_msg.returncode == 0 else "Unknown"

        profiler.mark("get_git_version_info End (Success)")
        return {
            'hash': commit_hash,
            'short_hash': commit_hash[:8],
            'message': commit_message
        }
    except Exception as e:
        logger.error(f"Error getting git version info: {e}")
        return None


def check_github_for_updates(current_hash, repo_owner="hwpaige", repo_name="spacex-dashboard", branch="master"):
    """Check if a newer version is available on GitHub using urllib for better boot performance."""
    profiler.mark("check_github_for_updates Start")
    try:
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{branch}"
        # Use urllib.request with a short timeout to avoid GIL contention during boot
        req = urllib.request.Request(api_url, headers={'User-Agent': 'SpaceX-Dashboard-App'})
        logger.info(f"Checking for updates at {api_url}...")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                latest = json.loads(response.read().decode())
                latest_hash = latest['sha']
                profiler.mark("check_github_for_updates End (Success)")
                logger.info(f"Update check successful. Latest hash: {latest_hash[:8]}")
                return latest_hash != current_hash, {
                    'hash': latest_hash,
                    'short_hash': latest_hash[:8],
                    'message': latest['commit']['message'],
                    'author': latest['commit']['author']['name'],
                    'date': latest['commit']['author']['date'],
                    'branch': branch
                }
            else:
                logger.warning(f"GitHub update check returned status {response.status}")
    except urllib.error.URLError as e:
        logger.info(f"GitHub update check network error (possibly offline): {e}")
    except socket.timeout:
        logger.info("GitHub update check timed out after 3 seconds")
    except Exception as e:
        logger.info(f"GitHub update check failed: {type(e).__name__}: {e}")
    
    profiler.mark("check_github_for_updates End (Fail/Timeout)")
    return False, None

def connect_to_wifi_worker(ssid, password, wifi_interface=None):
    """
    Worker function to connect to WiFi on Windows or Linux.
    Returns (success, error_message)
    """
    try:
        if IS_WINDOWS:
            try:
                # Only create/update profile if we have a password. 
                # Otherwise, assume profile exists or isn't needed (e.g. open network or already saved in OS).
                if password:
                    profile_xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig><SSID><name>{ssid}</name></SSID></SSIDConfig>
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
                    # Use a safer temp path for Windows if possible, but keeping original logic
                    temp_dir = os.path.join(os.environ.get('TEMP', 'C:\\temp'), 'wifi_profiles')
                    os.makedirs(temp_dir, exist_ok=True)
                    profile_path = os.path.join(temp_dir, f'wifi_profile_{ssid}.xml')
                    with open(profile_path, 'w') as f:
                        f.write(profile_xml)
                    
                    subprocess.run(['netsh', 'wlan', 'add', 'profile', f'filename={profile_path}'], capture_output=True, timeout=10)
                    
                    try: os.remove(profile_path)
                    except: pass
                
                # Always attempt to connect
                conn_res = subprocess.run(['netsh', 'wlan', 'connect', f'name={ssid}'], capture_output=True, timeout=10)
                
                if conn_res.returncode == 0:
                    return True, None
                return False, conn_res.stderr.decode()
            except Exception as e:
                return False, str(e)
        else:
            # Linux logic
            if not wifi_interface: wifi_interface = get_wifi_interface()
            
            # Try nmcli first
            nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=3)
            if nmcli_check.returncode == 0:
                logger.info(f"Connecting to {ssid} via nmcli on interface {wifi_interface} (with rescan and profile cleanup)")
                
                # 1. Rescan to ensure the SSID is visible to nmcli
                try: 
                    subprocess.run(['nmcli', 'device', 'wifi', 'rescan', 'ifname', wifi_interface], capture_output=True, timeout=8)
                    time.sleep(2) # Give it a moment to populate results
                except Exception as e:
                    logger.debug(f"nmcli rescan failed: {e}")
                
                if password:
                    # 2. Proactively remove existing profile for this SSID to avoid conflicts/stale settings
                    try:
                        logger.debug(f"Cleaning up existing NM profile for {ssid}...")
                        remove_nm_connection(ssid)
                    except Exception as e:
                        logger.debug(f"Pre-connect profile cleanup failed (non-critical): {e}")

                    # 3. Connect using nmcli with explicit profile creation to avoid auto-detection issues
                    # Create profile
                    logger.debug(f"Creating NM profile for {ssid}...")
                    subprocess.run(['nmcli', 'con', 'add', 'type', 'wifi', 'con-name', ssid, 'ifname', wifi_interface, 'ssid', ssid], 
                                 capture_output=True, timeout=10)
                    
                    logger.debug(f"Setting security for {ssid}...")
                    
                    # Auto-detect security type
                    key_mgmt = 'wpa-psk' # Default to WPA-PSK
                    detected_sec = _get_linux_wifi_security_type(ssid, wifi_interface)
                    if detected_sec:
                        key_mgmt = detected_sec
                        logger.info(f"Detected security for {ssid}: {key_mgmt}")
                    
                    subprocess.run(['nmcli', 'con', 'modify', ssid, 'wifi-sec.key-mgmt', key_mgmt], capture_output=True, timeout=5)
                    subprocess.run(['nmcli', 'con', 'modify', ssid, 'wifi-sec.psk', password], capture_output=True, timeout=5)
                
                # Bring up connection (either the new one we just made, or the existing one)
                logger.info(f"Activating connection {ssid}...")
                
                # Retry logic for connection activation
                conn_success = False
                output = ""
                for conn_attempt in range(3):
                    res = subprocess.run(['nmcli', 'con', 'up', ssid], capture_output=True, text=True, timeout=45)
                    if res.returncode == 0:
                        output = res.stdout.strip()
                        logger.info(f"nmcli connection successful: {output}")
                        conn_success = True
                        break
                    else:
                        output = res.stderr.strip() or res.stdout.strip()
                        if conn_attempt < 2:
                            logger.warning(f"nmcli connection attempt {conn_attempt+1} failed: {output}. Retrying...")
                            time.sleep(2)

                if conn_success:
                    return True, None
                
                error_out = output
                logger.warning(f"nmcli connection FAILED for {ssid} (after retries): {error_out}")
                # Don't return yet; try fallback if available

            # Fallback to wpa_cli
            wpa_check = subprocess.run(['which', 'wpa_cli'], capture_output=True, timeout=3)
            if wpa_check.returncode == 0:
                logger.info(f"Connecting to {ssid} via wpa_cli fallback on {wifi_interface}")
                add_res = subprocess.run(['wpa_cli', '-i', wifi_interface, 'add_network'], capture_output=True, text=True, timeout=5)
                if add_res.returncode == 0:
                    net_id = add_res.stdout.strip()
                    ssid_p = f'"{ssid}"' if all(ord(c) < 128 for c in ssid) else ssid.encode('utf-8').hex()
                    subprocess.run(['wpa_cli', '-i', wifi_interface, 'set_network', net_id, 'ssid', ssid_p], capture_output=True, timeout=5)
                    if password:
                        subprocess.run(['wpa_cli', '-i', wifi_interface, 'set_network', net_id, 'psk', f'"{password}"'], capture_output=True, timeout=5)
                    subprocess.run(['wpa_cli', '-i', wifi_interface, 'enable_network', net_id], capture_output=True, timeout=5)
                    sel_res = subprocess.run(['wpa_cli', '-i', wifi_interface, 'select_network', net_id], capture_output=True, timeout=5)
                    if sel_res.returncode == 0:
                        subprocess.run(['wpa_cli', '-i', wifi_interface, 'save_config'], capture_output=True, timeout=5)
                        logger.info(f"wpa_cli connection successful for {ssid}")
                        return True, None
            
            return False, "All connection methods failed"
    except Exception as e:
        logger.error(f"connect_to_wifi_worker error: {e}")
        return False, str(e)

def _get_linux_wifi_security_type(ssid, interface):
    """
    Detect the security type (key-mgmt) for a given SSID using nmcli scan results.
    Returns: 'wpa-psk', 'sae' (WPA3), 'none', or None (unknown)
    """
    # Try up to 3 times to find the SSID in scan results
    for attempt in range(3):
        try:
            # Scan for the specific SSID to get fresh info
            res = subprocess.run(['nmcli', '-t', '-f', 'SSID,SECURITY', 'device', 'wifi', 'list', 'ifname', interface], 
                               capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.strip().split('\n'):
                    parts = line.split(':')
                    if len(parts) >= 2 and parts[0] == ssid:
                        security = parts[1].upper()
                        if 'WPA' in security or 'RSN' in security:
                             if 'SAE' in security: return 'sae' # WPA3
                             return 'wpa-psk' # WPA/WPA2
                        if 'WEP' in security: return 'none'
                        return 'none' # Open
            
            # If not found, wait briefly and try again (unless it's the last attempt)
            if attempt < 2:
                time.sleep(1.5)
                # Trigger a fresh rescan if we didn't see it (nondestructive)
                try: subprocess.run(['nmcli', 'device', 'wifi', 'rescan', 'ifname', interface], capture_output=True, timeout=5)
                except: pass
                
        except Exception as e:
            logger.debug(f"Security detection attempt {attempt+1} failed: {e}")
            if attempt < 2: time.sleep(1)
            
    return None


def get_launch_trends_series(launches, chart_view_mode, current_year, current_month):
    """Process launch data into series for charting using plain Python (no pandas for better performance)"""
    profiler.mark("get_launch_trends_series Start")
    rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
    
    if chart_view_mode == 'cumulative':
        # Cumulative plots show Jan to current month of the current year (yearly goal progress)
        all_months = [f"{current_year}-{m:02d}" for m in range(1, current_month + 1)]
    else:
        # Non-cumulative plots show a rolling 12-month period
        all_months = []
        for i in range(11, -1, -1):
            m = current_month - i
            y = current_year
            while m <= 0:
                m += 12
                y -= 1
            all_months.append(f"{y}-{m:02d}")
    
    # Initialize counts: { month: { rocket: count } }
    counts = {m: {r: 0 for r in rocket_types} for m in all_months}
    
    for launch in launches:
        date_str = launch.get('date')
        if not date_str or date_str == 'TBD':
            continue
            
        try:
            # Assuming date format is YYYY-MM-DD
            year = int(date_str[:4])
            month_idx = int(date_str[5:7])
            
            month_key = f"{year}-{month_idx:02d}"
            
            # Check if this month is in our range
            if month_key not in counts:
                continue
            
            rocket = launch.get('rocket', 'Unknown')
            
            # Match rocket types (partial match for flexibility)
            matched_rocket = None
            for rt in rocket_types:
                if rt.lower() in rocket.lower():
                    matched_rocket = rt
                    break
            
            if matched_rocket and month_key in counts:
                counts[month_key][matched_rocket] += 1
        except (ValueError, IndexError):
            continue

    # Prepare series data
    series = []
    for rocket in rocket_types:
        values = []
        cumulative = 0
        for m in all_months:
            val = counts[m][rocket]
            if chart_view_mode == 'cumulative':
                cumulative += val
                values.append(cumulative)
            else:
                values.append(val)
        
        series.append({
            'label': rocket,
            'values': values
        })
    
    profiler.mark("get_launch_trends_series End")
    return all_months, series

# Global trajectory data cache to avoid redundant disk I/O
_TRAJECTORY_DATA_CACHE = None

def get_launch_trajectory_data(upcoming_launches, previous_launches=None):
    """
    Get trajectory data for the next upcoming launch or a specific launch.
    If upcoming_launches is a dict, treat it as a single launch object.
    If upcoming_launches is a list, use the first item (existing behavior).
    Standalone version of Backend.get_launch_trajectory.
    """
    profiler.mark("get_launch_trajectory_data Start")
    logger.info("get_launch_trajectory_data called")
    
    # Handle single launch object (dict) vs list of launches
    if isinstance(upcoming_launches, dict):
        # Single launch object
        display_launches = [upcoming_launches]
    else:
        # List of launches (existing behavior)
        display_launches = upcoming_launches
        if not display_launches:
            logger.info("No upcoming launches, trying recent launches")
            if previous_launches:
                recent_launches = previous_launches[:5]
                if recent_launches:
                    display_launches = [{
                        'mission': launch.get('mission', 'Unknown'),
                        'pad': launch.get('pad', 'Cape Canaveral'),
                        'orbit': launch.get('orbit', 'LEO'),
                        'net': launch.get('net', ''),
                        'landing_type': launch.get('landing_type')
                    } for launch in recent_launches]
                    logger.info(f"Using {len(display_launches)} recent launches for demo")

    if not display_launches:
        logger.info("No launches available at all")
        return None

    next_launch = display_launches[0]
    mission_name = next_launch.get('mission', 'Unknown')
    pad = next_launch.get('pad', '')
    orbit = next_launch.get('orbit', '')
    logger.info(f"Next launch: {mission_name} from {pad}")

    # Launch site coordinates
    launch_sites = {
        'LC-39A': {'lat': 28.6084, 'lon': -80.6043, 'name': 'Cape Canaveral, FL'},
        'LC-40': {'lat': 28.5619, 'lon': -80.5773, 'name': 'Cape Canaveral, FL'},
        'SLC-4E': {'lat': 34.6321, 'lon': -120.6107, 'name': 'Vandenberg, CA'},
        'Starbase': {'lat': 25.9975, 'lon': -97.1566, 'name': 'Starbase, TX'},
        'Launch Complex 39A': {'lat': 28.6084, 'lon': -80.6043, 'name': 'Cape Canaveral, FL'},
        'Launch Complex 40': {'lat': 28.5619, 'lon': -80.5773, 'name': 'Cape Canaveral, FL'},
        'Space Launch Complex 4E': {'lat': 34.6321, 'lon': -120.6107, 'name': 'Vandenberg, CA'}
    }

    # Find launch site coordinates
    launch_site = None
    matched_site_key = None
    for site_key, site_data in launch_sites.items():
        if site_key in pad:
            launch_site = site_data
            matched_site_key = site_key
            break

    if not launch_site:
        launch_site = launch_sites['LC-39A']
        matched_site_key = 'LC-39A'
        logger.info(f"Using default launch site: {launch_site}")

    def _normalize_orbit(orbit_label: str, site_name: str) -> str:
        try:
            label = (orbit_label or '').lower()
            if 'gto' in label or 'geostationary' in label:
                return 'GTO'
            if 'suborbital' in label:
                return 'Suborbital'
            # Explicit Polar/SSO detection
            if any(k in label for k in ['polar', 'sso', 'sun-synchronous']):
                return 'LEO-Polar'
            if 'leo' in label or 'low earth orbit' in label:
                if 'Vandenberg' in site_name:
                    return 'LEO-Polar'
                return 'LEO-Equatorial'
            return 'Default'
        except Exception:
            return 'Default'

    normalized_orbit = _normalize_orbit(orbit, launch_site.get('name', ''))

    # Resolve an inclination assumption
    def _resolve_inclination_deg(norm_orbit: str, site_name: str, site_lat: float) -> float:
        try:
            label = (orbit or '').lower()
            if 'iss' in label:
                return 51.6
            if norm_orbit == 'LEO-Polar' or 'sso' in label or 'sun-synchronous' in label:
                return 97.5 # Better average for SSO
            if norm_orbit == 'LEO-Equatorial':
                base = abs(site_lat)
                return max(20.0, min(60.0, base + 0.5))
            if norm_orbit == 'GTO':
                return max(20.0, min(35.0, abs(site_lat)))
            if norm_orbit == 'Suborbital':
                return max(10.0, min(45.0, abs(site_lat)))
        except Exception:
            pass
        return 30.0

    assumed_incl = _resolve_inclination_deg(
        normalized_orbit,
        launch_site.get('name', ''),
        launch_site.get('lat', 0.0)
    )

    ORBIT_CACHE_VERSION = 'v230-hybrid-ro'
    landing_type = next_launch.get('landing_type')
    landing_loc = next_launch.get('landing_location')
    cache_key = f"{ORBIT_CACHE_VERSION}:{matched_site_key}:{normalized_orbit}:{round(assumed_incl,1)}:{landing_type}:{landing_loc}"
    
    global _TRAJECTORY_DATA_CACHE
    if _TRAJECTORY_DATA_CACHE is None:
        logger.info("Loading trajectory cache from disk...")
        cache_loaded = load_cache_from_file(TRAJECTORY_CACHE_FILE)
        if cache_loaded and isinstance(cache_loaded.get('data'), dict):
            _TRAJECTORY_DATA_CACHE = cache_loaded['data']
        else:
            # Handle direct dictionary without 'data' wrapper if it exists
            _TRAJECTORY_DATA_CACHE = cache_loaded if isinstance(cache_loaded, dict) else {}

    if cache_key in _TRAJECTORY_DATA_CACHE:
        cached = _TRAJECTORY_DATA_CACHE[cache_key]
        logger.info(f"Trajectory in-memory cache hit for {cache_key}")
        return {
            'launch_site': cached.get('launch_site', launch_site),
            'trajectory': cached.get('trajectory', []),
            'booster_trajectory': cached.get('booster_trajectory', []),
            'sep_idx': cached.get('sep_idx'),
            'orbit_path': cached.get('orbit_path', []),
            'orbit': orbit or cached.get('orbit', normalized_orbit),
            'mission': mission_name,
            'pad': pad,
            'landing_type': landing_type,
            'landing_location': cached.get('landing_location', next_launch.get('landing_location'))
        }

    traj_cache = _TRAJECTORY_DATA_CACHE
    logger.info(f"Trajectory cache miss for {cache_key}; generating new trajectory")

    def get_radius(progress, target_radius, offset=0.0):
        """Calculate visual radius with a smooth quadratic ease-out to avoid janky dips."""
        TRAJ_START_RADIUS = 1.012 
        # Use quadratic ease-out: 2t - t^2. This ensures vertical velocity is zero at the end.
        climb_progress = 2 * progress - progress**2
        radius = TRAJ_START_RADIUS + (target_radius - TRAJ_START_RADIUS) * climb_progress + offset
        return radius

    def generate_curved_trajectory(start_point, end_point, num_points, orbit_type='default', end_bearing_deg=None):
        points = []
        start_lat = start_point['lat']
        start_lon = start_point['lon']
        end_lat = end_point['lat']
        end_lon = end_point['lon']

        if end_bearing_deg is not None:
            lat1 = math.radians(start_lat); lon1 = math.radians(start_lon)
            lat2 = math.radians(end_lat);   lon2 = math.radians(end_lon)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(1e-12, 1-a)))
            ang_deg = math.degrees(c)
            # Tighter control point distance (L) to avoid "flat" segments near insertion
            L = min(15.0, max(3.0, ang_deg / 4.0))
            br = math.radians(end_bearing_deg)
            cos_lat = max(1e-6, math.cos(math.radians(end_lat)))
            dlat_deg = L * math.cos(br)
            dlon_deg = (L * math.sin(br)) / cos_lat
            control_lat = end_lat - dlat_deg
            control_lon = (end_lon - dlon_deg + 180.0) % 360.0 - 180.0
        else:
            mid_lat = (start_lat + end_lat) / 2
            mid_lon = (start_lon + end_lon) / 2
            dist = _ang_dist_deg(start_point, end_point)
            
            # Scale control point offset based on distance
            offset = max(5, min(30, dist * 0.4))
            
            if orbit_type == 'polar':
                control_lat = max(-85.0, mid_lat - offset)
                control_lon = mid_lon - offset/2
            elif orbit_type == 'equatorial':
                # Aim more towards equator
                target_equator_lat = 0
                control_lat = (mid_lat + target_equator_lat) / 2
                control_lon = mid_lon + offset
            elif orbit_type == 'gto':
                control_lat = mid_lat + offset
                control_lon = mid_lon + offset * 2
            elif orbit_type == 'suborbital':
                # Suborbital/Booster return needs a tighter arc
                control_lat = mid_lat + offset/4
                control_lon = mid_lon + offset/4
            else:
                control_lat = mid_lat + offset
                control_lon = mid_lon + offset * 1.5

        for i in range(num_points + 1):
            t = i / num_points
            lat = (1-t)**2 * start_lat + 2*(1-t)*t * control_lat + t**2 * end_lat
            lon = (1-t)**2 * start_lon + 2*(1-t)*t * control_lon + t**2 * end_lon
            lon = (lon + 180) % 360 - 180
            points.append({'lat': lat, 'lon': lon})
        return points

    def generate_spherical_path(start_point, inclination_deg, num_points=2000, descending=False):
        """Generate a full Great Circle path passing through start_point with given inclination."""
        lat0 = float(start_point['lat']); lon0 = float(start_point['lon'])
        # Handle nearly-polar or nearly-equatorial cases with small epsilon
        eff_i_deg = max(0.1, min(179.9, abs(inclination_deg)))
        i_rad = math.radians(eff_i_deg)
        lat0_rad = math.radians(lat0); lon0_rad = math.radians(lon0)
        
        # Position vector
        x0 = math.cos(lat0_rad) * math.cos(lon0_rad)
        y0 = math.cos(lat0_rad) * math.sin(lon0_rad)
        z0 = math.sin(lat0_rad)
        
        sin_i = math.sin(i_rad)
        # Argument of latitude u0 at start_point
        u0 = math.asin(max(-1.0, min(1.0, z0 / (sin_i or 1e-6))))
        
        # If we want to be on the descending part of the orbit (going South)
        if descending:
            u0 = math.pi - u0
            
        # Longitude of Ascending Node (Omega)
        Omega = math.atan2(y0, x0) - math.atan2(math.sin(u0) * math.cos(i_rad), math.cos(u0))
        
        cosO = math.cos(Omega); sinO = math.sin(Omega)
        cosi = math.cos(i_rad); sili = math.sin(i_rad)
        
        points = []
        for k in range(num_points):
            u = u0 + (2.0 * math.pi * k) / num_points
            cu = math.cos(u); su = math.sin(u)
            # Transform from orbital frame to ECEF-like lat/lon
            x = cosO * cu - sinO * (su * cosi)
            y = sinO * cu + cosO * (su * cosi)
            z = su * sili
            points.append({
                'lat': math.degrees(math.atan2(z, max(1e-12, math.hypot(x, y)))), 
                'lon': (math.degrees(math.atan2(y, x)) + 180) % 360 - 180
            })
        return points

    # Main generation
    target_r = compute_orbit_radius(orbit)
    
    # Heuristic for launch direction: VAFB launches are usually descending (Southward)
    is_desc = False
    if 'Vandenberg' in launch_site.get('name', '') or 'SLC-4E' in pad:
        is_desc = True
    
    # Generate the Master Path (The Orbit)
    # We use 2000 points for a smooth full circle
    master_path = generate_spherical_path(launch_site, assumed_incl, num_points=2000, descending=is_desc)
    
    # The ascent trajectory is a segment of the SAME Master Path
    # LEO ascent usually takes ~10% of an orbit. Let's use 12.5% for visual length.
    traj_len = int(len(master_path) * 0.125)
    trajectory = [p.copy() for p in master_path[:traj_len]]
    
    # The orbit path is the REMAINING part of the Master Path to avoid overlap and "double touching"
    if normalized_orbit != 'Suborbital':
        # Starts at the insertion point (traj_len-1) and goes around to the end of the master path circle.
        # This prevents the orbit line from being drawn over the ascent segment.
        orbit_path = [p.copy() for p in master_path[traj_len-1:]]
    else:
        orbit_path = []

    # Set radii for the orbit path
    for p in orbit_path:
        p['r'] = target_r

    # Add radii to main trajectory
    for i, p in enumerate(trajectory):
        progress = i / (len(trajectory) - 1)
        p['r'] = get_radius(progress, target_r)

    # Booster Return Trajectory (RTLS vs ASDS vs Expendable simulation)
    booster_trajectory = []
    sep_idx = None
    if trajectory and len(trajectory) > 5:
        try:
            # Separation usually around 1/5th of the way to orbit
            sep_idx = max(2, len(trajectory) // 5)
            # Create booster ascent with a tiny radius offset to ensure it's visible outside main trajectory
            ascent_part = []
            for i, p in enumerate(trajectory[:sep_idx+1]):
                bp = p.copy()
                # Apply a subtle 0.001 offset (approx 6km) to keep booster visible
                bp['r'] = (bp.get('r') or 1.012) + 0.001
                ascent_part.append(bp)
                
            sep_point = ascent_part[-1]
            sep_radius = sep_point['r']

            l_type = (landing_type or '').upper()
            l_loc = (next_launch.get('landing_location') or '').upper()
            combined_landing_info = f"{l_type} {l_loc}"
            
            # Expanded detection for ASDS and RTLS
            asds_keywords = ['ASDS', 'DRONE', 'SHIP', 'OCISLY', 'JRTI', 'ASOG', 'GRAVITAS', 'INSTRUCTIONS', 'STILL LOVE YOU']
            rtls_keywords = ['RTLS', 'LAUNCH SITE', 'CATCH', 'TOWER', 'LZ', 'LANDING ZONE']
            
            if any(k in combined_landing_info for k in asds_keywords):
                # Droneship landing: continues downrange to a point further along the trajectory
                landing_idx = min(len(trajectory) - 1, max(sep_idx + 3, len(trajectory) // 3))
                landing_point = trajectory[landing_idx]
                return_part = generate_curved_trajectory(sep_point, landing_point, 100, orbit_type='suborbital')
                
                # Add radius to return part (ballistic arc)
                for i, p in enumerate(return_part):
                    prog = i / (len(return_part) - 1)
                    # Parabolic arc from sep_radius to 1.01, peaking at sep_radius + 0.02
                    p['r'] = sep_radius + (1.012 - sep_radius) * prog + 0.02 * math.sin(prog * math.pi)
                
                booster_trajectory = return_part
                sep_idx = 0
                logger.info(f"Generated ASDS booster trajectory (info: {combined_landing_info})")
            elif any(k in combined_landing_info for k in rtls_keywords):
                # RTLS/Catch: returns to launch site
                return_part = generate_curved_trajectory(sep_point, launch_site, 100, orbit_type='suborbital')
                for i, p in enumerate(return_part):
                    prog = i / (len(return_part) - 1)
                    # Higher arc for RTLS boostback (~300km peak)
                    p['r'] = sep_radius + (1.012 - sep_radius) * prog + 0.03 * math.sin(prog * math.pi)
                
                booster_trajectory = return_part
                sep_idx = 0
                logger.info(f"Generated RTLS/Catch booster trajectory (info: {combined_landing_info})")
            elif any(k in combined_landing_info for k in ['OCEAN', 'SPLASHDOWN']):
                landing_idx = min(len(trajectory) - 1, max(sep_idx + 2, len(trajectory) // 4))
                landing_point = trajectory[landing_idx]
                return_part = generate_curved_trajectory(sep_point, landing_point, 100, orbit_type='suborbital')
                for i, p in enumerate(return_part):
                    prog = i / (len(return_part) - 1)
                    p['r'] = sep_radius + (1.012 - sep_radius) * prog + 0.015 * math.sin(prog * math.pi)
                booster_trajectory = return_part
                sep_idx = 0
                logger.info(f"Generated Ocean splashdown booster trajectory (type: {landing_type})")
            else:
                # Expendable/Unknown: no return trajectory to show
                booster_trajectory = []
                sep_idx = None
                logger.info(f"Skipping booster trajectory for unknown/expendable type: {landing_type}")
        except Exception as e:
            logger.warning(f"Booster trajectory generation failed: {e}")

    result = {
        'launch_site': launch_site,
        'trajectory': trajectory,
        'booster_trajectory': booster_trajectory,
        'sep_idx': sep_idx,
        'orbit_path': orbit_path,
        'orbit': orbit,
        'mission': mission_name,
        'pad': pad,
        'landing_type': landing_type,
        'landing_location': next_launch.get('landing_location')
    }

    # Persist to cache
    try:
        traj_cache[cache_key] = {
            'launch_site': launch_site,
            'trajectory': trajectory,
            'booster_trajectory': booster_trajectory,
            'sep_idx': sep_idx,
            'orbit_path': orbit_path,
            'orbit': normalized_orbit,
            'inclination_deg': assumed_incl,
            'landing_type': landing_type,
            'landing_location': next_launch.get('landing_location'),
            'model': 'v11-non-overlapping-orbit'
        }
        save_cache_to_file(TRAJECTORY_CACHE_FILE, traj_cache, datetime.now(pytz.UTC))
    except Exception as e:
        logger.warning(f"Failed to save trajectory cache: {e}")

    return result

# Global date parsing cache to avoid redundant expensive calls across different modules
_DATE_PARSE_CACHE = {}
_DATE_PARSE_CACHE_DIRTY = False

def _load_date_cache():
    global _DATE_PARSE_CACHE
    try:
        cache_data = load_cache_from_file(RUNTIME_CACHE_FILE_PARSED_DATES)
        if cache_data and 'data' in cache_data:
            # Convert timestamps back to datetime objects
            for net_str, ts in cache_data['data'].items():
                if ts is None:
                    _DATE_PARSE_CACHE[net_str] = None
                else:
                    _DATE_PARSE_CACHE[net_str] = datetime.fromtimestamp(ts, pytz.UTC)
            logger.info(f"Loaded {len(_DATE_PARSE_CACHE)} parsed dates from cache")
    except Exception as e:
        logger.debug(f"Failed to load date parse cache: {e}")

def _save_date_cache():
    global _DATE_PARSE_CACHE, _DATE_PARSE_CACHE_DIRTY
    if not _DATE_PARSE_CACHE_DIRTY:
        return
    try:
        # Convert datetime objects to timestamps for JSON
        serializable_cache = {}
        for net_str, dt in _DATE_PARSE_CACHE.items():
            if dt is None:
                serializable_cache[net_str] = None
            else:
                serializable_cache[net_str] = dt.timestamp()
        
        save_cache_to_file(RUNTIME_CACHE_FILE_PARSED_DATES, serializable_cache, datetime.now(pytz.UTC))
        _DATE_PARSE_CACHE_DIRTY = False
        logger.info(f"Saved {len(_DATE_PARSE_CACHE)} parsed dates to cache")
    except Exception as e:
        logger.debug(f"Failed to save date parse cache: {e}")

# Initial load
_load_date_cache()

def _get_parsed_dt(net_str):
    """Helper to get parsed datetime from cache or parse it if not cached."""
    global _DATE_PARSE_CACHE, _DATE_PARSE_CACHE_DIRTY
    if not net_str: return None
    if net_str not in _DATE_PARSE_CACHE:
        try:
            dt = parse(net_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            else:
                dt = dt.astimezone(pytz.UTC)
            _DATE_PARSE_CACHE[net_str] = dt
            _DATE_PARSE_CACHE_DIRTY = True
        except Exception:
            _DATE_PARSE_CACHE[net_str] = None
            _DATE_PARSE_CACHE_DIRTY = True
    return _DATE_PARSE_CACHE[net_str]

def group_event_data(data, mode, event_type, timezone_obj):
    """
    Group and filter launch or race event data by date range (Today, This Week, Later, etc.).
    UI-agnostic logic extracted from EventModel.update_data.
    """
    global _DATE_PARSE_CACHE, _DATE_PARSE_CACHE_DIRTY
    profiler.mark(f"group_event_data Start (mode={mode}, type={event_type})")
    
    # ...
    # Determine local "today" for grouping
    today = datetime.now(timezone_obj).date()
    this_week_end = today + timedelta(days=7)
    last_week_start = today - timedelta(days=7)
    grouped = []
    
    if mode == 'spacex':
        # data is expected to be a dict with 'upcoming' and 'previous' keys
        launches = data.get('upcoming' if event_type == 'upcoming' else 'previous', [])
        logger.info(f"group_event_data: Processing {len(launches)} launches")
        
        # Pre-parse dates and add local time to each launch to avoid redundant expensive calls
        processed_launches = []
        
        for l in launches:
            launch = parse_launch_data(l)
            net = launch.get('net', '') or launch.get('date_start', '')
            dt = _get_parsed_dt(net)
            if dt:
                try:
                    # Cache the local time string
                    launch['_parsed_dt'] = dt
                    launch['localTime'] = dt.astimezone(timezone_obj).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    launch['localTime'] = 'TBD'
                    launch['_parsed_dt'] = None
            else:
                launch['localTime'] = 'TBD'
                launch['_parsed_dt'] = None
            processed_launches.append(launch)
        
        if event_type == 'upcoming':
            # Use the pre-parsed datetime for sorting and filtering
            launches_sorted = sorted(processed_launches, key=lambda x: x.get('_parsed_dt') or datetime.max.replace(tzinfo=pytz.UTC))
            
            today_launches = []
            this_week_launches = []
            later_launches = []
            
            for l in launches_sorted:
                dt = l.get('_parsed_dt')
                if not dt:
                    later_launches.append(l)
                    continue
                
                l_date = dt.astimezone(timezone_obj).date()
                if l_date == today:
                    today_launches.append(l)
                elif today < l_date <= this_week_end:
                    this_week_launches.append(l)
                elif l_date > this_week_end:
                    later_launches.append(l)
            
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
            launches_sorted = sorted(processed_launches, key=lambda x: x.get('_parsed_dt') or datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
            
            today_launches = []
            last_week_launches = []
            earlier_launches = []
            
            for l in launches_sorted:
                dt = l.get('_parsed_dt')
                if not dt:
                    earlier_launches.append(l)
                    continue
                
                l_date = dt.astimezone(timezone_obj).date()
                if l_date == today:
                    today_launches.append(l)
                elif last_week_start <= l_date < today:
                    last_week_launches.append(l)
                elif l_date < last_week_start:
                    earlier_launches.append(l)
            
            if today_launches:
                grouped.append({'group': "Today's Launches 🚀"})
                grouped.extend(today_launches)
            if last_week_launches:
                grouped.append({'group': 'Last Week'})
                grouped.extend(last_week_launches)
            if earlier_launches:
                grouped.append({'group': 'Earlier'})
                grouped.extend(earlier_launches)
    
    profiler.mark(f"group_event_data End (grouped count: {len(grouped)})")
    return grouped

LAUNCH_DESCRIPTIONS = [
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

def check_wifi_interface():
    """Check if WiFi interface is available and log status."""
    try:
        is_windows = platform.system() == 'Windows'
        if is_windows:
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True, timeout=5)
            if 'wlan' in result.stdout.lower() or 'wireless' in result.stdout.lower():
                logger.info("WiFi interface detected on Windows")
                return True
        else:
            try:
                result = subprocess.run(['nmcli', 'device', 'status'], capture_output=True, text=True, timeout=5)
                if 'wifi' in result.stdout.lower():
                    logger.info("WiFi interface detected on Linux via nmcli")
                    return True
            except:
                interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                for interface in interfaces:
                    try:
                        result = subprocess.run(['ip', 'link', 'show', interface], capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            logger.info(f"WiFi interface {interface} detected on Linux")
                            return True
                    except: continue
        logger.warning("No WiFi interface detected")
        return False
    except Exception as e:
        logger.error(f"Error checking WiFi interface: {e}")
        return False

def get_wifi_interface_info():
    """Get information about the WiFi interface for debugging."""
    try:
        is_windows = platform.system() == 'Windows'
        if is_windows:
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'], capture_output=True, text=True, timeout=5)
            return f"Windows WiFi Interfaces:\n{result.stdout}"
        else:
            interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
            info_lines = ["Linux Wireless Interfaces:"]
            for interface in interfaces:
                try:
                    ip_result = subprocess.run(['ip', 'addr', 'show', interface], capture_output=True, text=True, timeout=5)
                    if ip_result.returncode == 0:
                        info_lines.append(f"\n--- {interface} ---")
                        info_lines.append(ip_result.stdout.strip())
                        try:
                            iw_result = subprocess.run(['iwconfig', interface], capture_output=True, text=True, timeout=5)
                            info_lines.append("Wireless Info:\n" + iw_result.stdout.strip())
                        except: info_lines.append("Wireless Info: iwconfig not available")
                        try:
                            nm_result = subprocess.run(['nmcli', 'device', 'show', interface], capture_output=True, text=True, timeout=5)
                            info_lines.append("NetworkManager Info:\n" + nm_result.stdout.strip())
                        except: info_lines.append("NetworkManager Info: nmcli not available")
                except: continue
            return "\n".join(info_lines) if len(info_lines) > 1 else "No wireless interfaces found"
    except Exception as e:
        return f"Error getting WiFi interface info: {e}"

def get_wifi_debug_info():
    """Get comprehensive WiFi debugging information."""
    try:
        debug_info = ["=== WiFi Debug Information ==="]
        debug_info.append(f"Platform: {platform.system()} {platform.release()}")

        if platform.system() == 'Linux':
            for service in ['NetworkManager', 'wpa_supplicant']:
                try:
                    res = subprocess.run(['systemctl', 'status', service], capture_output=True, text=True, timeout=5)
                    debug_info.append(f"\n{service} Status:\n{res.stdout}")
                except: debug_info.append(f"\n{service} Status: Unable to check")

            try:
                res = subprocess.run(['nmcli', 'device', 'status'], capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nDevice Status:\n{res.stdout}")
            except: debug_info.append("\nDevice Status: nmcli not available")

            try:
                res = subprocess.run(['nmcli', 'device', 'wifi', 'list'], capture_output=True, text=True, timeout=10)
                debug_info.append(f"\nWiFi Networks:\n{res.stdout}")
            except: debug_info.append("\nWiFi Networks: Unable to scan")

            try:
                res = subprocess.run(['nmcli', 'connection', 'show', '--active'], capture_output=True, text=True, timeout=5)
                debug_info.append(f"\nActive Connections:\n{res.stdout}")
            except: debug_info.append("\nActive Connections: Unable to check")
        else:
            debug_info.append("\nDetailed debug info currently only supported on Linux.")

        return "\n".join(debug_info)
    except Exception as e:
        return f"Error getting WiFi debug info: {e}"

def start_update_script(script_path, branch="master"):
    """Start the update script in a detached process."""
    if not os.path.exists(script_path):
        return False, f"Update script not found at {script_path}"

    try:
        if platform.system() == 'Linux':
            log_path = '/tmp/spacex-dashboard-update.log'
            try:
                log_file = open(log_path, 'ab', buffering=0)
            except:
                log_file = subprocess.DEVNULL

            child_env = os.environ.copy()
            child_env['KEEP_APP_RUNNING'] = '1'

            proc = subprocess.Popen(
                ['/bin/bash', script_path, branch],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(script_path),
                env=child_env,
                start_new_session=True,
                close_fds=True
            )
            return True, {"pid": proc.pid, "log_path": log_path}
        else:
            subprocess.Popen(
                ['/bin/bash' if os.path.exists('/bin/bash') else 'bash', script_path, branch],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.path.dirname(script_path)
            )
            return True, {"pid": None, "log_path": None}
    except Exception as e:
        return False, str(e)

def generate_month_labels_for_days(year=None):
    """Generate month labels for daily data points."""
    if year is None:
        year = datetime.now(pytz.UTC).year
    labels = []
    for day in range(1, 367):
        try:
            date = datetime(year, 1, 1) + timedelta(days=day-1)
            labels.append(date.strftime('%b') if date.day == 1 else '')
        except ValueError:
            break
    return labels

def connect_to_wifi_nmcli(ssid, password=None, wifi_device=None):
    """Connect to WiFi using nmcli (Linux). Returns (success, error_or_output)."""
    if platform.system() != 'Linux':
        return False, "nmcli only supported on Linux"

    try:
        # Rescan
        rescan_cmd = ['nmcli', 'device', 'wifi', 'rescan']
        if wifi_device: rescan_cmd.extend(['ifname', wifi_device])
        subprocess.run(rescan_cmd, capture_output=True, timeout=10)
        time.sleep(4)

        # Connect
        import shlex
        if password:
            cmd = f'nmcli device wifi connect {shlex.quote(ssid)} password {shlex.quote(password)}'
        else:
            cmd = f'nmcli device wifi connect {shlex.quote(ssid)}'
        if wifi_device: cmd += f' ifname {wifi_device}'

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, result.stderr.strip()

        # Set autoconnect
        manage_nm_autoconnect(ssid)
        return True, result.stdout.strip()
    except Exception as e:
        return False, str(e)

def get_max_value_from_series(series):
    """Calculate the maximum value from a list of series data."""
    if not series: return 0
    all_vals = []
    # Handle both [{'values': [...]}, ...] and [{'value': ...}, ...]
    for s in series:
        if 'values' in s:
            all_vals.extend([float(v) for v in s['values']])
        elif 'value' in s:
            all_vals.append(float(s['value']))
    return int(max(all_vals)) if all_vals else 0

def is_launch_finished(status):
    """Check if a launch status indicates it has completed (Success or Failure)."""
    if not status:
        return False
    s = str(status).lower()
    return any(keyword in s for keyword in ['success', 'failure', 'successful', 'complete'])

def get_calendar_mapping(launch_data, tz_obj=None):
    """
    Generate a mapping of date strings (YYYY-MM-DD) to lists of launches.
    Extracted from Backend.launchesByDate to allow pre-computation during boot.
    """
    profiler.mark("get_calendar_mapping Start")
    mapping = {}
    if not launch_data:
        return mapping
        
    for l in launch_data.get('previous', []):
        d = l.get('date')
        t = l.get('time')
        if tz_obj and l.get('net'):
            try:
                dt_utc = _get_parsed_dt(l['net'])
                if dt_utc:
                    dt_local = dt_utc.astimezone(tz_obj)
                    d = dt_local.strftime('%Y-%m-%d')
                    t = dt_local.strftime('%H:%M:%S')
            except Exception:
                pass

        if d:
            if d not in mapping: mapping[d] = []
            l_typed = l.copy()
            l_typed['type'] = 'past'
            # Keep original date/time as UTC (from parse_launch_data)
            # Add local versions for UI display
            l_typed['localDate'] = d
            l_typed['localTime'] = d + " " + t
            mapping[d].append(l_typed)
            
    for l in launch_data.get('upcoming', []):
        d = l.get('date')
        t = l.get('time')
        if tz_obj and l.get('net'):
            try:
                dt_utc = _get_parsed_dt(l['net'])
                if dt_utc:
                    dt_local = dt_utc.astimezone(tz_obj)
                    d = dt_local.strftime('%Y-%m-%d')
                    t = dt_local.strftime('%H:%M:%S')
            except Exception:
                pass

        if d:
            if d not in mapping: mapping[d] = []
            l_typed = l.copy()
            l_typed['type'] = 'upcoming'
            # Keep original date/time as UTC (from parse_launch_data)
            # Add local versions for UI display
            l_typed['localDate'] = d
            l_typed['localTime'] = d + " " + t
            mapping[d].append(l_typed)
    profiler.mark(f"get_calendar_mapping End ({len(mapping)} dates)")
    _save_date_cache()
    return mapping

def get_next_launch_info(upcoming_launches, tz_obj):
    """Find and format the next upcoming launch."""
    current_time = datetime.now(pytz.UTC)
    valid_launches = []
    for l in upcoming_launches:
        if l.get('time') == 'TBD': continue
        try:
            lt_utc = _get_parsed_dt(l['net'])
            if not lt_utc: continue
            is_finished = is_launch_finished(l.get('status'))
            # Include future launches OR ongoing launches (not finished regardless of T0)
            if lt_utc > current_time or (lt_utc <= current_time and not is_finished):
                valid_launches.append(l)
        except Exception:
            continue
            
    if valid_launches:
        next_l = min(valid_launches, key=lambda x: _get_parsed_dt(x['net']) or datetime.max.replace(tzinfo=pytz.UTC))
        launch = next_l.copy()
        dt_utc = _get_parsed_dt(next_l['net'])
        if dt_utc:
            launch_datetime = dt_utc.astimezone(tz_obj)
            launch['local_date'] = launch_datetime.strftime('%Y-%m-%d')
            launch['local_time'] = launch_datetime.strftime('%H:%M:%S')
            return launch
    return None

def get_upcoming_launches_list(upcoming_launches, tz_obj, limit=10):
    """Sort and format a list of upcoming launches."""
    current_time = datetime.now(pytz.UTC)
    valid_launches = []
    for l in upcoming_launches:
        if l.get('time') == 'TBD': continue
        try:
            lt_utc = _get_parsed_dt(l['net'])
            if not lt_utc: continue
            is_finished = is_launch_finished(l.get('status'))
            # Include future launches OR ongoing launches (not finished regardless of T0)
            if lt_utc > current_time or (lt_utc <= current_time and not is_finished):
                valid_launches.append(l)
        except Exception:
            continue

    launches = []
    for l in sorted(valid_launches, key=lambda x: _get_parsed_dt(x['net']) or datetime.max.replace(tzinfo=pytz.UTC))[:limit]:
        launch = l.copy()
        dt_utc = _get_parsed_dt(l['net'])
        if dt_utc:
            launch_datetime = dt_utc.astimezone(tz_obj)
            launch['local_date'] = launch_datetime.strftime('%Y-%m-%d')
            launch['local_time'] = launch_datetime.strftime('%H:%M:%S')
            launches.append(launch)
    return launches

def get_closest_x_video_url(launch_data):
    """Find the X.com livestream URL of the launch closest to current time."""
    if not launch_data:
        logger.debug("get_closest_x_video_url: No launch data provided, returning empty URL")
        return ""

    current_time = datetime.now(pytz.UTC)
    previous = launch_data.get('previous', [])
    upcoming = launch_data.get('upcoming', [])

    all_launches = previous + upcoming
    closest_url = ""
    min_diff = float('inf')

    for launch in all_launches:
        # Prefer explicit x_video_url, but fallback to video_url if it's an X/Twitter link
        x_url = launch.get('x_video_url')
        if not x_url:
            v_url = launch.get('video_url', '')
            if v_url and ('x.com' in v_url.lower() or 'twitter.com' in v_url.lower()):
                x_url = v_url
        
        if not x_url:
            continue

        try:
            launch_net = _get_parsed_dt(launch['net'])
            if not launch_net:
                continue

            diff = abs((current_time - launch_net).total_seconds())
            
            # Prioritization:
            # 1. If it's very close to now (within 12 hours), it's likely the "Live" one we want.
            # 2. Upcoming launches with URLs are generally better candidates than old previous ones.
            # But for now, we'll stick to closest in time, but allow the fallback.
            
            if diff < min_diff:
                min_diff = diff
                closest_url = x_url
        except Exception:
            continue

    logger.debug(f"get_closest_x_video_url: Found URL: {closest_url}")
    return closest_url

def initialize_all_weather(locations_config):
    """Fetch initial weather for all configured locations."""
    return fetch_weather_for_all_locations(locations_config)

def get_best_wifi_reconnection_candidate(remembered_networks, visible_networks, nm_profiles=None):
    """
    Identify the best WiFi candidate for auto-reconnection.
    Priority: Visible remembered networks (most recent first) > NM profiles (if Linux)
    """
    # Build a set of visible SSIDs for fast lookup
    visible_ssids = {net.get('ssid') for net in visible_networks if net.get('ssid')}

    # 1. Filter remembered networks to only those currently visible and having passwords
    candidates = [n for n in remembered_networks if n.get('ssid') in visible_ssids and n.get('password')]

    if candidates:
        # Most recent first (assuming remembered_networks is sorted or has timestamps)
        return {'type': 'direct', 'ssid': candidates[0]['ssid'], 'password': candidates[0]['password']}

    # 2. If no direct matches with passwords, check NM profiles on Linux
    if nm_profiles:
        for n in remembered_networks:
            target_ssid = n.get('ssid')
            if not target_ssid: continue

            # Match by SSID or by name
            matched = next((p for p in nm_profiles if p.get('ssid') == target_ssid), None)
            if matched is None:
                matched = next((p for p in nm_profiles if p.get('name') == target_ssid), None)

            if matched:
                return {'type': 'nmcli', 'ssid': target_ssid, 'profile_name': matched['name']}

    return None

def calculate_chart_interval(max_value):
    """Calculate a dynamic interval for chart axes based on max value."""
    if max_value <= 0:
        return 1

    # Target 6-8 labels for good readability
    target_labels = 7
    rough_interval = max_value / target_labels

    # Round to nice numbers: 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, etc.
    nice_intervals = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]

    # Find the smallest nice interval that's >= rough_interval
    for interval in nice_intervals:
        if interval >= rough_interval:
            return interval

    # If we get here, rough_interval is very large, return the largest nice interval
    return nice_intervals[-1]

def filter_and_sort_wifi_networks(raw_networks):
    """Remove duplicates (preferring strongest signal) and sort by signal strength."""
    seen_ssids = {}
    for network in raw_networks or []:
        ssid = network.get('ssid')
        if ssid:
            prev = seen_ssids.get(ssid)
            try:
                current_signal = int(network.get('signal', -100))
                prev_signal = int(prev.get('signal', -100)) if prev else -100
                if prev is None or current_signal > prev_signal:
                    seen_ssids[ssid] = network
            except Exception:
                if prev is None: seen_ssids[ssid] = network

    return sorted(list(seen_ssids.values()), key=lambda x: int(x.get('signal', -100)), reverse=True)

def get_nmcli_profiles():
    """Fetch WiFi connection profiles from nmcli on Linux."""
    if platform.system() != 'Linux':
        return []

    try:
        nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=3)
        if nmcli_check.returncode != 0:
            return []

        list_conns = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,802-11-wireless.ssid', 'connection', 'show'],
                                    capture_output=True, text=True, timeout=5)
        if list_conns.returncode != 0:
            return []

        profiles = []
        for line in list_conns.stdout.strip().split('\n'):
            if not line: continue
            parts = line.split(':')
            if len(parts) >= 3 and parts[1].lower() == 'wifi':
                profiles.append({'name': parts[0], 'ssid': parts[2]})
        return profiles
    except Exception as e:
        logger.debug(f"Failed to fetch nmcli profiles: {e}")
        return []

def fetch_weather_for_all_locations(locations_config, active_location=None):
    """Fetch weather for all configured locations, prioritizing active location for performance."""
    profiler.mark("fetch_weather_for_all_locations Start")

    # Try loading from cache first
    try:
        cache = load_cache_from_file(CACHE_FILE_WEATHER)
        current_time = datetime.now(pytz.UTC)
        if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_WEATHER:
            logger.info("Using cached weather data for all locations")
            profiler.mark("fetch_weather_for_all_locations End (Cache Hit)")
            return cache['data']
    except Exception as e:
        logger.warning(f"Failed to load weather cache: {e}")

    # Check network connectivity
    if not test_network_connectivity():
        if cache and cache.get('data'):
            return cache['data']
        return {loc: {'temperature_c': (77 - 32) * 5/9, 'temperature_f': 77, 'wind_speed_ms': 5, 'wind_speed_kts': 9.7, 'wind_direction': 90, 'cloud_cover': 50} for loc in locations_config}

    try:
        emit_loader_status("Fetching global weather data…")
        
        if active_location and active_location in locations_config:
            # OPTIMIZATION: Prioritize active location to improve UI responsiveness
            logger.info(f"Optimization: Fetching weather only for active location: {active_location}")
            loc_data = locations_config[active_location]
            single_weather = fetch_weather(loc_data.get('lat'), loc_data.get('lon'), active_location)
            
            # Use cached data for other locations if available, otherwise use defaults
            weather_data = {}
            if cache and cache.get('data'):
                weather_data = cache['data'].copy()
            
            weather_data[active_location] = single_weather
            
            # Fill remaining missing locations with defaults
            for loc in locations_config:
                if loc not in weather_data:
                    weather_data[loc] = {'temperature_c': (77 - 32) * 5/9, 'temperature_f': 77, 'wind_speed_ms': 5, 'wind_speed_kts': 9.7, 'wind_direction': 90, 'cloud_cover': 50}
        else:
            # Full fetch via unified endpoint
            url = f"{LAUNCH_API_BASE_URL}/weather_all"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            weather_data = data.get('weather', {})
            
            # Post-process forecast data for each location
            for loc, loc_weather in weather_data.items():
                if 'forecast' in loc_weather and 'daily' in loc_weather['forecast']:
                    daily = loc_weather['forecast']['daily']
                    hourly = loc_weather['forecast'].get('hourly', {})
                    forecast_list = []
                    
                    times = daily.get('time', [])
                    max_temps_c = daily.get('temperature_2m_max', [])
                    min_temps_c = daily.get('temperature_2m_min', [])
                    codes = daily.get('weathercode', [])
                    
                    # Convert to Fahrenheit
                    max_temps = [c_to_f(c) for c in max_temps_c]
                    min_temps = [c_to_f(c) for c in min_temps_c]
                    
                    hourly_times = hourly.get('time', [])
                    hourly_temps_c = hourly.get('temperature_2m', [])
                    hourly_temps = [c_to_f(c) for c in hourly_temps_c]
                    # API documentation says windspeed_10m, but we'll check both for robustness
                    hourly_winds = hourly.get('windspeed_10m', hourly.get('wind_speed_10m', []))
                    hourly_dirs = hourly.get('winddirection_10m', [])
                    
                    for i in range(len(times)):
                        try:
                            dt = datetime.strptime(times[i], "%Y-%m-%d")
                            day_name = dt.strftime("%a")
                            
                            day_hourly_temps = []
                            day_hourly_winds = []
                            day_str = times[i]
                            
                            for h_idx, h_time in enumerate(hourly_times):
                                if h_time.startswith(day_str):
                                    day_hourly_temps.append(hourly_temps[h_idx])
                                    if h_idx < len(hourly_winds):
                                        day_hourly_winds.append(hourly_winds[h_idx])
                            
                            if not day_hourly_temps:
                                day_hourly_temps = [min_temps[i], max_temps[i]]
                            
                            # Calculate a representative wind for the day
                            if day_hourly_winds:
                                avg_wind = sum(day_hourly_winds) / len(day_hourly_winds)
                                # Find corresponding wind directions
                                day_hourly_dirs = []
                                for h_idx, h_time in enumerate(hourly_times):
                                    if h_time.startswith(day_str) and h_idx < len(hourly_dirs):
                                        day_hourly_dirs.append(hourly_dirs[h_idx])
                                avg_dir = sum(day_hourly_dirs) / len(day_hourly_dirs) if day_hourly_dirs else 0
                                wind_str = f"{int(avg_wind)}kt {int(avg_dir)}°"
                            else:
                                day_hourly_winds = [0, 0]
                                wind_str = "N/A"

                            forecast_list.append({
                                'day': day_name,
                                'temp_low': f"{int(min_temps[i])}°",
                                'temp_high': f"{int(max_temps[i])}°",
                                'condition': WEATHER_CODE_MAP.get(codes[i], "Unknown"),
                                'wind': wind_str,
                                'temps': day_hourly_temps,
                                'winds': day_hourly_winds
                            })
                        except Exception:
                            continue
                    
                    loc_weather['forecast_processed'] = forecast_list
        
        # Save to cache
        save_cache_to_file(CACHE_FILE_WEATHER, weather_data, datetime.now(pytz.UTC))
        logger.info(f"Fetched and cached weather for {len(weather_data)} locations")
        profiler.mark("fetch_weather_for_all_locations End (API Success)")
        return weather_data
    except Exception as e:
        logger.error(f"Failed to fetch weather from new API: {e}")
        if cache and cache.get('data'):
            return cache['data']
        return {loc: {'temperature_c': (77 - 32) * 5/9, 'temperature_f': 77, 'wind_speed_ms': 5, 'wind_speed_kts': 9.7, 'wind_direction': 90, 'cloud_cover': 50} for loc in locations_config}

def perform_full_dashboard_data_load(locations_config, status_callback=None, tz_obj=None, active_location=None):
    """Orchestrate parallel fetch of launches, narratives, and weather data."""
    profiler.mark("perform_full_dashboard_data_load Start")
    
    # State tracking for parallel updates
    status_state = {
        'launches': 'Pending',
        'weather': 'Pending',
        'narratives': 'Pending'
    }

    def _emit_combined_status():
        if not status_callback:
            return
            
        # Prioritize showing what's currently being worked on
        if status_state['launches'] == 'Loading':
            msg = "Fetching SpaceX launch data…"
        elif status_state['weather'] == 'Loading':
            msg = "Getting live weather for locations…"
        elif status_state['narratives'] == 'Loading':
            msg = "Retrieving mission narratives…"
        elif all(s == 'Complete' for s in status_state.values()):
            msg = "Data loading complete"
        else:
            msg = "Initializing dashboard data…"
            
        try:
            status_callback(msg)
        except:
            pass

    def _emit(msg):
        if status_callback:
            try: status_callback(msg)
            except: pass

    status_state['launches'] = 'Loading'
    _emit_combined_status()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Launch data
        def _fetch_l():
            profiler.mark("Thread: Fetch Launches Start")
            try:
                res = fetch_launches()
                status_state['launches'] = 'Complete'
                _emit_combined_status()
                profiler.mark("Thread: Fetch Launches End")
                return res
            except:
                status_state['launches'] = 'Failed'
                _emit_combined_status()
                profiler.mark("Thread: Fetch Launches Failed")
                return {'previous': [], 'upcoming': []}

        # Weather data
        def _fetch_w():
            profiler.mark("Thread: Fetch Weather Start")
            status_state['weather'] = 'Loading'
            _emit_combined_status()
            # Pass active_location to fetch_weather_for_all_locations for optimization
            res = fetch_weather_for_all_locations(locations_config, active_location)
            status_state['weather'] = 'Complete'
            _emit_combined_status()
            profiler.mark("Thread: Fetch Weather End")
            return res

        # Narratives
        def _fetch_n():
            profiler.mark("Thread: Fetch Narratives Start")
            status_state['narratives'] = 'Loading'
            _emit_combined_status()
            res = fetch_narratives()
            status_state['narratives'] = 'Complete'
            _emit_combined_status()
            profiler.mark("Thread: Fetch Narratives End")
            return res

        f_launch = executor.submit(_fetch_l)
        f_weather = executor.submit(_fetch_w)
        f_narratives = executor.submit(_fetch_n)

        profiler.mark("Waiting for data threads...")
        launch_data = f_launch.result()
        profiler.mark("Launch data received")
        weather_data = f_weather.result()
        profiler.mark("Weather data received")
        narratives = f_narratives.result()
        profiler.mark("Narratives received")
        
        # Enrich narratives with launch data now that both are available
        narratives = fetch_narratives(launch_data)

    profiler.mark("perform_full_dashboard_data_load End")
    _emit("Finalizing dashboard UI…")
    
    # Pre-compute calendar mapping while still in the background
    calendar_mapping = get_calendar_mapping(launch_data, tz_obj=tz_obj)
    
    return launch_data, weather_data, narratives, calendar_mapping

def get_rpi_config_resolution():
    """Attempt to detect resolution from Raspberry Pi boot config."""
    if platform.system() != 'Linux':
        return None, None
        
    config_paths = [
        "/boot/firmware/config.txt",
        "/boot/config.txt"
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            try:
                width, height = None, None
                with open(path, 'r') as f:
                    content = f.read()
                    
                # Look for max_framebuffer_width/height
                w_match = re.search(r'^max_framebuffer_width=(\d+)', content, re.MULTILINE)
                h_match = re.search(r'^max_framebuffer_height=(\d+)', content, re.MULTILINE)
                
                if w_match: width = int(w_match.group(1))
                if h_match: height = int(h_match.group(1))
                
                # If width not found via max_framebuffer_width, check hdmi_timings
                if not width:
                    # hdmi_timings=width 0 h_front_porch h_sync h_back_porch height ...
                    timings_match = re.search(r'^hdmi_timings=(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)', content, re.MULTILINE)
                    if timings_match:
                        width = int(timings_match.group(1))
                        if not height:
                            height = int(timings_match.group(2))
                            
                if width and height:
                    return width, height
                if width:
                    return width, None
                if height:
                    return None, height
            except Exception as e:
                logger.debug(f"Failed to read {path}: {e}")
                
    return None, None

def setup_dashboard_environment():
    """Set environment variables for Qt and hardware acceleration."""
    # Check if flags are already set (e.g. by .xsession or systemd)
    # If so, we avoid overwriting them to preserve critical stability flags
    if "QTWEBENGINE_CHROMIUM_FLAGS" in os.environ:
        logger.info("setup_dashboard_environment: QTWEBENGINE_CHROMIUM_FLAGS already set, respecting environment.")
    elif platform.system() == 'Windows':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
            "--disable-web-security --allow-running-insecure-content "
            "--disable-gpu-sandbox --disable-software-rasterizer "
            "--disable-gpu-driver-bug-workarounds --no-sandbox "
            "--autoplay-policy=no-user-gesture-required "
            "--no-user-gesture-required-for-fullscreen "
            "--disable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
        )
    elif platform.system() == 'Linux':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-webgl "
            "--disable-gpu-sandbox --no-sandbox "
            "--disable-dev-shm-usage --enable-accelerated-video-decode "
            "--enable-gpu-memory-buffer-video-frames --enable-accelerated-2d-canvas "
            "--enable-gpu-rasterization --enable-zero-copy "
            "--enable-native-gpu-memory-buffers --enable-features=VaapiVideoDecoder "
            "--disable-web-security --allow-running-insecure-content "
            "--gpu-testing-vendor-id=0xFFFF --gpu-testing-device-id=0xFFFF "
            "--disable-gpu-driver-bug-workarounds "
            "--memory-pressure-off --max_old_space_size=2048 --memory-reducer "
            "--gpu-memory-buffer-size-mb=512 --max-tiles-for-interest-area=512 "
            "--num-raster-threads=2 --disable-background-timer-throttling "
            "--disable-renderer-backgrounding --disable-backgrounding-occluded-windows "
            "--autoplay-policy=no-user-gesture-required "
            "--no-user-gesture-required-for-fullscreen "
            "--disable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
        )
    else:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu --enable-webgl --disable-web-security"

    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    os.environ["QSG_RHI_BACKEND"] = "gl"

    # High DPI Scaling support
    # Detect physical resolution from config file if environment variables are missing
    detected_w, detected_h = get_rpi_config_resolution()
    
    # Priority for determining the default scale factor:
    # 1. DASHBOARD_WIDTH == 1480 (explicitly small display) -> 1.0
    # 2. Config file width/height matching small display -> 1.0
    # 3. Windows -> 1.0
    # 4. DASHBOARD_WIDTH == 3840 (explicitly large display) -> 2.0
    # 5. Config file matching large display -> 2.0
    # 6. Default fallback for Linux -> 2.0
    
    if platform.system() == 'Windows':
        default_scale = "1.0"
    elif os.environ.get("DASHBOARD_WIDTH") == "1480":
        default_scale = "1.0"
    elif detected_w == 1480 or detected_h == 320:
        default_scale = "1.0"
    elif os.environ.get("DASHBOARD_WIDTH") == "3840":
        default_scale = "2.0"
    elif detected_w == 3840 or detected_h == 1100:
        default_scale = "2.0"
    elif os.environ.get("DASHBOARD_WIDTH") == "2560":
        default_scale = "1.333"
    elif detected_w == 2560 or detected_h == 734:
        default_scale = "1.333"
    else:
        default_scale = "2.0"

    dashboard_scale = os.environ.get("DASHBOARD_SCALE", default_scale)
    
    # Set QT_SCALE_FACTOR to ensure consistent scaling across all displays
    os.environ["QT_SCALE_FACTOR"] = dashboard_scale

    if platform.system() == 'Linux':
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        os.environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl"
        os.environ.setdefault("MESA_GL_VERSION_OVERRIDE", "3.3")
        os.environ.setdefault("MESA_GLSL_VERSION_OVERRIDE", "330")

def setup_dashboard_logging(module_file):
    """Initialize logging with file and console handlers."""
    try:
        log_dir = os.path.join(os.path.dirname(module_file), '..', 'docs')
        if not os.path.exists(log_dir):
            try: os.makedirs(log_dir, exist_ok=True)
            except: log_dir = os.path.dirname(module_file)

        log_file = os.path.join(log_dir, 'app.log')
        if not os.access(os.path.dirname(log_file), os.W_OK):
            log_file = os.path.join(os.path.dirname(module_file), 'app.log')

        # Print intention first to verify path logic
        print(f"ATTEMPTING TO LOG TO: {os.path.abspath(log_file)}")

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )
        # Log the log path immediately to stdout and logger
        print(f"LOGGING SETUP COMPLETE. File: {os.path.abspath(log_file)}")
        logger.info(f"LOGGING INITIALIZED: {os.path.abspath(log_file)}")
        return os.path.abspath(log_file)
    except Exception as e:
        # Fallback to console only if file logging fails
        print(f"ERROR SETTING UP LOGGING: {e}", file=sys.stderr)
        logging.basicConfig(level=logging.INFO, force=True)
        return None

def format_qt_message(mode, context, message):
    """Format Qt/QML messages for logging, applying filters and sanitation."""
    try:
        level_name = mode.name if hasattr(mode, 'name') else str(mode)
    except Exception:
        level_name = str(mode)

    location = f" {context.file}:{context.line}" if context and context.file and context.line else ""
    try:
        sanitized = str(message).encode('utf-8', errors='replace').decode('utf-8')
        if "current style does not support customization" in sanitized:
            return None
        return f"[QT-{level_name}]{location} {sanitized}"
    except Exception:
        return f"[QT-{level_name}]{location} <message encoding failed>"

def get_launch_tray_visibility_state(launch_data, mode):
    """Determine if the launch tray should be visible based on launch data."""
    if mode != 'spacex':
        return False

    upcoming = launch_data.get('upcoming')
    if not upcoming:
        return False

    current_time = datetime.now(pytz.UTC)
    try:
        # Sort upcoming launches by time
        upcoming_sorted = sorted(
            [l for l in upcoming if l.get('time') != 'TBD' and l.get('net')],
            key=lambda x: _get_parsed_dt(x.get('net')) or datetime.min.replace(tzinfo=pytz.UTC)
        )
    except Exception:
        upcoming_sorted = upcoming

    for launch in upcoming_sorted:
        try:
            launch_time = _get_parsed_dt(launch.get('net'))
            if not launch_time: continue
        except Exception:
            continue

        # Pre‑launch window: within next hour
        if current_time <= launch_time <= current_time + timedelta(hours=1):
            return True

        # Ongoing/post‑T0: keep tray visible if it just launched and isn't finished yet
        is_finished = is_launch_finished(launch.get('status'))
        if launch_time <= current_time and not is_finished:
            return True

    return False

def get_countdown_string(launch_data, mode, next_launch, tz_obj):
    """Generate a formatted countdown string for the dashboard."""
    if mode == 'spacex':
        upcoming = launch_data.get('upcoming', [])
        try:
            # Sort upcoming launches by time
            upcoming_sorted = sorted(
                [l for l in upcoming if l.get('time') != 'TBD' and l.get('net')],
                key=lambda x: _get_parsed_dt(x.get('net')) or datetime.min.replace(tzinfo=pytz.UTC)
            )
        except Exception:
            upcoming_sorted = upcoming

        now_utc = datetime.now(pytz.UTC)
        # Check for ongoing/just-launched (not finished regardless of T0)
        for l in upcoming_sorted:
            try:
                lt_utc = _get_parsed_dt(l.get('net'))
                if not lt_utc: continue
            except Exception:
                continue
            
            is_finished = is_launch_finished(l.get('status'))
            if lt_utc <= now_utc and not is_finished:
                delta = datetime.now(tz_obj) - lt_utc.astimezone(tz_obj)
                total_seconds = int(max(delta.total_seconds(), 0))
                days, rem = divmod(total_seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, seconds = divmod(rem, 60)
                return f"T+ {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"

        # Fallback to T- for next launch
        if not next_launch:
            return "No upcoming launches"
        try:
            launch_time = _get_parsed_dt(next_launch.get('net'))
            if launch_time:
                launch_time = launch_time.astimezone(tz_obj)
                current_time = datetime.now(tz_obj)
                delta = launch_time - current_time
                total_seconds = int(max(delta.total_seconds(), 0))
                days, rem = divmod(total_seconds, 86400)
                hours, rem = divmod(rem, 3600)
                minutes, seconds = divmod(rem, 60)
                return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
            else:
                return "T- TBD"
        except Exception:
            return "T- Error"

def get_countdown_breakdown(launch_data, mode, next_launch, tz_obj):
    """Generate a breakdown of the countdown for the dashboard tray."""
    now_utc = datetime.now(pytz.UTC)
    target_time = None
    is_t_plus = False

    if mode == 'spacex':
        upcoming = launch_data.get('upcoming', [])
        try:
            # Sort upcoming launches by time
            upcoming_sorted = sorted(
                [l for l in upcoming if l.get('time') != 'TBD' and l.get('net')],
                key=lambda x: _get_parsed_dt(x.get('net')) or datetime.min.replace(tzinfo=pytz.UTC)
            )
        except Exception:
            upcoming_sorted = upcoming

        # Check for ongoing/just-launched (not finished regardless of T0)
        for l in upcoming_sorted:
            try:
                lt_utc = _get_parsed_dt(l.get('net'))
                if not lt_utc: continue
            except Exception:
                continue
            
            is_finished = is_launch_finished(l.get('status'))
            if lt_utc <= now_utc and not is_finished:
                target_time = lt_utc
                is_t_plus = True
                break

    if not target_time and next_launch:
        try:
            target_time = _get_parsed_dt(next_launch.get('net'))
        except Exception:
            pass

    if not target_time:
        return {
            'days': '0', 'hours': '00', 'minutes': '00', 'seconds': '00', 'milliseconds': '000',
            'prefix': 'T-', 'label': 'TBD'
        }

    target_time_tz = target_time.astimezone(tz_obj)
    current_time_tz = datetime.now(tz_obj)
    
    if is_t_plus:
        delta = current_time_tz - target_time_tz
        prefix = 'T+'
    else:
        delta = target_time_tz - current_time_tz
        prefix = 'T-'

    total_seconds = max(delta.total_seconds(), 0)
    days, rem = divmod(int(total_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    # Use fractional seconds to get precise milliseconds
    milliseconds = int((total_seconds - int(total_seconds)) * 1000)
    # Alternatively, use delta.microseconds if total_seconds was calculated from delta
    # milliseconds = int(delta.microseconds / 1000)

    return {
        'days': str(days),
        'hours': f"{hours:02d}",
        'minutes': f"{minutes:02d}",
        'seconds': f"{seconds:02d}",
        'milliseconds': f"{milliseconds:03d}",
        'prefix': prefix,
        'label': 'LIFTOFF' if is_t_plus else 'LAUNCH'
    }

def get_update_progress_summary(log_path):
    """Read the last few lines of the update log to provide a status update."""
    if not log_path or not os.path.exists(log_path):
        return "Preparing update…"
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        if lines:
            tail_lines = lines[-15:]
            tail = "\n".join([ln.rstrip() for ln in tail_lines]).strip()
            return tail if tail else "Updating…"
    except Exception:
        pass
    return "Updating…"

def perform_bootstrap_diagnostics(src_dir, wifi_connected_state=True, skip_update_check=False):
    """Perform bootstrap network and update checks. Update check can be skipped to avoid boot delay."""
    profiler.mark("perform_bootstrap_diagnostics Start")
    connectivity_result = test_network_connectivity()
    update_available = False
    current_info = {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}
    latest_info = {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}

    try:
        current_info = get_git_version_info(src_dir) or current_info
    except: pass

    if connectivity_result and not skip_update_check:
        try:
            current_hash = current_info.get('hash', '')
            update_available, latest_info = check_github_for_updates(current_hash)
            latest_info = latest_info or current_info
        except: pass

    profiler.mark("perform_bootstrap_diagnostics End")
    return connectivity_result, update_available, current_info, latest_info

def disconnect_from_wifi(wifi_interface=None):
    """Disconnect from the current WiFi network on Windows or Linux."""
    try:
        is_windows = platform.system() == 'Windows'
        if is_windows:
            subprocess.run(['netsh', 'wlan', 'disconnect'], capture_output=True, timeout=10)
            return True, "Disconnected"
        else:
            # Linux: try nmcli first
            try:
                result = subprocess.run(['nmcli', 'device', 'disconnect', 'wifi'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return True, "Disconnected (nmcli)"
            except: pass

            # Fallback for Linux
            if not wifi_interface: wifi_interface = get_wifi_interface()
            try:
                # Try to use nmcli to disconnect the device specifically
                subprocess.run(['nmcli', 'device', 'disconnect', wifi_interface], capture_output=True, timeout=5)
                return True, "Disconnected (device fallback)"
            except Exception as e:
                return False, str(e)
    except Exception as e:
        return False, str(e)

def bring_up_nm_connection(profile_name):
    """Bring up a specific NetworkManager connection profile (Linux)."""
    if platform.system() != 'Linux':
        return False, "Not on Linux"
    try:
        res = subprocess.run(['nmcli', 'connection', 'up', 'id', profile_name], capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            return True, res.stdout.strip()
        return False, res.stderr.strip()
    except Exception as e:
        return False, str(e)


def load_remembered_networks():
    """Load remembered networks from the JSON cache file."""
    if not os.path.exists(REMEMBERED_NETWORKS_FILE):
        return []
    try:
        with open(REMEMBERED_NETWORKS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load remembered networks: {e}")
        return []

def save_remembered_networks(networks):
    """Save the list of remembered networks to the JSON cache file."""
    try:
        os.makedirs(os.path.dirname(REMEMBERED_NETWORKS_FILE), exist_ok=True)
        with open(REMEMBERED_NETWORKS_FILE, 'w') as f:
            json.dump(networks, f, indent=4)
        logger.info(f"Saved {len(networks)} remembered networks to {REMEMBERED_NETWORKS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save remembered networks: {e}")
        return False

def load_last_connected_network():
    """Load the last connected network SSID from the JSON cache file."""
    if not os.path.exists(LAST_CONNECTED_NETWORK_FILE):
        return None
    try:
        with open(LAST_CONNECTED_NETWORK_FILE, 'r') as f:
            data = json.load(f)
            return data.get('ssid')
    except Exception as e:
        logger.error(f"Failed to load last connected network: {e}")
        return None

def save_last_connected_network(ssid):
    """Save the last connected network SSID to the JSON cache file."""
    try:
        os.makedirs(os.path.dirname(LAST_CONNECTED_NETWORK_FILE), exist_ok=True)
        with open(LAST_CONNECTED_NETWORK_FILE, 'w') as f:
            json.dump({'ssid': ssid, 'timestamp': time.time()}, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Failed to save last connected network: {e}")
        return False

def sync_remembered_networks(networks, ssid, timestamp, password=None):
    """Update a list of remembered networks with the latest connection info and return sorted list."""
    if not networks: networks = []
    found = False
    for n in networks:
        if n.get('ssid') == ssid:
            n['last_connected'] = timestamp
            if password: n['password'] = password
            found = True
            break
    if not found:
        networks.append({'ssid': ssid, 'password': password, 'last_connected': timestamp})

    # Sort by recency
    networks.sort(key=lambda x: x.get('last_connected', 0), reverse=True)
    return networks

def remove_nm_connection(ssid_or_name):
    """Delete a NetworkManager connection profile by SSID or Name (Linux)."""
    if platform.system() != 'Linux':
        return False, "Not on Linux"
    try:
        # First, try to find a connection matching the SSID or name
        result = subprocess.run(['nmcli', '-t', '-f', 'NAME,802-11-wireless.ssid', 'connection', 'show'],
                              capture_output=True, text=True, timeout=5)

        target_name = None
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if not line: continue
                parts = line.split(':')
                if len(parts) >= 2:
                    name, ssid = parts[0], parts[1]
                    if ssid == ssid_or_name or name == ssid_or_name:
                        target_name = name
                        break

        if not target_name:
            # Fallback to assuming the input IS the name
            target_name = ssid_or_name

        logger.info(f"Attempting to delete NM connection profile: '{target_name}'")
        del_res = subprocess.run(['nmcli', 'connection', 'delete', 'id', target_name],
                                capture_output=True, text=True, timeout=10)

        if del_res.returncode == 0:
            logger.info(f"Successfully deleted NM profile: {target_name}")
            return True, del_res.stdout.strip()
        else:
            logger.warning(f"Failed to delete NM profile: {del_res.stderr.strip()}")
            return False, del_res.stderr.strip()
    except Exception as e:
        logger.error(f"Error removing NM connection: {e}")
        return False, str(e)
