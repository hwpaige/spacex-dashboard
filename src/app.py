import sys
import requests
import os
import json
import platform
import fastf1
import numpy as np
import pandas as pd
import shlex
import math
import concurrent.futures
import urllib.request
import urllib.error
import socket
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
from cryptography.fernet import Fernet
from track_generator import generate_track_map
from plotly_charts import generate_f1_standings_chart
import http.server
import socketserver
import threading
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
try:
    # Try to write to app.log in the docs directory
    log_file_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'app.log')

    # If we can't write to the docs directory, try /tmp
    if not os.access(os.path.dirname(log_file_path), os.W_OK):
        log_file_path = '/tmp/spacex_dashboard_app.log'
        print(f"Using log file: {log_file_path}")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, mode='w', encoding='utf-8'),  # Overwrite log file at each launch
            logging.StreamHandler(sys.stdout)
        ]
    )
    print(f"Logging to: {log_file_path}")

except (OSError, PermissionError) as e:
    print(f"Warning: Cannot set up file logging: {e}, using console only")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
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

# Ensure file handler uses UTF-8 and proper path
try:
    # Try to write to app.log in the current directory first
    log_file_path = os.path.join(os.path.dirname(__file__), 'app.log')

    # If we can't write to the current directory, try /tmp
    if not os.access(os.path.dirname(log_file_path), os.W_OK):
        log_file_path = '/tmp/spacex_dashboard_app.log'
        print(f"Using log file: {log_file_path}")

    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    print(f"File logging to: {log_file_path}")

except (OSError, PermissionError) as e:
    print(f"Warning: Cannot set up file logging: {e}, skipping file handler")
    file_handler = None

if file_handler:
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
CACHE_FILE_PREVIOUS = os.path.join(os.path.dirname(__file__), '..', 'cache', 'previous_launches_cache.json')
CACHE_FILE_PREVIOUS_BACKUP = os.path.join(os.path.dirname(__file__), '..', 'cache', 'previous_launches_cache_backup.json')
CACHE_FILE_UPCOMING = os.path.join(os.path.dirname(__file__), '..', 'cache', 'upcoming_launches_cache.json')

# Cache for F1 data - moved to persistent location outside git repo
CACHE_DIR_F1 = os.path.expanduser('~/.cache/spacex-dashboard')  # Persistent cache directory
os.makedirs(CACHE_DIR_F1, exist_ok=True)
CACHE_FILE_F1_SCHEDULE = os.path.join(CACHE_DIR_F1, 'f1_schedule_cache.json')
CACHE_FILE_F1_DRIVERS = os.path.join(CACHE_DIR_F1, 'f1_drivers_cache.json')
CACHE_FILE_F1_CONSTRUCTORS = os.path.join(CACHE_DIR_F1, 'f1_constructors_cache.json')

# Different refresh intervals for different F1 data types
CACHE_REFRESH_INTERVAL_F1_SCHEDULE = 86400  # 24 hours for race schedule (rarely changes)
CACHE_REFRESH_INTERVAL_F1_STANDINGS = 3600  # 1 hour for standings (updates frequently)

f1_cache = None

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

