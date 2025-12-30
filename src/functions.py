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
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import numpy as np
import pytz
import requests
import concurrent.futures
from dateutil.parser import parse
from track_generator import generate_track_map
from cryptography.fernet import Fernet
import http.server
import socketserver
import threading
import pandas as pd
from plotly_charts import (
    generate_f1_standings_chart,
    generate_f1_telemetry_chart,
    generate_f1_weather_chart,
    generate_f1_positions_chart,
    generate_f1_laps_chart
)

logger = logging.getLogger(__name__)

__all__ = [
    # status helpers
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
    "fetch_f1_data",
    "fetch_weather",
    # parsing/math helpers
    "parse_metar",
    "rotate",
    # exported constants
    "CACHE_REFRESH_INTERVAL_PREVIOUS",
    "CACHE_REFRESH_INTERVAL_UPCOMING",
    "CACHE_REFRESH_INTERVAL_F1",
    "CACHE_REFRESH_INTERVAL_F1_SCHEDULE",
    "CACHE_REFRESH_INTERVAL_F1_STANDINGS",
    "TRAJECTORY_CACHE_FILE",
    "CACHE_FILE_PREVIOUS",
    "CACHE_FILE_PREVIOUS_BACKUP",
    "CACHE_FILE_UPCOMING",
    "CACHE_DIR_F1",
    "CACHE_FILE_F1_SCHEDULE",
    "CACHE_FILE_F1_DRIVERS",
    "CACHE_FILE_F1_CONSTRUCTORS",
    "RUNTIME_CACHE_FILE_PREVIOUS",
    "RUNTIME_CACHE_FILE_UPCOMING",
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
    "get_country_flag_url",
    "connect_to_wifi_worker",
    "get_launch_trends_series",
    "generate_f1_chart_html",
    "get_launch_trajectory_data",
    "group_event_data",
    "LAUNCH_DESCRIPTIONS",
    "normalize_team_name",
    "check_wifi_interface",
    "get_wifi_interface_info",
    "get_wifi_debug_info",
    "start_update_script",
    "get_f1_driver_points_chart",
    "get_f1_constructor_points_chart",
    "get_f1_driver_points_series",
    "get_f1_constructor_points_series",
    "get_f1_driver_standings_over_time_series",
    "get_empty_chart_html",
    "get_empty_chart_url",
    "generate_month_labels_for_days",
    "connect_to_wifi_nmcli",
    "get_max_value_from_series",
    "get_next_launch_info",
    "get_upcoming_launches_list",
    "get_next_race_info",
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
CACHE_REFRESH_INTERVAL_PREVIOUS = 86400  # 24 hours for historical data
CACHE_REFRESH_INTERVAL_UPCOMING = 3600   # 1 hour for upcoming launches
CACHE_REFRESH_INTERVAL_F1 = 3600         # 1 hour for F1 data
TRAJECTORY_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'cache', 'trajectory_cache.json')
CACHE_FILE_PREVIOUS = os.path.join(os.path.dirname(__file__), '..', 'cache', 'previous_launches_cache.json')
CACHE_FILE_PREVIOUS_BACKUP = os.path.join(os.path.dirname(__file__), '..', 'cache', 'previous_launches_cache_backup.json')
CACHE_FILE_UPCOMING = os.path.join(os.path.dirname(__file__), '..', 'cache', 'upcoming_launches_cache.json')

# Cache for F1 data - persistent location outside git repo
CACHE_DIR_F1 = os.path.expanduser('~/.cache/spacex-dashboard')  # Persistent cache directory
os.makedirs(CACHE_DIR_F1, exist_ok=True)
CACHE_FILE_F1_SCHEDULE = os.path.join(CACHE_DIR_F1, 'f1_schedule_cache.json')
CACHE_FILE_F1_DRIVERS = os.path.join(CACHE_DIR_F1, 'f1_drivers_cache.json')
CACHE_FILE_F1_CONSTRUCTORS = os.path.join(CACHE_DIR_F1, 'f1_constructors_cache.json')

# Runtime (user) cache paths for SpaceX launches. Keep the git-seeded repo cache intact
# and write incremental updates to the persistent user cache.
RUNTIME_CACHE_FILE_PREVIOUS = os.path.join(CACHE_DIR_F1, 'previous_launches_cache.json')
RUNTIME_CACHE_FILE_UPCOMING = os.path.join(CACHE_DIR_F1, 'upcoming_launches_cache.json')
RUNTIME_CACHE_FILE_NARRATIVES = os.path.join(CACHE_DIR_F1, 'narratives_cache.json')

# Different refresh intervals for different F1 data types
CACHE_REFRESH_INTERVAL_F1_SCHEDULE = 86400  # 24 hours for race schedule (rarely changes)
CACHE_REFRESH_INTERVAL_F1_STANDINGS = 3600  # 1 hour for standings (updates frequently)
CACHE_REFRESH_INTERVAL_NARRATIVES = 3600    # 1 hour for narratives

# WiFi and Encryption paths
# WiFi and Encryption paths - Updated to use persistent cache directory
WIFI_KEY_FILE = os.path.join(CACHE_DIR_F1, 'wifi_key.bin')
REMEMBERED_NETWORKS_FILE = os.path.join(CACHE_DIR_F1, 'remembered_networks.json')
LAST_CONNECTED_NETWORK_FILE = os.path.join(CACHE_DIR_F1, 'last_connected_network.json')
THEME_SETTINGS_FILE = os.path.join(CACHE_DIR_F1, 'theme_settings.json')

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
                cache_data['timestamp'] = datetime.fromisoformat(cache_data['timestamp']).replace(tzinfo=pytz.UTC)
                return cache_data
    except (OSError, PermissionError, json.JSONDecodeError, ValueError) as e:
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


# Helpers for launch caches that prefer the runtime cache but fall back to the git seed
def load_launch_cache(kind: str):
    """Load a launch cache for kind in {'previous','upcoming'}.
    Prefer the runtime cache in ~/.cache; fall back to the git-seeded cache under repo /cache.
    Returns a dict: {'data': list, 'timestamp': datetime} or None.
    """
    try:
        if kind not in ('previous', 'upcoming'):
            raise ValueError("kind must be 'previous' or 'upcoming'")
        runtime_path = RUNTIME_CACHE_FILE_PREVIOUS if kind == 'previous' else RUNTIME_CACHE_FILE_UPCOMING
        seed_path = CACHE_FILE_PREVIOUS if kind == 'previous' else CACHE_FILE_UPCOMING

        data = load_cache_from_file(runtime_path)
        if data and isinstance(data.get('data'), list):
            logger.info(f"Loaded {kind} launches from runtime cache: {runtime_path}")
            return data

        logger.info(f"Runtime {kind} cache unavailable or invalid; falling back to seed cache: {seed_path}")
        return load_cache_from_file(seed_path)
    except Exception as e:
        logger.warning(f"Failed to load {kind} launch cache (runtime/seed): {e}")
        return None


def save_launch_cache(kind: str, data_list: list, timestamp=None):
    """Save launches to runtime cache only (keep seed intact)."""
    try:
        if kind not in ('previous', 'upcoming'):
            raise ValueError("kind must be 'previous' or 'upcoming'")
        path = RUNTIME_CACHE_FILE_PREVIOUS if kind == 'previous' else RUNTIME_CACHE_FILE_UPCOMING
        ts = timestamp or datetime.now(pytz.UTC)
        save_cache_to_file(path, data_list, ts)
        logger.info(f"Saved {len(data_list)} {kind} launches to runtime cache: {path}")
    except Exception as e:
        logger.warning(f"Failed to save {kind} launch cache: {e}")


