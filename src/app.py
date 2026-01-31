import functions as funcs
# Initialize environment variables before importing PyQt6 to ensure Qt picks them up
funcs.setup_dashboard_environment()

import platform
IS_WINDOWS = platform.system() == 'Windows'
import sys
import os
import json
from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtProperty, QObject, QAbstractListModel, QModelIndex, QVariant, pyqtSlot, qInstallMessageHandler, QRectF, QPoint, QDir, QThread
from PyQt6.QtGui import QFontDatabase, QCursor, QRegion, QPainter, QPen, QBrush, QColor, QFont, QLinearGradient
from PyQt6.QtQml import QQmlApplicationEngine, QQmlContext, qmlRegisterType
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface, QQuickPaintedItem
from PyQt6.QtWebEngineQuick import QtWebEngineQuick
from PyQt6.QtCharts import QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz
from dateutil.tz import tzlocal
import time
import subprocess
import signal
import calendar
import threading
from functions import (
    # status helpers
    profiler,
    set_loader_status_callback,
    emit_loader_status,
    # cache io
    load_cache_from_file,
    save_cache_to_file,
    # launch cache helpers
    load_launch_cache,
    save_launch_cache,
    # network/system helpers
    check_wifi_status,
    fetch_launches,
    fetch_weather,
    get_encryption_key,
    encrypt_password,
    decrypt_password,
    get_wifi_interface,
    load_remembered_networks,
    save_remembered_networks,
    load_last_connected_network,
    save_last_connected_network,
    start_http_server,
    # parsing/math helpers
    # CACHE_REFRESH constants
    CACHE_REFRESH_INTERVAL_PREVIOUS,
    CACHE_REFRESH_INTERVAL_UPCOMING,
    CACHE_REFRESH_INTERVAL_F1,
    CACHE_REFRESH_INTERVAL_F1_SCHEDULE,
    CACHE_REFRESH_INTERVAL_F1_STANDINGS,
    # CACHE_FILE constants
    TRAJECTORY_CACHE_FILE,
    RUNTIME_CACHE_FILE_LAUNCHES,
    CACHE_FILE_WEATHER,
    RUNTIME_CACHE_FILE_CALENDAR,
    RUNTIME_CACHE_FILE_CHART_TRENDS,
    RUNTIME_CACHE_FILE_NARRATIVES,
    WIFI_KEY_FILE,
    REMEMBERED_NETWORKS_FILE,
    LAST_CONNECTED_NETWORK_FILE,
    # data constants
    location_settings,
    radar_locations,
    circuit_coords,
    perform_wifi_scan,
    manage_nm_autoconnect,
    test_network_connectivity,
    get_git_version_info,
    check_github_for_updates,
    get_launch_trends_series,
    get_launch_trajectory_data,
    group_event_data,
    LAUNCH_DESCRIPTIONS,
    check_wifi_interface,
    get_wifi_interface_info,
    get_wifi_debug_info,
    start_update_script,
    generate_month_labels_for_days,
    connect_to_wifi_nmcli,
    connect_to_wifi_worker,
    get_max_value_from_series,
    get_next_launch_info,
    get_upcoming_launches_list,
    initialize_all_weather,
    get_best_wifi_reconnection_candidate,
    calculate_chart_interval,
    filter_and_sort_wifi_networks,
    get_nmcli_profiles,
    fetch_weather_for_all_locations,
    perform_full_dashboard_data_load,
    setup_dashboard_environment,
    setup_dashboard_logging,
    format_qt_message,
    get_launch_tray_visibility_state,
    get_countdown_string,
    get_countdown_breakdown,
    get_update_progress_summary,
    perform_bootstrap_diagnostics,
    disconnect_from_wifi,
    bring_up_nm_connection,
    sync_remembered_networks,
    fetch_narratives,
    remove_nm_connection,
    get_closest_x_video_url,
    load_theme_settings,
    save_theme_settings,
    load_branch_setting,
    save_branch_setting,
    get_rpi_config_resolution
)
# DBus imports are now conditional and imported only on Linux
# import dbus
# import dbus.mainloop.glib
# from gi.repository import GLib

# Loader status helpers moved to functions.py

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

# test update 9

# Initialize logging
setup_dashboard_logging(__file__)
logger = logging.getLogger(__name__)

logger.info(f"BOOT: Environment initialized. DASHBOARD_WIDTH={os.environ.get('DASHBOARD_WIDTH', 'Not Set')}, QT_SCALE_FACTOR={os.environ.get('QT_SCALE_FACTOR')}")

# Qt message handler to surface QML / Qt internal messages (errors, warnings, info)
# Install as early as possible after logger initialization

def _qt_message_handler(mode, context, message):
    msg = format_qt_message(mode, context, message)
    if msg: logger.error(msg)

# Install the handler only once
try:
    qInstallMessageHandler(_qt_message_handler)
except Exception as _e:  # Fallback (should not normally occur)
    logger.warning(f"Failed to install Qt message handler: {_e}")

# CACHE_REFRESH_INTERVAL constants and CACHE_FILE paths are now imported from functions.py
f1_cache = None

# F1 Team colors, location settings, radar URLs, and circuit coordinates moved to functions.py

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
    LandingTypeRole = Qt.ItemDataRole.UserRole + 20
    LandingLocationRole = Qt.ItemDataRole.UserRole + 21
    XVideoUrlRole = Qt.ItemDataRole.UserRole + 22

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
                elif role == self.LandingTypeRole:
                    return item.get('landing_type', '')
                elif role == self.LandingLocationRole:
                    return item.get('landing_location', '')
                elif role == self.XVideoUrlRole:
                    return item.get('x_video_url', '')
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
        roles[self.LandingTypeRole] = b"landingType"
        roles[self.LandingLocationRole] = b"landingLocation"
        roles[self.XVideoUrlRole] = b"xVideoUrl"
        return roles

    def update_data(self):
        profiler.mark(f"EventModel: update_data Start ({self._mode}, {self._event_type})")
        self.beginResetModel()
        try:
            # Delegate logic to UI-agnostic helper in functions.py
            profiler.mark(f"EventModel: Calling group_event_data ({self._mode})")
            self._grouped_data = group_event_data(self._data, self._mode, self._event_type, self._tz)
        except Exception as e:
            logger.error(f"EventModel: Failed to update data: {e}")
            self._grouped_data = []
        self.endResetModel()
        profiler.mark(f"EventModel: update_data End (count: {len(self._grouped_data)})")

class WeatherForecastModel(QAbstractListModel):
    DayRole = Qt.ItemDataRole.UserRole + 1
    TempLowRole = Qt.ItemDataRole.UserRole + 2
    TempHighRole = Qt.ItemDataRole.UserRole + 3
    ConditionRole = Qt.ItemDataRole.UserRole + 4
    WindRole = Qt.ItemDataRole.UserRole + 5
    TempsRole = Qt.ItemDataRole.UserRole + 6
    WindsRole = Qt.ItemDataRole.UserRole + 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return QVariant()
        item = self._data[index.row()]
        if role == self.DayRole:
            return item.get('day', '')
        elif role == self.TempLowRole:
            return item.get('temp_low', '')
        elif role == self.TempHighRole:
            return item.get('temp_high', '')
        elif role == self.ConditionRole:
            return item.get('condition', '')
        elif role == self.WindRole:
            return item.get('wind', '')
        elif role == self.TempsRole:
            return item.get('temps', [])
        elif role == self.WindsRole:
            return item.get('winds', [])
        return QVariant()

    def roleNames(self):
        return {
            self.DayRole: b"day",
            self.TempLowRole: b"tempLow",
            self.TempHighRole: b"tempHigh",
            self.ConditionRole: b"condition",
            self.WindRole: b"wind",
            self.TempsRole: b"temps",
            self.WindsRole: b"winds"
        }

    def update_data(self, forecast_list):
        self.beginResetModel()
        self._data = forecast_list
        self.endResetModel()

class DataLoader(QObject):
    finished = pyqtSignal(dict, dict, list, dict)
    statusUpdate = pyqtSignal(str)

    def __init__(self, tz_obj=None, active_location=None):
        super().__init__()
        self.tz_obj = tz_obj
        self.active_location = active_location

    def run(self):
        logger.info(f"DataLoader: Starting parallel data loading (active: {self.active_location})...")
        def _safe_emit_status(msg):
            try: self.statusUpdate.emit(msg)
            except RuntimeError: pass

        def _safe_emit_finished(l, f, w, c):
            try: self.finished.emit(l, f, w, c)
            except RuntimeError: pass

        profiler.mark("DataLoader: Starting full data load")
        # Delegate full load to functions.py
        launch_data, weather_data, narratives, calendar_mapping = perform_full_dashboard_data_load(
            location_settings, 
            status_callback=_safe_emit_status,
            tz_obj=self.tz_obj,
            active_location=self.active_location
        )
        profiler.mark("DataLoader: Full data load complete")

        _safe_emit_finished(launch_data, weather_data, narratives, calendar_mapping)

class LaunchUpdater(QObject):
    finished = pyqtSignal(dict, list, dict)
    def __init__(self, tz_obj=None):
        super().__init__()
        self.tz_obj = tz_obj

    def run(self):
        profiler.mark("LaunchUpdater: Starting update")
        launch_data = fetch_launches()
        narratives = fetch_narratives(launch_data)
        
        # Pre-compute calendar mapping
        from functions import get_calendar_mapping
        calendar_mapping = get_calendar_mapping(launch_data, tz_obj=self.tz_obj)
        
        profiler.mark("LaunchUpdater: Update complete")
        self.finished.emit(launch_data, narratives, calendar_mapping)

class WeatherUpdater(QObject):
    finished = pyqtSignal(dict)
    def __init__(self, active_location=None):
        super().__init__()
        self.active_location = active_location

    def run(self):
        profiler.mark(f"WeatherUpdater: Starting update (active: {self.active_location})")
        weather_data = fetch_weather_for_all_locations(location_settings, self.active_location)
        profiler.mark("WeatherUpdater: Update complete")
        self.finished.emit(weather_data)

class NextLaunchUpdater(QObject):
    finished = pyqtSignal(dict)
    def __init__(self, launch_id):
        super().__init__()
        self.launch_id = launch_id
    def run(self):
        profiler.mark(f"NextLaunchUpdater: Starting update ({self.launch_id})")
        # Use v2.3.0 detailed mode
        detailed_data = funcs.fetch_launch_details(self.launch_id)
        profiler.mark(f"NextLaunchUpdater: Update complete ({self.launch_id})")
        if detailed_data:
            self.finished.emit(detailed_data)