# Load cache from file
def load_cache_from_file(cache_file):
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                cache_data['timestamp'] = datetime.fromisoformat(cache_data['timestamp']).replace(tzinfo=pytz.UTC)
                return cache_data
    except (OSError, PermissionError, json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to load cache from {cache_file}: {e}")
    return None

# Save cache to file
def save_cache_to_file(cache_file, data, timestamp):
    try:
        cache_data = {'data': data, 'timestamp': timestamp.isoformat()}
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
    except (OSError, PermissionError) as e:
        logger.warning(f"Failed to save cache to {cache_file}: {e}")

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
                logger.warning(f"BOOT: nmcli status check failed: {e}, trying fallback methods...")

            # Method 2: Check IP address and interface status
            if not connected:
                logger.debug("BOOT: nmcli failed, checking IP addresses on common interfaces...")
                interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
                has_ip = False
                active_interface = None

                for interface in interfaces:
                    try:
                        logger.debug(f"BOOT: Checking interface {interface}...")
                        # Check if interface has an IP address
                        result = subprocess.run(['ip', 'addr', 'show', interface],
                                              capture_output=True, text=True, timeout=5)

                        logger.debug(f"BOOT: ip addr show {interface} return code: {result.returncode}")
                        if result.returncode == 0:
                            has_inet = 'inet ' in result.stdout
                            has_up = 'UP' in result.stdout
                            logger.debug(f"BOOT: {interface} - has inet: {has_inet}, has UP: {has_up}")
                            if has_inet and has_up:
                                has_ip = True
                                active_interface = interface
                                logger.info(f"BOOT: Linux WiFi interface {interface} has IP address and is UP")
                                break
                        else:
                            logger.debug(f"BOOT: ip addr command failed for {interface}: {result.stderr}")
                    except Exception as e:
                        logger.debug(f"BOOT: Error checking {interface}: {e}")
                        continue

                if has_ip:
                    connected = True
                    logger.info("BOOT: Linux WiFi connected via IP address check")

                    # Method 3: Try iw to get SSID
                    if active_interface:
                        logger.debug(f"BOOT: Trying iw dev {active_interface} link...")
                        try:
                            iw_result = subprocess.run(['iw', 'dev', active_interface, 'link'],
                                                     capture_output=True, text=True, timeout=5)
                            logger.debug(f"BOOT: iw command return code: {iw_result.returncode}")
                            if iw_result.returncode == 0 and 'SSID:' in iw_result.stdout:
                                ssid_match = re.search(r'SSID:\s*(.+)', iw_result.stdout)
                                if ssid_match:
                                    current_ssid = ssid_match.group(1).strip()
                                    logger.info(f"BOOT: Linux WiFi SSID via iw: '{current_ssid}'")
                            else:
                                logger.debug(f"BOOT: iw command output: {iw_result.stdout}")
                        except Exception as e:
                            logger.debug(f"BOOT: iw link check failed: {e}")

                        # Method 4: Try iwgetid as fallback
                        if not current_ssid:
                            logger.debug("BOOT: iw failed, trying iwgetid...")
                            try:
                                ssid_result = subprocess.run(['iwgetid', '-r'],
                                                           capture_output=True, text=True, timeout=5)
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

# Fetch SpaceX launch data
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
        previous_cache = load_cache_from_file(CACHE_FILE_PREVIOUS)
        upcoming_cache = load_cache_from_file(CACHE_FILE_UPCOMING)
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

    # Load previous launches cache (source of truth - only add new launches)
    previous_cache = load_cache_from_file(CACHE_FILE_PREVIOUS)
    if previous_cache:
        previous_launches = previous_cache['data']
        logger.info(f"Loaded {len(previous_launches)} previous launches from cache")
        
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
                save_cache_to_file(CACHE_FILE_PREVIOUS, previous_launches, current_time)
                logger.info(f"Added {len(new_launches)} new launches to cache")
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
            save_cache_to_file(CACHE_FILE_PREVIOUS, previous_launches, current_time)
        else:
            logger.error("Both main and backup caches are unavailable, using fallback data")
            previous_launches = [
                {'mission': 'Starship Flight 7', 'date': '2025-01-15', 'time': '12:00:00', 'net': '2025-01-15T12:00:00Z', 'status': 'Success', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': 'https://www.youtube.com/embed/videoseries?si=rvwtzwj_URqw2dtK&controls=0&list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY'},
                {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
            ]

    # Load upcoming launches cache
    upcoming_cache = load_cache_from_file(CACHE_FILE_UPCOMING)
    if upcoming_cache and (current_time - upcoming_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_UPCOMING:
        upcoming_launches = upcoming_cache['data']
        logger.info("Using persistent cached upcoming launches")
    else:
        try:
            logger.info("Fetching fresh upcoming launches from API")
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
            logger.info(f"Successfully fetched and saved {len(upcoming_launches)} upcoming launches")
        except Exception as e:
            logger.error(f"LL2 API error for upcoming launches: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            upcoming_launches = []

    return {'previous': previous_launches, 'upcoming': upcoming_launches}

# Fetch F1 data with optimized component-based caching
def fetch_f1_data():
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
    schedule_cache = load_cache_from_file(CACHE_FILE_F1_SCHEDULE)
    if schedule_cache and (current_time - schedule_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_SCHEDULE:
        f1_data['schedule'] = schedule_cache['data']
        logger.info("Using cached F1 schedule data")
    else:
        logger.info("Fetching fresh F1 schedule data")
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

                # Generate track map
                track_map_path = generate_track_map(race['circuit']['circuitName'])
                # Sanitize circuit name for filename (same as in track_generator.py)
                safe_circuit_name = race['circuit']['circuitName'].replace('|', '-').replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', '-').replace('<', '-').replace('>', '-')
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

        except Exception as e:
            logger.error(f"Failed to fetch F1 schedule: {e}")
            f1_data['schedule'] = []

    # Fetch driver standings (frequently changing)
    drivers_cache = load_cache_from_file(CACHE_FILE_F1_DRIVERS)
    if drivers_cache and (current_time - drivers_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_STANDINGS:
        f1_data['driver_standings'] = drivers_cache['data']
        logger.info("Using cached F1 driver standings")
    else:
        logger.info("Fetching fresh F1 driver standings")
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
                    standing['Constructor'] = {
                        'name': standing['team']['teamName'],
                        'constructorId': standing['teamId'],
                        'nationality': standing['team']['country']
                    }

            f1_data['driver_standings'] = driver_standings
            save_cache_to_file(CACHE_FILE_F1_DRIVERS, driver_standings, current_time)
            logger.info(f"Cached F1 driver standings with {len(driver_standings)} drivers")

        except Exception as e:
            logger.error(f"Failed to fetch F1 driver standings: {e}")
            f1_data['driver_standings'] = []

    # Fetch constructor standings (frequently changing)
    constructors_cache = load_cache_from_file(CACHE_FILE_F1_CONSTRUCTORS)
    if constructors_cache and (current_time - constructors_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL_F1_STANDINGS:
        f1_data['constructor_standings'] = constructors_cache['data']
        logger.info("Using cached F1 constructor standings")
    else:
        logger.info("Fetching fresh F1 constructor standings")
        try:
            url = "https://f1api.dev/api/current/constructors-championship"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            constructor_standings = data.get('constructors_championship', [])

            # Normalize
            for standing in constructor_standings:
                if 'team' in standing and 'Constructor' not in standing:
                    standing['Constructor'] = {
                        'name': standing['team']['teamName'],
                        'constructorId': standing['teamId'],
                        'nationality': standing['team']['country']
                    }

            f1_data['constructor_standings'] = constructor_standings
            save_cache_to_file(CACHE_FILE_F1_CONSTRUCTORS, constructor_standings, current_time)
            logger.info(f"Cached F1 constructor standings with {len(constructor_standings)} teams")

        except Exception as e:
            logger.error(f"Failed to fetch F1 constructor standings: {e}")
            f1_data['constructor_standings'] = []

    f1_cache = f1_data
    logger.info("Successfully assembled F1 data from optimized cache")
    return f1_data

# Fetch weather data
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

# Track rotations for F1 circuits
track_rotations = [('Sakhir', 92.0), ('Jeddah', 104.0), ('Melbourne', 44.0), ('Baku', 357.0), ('Miami', 2.0), ('Monte Carlo', 62.0), ('Catalunya', 95.0), ('Montreal', 62.0), ('Silverstone', 92.0), ('Hungaroring', 40.0), ('Spa-Francorchamps', 91.0), ('Zandvoort', 0.0), ('Monza', 95.0), ('Singapore', 335.0), ('Suzuka', 49.0), ('Lusail', 61.0), ('Austin', 0.0), ('Mexico City', 36.0), ('Interlagos', 0.0), ('Las Vegas', 90.0), ('Yas Marina Circuit', 335.0)]

# Rotation function
def rotate(xy, *, angle):
    rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                        [-np.sin(angle), np.cos(angle)]])
    return np.matmul(xy, rot_mat)

# Location settings
location_settings = {
    'Starbase': {'lat': 25.9975, 'lon': -97.1566, 'timezone': 'America/Chicago'},
    'Vandy': {'lat': 34.632, 'lon': -120.611, 'timezone': 'America/Los_Angeles'},
    'Cape': {'lat': 28.392, 'lon': -80.605, 'timezone': 'America/New_York'},
    'Hawthorne': {'lat': 33.916, 'lon': -118.352, 'timezone': 'America/Los_Angeles'}
}

# Radar URLs - Enable for all platforms including Raspberry Pi
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
    TrackMapPathRole = Qt.ItemDataRole.UserRole + 19

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
                elif role == self.TrackMapPathRole:
                    return item.get('track_map_path', '')
                elif role == self.LocalTimeRole:
                    return item.get('localTime', 'TBD')
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
        roles[self.TrackMapPathRole] = b"trackMapPath"
        return roles

    def update_data(self):
        self.beginResetModel()
        today = datetime.now(pytz.UTC).date()
        this_week_end = today + timedelta(days=7)
        last_week_start = today - timedelta(days=7)
        grouped = []
        if self._mode == 'spacex':
            launches = self._data['upcoming'] if self._event_type == 'upcoming' else self._data['previous']
            
            # Add local time to each launch
            for launch in launches:
                net = launch.get('net', '') or launch.get('date_start', '')
                if net:
                    try:
                        launch['localTime'] = parse(net).astimezone(self._tz).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        launch['localTime'] = 'TBD'
                else:
                    launch['localTime'] = 'TBD'
            
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
            # Use the data passed to the model instead of fetching fresh data
            races = self._data
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
    statusUpdate = pyqtSignal(str)

    def run(self):
        logger.info("DataLoader: Starting parallel data loading...")
        self.statusUpdate.emit("Fetching SpaceX launch data...")
        
        # Function to fetch launch data
        def fetch_launch_data():
            try:
                logger.info("DataLoader: Calling fetch_launches...")
                launch_data = fetch_launches()
                logger.info(f"DataLoader: fetch_launches returned {len(launch_data.get('upcoming', []))} upcoming launches")
                return launch_data
            except Exception as e:
                logger.error(f"DataLoader: fetch_launches failed: {e}")
                return {'previous': [], 'upcoming': []}
        
        # Function to fetch F1 data
        def fetch_f1_data_wrapper():
            try:
                self.statusUpdate.emit("Loading F1 race schedule...")
                return fetch_f1_data()
            except Exception as e:
                logger.error(f"DataLoader: fetch_f1_data failed: {e}")
                return {'schedule': [], 'driver_standings': [], 'constructor_standings': []}
        
        # Function to fetch weather data
        def fetch_weather_data():
            self.statusUpdate.emit("Getting weather data...")
            weather_data = {}
            for location, settings in location_settings.items():
                try:
                    weather = fetch_weather(settings['lat'], settings['lon'], location)
                    weather_data[location] = weather
                    logger.info(f"DataLoader: Fetched weather for {location}")
                except Exception as e:
                    logger.warning(f"DataLoader: Failed to fetch weather for {location}: {e}")
                    weather_data[location] = {
                        'temperature_c': 25,
                        'temperature_f': 77,
                        'wind_speed_ms': 5,
                        'wind_speed_kts': 9.7,
                        'wind_direction': 90,
                        'cloud_cover': 50
                    }
            return weather_data
        
        # Run all API calls in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all tasks
            launch_future = executor.submit(fetch_launch_data)
            f1_future = executor.submit(fetch_f1_data_wrapper)
            weather_future = executor.submit(fetch_weather_data)
            
            # Wait for all to complete and get results
            launch_data = launch_future.result()
            f1_data = f1_future.result()
            weather_data = weather_future.result()
        
        self.statusUpdate.emit("Data loading complete")
        logger.info("DataLoader: Finished loading all data in parallel")
        self.finished.emit(launch_data, f1_data, weather_data)

class LaunchUpdater(QObject):
    finished = pyqtSignal(dict)

    def run(self):
        launch_data = fetch_launches()
        self.finished.emit(launch_data)

class WeatherUpdater(QObject):
    finished = pyqtSignal(dict)

    def run(self):
        weather_data = {}
        for location, settings in location_settings.items():
            try:
                weather = fetch_weather(settings['lat'], settings['lon'], location)
                weather_data[location] = weather
                logger.info(f"Weather updated for {location}: {weather}")
            except Exception as e:
                logger.error(f"Failed to update weather for {location}: {e}")
                # Provide fallback data
                weather_data[location] = {
                    'temperature_c': 25,
                    'temperature_f': 77,
                    'wind_speed_ms': 5,
                    'wind_speed_kts': 9.7,
                    'wind_direction': 90,
                    'cloud_cover': 50
                }
        self.finished.emit(weather_data)

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
    rememberedNetworksChanged = pyqtSignal()
    loadingFinished = pyqtSignal()
    updateGlobeTrajectory = pyqtSignal()
    reloadWebContent = pyqtSignal()
    launchTrayVisibilityChanged = pyqtSignal()
    loadingStatusChanged = pyqtSignal()
    updateAvailableChanged = pyqtSignal()

    def __init__(self, initial_wifi_connected=False, initial_wifi_ssid=""):
        super().__init__()
        logger.info("Backend initializing...")
        self._mode = 'spacex'
        self._event_type = 'upcoming'
        self._theme = 'dark'
        self._location = 'Starbase'
        self._chart_view_mode = 'actual'  # 'actual' or 'cumulative'
        self._chart_type = 'line'  # 'bar' or 'line'
        self._f1_chart_stat = 'points'  # 'points', 'wins', etc.
        self._f1_chart_type = 'standings'  # 'standings', 'weather', 'telemetry', etc.
        self._f1_standings_type = 'drivers'  # 'drivers' or 'constructors'
        self._isLoading = True
        self._loading_status = "Initializing..."
        self._launch_data = {'previous': [], 'upcoming': []}
        self._f1_data = {'schedule': [], 'driver_standings': [], 'constructor_standings': []}
        self._weather_data = {}
        self._tz = pytz.timezone(location_settings[self._location]['timezone'])
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self._launch_trends_cache = {}  # Cache for launch trends series
        self._update_available = False
        self._launch_tray_manual_override = None  # None = auto, True = show, False = hide
        
        # WiFi properties - initialize with provided values
        self._wifi_networks = []
        self._wifi_connected = initial_wifi_connected
        self._wifi_connecting = False
        self._current_wifi_ssid = initial_wifi_ssid
        self._remembered_networks = self.load_remembered_networks()
        self._last_connected_network = self.load_last_connected_network()

        # DataLoader will be started after WiFi check in main startup
        self.loader = None
        self.thread = None
        self._data_loading_deferred = False

        logger.info(f"Initial WiFi status: connected={initial_wifi_connected}, ssid='{initial_wifi_ssid}'")
        logger.info("Setting up timers...")

    def get_encryption_key(self):
        """Get or create encryption key for WiFi passwords"""
        key_file = os.path.join(os.path.dirname(__file__), '..', 'cache', 'wifi_key.bin')
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate a new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions on Linux
            if platform.system() != 'Windows':
                try:
                    os.chmod(key_file, 0o600)
                except:
                    pass
            return key

    def encrypt_password(self, password):
        """Encrypt a password"""
        if not password:
            return None
        f = Fernet(self.get_encryption_key())
        return f.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted_password):
        """Decrypt a password"""
        if not encrypted_password:
            return None
        try:
            f = Fernet(self.get_encryption_key())
            return f.decrypt(encrypted_password.encode()).decode()
        except:
            return None

    def get_wifi_interface(self):
        """Get the WiFi interface name"""
        try:
            # Try nmcli first
            device_result = subprocess.run(['nmcli', 'device', 'status'], capture_output=True, text=True, timeout=5)
            if device_result.returncode == 0:
                for line in device_result.stdout.split('\n'):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].lower() == 'wifi':
                        return parts[0]
            
            # Fallback to common interface names
            import os
            for iface in ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']:
                if os.path.exists(f'/sys/class/net/{iface}'):
                    return iface
        except Exception as e:
            logger.debug(f"Error detecting WiFi interface: {e}")
        
        return 'wlan0'  # Default fallback

    def load_remembered_networks(self):
        """Load remembered WiFi networks from file"""
        try:
            remembered_file = os.path.join(os.path.dirname(__file__), '..', 'cache', 'remembered_networks.json')
            if os.path.exists(remembered_file):
                with open(remembered_file, 'r', encoding='utf-8') as f:
                    networks = json.load(f)
                    # Decrypt passwords
                    for network in networks:
                        if 'password' in network and network['password']:
                            network['password'] = self.decrypt_password(network['password'])
                    return networks
            return []
        except Exception as e:
            logger.error(f"Error loading remembered networks: {e}")
            return []

    def save_remembered_networks(self):
        """Save remembered WiFi networks to file"""
        try:
            remembered_file = os.path.join(os.path.dirname(__file__), '..', 'cache', 'remembered_networks.json')
            # Encrypt passwords before saving
            networks_to_save = []
            for network in self._remembered_networks:
                network_copy = network.copy()
                if 'password' in network_copy and network_copy['password']:
                    network_copy['password'] = self.encrypt_password(network_copy['password'])
                networks_to_save.append(network_copy)
            with open(remembered_file, 'w', encoding='utf-8') as f:
                json.dump(networks_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving remembered networks: {e}")

    def add_remembered_network(self, ssid, password=None):
        """Add a network to remembered networks"""
        # Remove if already exists
        self._remembered_networks = [n for n in self._remembered_networks if n['ssid'] != ssid]
        # Add to front
        self._remembered_networks.insert(0, {'ssid': ssid, 'password': password})
        # Keep only last 10
        self._remembered_networks = self._remembered_networks[:10]
        self.save_remembered_networks()
        self.rememberedNetworksChanged.emit()

    def remove_remembered_network(self, ssid):
        """Remove a network from remembered networks"""
        self._remembered_networks = [n for n in self._remembered_networks if n['ssid'] != ssid]
        self.save_remembered_networks()
        self.rememberedNetworksChanged.emit()

    def reload_web_content(self):
        """Signal QML to reload all web-based content (globe, charts, etc.) when WiFi connects"""
        try:
            logger.info("Signaling QML to reload web content after WiFi connection...")
            self.reloadWebContent.emit()
            logger.info("Web content reload signal sent")
            
        except Exception as e:
            logger.error(f"Error signaling web content reload: {e}")

    def load_last_connected_network(self):
        """Load the last connected network from file"""
        try:
            last_connected_file = os.path.join(os.path.dirname(__file__), '..', 'cache', 'last_connected_network.json')
            if os.path.exists(last_connected_file):
                with open(last_connected_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading last connected network: {e}")
        return None

    def save_last_connected_network(self, ssid):
        """Save the last connected network to file"""
        try:
            last_connected_file = os.path.join(os.path.dirname(__file__), '..', 'cache', 'last_connected_network.json')
            with open(last_connected_file, 'w', encoding='utf-8') as f:
                json.dump({'ssid': ssid, 'timestamp': time.time()}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving last connected network: {e}")

    def _try_nmcli_connection(self, ssid, password, wifi_device):
        """Try to connect using nmcli as fallback"""
        # Check if nmcli is available
        nmcli_check = subprocess.run(['which', 'nmcli'], capture_output=True, timeout=5)
        if nmcli_check.returncode != 0:
            logger.error("nmcli not found. Please install network-manager: sudo apt install network-manager")
            return False

        logger.info(f"Trying nmcli connection to: {ssid}")

        # Check what networks nmcli can see
        # First rescan to ensure nmcli has fresh data
        rescan_cmd = ['nmcli', 'device', 'wifi', 'rescan']
        if wifi_device:
            rescan_cmd.extend(['ifname', wifi_device])
        rescan_result = subprocess.run(rescan_cmd, capture_output=True, text=True, timeout=10)
        if rescan_result.returncode != 0:
            logger.debug(f"nmcli rescan failed: {rescan_result.stderr}")
        
        # Wait a moment for rescan to complete
        time.sleep(3)
        
        # List networks with specific interface
        list_cmd = ['nmcli', 'device', 'wifi', 'list']
        if wifi_device:
            list_cmd.extend(['ifname', wifi_device])
        list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10)
        logger.debug(f"nmcli wifi list output: {list_result.stdout}")
        
        # Parse the output to find SSIDs
        available_networks = []
        lines = list_result.stdout.strip().split('\n')
        if lines:
            # Skip header line
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 1:
                    # SSID is usually the last column
                    ssid_candidate = parts[-1] if parts else ""
                    if ssid_candidate and ssid_candidate != '--' and ssid_candidate != 'SSID':
                        available_networks.append(ssid_candidate)
        
        logger.debug(f"Parsed available networks: {available_networks}")
        
        if ssid not in available_networks:
            logger.warning(f"Network '{ssid}' not found in nmcli wifi list. Available networks: {available_networks}")
            return False

        # Connect to the new network
        # Use shlex.quote to properly escape the SSID and password for shell
        if password:
            # For networks with password
            cmd = f'nmcli device wifi connect {shlex.quote(ssid)} password {shlex.quote(password)}'
            if wifi_device:
                cmd += f' ifname {wifi_device}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        else:
            # For open networks
            cmd = f'nmcli device wifi connect {shlex.quote(ssid)}'
            if wifi_device:
                cmd += f' ifname {wifi_device}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            logger.info(f"Successfully connected to {ssid} using nmcli")
            return True
        else:
            logger.error(f"nmcli connection failed: {result.stderr}")
            return False

    def startDataLoader(self):
        """Start the data loading thread after WiFi check completes"""
        logger.info("BOOT: startDataLoader called")
        self.setLoadingStatus("Checking network connectivity...")

        # Check network connectivity before starting data loading
        logger.info("BOOT: Checking network connectivity before starting data loading...")
        connectivity_result = self.check_network_connectivity()
        logger.info(f"BOOT: Network connectivity check result: {connectivity_result}")

        # Check for updates if we have network connectivity
        logger.info("BOOT: Checking for app updates...")
        try:
            update_available = self.check_for_updates()
            self.updateAvailable = update_available
            logger.info(f"BOOT: Update check result: {update_available}")
        except Exception as e:
            logger.error(f"BOOT: Error checking for updates: {e}")
            self.updateAvailable = False

        if not connectivity_result:
            logger.warning("BOOT: No network connectivity detected - deferring data loading")
            logger.info("BOOT: Setting _data_loading_deferred = True")
            self.setLoadingStatus("No network connection - using cached data")
            # Set a flag to indicate data loading is deferred
            self._data_loading_deferred = True
            # Set up a loading timeout timer to prevent indefinite loading screen
            logger.info("BOOT: Creating loading timeout timer (15 seconds)")
            self._loading_timeout_timer = QTimer(self)
            self._loading_timeout_timer.setSingleShot(True)
            self._loading_timeout_timer.timeout.connect(self._on_loading_timeout)
            self._loading_timeout_timer.start(15000)  # 15 second timeout
            logger.info("BOOT: Loading timeout timer started (15 seconds)")
            # Set up timers anyway (they will check connectivity when they run)
            self._setup_timers()
            logger.info("BOOT: Data loading deferred - app will show cached data after timeout")
            return

        # Clear deferred flag if we have connectivity
        logger.info("BOOT: Network connectivity available - clearing deferred flag")
        self._data_loading_deferred = False
        self.setLoadingStatus("Loading SpaceX launch data...")

        if self.loader is None:
            logger.info("BOOT: Creating new DataLoader...")
            self.loader = DataLoader()
            self.thread = QThread()
            self.loader.moveToThread(self.thread)
            self.loader.finished.connect(self.on_data_loaded)
            self.loader.statusUpdate.connect(self.setLoadingStatus)
            self.thread.started.connect(self.loader.run)
            logger.info("BOOT: Starting DataLoader thread...")
            self.thread.start()
        else:
            logger.info("BOOT: DataLoader already exists")

        self._setup_timers()

    def _setup_timers(self):
        """Set up all the periodic timers"""
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

        # Update check timer - check every 6 hours (21600000 ms)
        self.update_check_timer = QTimer(self)
        self.update_check_timer.timeout.connect(self.check_for_updates_periodic)
        self.update_check_timer.start(21600000)  # 6 hours

    def check_for_updates_periodic(self):
        """Periodic update check"""
        try:
            update_available = self.check_for_updates()
            self.updateAvailable = update_available
            logger.info(f"Periodic update check result: {update_available}")
        except Exception as e:
            logger.error(f"Error in periodic update check: {e}")
        
    # ...existing code...
        
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
            self.launchTrayVisibilityChanged.emit()
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
            self.launchTrayVisibilityChanged.emit()

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
            self.launchTrayVisibilityChanged.emit()

    @pyqtProperty(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        if self._theme != value:
            self._theme = value
            self.themeChanged.emit()

    @pyqtProperty(bool, notify=launchTrayVisibilityChanged)
    def launchTrayVisible(self):
        if self._launch_tray_manual_override is not None:
            return self._launch_tray_manual_override
        
        # Auto mode: show if there's a launch within 1 hour
        if self._mode != 'spacex' or not self._launch_data.get('upcoming'):
            return False
            
        current_time = datetime.now(pytz.UTC)
        for launch in self._launch_data['upcoming']:
            if launch.get('time') == 'TBD':
                continue
            try:
                launch_time = parse(launch['net']).replace(tzinfo=pytz.UTC)
                if current_time <= launch_time <= current_time + timedelta(hours=1):
                    return True
            except:
                continue
        return False

    @pyqtProperty(bool, notify=launchTrayVisibilityChanged)
    def launchTrayManualMode(self):
        return self._launch_tray_manual_override is not None

    @pyqtSlot(bool)
    def setLaunchTrayManualMode(self, enabled):
        if enabled:
            self._launch_tray_manual_override = True
        else:
            self._launch_tray_manual_override = None
        self.launchTrayVisibilityChanged.emit()

    @pyqtProperty(bool, notify=loadingFinished)
    def isLoading(self):
        return self._isLoading

    @pyqtProperty(str, notify=loadingStatusChanged)
    def loadingStatus(self):
        return self._loading_status

    @pyqtSlot(str)
    def setLoadingStatus(self, status):
        if self._loading_status != status:
            self._loading_status = status
            self.loadingStatusChanged.emit()

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

    @pyqtProperty(list, notify=rememberedNetworksChanged)
    def rememberedNetworks(self):
        return self._remembered_networks

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
            launch_time = parse(next_launch['net']).replace(tzinfo=pytz.UTC).astimezone(self._tz)
            current_time = datetime.now(self._tz)
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
            return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s to {next_race['country_name']}"

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
        current_month = datetime.now(pytz.UTC).month
        df = df[df['date'].dt.year == current_year]
        rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
        df = df[df['rocket'].isin(rocket_types)]
        df['month'] = df['date'].dt.to_period('M').astype(str)
        df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
        df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)

        # Generate all months from January to current month
        all_months = []
        for month in range(1, current_month + 1):
            month_str = f"{current_year}-{month:02d}"
            all_months.append(month_str)

        return all_months

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
        current_month = datetime.now(pytz.UTC).month
        df = df[df['date'].dt.year == current_year]
        rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
        df = df[df['rocket'].isin(rocket_types)]
        df['month'] = df['date'].dt.to_period('M').astype(str)
        df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
        df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)

        # Generate all months from January to current month
        all_months = []
        for month in range(1, current_month + 1):
            month_str = f"{current_year}-{month:02d}"
            all_months.append(month_str)

        # Reindex the pivot table to include all months, filling missing ones with 0
        df_pivot = df_pivot.reindex(all_months, fill_value=0)

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

    @pyqtProperty(QVariant, notify=f1Changed)
    def driverStandingsOverTimeSeries(self):
        standings = self._f1_data['driver_standings']
        if not standings:
            return []
        
        # Get top 10 drivers
        top_drivers = standings[:10]
        stat_key = getattr(self, '_f1_chart_stat', 'points')
        
        # Group drivers by team and create series
        series_data = []
        team_drivers = {}
        
        for driver in top_drivers:
            team_id = driver.get('teamId', 'unknown')
            if team_id not in team_drivers:
                team_drivers[team_id] = []
            team_drivers[team_id].append(driver)
        
        # Create a series for each driver
        for team_id, drivers in team_drivers.items():
            team_color = F1_TEAM_COLORS.get(team_id, '#808080')  # Default grey
            for driver in drivers:
                driver_name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
                points = float(driver.get(stat_key, 0))
                series_data.append({
                    'label': driver_name,
                    'values': [points],  # Single point for now, can be expanded for historical data
                    'color': team_color,
                    'team': driver.get('Constructor', {}).get('name', team_id)
                })
        
        return series_data

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
    def f1ChartType(self):
        return getattr(self, '_f1_chart_type', 'standings')

    @f1ChartType.setter
    def f1ChartType(self, value):
        if self._f1_chart_type != value:
            self._f1_chart_type = value
            self.f1Changed.emit()

    @pyqtProperty(str, notify=f1Changed)
    def f1ChartUrl(self):
        """Generate URL for interactive Plotly chart HTML for F1 data"""
        logging.info("f1ChartUrl property accessed")
        chart_type = getattr(self, '_f1_chart_type', 'standings')
        logging.info(f"F1 chart URL: chart type = {chart_type}")
        
        try:
            if chart_type == 'standings':
                standings = self._f1_data['driver_standings']
                logging.info(f"F1 chart URL: standings count = {len(standings) if standings else 0}")
                if not standings:
                    logging.info("F1 chart URL: No standings data, returning placeholder")
                    return self._get_empty_chart_url()

                # Convert current standings data to format expected by plotly_charts
                driver_data = []
                stat_key = getattr(self, '_f1_chart_stat', 'points')

                # Get top 10 drivers
                top_drivers = standings[:10]
                logging.info(f"F1 chart URL: Processing {len(top_drivers)} drivers with stat '{stat_key}'")

                # For now, we'll show current standings as a single "round"
                # In the future, this could be expanded to show historical data
                for driver in top_drivers:
                    driver_name = f"{driver['Driver']['givenName']} {driver['Driver']['familyName']}"
                    points = float(driver.get(stat_key, 0))
                    driver_data.append({
                        'driver': driver_name,
                        'round': 1,  # Current round
                        'points': points
                    })

                plot_chart_type = getattr(self, '_chart_type', 'line')
                theme = getattr(self, '_theme', 'dark')
                logging.info(f"F1 chart URL: Generating {plot_chart_type} chart for {len(driver_data)} drivers")

                html = generate_f1_standings_chart(driver_data, plot_chart_type, theme)
            elif chart_type == 'telemetry':
                html = generate_f1_telemetry_chart(getattr(self, '_theme', 'dark'))
            elif chart_type == 'weather':
                html = generate_f1_weather_chart(getattr(self, '_theme', 'dark'))
            elif chart_type == 'positions':
                html = generate_f1_positions_chart(getattr(self, '_theme', 'dark'))
            elif chart_type == 'laps':
                html = generate_f1_laps_chart(getattr(self, '_theme', 'dark'))
            else:
                html = generate_f1_standings_chart([], 'line', getattr(self, '_theme', 'dark'))
            
            logging.info(f"F1 chart URL: Generated HTML length = {len(html)}")

            # Save to temporary file
            import tempfile
            import os
            temp_file = os.path.join(tempfile.gettempdir(), 'f1_chart.html')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html)

            file_url = f'file:///{temp_file.replace("\\", "/")}'
            logging.info(f"F1 chart URL: Saved to {file_url}")
            return file_url

        except Exception as e:
            logging.error(f"F1 chart URL error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return self._get_empty_chart_url()

    def _get_empty_chart_url(self):
        """Return URL for empty chart state"""
        try:
            html = self._get_empty_chart_html()
            import tempfile
            import os
            temp_file = os.path.join(tempfile.gettempdir(), 'f1_chart_empty.html')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html)
            return f'file:///{temp_file.replace("\\", "/")}'
        except Exception as e:
            logging.error(f"Error creating empty chart URL: {e}")
            return ""

    def _get_empty_chart_html(self):
        """Return HTML for empty chart state"""
        theme = getattr(self, '_theme', 'dark')
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
        </html>
        """

    @pyqtProperty(str, notify=f1Changed)
    def f1StandingsType(self):
        return getattr(self, '_f1_standings_type', 'drivers')

    @f1StandingsType.setter
    def f1StandingsType(self, value):
        if self._f1_standings_type != value:
            self._f1_standings_type = value
            self.f1Changed.emit()

    @pyqtProperty(bool, notify=updateAvailableChanged)
    def updateAvailable(self):
        return self._update_available

    @updateAvailable.setter
    def updateAvailable(self, value):
        if self._update_available != value:
            self._update_available = value
            self.updateAvailableChanged.emit()

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
    def get_upcoming_launches(self):
        current_time = datetime.now(pytz.UTC)
        valid_launches = [l for l in self._launch_data['upcoming'] if l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
        launches = []
        for l in sorted(valid_launches, key=lambda x: parse(x['net']))[:10]:
            launch = l.copy()
            launch_datetime = parse(l['net']).replace(tzinfo=pytz.UTC).astimezone(self._tz)
            launch['local_date'] = launch_datetime.strftime('%Y-%m-%d')
            launch['local_time'] = launch_datetime.strftime('%H:%M:%S')
            launches.append(launch)
        return launches

    @pyqtSlot(result=QVariant)
    def get_launch_trajectory(self):
        # Example: Add logging to show the orbit type being processed
        next_launch = None
        if self._launch_data and self._launch_data.get('upcoming'):
            next_launch = self._launch_data['upcoming'][0] if self._launch_data['upcoming'] else None
        if not next_launch:
            logger.info("No upcoming launch found for trajectory generation")
            return None

        logger.info(f"Next launch: {next_launch.get('mission', 'Unknown')} from {next_launch.get('pad', 'Unknown')}")
        pad = next_launch.get('pad', '')
        orbit = next_launch.get('orbit', '')

        logger.info(f"Processing orbit type: '{orbit}' for trajectory generation")

        # ...existing code for trajectory generation...
        """Get trajectory data for the next upcoming launch"""
        logger.info("get_launch_trajectory called")
        upcoming = self.get_upcoming_launches()
        logger.info(f"Found {len(upcoming)} upcoming launches")

        # If no upcoming launches, try to use recent launches for demo
        if not upcoming:
            logger.info("No upcoming launches, trying recent launches")
            if self._launch_data and self._launch_data.get('previous'):
                recent_launches = self._launch_data['previous'][:5]  # Get first 5 recent launches
                if recent_launches:
                    upcoming = [{
                        'mission': launch.get('mission', 'Unknown'),
                        'pad': launch.get('pad', 'Cape Canaveral'),
                        'orbit': launch.get('orbit', 'LEO')
                    } for launch in recent_launches]
                    logger.info(f"Using {len(upcoming)} recent launches for demo")

        if not upcoming:
            logger.info("No launches available at all")
            return None

        next_launch = upcoming[0]
        logger.info(f"Next launch: {next_launch.get('mission', 'Unknown')} from {next_launch.get('pad', 'Unknown')}")
        pad = next_launch.get('pad', '')
        orbit = next_launch.get('orbit', '')

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
        for site_key, site_data in launch_sites.items():
            if site_key in pad:
                launch_site = site_data
                break

        if not launch_site:
            # Default to Cape Canaveral if pad not recognized
            launch_site = launch_sites['LC-39A']
            logger.info(f"Using default launch site: {launch_site}")

        logger.info(f"Launch site: {launch_site}")

        def generate_curved_trajectory(start_point, end_point, num_points, orbit_type='default'):
            """Generate a smooth rocket launch trajectory with continuous curvature"""
            points = []

            start_lat = start_point['lat']
            start_lon = start_point['lon']
            end_lat = end_point['lat']
            end_lon = end_point['lon']

            # Calculate total distance
            lat_diff = end_lat - start_lat
            lon_diff = (end_lon - start_lon + 180) % 360 - 180  # Handle longitude wraparound

            # Create control point for quadratic Bézier curve
            # Control point is positioned above and between start and end
            mid_lat = (start_lat + end_lat) / 2
            mid_lon = (start_lon + end_lon) / 2

            # Lift the control point upward for the arc effect
            if orbit_type == 'polar':
                control_lat = max(-85.0, mid_lat - 20)  # South arc for polar orbits from Vandenberg
                control_lon = mid_lon - 20  # Slight westward curve
            elif orbit_type == 'equatorial':
                control_lat = mid_lat + 15  # Moderate arc
                control_lon = mid_lon + 30  # Curve eastward
            elif orbit_type == 'gto':
                control_lat = mid_lat + 25  # Higher arc for GTO
                control_lon = mid_lon + 60  # Longer eastward curve
            elif orbit_type == 'suborbital':
                control_lat = mid_lat + 10  # Lower arc for suborbital
                control_lon = mid_lon + 15  # Shorter curve
            else:  # default
                control_lat = mid_lat + 20  # Standard arc
                control_lon = mid_lon + 45  # Standard curve

            # Generate points along quadratic Bézier curve
            for i in range(num_points + 1):
                t = i / num_points  # Parameter from 0 to 1

                # Quadratic Bézier formula: B(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
                lat = (1-t)**2 * start_lat + 2*(1-t)*t * control_lat + t**2 * end_lat
                lon = (1-t)**2 * start_lon + 2*(1-t)*t * control_lon + t**2 * end_lon

                # Keep longitude in valid range
                lon = (lon + 180) % 360 - 180

                points.append({'lat': lat, 'lon': lon})

            return points

        # Generate trajectory based on orbit type
        trajectory = []
        logger.info(f"Generating ascent trajectory for orbit type: '{orbit}'")

        if 'Low Earth Orbit' in orbit or 'LEO' in orbit:
            # LEO trajectory - create a curved arc
            if launch_site['name'] == 'Vandenberg, CA':
                # Vandenberg polar LEO trajectory - launch south-southwest over Pacific (~190° azimuth)
                trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] - 30, 'lon': launch_site['lon'] - 10}, 20, orbit_type='polar')
            else:
                # Equatorial orbit from Florida/Texas - arc eastward
                trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'], 'lon': launch_site['lon'] + 120}, 35, orbit_type='equatorial')

        elif 'Geostationary' in orbit or 'GTO' in orbit:
            # Geostationary transfer orbit - higher arc toward equator
            trajectory = generate_curved_trajectory(launch_site, {'lat': 0, 'lon': launch_site['lon'] + 150}, 30, orbit_type='gto')

        elif 'Suborbital' in orbit:
            # Suborbital trajectory - shorter, lower arc
            trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] + 15, 'lon': launch_site['lon'] + 45}, 15, orbit_type='suborbital')

        else:
            # Default trajectory
            trajectory = generate_curved_trajectory(launch_site, {'lat': launch_site['lat'] + 20, 'lon': launch_site['lon'] + 60}, 20, orbit_type='default')

        result = {
            'launch_site': launch_site,
            'trajectory': trajectory,
            'orbit': orbit,
            'mission': next_launch.get('mission', ''),
            'pad': pad
        }

        # --- Add orbital path as a circular or elliptical arc ---
        def generate_orbit_path(trajectory, orbit_type='LEO', num_points=60):
            # Use the last point of the ascent as the starting point of the orbit
            if not trajectory:
                return []
            start = trajectory[-1]
            # For LEO, use a circular path at the same latitude as the end of ascent
            # For GTO, use a more elliptical path (simulate higher apogee)
            # For polar, sweep longitude, keep latitude near end point
            points = []
            if orbit_type in ['LEO', 'Low Earth Orbit', 'polar', 'equatorial']:
                # Circular orbit in the plane of the end point
                lat = start['lat']
                for i in range(num_points):
                    theta = (i / num_points) * 360.0
                    lon = (start['lon'] + theta) % 360 - 180
                    points.append({'lat': lat, 'lon': lon})
            elif orbit_type in ['GTO', 'Geostationary']:
                # Elliptical: latitude oscillates, longitude sweeps
                for i in range(num_points):
                    theta = (i / num_points) * 360.0
                    lon = (start['lon'] + theta) % 360 - 180
                    # Simulate elliptical inclination
                    lat = start['lat'] + 10 * math.sin(math.radians(theta))
                    points.append({'lat': lat, 'lon': lon})
            else:
                # Default: circular at end latitude
                lat = start['lat']
                for i in range(num_points):
                    theta = (i / num_points) * 360.0
                    lon = (start['lon'] + theta) % 360 - 180
                    points.append({'lat': lat, 'lon': lon})
            return points

        result['orbit_path'] = generate_orbit_path(trajectory, orbit, 90)
        logger.info(f"Generated orbit path with {len(result['orbit_path'])} points for orbit type: '{orbit}'")
        logger.info(f"Returning trajectory with {len(trajectory)} points and orbit path with {len(result['orbit_path'])} points")
        logger.info(f"Generated orbit path with {len(result['orbit_path'])} points")
        logger.info(f"Returning trajectory with {len(trajectory)} points and orbit path with {len(result['orbit_path'])} points")
        logger.info(f"Returning trajectory with {len(trajectory)} points")
        return result

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

    @pyqtSlot()
    def update_weather(self):
        """Update weather data in a separate thread to avoid blocking UI"""
        if hasattr(self, '_weather_updater_thread') and self._weather_updater_thread.isRunning():
            return  # Skip if already updating

        self._weather_updater = WeatherUpdater()
        self._weather_updater_thread = QThread()
        self._weather_updater.moveToThread(self._weather_updater_thread)
        self._weather_updater.finished.connect(self._on_weather_updated)
        self._weather_updater_thread.started.connect(self._weather_updater.run)
        self._weather_updater_thread.start()

    def update_launches_periodic(self):
        """Update launch data in a separate thread to avoid blocking UI"""
        if hasattr(self, '_launch_updater_thread') and self._launch_updater_thread.isRunning():
            return  # Skip if already updating

        self._launch_updater = LaunchUpdater()
        self._launch_updater_thread = QThread()
        self._launch_updater.moveToThread(self._launch_updater_thread)
        self._launch_updater.finished.connect(self._on_launches_updated)
        self._launch_updater_thread.started.connect(self._launch_updater.run)
        self._launch_updater_thread.start()

    def update_time(self):
        self.timeChanged.emit()

    @pyqtSlot()
    def update_countdown(self):
        self.countdownChanged.emit()

    def update_event_model(self):
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self.eventModelChanged.emit()

    @pyqtSlot(dict, dict, dict)
    def on_data_loaded(self, launch_data, f1_data, weather_data):
        logger.info("Backend: on_data_loaded called")
        self.setLoadingStatus("Data loaded successfully")
        logger.info(f"Backend: Received {len(launch_data.get('upcoming', []))} upcoming launches")
        logging.info("Data loaded - updating F1 chart")
        self._launch_data = launch_data
        self._f1_data = f1_data
        self._weather_data = weather_data
        # Update the EventModel's data reference
        self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
        self._event_model.update_data()
        self._isLoading = False
        self.loadingFinished.emit()
        self.launchesChanged.emit()
        self.launchTrayVisibilityChanged.emit()
        self.f1Changed.emit()
        logging.info("F1 changed signal emitted")
        self.weatherChanged.emit()
        self.eventModelChanged.emit()

        # Update trajectory now that data is loaded
        self.updateGlobeTrajectory.emit()

    def _on_loading_timeout(self):
        """Handle loading timeout when no network connectivity is available"""
        logger.info("BOOT: Loading timeout reached - transitioning to offline mode")
        logger.info("BOOT: Loading cached launch data...")
        # Load cached data if available, otherwise use empty data
        self._launch_data = self._load_cached_launch_data()
        logger.info("BOOT: Loading cached F1 data...")
        self._f1_data = self._load_cached_f1_data()
        logger.info("BOOT: Loading cached weather data...")
        self._weather_data = self._load_cached_weather_data()

        # Update the EventModel's data reference
        logger.info(f"BOOT: Updating EventModel data (mode: {self._mode})")
        self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
        self._event_model.update_data()

        # Exit loading state
        logger.info("BOOT: Exiting loading state and emitting loadingFinished signal")
        self._isLoading = False
        self.loadingFinished.emit()
        logger.info("BOOT: Offline mode activated - app should now show cached data")

    def _load_cached_launch_data(self):
        """Load cached launch data for offline mode"""
        try:
            previous_cache = load_cache_from_file(CACHE_FILE_PREVIOUS)
            upcoming_cache = load_cache_from_file(CACHE_FILE_UPCOMING)
            if previous_cache and upcoming_cache:
                logger.info("Backend: Loaded cached launch data for offline mode")
                return {
                    'previous': previous_cache['data'],
                    'upcoming': upcoming_cache['data']
                }
        except Exception as e:
            logger.warning(f"Backend: Failed to load cached launch data: {e}")
        logger.info("Backend: No cached launch data available")
        return {'previous': [], 'upcoming': []}

    def _load_cached_f1_data(self):
        """Load cached F1 data for offline mode"""
        try:
            schedule_cache = load_cache_from_file(CACHE_FILE_F1_SCHEDULE)
            drivers_cache = load_cache_from_file(CACHE_FILE_F1_DRIVERS)
            constructors_cache = load_cache_from_file(CACHE_FILE_F1_CONSTRUCTORS)
            
            schedule = schedule_cache['data'] if schedule_cache else []
            driver_standings = drivers_cache['data'] if drivers_cache else []
            constructor_standings = constructors_cache['data'] if constructors_cache else []
            
            logger.info("Backend: Loaded cached F1 data for offline mode")
            return {
                'schedule': schedule,
                'driver_standings': driver_standings,
                'constructor_standings': constructor_standings
            }
        except Exception as e:
            logger.warning(f"Backend: Failed to load cached F1 data: {e}")
        logger.info("Backend: No cached F1 data available")
        return {'schedule': [], 'driver_standings': [], 'constructor_standings': []}

    def _load_cached_weather_data(self):
        """Load cached/default weather data for offline mode"""
        # Return default weather data for all locations
        weather_data = {}
        for location in location_settings.keys():
            weather_data[location] = {
                'temperature_c': 25,
                'temperature_f': 77,
                'wind_speed_ms': 5,
                'wind_speed_kts': 9.7,
                'wind_direction': 90,
                'cloud_cover': 50
            }
        logger.info("Backend: Using default weather data for offline mode")
        return weather_data

        logger.info("Backend: Data loading complete, cleaning up thread")
        self.thread.quit()
        self.thread.wait()

    @pyqtSlot(dict)
    def _on_launches_updated(self, launch_data):
        """Handle launch data update completion"""
        self._launch_data = launch_data
        self._launch_trends_cache.clear()  # Clear cache when data updates
        self.launchesChanged.emit()
        self.launchTrayVisibilityChanged.emit()
        self.update_event_model()
        # Clean up thread
        if hasattr(self, '_launch_updater_thread'):
            self._launch_updater_thread.quit()
            self._launch_updater_thread.wait()

        # Auto-reconnect to last connected network if not currently connected
        self._auto_reconnect_to_last_network()

    @pyqtSlot(dict)
    def _on_weather_updated(self, weather_data):
        """Handle weather data update completion"""
        self._weather_data = weather_data
        self.weatherChanged.emit()
        # Clean up thread
        if hasattr(self, '_weather_updater_thread'):
            self._weather_updater_thread.quit()
            self._weather_updater_thread.wait()

    def _auto_reconnect_to_last_network(self):
        """Auto-reconnect to the last connected network if not currently connected"""
        try:
            # Only attempt reconnection if we're not already connected and not currently connecting
            if self._wifi_connected or self._wifi_connecting:
                logger.debug("WiFi already connected or connecting, skipping auto-reconnection")
                return

            if not self._last_connected_network:
                logger.debug("No last connected network to auto-reconnect to")
                return

            last_ssid = self._last_connected_network.get('ssid')
            if not last_ssid:
                logger.debug("No last connected network SSID found")
                return

            # Check if we've attempted reconnection recently (avoid spam)
            current_time = time.time()
            if hasattr(self, '_last_reconnect_attempt') and (current_time - self._last_reconnect_attempt) < 30:  # 30 second cooldown
                logger.debug("Auto-reconnection attempted too recently, skipping")
                return

            self._last_reconnect_attempt = current_time
            logger.info(f"Attempting auto-reconnection to last connected network: {last_ssid}")

            # Find the network in remembered networks
            remembered_network = None
            for network in self._remembered_networks:
                if network['ssid'] == last_ssid:
                    remembered_network = network
                    break

            if not remembered_network or not remembered_network.get('password'):
                logger.warning(f"Cannot auto-reconnect to {last_ssid}: network not in remembered list or no password stored")
                return

            # Check if the network is currently available before attempting connection
            available_networks = [net['ssid'] for net in self._wifi_networks]
            if last_ssid not in available_networks:
                logger.info(f"Last connected network '{last_ssid}' not currently available, skipping auto-reconnection")
                return

            # Add a small delay before attempting reconnection to avoid race conditions
            QTimer.singleShot(2000, lambda: self._perform_auto_reconnection(last_ssid, remembered_network['password']))

        except Exception as e:
            logger.error(f"Error during auto-reconnection setup: {e}")

    def _perform_auto_reconnection(self, ssid, password):
        """Perform the actual auto-reconnection attempt"""
        try:
            if self._wifi_connected or self._wifi_connecting:
                logger.debug("Connection state changed, aborting auto-reconnection")
                return

            logger.info(f"Performing auto-reconnection to {ssid}")
            self.connectToWifi(ssid, password)
            logger.info(f"Auto-reconnection initiated for network: {ssid}")

        except Exception as e:
            logger.error(f"Error performing auto-reconnection: {e}")

    @pyqtSlot()
    def scanWifiNetworks(self):
        """Scan for available WiFi networks using wpa_supplicant directly"""
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
                # Use wpa_supplicant directly for Linux WiFi scanning (NetworkManager disabled)
                logger.info("Scanning WiFi networks using wpa_supplicant (wpa_cli)...")
                networks = []
                
                try:
                    # Check if wpa_cli is available
                    wpa_check = subprocess.run(['which', 'wpa_cli'], capture_output=True, timeout=3)
                    if wpa_check.returncode == 0:
                        logger.info("wpa_cli found, attempting direct wpa_supplicant scan")

                        # Get the WiFi interface
                        wifi_interface = self.get_wifi_interface()
                        logger.debug(f"Using WiFi interface: {wifi_interface}")

                        # Try to scan using wpa_cli
                        scan_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'scan'],
                                                   capture_output=True, text=True, timeout=5)

                        if scan_result.returncode == 0:
                            logger.info("wpa_cli scan initiated successfully")

                            # Wait for scan results
                            time.sleep(3)

                            # Get scan results
                            results_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'scan_results'],
                                                          capture_output=True, text=True, timeout=5)

                            if results_result.returncode == 0 and results_result.stdout.strip():
                                logger.info("wpa_cli scan results retrieved successfully")
                                raw_output = results_result.stdout.strip()
                                logger.debug(f"Raw wpa_cli scan_results output:\n{raw_output}")
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

                                        # Decode escape sequences in SSID if present (wpa_cli may output \x escapes for non-ASCII)
                                        if ssid and '\\x' in ssid:
                                            try:
                                                # wpa_cli outputs UTF-8 bytes as \x escapes, need to decode properly
                                                ssid = ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                            except Exception as e:
                                                logger.debug(f"Failed to decode SSID escapes: {e}, keeping original")

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
                                        else:
                                            logger.debug(f"Skipping network with empty or hidden SSID: '{ssid}'")
                                    else:
                                        logger.debug(f"Skipping line with insufficient parts: {len(parts)} parts")

                                logger.info(f"wpa_cli scan found {len(networks)} networks")
                            else:
                                logger.warning("wpa_cli scan_results failed or returned empty")
                                networks = []
                        else:
                            logger.warning(f"wpa_cli scan failed: {scan_result.stderr}")
                            networks = []
                    else:
                        logger.error("wpa_cli not found - WiFi scanning not available")
                        networks = []
                except subprocess.TimeoutExpired:
                    logger.warning("wpa_cli scan timed out")
                    networks = []
                except Exception as wpa_e:
                    logger.error(f"wpa_cli scan failed: {wpa_e}")
            # Remove duplicates and sort by signal strength
            seen_ssids = {}
            for network in networks:
                ssid = network['ssid']
                if ssid:
                    if ssid not in seen_ssids or network['signal'] > seen_ssids[ssid]['signal']:
                        seen_ssids[ssid] = network
                        logger.debug(f"Keeping network {ssid} with signal {network['signal']}")

            unique_networks = list(seen_ssids.values())
            logger.info(f"After deduplication: {len(unique_networks)} unique networks from {len(networks)} total entries")
            for network in unique_networks:
                logger.debug(f"Final network: {network['ssid']} (signal: {network['signal']})")

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
                # Try wpa_cli first (more reliable), then nmcli as fallback
                try:
                    # Get the WiFi interface
                    wifi_interface = self.get_wifi_interface()
                    logger.debug(f"Using WiFi interface: {wifi_interface}")

                    # Check if wpa_cli is available
                    wpa_check = subprocess.run(['which', 'wpa_cli'], capture_output=True, timeout=3)
                    if wpa_check.returncode == 0:
                        logger.info(f"Trying wpa_cli connection to: {ssid}")
                        
                        # Use wpa_cli directly
                        # Add network
                        add_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'add_network'], 
                                                  capture_output=True, text=True, timeout=5)
                        if add_result.returncode == 0:
                                network_id = add_result.stdout.strip()
                                logger.info(f"Added network with ID: {network_id}")
                                
                                # Set SSID - handle Unicode characters by hex encoding if necessary
                                if all(ord(c) < 128 for c in ssid):
                                    # ASCII SSID
                                    ssid_param = f'"{ssid}"'
                                else:
                                    # Unicode SSID - encode as hex
                                    ssid_hex = ssid.encode('utf-8').hex()
                                    ssid_param = ssid_hex
                                
                                ssid_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'set_network', network_id, 'ssid', ssid_param], 
                                                           capture_output=True, text=True, timeout=5)
                                if ssid_result.returncode != 0:
                                    logger.error(f"Failed to set SSID: {ssid_result.stderr}")
                                    # Clean up
                                    subprocess.run(['wpa_cli', '-i', wifi_interface, 'remove_network', network_id], capture_output=True)
                                    self._wifi_connecting = False
                                    self.wifiConnectingChanged.emit()
                                    return
                                
                                if password:
                                    # Set password
                                    psk_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'set_network', network_id, 'psk', f'"{password}"'], 
                                                              capture_output=True, text=True, timeout=5)
                                    if psk_result.returncode != 0:
                                        logger.error(f"Failed to set password: {psk_result.stderr}")
                                        # Clean up
                                        subprocess.run(['wpa_cli', '-i', wifi_interface, 'remove_network', network_id], capture_output=True)
                                        self._wifi_connecting = False
                                        self.wifiConnectingChanged.emit()
                                        return
                                
                                # Enable network
                                enable_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'enable_network', network_id], 
                                                             capture_output=True, text=True, timeout=5)
                                if enable_result.returncode != 0:
                                    logger.error(f"Failed to enable network: {enable_result.stderr}")
                                    # Clean up
                                    subprocess.run(['wpa_cli', '-i', wifi_interface, 'remove_network', network_id], capture_output=True)
                                    self._wifi_connecting = False
                                    self.wifiConnectingChanged.emit()
                                    return
                                
                                # Select network
                                select_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'select_network', network_id], 
                                                             capture_output=True, text=True, timeout=5)
                                if select_result.returncode == 0:
                                    logger.info(f"Successfully connected to {ssid} using wpa_cli")
                                    # Save the configuration to persist across reboots
                                    save_result = subprocess.run(['wpa_cli', '-i', wifi_interface, 'save_config'], 
                                                               capture_output=True, text=True, timeout=5)
                                    if save_result.returncode == 0:
                                        logger.info("WiFi configuration saved to persist across reboots")
                                    else:
                                        logger.warning(f"Failed to save WiFi config: {save_result.stderr}")
                                    # Remember this network for future connections
                                    self.add_remembered_network(ssid, password)
                                    # Save as last connected network
                                    self.save_last_connected_network(ssid)
                                else:
                                    logger.error(f"Failed to select network: {select_result.stderr}")
                                    # Clean up
                                    subprocess.run(['wpa_cli', '-i', wifi_interface, 'remove_network', network_id], capture_output=True)
                        else:
                            logger.error(f"Failed to add network: {add_result.stderr}")
                    else:
                        logger.warning("wpa_cli not available, trying nmcli fallback")
                        # Fallback to nmcli
                        if self._try_nmcli_connection(ssid, password, wifi_interface):
                            self.add_remembered_network(ssid, password)
                            self.save_last_connected_network(ssid)
                        
                except Exception as e:
                    logger.error(f"wpa_cli connection failed: {e}")
                    # Try nmcli as fallback
                    try:
                        if self._try_nmcli_connection(ssid, password, self.get_wifi_interface()):
                            self.add_remembered_network(ssid, password)
                            self.save_last_connected_network(ssid)
                    except Exception as e2:
                        logger.error(f"nmcli fallback also failed: {e2}")
                    
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

    @pyqtSlot(str)
    def connectToRememberedNetwork(self, ssid):
        """Connect to a remembered WiFi network"""
        for network in self._remembered_networks:
            if network['ssid'] == ssid:
                password = network.get('password')
                self.connectToWifi(ssid, password)
                return
        logger.error(f"Remembered network '{ssid}' not found")

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
                            wifi_interface = self.get_wifi_interface()
                            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], capture_output=True)
                            subprocess.run(['sudo', 'dhclient', '-r', wifi_interface], capture_output=True)
                        except:
                            # Try without sudo
                            try:
                                wifi_interface = self.get_wifi_interface()
                                subprocess.run(['killall', 'wpa_supplicant'], capture_output=True)
                                subprocess.run(['dhclient', '-r', wifi_interface], capture_output=True)
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
        """Perform one-time WiFi status check when popup opens (no periodic checking)"""
        # Only update status once when popup opens - no periodic timer
        logger.info("Performing one-time WiFi status check on popup open")
        self.update_wifi_status()

    @pyqtSlot()
    def stopWifiTimer(self):
        """Stop WiFi status checking timer (no longer used - timer not started)"""
        # Timer is no longer started, but keep method for compatibility
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
                                        # Decode SSID if it contains escape sequences
                                        if current_ssid and '\\x' in current_ssid:
                                            try:
                                                current_ssid = current_ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                            except Exception as e:
                                                logger.debug(f"Failed to decode current SSID: {e}")
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
                                    # Decode SSID if it contains escape sequences
                                    if current_ssid and '\\x' in current_ssid:
                                        try:
                                            current_ssid = current_ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                        except Exception as e:
                                            logger.debug(f"Failed to decode current SSID from active connections: {e}")
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
                                        # Decode SSID if it contains escape sequences
                                        if current_ssid and '\\x' in current_ssid:
                                            try:
                                                current_ssid = current_ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                            except Exception as e:
                                                logger.debug(f"Failed to decode current SSID from iw: {e}")
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
                                        # Decode SSID if it contains escape sequences
                                        if current_ssid and '\\x' in current_ssid:
                                            try:
                                                current_ssid = current_ssid.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                                            except Exception as e:
                                                logger.debug(f"Failed to decode current SSID from iwgetid: {e}")
                                        logger.info(f"Current SSID via iwgetid: {current_ssid}")
                                except Exception as e:
                                    logger.debug(f"iwgetid failed: {e}")
            
            # Update properties
            wifi_changed = (self._wifi_connected != connected) or (self._current_wifi_ssid != current_ssid)
            wifi_just_connected = not self._wifi_connected and connected
            
            self._wifi_connected = connected
            self._current_wifi_ssid = current_ssid
            
            if wifi_changed:
                logger.info(f"WiFi status updated - Connected: {connected}, SSID: {current_ssid}")
                self.wifiConnectedChanged.emit()

                # Handle WiFi connection established
                if wifi_just_connected:
                    logger.info("WiFi connection detected - reloading web content")
                    self.reload_web_content()

                    # If data loading was deferred due to no connectivity, start it now
                    if hasattr(self, '_data_loading_deferred') and self._data_loading_deferred:
                        logger.info("WiFi connected - starting deferred data loading")
                        self._data_loading_deferred = False
                        # Cancel the loading timeout timer since we're now loading data
                        if hasattr(self, '_loading_timeout_timer') and self._loading_timeout_timer.isActive():
                            self._loading_timeout_timer.stop()
                            logger.info("Backend: Cancelled loading timeout timer - network connected")
                        # Start data loading now that we have connectivity
                        if self.loader is None:
                            logger.info("Backend: Creating deferred DataLoader...")
                            self.loader = DataLoader()
                            self.thread = QThread()
                            self.loader.moveToThread(self.thread)
                            self.loader.finished.connect(self.on_data_loaded)
                            self.loader.statusUpdate.connect(self.setLoadingStatus)
                            self.thread.started.connect(self.loader.run)
                            logger.info("Backend: Starting deferred DataLoader thread...")
                            self.thread.start()
                        else:
                            logger.info("Backend: Deferred DataLoader already exists")
                
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

    @pyqtSlot(str, result=str)
    def getCountryFlag(self, country_name):
        """Get flag icon path for a country name"""
        # Country to ISO code mapping
        code_map = {
            'Australia': 'au',
            'Austria': 'at',
            'Azerbaijan': 'az',
            'Bahrain': 'bh',
            'Belgium': 'be',
            'Brazil': 'br',
            'Canada': 'ca',
            'China': 'cn',
            'France': 'fr',
            'Germany': 'de',
            'Great Britain': 'gb',
            'Hungary': 'hu',
            'Italy': 'it',
            'Japan': 'jp',
            'Mexico': 'mx',
            'Monaco': 'mc',
            'Netherlands': 'nl',
            'Portugal': 'pt',
            'Qatar': 'qa',
            'Russia': 'ru',
            'Saudi Arabia': 'sa',
            'Singapore': 'sg',
            'South Korea': 'kr',
            'Spain': 'es',
            'Turkey': 'tr',
            'UAE': 'ae',
            'United Arab Emirates': 'ae',
            'UK': 'gb',
            'United Kingdom': 'gb',
            'United States': 'us',
            'USA': 'us',
            'Vietnam': 'vn'
        }
        code = code_map.get(country_name)
        if not code:
            return ""
        
        # Cache directory for flags
        cache_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "images", "flags")
        os.makedirs(cache_dir, exist_ok=True)
        flag_path = os.path.join(cache_dir, f"{code}.svg")
        
        # Download if not cached
        if not os.path.exists(flag_path):
            try:
                url = f"https://flagicons.lipis.dev/flags/4x3/{code}.svg"
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                with open(flag_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Cached flag for {country_name} ({code})")
            except Exception as e:
                logger.warning(f"Failed to download flag for {country_name}: {e}")
                return ""
        
        return f"file:///{flag_path}"

    @pyqtSlot()
    @pyqtSlot()
    @pyqtSlot()
    def runUpdateScript(self):
        """Run the update and reboot script"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'update_and_reboot.sh')      
            logger.info(f"Running update script: {script_path}")

            # Run the script in the background since it will kill this process
            subprocess.Popen(['bash', script_path],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           cwd=os.path.dirname(script_path))

            logger.info("Update script started - app will be terminated")

        except Exception as e:
            logger.error(f"Error running update script: {e}")

    def get_current_version(self):
        """Get the current git commit hash"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=os.path.dirname(__file__))
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning("Failed to get current git commit hash")
                return None
        except Exception as e:
            logger.error(f"Error getting current version: {e}")
            return None

    def check_for_updates(self):
        """Check if there's a newer version available on GitHub"""
        try:
            # Get current commit hash
            current_version = self.get_current_version()
            if not current_version:
                logger.warning("Could not determine current version")
                return False
            
            # Check GitHub API for latest commit on master branch
            repo_owner = "hwpaige"
            repo_name = "spacex-dashboard"
            api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/master"
            
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                latest_commit = response.json()
                latest_version = latest_commit['sha']
                
                logger.info(f"Current version: {current_version[:8]}")
                logger.info(f"Latest version: {latest_version[:8]}")
                
                # Compare versions
                if current_version != latest_version:
                    logger.info("Update available!")
                    return True
                else:
                    logger.info("Already up to date")
                    return False
            else:
                logger.warning(f"Failed to check GitHub API: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return False

    def check_network_connectivity(self):
        """Check if we have active network connectivity (beyond just WiFi connection)"""
        logger.info("BOOT: check_network_connectivity called")
        try:
            # First check if WiFi is connected
            logger.info(f"BOOT: WiFi connected status: {self._wifi_connected}")
            if not self._wifi_connected:
                logger.warning("BOOT: Network connectivity check failed: WiFi not connected")
                return False

            # Try to reach a reliable external host to verify internet connectivity
            # Test with a simple HTTP request to a reliable service
            logger.info("BOOT: Testing internet connectivity with HTTP request to google.com...")
            try:
                # Use a timeout to avoid hanging
                urllib.request.urlopen('http://www.google.com', timeout=5)
                logger.info("BOOT: Network connectivity check passed: Internet accessible")
                return True
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                logger.warning(f"BOOT: Network connectivity check failed: Cannot reach internet ({e})")
                return False

        except Exception as e:
            logger.error(f"BOOT: Error checking network connectivity: {e}")
            return False

if __name__ == '__main__':
    # Set console encoding to UTF-8 to handle Unicode characters properly
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    
    logger.info("BOOT: Starting SpaceX Dashboard application...")
    logger.info(f"BOOT: Python version: {sys.version}")
    logger.info(f"BOOT: Platform: {platform.system()} {platform.release()}")
    logger.info(f"BOOT: Qt version available: {QApplication.instance() is None}")
    
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
            "--disable-web-security --allow-running-insecure-content"
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
    
    # Set style to Fusion to ensure compatibility
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"
    fusion_style = QStyleFactory.create("Fusion")
    if fusion_style:
        QApplication.setStyle(fusion_style)
    
    # Start local HTTP server for serving HTML files
    def start_http_server():
        port = 8080
        os.chdir(os.path.dirname(__file__))  # Serve from src directory
        handler = http.server.SimpleHTTPRequestHandler

        # Try to start server on port 8080, then try alternative ports if busy
        for attempt_port in [8080, 8081, 8082, 8083, 8084]:
            try:
                with socketserver.TCPServer(("", attempt_port), handler) as httpd:
                    # Allow address reuse to prevent "address already in use" errors
                    httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    logger.info(f"Serving HTTP on port {attempt_port}")
                    httpd.serve_forever()
            except OSError as e:
                if e.errno == 10048:  # WinError 10048: Address already in use
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
    
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    
    app = QApplication(sys.argv)
    if platform.system() != 'Windows':
        app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))  # Blank cursor globally

    # Load fonts
    font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "D-DIN.ttf")
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    # Load Font Awesome (assuming you place 'Font-Awesome.otf' in assets; download from fontawesome.com if needed)
    fa_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Font Awesome 5 Free-Solid-900.otf")
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
            grid_color = QColor("#ffffff")  # Tesla-style white grid lines
            axis_color = QColor("#666666")
            colors = [QColor("#00D4FF"), QColor("#FF6B6B"), QColor("#4ECDC4")]
        else:
            bg_color = QColor("#f0f0f0")
            text_color = QColor("black")
            grid_color = QColor("#ccc")
            axis_color = QColor("#999")
            colors = [QColor("#0066CC"), QColor("#FF4444"), QColor("#00AA88")]

        painter.fillRect(0, 0, int(width), int(height), bg_color)

        # Draw Tesla-style grid lines (subtle white solid lines with transparency)
        grid_pen = QPen(grid_color, 1, Qt.PenStyle.SolidLine)
        grid_pen.setColor(QColor(grid_color.red(), grid_color.green(), grid_color.blue(), 60))  # 60/255 alpha for subtlety
        painter.setPen(grid_pen)
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
                # Convert month period (e.g., "2024-01") to short month name (e.g., "Jan")
                month_num = int(month.split('-')[1])
                month_name = calendar.month_abbr[month_num]
                painter.drawText(int(x - 10), int(height - 5), month_name)

        # Draw legend
        legend_x = width - margin - 100
        legend_y = margin + 10
        legend_spacing = 20
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
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
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
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
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
                color = colors[s % len(colors)]
            painter.setPen(QPen(color, 3))
            points = []
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / self._max_value if self._max_value > 0 else height - margin
                points.append(QPoint(int(x), int(y)))
            
            # Draw lines if multiple points
            if len(points) > 1:
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])
            
            # Draw points
            painter.setBrush(QBrush(color))
            for point in points:
                painter.drawEllipse(point, 4, 4)

    def _draw_area_chart(self, painter, width, height, margin, colors):
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
                color = colors[s % len(colors)]
            painter.setPen(QPen(color, 3))
            painter.setBrush(QBrush(color.lighter(150)))
            points = [QPoint(int(margin), int(height - margin))]
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / self._max_value if self._max_value > 0 else height - margin
                points.append(QPoint(int(x), int(y)))
            points.append(QPoint(int(width - margin), int(height - margin)))
            painter.drawPolygon(points)