def parse_metar(raw_metar):
    """
    Parse METAR string to extract weather data
    Returns dict with temperature_c, temperature_f, wind_speed_ms, wind_speed_kts, wind_direction, cloud_cover
    """
    import re

    # Default values
    temperature_c = 25
    wind_speed_kts = 0
    wind_direction = 0
    cloud_cover = 0

    try:
        # Extract temperature (format: 25/20 where first is temp, second is dewpoint)
        temp_match = re.search(r'(\d{1,3})/', raw_metar)
        if temp_match:
            temperature_c = int(temp_match.group(1))
            # Convert M (minus) prefix for negative temperatures
            if raw_metar[temp_match.start()-1] == 'M':
                temperature_c = -temperature_c

        # Extract wind (format: 12010KT or 12010G15KT)
        wind_match = re.search(r'(\d{3})(\d{2,3})(?:G\d{2,3})?KT', raw_metar)
        if wind_match:
            wind_direction = int(wind_match.group(1))
            wind_speed_kts = int(wind_match.group(2))

        # Estimate cloud cover based on cloud types
        if 'SKC' in raw_metar or 'CLR' in raw_metar:
            cloud_cover = 0  # Clear
        elif 'FEW' in raw_metar:
            cloud_cover = 25  # Few clouds
        elif 'SCT' in raw_metar:
            cloud_cover = 50  # Scattered
        elif 'BKN' in raw_metar:
            cloud_cover = 75  # Broken
        elif 'OVC' in raw_metar:
            cloud_cover = 100  # Overcast
        else:
            cloud_cover = 50  # Default to partly cloudy if no cloud info

    except Exception as e:
        logger.warning(f"Error parsing METAR data '{raw_metar}': {e}")

    # Convert to required format
    temperature_f = temperature_c * 9 / 5 + 32
    wind_speed_ms = wind_speed_kts * 0.514444  # Convert knots to m/s

    return {
        'temperature_c': temperature_c,
        'temperature_f': temperature_f,
        'wind_speed_ms': wind_speed_ms,
        'wind_speed_kts': wind_speed_kts,
        'wind_direction': wind_direction,
        'cloud_cover': cloud_cover
    }


def rotate(xy, *, angle):
    """Rotate an array of 2D points by angle (radians) using a standard rotation matrix."""
    rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                        [-np.sin(angle), np.cos(angle)]])
    return np.matmul(xy, rot_mat)


# --- System/network helpers moved from app.py ---
def check_wifi_status():
    """Check WiFi connection status and return (connected, ssid) tuple"""
    try:
        is_windows = platform.system() == 'Windows'
        logger.info(f"BOOT: Checking WiFi status on {platform.system()} platform")

        if is_windows:
            logger.debug("BOOT: Using Windows netsh command to check WiFi status")
            # Check WiFi interface status using Windows commands
            result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                  capture_output=True, text=True, timeout=5)

            logger.debug(f"BOOT: netsh return code: {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"BOOT: netsh command failed with return code {result.returncode}")
                logger.debug(f"BOOT: netsh stderr: {result.stderr}")

            connected = False
            current_ssid = ""

            logger.debug("BOOT: Parsing netsh output...")
            for line in result.stdout.split('\n'):
                line = line.strip()
                logger.debug(f"BOOT: netsh line: '{line}'")

                if 'State' in line and 'connected' in line.lower():
                    connected = True
                    logger.info("BOOT: Windows WiFi state shows CONNECTED")

                if 'SSID' in line and 'BSSID' not in line:
                    ssid_match = re.search(r'SSID\s*:\s*(.+)', line)
                    if ssid_match:
                        current_ssid = ssid_match.group(1).strip()
                        logger.info(f"BOOT: Windows WiFi SSID found: '{current_ssid}'")

            logger.info(f"BOOT: Windows WiFi check result - Connected: {connected}, SSID: '{current_ssid}'")
            return connected, current_ssid
        else:
            logger.debug("BOOT: Using Linux WiFi checking methods")
            # Enhanced Linux WiFi status checking with multiple methods
            connected = False
            current_ssid = ""

            # Method 1: Try nmcli first (most reliable on modern Linux)
            logger.debug("BOOT: Trying nmcli connection show --active...")
            try:
                nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=3)
                if nmcli_check.returncode == 0:
                    # Get active wifi connections
                    result = subprocess.run(['nmcli', '-t', '-f', 'TYPE,SSID,DEVICE', 'connection', 'show', '--active'],
                                          capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            if not line: continue
                            parts = line.split(':')
                            if len(parts) >= 3 and parts[0].lower() == '802-11-wireless':
                                connected = True
                                current_ssid = parts[1]
                                logger.info(f"BOOT: Linux WiFi connected via nmcli (active connection): '{current_ssid}'")
                                break
                    
                    if not connected:
                        # Fallback to device status if active connection check failed
                        logger.debug("BOOT: Trying nmcli device status fallback...")
                        result = subprocess.run(['nmcli', 'device', 'status'],
                                              capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                parts = line.split()
                                if len(parts) >= 4 and parts[1].lower() == 'wifi' and parts[2].lower() == 'connected':
                                    connected = True
                                    # Try to get SSID for this device
                                    dev = parts[0]
                                    ssid_res = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'device', 'wifi', 'list', 'ifname', dev],
                                                            capture_output=True, text=True, timeout=5)
                                    if ssid_res.returncode == 0:
                                        for sline in ssid_res.stdout.split('\n'):
                                            if sline.startswith('yes:'):
                                                current_ssid = sline.split(':', 1)[1].strip()
                                                break
                                    logger.info(f"BOOT: Linux WiFi connected via nmcli device status: '{current_ssid}'")
                                    break
            except Exception as e:
                logger.warning(f"BOOT: nmcli status check encountered error: {e}")

            # Method 2: Fallback to /proc/net/wireless or iwgetid if nmcli failed
            if not connected:
                logger.debug("BOOT: Trying iwgetid fallback...")
                try:
                    iw_res = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=3)
                    if iw_res.returncode == 0:
                        current_ssid = iw_res.stdout.strip()
                        if current_ssid:
                            connected = True
                            logger.info(f"BOOT: Linux WiFi connected via iwgetid: '{current_ssid}'")
                except: pass

            logger.info(f"BOOT: Linux WiFi check result - Connected: {connected}, SSID: '{current_ssid}'")
            return connected, current_ssid
    except Exception as e:
        logger.error(f"Error in check_wifi_status: {e}")
        return False, ""