class Backend(QObject):
    modeChanged = pyqtSignal()
    eventTypeChanged = pyqtSignal()
    countdownChanged = pyqtSignal()
    timeChanged = pyqtSignal()
    weatherChanged = pyqtSignal()
    launchesChanged = pyqtSignal()
    chartViewModeChanged = pyqtSignal()
    chartTypeChanged = pyqtSignal()
    f1Changed = pyqtSignal() # Kept for potential future use or to avoid breaking QML bindings if they exist but weren't found
    themeChanged = pyqtSignal()
    locationChanged = pyqtSignal()
    radarBaseUrlChanged = pyqtSignal()
    eventModelChanged = pyqtSignal()
    wifiNetworksChanged = pyqtSignal()
    wifiConnectedChanged = pyqtSignal()
    wifiConnectingChanged = pyqtSignal()
    rememberedNetworksChanged = pyqtSignal()
    networkConnectedChanged = pyqtSignal()
    loadingFinished = pyqtSignal()
    # New signals for signal-based startup flow
    launchCacheReady = pyqtSignal()
    firstOnline = pyqtSignal()
    weatherForecastModelChanged = pyqtSignal()
    updateGlobeTrajectory = pyqtSignal()
    reloadWebContent = pyqtSignal()
    launchTrayVisibilityChanged = pyqtSignal()
    loadingStatusChanged = pyqtSignal()
    updateAvailableChanged = pyqtSignal()
    updateDialogRequested = pyqtSignal()
    targetBranchChanged = pyqtSignal()
    versionInfoChanged = pyqtSignal()
    liveLaunchUrlChanged = pyqtSignal()
    videoUrlChanged = pyqtSignal()
    brightnessChanged = pyqtSignal()
    contrastChanged = pyqtSignal()
    colorPresetChanged = pyqtSignal()
    videoGainRedChanged = pyqtSignal()
    videoGainGreenChanged = pyqtSignal()
    videoGainBlueChanged = pyqtSignal()
    sharpnessChanged = pyqtSignal()
    inputSourceChanged = pyqtSignal()
    powerModeChanged = pyqtSignal()
    selectedLaunchChanged = pyqtSignal()
    widthChanged = pyqtSignal()
    heightChanged = pyqtSignal()
    # Globe spin/watchdog feature flag
    globeAutospinGuardChanged = pyqtSignal()
    # WiFi scanning progress notify (for UI spinner)
    wifiScanInProgressChanged = pyqtSignal()
    # WiFi scan results delivered from background thread (queued to UI thread)
    wifiScanResultsReady = pyqtSignal(list)
    # Emitted by background boot worker to deliver results to main thread
    initialChecksReady = pyqtSignal(bool, bool, dict, dict)
    # Background update result from boot worker (moved out of critical path)
    initialUpdateCheckReady = pyqtSignal(bool, dict)
    # Update progress UI signals
    updatingInProgressChanged = pyqtSignal()
    updatingStatusChanged = pyqtSignal()
    # Signal for thread-safe WiFi status updates
    wifiCheckReady = pyqtSignal(bool, str)
    touchCalibrationExistsChanged = pyqtSignal()
    calibrationStarted = pyqtSignal()
    calibrationFinished = pyqtSignal()

    def __init__(self, initial_wifi_connected=False, initial_wifi_ssid=""):
        super().__init__()
        logger.info("Backend initializing...")
        self._mode = 'spacex'
        self._event_type = 'upcoming'
        self._theme = load_theme_settings()
        self._target_branch = load_branch_setting()
        self._location = 'Starbase'
        # Initialize timezone based on default location
        self._tz = tzlocal()
        if self._location in location_settings:
            tz_name = location_settings[self._location].get('timezone', 'UTC')
            try:
                self._tz = pytz.timezone(tz_name)
                logger.info(f"Backend: Initial timezone set to {tz_name} for {self._location}")
            except Exception as e:
                logger.error(f"Backend: Failed to set initial timezone {tz_name}: {e}")
        
        self._chart_view_mode = 'actual'  # 'actual' or 'cumulative'
        self._chart_type = 'line'  # 'bar' or 'line'
        self._boot_mode = True
        self._isLoading = True
        self._loading_status = "Initializing..."
        self._online_load_in_progress = False
        # Try to load initial data from cache to avoid empty UI on first load
        try:
            profiler.mark("Backend: Loading Launch Cache Start")
            prev = load_launch_cache('previous')
            up = load_launch_cache('upcoming')
            self._launch_data = {
                'previous': prev['data'] if prev else [],
                'upcoming': up['data'] if up else []
            }
            profiler.mark("Backend: Loading Launch Cache End")
        except Exception as e:
            logger.warning(f"Failed to load initial launch cache: {e}")
            self._launch_data = {'previous': [], 'upcoming': []}
        
        profiler.mark("Backend: get_closest_x_video_url Start")
        self._live_launch_url = get_closest_x_video_url(self._launch_data)
        profiler.mark("Backend: get_closest_x_video_url End")
        self._launch_descriptions = LAUNCH_DESCRIPTIONS
        self._weather_data = {}
        try:
            profiler.mark("Backend: Loading Weather Cache Start")
            weather_cache = load_cache_from_file(CACHE_FILE_WEATHER)
            if weather_cache and 'data' in weather_cache:
                self._weather_data = weather_cache['data']
                logger.info(f"Backend: Loaded cached weather for {len(self._weather_data)} locations")
                # Force timestamp update to ensure UI sees recent data if cache is fresh
                if 'timestamp' in weather_cache:
                    logger.info(f"Backend: Weather cache timestamp: {weather_cache['timestamp']}")
            profiler.mark("Backend: Loading Weather Cache End")
        except Exception as e:
            logger.debug(f"Failed to load initial weather cache: {e}")

        self._weather_forecast_model = WeatherForecastModel()
        # Seed the forecast model from cache immediately if available
        if self._weather_data:
            self._on_weather_updated(self._weather_data)
        # Initialize radar base URL
        self._radar_base_url = radar_locations.get(self._location, radar_locations.get('Starbase', ''))
        self._f1_data = {'schedule': [], 'standings': [], 'drivers': [], 'constructors': []}
        profiler.mark("Backend: Initializing EventModel Start")
        self._event_model = EventModel(self._launch_data, self._mode, self._event_type, self._tz)
        profiler.mark("Backend: Initializing EventModel End")
        self._launch_trends_cache = {}  # Cache for launch trends series
        try:
            trends_cache = load_cache_from_file(RUNTIME_CACHE_FILE_CHART_TRENDS)
            if trends_cache:
                self._launch_trends_cache = trends_cache['data']
                logger.info("Backend: Loaded launch trends cache from disk")
        except Exception as e:
            logger.debug(f"Failed to load launch trends cache: {e}")
        # Platform-aware defaults for resolution and scaling
        detected_w, detected_h = get_rpi_config_resolution()
        is_small_display = (os.environ.get("DASHBOARD_WIDTH") == "1480" or detected_w == 1480 or detected_h == 320)
        is_large_display = (os.environ.get("DASHBOARD_WIDTH") == "3840" or detected_w == 3840 or detected_h == 1100)
        is_2k_display = (os.environ.get("DASHBOARD_WIDTH") == "2560" or detected_w == 2560 or detected_h == 734)
        
        if platform.system() == 'Windows' or is_small_display:
            # Default to small display resolution (1480x320) and 1x scale
            default_w, default_h, default_s = 1480, 320, "1.0"
        elif is_2k_display:
            # Matches DFR1125 in 2K mode (2560x734)
            default_w, default_h, default_s = 2560, 734, "1.333"
            is_large_display = True # Treat as large display for DDC/CI features
        elif is_large_display:
            # Matches DFR1125 4K Bar Display (14 inch 3840x1100)
            default_w, default_h, default_s = 3840, 1100, "2.0"
        else:
            # Linux default fallback (usually large display for backward compatibility)
            default_w, default_h, default_s = 3840, 1100, "2.0"

        self._width = int(os.environ.get("DASHBOARD_WIDTH", default_w))
        self._height = int(os.environ.get("DASHBOARD_HEIGHT", default_h))
        self._is_large_display = is_large_display
        self._brightness = 100
        self._target_brightness = 100
        self._last_applied_brightness = -1
        self._contrast = 50
        self._target_contrast = 50
        self._last_applied_contrast = -1
        self._color_preset = "02"
        self._video_gain_red = 50
        self._target_video_gain_red = 50
        self._last_applied_video_gain_red = -1
        self._video_gain_green = 50
        self._target_video_gain_green = 50
        self._last_applied_video_gain_green = -1
        self._video_gain_blue = 50
        self._target_video_gain_blue = 50
        self._last_applied_video_gain_blue = -1
        self._sharpness = 50
        self._target_sharpness = 50
        self._last_applied_sharpness = -1
        self._input_source = "11"
        self._power_mode = "01"
        self._touch_calibration_exists = funcs.check_touch_calibration_exists()
        self._brightness_lock = threading.Lock()
        self._brightness_timer = QTimer()
        self._brightness_timer.setSingleShot(True)
        self._brightness_timer.timeout.connect(self._apply_brightness)
        
        self._display_settings_timer = QTimer()
        self._display_settings_timer.setSingleShot(True)
        self._display_settings_timer.timeout.connect(self._apply_display_settings)

        if self._is_large_display and not IS_WINDOWS:
            QTimer.singleShot(5000, self._initial_display_settings_fetch)
        
        # Support logical scaling for High DPI displays
        try:
            scale_str = os.environ.get("DASHBOARD_SCALE", default_s)
            scale = float(scale_str)
            if scale != 1.0:
                # If we are scaling the UI up (e.g. scale=2.0), we need to reduce the logical 
                # window size so that the physical window (logical * scale) remains the same.
                self._width = int(self._width / scale)
                self._height = int(self._height / scale)
            
            logger.info(f"Backend: Initialized resolution: {self._width}x{self._height} (logical), scale: {scale}")
        except (ValueError, TypeError):
            logger.warning(f"Backend: Invalid DASHBOARD_SCALE value: {scale_str}")
            scale = 1.0

        try:
            cal_cache = load_cache_from_file(RUNTIME_CACHE_FILE_CALENDAR)
            if cal_cache:
                self._launches_by_date_cache = cal_cache['data']
                logger.info("Backend: Loaded calendar cache from disk")
        except Exception as e:
            logger.debug(f"Failed to load calendar cache: {e}")
        self._precomputing_calendar = False
        self._precomputing_trends = False
        self._update_available = False
        self._launch_tray_manual_override = None  # None = auto, True = show, False = hide
        self._last_update_check = None  # Track when updates were last checked
        self._current_version_info = None  # Cached current version info
        self._latest_version_info = None  # Cached latest version info
        self._update_checking = False  # Track if update check is in progress
        # Throttle web content reload signals to avoid flapping-induced UI hiccups
        self._last_web_reload_emit = 0.0
        self._min_reload_emit_interval_sec = 8.0
        self._last_live_url_update = 0.0
        self._last_tray_visible = False
        
        # WiFi properties - initialize with provided values
        self._wifi_networks = []
        self._wifi_connected = initial_wifi_connected
        self._wifi_connecting = False
        self._current_wifi_ssid = initial_wifi_ssid
        self._target_wifi_ssid = None # Track target SSID to prevent premature state clearing
        # Expose scan progress to QML for spinner/disabled state
        self._wifi_scan_in_progress = False
        self._remembered_networks = load_remembered_networks()
        self._last_connected_network = load_last_connected_network()
        # Notify QML that remembered networks are available at startup
        # Notify QML that remembered networks are available at startup
        try:
            self.rememberedNetworksChanged.emit()
            self.wifiCheckReady.connect(self._apply_wifi_status) # Connect new signal
        except Exception:
            pass
        
        # Network connectivity properties (separate from WiFi)
        # Optimistically mirror Wi‑Fi state so the header icon doesn't show
        # a red disconnected badge during splash when we're actually online.
        # A background check will correct this within seconds if wrong.
        self._network_connected = bool(initial_wifi_connected)
        self._last_network_check = None
        self._network_check_in_progress = False

        # Update progress UI state
        self._updating_in_progress = False
        self._updating_status = ""
        self._update_log_timer = None
        self._update_log_path = '/tmp/spacex-dashboard-update.log' if platform.system() == 'Linux' else None
        self._updater_pid = None  # PID of detached update script for cancellation on Linux

        # Initialize videoUrl to a safe default while HTTP server starts
        self._video_url = ""
        self._selected_launch_mission = ""  # Track which launch is currently selected
        self._http_ready_timer = QTimer(self)
        self._http_ready_timer.setInterval(100)
        self._http_ready_timer.timeout.connect(self._check_http_server_ready)
        self._http_ready_timer.start()

        # DataLoader will be started after WiFi check in main startup
        self.loader = None
        self.thread = None
        self._data_loading_deferred = False
        self._first_online_emitted = False
        self._web_reloaded_after_online = False
        # Globe watchdog/auto-resume feature flag (exposed to QML+globe.html)
        self._globe_autospin_guard = True
        # Trajectory precompute/debounce helpers
        self._trajectory_recompute_timer = QTimer(self)
        self._trajectory_recompute_timer.setSingleShot(True)
        try:
            self._trajectory_recompute_timer.setInterval(2000)  # Increased from 250ms for performance
        except Exception:
            pass
        self._trajectory_compute_inflight = False
        self._trajectory_emit_timer = QTimer(self)
        self._trajectory_emit_timer.setSingleShot(True)
        try:
            self._trajectory_emit_timer.setInterval(500)  # Increased from 120ms for performance
        except Exception:
            pass

        self._time_timer = QTimer(self)
        self._time_timer.setInterval(5000)  # Increased from 1000ms for performance - time display updates every 5 seconds
        self._time_timer.timeout.connect(self.update_time)
        self._time_timer.start()

        def _on_traj_timer():
            try:
                self._compute_trajectory_async()
            except Exception as _e:
                logger.debug(f"Failed to start async trajectory compute: {_e}")

        try:
            self._trajectory_recompute_timer.timeout.connect(_on_traj_timer)
        except Exception as _e:
            logger.debug(f"Could not connect trajectory timer: {_e}")

        logger.info(f"Initial WiFi status: connected={initial_wifi_connected}, ssid='{initial_wifi_ssid}'")
        logger.info("Setting up timers...")
        # Route background boot results back to the main thread
        try:
            self.initialChecksReady.connect(self._apply_initial_checks_results)
            self.initialUpdateCheckReady.connect(self._apply_initial_update_result)
        except Exception as _e:
            logger.debug(f"Could not connect boot result signals: {_e}")
        # Connect Wi‑Fi scan results signal (ensures UI-thread application)
        try:
            self.wifiScanResultsReady.connect(self._apply_wifi_scan_results)
        except Exception as _e:
            logger.debug(f"Could not connect wifiScanResultsReady signal: {_e}")
        # Boot guard timer placeholder
        self._initial_checks_guard_timer = None
        
        self._timers_initialized = False
        
        # Safety timer: if we don't get online data within 5s, dismiss splash and show cached data
        self._loading_timeout_timer = QTimer(self)
        self._loading_timeout_timer.setSingleShot(True)
        self._loading_timeout_timer.setInterval(5000)
        self._loading_timeout_timer.timeout.connect(self._on_loading_timeout)
        self._loading_timeout_timer.start()

        # Emit initial states on the next Qt tick so QML bindings are already connected
        try:
            def _emit_initial_connectivity():
                try:
                    logger.debug("Splash: emitting initial wifiConnectedChanged + networkConnectedChanged")
                    self.wifiConnectedChanged.emit()
                except Exception as _e1:
                    logger.debug(f"Failed to emit initial wifiConnectedChanged: {_e1}")
                try:
                    self.networkConnectedChanged.emit()
                except Exception as _e2:
                    logger.debug(f"Failed to emit initial networkConnectedChanged: {_e2}")

            QTimer.singleShot(0, _emit_initial_connectivity)
        except Exception as _e:
            logger.debug(f"Failed to schedule initial connectivity emits: {_e}")

        # Kick off an async network connectivity check right away to validate
        # the optimistic value without blocking the UI.
        try:
            QTimer.singleShot(0, self._start_network_connectivity_check_async)
        except Exception as _e:
            logger.debug(f"Failed to schedule initial async connectivity check: {_e}")

        # Attempt boot-time Wi‑Fi scan and auto-reconnect to the most recently used network (non-blocking)
        # First, kick off an initial scan so the network list is populated during splash
        # and any subsequent auto-reconnect uses the same discovery path as the Scan button.
        def _boot_initial_scan():
            try:
                logger.info("BOOT: Performing initial WiFi scan to populate network list…")
                self.scanWifiNetworks()
            except Exception as _e:
                logger.debug(f"Failed to perform boot-time WiFi scan: {_e}")

        def _boot_autoreconnect():
            try:
                # Always perform scan at boot for initial list, regardless of platform
                # Auto-reconnect logic remains Linux-focused (Pi), other platforms keep manual connect.
                if platform.system() != 'Linux':
                    return
                if self._wifi_connected or self._wifi_connecting:
                    return
                if not self._last_connected_network or not self._last_connected_network.get('ssid'):
                    return
                logger.info("BOOT: Scheduling auto-reconnect to last WiFi network…")
                # Run the scanning/connection in a background thread to avoid UI stalls
                try:
                    self._boot_auto_reconnect_in_progress = True
                except Exception:
                    pass
                def _worker():
                    try:
                        self._auto_reconnect_to_last_network(boot_time=True)
                    finally:
                        # Clear the in-progress flag regardless of outcome
                        try:
                            self._boot_auto_reconnect_in_progress = False
                        except Exception:
                            pass
                threading.Thread(target=_worker, daemon=True).start()
            except Exception as _e:
                logger.debug(f"Failed to schedule boot-time auto-reconnect: {_e}")

        # Seed bootstrap: apply git/runtime cached data immediately and exit splash based on signal, no time-based waits
        try:
            QTimer.singleShot(0, self._seed_bootstrap)
        except Exception as _e:
            logger.debug(f"Failed to schedule seed bootstrap: {_e}")

        # When network connectivity flips to online for the first time, begin online data loading and refresh web embeds
        try:
            def _on_network_connected_changed():
                try:
                    if self._network_connected and not self._first_online_emitted:
                        self._first_online_emitted = True
                        logger.info("BOOT: firstOnline detected — emitting signal and starting online data load")
                        try:
                            self.firstOnline.emit()
                        except Exception:
                            pass
                        # Start data loading immediately (no guards or timeouts)
                        self._start_data_loading_online()
                except Exception as _e:
                    logger.debug(f"Error in firstOnline handler: {_e}")

            self.networkConnectedChanged.connect(_on_network_connected_changed)
        except Exception as _e:
            logger.debug(f"Failed to connect networkConnectedChanged to firstOnline handler: {_e}")

        # Wait a moment so system services (wpa_supplicant/NetworkManager) are ready
        # Kick off an initial scan early for the UI list, but don't block auto‑reconnect on it.
        # Try auto‑reconnect a bit earlier (~1.5s) since nmcli profile bring‑up doesn't require scan results.
        try:
            QTimer.singleShot(800, _boot_initial_scan)
            QTimer.singleShot(1500, _boot_autoreconnect)
        except Exception as _e:
            logger.debug(f"Failed to set boot-time auto-reconnect timer: {_e}")

        logger.info("Backend initialization complete")
        logger.info(f"Initial theme: {self._theme}")
        logger.info(f"Initial location: {self._location}")
        logger.info(f"Initial time: {self.currentTime}")
        logger.info(f"Initial countdown: {self.countdown}")

    @pyqtSlot(str, str)
    def add_remembered_network(self, ssid, password):
        """Add a network to remembered list and persist to file"""
        ts = time.time()
        self._remembered_networks = sync_remembered_networks(self._remembered_networks, ssid, ts, password)
        save_remembered_networks(self._remembered_networks)
        self.rememberedNetworksChanged.emit()

    @pyqtSlot(str)
    def remove_remembered_network(self, ssid):
        """Remove a network from remembered networks"""
        self._remembered_networks = [n for n in self._remembered_networks if n['ssid'] != ssid]
        save_remembered_networks(self._remembered_networks)
        
        # On Linux, also attempt to remove the NetworkManager connection profile
        if platform.system() == 'Linux':
            logger.info(f"Removing NetworkManager profile for forgotten network: {ssid}")
            try:
                # We do this in a background thread to avoid any potential UI delay
                threading.Thread(target=lambda: remove_nm_connection(ssid), daemon=True).start()
            except Exception as e:
                logger.debug(f"Failed to start NM profile removal thread: {e}")
                
        self.rememberedNetworksChanged.emit()

    def reload_web_content(self):
        """Signal QML to reload all web-based content (globe, charts, etc.) when WiFi connects"""
        try:
            now = time.time()
            # Rate-limit emits to avoid repeated reloads during brief connect/disconnect flaps
            if (now - getattr(self, '_last_web_reload_emit', 0)) < getattr(self, '_min_reload_emit_interval_sec', 8.0):
                logger.info("Reload web content throttled (recent emit) — skipping")
                return
            self._last_web_reload_emit = now
            logger.info("Signaling QML to reload web content after WiFi connection…")
            self.reloadWebContent.emit()
            logger.info("Web content reload signal sent")
            
        except Exception as e:
            logger.error(f"Error signaling web content reload: {e}")

    def save_last_connected_network(self, ssid):
        """Save the last connected network to file"""
        try:
            ts = save_last_connected_network(ssid)
            # Update internal list and sort
            self._remembered_networks = sync_remembered_networks(self._remembered_networks, ssid, ts)
            save_remembered_networks(self._remembered_networks)
            self.rememberedNetworksChanged.emit()
        except Exception as e:
            logger.error(f"Error saving last connected network: {e}")

    def _try_nmcli_connection(self, ssid, password, wifi_device):
        """Try to connect using nmcli as fallback"""
        success, result = connect_to_wifi_nmcli(ssid, password, wifi_device)
        if success:
            logger.info(f"Successfully connected to {ssid} using nmcli: {result}")
            self.save_last_connected_network(ssid)
            return True
        else:
            logger.warning(f"nmcli connection failed for {ssid}: {result}")
            return False

    def startDataLoader(self):
        """Start the data loading thread after WiFi check completes"""
        profiler.mark("Backend: startDataLoader")
        logger.info("BOOT: startDataLoader called (legacy path)")
        self.setLoadingStatus("Checking network connectivity…")
        # Legacy path kept for compatibility; avoid time-based gating. We'll kick off background
        # connectivity check and, if online, start immediate data loading. No splash timers.

        def _initial_checks_worker():
            # First, check actual WiFi status to update the UI and inform diagnostic checks
            try:
                connected, ssid = check_wifi_status()
                self.wifiCheckReady.emit(connected, ssid)
            except Exception as e:
                logger.error(f"BOOT: Async WiFi check failed: {e}")
                connected = self._wifi_connected

            src_dir = os.path.dirname(__file__)
            # Run bootstrap diagnostics WITHOUT blocking for update check to speed up data loading
            res = perform_bootstrap_diagnostics(src_dir, connected, skip_update_check=True)
            # Emit results; connected slot will run on the main thread
            try:
                self.initialChecksReady.emit(*res)
            except Exception as e:
                logger.error(f"BOOT: Failed to emit initialChecksReady: {e}")

            # NOW, perform update check in the background if we have connectivity,
            # so it doesn't block the DataLoader from starting.
            if res[0]: # connectivity_result
                try:
                    logger.info("BOOT: Starting background update check...")
                    current_info = res[2]
                    current_hash = current_info.get('hash', '')
                    has_update, latest_info = check_github_for_updates(current_hash, branch=self._target_branch)
                    self.initialUpdateCheckReady.emit(has_update, latest_info or {})
                except Exception as e:
                    logger.debug(f"BOOT: Background update check failed: {e}")

        threading.Thread(target=_initial_checks_worker, daemon=True).start()
        # Return immediately; UI remains responsive while checks run. No guard timers.

    @pyqtSlot(bool, bool, dict, dict)
    def _apply_initial_checks_results(self, connectivity_result, update_available, current_info, latest_info):
        """Apply initial check results on the main (Qt) thread."""
        profiler.mark("Backend: _apply_initial_checks_results Start")
        try:
            # Note: update_available and latest_info might be defaults if skip_update_check was used
            self.updateAvailable = update_available
            self._current_version_info = current_info
            self._latest_version_info = latest_info

            if connectivity_result:
                # If we have connectivity, stop the timeout timer as we're now definitely loading real data
                try:
                    if self._loading_timeout_timer.isActive():
                        self._loading_timeout_timer.stop()
                        logger.info("BOOT: Connectivity confirmed, stopped loading timeout timer")
                except Exception:
                    pass
                self._online_load_in_progress = True
                # Clear deferred flag if we have connectivity
                logger.info("BOOT: Network connectivity available - clearing deferred flag")
                self._data_loading_deferred = False
                self.setLoadingStatus("Loading SpaceX launch data...")
            else:
                logger.warning("BOOT: No network connectivity detected - staying with seed/runtime cache; will wait for firstOnline signal")
                # We no longer return here. Proceed to start DataLoader so cached data is processed.
                # self._setup_timers()
                # return

            if self.loader is None:
                logger.info("BOOT: Creating new DataLoader...")
                self.loader = DataLoader(self._tz, self._location)
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
            profiler.mark("Backend: _apply_initial_checks_results End")
        except Exception as e:
            logger.error(f"BOOT: Failed to apply initial checks results on main thread: {e}")
            profiler.mark("Backend: _apply_initial_checks_results Error")

    @pyqtSlot(bool, dict)
    def _apply_initial_update_result(self, update_available, latest_info):
        """Apply the result of the background boot-time update check."""
        try:
            # Crucially, always set latest_info if available to ensure branch-correct messages
            if latest_info:
                self._latest_version_info = latest_info
            self.updateAvailable = update_available
            self.versionInfoChanged.emit() # Ensure UI sees the new info
            logger.info(f"BOOT: Background update check finished (update_available={update_available})")
        except Exception as e:
            logger.error(f"BOOT: Failed to apply background update result: {e}")

    @pyqtSlot()
    def _on_initial_checks_guard_timeout(self):
        """Deprecated: time-based guard disabled (signal-based startup)."""
        logger.info("BOOT: _on_initial_checks_guard_timeout called but guard is disabled; no action")

    def _setup_timers(self):
        """Set up all the periodic timers"""
        profiler.mark("Backend: _setup_timers Start")
        if self._timers_initialized:
            logger.debug("Timers already initialized; skipping")
            profiler.mark("Backend: _setup_timers Skip")
            return
        self._timers_initialized = True
        logger.info("Setting up timers...")
        # Timers
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(300000)

        self.launch_timer = QTimer(self)
        self.launch_timer.timeout.connect(self.update_launches_periodic)
        self.launch_timer.start(CACHE_REFRESH_INTERVAL_UPCOMING * 1000)

        # WiFi timer for status updates - check every 60 seconds
        self.wifi_timer = QTimer(self)
        self.wifi_timer.timeout.connect(self.update_wifi_status)
        self.wifi_timer.start(60000)

        # Update check timer - check every 6 hours (21600000 ms)
        self.update_check_timer = QTimer(self)
        self.update_check_timer.timeout.connect(self.check_for_updates_periodic)
        self.update_check_timer.start(21600000)  # 6 hours

        # Near-real-time update for next launch - check every 2 minutes (v2.3.0 detailed)
        self.next_launch_timer = QTimer(self)
        self.next_launch_timer.timeout.connect(self.update_next_launch_periodic)
        self.next_launch_timer.start(120000)  # 2 minutes

        # Countdown timer - 1 second for precision
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

        profiler.mark("Backend: _setup_timers End")

    @pyqtSlot()
    def check_for_updates_periodic(self):
        """Periodic update check in background"""
        self.checkForUpdatesNow()

    @pyqtProperty(int)
    def httpPort(self):
        return funcs.HTTP_SERVER_PORT

    @pyqtProperty(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if self._mode != value:
            self._mode = value
            self.modeChanged.emit()
            self._emit_tray_visibility_changed()
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
            self._clear_launch_caches()
            # Also emit launchesChanged to refresh the chart
            self.launchesChanged.emit()
            self._emit_tray_visibility_changed()

    @pyqtProperty(str, notify=chartTypeChanged)
    def chartType(self):
        return self._chart_type

    @chartType.setter
    def chartType(self, value):
        if self._chart_type != value:
            self._chart_type = value
            self.chartTypeChanged.emit()
            self._clear_launch_caches()
            # Also emit launchesChanged to refresh the chart
            self.launchesChanged.emit()
            self._emit_tray_visibility_changed()

    @pyqtProperty(str, notify=themeChanged)
    def theme(self):
        return self._theme

    @theme.setter
    def theme(self, value):
        if self._theme != value:
            self._theme = value
            save_theme_settings(value)
            self.themeChanged.emit()

    @pyqtProperty(str, notify=targetBranchChanged)
    def targetBranch(self):
        return self._target_branch

    @targetBranch.setter
    def targetBranch(self, value):
        if self._target_branch != value:
            self._target_branch = value
            save_branch_setting(value)
            self.targetBranchChanged.emit()
            
            # Reset update status and latest info when branch changes to ensure 
            # "Update Now" disappears while we re-check for the new branch.
            self.updateAvailable = False
            self._latest_version_info = None # Trigger fetch on next access
            self.versionInfoChanged.emit()
            
            # Re-check for updates when branch changes
            self.checkForUpdatesNow()

    def _emit_tray_visibility_changed(self):
        """Emit launchTrayVisibilityChanged only if the state has actually changed to reduce UI churn."""
        current = self.launchTrayVisible
        if current != self._last_tray_visible:
            self._last_tray_visible = current
            logger.debug(f"Backend: Tray visibility changed to {current}, emitting signal")
            self.launchTrayVisibilityChanged.emit()

    @pyqtProperty(bool, notify=launchTrayVisibilityChanged)
    def launchTrayVisible(self):
        if self._launch_tray_manual_override is not None:
            return self._launch_tray_manual_override
        return get_launch_tray_visibility_state(self._launch_data, self._mode)

    @pyqtProperty(bool, notify=launchTrayVisibilityChanged)
    def launchTrayManualMode(self):
        return self._launch_tray_manual_override is not None

    @pyqtSlot(bool)
    def setLaunchTrayManualMode(self, enabled):
        if enabled:
            self._launch_tray_manual_override = True
        else:
            self._launch_tray_manual_override = None
        self._emit_tray_visibility_changed()

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
            logger.info(f"BOOT: Loading status changed to: {status}")
            self.loadingStatusChanged.emit()

    # --- Update progress UI properties ---
    @pyqtProperty(bool, notify=updatingInProgressChanged)
    def updatingInProgress(self):
        return self._updating_in_progress

    @pyqtProperty(str, notify=updatingStatusChanged)
    def updatingStatus(self):
        return self._updating_status

    def _set_updating_in_progress(self, val: bool):
        if self._updating_in_progress != bool(val):
            self._updating_in_progress = bool(val)
            try:
                self.updatingInProgressChanged.emit()
            except Exception:
                pass

    def _set_updating_status(self, text: str):
        text = str(text) if text is not None else ""
        if self._updating_status != text:
            self._updating_status = text
            try:
                self.updatingStatusChanged.emit()
            except Exception:
                pass

    def _start_update_progress_ui(self):
        """Show an in-app updating overlay and begin polling the updater log for progress."""
        try:
            self._set_updating_status("Starting updater…")
            self._set_updating_in_progress(True)
            # Start (or restart) a timer to poll the log
            if self._update_log_timer is None:
                self._update_log_timer = QTimer(self)
                self._update_log_timer.timeout.connect(self._poll_update_log)
            # Poll quickly at first to catch early messages
            self._update_log_timer.start(750)
        except Exception as e:
            logger.warning(f"Failed to start update progress UI: {e}")

    def _poll_update_log(self):
        """Read the last lines from the update log and reflect them into the UI."""
        try:
            if not self._updating_in_progress:
                if self._update_log_timer and self._update_log_timer.isActive():
                    self._update_log_timer.stop()
                return
            
            tail = get_update_progress_summary(self._update_log_path)
            self._set_updating_status(tail)

            # If the script has reached the reboot step, keep showing status
            # The system will reboot shortly and the app will close.
        except Exception as e:
            logger.debug(f"Update log polling failed: {e}")
            # Keep previous status; try again later

    def _check_http_server_ready(self):
        """Check if the local HTTP server is ready and update videoUrl."""
        if funcs.HTTP_SERVER_READY.is_set():
            self._video_url = f"http://localhost:{funcs.HTTP_SERVER_PORT}/youtube_embed.html"
            logger.info(f"BOOT: HTTP server ready on port {funcs.HTTP_SERVER_PORT}, videoUrl set to {self._video_url}")
            self.videoUrlChanged.emit()
            if self._http_ready_timer:
                self._http_ready_timer.stop()
                self._http_ready_timer = None

    @pyqtProperty(str, notify=videoUrlChanged)
    def videoUrl(self):
        return self._video_url

    @pyqtProperty(str, notify=selectedLaunchChanged)
    def selectedLaunch(self):
        return self._selected_launch_mission

    @pyqtProperty(int, notify=widthChanged)
    def width(self):
        return self._width

    @pyqtProperty(int, notify=heightChanged)
    def height(self):
        return self._height

    @pyqtProperty(bool, notify=widthChanged)
    def isHighResolution(self):
        return self._is_large_display

    @pyqtProperty(int, notify=brightnessChanged)
    def brightness(self):
        return self._brightness

    @pyqtProperty(int, notify=contrastChanged)
    def contrast(self):
        return self._contrast

    @pyqtProperty(str, notify=colorPresetChanged)
    def colorPreset(self):
        return self._color_preset

    @pyqtProperty(int, notify=videoGainRedChanged)
    def videoGainRed(self):
        return self._video_gain_red

    @pyqtProperty(int, notify=videoGainGreenChanged)
    def videoGainGreen(self):
        return self._video_gain_green

    @pyqtProperty(int, notify=videoGainBlueChanged)
    def videoGainBlue(self):
        return self._video_gain_blue

    @pyqtProperty(int, notify=sharpnessChanged)
    def sharpness(self):
        return self._sharpness

    @pyqtProperty(str, notify=inputSourceChanged)
    def inputSource(self):
        return self._input_source

    @pyqtProperty(str, notify=powerModeChanged)
    def powerMode(self):
        return self._power_mode

    @pyqtProperty(bool, notify=touchCalibrationExistsChanged)
    def touchCalibrationExists(self):
        return self._touch_calibration_exists

    @pyqtSlot()
    def calibrateTouchscreen(self):
        """Run the touch calibration script."""
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'calibrate_touch.sh')
        if not os.path.exists(script_path):
            logger.error(f"Calibration script not found at {script_path}")
            return

        def _worker():
            try:
                self.calibrationStarted.emit()
                if platform.system() == 'Linux':
                    subprocess.run(['chmod', '+x', script_path], check=True)
                    # Ensure we pass the current environment to the script, especially DISPLAY and XAUTHORITY
                    env = os.environ.copy()
                    if 'DISPLAY' not in env:
                        env['DISPLAY'] = ':0'
                    
                    logger.info(f"Running calibration script: {script_path}")
                    # We use a longer timeout or no timeout as calibration takes time
                    result = subprocess.run([script_path], capture_output=True, text=True, env=env)
                    
                    if result.returncode == 0:
                        logger.info("Calibration script finished successfully")
                        if result.stdout:
                            logger.info(f"Script STDOUT: {result.stdout}")
                    else:
                        logger.error(f"Calibration script failed with return code {result.returncode}")
                        if result.stdout:
                            logger.error(f"STDOUT: {result.stdout}")
                        if result.stderr:
                            logger.error(f"STDERR: {result.stderr}")
                else:
                    logger.info("Simulation: Running touch calibration")
                    time.sleep(5)
                
                # Update state
                self._touch_calibration_exists = funcs.check_touch_calibration_exists()
                self.touchCalibrationExistsChanged.emit()
                self.calibrationFinished.emit()
            except Exception as e:
                logger.error(f"Error running calibration: {e}")
                self.calibrationFinished.emit()

        threading.Thread(target=_worker, daemon=True).start()

    @pyqtSlot()
    def removeTouchCalibration(self):
        """Remove existing touch calibration."""
        success, msg = funcs.remove_touch_calibration()
        logger.info(msg)
        if success:
            self._touch_calibration_exists = False
            self.touchCalibrationExistsChanged.emit()

    @pyqtSlot(float)
    def setBrightness(self, value):
        """Update brightness with debouncing and serial hardware execution."""
        int_val = int(round(value))
        self._target_brightness = int_val
        if self._brightness != int_val:
            self._brightness = int_val
            logger.debug(f"Backend: Brightness UI set to {int_val}%")
            self.brightnessChanged.emit()
        self._brightness_timer.start(300)

    @pyqtSlot(float)
    def setContrast(self, value):
        int_val = int(round(value))
        self._target_contrast = int_val
        if self._contrast != int_val:
            self._contrast = int_val
            self.contrastChanged.emit()
        self._display_settings_timer.start(300)

    @pyqtSlot(str)
    def setColorPreset(self, value):
        if self._color_preset != value:
            self._color_preset = value
            self.colorPresetChanged.emit()
            self._set_setting_on_hardware("14", value)

    @pyqtSlot(float)
    def setVideoGainRed(self, value):
        int_val = int(round(value))
        self._target_video_gain_red = int_val
        if self._video_gain_red != int_val:
            self._video_gain_red = int_val
            self.videoGainRedChanged.emit()
        self._display_settings_timer.start(300)

    @pyqtSlot(float)
    def setVideoGainGreen(self, value):
        int_val = int(round(value))
        self._target_video_gain_green = int_val
        if self._video_gain_green != int_val:
            self._video_gain_green = int_val
            self.videoGainGreenChanged.emit()
        self._display_settings_timer.start(300)

    @pyqtSlot(float)
    def setVideoGainBlue(self, value):
        int_val = int(round(value))
        self._target_video_gain_blue = int_val
        if self._video_gain_blue != int_val:
            self._video_gain_blue = int_val
            self.videoGainBlueChanged.emit()
        self._display_settings_timer.start(300)

    @pyqtSlot(float)
    def setSharpness(self, value):
        int_val = int(round(value))
        self._target_sharpness = int_val
        if self._sharpness != int_val:
            self._sharpness = int_val
            self.sharpnessChanged.emit()
        self._display_settings_timer.start(300)

    @pyqtSlot(str)
    def setInputSource(self, value):
        if self._input_source != value:
            self._input_source = value
            self.inputSourceChanged.emit()
            self._set_setting_on_hardware("60", value)

    @pyqtSlot(str)
    def setPowerMode(self, value):
        if self._power_mode != value:
            self._power_mode = value
            self.powerModeChanged.emit()
            self._set_setting_on_hardware("D6", value)

    def _apply_brightness(self):
        """Triggered by debounce timer to ensure the latest target is set on hardware."""
        logger.debug(f"Backend: Debounce timer fired, target: {self._target_brightness}%")
        self.set_brightness_on_hardware(self._target_brightness)

    def _apply_display_settings(self):
        """Debounced applicator for multi-value slider settings (Contrast, RGB, Sharpness)."""
        if IS_WINDOWS or not self._is_large_display:
            return

        def _worker():
            with self._brightness_lock:
                targets = [
                    ("12", self._target_contrast, "_last_applied_contrast"),
                    ("16", self._target_video_gain_red, "_last_applied_video_gain_red"),
                    ("18", self._target_video_gain_green, "_last_applied_video_gain_green"),
                    ("1A", self._target_video_gain_blue, "_last_applied_video_gain_blue"),
                    ("87", self._target_sharpness, "_last_applied_sharpness"),
                ]
                
                for vcp, target_val, last_attr in targets:
                    last_val = getattr(self, last_attr)
                    if target_val != last_val:
                        # Scale 0-100 to 0-31 for this monitor's quirks
                        hw_val = int(round(target_val * 31 / 100))
                        cmd = f"/usr/bin/ddcutil setvcp {vcp} {hw_val} --bus=13 --noverify --mccs 2.2"
                        try:
                            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                            if result.returncode == 0:
                                setattr(self, last_attr, target_val)
                                logger.info(f"Backend: Set VCP {vcp} to {hw_val} (UI: {target_val})")
                            else:
                                logger.error(f"Backend: ddcutil VCP {vcp} failed: {result.stderr.strip()}")
                        except Exception as e:
                            logger.error(f"Backend: Exception setting VCP {vcp}: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _set_setting_on_hardware(self, vcp, value):
        """Direct applicator for discrete settings (non-debounced)."""
        if IS_WINDOWS or not self._is_large_display:
            return
        
        def _worker():
            with self._brightness_lock:
                cmd = f"/usr/bin/ddcutil setvcp {vcp} {value} --bus=13 --noverify --mccs 2.2"
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info(f"Backend: Successfully set VCP {vcp} to {value}")
                    else:
                        logger.error(f"Backend: ddcutil setvcp {vcp} failed: {result.stderr.strip()}")
                except Exception as e:
                    logger.error(f"Backend: Exception setting VCP {vcp}: {e}")
        
        threading.Thread(target=_worker, daemon=True).start()

    def set_brightness_on_hardware(self, value):
        if IS_WINDOWS:
            logger.info(f"Backend: Simulation: Setting brightness to {value}%")
            return

        def _worker():
            # Use a lock to ensure only one ddcutil process runs at a time
            with self._brightness_lock:
                to_set = self._target_brightness
                
                # Don't repeat the same value if we just set it successfully
                if to_set == self._last_applied_brightness:
                    logger.debug(f"Backend: Skipping redundant hardware set for {to_set}%")
                    return

                try:
                    if self._is_large_display:
                        # DFR1125 4K monitor on bus 13 (as verified)
                        # Root cause identified: Monitor VCP feature 10 actually uses a 0-31 scale
                        # but reports 0-100. Values above 31 wrap around (32=0, 33=1, etc.).
                        # We must scale our 0-100% slider value to 0-31 for the hardware.
                        hw_value = int(round(to_set * 31 / 100))
                        
                        # Added --noverify to speed up command execution
                        # Added --mccs 2.2 to avoid auto-detection overhead
                        cmd = f"/usr/bin/ddcutil setvcp 10 {hw_value} --bus=13 --noverify --mccs 2.2"
                        logger.debug(f"Backend: Executing hardware command: {cmd} (UI value: {to_set}%)")
                        
                        # Use a reasonable timeout
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                        
                        if result.returncode == 0:
                            self._last_applied_brightness = to_set
                            logger.info(f"Backend: Successfully set DFR1125 hardware brightness to {hw_value} (UI: {to_set}%)")
                        else:
                            logger.error(f"Backend: ddcutil failed with code {result.returncode}: {result.stderr.strip()}")
                    else:
                        # Waveshare display
                        backlight_path = "/sys/class/backlight/rpi_backlight/brightness"
                        if os.path.exists(backlight_path):
                            hw_val = int(to_set * 2.55)
                            subprocess.run(f"echo {hw_val} | sudo tee {backlight_path}", shell=True, check=True, capture_output=True)
                            self._last_applied_brightness = to_set
                            logger.info(f"Backend: Set Waveshare backlight to {hw_val}")
                except subprocess.TimeoutExpired:
                    logger.error("Backend: ddcutil command timed out")
                except Exception as e:
                    logger.error(f"Backend: Failed to set brightness to {to_set}: {e}")

        # Start the worker thread
        threading.Thread(target=_worker, daemon=True).start()

    def _initial_display_settings_fetch(self):
        if IS_WINDOWS or not self._is_large_display:
            return

        def _worker():
            try:
                with self._brightness_lock:
                    # Brightness (10)
                    cmd = "/usr/bin/ddcutil getvcp 10 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == "10":
                            try:
                                val = int(parts[3])
                                ui_val = min(100, max(0, int(round(val * 100 / 31))))
                                self._brightness = ui_val
                                self._last_applied_brightness = ui_val
                                self._target_brightness = ui_val
                                self.brightnessChanged.emit()
                                logger.info(f"Backend: Initial brightness fetched: {ui_val}%")
                            except ValueError: pass

                    # Contrast (12)
                    cmd = "/usr/bin/ddcutil getvcp 12 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == "12":
                            try:
                                val = int(parts[3])
                                ui_val = min(100, max(0, int(round(val * 100 / 31))))
                                self._contrast = ui_val
                                self._last_applied_contrast = ui_val
                                self._target_contrast = ui_val
                                self.contrastChanged.emit()
                                logger.info(f"Backend: Initial contrast fetched: {ui_val}%")
                            except ValueError: pass

                    # Color Preset (14)
                    cmd = "/usr/bin/ddcutil getvcp 14 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == "14":
                            val = parts[3].lower().replace("0x", "")
                            if len(val) == 1: val = "0" + val
                            self._color_preset = val
                            self.colorPresetChanged.emit()

                    # RGB Gains (16, 18, 1A)
                    for vcp, attr, sig in [("16", "video_gain_red", self.videoGainRedChanged), 
                                           ("18", "video_gain_green", self.videoGainGreenChanged), 
                                           ("1A", "video_gain_blue", self.videoGainBlueChanged)]:
                        cmd = f"/usr/bin/ddcutil getvcp {vcp} --bus=13 --brief"
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            parts = result.stdout.strip().split()
                            if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == vcp:
                                try:
                                    val = int(parts[3])
                                    ui_val = min(100, max(0, int(round(val * 100 / 31))))
                                    setattr(self, f"_{attr}", ui_val)
                                    setattr(self, f"_last_applied_{attr}", ui_val)
                                    setattr(self, f"_target_{attr}", ui_val)
                                    sig.emit()
                                except ValueError: pass

                    # Sharpness (87)
                    cmd = "/usr/bin/ddcutil getvcp 87 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == "87":
                            try:
                                val = int(parts[3])
                                ui_val = min(100, max(0, int(round(val * 100 / 31))))
                                self._sharpness = ui_val
                                self._last_applied_sharpness = ui_val
                                self._target_sharpness = ui_val
                                self.sharpnessChanged.emit()
                            except ValueError: pass

                    # Input Source (60)
                    cmd = "/usr/bin/ddcutil getvcp 60 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and parts[0] == "VCP" and parts[1] == "60":
                            val = parts[3].lower().replace("0x", "")
                            if len(val) == 1: val = "0" + val
                            self._input_source = val
                            self.inputSourceChanged.emit()

                    # Power Mode (D6)
                    cmd = "/usr/bin/ddcutil getvcp D6 --bus=13 --brief"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split()
                        if len(parts) >= 4 and (parts[0] == "VCP" and (parts[1] == "D6" or parts[1] == "d6")):
                            val = parts[3].lower().replace("0x", "")
                            if len(val) == 1: val = "0" + val
                            self._power_mode = val
                            self.powerModeChanged.emit()

            except Exception as e:
                logger.error(f"Backend: Failed to fetch initial display settings: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    @pyqtProperty(str, notify=locationChanged)
    def location(self):
        return self._location

    @location.setter
    def location(self, value):
        if self._location != value:
            self._location = value
            # Update timezone based on location
            if self._location in location_settings:
                tz_name = location_settings[self._location].get('timezone', 'UTC')
                try:
                    self._tz = pytz.timezone(tz_name)
                    logger.info(f"Backend: Timezone updated to {tz_name} for {self._location}")
                except Exception as e:
                    logger.error(f"Backend: Failed to set timezone {tz_name}: {e}")
                    self._tz = tzlocal()
            else:
                self._tz = tzlocal()

            logger.info(f"Backend: Location changed to {self._location}")
            # Explicitly update radar URL property on location change
            self._radar_base_url = radar_locations.get(self._location, radar_locations.get('Starbase', ''))
            
            # Reset calendar mapping cache so it recomputes with new timezone
            self._launches_by_date_cache = None
            
            self.radarBaseUrlChanged.emit()
            self.locationChanged.emit()
            self.weatherChanged.emit()
            self.launchesChanged.emit() # Notify that calendar mapping may have changed
            self.update_countdown() # Triggers countdownChanged and launchTrayVisibilityChanged
            self.update_event_model()

    @pyqtProperty(str, notify=locationChanged)
    def timezoneAbbrev(self):
        return datetime.now(self._tz).strftime('%Z')

    @pyqtProperty(EventModel, notify=eventModelChanged)
    def eventModel(self):
        return self._event_model

    @pyqtProperty(list, notify=wifiNetworksChanged)
    def wifiNetworks(self):
        return self._wifi_networks

    @pyqtProperty(bool, notify=wifiConnectedChanged)
    def wifiConnected(self):
        """Expose WiFi connected state to QML (used by status icon and labels)."""
        return self._wifi_connected

    @pyqtProperty(bool, notify=networkConnectedChanged)
    def networkConnected(self):
        return self._network_connected

    @pyqtProperty(bool, notify=wifiConnectingChanged)
    def wifiConnecting(self):
        return self._wifi_connecting

    @pyqtProperty(bool, notify=wifiScanInProgressChanged)
    def wifiScanInProgress(self):
        """Expose WiFi scan progress to QML for showing a spinner/disabled state."""
        return getattr(self, '_wifi_scan_in_progress', False)

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
        return get_countdown_string(
            self._launch_data,
            self._mode, 
            self.get_next_launch(),
            self._tz
        )

    @pyqtProperty(QVariant, notify=countdownChanged)
    def countdownBreakdown(self):
        return get_countdown_breakdown(
            self._launch_data,
            self._mode,
            self.get_next_launch(),
            self._tz
        )

    @pyqtProperty(QVariant, notify=launchesChanged)
    def allLaunchData(self):
        """Expose all launch data (combined previous and upcoming) for calendar view"""
        return self._launch_data

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchesByDate(self):
        """Returns a mapping of date strings to lists of launches for optimized calendar lookups"""
        # Internal caching to avoid repeated O(N) traversals
        if hasattr(self, '_launches_by_date_cache') and self._launches_by_date_cache is not None:
            return self._launches_by_date_cache
            
        # If not ready, return empty to avoid blocking UI thread and trigger background compute
        if not getattr(self, '_precomputing_calendar', False):
            logger.info("Backend: Calendar mapping requested but not ready; triggering background compute")
            threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()
            
        return {}

    @pyqtProperty(str, notify=liveLaunchUrlChanged)
    def liveLaunchUrl(self):
        return self._live_launch_url

    def _get_launch_trends_data(self):
        """Helper to get launch trends data with internal caching to avoid redundant calls."""
        current_year = datetime.now(pytz.UTC).year
        current_month = datetime.now(pytz.UTC).month
        
        # Cache key includes year, month, and view mode
        cache_key = f"{current_year}_{current_month}_{self._chart_view_mode}"
        
        # Use content-based signature instead of id() for better cache hits across reloads
        prev_launches = self._launch_data.get('previous', [])
        data_sig = f"{len(prev_launches)}"
        if prev_launches:
            # Use first and last item IDs/nets as a heuristic for data identity
            data_sig += f"_{prev_launches[0].get('id','0')}_{prev_launches[-1].get('id','0')}"
        
        if (self._launch_trends_cache.get('key') == cache_key and 
            self._launch_trends_cache.get('data_sig') == data_sig):
            return self._launch_trends_cache['data']
            
        # If not ready, return cached or empty and trigger background compute
        if not getattr(self, '_precomputing_trends', False):
             logger.info("Backend: Launch trends requested but not ready; triggering background compute")
             threading.Thread(target=self._precompute_launch_trends, args=(cache_key, data_sig), daemon=True).start()
        
        # Return whatever we have in cache (even if stale) or a default empty structure
        return self._launch_trends_cache.get('data', {'months': [], 'series': [], 'max_value': 0})

    def _precompute_launch_trends(self, cache_key, data_sig):
        """Pre-compute launch trends in the background."""
        if getattr(self, '_precomputing_trends', False):
            return
        self._precomputing_trends = True
        try:
            profiler.mark("Backend: _precompute_launch_trends Recomputing")
            prev_launches = self._launch_data.get('previous', [])
            current_year = datetime.now(pytz.UTC).year
            current_month = datetime.now(pytz.UTC).month

            from functions import get_launch_trends_series, get_max_value_from_series, RUNTIME_CACHE_FILE_CHART_TRENDS
            months, series = get_launch_trends_series(
                prev_launches,
                self._chart_view_mode,
                current_year,
                current_month
            )
            
            data = {
                'months': months,
                'series': series,
                'max_value': get_max_value_from_series(series)
            }
            
            self._launch_trends_cache = {
                'key': cache_key,
                'data_sig': data_sig,
                'data': data
            }
            
            # Persist to disk
            try:
                save_cache_to_file(RUNTIME_CACHE_FILE_CHART_TRENDS, self._launch_trends_cache, datetime.now(pytz.UTC))
                logger.info("Backend: Saved launch trends cache to disk (background)")
            except Exception as e:
                logger.debug(f"Failed to save launch trends cache: {e}")
                
            profiler.mark("Backend: _precompute_launch_trends End (Recomputed)")
            self.launchesChanged.emit() # Signal UI to refresh charts
        except Exception as e:
            logger.error(f"Failed to precompute launch trends: {e}")
        finally:
            self._precomputing_trends = False

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrends(self):
        data = self._get_launch_trends_data()
        return {'months': data['months'], 'series': data['series']}

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsMonths(self):
        return self._get_launch_trends_data()['months']

    @pyqtProperty(int, notify=launchesChanged)
    def launchTrendsMaxValue(self):
        return self._get_launch_trends_data()['max_value']

    def _generate_month_labels_for_days(self):
        """Generate month labels for daily data points"""
        return generate_month_labels_for_days(datetime.now(pytz.UTC).year)

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsSeries(self):
        return self._get_launch_trends_data()['series']

    @pyqtProperty(bool, notify=updateAvailableChanged)
    def updateAvailable(self):
        return self._update_available

    @updateAvailable.setter
    def updateAvailable(self, value):
        if self._update_available != value:
            self._update_available = value
            self.updateAvailableChanged.emit()

    @pyqtProperty('QVariantMap', notify=versionInfoChanged)
    def currentVersionInfo(self):
        if self._current_version_info is None or self._current_version_info.get('hash') == 'Unknown':
            self._current_version_info = self.get_current_version_info() or {}
        return self._current_version_info

    @pyqtProperty('QVariantMap', notify=versionInfoChanged)
    def latestVersionInfo(self):
        # We now trust _latest_version_info to be updated by periodic checks
        # or manual branch switches. If it's None, we do one initial fetch.
        if self._latest_version_info is None or self._latest_version_info.get('hash') == 'Unknown':
            self._latest_version_info = self.get_latest_version_info() or {}
        return self._latest_version_info

    @pyqtProperty(str, notify=versionInfoChanged)
    def lastUpdateCheckTime(self):
        if hasattr(self, '_last_update_check') and self._last_update_check:
            return self._last_update_check.strftime("%H:%M:%S")
        return "Never"

    @pyqtProperty(bool, notify=versionInfoChanged)
    def updateChecking(self):
        return self._update_checking

    # Globe auto-spin watchdog feature flag
    @pyqtProperty(bool, notify=globeAutospinGuardChanged)
    def globeAutospinGuard(self):
        return getattr(self, '_globe_autospin_guard', True)

    @globeAutospinGuard.setter
    def globeAutospinGuard(self, value: bool):
        try:
            value = bool(value)
        except Exception:
            value = True
        if getattr(self, '_globe_autospin_guard', True) != value:
            self._globe_autospin_guard = value
            try:
                self.globeAutospinGuardChanged.emit()
            except Exception:
                pass

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchDescriptions(self):
        # Ensure we're returning the latest enriched narratives
        return self._launch_descriptions

    @pyqtSlot(result=QVariant)
    def get_next_launch(self):
        return get_next_launch_info(self._launch_data['upcoming'], self._tz)

    @pyqtSlot(result=QVariant)
    def get_upcoming_launches(self):
        return get_upcoming_launches_list(self._launch_data['upcoming'], self._tz)

    @pyqtProperty(str, notify=radarBaseUrlChanged)
    def radarBaseUrl(self):
        return self._radar_base_url

    # Replaces getRadarUrl method
    # @pyqtSlot(str, result=str)
    # def getRadarUrl(self, location_name):...

    @pyqtSlot(result=QVariant)
    def get_launch_trajectory(self):
        """Get trajectory data for the next upcoming launch or currently selected launch"""
        # If we have a specific trajectory loaded, return that
        if hasattr(self, '_current_trajectory') and self._current_trajectory:
            logger.info("get_launch_trajectory: Returning current selected launch trajectory")
            return self._current_trajectory
        
        # Otherwise, get the default next launch trajectory
        upcoming = self.get_upcoming_launches()
        previous = self._launch_data.get('previous', [])
        
        # Set selected launch to the next upcoming launch if available
        if upcoming and len(upcoming) > 0:
            next_launch = upcoming[0]
            mission = next_launch.get('mission', '')
            if mission and self._selected_launch_mission != mission:
                self._selected_launch_mission = mission
                self.selectedLaunchChanged.emit()
                logger.info(f"get_launch_trajectory: Set selected launch to next upcoming: {mission}")
        
        # Use the centralized trajectory calculator in functions.py
        result = get_launch_trajectory_data(upcoming, previous)
        if result and 'booster_trajectory' in result:
            logger.info(f"get_launch_trajectory: Returning {len(result['trajectory'])} main points and {len(result['booster_trajectory'])} booster points")
        elif result:
            logger.info(f"get_launch_trajectory: Returning {len(result['trajectory'])} main points (no booster)")
        else:
            logger.info("get_launch_trajectory: Returning None")
        return result

    @pyqtSlot(str, str, str, str)
    def loadLaunchTrajectory(self, mission, pad, orbit, landing_type):
        """Load trajectory data for a specific launch"""
        try:
            logger.info(f"Loading trajectory for launch: {mission} from {pad}")
            
            # Set the selected launch for visual indication
            if self._selected_launch_mission != mission:
                self._selected_launch_mission = mission
                self.selectedLaunchChanged.emit()
            
            # Create a launch object for the trajectory calculator
            launch_data = {
                'mission': mission,
                'pad': pad,
                'orbit': orbit,
                'landing_type': landing_type
            }
            
            # Use the trajectory calculator with this specific launch
            result = get_launch_trajectory_data(launch_data)
            
            if result:
                # Store the trajectory data for the globe
                self._current_trajectory = result
                logger.info(f"Trajectory loaded for {mission}: {len(result.get('trajectory', []))} points")
                
                # Emit signal to update globe
                self.updateGlobeTrajectory.emit()
            else:
                logger.warning(f"Failed to generate trajectory for {mission}")
                
        except Exception as e:
            logger.error(f"Error loading trajectory for {mission}: {e}")

    @pyqtSlot(str, result=str)
    def getConvertedVideoUrl(self, video_url):
        """Helper to convert raw YouTube URLs to embed format without updating state."""
        if not video_url or not video_url.strip():
            return ""
        if 'youtube.com/watch?v=' in video_url:
            video_id = video_url.split('v=')[1].split('&')[0]
            return f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
        if 'youtube.com/live/' in video_url:
            video_id = video_url.split('youtube.com/live/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
        if 'youtu.be/' in video_url:
            video_id = video_url.split('youtu.be/')[1].split('?')[0]
            return f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
        return video_url

    @pyqtSlot(str)
    def loadLaunchVideo(self, video_url):
        """Load video for a specific launch, or clear if no video"""
        try:
            # Always update the video URL, even if empty (to clear the view)
            if video_url and video_url.strip():
                # Convert YouTube watch URLs to embed URLs
                if 'youtube.com/watch?v=' in video_url:
                    video_id = video_url.split('v=')[1].split('&')[0]
                    video_url = f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
                elif 'youtube.com/live/' in video_url:
                    video_id = video_url.split('youtube.com/live/')[1].split('?')[0]
                    video_url = f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
                elif 'youtu.be/' in video_url:
                    video_id = video_url.split('youtu.be/')[1].split('?')[0]
                    video_url = f"https://www.youtube.com/embed/{video_id}?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
                
                logger.info(f"Loading video: {video_url}")
            else:
                logger.info("Clearing video view (no video for this launch)")
                video_url = ""  # Ensure it's an empty string
            
            # Update the video URL which will be picked up by the YouTube WebEngine view
            if self._video_url != video_url:
                self._video_url = video_url
                self.videoUrlChanged.emit()
        except Exception as e:
            logger.error(f"Error loading video: {e}")

    @pyqtSlot(bool)
    def setBootMode(self, val):
        self._boot_mode = bool(val)
        if not self._boot_mode:
            profiler.mark("Disabling Boot Mode")
            logger.info("BOOT: Boot mode disabled, triggering chart re-evaluation")
            profiler.mark("Boot Mode Disabled (Charts Triggered)")

    def initialize_weather(self):
        return initialize_all_weather(location_settings)

    @pyqtSlot()
    def update_weather(self):
        """Update weather data in a separate thread to avoid blocking UI"""
        if hasattr(self, '_weather_updater_thread') and self._weather_updater_thread.isRunning():
            return  # Skip if already updating

        self._weather_updater = WeatherUpdater(self._location)
        self._weather_updater_thread = QThread()
        self._weather_updater.moveToThread(self._weather_updater_thread)
        self._weather_updater.finished.connect(self._on_weather_updated)
        self._weather_updater_thread.started.connect(self._weather_updater.run)
        self._weather_updater_thread.start()

    def update_launches_periodic(self):
        """Update launch data in a separate thread to avoid blocking UI"""
        if hasattr(self, '_launch_updater_thread') and self._launch_updater_thread.isRunning():
            return  # Skip if already updating

        self._launch_updater = LaunchUpdater(self._tz)
        self._launch_updater_thread = QThread()
        self._launch_updater.moveToThread(self._launch_updater_thread)
        self._launch_updater.finished.connect(self._on_launches_updated)
        self._launch_updater_thread.started.connect(self._launch_updater.run)
        self._launch_updater_thread.start()

    @pyqtSlot()
    def update_next_launch_periodic(self):
        """Update only the next upcoming launch data in near real-time (v2.3.0 detailed)"""
        if not self.networkConnected or self._mode != 'spacex':
            return

        # Skip if either updater is already running to avoid overlaps
        if (hasattr(self, '_launch_updater_thread') and self._launch_updater_thread.isRunning()) or \
           (hasattr(self, '_next_launch_updater_thread') and self._next_launch_updater_thread.isRunning()):
            return

        next_launch = self.get_next_launch()
        if not next_launch or not next_launch.get('id'):
            return

        logger.info(f"Backend: Near-real-time update for next launch {next_launch['id']}")
        self._next_launch_updater = NextLaunchUpdater(next_launch['id'])
        self._next_launch_updater_thread = QThread()
        self._next_launch_updater.moveToThread(self._next_launch_updater_thread)
        self._next_launch_updater.finished.connect(self._on_next_launch_updated)
        self._next_launch_updater_thread.started.connect(self._next_launch_updater.run)
        
        # Cleanup
        self._next_launch_updater.finished.connect(self._next_launch_updater_thread.quit)
        self._next_launch_updater.finished.connect(self._next_launch_updater_thread.deleteLater)
        self._next_launch_updater_thread.finished.connect(self._next_launch_updater_thread.deleteLater)
        
        self._next_launch_updater_thread.start()

    @pyqtSlot(dict)
    def _on_next_launch_updated(self, detailed_data):
        """Handle the result of a single-launch detailed fetch."""
        if not detailed_data or not self._launch_data:
            return

        upcoming = self._launch_data.get('upcoming', [])
        if not upcoming:
            return

        # Find the launch by ID in the upcoming list
        launch_index = -1
        for i, l in enumerate(upcoming):
            if l.get('id') == detailed_data.get('id'):
                launch_index = i
                break
        
        if launch_index == -1:
            return

        # Parse detailed data and update the item in the list
        parsed_data = funcs.parse_launch_data(detailed_data, is_detailed=True)
        
        # Only update and notify if something changed (like status)
        if upcoming[launch_index] != parsed_data:
            logger.info(f"Backend: Launch {parsed_data.get('id')} status/data changed! Status: {parsed_data.get('status')}")
            upcoming[launch_index] = parsed_data
            
            # Persist the update to disk cache so it's available after restart
            try:
                save_launch_cache('upcoming', upcoming)
                logger.info("Backend: Persisted next launch update to disk cache")
            except Exception as e:
                logger.warning(f"Backend: Failed to persist next launch update to cache: {e}")

            self._update_live_launch_url()
            self.launchesChanged.emit()
            self._emit_tray_visibility_changed()
            # Update the model to refresh UI list/pill
            if hasattr(self, '_event_model'):
                self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
                self._event_model.update_data()
            else:
                self.update_event_model()

    def update_time(self):
        self.timeChanged.emit()

    def _update_live_launch_url(self):
        self._last_live_url_update = time.time()
        new_live_url = get_closest_x_video_url(self._launch_data)
        if new_live_url != getattr(self, '_live_launch_url', ''):
            self._live_launch_url = new_live_url
            self.liveLaunchUrlChanged.emit()

    @pyqtSlot()
    def update_countdown(self):
        # Update countdown every second and re-evaluate tray visibility
        now = time.time()
        current_tray_visible = self.launchTrayVisible
        
        # Update URL if:
        # 1. It's been more than 60 seconds since last update
        # 2. The tray just became visible (opened)
        if (now - self._last_live_url_update >= 60) or (current_tray_visible and not self._last_tray_visible):
            self._update_live_launch_url()

        self.countdownChanged.emit()
        self._emit_tray_visibility_changed()

    def update_event_model(self):
        self._event_model = EventModel(self._launch_data if self._mode == 'spacex' else self._f1_data['schedule'], self._mode, self._event_type, self._tz)
        self.timeChanged.emit()  # Ensure time updates when timezone changes
        self.eventModelChanged.emit()
        # Timezone change affects calendar mapping, trigger recompute
        self._clear_launch_caches()
        threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()

    @pyqtSlot(dict, dict, list, dict)
    def on_data_loaded(self, launch_data, weather_data, narratives, calendar_mapping=None):
        profiler.mark("Backend: on_data_loaded Start")
        logger.info("Backend: on_data_loaded called")
        self.setLoadingStatus("Data loaded successfully")
        logger.info(f"Backend: Received {len(launch_data.get('upcoming', []))} upcoming launches")
        self._launch_data = launch_data
        self._launch_descriptions = narratives
        self._update_live_launch_url()
        self._clear_launch_caches()
        
        # Apply pre-computed calendar mapping if provided, or trigger background recompute
        if calendar_mapping:
            self._launches_by_date_cache = calendar_mapping
            logger.info("Backend: Applied pre-computed calendar mapping from DataLoader")
        else:
            threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()
            
        # self._f1_data is now initialized in __init__ and not updated here as it's currently missing from loader
        self._weather_data = weather_data
        # Update the EventModel's data reference
        profiler.mark("Backend: Updating EventModel")
        self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
        self._event_model.update_data()
        profiler.mark("Backend: EventModel updated")
        
        # Exit loading state after data is loaded and processed
        self.setLoadingStatus("Application loaded...")
        self._isLoading = False
        profiler.mark("Backend: Emitting UI update signals Start")
        self.loadingFinished.emit()
        self.launchesChanged.emit()
        self._emit_tray_visibility_changed()
        self.weatherChanged.emit()
        self.eventModelChanged.emit()
        profiler.mark("Backend: Emitting UI update signals End")

        # Update trajectory now that data is loaded (debounced) and precompute in background
        profiler.mark("Backend: Scheduling trajectory recompute")
        self._emit_update_globe_trajectory_debounced()
        self._schedule_trajectory_recompute()
        profiler.mark("Backend: on_data_loaded End")
        profiler.log_summary()
        # REDUNDANT RELOAD REMOVED: Data loading should not force a full UI reload.
        # Specific updates like update_charts, update_f1_data etc. are handled below.
        # if self._first_online_emitted and not self._web_reloaded_after_online:
        #     try:
        #         self.reload_web_content()
        #         self._web_reloaded_after_online = True
        #         logger.info("Issued one-shot web content reload after first online data load")
        #     except Exception as _e:
        #         logger.debug(f"Failed to reload web content after first online: {_e}")

    def _on_loading_timeout(self):
        """Handle loading timeout when no network connectivity is available"""
        profiler.mark("Backend: _on_loading_timeout Start")
        if not self._isLoading or getattr(self, '_online_load_in_progress', False):
            profiler.mark("Backend: _on_loading_timeout Skip (Not Loading or Online Load Started)")
            return
        logger.info("BOOT: Loading timeout reached (deprecated) — offline path retained for compatibility")
        logger.info("BOOT: Loading cached launch data...")
        # Load cached data if available, otherwise use empty data
        self._launch_data = self._load_cached_launch_data()
        self._update_live_launch_url()
        self._clear_launch_caches()
        # Trigger background recompute for calendar mapping
        threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()
        logger.info("BOOT: Loading cached weather data...")
        self._weather_data = self._load_cached_weather_data()

        # Update the EventModel's data reference
        logger.info(f"BOOT: Updating EventModel data (mode: {self._mode})")
        profiler.mark("Backend: _on_loading_timeout Updating EventModel")
        self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data['schedule']
        self._event_model.update_data()

        # Exit loading state after offline data is loaded
        self.setLoadingStatus("Application loaded...")
        self._isLoading = False
        self.loadingFinished.emit()
        # Mirror the same UI update signals as online path so QML refreshes lists and trajectory
        try:
            self.launchesChanged.emit()
            self._emit_tray_visibility_changed()
            self.weatherChanged.emit()
            self.eventModelChanged.emit()
            # Update trajectory now that cached data is applied
            self._emit_update_globe_trajectory_debounced()
            self._schedule_trajectory_recompute()
        except Exception as _e:
            logger.debug(f"BOOT: Error emitting offline refresh signals: {_e}")
        logger.info("BOOT: Offline mode activated - app should now show cached data")
        profiler.mark("Backend: _on_loading_timeout End")

    def _seed_bootstrap(self):
        """Apply cached (runtime or git-seeded) data immediately and exit splash.
        This is signal-based and avoids any time-based waits."""
        profiler.mark("Backend: _seed_bootstrap Start")
        try:
            self.setLoadingStatus("Loading cached SpaceX data…")
            
            # Optimization: Use already loaded data if available, avoid redundant I/O
            if not self._launch_data.get('previous') and not self._launch_data.get('upcoming'):
                profiler.mark("Backend: _seed_bootstrap Loading Cache")
                # Load launches from runtime cache, falling back to seed
                prev_cache = load_launch_cache('previous')
                up_cache = load_launch_cache('upcoming')
                self._launch_data = {
                    'previous': (prev_cache.get('data') if prev_cache else []) or [],
                    'upcoming': (up_cache.get('data') if up_cache else []) or []
                }
            
            self._update_live_launch_url()
            
            # Seed the calendar cache if it's still None after __init__
            reloaded = 'prev_cache' in locals() or 'up_cache' in locals()
            if reloaded:
                self._clear_launch_caches()
            
            if (reloaded or getattr(self, '_launches_by_date_cache', None) is None) and self._launch_data:
                # Trigger background recompute to avoid UI blocking
                threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()
                logger.info("Backend: Triggered background calendar cache seeding during bootstrap")
                
            # Update EventModel immediately
            profiler.mark("Backend: _seed_bootstrap Updating EventModel")
            self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data.get('schedule', [])
            self._event_model.update_data()

            profiler.mark("Backend: _seed_bootstrap Emitting Signals Start")
            try:
                profiler.mark("Backend: _seed_bootstrap emitting launchCacheReady")
                self.launchCacheReady.emit()
            except Exception:
                pass
            
            profiler.mark("Backend: _seed_bootstrap emitting launchesChanged Start")
            self.launchesChanged.emit()
            profiler.mark("Backend: _seed_bootstrap emitting launchesChanged End")
            
            profiler.mark("Backend: _seed_bootstrap emitting launchTrayVisibilityChanged Start")
            self._emit_tray_visibility_changed()
            profiler.mark("Backend: _seed_bootstrap emitting launchTrayVisibilityChanged End")
            
            profiler.mark("Backend: _seed_bootstrap emitting eventModelChanged Start")
            self.eventModelChanged.emit()
            profiler.mark("Backend: _seed_bootstrap emitting eventModelChanged End")
            
            profiler.mark("Backend: _seed_bootstrap Emitting Signals End")
            # Update trajectory now that we have at least cached data
            self._emit_update_globe_trajectory_debounced()
            self._schedule_trajectory_recompute()
            
            # NOTE: Do NOT exit splash here. Wait for network or timeout.
            # self.setLoadingStatus("Application loaded…")
            # self._isLoading = False
            # self.loadingFinished.emit()
            logger.info("BOOT: Seed/runtime cache applied; waiting for network or timeout to dismiss splash")
            profiler.mark("Backend: _seed_bootstrap End")
        except Exception as e:
            logger.error(f"Seed bootstrap failed: {e}")
            profiler.mark("Backend: _seed_bootstrap Error")

    def _start_data_loading_online(self):
        """Start DataLoader immediately (no guard timers), used when firstOnline fires."""
        try:
            # Phase 3 Guard: prevent multiple loader threads
            if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
                logger.info("BOOT: DataLoader thread already running; skipping redundant start")
                return

            self.setLoadingStatus("Loading online data…")
            if self.loader is None:
                logger.info("BOOT: Creating new DataLoader for online load…")
                # DataLoader is defined in this file
                self.loader = DataLoader(self._tz, self._location)
                self.thread = QThread()
                self.loader.moveToThread(self.thread)
                self.loader.finished.connect(self.on_data_loaded)
                self.loader.statusUpdate.connect(self.setLoadingStatus)
                self.thread.started.connect(self.loader.run)
                self.thread.start()
            else:
                logger.info("BOOT: Restarting existing DataLoader thread…")
                if not self.thread.isRunning():
                    self.thread.start()
            # Ensure periodic timers are running
            self._setup_timers()
        except Exception as e:
            logger.error(f"Failed to start online data loading: {e}")

    # --- Globe trajectory helpers (async precompute + debounced emits) ---
    def _emit_update_globe_signal(self):
        try:
            # Don't touch the globe if we are in the middle of a connection attempt
            if getattr(self, '_wifi_connecting', False):
                return
            self.updateGlobeTrajectory.emit()
        except Exception as _e:
            logger.debug(f"Failed to emit updateGlobeTrajectory: {_e}")

    def _emit_update_globe_trajectory_debounced(self):
        try:
            if self._trajectory_emit_timer.isActive():
                self._trajectory_emit_timer.stop()
        except Exception:
            pass
        try:
            # Connect once
            if not hasattr(self, '_traj_emit_connected') or not self._traj_emit_connected:
                self._trajectory_emit_timer.timeout.connect(self._emit_update_globe_signal)
                self._traj_emit_connected = True
        except Exception as _e:
            logger.debug(f"Failed to connect trajectory emit timer: {_e}")
        try:
            self._trajectory_emit_timer.start()
        except Exception as _e:
            logger.debug(f"Failed to start trajectory emit timer: {_e}")

    def _schedule_trajectory_recompute(self, delay_ms: int = 250):
        try:
            self._trajectory_recompute_timer.stop()
        except Exception:
            pass
        try:
            self._trajectory_recompute_timer.setInterval(max(0, int(delay_ms)))
        except Exception:
            pass
        try:
            self._trajectory_recompute_timer.start()
            logger.info("Scheduled trajectory recompute (debounced)")
        except Exception as _e:
            logger.debug(f"Failed to start trajectory recompute timer: {_e}")

    def _compute_trajectory_async(self):
        if getattr(self, '_trajectory_compute_inflight', False):
            logger.debug("Trajectory compute already in flight; skipping")
            return
        self._trajectory_compute_inflight = True

        def _worker():
            try:
                logger.info("Computing launch trajectory in background…")
                # This will also populate the on-disk trajectory cache if needed
                _ = self.get_launch_trajectory()
            except Exception as e:
                logger.warning(f"Background trajectory compute failed: {e}")
            finally:
                def _done():
                    self._trajectory_compute_inflight = False
                    self._emit_update_globe_trajectory_debounced()
                try:
                    QTimer.singleShot(0, _done)
                except Exception:
                    # As a fallback, emit directly (may still work on main thread)
                    _done()

        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as _e:
            logger.debug(f"Failed to start trajectory worker thread: {_e}")

    def _load_cached_launch_data(self):
        """Load cached launch data for offline mode"""
        try:
            previous_cache = load_launch_cache('previous')
            upcoming_cache = load_launch_cache('upcoming')
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

    def _load_cached_weather_data(self):
        """Load cached/default weather data for offline mode"""
        # Return default weather data for all locations
        weather_data = {}
        for location in location_settings.keys():
            weather_data[location] = {
                'temperature_c': (25 - 32) * 5/9,
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

    def _clear_launch_caches(self):
        """Clear all internal caches derived from launch data"""
        self._launch_trends_cache.clear()
        self._launches_by_date_cache = None

    def _precompute_calendar_mapping(self):
        """Pre-compute the calendar mapping in the background to avoid UI blocking."""
        if getattr(self, '_precomputing_calendar', False):
            return
        self._precomputing_calendar = True
        try:
            from functions import get_calendar_mapping, RUNTIME_CACHE_FILE_CALENDAR
            mapping = get_calendar_mapping(self._launch_data, self._tz)
            self._launches_by_date_cache = mapping
            
            # Persist to disk for faster subsequent app runs
            try:
                save_cache_to_file(RUNTIME_CACHE_FILE_CALENDAR, mapping, datetime.now(pytz.UTC))
                logger.info("Backend: Pre-computed and saved calendar cache to disk")
            except Exception as e:
                logger.debug(f"Failed to save calendar cache: {e}")
                
            try:
                self.launchesChanged.emit() # Signal that mapping is ready for QML
            except Exception:
                pass 
        except Exception as e:
            logger.error(f"Failed to pre-compute calendar mapping: {e}")
        finally:
            self._precomputing_calendar = False

    @pyqtSlot(dict, list, dict)
    def _on_launches_updated(self, launch_data, narratives, calendar_mapping=None):
        """Handle launch data update completion"""
        self._launch_data = launch_data
        self._launch_descriptions = narratives
        self._update_live_launch_url()
        self._clear_launch_caches()
        
        # Apply pre-computed calendar mapping if provided, or trigger background recompute
        if calendar_mapping:
            self._launches_by_date_cache = calendar_mapping
            logger.info("Backend: Applied pre-computed calendar mapping from LaunchUpdater")
        else:
            threading.Thread(target=self._precompute_calendar_mapping, daemon=True).start()
            
        self.launchesChanged.emit()
        self._emit_tray_visibility_changed()
        self.update_event_model()
        # Update globe trajectory in case current/next launch changed (e.g., after Success)
        self._emit_update_globe_trajectory_debounced()
        self._schedule_trajectory_recompute()
        # Clean up thread
        if hasattr(self, '_launch_updater_thread'):
            self._launch_updater_thread.quit()
            self._launch_updater_thread.wait()

        # Auto-reconnect to last connected network if not currently connected
        self._auto_reconnect_to_last_network()

    @pyqtProperty(QObject, notify=weatherForecastModelChanged)
    def weatherForecastModel(self):
        return self._weather_forecast_model

    @pyqtSlot(dict)
    def _on_weather_updated(self, weather_data):
        """Handle weather data update completion"""
        if not weather_data:
            logger.warning("Backend: Received empty weather data in _on_weather_updated")
            return

        self._weather_data = weather_data
        
        # Extract forecast for active location if available, else use dummy/simulated forecast
        active_weather = self._weather_data.get(self._location, {})
        if not active_weather:
            logger.warning(f"Backend: No weather data for current location '{self._location}'")
        
        # Prioritize processed forecast from API
        forecast = active_weather.get('forecast_processed', [])
        
        if not forecast:
            # Fallback to 'forecast' if 'forecast_processed' is missing for some reason
            forecast = active_weather.get('forecast', [])
            
            if not forecast or isinstance(forecast, dict):
                logger.info(f"Backend: Generating simulated forecast for {self._location}")
                # Generate simulated forecast if API doesn't provide it yet
                # Note: if forecast is a dict, it's the raw API response we haven't processed
                forecast = []
                days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                current_day_idx = datetime.now().weekday()
                base_temp = active_weather.get('temperature_f', 75)
                
                for i in range(1, 6):
                    day_name = days[(current_day_idx + i) % 7]
                    low = int(base_temp - 5 - i)
                    high = int(base_temp + 5 + i)
                    # Generate simple daily curve: low -> high -> lowish
                    # 6 points for the sparkline
                    temps = [low, int(low + (high-low)*0.3), high, int(high - (high-low)*0.2), int(high - (high-low)*0.5), low + 2]
                    
                    # Generate simple daily wind curve
                    base_wind = int(active_weather.get('wind_speed_kts', 10))
                    winds = [base_wind, base_wind + i, base_wind + i + 2, base_wind + i + 1, base_wind + i - 1, base_wind]
                    avg_wind = sum(winds) / len(winds)
                    sim_dir = (90 + i * 10) % 360

                    forecast.append({
                        'day': day_name,
                        'temp_low': f"{low}°",
                        'temp_high': f"{high}°",
                        'condition': 'Partly Cloudy',
                        'wind': f"{int(avg_wind)}kt {sim_dir}°",
                        'temps': temps,
                        'winds': winds
                    })
        
        logger.info(f"Backend: Updating weather forecast model with {len(forecast)} days")
        self._weather_forecast_model.update_data(forecast)
        self.weatherChanged.emit()
        self.weatherForecastModelChanged.emit()
        # Clean up thread
        if hasattr(self, '_weather_updater_thread'):
            self._weather_updater_thread.quit()
            self._weather_updater_thread.wait()

    def _safety_reset_wifi_connecting(self, ssid=None):
        """Reset the connecting state if it's been stuck for too long"""
        if getattr(self, '_wifi_connecting', False):
            logger.warning(f"WiFi connection cleanup: State was stuck 'connecting' for {ssid or 'unknown'}; resetting UI.")
            self._wifi_connecting = False
            self._wifi_connect_in_progress = False
            self._target_wifi_ssid = None # Also reset target SSID
            self.wifiConnectingChanged.emit()

    def _auto_reconnect_to_last_network(self, boot_time=False):
        """Auto-reconnect to the last connected network in background"""
        def _worker():
            try:
                # If connecting right now, skip
                if self._wifi_connecting:
                    logger.debug("WiFi is currently connecting, skipping auto-reconnection")
                    return

                # Determine current SSID
                current_ssid = self._current_wifi_ssid or ''
                # Determine preferred SSID by most recent remembered/last-connected
                preferred_ssid = None
                if self._remembered_networks:
                    preferred_ssid = self._remembered_networks[0].get('ssid')
                if (not preferred_ssid) and self._last_connected_network:
                    preferred_ssid = self._last_connected_network.get('ssid')
                if not preferred_ssid and not boot_time:
                    logger.debug("No last connected network; skipping auto-reconnect")
                    return

                if boot_time and not IS_WINDOWS:
                    # Boot path for Linux uses NM profiles more aggressively via dedicated helper
                    self._scan_and_reconnect_to_best_network()
                    return

                # Identify best candidate using shared logic
                nm_profiles = get_nmcli_profiles() if not IS_WINDOWS else []
                candidate = get_best_wifi_reconnection_candidate(
                    self._remembered_networks, 
                    self._wifi_networks,
                    nm_profiles
                )

                if not candidate:
                    if not self._wifi_networks:
                        # No scan results yet, trigger scan and retry
                        QTimer.singleShot(0, self.scanWifiNetworks)
                        QTimer.singleShot(2500, lambda: self._auto_reconnect_to_last_network(False))
                    return

                if candidate['type'] == 'direct':
                    logger.info(f"Auto-reconnecting to visible remembered network: {candidate['ssid']}")
                    QTimer.singleShot(1000, lambda: self._perform_auto_reconnection(candidate['ssid'], candidate['password']))
                elif candidate['type'] == 'nmcli':
                    logger.info(f"Bringing up NM profile for {candidate['ssid']} ({candidate['profile_name']})")
                    success, output = bring_up_nm_connection(candidate['profile_name'])
                    if success:
                        QTimer.singleShot(0, lambda s=candidate['ssid']: self.save_last_connected_network(s))
                        QTimer.singleShot(0, self.update_wifi_status)
                    else:
                        logger.warning(f"Failed to bring up NM profile: {output}")
            except Exception as e:
                logger.error(f"Error during auto-reconnection setup: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _scan_and_reconnect_to_best_network(self):
        """Try to auto-reconnect using NM profiles on Linux (intended for boot path)"""
        try:
            if platform.system() != 'Linux': return

            # Wait briefly for scan if in progress
            wait_start = time.time()
            while getattr(self, '_wifi_scan_in_progress', False) and (time.time() - wait_start) < 6.0:
                time.sleep(0.2)
            
            if not self._wifi_networks and not getattr(self, '_wifi_scan_in_progress', False):
                self.scanWifiNetworks()
                wait_start = time.time()
                while getattr(self, '_wifi_scan_in_progress', False) and (time.time() - wait_start) < 6.0:
                    time.sleep(0.2)

            nm_profiles = get_nmcli_profiles()
            candidate = get_best_wifi_reconnection_candidate(
                self._remembered_networks, 
                self._wifi_networks,
                nm_profiles
            )

            if candidate and candidate['type'] == 'nmcli':
                logger.info(f"BOOT: Bringing up NM profile for {candidate['ssid']} using profile '{candidate['profile_name']}'")
                success, output = bring_up_nm_connection(candidate['profile_name'])
                if success:
                    self.save_last_connected_network(candidate['ssid'])
                    self.update_wifi_status()
                    return
                else:
                    logger.warning(f"BOOT: NM profile activation failed: {output}")
            
            # Fallback to direct connect if NM failed or no nmcli candidate
            for cand in self._remembered_networks:
                if cand.get('ssid') and cand.get('password'):
                    logger.info(f"BOOT: Falling back to direct connect for '{cand['ssid']}'")
                    QTimer.singleShot(0, lambda s=cand['ssid'], p=cand['password']: self.connectToWifi(s, p))
                    return
        except Exception as e:
            logger.error(f"Error during boot-time scan/reconnect: {e}")

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
        """Scan for available WiFi networks without blocking the UI thread."""
        if getattr(self, '_wifi_scan_in_progress', False):
            return
        self._wifi_scan_in_progress = True
        try: self.wifiScanInProgressChanged.emit()
        except: pass

        def _worker():
            try:
                networks = perform_wifi_scan(get_wifi_interface())
            except Exception as e:
                logger.error(f"Error scanning WiFi networks: {e}")
                networks = []

            self.wifiScanResultsReady.emit(networks)

        threading.Thread(target=_worker, daemon=True).start()

    @pyqtSlot(list)
    def _apply_wifi_scan_results(self, networks):
        """Apply Wi‑Fi scan results on the UI thread and reset scanning state."""
        try:
            self._wifi_networks = filter_and_sort_wifi_networks(networks)
            logger.info(f"WiFi scan completed, found {len(self._wifi_networks)} networks")
            try:
                ssid_list = ", ".join([f"{n.get('ssid','')} ({n.get('signal','?')})" for n in self._wifi_networks if n.get('ssid')])
                if ssid_list:
                    logger.info(f"Available WiFi networks: {ssid_list}")
                else:
                    logger.info("Available WiFi networks: <none>")
            except Exception as _e:
                logger.debug(f"Failed to print SSID list: {_e}")
            self.wifiNetworksChanged.emit()
        except Exception as e:
            logger.error(f"Failed to apply WiFi scan results: {e}")
        finally:
            # Always clear scanning flag so UI doesn't get stuck
            self._wifi_scan_in_progress = False
            try:
                self.wifiScanInProgressChanged.emit()
            except Exception:
                pass

    @pyqtSlot(str, str)
    def connectToWifi(self, ssid, password):
        """Connect to a WiFi network without blocking the UI thread."""
        if getattr(self, '_wifi_connect_in_progress', False):
            return
        self._wifi_connect_in_progress = True
        self._wifi_connecting = True
        self._target_wifi_ssid = ssid # Set target SSID
        self.wifiConnectingChanged.emit()

        # Safety reset timer in case worker hangs
        QTimer.singleShot(60000, lambda: self._safety_reset_wifi_connecting(ssid))

        def _finish():
            try:
                self._wifi_connecting = False
                self.wifiConnectingChanged.emit()
                self.update_wifi_status()
            finally:
                self._wifi_connect_in_progress = False

        def _worker():
            try:
                wifi_interface = get_wifi_interface()
                success, error = connect_to_wifi_worker(ssid, password, wifi_interface)
                
                if success:
                    # Persist remembered network (needs main thread for property update)
                    QTimer.singleShot(0, lambda: self.add_remembered_network(ssid, password))
                    
                    # Save last connected network (io bound, safe in thread)
                    try:
                        self.save_last_connected_network(ssid)
                    except Exception as e:
                        logger.error(f"Failed to save last connected network: {e}")

                    # Call Linux-specific autoconnect manager (BLOCKING subprocess calls - run in thread)
                    if not IS_WINDOWS:
                        try:
                            manage_nm_autoconnect(ssid)
                        except Exception as e:
                            logger.error(f"Failed to manage NM autoconnect: {e}")
                
                # Signal completion on main thread
                QTimer.singleShot(0, _finish)
            except Exception as e:
                logger.error(f"WiFi connection worker error: {e}")
                QTimer.singleShot(0, _finish)

        threading.Thread(target=_worker, daemon=True).start()

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
        """Disconnect from current WiFi network (Threaded)"""
        def _worker():
            try:
                success, output = disconnect_from_wifi(get_wifi_interface())
                
                # Update UI on main thread
                def _update_ui():
                    if success:
                        logger.info(f"WiFi disconnected: {output}")
                        self._wifi_connected = False
                        self._current_wifi_ssid = ""
                        self.wifiConnectedChanged.emit()
                        self.update_wifi_status()
                    else:
                        logger.error(f"Failed to disconnect WiFi: {output}")
                        self._current_wifi_ssid = ""
                        self.wifiConnectedChanged.emit()
                
                QTimer.singleShot(0, _update_ui)
            except Exception as e:
                logger.error(f"Disconnect worker failed: {e}")
        
        threading.Thread(target=_worker, daemon=True).start()

    def _manage_networkmanager_autoconnect(self, current_ssid):
        """Manage NetworkManager autoconnect settings for the current network"""
        manage_nm_autoconnect(current_ssid)

    @pyqtSlot()
    def startWifiTimer(self):
        """WiFi timer now runs continuously - this method is kept for compatibility"""
        # Timer runs continuously now, no need to start/stop it
        logger.debug("WiFi timer is running continuously")

    @pyqtSlot()
    def stopWifiTimer(self):
        """WiFi timer now runs continuously - this method is kept for compatibility"""
        # Timer runs continuously now, no need to start/stop it
        logger.debug("WiFi timer is running continuously")

    def update_wifi_status(self):
        """Update WiFi connection status with enhanced fallback methods"""
        def _worker():
            try:
                connected, current_ssid = check_wifi_status()
                # Use signal for thread-safe main-thread execution
                self.wifiCheckReady.emit(connected, current_ssid)
            except Exception as e:
                logger.error(f"WiFi status check worker error: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    @pyqtSlot(bool, str) # Mark as slot for signal connection
    def _apply_wifi_status(self, connected, current_ssid):
        """Apply WiFi status results on the main thread"""
        try:
            # Update properties
            wifi_changed = (self._wifi_connected != connected) or (self._current_wifi_ssid != current_ssid)
            wifi_just_connected = not self._wifi_connected and connected
            
            self._wifi_connected = connected
            self._current_wifi_ssid = current_ssid

            # If the system reports we're connected to the TARGET network, clear UI "connecting" state
            # If no target set (legacy/manual), proceed as before.
            target_match = (not getattr(self, '_target_wifi_ssid', None)) or (current_ssid == getattr(self, '_target_wifi_ssid', None))
            
            if connected and target_match and (getattr(self, '_wifi_connecting', False) or getattr(self, '_wifi_connect_in_progress', False)):
                logger.info(f"Connected to target {current_ssid} - clearing connecting state")
                try:
                    self._wifi_connecting = False
                    self._wifi_connect_in_progress = False
                    self._target_wifi_ssid = None # Reset target
                    self.wifiConnectingChanged.emit()
                    self.wifiScanInProgressChanged.emit() # Ensure spinner stops
                except: pass
            
            if wifi_changed:
                logger.info(f"WiFi status updated - Connected: {connected}, SSID: {current_ssid}")
                self.wifiConnectedChanged.emit()

                if connected and current_ssid:
                    logger.info(f"Syncing connection metadata for '{current_ssid}'")
                    # Update last connected
                    self.save_last_connected_network(current_ssid)
                    
                    # Ensure it's in remembered networks
                    if not any(n.get('ssid') == current_ssid for n in (self._remembered_networks or [])):
                        self.add_remembered_network(current_ssid, None)
                    else:
                        # Even if remembered, emit change to ensure UI elements (like Remove button) sync up
                        try: self.rememberedNetworksChanged.emit()
                        except: pass

                if wifi_just_connected:
                    logger.info("WiFi connection detected - reloading web content")
                    self.reload_web_content()
                    self._web_reloaded_after_online = True

            if hasattr(self, '_data_loading_deferred') and self._data_loading_deferred:
                logger.info("WiFi connected - starting deferred data loading")
                self._data_loading_deferred = False
                if hasattr(self, '_loading_timeout_timer') and self._loading_timeout_timer.isActive():
                    self._loading_timeout_timer.stop()
                self._resume_data_loading()

            # Trigger network connectivity check if needed
            if connected:
                current_time = time.time()
                if not hasattr(self, '_last_network_check') or self._last_network_check is None or current_time - self._last_network_check > 30:
                    self._last_network_check = current_time
                    self._start_network_connectivity_check_async()
            elif getattr(self, '_network_connected', False):
                self._network_connected = False
                try: self.networkConnectedChanged.emit()
                except: pass

        except Exception as e:
            logger.error(f"Failed to apply WiFi status: {e}")


    def _resume_data_loading(self):
        """Resume or start data loading once connection is detected"""
        try:
            # Phase 3 Guard: prevent multiple loader threads
            if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
                logger.info("WiFi connected - DataLoader already running; skipping")
                return

            if self.loader is None:
                logger.info("WiFi connected - creating new DataLoader...")
                # DataLoader is defined in this file
                self.loader = DataLoader(self._tz, self._location)
                self.thread = QThread()
                self.loader.moveToThread(self.thread)
                self.loader.finished.connect(self.on_data_loaded)
                self.loader.statusUpdate.connect(self.setLoadingStatus)
                self.thread.started.connect(self.loader.run)
                self.thread.start()
            else:
                logger.info("WiFi connected - restart existing DataLoader if needed")
                if not self.thread.isRunning():
                    self.thread.start()
        except Exception as e:
            logger.error(f"Failed to resume data loading: {e}")
            self._wifi_connected = False
            self._current_wifi_ssid = ""
            self.wifiConnectedChanged.emit()

    def check_wifi_interface(self):
        """Check if WiFi interface is available and log status"""
        return check_wifi_interface()

    @pyqtSlot(result=str)
    def getWifiInterfaceInfo(self):
        """Get information about the WiFi interface for debugging"""
        return get_wifi_interface_info()

    @pyqtSlot(result=str)
    def getWifiDebugInfo(self):
        """Get comprehensive WiFi debugging information"""
        return get_wifi_debug_info()

    @pyqtSlot()
    def runUpdateScript(self):
        """Run the update and reboot script"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'update_and_reboot.sh')      
            logger.info(f"Running update script: {script_path}")

            # Proactively show the in-app progress UI
            self._set_updating_status("Starting updater…")
            self._set_updating_in_progress(True)

            success, result = start_update_script(script_path, branch=self._target_branch)
            
            if success:
                if result.get('pid'):
                    self._updater_pid = result['pid']
                    self._update_log_path = result['log_path']
                    logger.info(f"Update script started (pid={self._updater_pid}). Logs: {self._update_log_path}.")
                    self._start_update_progress_ui()
                else:
                    logger.info("Updater started. Showing generic update status…")
                    self._start_update_progress_ui()
            else:
                logger.error(f"Failed to start updater: {result}")
                self._set_updating_status(f"Failed to start updater: {result}")

            # As a safety net, if on Linux and the log file doesn't appear shortly, inform the user
            try:
                if platform.system() == 'Linux':
                    def _check_log_appeared():
                        path = self._update_log_path
                        if path and os.path.exists(path):
                            return
                        # Update status hinting at permissions if still missing
                        self._set_updating_status("Updater running… (log not yet available). If this persists, check script permissions and sudo rights.")
                    QTimer.singleShot(2000, _check_log_appeared)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error running update script: {e}")
            # Keep overlay visible and show error so the user can report/log
            try:
                self._set_updating_in_progress(True)
                self._set_updating_status(f"Failed to start updater: {e}")
            except Exception:
                pass

    @pyqtSlot()
    def cancelUpdate(self):
        """Attempt to cancel a running update: terminate detached updater and hide overlay."""
        try:
            if platform.system() == 'Linux' and self._updater_pid:
                self._set_updating_status("Canceling update…")
                try:
                    # Send SIGTERM to the process group created by start_new_session
                    os.killpg(self._updater_pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to update process group (pgid={self._updater_pid})")
                except Exception as e1:
                    logger.warning(f"Failed to SIGTERM updater group: {e1}")
                # As a safety, escalate to SIGKILL after a short delay
                def _force_kill():
                    try:
                        os.killpg(self._updater_pid, signal.SIGKILL)
                        logger.info(f"Sent SIGKILL to update process group (pgid={self._updater_pid})")
                    except Exception:
                        pass
                    self._finalize_cancel_ui()
                QTimer.singleShot(1500, _force_kill)
            else:
                # Non-Linux or no PID: just update UI state
                self._finalize_cancel_ui()
        except Exception as e:
            logger.warning(f"Cancel update failed: {e}")
            self._finalize_cancel_ui()

    def _finalize_cancel_ui(self):
        try:
            if self._update_log_timer and self._update_log_timer.isActive():
                self._update_log_timer.stop()
        except Exception:
            pass
        self._set_updating_status("Update canceled.")
        # Hide overlay shortly after message so the user sees confirmation
        def _hide():
            self._set_updating_in_progress(False)
        QTimer.singleShot(800, _hide)

    @pyqtSlot(result=str)
    def get_current_version(self):
        """Get the current git commit hash"""
        src_dir = os.path.dirname(__file__)
        info = get_git_version_info(src_dir)
        return info['hash'] if info else "Unknown"

    @pyqtSlot(result=QVariant)
    def get_current_version_info(self):
        """Get current version info including commit hash and message"""
        src_dir = os.path.dirname(__file__)
        info = get_git_version_info(src_dir)
        return info if info else {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}

    @pyqtSlot(result=QVariant)
    def get_latest_version_info(self):
        """Get latest version info from GitHub including commit hash and message"""
        src_dir = os.path.dirname(__file__)
        current_info = get_git_version_info(src_dir)
        current_hash = current_info['hash'] if current_info else ""
        
        has_update, latest_info = check_github_for_updates(current_hash, branch=self._target_branch)
        return latest_info if latest_info else {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}

    @pyqtSlot(str)
    def setTargetBranch(self, branch):
        self.targetBranch = branch

    @pyqtSlot()
    def checkForUpdatesNow(self):
        """Start an asynchronous check for updates"""
        if self._update_checking:
            return
        
        self._update_checking = True
        self.versionInfoChanged.emit()
        threading.Thread(target=self._perform_update_check, daemon=True).start()

    def _perform_update_check(self):
        """Perform the actual update check (called asynchronously)"""
        try:
            src_dir = os.path.dirname(__file__)
            current_info = get_git_version_info(src_dir)
            current_hash = current_info['hash'] if current_info else ""
            
            has_update, latest_info = check_github_for_updates(current_hash, branch=self._target_branch)
            
            if latest_info:
                self._latest_version_info = latest_info
                if has_update:
                    self.updateAvailable = True
                    logger.info(f"New update available: {latest_info['short_hash']}")
                else:
                    self.updateAvailable = False
                    logger.debug("No updates available (already on latest)")
            else:
                self.updateAvailable = False
                logger.debug("No update info retrieved")
                
            self._last_update_check = datetime.now()
            # Refresh cached version info
            self._current_version_info = current_info or {}
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
        finally:
            self._update_checking = False
            self.versionInfoChanged.emit()

    @pyqtSlot()
    def show_update_dialog(self):
        """Show the update dialog"""
        self.updateDialogRequested.emit()

    @pyqtSlot()
    def reboot_device(self):
        """Reboot the device"""
        logger.info("Reboot requested via UI")
        try:
            if platform.system() == 'Linux':
                # Try standard reboot command with sudo
                # Use sudo -n to avoid hanging if password is required (though it shouldn't be)
                subprocess.run(['sudo', '-n', 'reboot'], check=True)
            else:
                logger.info("Reboot not supported on this platform (simulating)")
        except Exception as e:
            logger.error(f"Failed to reboot: {e}")
            # Fallback to absolute path if standard reboot fails
            try:
                if platform.system() == 'Linux':
                    subprocess.run(['sudo', '-n', '/usr/sbin/reboot'], check=True)
            except Exception as e2:
                logger.error(f"Fallback reboot failed: {e2}")
    def check_network_connectivity(self):
        """Check if we have active network connectivity (beyond just WiFi connection)"""
        return test_network_connectivity()

    # --- Non-blocking network connectivity check helpers ---
    def _start_network_connectivity_check_async(self):
        """Run the network connectivity check in a background thread to avoid blocking UI."""
        try:
            if self._network_check_in_progress:
                logger.debug("Network connectivity check already in progress; skipping new request")
                return

            self._network_check_in_progress = True

            def _worker():
                try:
                    # Perform the potentially blocking check off the UI thread
                    result = self.check_network_connectivity()
                except Exception as e:
                    logger.debug(f"Background network check error: {e}")
                    result = False

                # Marshal result back to the main thread
                def _apply():
                    try:
                        previous = self._network_connected
                        if result != previous:
                            self._network_connected = result
                            logger.info(f"Network connectivity status changed: {result}")
                            # Emit signals; keep compatibility by reusing wifiConnectedChanged
                            try:
                                self.wifiConnectedChanged.emit()
                            except Exception as _e:
                                logger.debug(f"Emit wifiConnectedChanged failed: {_e}")
                            try:
                                self.networkConnectedChanged.emit()
                            except Exception as _e:
                                logger.debug(f"Emit networkConnectedChanged failed: {_e}")
                    finally:
                        self._network_check_in_progress = False

                # Use QTimer.singleShot(0, ...) to ensure execution on the Qt main thread
                try:
                    QTimer.singleShot(0, _apply)
                except Exception as e:
                    logger.debug(f"Failed to schedule result application on main thread: {e}; applying directly")
                    _apply()

            threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:
            logger.debug(f"Failed to start background network check: {e}")
            self._network_check_in_progress = False


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

        profiler.mark("ChartItem: paint Start")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 25  # Reduced margin for closer fit to container

        # Colors - Tesla-inspired dark theme
        if self._theme == "dark":
            bg_color = QColor("#181818")  # Match card background
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

        # Calculate dynamic y-axis intervals based on data range
        interval = calculate_chart_interval(self._max_value)

        # Draw Tesla-style grid lines (ultra-thin white lines with subtle glow)
        # Main grid lines - very thin with slight glow
        grid_pen = QPen(grid_color, 0.5, Qt.PenStyle.SolidLine)
        grid_pen.setColor(QColor(grid_color.red(), grid_color.green(), grid_color.blue(), 80))  # Higher opacity for main lines
        painter.setPen(grid_pen)
        max_intervals = int(self._max_value / interval) + 1
        actual_max = max_intervals * interval

        # Draw horizontal grid lines with subtle glow effect
        for i in range(max_intervals + 1):
            value = actual_max - (i * interval)
            y = margin + (height - 2 * margin) * (actual_max - value) / actual_max if actual_max > 0 else margin

            # Subtle glow behind main line
            glow_pen = QPen(QColor(grid_color.red(), grid_color.green(), grid_color.blue(), 30), 2, Qt.PenStyle.SolidLine)
            painter.setPen(glow_pen)
            painter.drawLine(int(margin), int(y), int(width - margin), int(y))

            # Main grid line
            painter.setPen(grid_pen)
            painter.drawLine(int(margin), int(y), int(width - margin), int(y))

        # Draw vertical grid lines for x-axis with same styling
        if self._months:
            for i in range(len(self._months)):
                x = margin + (width - 2 * margin) * i / (len(self._months) - 1) if len(self._months) > 1 else margin

                # Subtle glow behind main line
                glow_pen = QPen(QColor(grid_color.red(), grid_color.green(), grid_color.blue(), 30), 2, Qt.PenStyle.SolidLine)
                painter.setPen(glow_pen)
                painter.drawLine(int(x), int(margin), int(x), int(height - margin))

                # Main grid line
                painter.setPen(grid_pen)
                painter.drawLine(int(x), int(margin), int(x), int(height - margin))

        # Draw y-axis labels with modern Tesla styling
        label_font = painter.font()
        label_font.setPixelSize(11)
        label_font.setWeight(QFont.Weight.Medium)  # Slightly bolder for better readability
        painter.setFont(label_font)

        for i in range(max_intervals + 1):
            value = actual_max - (i * interval)
            y = margin + (height - 2 * margin) * (actual_max - value) / actual_max if actual_max > 0 else margin

            # Draw label with subtle shadow for depth
            label_text = f"{int(value)}"

            # Shadow
            painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
            painter.drawText(int(margin - 45), int(y + 4), label_text)

            # Main label
            painter.setPen(QPen(text_color))
            painter.drawText(int(margin - 45), int(y + 3), label_text)
            y = margin + (height - 2 * margin) * (actual_max - value) / actual_max if actual_max > 0 else margin
            painter.drawText(int(5), int(y + 4), f"{int(value)}")

        # Draw x-axis labels
        if self._months:
            for i, month in enumerate(self._months):
                x = margin + (width - 2 * margin) * i / (len(self._months) - 1) if len(self._months) > 1 else margin
                # Convert month period (e.g., "2024-01") to short month name (e.g., "Jan")
                month_num = int(month.split('-')[1])
                month_name = calendar.month_abbr[month_num]
                painter.drawText(int(x - 10), int(height - 5), month_name)

        # Draw legend - horizontal line just above the plot
        legend_y = margin - 20  # Position higher with increased gap to plot
        legend_spacing = 10  # Tight horizontal spacing
        
        # Calculate total width needed for legend items
        total_legend_width = 0
        font_metrics = painter.fontMetrics()
        for series_data in self._series:
            text_width = font_metrics.horizontalAdvance(series_data['label'])
            item_width = 12 + 16 + text_width
            total_legend_width += item_width
        total_legend_width += (len(self._series) - 1) * legend_spacing if self._series else 0
        
        # Center the legend horizontally
        legend_x_start = (width - total_legend_width) / 2
        
        current_x = legend_x_start
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
                color = colors[s % len(colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color))
            painter.drawEllipse(int(current_x), int(legend_y), 12, 12)
            painter.setPen(QPen(text_color))
            painter.drawText(int(current_x + 16), int(legend_y + 10), series_data['label'])
            
            # Move to next item position
            text_width = font_metrics.horizontalAdvance(series_data['label'])
            current_x += 12 + 16 + text_width + legend_spacing

        # Draw chart
        if self._chart_type == "bar":
            self._draw_bar_chart(painter, width, height, margin, colors, actual_max)
        elif self._chart_type == "line":
            self._draw_line_chart(painter, width, height, margin, colors, actual_max)
        elif self._chart_type == "area":
            self._draw_area_chart(painter, width, height, margin, colors, actual_max)
        
        profiler.mark("ChartItem: paint End")

    def _draw_bar_chart(self, painter, width, height, margin, colors, actual_max):
        if not self._months:
            return
        bar_width = (width - 2 * margin) / len(self._months) / len(self._series)
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                base_color = QColor(series_data['color'])
            else:
                base_color = colors[s % len(colors)]
            if self._view_mode == 'cumulative':
                # Cumulative plot: split bars into base and increment
                for i, value in enumerate(series_data['values']):
                    prev_value = series_data['values'][i-1] if i > 0 else 0
                    increment = value - prev_value
                    x = margin + i * (width - 2 * margin) / len(self._months) + s * bar_width
                    
                    # Draw base (previous cumulative) with clean Tesla styling
                    base_height = (height - 2 * margin) * prev_value / actual_max if actual_max > 0 else 0
                    y_base = height - margin - base_height

                    # Subtle single-layer glow for depth
                    glow_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 40)
                    painter.setBrush(QBrush(glow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    glow_width = bar_width * 1.1
                    glow_height = base_height * 1.05
                    glow_x = x - (glow_width - bar_width) / 2
                    glow_y = y_base - (glow_height - base_height) / 2
                    painter.drawRoundedRect(QRectF(glow_x, glow_y, glow_width, glow_height), 0.5, 0.5)

                    # Clean solid bar with minimal border
                    painter.setBrush(QBrush(base_color))
                    painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 150), 0.5))
                    painter.drawRoundedRect(QRectF(x, y_base, bar_width, base_height), 0.5, 0.5)
                    
                    # Draw increment with clean Tesla styling
                    increment_height = (height - 2 * margin) * increment / actual_max if actual_max > 0 else 0
                    y_increment = y_base - increment_height
                    increment_color = base_color.lighter(125)

                    # Subtle increment glow
                    increment_glow_color = QColor(increment_color.red(), increment_color.green(), increment_color.blue(), 40)
                    painter.setBrush(QBrush(increment_glow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    increment_glow_width = bar_width * 1.1
                    increment_glow_height = increment_height * 1.05
                    increment_glow_x = x - (increment_glow_width - bar_width) / 2
                    increment_glow_y = y_increment - (increment_glow_height - increment_height) / 2
                    painter.drawRoundedRect(QRectF(increment_glow_x, increment_glow_y, increment_glow_width, increment_glow_height), 0.5, 0.5)

                    # Clean increment bar
                    painter.setBrush(QBrush(increment_color))
                    painter.setPen(QPen(QColor(increment_color.red(), increment_color.green(), increment_color.blue(), 150), 0.5))
                    painter.drawRoundedRect(QRectF(x, y_increment, bar_width, increment_height), 0.5, 0.5)
            else:
                # Non-cumulative plot: draw bars with clean Tesla styling
                for i, value in enumerate(series_data['values']):
                    x = margin + i * (width - 2 * margin) / len(self._months) + s * bar_width
                    bar_height = (height - 2 * margin) * value / actual_max if actual_max > 0 else 0
                    y = height - margin - bar_height

                    # Subtle single-layer glow
                    glow_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 40)
                    painter.setBrush(QBrush(glow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    glow_width = bar_width * 1.1
                    glow_height = bar_height * 1.05
                    glow_x = x - (glow_width - bar_width) / 2
                    glow_y = y - (glow_height - bar_height) / 2
                    painter.drawRoundedRect(QRectF(glow_x, glow_y, glow_width, glow_height), 0.5, 0.5)

                    # Clean solid bar
                    painter.setBrush(QBrush(base_color))
                    painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 150), 0.5))
                    painter.drawRoundedRect(QRectF(x, y, bar_width, bar_height), 0.5, 0.5)

    def _draw_line_chart(self, painter, width, height, margin, colors, actual_max):
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
                color = colors[s % len(colors)]

            points = []
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / actual_max if actual_max > 0 else height - margin
                points.append(QPoint(int(x), int(y)))

            # Draw simplified glow line (1 layer instead of 3)
            glow_color = QColor(color.red(), color.green(), color.blue(), 40)
            painter.setPen(QPen(glow_color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if len(points) > 1:
                painter.drawPolyline(points)

            # Draw main line with smooth caps and joins
            painter.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if len(points) > 1:
                painter.drawPolyline(points)

            # Draw simplified point markers (1 layer instead of 4)
            for point in points:
                # Single glow layer
                glow_color = QColor(color.red(), color.green(), color.blue(), 60)
                painter.setBrush(QBrush(glow_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(point, 5, 5)

                # Main point with subtle border
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 150), 0.5))
                painter.drawEllipse(point, 2, 2)

    def _draw_area_chart(self, painter, width, height, margin, colors, actual_max):
        for s, series_data in enumerate(self._series):
            # Use custom color from series data if available, otherwise use default
            if 'color' in series_data:
                color = QColor(series_data['color'])
            else:
                color = colors[s % len(colors)]

            points = [QPoint(int(margin), int(height - margin))]
            for i, value in enumerate(series_data['values']):
                x = margin + (width - 2 * margin) * i / max(1, len(series_data['values']) - 1)
                y = height - margin - (height - 2 * margin) * value / actual_max if actual_max > 0 else height - margin
                points.append(QPoint(int(x), int(y)))
            points.append(QPoint(int(width - margin), int(height - margin)))

            # Draw simplified glow fill (1 layer instead of 3)
            glow_fill_color = QColor(color.red(), color.green(), color.blue(), 25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_fill_color))
            
            # Use a slightly offset polygon for the single glow layer
            glow_points = []
            for point in points:
                if point.y() < height - margin:
                    glow_points.append(QPoint(int(point.x()), int(point.y() - 2)))
                else:
                    glow_points.append(point)
            painter.drawPolygon(glow_points)

            # Draw main area fill with sophisticated gradient
            gradient = QLinearGradient(0, margin, 0, height - margin)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 180))  # Top
            gradient.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(), 140))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 100))  # Bottom

            painter.setBrush(QBrush(gradient))
            painter.drawPolygon(points)

            # Draw simplified outline (1 layer instead of 3)
            outline_color = QColor(color.red(), color.green(), color.blue(), 90)
            painter.setPen(QPen(outline_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(points)

            # Draw final sharp outline
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPolygon(points)
        
        profiler.mark("ChartItem: paint End")

qmlRegisterType(ChartItem, 'Charts', 1, 0, 'ChartItem')

if __name__ == '__main__':
    profiler.mark("Main Execution Started")
    # Set console encoding to UTF-8 to handle Unicode characters properly
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    
    logger.info("BOOT: Starting SpaceX Dashboard application...")
    
    # Start local HTTP server for serving HTML files
    profiler.mark("Starting HTTP Server")
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    
    # Ensure Qt WebEngine QML types are initialized before loading QML
    try:
        profiler.mark("QtWebEngineQuick Initialize")
        QtWebEngineQuick.initialize()
    except Exception as e:
        print(f"QtWebEngineQuick.initialize() notice: {e}")

    profiler.mark("QApplication Initialization")
    # Support high DPI scaling by using environment variables if set
    # These are typically set in setup_dashboard_environment() from functions.py
    # or by the user via DASHBOARD_SCALE.
    # We already called setup_dashboard_environment() at the top of the file.
    
    # QApplication setup
    # Optimize Qt WebEngine for Raspberry Pi performance
    if '--disable-background-timer-throttling' not in sys.argv:
        sys.argv.append('--disable-background-timer-throttling')
    if '--memory-pressure-off' not in sys.argv:
        sys.argv.append('--memory-pressure-off')
        
    app = QApplication(sys.argv)
    if platform.system() != 'Windows':
        app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))  # Blank cursor globally

    # Load fonts
    profiler.mark("Loading Fonts")
    font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "D-DIN.ttf")
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)

    fa_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Font Awesome 5 Free-Solid-900.otf")
    if os.path.exists(fa_path):
        QFontDatabase.addApplicationFont(fa_path)

    # Create Backend immediately with default offline status to speed up UI presentation.
    # Initial WiFi check will run asynchronously to avoid blocking the main thread.
    profiler.mark("Creating Backend")
    logger.info("BOOT: Creating Backend instance...")
    backend = Backend(initial_wifi_connected=False, initial_wifi_ssid="")
    # Now start the data loader which will kick off background checks
    profiler.mark("Starting Data Loader")
    logger.info("BOOT: Starting data loader...")
    backend.startDataLoader()
    
    profiler.mark("Initializing QML Engine")
    engine = QQmlApplicationEngine()
    # Connect QML warnings signal (list of QQmlError objects)
    def _log_qml_warnings(errors):
        for e in errors:
            msg = format_qt_message(None, None, e.toString())
            if msg: logger.error(f"QML warning: {msg}")
    try:
        engine.warnings.connect(_log_qml_warnings)
    except Exception as _e:
        logger.warning(f"Could not connect engine warnings signal: {_e}")
    profiler.mark("Setting Context Properties")
    context = engine.rootContext()
    context.setContextProperty("backend", backend)
    context.setContextProperty("radarLocations", radar_locations)
    context.setContextProperty("circuitCoords", circuit_coords)
    context.setContextProperty("spacexLogoPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'spacex_logo.png').replace('\\', '/'))
    context.setContextProperty("chevronPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'double-chevron.png').replace('\\', '/'))

    profiler.mark("Preparing URLs")
    globe_file_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'globe.html')
    earth_texture_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'earth_texture.jpg')
    youtube_html_path = os.path.join(os.path.dirname(__file__), 'youtube_embed.html')

    context.setContextProperty("globeUrl", "file:///" + globe_file_path.replace('\\', '/'))

    from ui_qml import qml_code  # Load QML from external module
    profiler.mark("Engine LoadData Start")
    engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
    profiler.mark("Engine LoadData End")
    if not engine.rootObjects():
        logger.error("QML root object creation failed (see earlier QML errors above).")
        print("QML load failed. Check console for Qt errors.")
        sys.exit(-1)
    profiler.mark("App Startup Complete")
    backend.setBootMode(False)
    profiler.log_summary()
    sys.exit(app.exec())