qmlRegisterType(ChartItem, 'Charts', 1, 0, 'ChartItem')

# Check WiFi status before creating Backend to ensure accurate initial state
logger.info("BOOT: Checking initial WiFi status before creating Backend...")
wifi_connected, wifi_ssid = check_wifi_status()
logger.info(f"BOOT: Initial WiFi check result - connected: {wifi_connected}, SSID: {wifi_ssid}")

logger.info("BOOT: Creating Backend instance...")
backend = Backend(initial_wifi_connected=wifi_connected, initial_wifi_ssid=wifi_ssid)
# Now start the data loader after WiFi is stable
logger.info("BOOT: Starting data loader...")
backend.startDataLoader()

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
context = engine.rootContext()
context.setContextProperty("backend", backend)
context.setContextProperty("radarLocations", radar_locations)
context.setContextProperty("circuitCoords", circuit_coords)
context.setContextProperty("spacexLogoPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'spacex_logo.png').replace('\\', '/'))
context.setContextProperty("f1LogoPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'f1-logo.png').replace('\\', '/'))
context.setContextProperty("chevronPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'double-chevron.png').replace('\\', '/'))

globe_file_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'globe.html')
print(f"DEBUG: Globe file path: {globe_file_path}")
print(f"DEBUG: Globe file exists: {os.path.exists(globe_file_path)}")

earth_texture_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'earth_texture.jpg')
print(f"DEBUG: Earth texture path: {earth_texture_path}")
print(f"DEBUG: Earth texture exists: {os.path.exists(earth_texture_path)}")

youtube_html_path = os.path.join(os.path.dirname(__file__), 'youtube_embed.html')
print(f"DEBUG: YouTube HTML path: {youtube_html_path}")
print(f"DEBUG: YouTube HTML exists: {os.path.exists(youtube_html_path)}")

context.setContextProperty("globeUrl", "file:///" + globe_file_path.replace('\\', '/'))
print(f"DEBUG: Globe URL set to: {context.property('globeUrl')}")
context.setContextProperty("videoUrl", "http://localhost:8080/youtube_embed.html")

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
        // Connect web content reload signal
        backend.reloadWebContent.connect(function() {
            console.log("Reloading web content after WiFi connection...")
            // Reload globe view
            if (typeof globeView !== 'undefined' && globeView.reload) {
                globeView.reload()
                console.log("Globe view reloaded")
            }
            // Reload F1 chart view
            if (typeof f1ChartView !== 'undefined' && f1ChartView.reload) {
                f1ChartView.reload()
                console.log("F1 chart view reloaded")
            }
            // Reload YouTube/map view
            if (typeof youtubeView !== 'undefined' && youtubeView.reload) {
                youtubeView.reload()
                console.log("YouTube/map view reloaded")
            }
            // Reload x.com view
            if (typeof xComView !== 'undefined' && xComView.reload) {
                xComView.reload()
                console.log("x.com view reloaded")
            }
            // Reload weather views
            if (typeof weatherSwipe !== 'undefined') {
                for (var i = 0; i < weatherSwipe.count; i++) {
                    var item = weatherSwipe.itemAt(i);
                    if (item && item.children[0] && item.children[0].reload) {
                        item.children[0].reload();
                        console.log("Weather view", i, "reloaded");
                    }
                }
            }
            // Refresh countdown
            if (typeof backend !== 'undefined' && backend.update_countdown) {
                backend.update_countdown();
                console.log("Countdown refreshed");
            }
            // Refresh weather data for bottom left pill
            if (typeof backend !== 'undefined' && backend.update_weather) {
                backend.update_weather();
                console.log("Weather data refresh initiated");
            }
        })
    }

    Rectangle {
        id: loadingScreen
        anchors.fill: parent
        color: backend.theme === "dark" ? "#1c2526" : "#ffffff"
        visible: !!(backend && backend.isLoading)
        z: 1

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 20

            Image {
                source: "file:///" + spacexLogoPath
                Layout.alignment: Qt.AlignHCenter
                width: 120
                height: 120
                sourceSize.width: 120
                sourceSize.height: 120
                fillMode: Image.PreserveAspectFit
            }

            Text {
                text: backend.loadingStatus
                Layout.alignment: Qt.AlignHCenter
                color: backend.theme === "dark" ? "#ffffff" : "#000000"
                font.pixelSize: 16
                font.family: "D-DIN"
                horizontalAlignment: Text.AlignHCenter
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
        function onUpdateGlobeTrajectory() {
            // Update trajectory when data loads
            var trajectoryData = backend.get_launch_trajectory();
            if (trajectoryData && globeView && globeView.runJavaScript) {
                globeView.runJavaScript("updateTrajectory(" + JSON.stringify(trajectoryData) + ");");
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 5
        anchors.rightMargin: 5
        anchors.topMargin: 5
        anchors.bottomMargin: 5
        spacing: 5
        visible: !!(!backend || !backend.isLoading)

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 5

            // Column 1: Launch Trends or Driver Standings
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: false

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !!(backend && backend.mode === "spacex")

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
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
                        }
                    }

                    // Chart control buttons container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        color: "transparent"
                        visible: backend && backend.mode === "spacex"

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "bar", "icon": "\uf080", "tooltip": "Bar Chart"},
                                    {"type": "line", "icon": "\uf201", "tooltip": "Line Chart"},
                                    {"type": "area", "icon": "\uf1fe", "tooltip": "Area Chart"},
                                    {"type": "actual", "icon": "\uf201", "tooltip": "Monthly View"},
                                    {"type": "cumulative", "icon": "\uf0cb", "tooltip": "Cumulative View"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    color: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                           (backend.chartType === modelData.type ?
                                            (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                            (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")) :
                                           (backend.chartViewMode === modelData.type ?
                                            (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                            (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5"))
                                    radius: 14
                                    border.color: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                 (backend.chartType === modelData.type ?
                                                  (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                  (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")) :
                                                 (backend.chartViewMode === modelData.type ?
                                                  (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                  (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"))
                                    border.width: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                 (backend.chartType === modelData.type ? 2 : 1) :
                                                 (backend.chartViewMode === modelData.type ? 2 : 1)

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                  backend.chartType = modelData.type :
                                                  backend.chartViewMode = modelData.type
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
                                }
                            }
                        }
                    }

                    // F1 Driver Points Chart
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend && backend.mode === "f1"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            spacing: 5

                            Text {
                                text: "F1 Driver Standings Over Time"
                                font.pixelSize: 14
                                font.bold: true
                                color: backend.theme === "dark" ? "white" : "black"
                                Layout.alignment: Qt.AlignHCenter
                                Layout.margins: 1
                            }

                            WebEngineView {
                                id: f1ChartView
                                Layout.fillWidth: true
                                Layout.fillHeight: true

                                // Bind url to chart file URL that updates reactively
                                url: backend.f1ChartUrl

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
                                Layout.margins: 0
                                spacing: 10

                                // Chart category buttons
                                RowLayout {
                                    spacing: 6
                                    Repeater {
                                        model: [
                                            {"type": "standings", "icon": "\uf091", "tooltip": "Driver Standings"},
                                            {"type": "weather", "icon": "\uf6c4", "tooltip": "Weather Data"},
                                            {"type": "telemetry", "icon": "\uf0e4", "tooltip": "Telemetry"},
                                            {"type": "positions", "icon": "\uf3c5", "tooltip": "Driver Positions"},
                                            {"type": "laps", "icon": "\uf2f1", "tooltip": "Lap Times"}
                                        ]
                                        Rectangle {
                                            Layout.preferredWidth: 40
                                            Layout.preferredHeight: 28
                                            color: backend.f1ChartType === modelData.type ?
                                                   (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                                   (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                            radius: 14
                                            border.color: backend.f1ChartType === modelData.type ?
                                                         (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                         (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                            border.width: backend.f1ChartType === modelData.type ? 2 : 1

                                            Behavior on color { ColorAnimation { duration: 200 } }
                                            Behavior on border.color { ColorAnimation { duration: 200 } }
                                            Behavior on border.width { NumberAnimation { duration: 200 } }

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.icon
                                                font.pixelSize: 14
                                                font.family: "Font Awesome 5 Free"
                                                color: backend.theme === "dark" ? "white" : "black"
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: backend.f1ChartType = modelData.type
                                            }

                                            ToolTip {
                                                text: modelData.tooltip
                                                delay: 500
                                            }
                                        }
                                    }
                                }

                                // Stat type buttons
                                RowLayout {
                                    spacing: 6
                                    Repeater {
                                        model: [
                                            {"type": "points", "icon": "\uf091", "tooltip": "Points"},
                                            {"type": "wins", "icon": "\uf005", "tooltip": "Wins"}
                                        ]
                                        Rectangle {
                                            Layout.preferredWidth: 40
                                            Layout.preferredHeight: 28
                                            color: backend.f1ChartStat === modelData.type ?
                                                   (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                                   (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                            radius: 14
                                            border.color: backend.f1ChartStat === modelData.type ?
                                                         (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                         (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                            border.width: backend.f1ChartStat === modelData.type ? 2 : 1

                                            Behavior on color { ColorAnimation { duration: 200 } }
                                            Behavior on border.color { ColorAnimation { duration: 200 } }
                                            Behavior on border.width { NumberAnimation { duration: 200 } }

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.icon
                                                font.pixelSize: 14
                                                font.family: "Font Awesome 5 Free"
                                                color: backend.theme === "dark" ? "white" : "black"
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: backend.f1ChartStat = modelData.type
                                            }

                                            ToolTip {
                                                text: modelData.tooltip
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
                Layout.preferredWidth: 1
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
                        anchors.margins: 10
                        visible: backend && backend.mode === "spacex"
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
                                    url: parent.visible ? radarLocations[backend.location].replace("radar", modelData) : ""
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
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend && backend.mode === "f1"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 5

                        Text {
                            text: backend.f1StandingsType === "drivers" ? "Driver Standings" : "Constructor Standings"
                            font.pixelSize: 14
                            font.bold: true
                            color: backend.theme === "dark" ? "white" : "black"
                            Layout.alignment: Qt.AlignHCenter
                            Layout.margins: 5
                        }

                        // Standings List
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            radius: 6

                            ListView {
                                anchors.fill: parent
                                anchors.margins: 10
                                model: backend.f1StandingsType === "drivers" ?
                                       backend.driverStandings.slice(0, 10) :
                                       backend.constructorStandings.slice(0, 10)
                                clip: true
                                delegate: Rectangle {
                                    width: ListView.view.width
                                    height: 35
                                    color: "transparent"

                                    Row {
                                        spacing: 10
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.left: parent.left

                                        Text {
                                            text: modelData.position;
                                            font.pixelSize: 12;
                                            color: backend.theme === "dark" ? "white" : "black";
                                            width: 20
                                        }

                                        // Team logo/color indicator
                                        Rectangle {
                                            width: 16
                                            height: 16
                                            radius: 8
                                            color: {
                                                var teamName = backend.f1StandingsType === "drivers" ?
                                                              (modelData.Constructors && modelData.Constructors.length > 0 ?
                                                               modelData.Constructors[0].name : "Unknown") :
                                                              modelData.Constructor.name;

                                                // Team color mapping
                                                var teamColors = {
                                                    "Mercedes": "#00D2BE",
                                                    "Red Bull": "#0600EF",
                                                    "Ferrari": "#DC0000",
                                                    "McLaren": "#FF8700",
                                                    "Alpine": "#0090FF",
                                                    "Aston Martin": "#006F62",
                                                    "Williams": "#005AFF",
                                                    "Alfa Romeo": "#900000",
                                                    "Haas F1 Team": "#FFFFFF",
                                                    "AlphaTauri": "#2B4562"
                                                };
                                                return teamColors[teamName] || "#666666";
                                            }
                                            border.color: backend.theme === "dark" ? "#ffffff" : "#000000"
                                            border.width: {
                                                var teamName = backend.f1StandingsType === "drivers" ?
                                                              (modelData.Constructors && modelData.Constructors.length > 0 ?
                                                               modelData.Constructors[0].name : "Unknown") :
                                                              modelData.Constructor.name;
                                                return teamName === "Haas F1 Team" ? 1 : 0;  // Border for white Haas logo
                                            }
                                        }

                                        Text {
                                            text: backend.f1StandingsType === "drivers" ?
                                                  (modelData.Driver.givenName + " " + modelData.Driver.familyName) :
                                                  modelData.Constructor.name;
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

                        // Standings type selector buttons
                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.margins: 0
                            spacing: 10

                            // Standings type buttons
                            RowLayout {
                                spacing: 6
                                Repeater {
                                    model: [
                                        {"type": "drivers", "icon": "\uf1b9", "tooltip": "Driver Standings"},
                                        {"type": "constructors", "icon": "\uf085", "tooltip": "Constructor Standings"}
                                    ]
                                    Rectangle {
                                        Layout.preferredWidth: 40
                                        Layout.preferredHeight: 28
                                        color: backend.f1StandingsType === modelData.type ?
                                               (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                               (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                        radius: 14
                                        border.color: backend.f1StandingsType === modelData.type ?
                                                     (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                     (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                        border.width: backend.f1StandingsType === modelData.type ? 2 : 1

                                        Behavior on color { ColorAnimation { duration: 200 } }
                                        Behavior on border.color { ColorAnimation { duration: 200 } }
                                        Behavior on border.width { NumberAnimation { duration: 200 } }

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.icon
                                            font.pixelSize: 14
                                            font.family: "Font Awesome 5 Free"
                                            color: backend.theme === "dark" ? "white" : "black"
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: backend.f1StandingsType = modelData.type
                                        }

                                        ToolTip {
                                            text: modelData.tooltip
                                            delay: 500
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                    // Weather view buttons container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        color: "transparent"
                        visible: backend && backend.mode === "spacex"

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "radar", "icon": "\uf7c0", "tooltip": "Weather Radar"},
                                    {"type": "wind", "icon": "\uf72e", "tooltip": "Wind Speed"},
                                    {"type": "gust", "icon": "\uf72e", "tooltip": "Wind Gusts"},
                                    {"type": "clouds", "icon": "\uf0c2", "tooltip": "Cloud Cover"},
                                    {"type": "temp", "icon": "\uf2c7", "tooltip": "Temperature"},
                                    {"type": "pressure", "icon": "\uf6c4", "tooltip": "Pressure"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    color: weatherSwipe.currentIndex === index ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 14
                                    border.color: weatherSwipe.currentIndex === index ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                    border.width: weatherSwipe.currentIndex === index ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: weatherSwipe.currentIndex = index
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
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
                Layout.preferredWidth: 1
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: backend.eventModel
                        clip: true
                        spacing: 5

                        delegate: Item {
                            width: ListView.view.width
                            height: model && model.isGroup ? 30 : (backend.mode === "spacex" ? launchColumn.height + 20 : (backend.mode === "f1" ? Math.max(80, 40 + (model && model.sessions && model.sessions.length ? model.sessions.length * 30 : 0)) : 40))

                            Rectangle { anchors.fill: parent; color: (model && model.isGroup) ? "transparent" : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"); radius: (model && model.isGroup) ? 0 : 6 }

                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 15
                                anchors.verticalCenter: parent.verticalCenter
                                text: (model && model.isGroup) ? (model.groupName ? model.groupName : "") : ""
                                font.pixelSize: 14; font.bold: true; color: "#999999"; visible: !!(model && model.isGroup)
                            }

                            Column {
                                id: launchColumn
                                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10
                                spacing: 5
                                visible: !!(model && !model.isGroup && backend.mode === "spacex" && typeof model === 'object')

                                Text { text: (model && model.mission) ? model.mission : ""; font.pixelSize: 14; color: backend.theme === "dark" ? "white" : "black" }
                                Row { spacing: 5
                                    Text { text: "\uf135"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Rocket: " + ((model && model.rocket) ? model.rocket : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf0ac"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Orbit: " + ((model && model.orbit) ? model.orbit : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf3c5"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Pad: " + ((model && model.pad) ? model.pad : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Text { text: "Date: " + ((model && model.date) ? model.date : "") + ((model && model.time) ? (" " + model.time) : "") + " UTC"; font.pixelSize: 12; color: "#999999" }
                                Text { text: backend.location + ": " + ((model && model.localTime) ? model.localTime : "TBD"); font.pixelSize: 12; color: "#999999" }
                                Text { text: "Status: " + ((model && model.status) ? model.status : ""); font.pixelSize: 12; color: ((model && model.status) && (model.status === "Success" || model.status === "Go" || model.status === "TBD" || model.status === "Go for Launch")) ? "#4CAF50" : "#F44336" }
                            }

                            Row {
                                anchors.fill: parent; anchors.margins: 10
                                visible: !!(model && !model.isGroup && backend.mode === "f1" && typeof model === 'object')
                                spacing: 10
                                
                                Column {
                                    width: parent.width * 0.6  // 60% for text
                                    spacing: 5
                                    
                                    // Race header with flag and name
                                    Row {
                                        spacing: 8
                                        Image {
                                            source: model && model.countryName ? backend.getCountryFlag(model.countryName) : ""
                                            width: 24
                                            height: 18
                                            visible: backend && backend.mode === "f1" && source !== ""
                                        }
                                        Text {
                                            text: model && model.countryName && !backend.getCountryFlag(model.countryName) ? '🏁' : ''
                                            font.pixelSize: 16
                                            visible: backend && backend.mode === "f1" && text !== ''
                                        }
                                        Text { 
                                            text: model && model.meetingName ? model.meetingName : ''; 
                                            color: backend.theme === "dark" ? "white" : "black"; 
                                            font.pixelSize: 14; 
                                            font.bold: true
                                        }
                                    }
                                    
                                    // Circuit info
                                    Text { text: model && model.circuitShortName ? model.circuitShortName : ""; color: "#999999"; font.pixelSize: 12 }
                                    Text { text: model && model.location ? model.location : ""; color: "#999999"; font.pixelSize: 12 }
                                    
                                    // Sessions list
                                    Column {
                                        spacing: 2
                                        visible: backend && backend.mode === "f1"
                                        
                                        property var raceSessions: model ? (model.sessions || []) : []
                                        
                                        Repeater {
                                            model: parent.raceSessions
                                            delegate: Row {
                                                spacing: 8
                                                visible: !!(modelData && typeof modelData === 'object' && modelData.session_name && modelData.date_start)
                                                Text { 
                                                    text: "\uf017"; 
                                                    font.family: "Font Awesome 5 Free"; 
                                                    font.pixelSize: 10; 
                                                    color: (modelData && modelData.session_type === "Race") ? "#FF4444" : (modelData && modelData.session_type === "Qualifying") ? "#FFAA00" : "#666666";
                                                    anchors.verticalCenter: parent.verticalCenter
                                                }
                                                Text { 
                                                    text: (modelData && modelData.session_name ? modelData.session_name : "") + ": " + (modelData && modelData.date_start ? Qt.formatDateTime(new Date(modelData.date_start), "MMM dd yyyy, hh:mm") + " UTC" : ""); 
                                                    color: (modelData && modelData.session_type === "Race") ? "#FF4444" : (modelData && modelData.session_type === "Qualifying") ? "#FFAA00" : "#999999"; 
                                                    font.pixelSize: 11;
                                                    font.bold: !!(modelData && modelData.session_type === "Race");
                                                    anchors.verticalCenter: parent.verticalCenter;
                                                    width: 200;  // Smaller since space is limited
                                                    wrapMode: Text.Wrap;
                                                    maximumLineCount: 2;
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                // Track map
                                Image {
                                    width: parent.width * 0.4  // 40% for map
                                    height: parent.height
                                    source: model && model.trackMapPath ? model.trackMapPath : ""
                                    visible: !!(model && model.trackMapPath)
                                    fillMode: Image.PreserveAspectFit
                                    asynchronous: true
                                }
                            }
                        }
                    }

                    // Launch view buttons container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        color: "transparent"
                        visible: backend && backend.mode === "spacex"

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "upcoming", "icon": "\uf135", "tooltip": "Upcoming Launches"},
                                    {"type": "past", "icon": "\uf1da", "tooltip": "Past Launches"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    color: backend.eventType === modelData.type ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 14
                                    border.color: backend.eventType === modelData.type ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                    border.width: backend.eventType === modelData.type ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: backend.eventType = modelData.type
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
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

                    WebEngineProfile {
                        id: youtubeProfile
                        httpUserAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        httpAcceptLanguage: "en-US,en"
                        // Allow sending Referer headers for YouTube embeds
                        offTheRecord: false
                        persistentCookiesPolicy: WebEngineProfile.AllowPersistentCookies
                        httpCacheType: WebEngineProfile.DiskHttpCache
                    }

                    WebEngineView {
                        id: youtubeView
                        profile: youtubeProfile
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        url: parent.visible ? (backend.mode === "spacex" ? videoUrl : (nextRace && nextRace.circuit_short_name && circuitCoords[nextRace.circuit_short_name] ? "https://www.openstreetmap.org/export/embed.html?bbox=" + (circuitCoords[nextRace.circuit_short_name].lon - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat - 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lon + 0.01) + "," + (circuitCoords[nextRace.circuit_short_name].lat + 0.01) + "&layer=mapnik&marker=" + circuitCoords[nextRace.circuit_short_name].lat + "," + circuitCoords[nextRace.circuit_short_name].lon : "")) : ""
                        settings {
                            webGLEnabled: true
                            accelerated2dCanvasEnabled: true
                            allowRunningInsecureContent: true
                            javascriptEnabled: true
                            localContentCanAccessRemoteUrls: true
                            playbackRequiresUserGesture: false  // Allow autoplay
                            pluginsEnabled: true
                            javascriptCanOpenWindows: false
                            javascriptCanAccessClipboard: false
                            allowWindowActivationFromJavaScript: false
                        }
                        onFullScreenRequested: function(request) { request.accept(); root.visibility = Window.FullScreen }
                        onLoadingChanged: function(loadRequest) {
                            if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                console.log("YouTube/Map WebEngineView load failed:", loadRequest.errorString);
                                console.log("Error code:", loadRequest.errorCode);
                                console.log("Error domain:", loadRequest.errorDomain);

                                // Handle specific error codes
                                if (loadRequest.errorCode === 153) {
                                    console.log("ERR_MISSING_REFERER_HEADER detected - YouTube requires proper Referer header for embeds");
                                    console.log("This is a new YouTube policy requiring API client identification");
                                    console.log("Attempting to reload with proper headers...");

                                    // Auto-retry for Referer header errors
                                    reloadTimer.restart();
                                } else if (loadRequest.errorCode === 2) {
                                    console.log("ERR_FAILED - Network or server error. Check your internet connection.");
                                } else if (loadRequest.errorCode === 3) {
                                    console.log("ERR_ABORTED - Request was aborted. This may be due to page navigation.");
                                } else if (loadRequest.errorCode === 6) {
                                    console.log("ERR_FILE_NOT_FOUND - Video not found. The YouTube video may have been removed.");
                                } else if (loadRequest.errorCode === -3) {
                                    console.log("ERR_ABORTED_BY_USER - Loading was cancelled.");
                                } else {
                                    console.log("Unknown error code:", loadRequest.errorCode, "- Check network connectivity and try the reload button.");
                                }
                            } else if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                console.log("YouTube/Map WebEngineView loaded successfully");
                                reloadTimer.stop(); // Stop any pending retries
                            }
                        }

                        // Auto-retry timer for content length mismatch
                        Timer {
                            id: reloadTimer
                            interval: 3000 // 3 seconds
                            repeat: false
                            onTriggered: {
                                console.log("Attempting to reload YouTube video after error 153...");
                                youtubeView.reload();
                            }
                        }
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
                spacing: 8

                // Left pill (time and weather) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.maximumWidth: 200
                    height: 28
                    radius: 14
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
                            id: weatherText
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
                    Layout.fillWidth: true
                    Layout.minimumWidth: 400
                    Layout.maximumWidth: 1500
                    height: 28
                    radius: 14
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1
                    clip: true

                    Text {
                        id: tickerText
                        anchors.verticalCenter: parent.verticalCenter
                        text: backend.launchDescriptions.join(" \\ ")
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 14
                        font.family: "D-DIN"

                        SequentialAnimation on x {
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: tickerRect.width
                                to: -tickerText.width + 400  // Pause with text still visible
                                duration: 1600000
                            }
                            PauseAnimation { duration: 4000 }  // 4 second pause
                            PropertyAnimation {
                                to: tickerRect.width  // Reset to starting position
                                duration: 0  // Instant reset
                            }
                        }
                    }
                }

                // Right side controls - consistent spacing
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    spacing: 8
                Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "\uf021"
                        font.family: "Font Awesome 5 Free"
                        font.pixelSize: 12
                        color: backend.theme === "dark" ? "white" : "black"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            console.log("Update clicked - running update script")
                            backend.runUpdateScript()
                        }
                    }

                    ToolTip {
                        text: backend.updateAvailable ? "Update Available - Click to Update and Reboot" : "Update and Reboot"
                        delay: 500
                    }

                    // Red dot indicator for available updates
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: "#FF4444"
                        border.color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                        border.width: 1
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.topMargin: -2
                        anchors.rightMargin: -2
                        visible: !!(backend && backend.updateAvailable)
                    }
                }

                    // WiFi icon
                    Rectangle {
                        width: 28
                        height: 28
                        radius: 14
                        color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: backend.wifiConnected ? "\uf1eb" : "\uf6ab"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.wifiConnected ? "#4CAF50" : "#F44336"
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
                    // Mode selector - F1/SpaceX toggle
                    Row {
                        spacing: 4
                        Repeater {
                            model: ["F1", "SpaceX"]
                            Rectangle {
                                width: 50
                                height: 32
                                color: backend.mode === modelData.toLowerCase() ?
                                       (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                       (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                radius: 16
                                border.color: backend.mode === modelData.toLowerCase() ?
                                             (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                             (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                border.width: backend.mode === modelData.toLowerCase() ? 2 : 1

                                Behavior on color { ColorAnimation { duration: 200 } }
                                Behavior on border.color { ColorAnimation { duration: 200 } }
                                Behavior on border.width { NumberAnimation { duration: 200 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData === "F1" ? "\uf1b9" : "\uf135"  // Car for F1, Rocket for SpaceX
                                    color: backend.theme === "dark" ? "white" : "black"
                                    font.pixelSize: 16
                                    font.family: "Font Awesome 5 Free"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: backend.mode = modelData.toLowerCase()
                                }

                                ToolTip {
                                    text: modelData === "F1" ? "Formula 1 Dashboard" : "SpaceX Dashboard"
                                    delay: 500
                                }
                            }
                        }
                    }
                }

                // Launch details tray toggle
                Rectangle {
                    visible: backend.mode === "spacex"
                    Layout.preferredWidth: 50
                    Layout.preferredHeight: 28
                    radius: 14
                    color: backend.launchTrayManualMode ?
                        "#FF3838" :
                        (backend.theme === "dark" ? "#666666" : "#CCCCCC")

                    Behavior on color { ColorAnimation { duration: 200 } }

                    Rectangle {
                        width: 22
                        height: 22
                        radius: 11
                        x: backend.launchTrayManualMode ? parent.width - width - 3 : 3
                        y: 3
                        color: "white"
                        border.color: backend.theme === "dark" ? "#333333" : "#E0E0E0"
                        border.width: 1

                        Behavior on x { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: backend.setLaunchTrayManualMode(!backend.launchTrayManualMode)
                        cursorShape: Qt.PointingHandCursor
                    }

                    ToolTip {
                        text: backend.launchTrayManualMode ? "Manual: Launch banner always shown" : "Auto: Show banner within 1 hour of launch"
                        delay: 500
                    }
                }

                Item { Layout.fillWidth: true }

                // Right pill (countdown, location, theme) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 400
                    Layout.maximumWidth: 400
                    height: 28
                    radius: 14
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1


                    Row {
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: backend.countdown
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        // Location selector
                        Row {
                            spacing: 4
                            Repeater {
                                model: ["Starbase", "Vandy", "Cape", "Hawthorne"]
                                Rectangle {
                                    width: 40
                                    height: 24
                                    color: backend.location === modelData ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 12
                                    border.color: backend.location === modelData ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                    border.width: backend.location === modelData ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.substring(0, 4)  // Abbreviate: Star, Vand, Cape, Hawt
                                        color: backend.theme === "dark" ? "white" : "black"
                                        font.pixelSize: 11
                                        font.family: "D-DIN"
                                        font.bold: backend.location === modelData
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: backend.location = modelData
                                    }

                                    ToolTip {
                                        text: modelData
                                        delay: 500
                                    }
                                }
                            }
                        }

                        // Theme selector
                        Row {
                            spacing: 4
                            Repeater {
                                model: ["Light", "Dark"]
                                Rectangle {
                                    width: 45
                                    height: 24
                                    color: backend.theme === modelData.toLowerCase() ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 12
                                    border.color: backend.theme === modelData.toLowerCase() ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                    border.width: backend.theme === modelData.toLowerCase() ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData === "Light" ? "\uf185" : "\uf186"  // Sun for Light, Moon for Dark
                                        color: backend.theme === "dark" ? "white" : "black"
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: backend.theme = modelData.toLowerCase()
                                    }

                                    ToolTip {
                                        text: modelData + " Theme"
                                        delay: 500
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

            property string selectedNetwork: ""

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
                            visible: !!(backend && backend.wifiConnected)
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

                            // Remove button for remembered networks
                            Button {
                                text: "\uf2ed"
                                font.family: "Font Awesome 5 Free"
                                Layout.preferredWidth: 22
                                Layout.preferredHeight: 22
                                visible: {
                                    for (var i = 0; i < backend.rememberedNetworks.length; i++) {
                                        if (backend.rememberedNetworks[i].ssid === modelData.ssid) {
                                            return true
                                        }
                                    }
                                    return false
                                }
                                onClicked: {
                                    backend.remove_remembered_network(modelData.ssid)
                                }

                                background: Rectangle {
                                    color: "#F44336"
                                    radius: 3
                                }

                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    font.pixelSize: 10
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }

                                ToolTip {
                                    text: "Remove from remembered networks"
                                    delay: 500
                                }
                            }

                            // Connect button - compact
                            Button {
                                text: "Connect"
                                Layout.preferredWidth: 55
                                Layout.preferredHeight: 22
                                onClicked: {
                                    wifiPopup.selectedNetwork = modelData.ssid
                                    // Check if this network is remembered
                                    var isRemembered = false
                                    for (var i = 0; i < backend.rememberedNetworks.length; i++) {
                                        if (backend.rememberedNetworks[i].ssid === modelData.ssid) {
                                            isRemembered = true
                                            break
                                        }
                                    }
                                    if (isRemembered) {
                                        backend.connectToRememberedNetwork(modelData.ssid)
                                        wifiPopup.close()
                                    } else {
                                        passwordDialog.open()
                                    }
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
            height: 120
            x: (parent.width - width) / 2
            y: (parent.height - height - 200) / 2  // Leave room for keyboard
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            onOpened: {
                passwordField.focus = true
                passwordField.text = ""
            }

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
                    text: "Password for " + wifiPopup.selectedNetwork
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 13
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                RowLayout {
                    spacing: 5

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

                        color: backend.theme === "dark" ? "white" : "black"
                    }

                    Button {
                        text: "👁"
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 28
                        onClicked: {
                            passwordField.echoMode = passwordField.echoMode === TextField.Password ? TextField.Normal : TextField.Password
                            passwordField.focus = true
                        }

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            radius: 3
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
                            backend.connectToWifi(wifiPopup.selectedNetwork, passwordField.text)
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

        // Virtual Keyboard for password entry
        Popup {
            id: virtualKeyboard
            width: 360
            height: 180
            x: passwordDialog.x + passwordDialog.width / 2 - width / 2
            y: passwordDialog.y + passwordDialog.height + 5
            modal: false
            focus: false
            visible: passwordDialog.visible
            property bool shiftPressed: false
            property bool numberMode: false

            onOpened: {
                // Reset keyboard state when opened
                shiftPressed = false
                numberMode = false
            }

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

                // QWERTY keyboard rows
                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 340

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"] : (virtualKeyboard.shiftPressed ? ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"] : ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 25
                            Layout.preferredHeight: 30
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
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

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 340

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"] : (virtualKeyboard.shiftPressed ? ["A", "S", "D", "F", "G", "H", "J", "K", "L"] : ["a", "s", "d", "f", "g", "h", "j", "k", "l"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 25
                            Layout.preferredHeight: 30
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
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

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 340

                    Button {
                        text: "⇧"
                        Layout.preferredWidth: 35
                        Layout.preferredHeight: 30
                        enabled: !virtualKeyboard.numberMode
                        onClicked: {
                            virtualKeyboard.shiftPressed = !virtualKeyboard.shiftPressed
                        }

                        background: Rectangle {
                            color: parent.pressed ? "#FF6B35" : (virtualKeyboard.numberMode ? (backend.theme === "dark" ? "#2a2e2e" : "#e0e0e0") : (virtualKeyboard.shiftPressed ? "#FF9800" : (backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0")))
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["-", "_", "+", "=", "{", "}", "[", "]", "|"] : (virtualKeyboard.shiftPressed ? ["Z", "X", "C", "V", "B", "N", "M"] : ["z", "x", "c", "v", "b", "n", "m"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 25
                            Layout.preferredHeight: 30
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
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

                    Button {
                        text: "⌫"
                        Layout.preferredWidth: 35
                        Layout.preferredHeight: 30
                        onClicked: passwordField.text = passwordField.text.slice(0, -1)

                        background: Rectangle {
                            color: parent.pressed ? "#D84315" : "#FF5722"
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
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

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 340

                    Button {
                        text: virtualKeyboard.numberMode ? "ABC" : "123"
                        Layout.preferredWidth: 40
                        Layout.preferredHeight: 30
                        onClicked: {
                            virtualKeyboard.numberMode = !virtualKeyboard.numberMode
                            virtualKeyboard.shiftPressed = false  // Reset shift when switching modes
                        }

                        background: Rectangle {
                            color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0")
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
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
                        text: "Space"
                        Layout.preferredWidth: 200
                        Layout.preferredHeight: 30
                        onClicked: passwordField.text += " "

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
                        text: "Done"
                        Layout.preferredWidth: 50
                        Layout.preferredHeight: 30
                        onClicked: virtualKeyboard.visible = false

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

        // Sliding launch details tray
        Popup {
            id: launchTray
            width: parent.width
            height: 25  // Start with larger collapsed height
            x: 0
            y: 0  // Position at top of screen
            modal: false
            focus: false
            visible: !!(backend && backend.launchTrayVisible)
            closePolicy: Popup.NoAutoClose

            leftPadding: 15
            rightPadding: 15
            topPadding: 0
            bottomPadding: 0
            leftMargin: 0
            rightMargin: 0
            topMargin: 0
            bottomMargin: 0

            property real expandedHeight: parent.height
            property real collapsedHeight: 25  // Increased for better visibility when collapsed
            property var nextLaunch: null
            property real colorFactor: (height - collapsedHeight) / (expandedHeight - collapsedHeight)
            property color collapsedColor: "#FF3838"
            property color expandedColor: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
            property string tMinus: ""

            Timer {
                interval: 1000  // Update every second for testing
                running: true
                repeat: true
                onTriggered: {
                    var arr = backend.get_upcoming_launches();
                    launchTray.nextLaunch = arr && arr[0] ? arr[0] : null;
                    // Use the backend's countdown calculation for consistency
                    launchTray.tMinus = backend.countdown;
                }
            }

            background: Rectangle {
                color: Qt.rgba(
                    launchTray.collapsedColor.r + launchTray.colorFactor * (launchTray.expandedColor.r - launchTray.collapsedColor.r),
                    launchTray.collapsedColor.g + launchTray.colorFactor * (launchTray.expandedColor.g - launchTray.collapsedColor.g),
                    launchTray.collapsedColor.b + launchTray.colorFactor * (launchTray.expandedColor.b - launchTray.collapsedColor.b),
                    0.7 + launchTray.colorFactor * 0.3  // Fade from 70% to 100% opacity
                )
                radius: 12
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1

                Behavior on color {
                    ColorAnimation { duration: 300 }
                }
            }

            // Smooth animation for height changes
            Behavior on height {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.OutCubic
                }
            }

            // Bottom status text - T-minus on left, launch name on right
            Item {
                width: parent.width
                height: 20
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 3  // Moved up slightly for better centering
                z: -1  // Ensure this is behind the drag handle

                Text {
                    text: launchTray.tMinus || "T-0"
                    font.pixelSize: 14
                    font.bold: true
                    color: "white"
                    anchors.left: parent.left
                    anchors.leftMargin: 0
                    anchors.right: parent.horizontalCenter
                    anchors.rightMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignLeft
                }

                Text {
                    text: launchTray.nextLaunch ? launchTray.nextLaunch.mission : "No upcoming launches"
                    font.pixelSize: 14
                    font.bold: true
                    color: "white"
                    elide: Text.ElideRight
                    anchors.right: parent.right
                    anchors.rightMargin: 0
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignRight
                }
            }

            // Drag handle at bottom
            Rectangle {
                width: parent.width
                height: 60  // Reduced height for more compact touch area
                color: "transparent"
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 2  // Small gap to match original spacing
                z: 1  // Ensure this is on top for touch events

                // Double chevron indicator
                Item {
                    width: 60
                    height: 30
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -3  // Moved down slightly for better centering
                    anchors.horizontalCenter: parent.horizontalCenter

                    Image {
                        source: "file:///" + chevronPath
                        width: 24
                        height: 24
                        anchors.centerIn: parent
                        rotation: launchTray.height > launchTray.collapsedHeight + 50 ? -90 : 90  // Point up when expanded, down when collapsed
                        Behavior on rotation {
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent  // Now fills the larger 40px height area

                    property point startGlobalPos: Qt.point(0, 0)
                    property real startHeight: 0
                    property bool isDragging: false

                    onPressed: {
                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                        startHeight = launchTray.height
                        isDragging = true
                    }

                    onPositionChanged: {
                        if (isDragging && pressed) {
                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                            var newHeight = startHeight + deltaY

                            // Constrain the height
                            newHeight = Math.max(launchTray.collapsedHeight, Math.min(launchTray.expandedHeight, newHeight))

                            launchTray.height = newHeight
                        }
                    }

                    onReleased: {
                        isDragging = false

                        // Snap based on drag distance from start position
                        var delta = launchTray.height - startHeight
                        var range = launchTray.expandedHeight - launchTray.collapsedHeight
                        var threshold = 0.15 * range

                        if (delta > threshold) {
                            // Dragged down enough, snap to expanded
                            launchTray.height = launchTray.expandedHeight
                        } else if (delta < -threshold) {
                            // Dragged up enough, snap to collapsed
                            launchTray.height = launchTray.collapsedHeight
                        } else {
                            // Not dragged enough, snap back to start
                            launchTray.height = startHeight
                        }
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 10
                anchors.bottomMargin: 10  // Reduced to bring content closer to bottom handle
                spacing: 10
                clip: true  // Ensure content doesn't overflow

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 15

                    RowLayout {
                        opacity: launchTray.colorFactor
                        visible: launchTray.height > launchTray.collapsedHeight + 10
                        Behavior on opacity { NumberAnimation { duration: 300 } }
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 10

                        Flickable {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            contentHeight: launchDetailsColumn.height
                            clip: true

                            Rectangle {
                                id: launchDetailsColumn
                                width: parent.width
                                radius: 12
                                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                                implicitHeight: launchDetailsLayout.height

                                ColumnLayout {
                                    id: launchDetailsLayout
                                    anchors.fill: parent
                                    anchors.margins: 15
                                    spacing: 10

                                    ColumnLayout {
                                        spacing: 6

                                        Text {
                                            text: "🚀 MISSION: " + (launchTray.nextLaunch ? launchTray.nextLaunch.mission.toUpperCase() : "NO UPCOMING LAUNCHES")
                                            font.pixelSize: 18
                                            font.bold: true
                                            font.letterSpacing: 1
                                            color: "#FF6B35"
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        // Table-like layout for launch details
                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📅"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LAUNCH DATE:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.local_date : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "⏰"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LAUNCH TIME:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.local_time : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📡"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "NET:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.net : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📊"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "STATUS:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.status.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: launchTray.nextLaunch && launchTray.nextLaunch.status.toLowerCase().includes("go") ? "#00FF88" : "#FF4444"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🚀"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "VEHICLE:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.rocket.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🛰️"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "ORBIT:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.orbit.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🏗️"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "PAD:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.pad.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🎥"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "STREAM:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.video_url : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                wrapMode: Text.Wrap
                                                visible: launchTray.nextLaunch
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            radius: 0
                            color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"

                            WebEngineView {
                                id: globeView
                                anchors.fill: parent
                                anchors.margins: 0
                                url: globeUrl
                                backgroundColor: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
                                zoomFactor: 1.0
                                settings.javascriptCanAccessClipboard: false
                                settings.allowWindowActivationFromJavaScript: false

                                onLoadingChanged: function(loadRequest) {
                                    console.log("WebEngineView loading changed:", loadRequest.status, loadRequest.url);
                                    if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                        console.log("Globe HTML loaded successfully");
                                        // Update trajectory when globe loads
                                        var trajectoryData = backend.get_launch_trajectory();
                                        if (trajectoryData) {
                                            globeView.runJavaScript("console.log('About to call updateTrajectory'); updateTrajectory(" + JSON.stringify(trajectoryData) + "); console.log('Called updateTrajectory');");
                                        }
                                    } else if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                        console.log("Globe HTML failed to load:", loadRequest.errorString);
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            radius: 12
                            color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"

                            WebEngineView {
                                id: xComView
                                anchors.fill: parent
                                anchors.margins: 5
                                url: "https://x.com/SpaceX"
                                zoomFactor: 0.6
                            }
                        }
                    }
                }
            }
        }
    }
}
"""
engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
if not engine.rootObjects():
    logger.error("QML root object creation failed (see earlier QML errors above).")
    print("QML load failed. Check console for Qt errors.")
    sys.exit(-1)
sys.exit(app.exec())