# --- Data fetchers moved from app.py ---
def fetch_launches():
    print("DEBUG: fetch_launches called")  # Temporary debug
    logger.info("Fetching SpaceX launch data")

    # Check network connectivity before making API calls
    try:
        urllib.request.urlopen('http://www.google.com', timeout=5)
        logger.debug("Network connectivity check passed for launch data")
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        logger.warning(f"Network connectivity check failed for launch data: {e}")
        # Return cached data if available
        previous_cache = load_launch_cache('previous')
        upcoming_cache = load_launch_cache('upcoming')
        if previous_cache and upcoming_cache:
            logger.info("Returning cached launch data due to network issues")
            return {
                'previous': previous_cache['data'],
                'upcoming': upcoming_cache['data']
            }
        else:
            logger.error("No cached data available and network is down")
            return {'previous': [], 'upcoming': []}

    current_time = datetime.now(pytz.UTC)
    current_date_str = current_time.strftime('%Y-%m-%d')
    current_year = current_time.year

    # Load previous launches (prefer runtime; keep git seed intact)
    prev_cache_existed_before = os.path.exists(RUNTIME_CACHE_FILE_PREVIOUS)
    previous_cache = load_launch_cache('previous')
    if previous_cache:
        previous_launches = previous_cache['data']
        logger.info(f"Loaded {len(previous_launches)} previous launches from cache")
        try:
            emit_loader_status("Loading SpaceX launch history from cache…")
        except Exception:
            pass
        
        # Check for new launches to add (only recent ones)
        try:
            logger.info("Checking for new launches to add...")
            current_year = current_time.year
            url = f'https://ll.thespacedevs.com/2.0.0/launch/previous/?lsp__name=SpaceX&net__gte={current_year}-01-01&limit=50'
            
            try:
                response = requests.get(url, timeout=10, verify=True)
            except Exception as ssl_error:
                logger.warning(f"SSL verification failed, trying without verification: {ssl_error}")
                response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()
            
            # Get the most recent launch date from cache
            if previous_launches:
                cache_dates = [launch['net'] for launch in previous_launches if launch.get('net')]
                if cache_dates:
                    latest_cache_date = max(cache_dates)
                    logger.info(f"Latest cached launch: {latest_cache_date}")
                else:
                    latest_cache_date = None
            else:
                latest_cache_date = None
            
            new_launches = []
            for launch in data['results']:
                launch_net = launch['net']
                if latest_cache_date and launch_net <= latest_cache_date:
                    break  # No more new launches
                
                try:
                    launch_data = {
                        'id': launch.get('id'),
                        'mission': launch['name'],
                        'date': launch['net'].split('T')[0],
                        'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
                        'net': launch['net'],
                        'status': launch['status']['name'],
                        'rocket': launch['rocket']['configuration']['name'],
                        'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                        'pad': launch['pad']['name'],
                        'video_url': launch.get('vidURLs', [{}])[0].get('url', '')
                    }
                    new_launches.append(launch_data)
                except Exception as e:
                    logger.warning(f"Skipping launch {launch.get('name', 'Unknown')} due to error: {e}")
                    continue
            
            if new_launches:
                # Add new launches to the beginning (most recent first)
                previous_launches = new_launches + previous_launches
                save_launch_cache('previous', previous_launches, current_time)
                logger.info(f"Added {len(new_launches)} new launches to cache")
                # Status reflecting first-time cache creation
                try:
                    suffix = " for the first time" if not prev_cache_existed_before else ""
                    emit_loader_status(f"Updating SpaceX launch history cache{suffix}…")
                except Exception:
                    pass
            else:
                logger.info("No new launches to add")
                
        except Exception as e:
            logger.warning(f"Failed to check for new launches: {e}")
            
    else:
        # Try backup cache if main cache is corrupted/missing
        logger.warning("Main previous launches cache not found or corrupted, trying backup...")
        backup_cache = load_cache_from_file(CACHE_FILE_PREVIOUS_BACKUP)
        if backup_cache:
            previous_launches = backup_cache['data']
            logger.info(f"Loaded {len(previous_launches)} previous launches from backup cache")
            # Save backup as main cache
            save_launch_cache('previous', previous_launches, current_time)
        else:
            logger.error("Both main and backup caches are unavailable, using fallback data")
            previous_launches = [
                {'mission': 'Starship Flight 7', 'date': '2025-01-15', 'time': '12:00:00', 'net': '2025-01-15T12:00:00Z', 'status': 'Success', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': 'https://www.youtube.com/embed/videoseries?si=rvwtzwj_URqw2dtK&controls=0&list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY'},
                {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
            ]

    # Load upcoming launches cache
    up_cache_existed_before = os.path.exists(RUNTIME_CACHE_FILE_UPCOMING)
    upcoming_cache = load_launch_cache('upcoming')
    if upcoming_cache and (current_time - upcoming_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_UPCOMING:
        upcoming_launches = upcoming_cache['data']
        logger.info("Using persistent cached upcoming launches")
        try:
            emit_loader_status("Loading upcoming launches from cache…")
        except Exception:
            pass
    else:
        try:
            logger.info("Fetching fresh upcoming launches from API")
            try:
                emit_loader_status("Fetching upcoming SpaceX launches…")
            except Exception:
                pass
            url = 'https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=50'
            logger.info(f"API URL: {url}")
            try:
                response = requests.get(url, timeout=10, verify=True)
            except Exception as ssl_error:
                logger.warning(f"SSL verification failed for upcoming launches, trying without verification: {ssl_error}")
                response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            data = response.json()
            logger.info(f"API response received, status: {response.status_code}")
            upcoming_launches = [
                {
                    'id': launch.get('id'),
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
            save_launch_cache('upcoming', upcoming_launches, current_time)
            logger.info(f"Successfully fetched and saved {len(upcoming_launches)} upcoming launches")
            try:
                suffix = " for the first time" if not up_cache_existed_before else ""
                emit_loader_status(f"Saving upcoming launches to cache{suffix}…")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"LL2 API error for upcoming launches: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Fallback to cached upcoming launches if available, even if stale
            cache_fallback = load_launch_cache('upcoming')
            if cache_fallback and cache_fallback.get('data'):
                upcoming_launches = cache_fallback['data']
                logger.warning(
                    f"Using cached upcoming launches due to API failure; count={len(upcoming_launches)}"
                )
            else:
                logger.warning("No cached upcoming launches available; proceeding with empty list")
                upcoming_launches = []

    return {'previous': previous_launches, 'upcoming': upcoming_launches}


def fetch_narratives():
    """Fetch witty launch narratives from the API with fallback and caching."""
    logger.info("Fetching narratives")
    narratives = []
    
    # Try loading from cache first
    try:
        cache = load_cache_from_file(RUNTIME_CACHE_FILE_NARRATIVES)
        current_time = datetime.now(pytz.UTC)
        if cache and (current_time - cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_NARRATIVES:
            logger.info("Using cached narratives")
            return cache['data']
    except Exception as e:
        logger.warning(f"Failed to load narratives cache: {e}")

    # Check network and fetch from API
    try:
        urllib.request.urlopen('http://www.google.com', timeout=5)
        url = "https://launch-narrative-api-dafccc521fb8.herokuapp.com/recent_launches_narratives"
        logger.info(f"Fetching narratives from API: {url}")
        
        # Verify=False to avoid potential SSL cert issues on embedded python envs
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # The API returns a dict with 'descriptions' key
        if isinstance(data, dict) and 'descriptions' in data:
            narratives = data['descriptions']
            if isinstance(narratives, list):
                save_cache_to_file(RUNTIME_CACHE_FILE_NARRATIVES, narratives, datetime.now(pytz.UTC))
                logger.info(f"Fetched and cached {len(narratives)} narratives")
                return narratives
        
        # Fallback if top-level list (in case API changes back)
        if isinstance(data, list):
            narratives = data
            save_cache_to_file(RUNTIME_CACHE_FILE_NARRATIVES, narratives, datetime.now(pytz.UTC))
            logger.info(f"Fetched and cached {len(narratives)} narratives")
            return narratives
            
        logger.warning(f"Narratives API returned unexpected format: {type(data)}")
            
    except Exception as e:
        logger.warning(f"Failed to fetch narratives from API: {e}")

    # Fallback to cache if available (even if stale)
    if cache and cache.get('data'):
        logger.info("Using stale cached narratives as fallback")
        return cache['data']

    # Final fallback to hardcoded descriptions
    logger.info("Using hardcoded fallback narratives")
    return LAUNCH_DESCRIPTIONS



def fetch_f1_data():
    """Fetch F1 data with optimized component-based caching."""
    logger.info("Fetching F1 data with optimized caching")

    # Check network connectivity before making API calls
    try:
        urllib.request.urlopen('http://www.google.com', timeout=5)
        logger.debug("Network connectivity check passed for F1 data")
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        logger.warning(f"Network connectivity check failed for F1 data: {e}")
        # Return cached data if available
        schedule_cache = load_cache_from_file(CACHE_FILE_F1_SCHEDULE)
        drivers_cache = load_cache_from_file(CACHE_FILE_F1_DRIVERS)
        constructors_cache = load_cache_from_file(CACHE_FILE_F1_CONSTRUCTORS)
        if schedule_cache and drivers_cache and constructors_cache:
            logger.info("Returning cached F1 data due to network issues")
            return {
                'schedule': schedule_cache['data'],
                'driver_standings': drivers_cache['data'],
                'constructor_standings': constructors_cache['data']
            }
        else:
            logger.error("No cached F1 data available and network is down")
            return {'schedule': [], 'driver_standings': [], 'constructor_standings': []}

    global f1_cache
    if f1_cache:
        return f1_cache

    current_time = datetime.now(pytz.UTC)
    f1_data = {}

    # Fetch race schedule (infrequently changing)
    schedule_cache_exists = os.path.exists(CACHE_FILE_F1_SCHEDULE)
    schedule_cache = load_cache_from_file(CACHE_FILE_F1_SCHEDULE)
    if schedule_cache and (current_time - schedule_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_SCHEDULE:
        f1_data['schedule'] = schedule_cache['data']
        logger.info("Using cached F1 schedule data")
        try:
            emit_loader_status("Loading F1 schedule from cache…")
        except Exception:
            pass
    else:
        logger.info("Fetching fresh F1 schedule data")
        try:
            emit_loader_status("Fetching F1 race schedule…")
        except Exception:
            pass
        try:
            url = f"https://f1api.dev/api/current"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info(f"F1 API response keys: {list(data.keys())}")
            races = data.get('races', [])
            meetings = []

            for race in races:
                meeting = {
                    "circuit_short_name": race['circuit']['circuitName'],
                    "location": race['circuit']['city'],
                    "country_name": race['circuit']['country'],
                    "meeting_name": race['raceName'],
                    "year": data['season'],
                    "round": race['round'],
                    "laps": race['laps'],
                    "winner": race.get('winner', {}),
                    "teamWinner": race.get('teamWinner', {}),
                    "fast_lap": race.get('fast_lap', {})
                }

                # Parse sessions
                sessions = []
                schedule = race['schedule']
                session_name_map = {
                    "fp1": "Practice 1",
                    "fp2": "Practice 2",
                    "fp3": "Practice 3",
                    "qualy": "Qualifying",
                    "sprintQualy": "Sprint Qualifying",
                    "sprintRace": "Sprint",
                    "race": "Race"
                }

                for session_key, session_data in schedule.items():
                    if session_data and session_data.get('date'):
                        sessions.append({
                            "location": meeting['location'],
                            "date_start": f"{session_data['date']}T{session_data.get('time', '00:00:00')}",
                            "session_type": "Practice" if "fp" in session_key else ("Qualifying" if "qualy" in session_key else "Race"),
                            "session_name": session_name_map.get(session_key, session_key),
                            "country_name": meeting['country_name'],
                            "circuit_short_name": meeting['circuit_short_name'],
                            "year": meeting['year']
                        })

                meeting['sessions'] = sorted(sessions, key=lambda x: parse(x['date_start']))

                # Generate track map (notify splash; add "for the first time" on first render)
                circuit_name = race['circuit']['circuitName']
                tracks_dir = os.path.join(os.path.dirname(__file__), '..', 'cache', 'tracks')
                safe_circuit_name = circuit_name.replace('|', '-').replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', '-').replace('<', '-').replace('>', '-')
                png_expected = os.path.join(tracks_dir, f"{safe_circuit_name}_track.png")
                try:
                    if os.path.exists(png_expected):
                        emit_loader_status(f"Loading track map for {circuit_name}…")
                    else:
                        emit_loader_status(f"Generating track map for {circuit_name} for the first time…")
                except Exception:
                    pass
                track_map_path = generate_track_map(circuit_name)
                # Sanitize circuit name for filename (same as in track_generator.py)
                meeting['track_map_path'] = f'file:///{os.path.join(os.path.dirname(__file__), "..", "cache", "tracks", f"{safe_circuit_name}_track.png")}' if track_map_path else ''

                if sessions:
                    # Use the race session date as the primary date for sorting
                    race_session = next((s for s in sessions if s['session_type'] == 'Race'), None)
                    if race_session:
                        meeting['date_start'] = race_session['date_start']
                    else:
                        meeting['date_start'] = min(s['date_start'] for s in sessions)
                meetings.append(meeting)

            f1_data['schedule'] = meetings
            save_cache_to_file(CACHE_FILE_F1_SCHEDULE, meetings, current_time)
            logger.info(f"Cached F1 schedule with {len(meetings)} races")
            try:
                suffix = " for the first time" if not schedule_cache_exists else ""
                emit_loader_status(f"Saving F1 schedule to cache{suffix}…")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to fetch F1 schedule: {e}")
            f1_data['schedule'] = []

    # Fetch driver standings (frequently changing)
    drivers_cache_existed = os.path.exists(CACHE_FILE_F1_DRIVERS)
    drivers_cache = load_cache_from_file(CACHE_FILE_F1_DRIVERS)
    if drivers_cache and (current_time - drivers_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_STANDINGS:
        f1_data['driver_standings'] = drivers_cache['data']
        logger.info("Using cached F1 driver standings")
        try:
            emit_loader_status("Loading F1 driver standings from cache…")
        except Exception:
            pass
    else:
        logger.info("Fetching fresh F1 driver standings")
        try:
            emit_loader_status("Fetching F1 driver standings…")
        except Exception:
            pass
        try:
            url = "https://f1api.dev/api/current/drivers-championship"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            driver_standings = data.get('drivers_championship', [])

            # Normalize to expected format
            for standing in driver_standings:
                if 'driver' in standing and 'Driver' not in standing:
                    standing['Driver'] = {
                        'givenName': standing['driver']['name'],
                        'familyName': standing['driver']['surname'],
                        'driverId': standing['driverId'],
                        'nationality': standing['driver']['nationality'],
                        'code': standing['driver']['shortName']
                    }
                if 'team' in standing and 'Constructor' not in standing:
                    # Normalize team name to standard format
                    api_team_name = standing['team']['teamName']
                    api_team_name_lower = api_team_name.lower()
                    normalized_team_name = api_team_name  # Default to original if no mapping found
                    
                    # Map API team names to standard names
                    team_name_mapping = {
                        'mclaren formula 1 team': 'McLaren',
                        'red bull racing': 'Red Bull',
                        'mercedes formula 1 team': 'Mercedes',
                        'scuderia ferrari': 'Ferrari',
                        'williams racing': 'Williams',
                        'rb f1 team': 'AlphaTauri',
                        'sauber f1 team': 'Alfa Romeo',
                        'haas f1 team': 'Haas F1 Team',
                        'aston martin f1 team': 'Aston Martin',
                        'alpine f1 team': 'Alpine',
                        # Keep old mappings as fallbacks
                        'mercedes-amg petronas f1 team': 'Mercedes',
                        'oracle red bull racing': 'Red Bull',
                        'scuderia ferrari hp': 'Ferrari', 
                        'mclaren f1 team': 'McLaren',
                        'bwt alpine f1 team': 'Alpine',
                        'aston martin aramco cognizant f1 team': 'Aston Martin',
                        'alfa romeo f1 team stake': 'Alfa Romeo',
                        'moneygram haas f1 team': 'Haas F1 Team',
                        'visa cash app rb f1 team': 'AlphaTauri',
                        # Fallback mappings for shorter names
                        'mercedes': 'Mercedes',
                        'red bull': 'Red Bull',
                        'ferrari': 'Ferrari',
                        'mclaren': 'McLaren',
                        'alpine': 'Alpine',
                        'aston martin': 'Aston Martin',
                        'williams': 'Williams',
                        'alfa romeo': 'Alfa Romeo',
                        'haas': 'Haas F1 Team',
                        'rb': 'AlphaTauri',
                        'alphatauri': 'AlphaTauri'
                    }
                    normalized_team_name = team_name_mapping.get(api_team_name_lower, api_team_name)
                    standing['Constructor'] = {
                        'name': normalized_team_name
                    }

            f1_data['driver_standings'] = driver_standings
            save_cache_to_file(CACHE_FILE_F1_DRIVERS, driver_standings, current_time)
            logger.info(f"Cached F1 driver standings with {len(driver_standings)} drivers")
            try:
                suffix = " for the first time" if not drivers_cache_existed else ""
                emit_loader_status(f"Saving driver standings to cache{suffix}…")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to fetch F1 driver standings: {e}")
            f1_data['driver_standings'] = []

    # Fetch constructor standings (frequently changing)
    constructors_cache_existed = os.path.exists(CACHE_FILE_F1_CONSTRUCTORS)
    constructors_cache = load_cache_from_file(CACHE_FILE_F1_CONSTRUCTORS)
    if constructors_cache and (current_time - constructors_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_STANDINGS:
        f1_data['constructor_standings'] = constructors_cache['data']
        logger.info("Using cached F1 constructor standings")
        try:
            emit_loader_status("Loading F1 constructor standings from cache…")
        except Exception:
            pass
    else:
        logger.info("Fetching fresh F1 constructor standings")
        try:
            emit_loader_status("Fetching F1 constructor standings…")
        except Exception:
            pass
        try:
            url = "https://f1api.dev/api/current/constructors-championship"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            constructor_standings = data.get('constructors_championship', [])

            # Normalize to expected format
            for standing in constructor_standings:
                if 'team' in standing and 'Constructor' not in standing:
                    api_team_name = standing['team']['teamName']
                    api_team_name_lower = api_team_name.lower()
                    team_name_mapping = {
                        'mclaren formula 1 team': 'McLaren',
                        'red bull racing': 'Red Bull',
                        'mercedes formula 1 team': 'Mercedes',
                        'scuderia ferrari': 'Ferrari',
                        'williams racing': 'Williams',
                        'rb f1 team': 'AlphaTauri',
                        'sauber f1 team': 'Alfa Romeo',
                        'haas f1 team': 'Haas F1 Team',
                        'aston martin f1 team': 'Aston Martin',
                        'alpine f1 team': 'Alpine',
                        # Keep old mappings as fallbacks
                        'mercedes-amg petronas f1 team': 'Mercedes',
                        'oracle red bull racing': 'Red Bull',
                        'scuderia ferrari hp': 'Ferrari', 
                        'mclaren f1 team': 'McLaren',
                        'bwt alpine f1 team': 'Alpine',
                        'aston martin aramco cognizant f1 team': 'Aston Martin',
                        'alfa romeo f1 team stake': 'Alfa Romeo',
                        'moneygram haas f1 team': 'Haas F1 Team',
                        'visa cash app rb f1 team': 'AlphaTauri',
                        # Fallback mappings for shorter names
                        'mercedes': 'Mercedes',
                        'red bull': 'Red Bull',
                        'ferrari': 'Ferrari',
                        'mclaren': 'McLaren',
                        'alpine': 'Alpine',
                        'aston martin': 'Aston Martin',
                        'williams': 'Williams',
                        'alfa romeo': 'Alfa Romeo',
                        'haas': 'Haas F1 Team',
                        'rb': 'AlphaTauri',
                        'alphatauri': 'AlphaTauri'
                    }
                    normalized_team_name = team_name_mapping.get(api_team_name_lower, api_team_name)
                    standing['Constructor'] = {'name': normalized_team_name}

            f1_data['constructor_standings'] = constructor_standings
            save_cache_to_file(CACHE_FILE_F1_CONSTRUCTORS, constructor_standings, current_time)
            logger.info(f"Cached F1 constructor standings with {len(constructor_standings)} teams")
            try:
                suffix = " for the first time" if not constructors_cache_existed else ""
                emit_loader_status(f"Saving constructor standings to cache{suffix}…")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to fetch F1 constructor standings: {e}")
            f1_data['constructor_standings'] = []

    f1_cache = f1_data
    logger.info("Successfully assembled F1 data from optimized cache")
    return f1_data


def fetch_weather(lat, lon, location):
    logger.info(f"Fetching METAR weather data for {location}")

    # METAR station mappings - closest weather stations for each location
    metar_stations = {
        'Starbase': 'KBRO',  # Brownsville International Airport
        'Vandy': 'KVBG',    # Vandenberg Space Force Base
        'Cape': 'KMLB',     # Melbourne International Airport (closest to Kennedy Space Center)
        'Hawthorne': 'KHHR' # Hawthorne Municipal Airport
    }

    station_id = metar_stations.get(location, 'KBRO')  # Default to KBRO if not found

    # Check network connectivity before making API calls
    try:
        urllib.request.urlopen('http://www.google.com', timeout=5)
        logger.debug("Network connectivity check passed for weather data")
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        logger.warning(f"Network connectivity check failed for weather data: {e}")
        # Return fallback data
        logger.info("Returning fallback weather data due to network issues")
        return {
            'temperature_c': 25,
            'temperature_f': 77,
            'wind_speed_ms': 5,
            'wind_speed_kts': 9.7,
            'wind_direction': 90,
            'cloud_cover': 50
        }

    try:
        # Use Aviation Weather Center METAR API
        url = f"https://aviationweather.gov/api/data/metar?ids={station_id}&format=raw"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        raw_metar = response.text.strip()

        if not raw_metar:
            raise ValueError(f"No METAR data received for station {station_id}")

        logger.info(f"Successfully fetched METAR data for {location} from {station_id}: {raw_metar}")

        # Parse METAR data
        parsed_data = parse_metar(raw_metar)

        time.sleep(1)  # Avoid rate limiting
        return parsed_data

    except Exception as e:
        logger.error(f"METAR API error for {location} (station {station_id}): {e}")
        return {
            'temperature_c': 25,
            'temperature_f': 77,
            'wind_speed_ms': 5,
            'wind_speed_kts': 9.7,
            'wind_direction': 90,
            'cloud_cover': 50
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
                return networks
        return []
    except Exception as e:
        logger.error(f"Error loading remembered networks: {e}")
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
    try:
        if os.path.exists(LAST_CONNECTED_NETWORK_FILE):
            with open(LAST_CONNECTED_NETWORK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading last connected network: {e}")
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

def start_http_server():
    """Start a simple HTTP server for the globe and other web content"""
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
            with socketserver.TCPServer(("", attempt_port), handler) as httpd:
                # Allow address reuse to prevent "address already in use" errors
                httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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


def test_network_connectivity(wifi_connected=True):
    """Check for active network connectivity by trying reliable external hosts"""
    if not wifi_connected:
        return False
    
    test_urls = [
        'http://www.google.com',
        'http://www.cloudflare.com',
        'http://1.1.1.1'
    ]

    for url in test_urls:
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except (urllib.error.URLError, socket.timeout, OSError):
            continue

    try:
        socket.gethostbyname('google.com')
        return True
    except socket.gaierror:
        pass

    return False


def get_git_version_info(src_dir):
    """Get summarized git version info (hash and message)"""
    try:
        res_hash = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd=src_dir)
        if res_hash.returncode != 0: return None
        commit_hash = res_hash.stdout.strip()

        res_msg = subprocess.run(['git', 'log', '-1', '--pretty=format:%s', commit_hash], capture_output=True, text=True, cwd=src_dir)
        commit_message = res_msg.stdout.strip() if res_msg.returncode == 0 else "Unknown"

        return {
            'hash': commit_hash,
            'short_hash': commit_hash[:8],
            'message': commit_message
        }
    except Exception as e:
        logger.error(f"Error getting git version info: {e}")
        return None


def check_github_for_updates(current_hash, repo_owner="hwpaige", repo_name="spacex-dashboard"):
    """Check if a newer version is available on GitHub"""
    try:
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/master"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            latest = response.json()
            latest_hash = latest['sha']
            return latest_hash != current_hash, {
                'hash': latest_hash,
                'short_hash': latest_hash[:8],
                'message': latest['commit']['message'],
                'author': latest['commit']['author']['name'],
                'date': latest['commit']['author']['date']
            }
    except Exception as e:
        logger.error(f"Error checking GitHub updates: {e}")
    return False, None


def get_country_flag_url(country_name, assets_dir):
    """Get or download a country flag SVG URL"""
    code_map = {
        'Australia': 'au', 'Austria': 'at', 'Azerbaijan': 'az', 'Bahrain': 'bh',
        'Belgium': 'be', 'Brazil': 'br', 'Canada': 'ca', 'China': 'cn',
        'France': 'fr', 'Germany': 'de', 'Great Britain': 'gb', 'Hungary': 'hu',
        'Italy': 'it', 'Japan': 'jp', 'Mexico': 'mx', 'Monaco': 'mc',
        'Netherlands': 'nl', 'Portugal': 'pt', 'Qatar': 'qa', 'Russia': 'ru',
        'Saudi Arabia': 'sa', 'Singapore': 'sg', 'South Korea': 'kr', 'Spain': 'es',
        'Turkey': 'tr', 'UAE': 'ae', 'United Arab Emirates': 'ae', 'UK': 'gb',
        'United Kingdom': 'gb', 'United States': 'us', 'USA': 'us', 'Vietnam': 'vn'
    }
    code = code_map.get(country_name)
    if not code: return ""
    
    flags_dir = os.path.join(assets_dir, "images", "flags")
    os.makedirs(flags_dir, exist_ok=True)
    flag_path = os.path.join(flags_dir, f"{code}.svg")
    
    if not os.path.exists(flag_path):
        try:
            url = f"https://flagicons.lipis.dev/flags/4x3/{code}.svg"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            with open(flag_path, 'wb') as f:
                f.write(resp.content)
        except Exception as e:
            logger.warning(f"Failed to download flag for {country_name}: {e}")
            return ""
    
    return f"file:///{flag_path.replace('\\', '/')}"


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
    """Process launch data into series for charting"""
    import pandas as pd
    df = pd.DataFrame(launches)
    if df.empty:
        return [], []
        
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['date'].dt.year == current_year]
    rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
    df = df[df['rocket'].isin(rocket_types)]
    df['month'] = df['date'].dt.to_period('M').astype(str)
    
    df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
    df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)
    
    # Ensure all months up to current are present
    all_months = [f"{current_year}-{m:02d}" for m in range(1, current_month + 1)]
    df_pivot = df_pivot.reindex(all_months, fill_value=0)
    
    for col in rocket_types:
        if col not in df_pivot.columns:
            df_pivot[col] = 0
            
    if chart_view_mode == 'cumulative':
        for col in rocket_types:
            df_pivot[col] = df_pivot[col].cumsum()
            
    data = []
    for rocket in rocket_types:
        data.append({
            'label': rocket,
            'values': df_pivot[rocket].tolist()
        })
    return all_months, data


def generate_f1_chart_html(f1_data, chart_type, stat_key, theme):
    """Generate HTML for interactive F1 charts"""
    try:
        if chart_type == 'standings':
            standings = f1_data.get('driver_standings', [])
            if not standings: return _get_empty_chart_html(theme)
            
            driver_data = []
            for driver in standings[:10]:
                d_name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
                driver_data.append({
                    'driver': d_name,
                    'round': 1,
                    'points': float(driver.get(stat_key, 0))
                })
            # This logic assumes the plotly_charts functions return the full HTML
            return generate_f1_standings_chart(driver_data, 'line', theme)
        elif chart_type == 'telemetry':
            return generate_f1_telemetry_chart(theme)
        elif chart_type == 'weather':
            return generate_f1_weather_chart(theme)
        elif chart_type == 'positions':
            return generate_f1_positions_chart(theme)
        elif chart_type == 'laps':
            return generate_f1_laps_chart(theme)
        else:
            return generate_f1_standings_chart([], 'line', theme)
    except Exception as e:
        logger.error(f"Error generating F1 chart HTML: {e}")
        return _get_empty_chart_html(theme)


def _get_empty_chart_html(theme):
    """Return HTML for empty chart state"""
    bg_color = 'rgba(42,46,46,1)' if theme == 'dark' else 'rgba(240,240,240,1)'
    text_color = 'white' if theme == 'dark' else 'black'

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background-color: {bg_color};
                color: {text_color};
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div>
            <h3>No F1 Data Available</h3>
            <p>Please check your internet connection and try again.</p>
        </div>
    </body>
    """

def get_launch_trajectory_data(upcoming_launches, previous_launches=None):
    """
    Get trajectory data for the next upcoming launch.
    Standalone version of Backend.get_launch_trajectory.
    """
    logger.info("get_launch_trajectory_data called")
    
    # If no upcoming launches, try to use recent launches for demo
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
                    'net': launch.get('net', '')
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
            if 'iss' in (orbit or '').lower():
                return 51.6
            if norm_orbit == 'LEO-Polar':
                return 97.0
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

    ORBIT_CACHE_VERSION = 'v5'
    cache_key = f"{ORBIT_CACHE_VERSION}:{matched_site_key}:{normalized_orbit}:{round(assumed_incl,1)}"
    
    traj_cache = {}
    cache_loaded = load_cache_from_file(TRAJECTORY_CACHE_FILE)
    if cache_loaded and isinstance(cache_loaded.get('data'), dict):
        traj_cache = cache_loaded['data']

    if cache_key in traj_cache:
        cached = traj_cache[cache_key]
        logger.info(f"Trajectory cache hit for {cache_key}")
        return {
            'launch_site': cached.get('launch_site', launch_site),
            'trajectory': cached.get('trajectory', []),
            'orbit_path': cached.get('orbit_path', []),
            'orbit': orbit or cached.get('orbit', normalized_orbit),
            'mission': mission_name,
            'pad': pad
        }

    logger.info(f"Trajectory cache miss for {cache_key}; generating new trajectory")

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
            L = min(20.0, max(5.0, ang_deg / 3.0))
            br = math.radians(end_bearing_deg)
            cos_lat = max(1e-6, math.cos(math.radians(end_lat)))
            dlat_deg = L * math.cos(br)
            dlon_deg = (L * math.sin(br)) / cos_lat
            control_lat = end_lat - dlat_deg
            control_lon = (end_lon - dlon_deg + 180.0) % 360.0 - 180.0
        else:
            mid_lat = (start_lat + end_lat) / 2
            mid_lon = (start_lon + end_lon) / 2
            if orbit_type == 'polar':
                control_lat = max(-85.0, mid_lat - 20)
                control_lon = mid_lon - 20
            elif orbit_type == 'equatorial':
                control_lat = mid_lat + 15
                control_lon = mid_lon + 30
            elif orbit_type == 'gto':
                control_lat = mid_lat + 25
                control_lon = mid_lon + 60
            elif orbit_type == 'suborbital':
                control_lat = mid_lat + 10
                control_lon = mid_lon + 15
            else:
                control_lat = mid_lat + 20
                control_lon = mid_lon + 45

        for i in range(num_points + 1):
            t = i / num_points
            lat = (1-t)**2 * start_lat + 2*(1-t)*t * control_lat + t**2 * end_lat
            lon = (1-t)**2 * start_lon + 2*(1-t)*t * control_lon + t**2 * end_lon
            lon = (lon + 180) % 360 - 180
            points.append({'lat': lat, 'lon': lon})
        return points

    def generate_orbit_path_inclined(trajectory, orbit_label, inclination_deg, num_points=180):
        if not trajectory: return []
        start = trajectory[-1]
        lat0 = float(start['lat']); lon0 = float(start['lon'])
        eff_i_deg = max(0.1, min(89.9, abs(inclination_deg) % 180 if abs(inclination_deg) % 180 <= 90 else 180 - (abs(inclination_deg) % 180)))
        i_rad = math.radians(eff_i_deg)
        lat0_rad = math.radians(lat0); lon0_rad = math.radians(lon0)
        x0 = math.cos(lat0_rad) * math.cos(lon0_rad)
        y0 = math.cos(lat0_rad) * math.sin(lon0_rad)
        z0 = math.sin(lat0_rad)
        sin_i = math.sin(i_rad)
        u0 = math.asin(max(-1.0, min(1.0, z0 / (sin_i or 1e-6))))
        Omega = math.atan2(y0, x0) - math.atan2(math.sin(u0) * math.cos(i_rad), math.cos(u0))
        cosO = math.cos(Omega); sinO = math.sin(Omega)
        cosi = math.cos(i_rad); sili = math.sin(i_rad)
        points = []
        for k in range(num_points):
            u = u0 + (2.0 * math.pi * k) / num_points
            cu = math.cos(u); su = math.sin(u)
            x = cosO * cu - sinO * (su * cosi)
            y = sinO * cu + cosO * (su * cosi)
            z = su * sili
            points.append({'lat': math.degrees(math.atan2(z, max(1e-12, math.hypot(x, y)))), 'lon': (math.degrees(math.atan2(y, x)) + 180) % 360 - 180})
        return points

    def _ang_dist_deg(a, b):
        lat1 = math.radians(a['lat']); lon1 = math.radians(a['lon'])
        lat2 = math.radians(b['lat']); lon2 = math.radians(b['lon'])
        h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
        return math.degrees(2 * math.atan2(math.sqrt(h), math.sqrt(max(1e-12, 1-h))))

    def _bearing_deg(lat1, lon1, lat2, lon2):
        phi1 = math.radians(lat1); phi2 = math.radians(lat2); dlon = math.radians(lon2-lon1)
        return (math.degrees(math.atan2(math.sin(dlon)*math.cos(phi2), math.cos(phi1)*math.sin(phi2)-math.sin(phi1)*math.cos(phi2)*math.cos(dlon))) + 360) % 360

    # Main generation
    if normalized_orbit == 'LEO-Polar':
        trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] - 30, 'lon': launch_site['lon'] - 10}, 20, orbit_type='polar')
    elif normalized_orbit == 'LEO-Equatorial':
        trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'], 'lon': launch_site['lon'] + 120}, 35, orbit_type='equatorial')
    elif normalized_orbit == 'GTO':
        trajectory = generate_curved_trajectory(launch_site, {'lat': 0, 'lon': launch_site['lon'] + 150}, 30, orbit_type='gto')
    elif normalized_orbit == 'Suborbital':
        trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] + 15, 'lon': launch_site['lon'] + 45}, 15, orbit_type='suborbital')
    else:
        trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] + 20, 'lon': launch_site['lon'] + 60}, 20, orbit_type='default')

    orbit_path = generate_orbit_path_inclined(trajectory, orbit, assumed_incl, 360)
    
    # Tangent- and position-match
    if trajectory and orbit_path:
        try:
            current_end = trajectory[-1]
            min_d = 1e9; orbit_idx = 0
            for i, p in enumerate(orbit_path):
                d = _ang_dist_deg(current_end, p)
                if d < min_d: min_d = d; orbit_idx = i
            
            snapped_end = orbit_path[orbit_idx]
            end_bearing = _bearing_deg(snapped_end['lat'], snapped_end['lon'], orbit_path[(orbit_idx+1)%len(orbit_path)]['lat'], orbit_path[(orbit_idx+1)%len(orbit_path)]['lon'])
            
            densified_n = max(40, int(len(trajectory) * 1.25))
            new_traj = generate_curved_trajectory(trajectory[0], snapped_end, densified_n, 
                                                orbit_type=('polar' if normalized_orbit == 'LEO-Polar' else ('equatorial' if normalized_orbit == 'LEO-Equatorial' else ('gto' if normalized_orbit == 'GTO' else 'default'))),
                                                end_bearing_deg=end_bearing)
            
            tail_len = max(6, int(0.15 * len(new_traj)))
            orbit_tail = [orbit_path[(orbit_idx - (tail_len-1-j)) % len(orbit_path)] for j in range(tail_len)]
            new_traj[-tail_len:] = orbit_tail
            trajectory = new_traj
        except Exception as e:
            logger.warning(f"Tangent match failed: {e}")

    result = {
        'launch_site': launch_site,
        'trajectory': trajectory,
        'orbit_path': orbit_path,
        'orbit': orbit,
        'mission': mission_name,
        'pad': pad
    }

    # Persist to cache
    try:
        traj_cache[cache_key] = {
            'launch_site': launch_site,
            'trajectory': trajectory,
            'orbit_path': orbit_path,
            'orbit': normalized_orbit,
            'inclination_deg': assumed_incl,
            'model': 'v6-tail-on-orbit-centralized'
        }
        save_cache_to_file(TRAJECTORY_CACHE_FILE, traj_cache, datetime.now(pytz.UTC))
    except Exception as e:
        logger.warning(f"Failed to save trajectory cache: {e}")

    return result

def group_event_data(data, mode, event_type, timezone_obj):
    """
    Group and filter launch or race event data by date range (Today, This Week, Later, etc.).
    UI-agnostic logic extracted from EventModel.update_data.
    """
    today = datetime.now(pytz.UTC).date()
    this_week_end = today + timedelta(days=7)
    last_week_start = today - timedelta(days=7)
    grouped = []
    
    if mode == 'spacex':
        # data is expected to be a dict with 'upcoming' and 'previous' keys
        launches = data.get('upcoming' if event_type == 'upcoming' else 'previous', [])
        
        # Add local time to each launch
        processed_launches = []
        for l in launches:
            launch = l.copy()
            net = launch.get('net', '') or launch.get('date_start', '')
            if net:
                try:
                    launch['localTime'] = parse(net).astimezone(timezone_obj).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    launch['localTime'] = 'TBD'
            else:
                launch['localTime'] = 'TBD'
            processed_launches.append(launch)
        
        if event_type == 'upcoming':
            launches = sorted(processed_launches, key=lambda x: parse(x['net']) if x.get('net') else datetime.max.replace(tzinfo=pytz.UTC))
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
            launches = sorted(processed_launches, key=lambda x: parse(x['net']) if x.get('net') else datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
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
        # data is expected to be a list of races
        races = data
        if event_type == 'upcoming':
            races = sorted(races, key=lambda x: parse(x['date_start']) if x.get('date_start') else datetime.max.replace(tzinfo=pytz.UTC))
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
            races = sorted(races, key=lambda x: parse(x['date_start']) if x.get('date_start') else datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
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

def normalize_team_name(api_team_name):
    """Normalize F1 team names from API to shorter dashboard-friendly versions."""
    if not api_team_name:
        return api_team_name
    api_team_name_lower = api_team_name.lower()
    team_name_mapping = {
        'mclaren formula 1 team': 'McLaren',
        'red bull racing': 'Red Bull',
        'mercedes formula 1 team': 'Mercedes',
        'scuderia ferrari': 'Ferrari',
        'williams racing': 'Williams',
        'rb f1 team': 'AlphaTauri',
        'sauber f1 team': 'Alfa Romeo',
        'haas f1 team': 'Haas F1 Team',
        'aston martin f1 team': 'Aston Martin',
        'alpine f1 team': 'Alpine',
        'mercedes-amg petronas f1 team': 'Mercedes',
        'oracle red bull racing': 'Red Bull',
        'scuderia ferrari hp': 'Ferrari', 
        'mclaren f1 team': 'McLaren',
        'bwt alpine f1 team': 'Alpine',
        'aston martin aramco cognizant f1 team': 'Aston Martin',
        'alfa romeo f1 team stake': 'Alfa Romeo',
        'moneygram haas f1 team': 'Haas F1 Team',
        'visa cash app rb f1 team': 'AlphaTauri',
        'mercedes': 'Mercedes',
        'red bull': 'Red Bull',
        'ferrari': 'Ferrari',
        'mclaren': 'McLaren',
        'alpine': 'Alpine',
        'aston martin': 'Aston Martin',
        'williams': 'Williams',
        'alfa romeo': 'Alfa Romeo',
        'haas': 'Haas F1 Team',
        'rb': 'AlphaTauri',
        'alphatauri': 'AlphaTauri'
    }
    return team_name_mapping.get(api_team_name_lower, api_team_name)

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

def start_update_script(script_path):
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
                ['/bin/bash', script_path],
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
                ['/bin/bash' if os.path.exists('/bin/bash') else 'bash', script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.path.dirname(script_path)
            )
            return True, {"pid": None, "log_path": None}
    except Exception as e:
        return False, str(e)

def get_f1_driver_points_chart(standings):
    """Transform F1 driver standings into chart-ready format."""
    if not standings:
        return []
    top_drivers = standings[:10]
    data = []
    for driver in top_drivers:
        name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
        data.append({
            'label': name,
            'value': float(driver.get('points', 0))
        })
    return data

def get_f1_constructor_points_chart(standings):
    """Transform F1 constructor standings into chart-ready format."""
    if not standings:
        return []
    top_constructors = standings[:10]
    data = []
    for constructor in top_constructors:
        data.append({
            'label': constructor['Constructor']['name'],
            'value': float(constructor.get('points', 0))
        })
    return data

def get_f1_driver_points_series(standings, stat_key='points'):
    """Transform F1 driver standings into line series format."""
    if not standings:
        return []
    top_drivers = standings[:10]
    values = [float(driver.get(stat_key, 0)) for driver in top_drivers]
    return [{'label': stat_key.title(), 'values': values}]

def get_f1_constructor_points_series(standings, stat_key='points'):
    """Transform F1 constructor standings into line series format."""
    if not standings:
        return []
    top_constructors = standings[:10]
    values = [float(constructor.get(stat_key, 0)) for constructor in top_constructors]
    return [{'label': stat_key.title(), 'values': values}]

def get_f1_driver_standings_over_time_series(standings, stat_key='points'):
    """Group drivers by team and create points series."""
    if not standings:
        return []
    
    top_drivers = standings[:10]
    series_data = []
    team_drivers = {}
    
    for driver in top_drivers:
        team_id = driver.get('teamId', 'unknown')
        if team_id not in team_drivers:
            team_drivers[team_id] = []
        team_drivers[team_id].append(driver)
    
    for team_id, drivers in team_drivers.items():
        team_color = F1_TEAM_COLORS.get(team_id, '#808080')
        for driver in drivers:
            name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
            series_data.append({
                'label': name,
                'values': [float(driver.get(stat_key, 0))],
                'color': team_color,
                'team': driver.get('Constructor', {}).get('name', team_id)
            })
    return series_data

def get_empty_chart_html(theme='dark'):
    """Return HTML for an empty chart state."""
    bg_color = 'rgba(42,46,46,1)' if theme == 'dark' else 'rgba(240,240,240,1)'
    text_color = 'white' if theme == 'dark' else 'black'
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                margin: 0; padding: 20px;
                background-color: {bg_color}; color: {text_color};
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex; align-items: center; justify-content: center;
                height: 100vh; text-align: center;
            }}
        </style>
    </head>
    <body>
        <div>
            <h3>No F1 Data Available</h3>
            <p>Please check your internet connection and try again.</p>
        </div>
    </body>
    </html>
    """

def get_empty_chart_url(theme='dark'):
    """Generate a temporary file URL for an empty chart."""
    try:
        html = get_empty_chart_html(theme)
        import tempfile
        temp_file = os.path.join(tempfile.gettempdir(), f'f1_chart_empty_{theme}.html')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(html)
        return f'file:///{temp_file.replace("\\", "/")}'
    except Exception as e:
        logger.error(f"Error creating empty chart URL: {e}")
        return ""

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

def get_next_launch_info(upcoming_launches, tz_obj):
    """Find and format the next upcoming launch."""
    current_time = datetime.now(pytz.UTC)
    valid_launches = [l for l in upcoming_launches if l.get('time') != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
    if valid_launches:
        next_l = min(valid_launches, key=lambda x: parse(x['net']))
        launch = next_l.copy()
        launch_datetime = parse(next_l['net']).replace(tzinfo=pytz.UTC).astimezone(tz_obj)
        launch['local_date'] = launch_datetime.strftime('%Y-%m-%d')
        launch['local_time'] = launch_datetime.strftime('%H:%M:%S')
        return launch
    return None

def get_upcoming_launches_list(upcoming_launches, tz_obj, limit=10):
    """Sort and format a list of upcoming launches."""
    current_time = datetime.now(pytz.UTC)
    valid_launches = [l for l in upcoming_launches if l.get('time') != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
    launches = []
    for l in sorted(valid_launches, key=lambda x: parse(x['net']))[:limit]:
        launch = l.copy()
        launch_datetime = parse(l['net']).replace(tzinfo=pytz.UTC).astimezone(tz_obj)
        launch['local_date'] = launch_datetime.strftime('%Y-%m-%d')
        launch['local_time'] = launch_datetime.strftime('%H:%M:%S')
        launches.append(launch)
    return launches

def get_next_race_info(race_schedule, tz_obj):
    """Find the next race in the schedule."""
    if not race_schedule: return None
    current = datetime.now(pytz.UTC)
    upcoming = [r for r in race_schedule if parse(r['date_start']).replace(tzinfo=pytz.UTC) > current]
    if upcoming:
        # Ergast returns schedule sorted by date generally, but min() is safer
        next_r = min(upcoming, key=lambda x: parse(x['date_start']))
        return next_r
    return None

def initialize_all_weather(locations_config):
    """Fetch initial weather for all configured locations."""
    weather_data = {}
    for location, settings in locations_config.items():
        try:
            weather = fetch_weather(settings['lat'], settings['lon'], location)
            weather_data[location] = weather
        except Exception as e:
            logger.error(f"Failed to initialize weather for {location}: {e}")
            # Fallback data
            weather_data[location] = {
                'temperature_c': 25, 'temperature_f': 77,
                'wind_speed_ms': 5, 'wind_speed_kts': 9.7,
                'wind_direction': 90, 'cloud_cover': 50
            }
    return weather_data

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

def fetch_weather_for_all_locations(locations_config):
    """Fetch weather for all configured locations in parallel."""
    weather_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(locations_config), 4)) as executor:
        future_to_location = {
            executor.submit(fetch_weather, settings['lat'], settings['lon'], location): location 
            for location, settings in locations_config.items()
        }
        for future in concurrent.futures.as_completed(future_to_location):
            location = future_to_location[future]
            try:
                weather_data[location] = future.result()
            except Exception as e:
                logger.warning(f"Failed to fetch weather for {location}: {e}")
                weather_data[location] = {
                    'temperature_c': 25, 'temperature_f': 77,
                    'wind_speed_ms': 5, 'wind_speed_kts': 9.7,
                    'wind_direction': 90, 'cloud_cover': 50
                }
    return weather_data

def perform_full_dashboard_data_load(locations_config, status_callback=None):
    """Orchestrate parallel fetch of launches, F1, and weather data."""
    def _emit(msg):
        if status_callback:
            try: status_callback(msg)
            except: pass

    _emit("Checking launch cache and fetching SpaceX data…")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Launch data
        def _fetch_l():
            try: return fetch_launches()
            except: return {'previous': [], 'upcoming': []}
        
        # F1 data
        def _fetch_f1():
            _emit("Checking F1 caches and schedule…")
            try: return fetch_f1_data()
            except: return {'schedule': [], 'driver_standings': [], 'constructor_standings': []}
            
        # Weather data
        def _fetch_w():
            _emit("Getting live weather for locations…")
            return fetch_weather_for_all_locations(locations_config)
            
        # Narratives
        def _fetch_n():
            _emit("Fetching launch narratives…")
            return fetch_narratives()

        f_launch = executor.submit(_fetch_l)
        f_f1 = executor.submit(_fetch_f1)
        f_weather = executor.submit(_fetch_w)
        f_narratives = executor.submit(_fetch_n)
        
        launch_data = f_launch.result()
        f1_data = f_f1.result()
        weather_data = f_weather.result()
        narratives = f_narratives.result()

    _emit("Data loading complete")
    return launch_data, f1_data, weather_data, narratives

def setup_dashboard_environment():
    """Set environment variables for Qt and hardware acceleration."""
    if platform.system() == 'Windows':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl "
            "--disable-web-security --allow-running-insecure-content "
            "--disable-gpu-sandbox --disable-software-rasterizer "
            "--disable-gpu-driver-bug-workarounds --no-sandbox "
            "--autoplay-policy=no-user-gesture-required "
            "--disable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
        )
    elif platform.system() == 'Linux':
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--enable-gpu --ignore-gpu-blocklist --enable-webgl "
            "--disable-gpu-sandbox --no-sandbox --use-gl=egl "
            "--disable-web-security --allow-running-insecure-content "
            "--gpu-testing-vendor-id=0xFFFF --gpu-testing-device-id=0xFFFF "
            "--disable-gpu-driver-bug-workarounds "
            "--autoplay-policy=no-user-gesture-required "
            "--disable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure"
        )
    else:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu --enable-webgl --disable-web-security"

    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
    os.environ["QSG_RHI_BACKEND"] = "gl"
    
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

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        # Log the log path immediately to stdout
        print(f"LOGGING TO: {os.path.abspath(log_file)}")
        logger.info(f"LOGGING INITIALIZED: {os.path.abspath(log_file)}")
        return os.path.abspath(log_file)
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
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
            key=lambda x: parse(x['net'])
        )
    except Exception:
        upcoming_sorted = upcoming

    for launch in upcoming_sorted:
        try:
            launch_time = parse(launch['net']).replace(tzinfo=pytz.UTC)
        except Exception:
            continue

        # Pre‑launch window: within next hour
        if current_time <= launch_time <= current_time + timedelta(hours=1):
            return True

        # Ongoing/post‑T0: keep tray visible while status != Success
        if launch_time <= current_time and (launch.get('status') or '').lower() != 'success':
            return True

    return False

def get_countdown_string(launch_data, f1_schedule, mode, next_launch, next_race, tz_obj):
    """Generate a formatted countdown string for the dashboard."""
    if mode == 'spacex':
        upcoming = launch_data.get('upcoming', [])
        try:
            upcoming_sorted = sorted(
                [l for l in upcoming if l.get('time') != 'TBD' and l.get('net')],
                key=lambda x: parse(x['net'])
            )
        except Exception:
            upcoming_sorted = upcoming

        now_utc = datetime.now(pytz.UTC)
        # Check for ongoing/just-launched
        for l in upcoming_sorted:
            try:
                lt_utc = parse(l['net']).replace(tzinfo=pytz.UTC)
            except Exception:
                continue
            status = (l.get('status') or '').lower()
            if lt_utc <= now_utc and status != 'success':
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
            launch_time = parse(next_launch['net']).replace(tzinfo=pytz.UTC).astimezone(tz_obj)
            current_time = datetime.now(tz_obj)
            delta = launch_time - current_time
            total_seconds = int(max(delta.total_seconds(), 0))
            days, rem = divmod(total_seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        except Exception:
            return "T- Error"
    else:
        # F1 Countdown
        if not next_race:
            return "No upcoming races"
        try:
            race_time = parse(next_race['date_start']).replace(tzinfo=pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            delta = race_time - current_time
            total_seconds = int(max(delta.total_seconds(), 0)) # seconds includes days but capped at 1 day
            # Use delta.days and delta.seconds separately
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s to {next_race['country_name']}"
        except Exception:
            return "T- Race Error"

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

def perform_bootstrap_diagnostics(src_dir, wifi_connected_state=True):
    """Perform bootstrap network and update checks in parallel."""
    connectivity_result = test_network_connectivity(wifi_connected_state)
    update_available = False
    current_info = {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}
    latest_info = {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}

    try:
        current_info = get_git_version_info(src_dir) or current_info
    except: pass

    if connectivity_result:
        try:
            current_hash = current_info.get('hash', '')
            update_available, latest_info = check_github_for_updates(current_hash)
            latest_info = latest_info or current_info
        except: pass

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
