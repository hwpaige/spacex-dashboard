"""
Shared helper functions extracted from app.py.

This module intentionally contains only UI-agnostic utilities so it can be
imported from both production code and tests without pulling in Qt.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime

import numpy as np
import pytz
import requests
from dateutil.parser import parse
from track_generator import generate_track_map

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

# Different refresh intervals for different F1 data types
CACHE_REFRESH_INTERVAL_F1_SCHEDULE = 86400  # 24 hours for race schedule (rarely changes)
CACHE_REFRESH_INTERVAL_F1_STANDINGS = 3600  # 1 hour for standings (updates frequently)

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

            # Method 1: Try nmcli first
            logger.debug("BOOT: Trying nmcli device status...")
            try:
                result = subprocess.run(['nmcli', 'device', 'status'],
                                      capture_output=True, text=True, timeout=5)

                logger.debug(f"BOOT: nmcli device status return code: {result.returncode}")
                if result.returncode != 0:
                    logger.warning(f"BOOT: nmcli device status failed with return code {result.returncode}")
                    logger.debug(f"BOOT: nmcli stderr: {result.stderr}")

                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    logger.debug(f"BOOT: nmcli output has {len(lines)} lines")
                    for line in lines:
                        logger.debug(f"BOOT: nmcli line: '{line}'")
                        parts = line.split()
                        if len(parts) >= 4:
                            device_type = parts[1].lower()
                            state = parts[2].lower()
                            logger.debug(f"BOOT: nmcli device: {parts[0]}, type: {device_type}, state: {state}")
                            if device_type == 'wifi' and state == 'connected':
                                connected = True
                                logger.info("BOOT: Linux WiFi connected via nmcli device status")
                                break

                # Get current SSID if connected via nmcli
                if connected:
                    logger.debug("BOOT: Getting SSID from nmcli...")
                    connected_device = None
                    for line in result.stdout.split('\n'):
                        parts = line.split()
                        if len(parts) >= 4 and parts[1].lower() == 'wifi' and parts[2].lower() == 'connected':
                            connected_device = parts[0]
                            logger.debug(f"BOOT: Found connected WiFi device: {connected_device}")
                            break

                    if connected_device:
                        ssid_result = subprocess.run(['nmcli', '-t', '-f', 'active,ssid', 'device', connected_device],
                                                   capture_output=True, text=True, timeout=5)
                        logger.debug(f"BOOT: nmcli SSID command return code: {ssid_result.returncode}")
                        if ssid_result.returncode == 0:
                            for line in ssid_result.stdout.split('\n'):
                                logger.debug(f"BOOT: nmcli SSID line: '{line}'")
                                if line.startswith('yes:'):
                                    current_ssid = line.split(':', 1)[1].strip()
                                    logger.info(f"BOOT: Linux WiFi SSID from nmcli: '{current_ssid}'")
                                    break
                        else:
                            logger.warning(f"BOOT: nmcli SSID command failed: {ssid_result.stderr}")
                    else:
                        logger.debug("BOOT: No connected device found, trying active connections...")
                        # Fallback to active connections
                        ssid_result = subprocess.run(['nmcli', '-t', '-f', 'name', 'connection', 'show', '--active'],
                                                   capture_output=True, text=True, timeout=5)
                        logger.debug(f"BOOT: nmcli active connections return code: {ssid_result.returncode}")
                        if ssid_result.returncode == 0:
                            connections = ssid_result.stdout.strip().split('\n')
                            logger.debug(f"BOOT: Active connections: {connections}")
                            if connections and connections[0]:
                                current_ssid = connections[0]
                                logger.info(f"BOOT: Linux WiFi SSID from active connections: '{current_ssid}'")

            except Exception as e:
                logger.debug(f"BOOT: nmcli method failed: {e}")
                # Try iwgetid as fallback
                try:
                    logger.debug("BOOT: Trying iwgetid...")
                    ssid_result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=5)
                    logger.debug(f"BOOT: iwgetid return code: {ssid_result.returncode}")
                    if ssid_result.returncode == 0:
                        current_ssid = ssid_result.stdout.strip()
                        logger.info(f"BOOT: Linux WiFi SSID via iwgetid: '{current_ssid}'")
                    else:
                        logger.debug(f"BOOT: iwgetid failed: {ssid_result.stderr}")
                except Exception as e:
                    logger.debug(f"BOOT: iwgetid failed: {e}")

            logger.info(f"BOOT: Linux WiFi check result - Connected: {connected}, SSID: '{current_ssid}'")
            return connected, current_ssid

    except Exception as e:
        logger.error(f"BOOT: Error checking WiFi status: {e}")
        logger.error(f"BOOT: Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"BOOT: Traceback: {traceback.format_exc()}")
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
