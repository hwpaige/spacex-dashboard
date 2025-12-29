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
import pandas as pd
import time
import subprocess
import signal
import calendar
from track_generator import generate_track_map
# Plotly chart generation is now handled in functions.py
import threading
import functions as funcs
from functions import (
    # status helpers
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
    fetch_f1_data,
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
    parse_metar,
    rotate,
    # CACHE_REFRESH constants
    CACHE_REFRESH_INTERVAL_PREVIOUS,
    CACHE_REFRESH_INTERVAL_UPCOMING,
    CACHE_REFRESH_INTERVAL_F1,
    CACHE_REFRESH_INTERVAL_F1_SCHEDULE,
    CACHE_REFRESH_INTERVAL_F1_STANDINGS,
    # CACHE_FILE constants
    TRAJECTORY_CACHE_FILE,
    CACHE_FILE_PREVIOUS,
    CACHE_FILE_PREVIOUS_BACKUP,
    CACHE_FILE_UPCOMING,
    CACHE_DIR_F1,
    CACHE_FILE_F1_SCHEDULE,
    CACHE_FILE_F1_DRIVERS,
    CACHE_FILE_F1_CONSTRUCTORS,
    RUNTIME_CACHE_FILE_PREVIOUS,
    RUNTIME_CACHE_FILE_UPCOMING,
    WIFI_KEY_FILE,
    REMEMBERED_NETWORKS_FILE,
    LAST_CONNECTED_NETWORK_FILE,
    # data constants
    F1_TEAM_COLORS,
    location_settings,
    radar_locations,
    circuit_coords,
    perform_wifi_scan,
    manage_nm_autoconnect,
    test_network_connectivity,
    get_git_version_info,
    check_github_for_updates,
    get_country_flag_url,
    get_launch_trends_series,
    generate_f1_chart_html,
    get_launch_trajectory_data,
    group_event_data,
    LAUNCH_DESCRIPTIONS,
    normalize_team_name,
    check_wifi_interface,
    get_wifi_interface_info,
    get_wifi_debug_info,
    start_update_script,
    get_f1_driver_points_chart,
    get_f1_constructor_points_chart,
    get_f1_driver_points_series,
    get_f1_constructor_points_series,
    get_f1_driver_standings_over_time_series,
    get_empty_chart_url,
    generate_month_labels_for_days,
    connect_to_wifi_nmcli,
    connect_to_wifi_worker,
    get_max_value_from_series,
    get_next_launch_info,
    get_upcoming_launches_list,
    get_next_race_info,
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
    get_update_progress_summary,
    perform_bootstrap_diagnostics,
    disconnect_from_wifi,
    bring_up_nm_connection,
    sync_remembered_networks,
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

# Initialize environment and logging
setup_dashboard_environment()
setup_dashboard_logging(__file__)
logger = logging.getLogger(__name__)

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
        try:
            # Delegate logic to UI-agnostic helper in functions.py
            self._grouped_data = group_event_data(self._data, self._mode, self._event_type, self._tz)
        except Exception as e:
            logger.error(f"EventModel: Failed to update data: {e}")
            self._grouped_data = []
        self.endResetModel()

class DataLoader(QObject):
    finished = pyqtSignal(dict, dict, dict)
    statusUpdate = pyqtSignal(str)

    def run(self):
        logger.info("DataLoader: Starting parallel data loading...")
        def _safe_emit_status(msg):
            try: self.statusUpdate.emit(msg)
            except RuntimeError: pass

        def _safe_emit_finished(l, f, w):
            try: self.finished.emit(l, f, w)
            except RuntimeError: pass

        # Delegate full load to functions.py
        launch_data, f1_data, weather_data = perform_full_dashboard_data_load(
            location_settings, 
            status_callback=_safe_emit_status
        )

        _safe_emit_finished(launch_data, f1_data, weather_data)

class LaunchUpdater(QObject):
    finished = pyqtSignal(dict)
    def run(self):
        launch_data = fetch_launches()
        self.finished.emit(launch_data)

class WeatherUpdater(QObject):
    finished = pyqtSignal(dict)
    def run(self):
        weather_data = fetch_weather_for_all_locations(location_settings)
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
    networkConnectedChanged = pyqtSignal()
    loadingFinished = pyqtSignal()
    # New signals for signal-based startup flow
    launchCacheReady = pyqtSignal()
    firstOnline = pyqtSignal()
    updateGlobeTrajectory = pyqtSignal()
    reloadWebContent = pyqtSignal()
    launchTrayVisibilityChanged = pyqtSignal()
    loadingStatusChanged = pyqtSignal()
    updateAvailableChanged = pyqtSignal()
    updateDialogRequested = pyqtSignal()
    # Globe spin/watchdog feature flag
    globeAutospinGuardChanged = pyqtSignal()
    # WiFi scanning progress notify (for UI spinner)
    wifiScanInProgressChanged = pyqtSignal()
    # WiFi scan results delivered from background thread (queued to UI thread)
    wifiScanResultsReady = pyqtSignal(list)
    # Emitted by background boot worker to deliver results to main thread
    initialChecksReady = pyqtSignal(bool, bool, dict, dict)
    # Update progress UI signals
    updatingInProgressChanged = pyqtSignal()
    updatingInProgressChanged = pyqtSignal()
    updatingStatusChanged = pyqtSignal()
    # Signal for thread-safe WiFi status updates
    wifiCheckReady = pyqtSignal(bool, str)

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
        self._last_update_check = None  # Track when updates were last checked
        self._current_version_info = None  # Cached current version info
        self._latest_version_info = None  # Cached latest version info
        self._update_checking = False  # Track if update check is in progress
        # Throttle web content reload signals to avoid flapping-induced UI hiccups
        self._last_web_reload_emit = 0.0
        self._min_reload_emit_interval_sec = 8.0
        
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
            self._trajectory_recompute_timer.setInterval(250)
        except Exception:
            pass
        self._trajectory_compute_inflight = False
        self._trajectory_emit_timer = QTimer(self)
        self._trajectory_emit_timer.setSingleShot(True)
        try:
            self._trajectory_emit_timer.setInterval(120)
        except Exception:
            pass

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
        except Exception as _e:
            logger.debug(f"Could not connect initialChecksReady signal: {_e}")
        # Connect Wi‑Fi scan results signal (ensures UI-thread application)
        try:
            self.wifiScanResultsReady.connect(self._apply_wifi_scan_results)
        except Exception as _e:
            logger.debug(f"Could not connect wifiScanResultsReady signal: {_e}")
        # Boot guard timer placeholder
        self._initial_checks_guard_timer = None

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
        logger.info("BOOT: startDataLoader called (legacy path)")
        self.setLoadingStatus("Checking network connectivity…")
        # Legacy path kept for compatibility; avoid time-based gating. We'll kick off background
        # connectivity check and, if online, start immediate data loading. No splash timers.

        def _initial_checks_worker():
            src_dir = os.path.dirname(__file__)
            res = perform_bootstrap_diagnostics(src_dir, self._wifi_connected)
            # Emit results; connected slot will run on the main thread
            try:
                self.initialChecksReady.emit(*res)
            except Exception as e:
                logger.error(f"BOOT: Failed to emit initialChecksReady: {e}")

        threading.Thread(target=_initial_checks_worker, daemon=True).start()
        # Return immediately; UI remains responsive while checks run. No guard timers.

    @pyqtSlot(bool, bool, dict, dict)
    def _apply_initial_checks_results(self, connectivity_result, update_available, current_info, latest_info):
        """Apply initial check results on the main (Qt) thread."""
        try:
            self.updateAvailable = update_available
            self._current_version_info = current_info
            self._latest_version_info = latest_info

            if not connectivity_result:
                logger.warning("BOOT: No network connectivity detected - staying with seed/runtime cache; will wait for firstOnline signal")
                # Set up periodic timers; connectivity checks will bring us online and trigger firstOnline
                self._setup_timers()
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
        except Exception as e:
            logger.error(f"BOOT: Failed to apply initial checks results on main thread: {e}")

    @pyqtSlot()
    def _on_initial_checks_guard_timeout(self):
        """Deprecated: time-based guard disabled (signal-based startup)."""
        logger.info("BOOT: _on_initial_checks_guard_timeout called but guard is disabled; no action")

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
        self.wifi_timer.start(10000)  # Check every 10 seconds

        # Update check timer - check every 6 hours (21600000 ms)
        self.update_check_timer = QTimer(self)
        self.update_check_timer.timeout.connect(self.check_for_updates_periodic)
        self.update_check_timer.start(21600000)  # 6 hours

    @pyqtSlot()
    def check_for_updates_periodic(self):
        """Periodic update check in background"""
        def _worker():
            try:
                # Use a background thread for the network request
                update_available = self.check_for_updates()
                QTimer.singleShot(0, lambda: self._apply_update_result(update_available))
            except Exception as e:
                logger.debug(f"Periodic update check failure: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_update_result(self, update_available):
        """Apply update result on main thread"""
        self.updateAvailable = update_available
        logger.info(f"Periodic update check result: {update_available}")
        
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
            self._f1_data.get('schedule', []), 
            self._mode, 
            self.get_next_launch(), 
            self.get_next_race(), 
            self._tz
        )

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrends(self):
        current_year = datetime.now(pytz.UTC).year
        current_month = datetime.now(pytz.UTC).month
        months, series = get_launch_trends_series(
            self._launch_data['previous'],
            self._chart_view_mode,
            current_year,
            current_month
        )
        return {'months': months, 'series': series}

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsMonths(self):
        current_year = datetime.now(pytz.UTC).year
        current_month = datetime.now(pytz.UTC).month
        months, _ = get_launch_trends_series(
            self._launch_data['previous'],
            self._chart_view_mode,
            current_year,
            current_month
        )
        return months

    @pyqtProperty(int, notify=launchesChanged)
    def launchTrendsMaxValue(self):
        current_year = datetime.now(pytz.UTC).year
        current_month = datetime.now(pytz.UTC).month
        _, series = get_launch_trends_series(
            self._launch_data['previous'],
            self._chart_view_mode,
            current_year,
            current_month
        )
        return get_max_value_from_series(series)

    def _generate_month_labels_for_days(self):
        """Generate month labels for daily data points"""
        return generate_month_labels_for_days(datetime.now(pytz.UTC).year)

    @pyqtProperty(QVariant, notify=launchesChanged)
    def launchTrendsSeries(self):
        current_year = datetime.now(pytz.UTC).year
        current_month = datetime.now(pytz.UTC).month
        _, series = get_launch_trends_series(
            self._launch_data['previous'],
            self._chart_view_mode,
            current_year,
            current_month
        )
        return series

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
        return get_f1_driver_points_chart(self._f1_data['driver_standings'])

    @pyqtProperty(QVariant, notify=f1Changed)
    def constructorPointsChart(self):
        return get_f1_constructor_points_chart(self._f1_data['constructor_standings'])

    @pyqtProperty(QVariant, notify=f1Changed)
    def driverPointsSeries(self):
        return get_f1_driver_points_series(self._f1_data['driver_standings'], getattr(self, '_f1_chart_stat', 'points'))

    @pyqtProperty(QVariant, notify=f1Changed)
    def constructorPointsSeries(self):
        return get_f1_constructor_points_series(self._f1_data['constructor_standings'], getattr(self, '_f1_chart_stat', 'points'))

    @pyqtProperty(QVariant, notify=f1Changed)
    def driverStandingsOverTimeSeries(self):
        return get_f1_driver_standings_over_time_series(self._f1_data['driver_standings'], getattr(self, '_f1_chart_stat', 'points'))

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
        return float(get_max_value_from_series(self.driverPointsSeries))

    @pyqtProperty(float, notify=f1Changed)
    def constructorPointsMaxValue(self):
        return float(get_max_value_from_series(self.constructorPointsSeries))

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
            stat_key = getattr(self, '_f1_chart_stat', 'points')
            theme = getattr(self, '_theme', 'dark')
            html = generate_f1_chart_html(self._f1_data, chart_type, stat_key, theme)

            import tempfile
            import os
            temp_file = os.path.join(tempfile.gettempdir(), 'f1_chart.html')
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html)

            return f'file:///{temp_file.replace("\\", "/")}'

        except Exception as e:
            logging.error(f"F1 chart URL error: {e}")
            return self._get_empty_chart_url()

    def _get_empty_chart_url(self):
        """Return URL for empty chart state"""
        return get_empty_chart_url(getattr(self, '_theme', 'dark'))


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

    @pyqtProperty('QVariantMap', notify=updateDialogRequested)
    def currentVersionInfo(self):
        if self._current_version_info is None:
            self._current_version_info = self.get_current_version_info() or {}
        return self._current_version_info

    @pyqtProperty('QVariantMap', notify=updateDialogRequested)
    def latestVersionInfo(self):
        if self._latest_version_info is None:
            self._latest_version_info = self.get_latest_version_info() or {}
        return self._latest_version_info

    @pyqtProperty(str, notify=updateDialogRequested)
    def lastUpdateCheckTime(self):
        if hasattr(self, '_last_update_check') and self._last_update_check:
            return self._last_update_check.strftime("%H:%M:%S")
        return "Never"

    @pyqtProperty(bool, notify=updateDialogRequested)
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

    @pyqtProperty(list, notify=launchesChanged)
    def launchDescriptions(self):
        return LAUNCH_DESCRIPTIONS

    @pyqtSlot(result=QVariant)
    def get_next_launch(self):
        return get_next_launch_info(self._launch_data['upcoming'], self._tz)

    @pyqtSlot(result=QVariant)
    def get_upcoming_launches(self):
        return get_upcoming_launches_list(self._launch_data['upcoming'], self._tz)

    @pyqtSlot(result=QVariant)
    def get_launch_trajectory(self):
        """Get trajectory data for the next upcoming launch"""
        logger.info("get_launch_trajectory called")
        upcoming = self.get_upcoming_launches()
        previous = self._launch_data.get('previous', [])
        
        # Use the centralized trajectory calculator in functions.py
        result = get_launch_trajectory_data(upcoming, previous)
        return result

    @pyqtSlot(result=QVariant)
    def get_next_race(self):
        return get_next_race_info(self._f1_data['schedule'], self._tz)

    def initialize_weather(self):
        return initialize_all_weather(location_settings)

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
        # Update countdown every second and re-evaluate tray visibility
        self.countdownChanged.emit()
        self.launchTrayVisibilityChanged.emit()

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
        # Exit loading state after data is loaded and processed
        self.setLoadingStatus("Application loaded...")
        self._isLoading = False
        self.loadingFinished.emit()
        self.launchesChanged.emit()
        self.launchTrayVisibilityChanged.emit()
        self.f1Changed.emit()
        logging.info("F1 changed signal emitted")
        self.weatherChanged.emit()
        self.eventModelChanged.emit()

        # Update trajectory now that data is loaded (debounced) and precompute in background
        self._emit_update_globe_trajectory_debounced()
        self._schedule_trajectory_recompute()
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
        logger.info("BOOT: Loading timeout reached (deprecated) — offline path retained for compatibility")
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

        # Exit loading state after offline data is loaded
        self.setLoadingStatus("Application loaded...")
        self._isLoading = False
        self.loadingFinished.emit()
        # Mirror the same UI update signals as online path so QML refreshes lists and trajectory
        try:
            self.launchesChanged.emit()
            self.launchTrayVisibilityChanged.emit()
            self.f1Changed.emit()
            self.weatherChanged.emit()
            self.eventModelChanged.emit()
            # Update trajectory now that cached data is applied
            self._emit_update_globe_trajectory_debounced()
            self._schedule_trajectory_recompute()
        except Exception as _e:
            logger.debug(f"BOOT: Error emitting offline refresh signals: {_e}")
        logger.info("BOOT: Offline mode activated - app should now show cached data")

    def _seed_bootstrap(self):
        """Apply cached (runtime or git-seeded) data immediately and exit splash.
        This is signal-based and avoids any time-based waits."""
        try:
            self.setLoadingStatus("Loading cached SpaceX data…")
            # Load launches from runtime cache, falling back to seed
            prev_cache = load_launch_cache('previous')
            up_cache = load_launch_cache('upcoming')
            self._launch_data = {
                'previous': (prev_cache.get('data') if prev_cache else []) or [],
                'upcoming': (up_cache.get('data') if up_cache else []) or []
            }
            # Update EventModel immediately
            self._event_model._data = self._launch_data if self._mode == 'spacex' else self._f1_data.get('schedule', [])
            self._event_model.update_data()

            # Notify UI of ready cache
            try:
                self.launchCacheReady.emit()
            except Exception:
                pass
            self.launchesChanged.emit()
            self.launchTrayVisibilityChanged.emit()
            self.eventModelChanged.emit()
            # Update trajectory now that we have at least cached data
            self._emit_update_globe_trajectory_debounced()
            self._schedule_trajectory_recompute()
            # Exit splash now that cache is applied
            self.setLoadingStatus("Application loaded…")
            self._isLoading = False
            self.loadingFinished.emit()
            logger.info("BOOT: Seed/runtime cache applied; splash dismissed via launchCacheReady")
        except Exception as e:
            logger.error(f"Seed bootstrap failed: {e}")

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
                self.loader = DataLoader()
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

    def _load_cached_f1_data(self):
        """Load cached F1 data for offline mode"""
        try:
            schedule_cache = load_cache_from_file(CACHE_FILE_F1_SCHEDULE)
            drivers_cache = load_cache_from_file(CACHE_FILE_F1_DRIVERS)
            constructors_cache = load_cache_from_file(CACHE_FILE_F1_CONSTRUCTORS)
            
            schedule = schedule_cache['data'] if schedule_cache else []
            driver_standings = drivers_cache['data'] if drivers_cache else []
            constructor_standings = constructors_cache['data'] if constructors_cache else []
            
            # Normalize driver standings
            for standing in driver_standings:
                if 'Constructor' in standing and 'name' in standing['Constructor']:
                    original_name = standing['Constructor']['name']
                    normalized_name = normalize_team_name(original_name)
                    standing['Constructor']['name'] = normalized_name
            
            # Normalize constructor standings  
            for standing in constructor_standings:
                if 'Constructor' in standing and 'name' in standing['Constructor']:
                    original_name = standing['Constructor']['name']
                    normalized_name = normalize_team_name(original_name)
                    standing['Constructor']['name'] = normalized_name
            
            logger.info("Backend: Loaded and normalized cached F1 data for offline mode")
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
        # Update globe trajectory in case current/next launch changed (e.g., after Success)
        self._emit_update_globe_trajectory_debounced()
        self._schedule_trajectory_recompute()
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

    def _start_network_connectivity_check_async(self):
        """Perform a background internet connectivity check"""
        if getattr(self, '_network_check_in_progress', False):
            return
            
        self._network_check_in_progress = True
        
        def _worker():
            try:
                # Use the imported test_network_connectivity helper
                is_online = test_network_connectivity(self._wifi_connected)
                QTimer.singleShot(0, lambda: self._apply_connectivity_result(is_online))
            except Exception as e:
                logger.debug(f"Connectivity check worker error: {e}")
            finally:
                self._network_check_in_progress = False

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_connectivity_result(self, is_online):
        """Apply the results of the background connectivity check"""
        if self._network_connected != is_online:
            logger.info(f"Network connectivity status changed: {is_online}")
            self._network_connected = is_online
            try: self.networkConnectedChanged.emit()
            except: pass

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
                self.loader = DataLoader()
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

    @pyqtSlot(str, result=str)
    def getCountryFlag(self, country_name):
        """Get flag icon path for a country name"""
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        return get_country_flag_url(country_name, assets_dir)

    @pyqtSlot()
    def runUpdateScript(self):
        """Run the update and reboot script"""
        try:
            script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'update_and_reboot.sh')      
            logger.info(f"Running update script: {script_path}")

            # Proactively show the in-app progress UI
            self._set_updating_status("Starting updater…")
            self._set_updating_in_progress(True)

            success, result = start_update_script(script_path)
            
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
        
        has_update, latest_info = check_github_for_updates(current_hash)
        return latest_info if latest_info else {'hash': 'Unknown', 'short_hash': 'Unknown', 'message': 'Unknown'}

    @pyqtSlot()
    def checkForUpdatesNow(self):
        """Start an asynchronous check for updates"""
        if self._update_checking:
            return
        
        self._update_checking = True
        self.updateDialogRequested.emit()
        threading.Thread(target=self._perform_update_check, daemon=True).start()

    def _perform_update_check(self):
        """Perform the actual update check (called asynchronously)"""
        try:
            src_dir = os.path.dirname(__file__)
            current_info = get_git_version_info(src_dir)
            current_hash = current_info['hash'] if current_info else ""
            
            has_update, latest_info = check_github_for_updates(current_hash)
            
            if has_update and latest_info:
                self._latest_version_info = latest_info
                self.updateAvailable = True
                logger.info(f"New update available: {latest_info['short_hash']}")
            else:
                self.updateAvailable = False
                logger.debug("No updates available")
                
            self._last_update_check = datetime.now()
            # Refresh cached version info
            self._current_version_info = current_info or {}
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
        finally:
            self._update_checking = False
            self.updateDialogRequested.emit()

    @pyqtSlot()
    def show_update_dialog(self):
        """Show the update dialog"""
        self.updateDialogRequested.emit()
    def check_network_connectivity(self):
        """Check if we have active network connectivity (beyond just WiFi connection)"""
        return test_network_connectivity(self._wifi_connected)

    # --- Non-blocking network connectivity check helpers ---
    def _start_network_connectivity_check_async(self):
        """Run the network connectivity check in a background thread to avoid blocking UI."""
        try:
            if self._network_check_in_progress:
                logger.debug("Network connectivity check already in progress; skipping new request")
                return

            self._network_check_in_progress = True

            def _worker(expected_wifi_connected):
                try:
                    # Perform the potentially blocking check off the UI thread
                    result = self.check_network_connectivity() if expected_wifi_connected else False
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

            # Snapshot wifi connected state to avoid race in worker
            expected_wifi_connected = self._wifi_connected

            threading.Thread(target=_worker, args=(expected_wifi_connected,), daemon=True).start()
        except Exception as e:
            logger.debug(f"Failed to start background network check: {e}")
            self._network_check_in_progress = False

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
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    
    app = QApplication(sys.argv)

    # Harden Qt WebEngine against background throttling before initialization
    try:
        extra_flags = [
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            # Keep GPU fast paths if available
            "--enable-zero-copy",
            "--ignore-gpu-blocklist",
        ]
        existing_flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
        to_add = []
        for f in extra_flags:
            if f not in existing_flags:
                to_add.append(f)
        if to_add:
            combined = (existing_flags + ' ' + ' '.join(to_add)).strip()
            os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = combined
            logger.info(f"Applied QTWEBENGINE_CHROMIUM_FLAGS: {combined}")
        else:
            logger.info("QTWEBENGINE_CHROMIUM_FLAGS already contain required anti-throttling flags")
    except Exception as _e:
        logger.warning(f"Failed to apply QTWEBENGINE_CHROMIUM_FLAGS: {_e}")

    # Ensure Qt WebEngine QML types are initialized before loading QML
    # This prevents runtime errors where WebEngineView is unknown in QML on some setups
    try:
        QtWebEngineQuick.initialize()
    except Exception as e:
        # If initialization is redundant or already done via QML import, ignore
        print(f"QtWebEngineQuick.initialize() notice: {e}")
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

            # Draw sophisticated multi-layer glow lines
            for glow_layer in range(3):
                glow_alpha = 60 - (glow_layer * 20)
                glow_width = 8 - (glow_layer * 2)
                glow_color = QColor(color.red(), color.green(), color.blue(), glow_alpha)
                painter.setPen(QPen(glow_color, glow_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                if len(points) > 1:
                    for i in range(len(points) - 1):
                        painter.drawLine(points[i], points[i + 1])

            # Draw main line with smooth caps and joins
            painter.setPen(QPen(color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            if len(points) > 1:
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

            # Draw sophisticated point markers with glow
            for point in points:
                # Multi-layer glow effect for points
                for glow_layer in range(4):
                    glow_alpha = 80 - (glow_layer * 20)
                    glow_radius = 6 - glow_layer
                    glow_color = QColor(color.red(), color.green(), color.blue(), glow_alpha)
                    painter.setBrush(QBrush(glow_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(point, glow_radius, glow_radius)

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

            # Draw sophisticated multi-layer glow fill
            for glow_layer in range(3):
                glow_alpha = 35 - (glow_layer * 10)
                glow_offset = glow_layer * 1.5

                glow_fill_color = QColor(color.red(), color.green(), color.blue(), glow_alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(glow_fill_color))

                # Create offset glow points for depth
                glow_points = []
                for point in points:
                    if point.y() < height - margin:  # Not the bottom points
                        glow_points.append(QPoint(int(point.x()), int(point.y() - glow_offset)))
                    else:
                        glow_points.append(point)
                painter.drawPolygon(glow_points)

            # Draw main area fill with sophisticated gradient
            gradient = QLinearGradient(0, margin, 0, height - margin)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 180))  # Top - more transparent
            gradient.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(), 140))  # Middle
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 100))  # Bottom - most transparent

            painter.setBrush(QBrush(gradient))
            painter.drawPolygon(points)

            # Draw sophisticated outline with multi-layer glow
            for outline_layer in range(3):
                outline_alpha = 120 - (outline_layer * 30)
                outline_width = 4 - outline_layer
                outline_color = QColor(color.red(), color.green(), color.blue(), outline_alpha)
                painter.setPen(QPen(outline_color, outline_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolygon(points)

            # Draw final sharp outline
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
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
# Do not override the status here; startDataLoader already set a meaningful
# initial message (e.g., "Checking network connectivity..."). Leaving this
# call in place could cause the UI to appear stuck on "Backend initialized..."
# if the background thread hasn't applied subsequent statuses yet.

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
context = engine.rootContext()
context.setContextProperty("backend", backend)
context.setContextProperty("radarLocations", radar_locations)
context.setContextProperty("circuitCoords", circuit_coords)
context.setContextProperty("spacexLogoPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'spacex_logo.png').replace('\\', '/'))
context.setContextProperty("f1LogoPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'f1-logo.png').replace('\\', '/'))
context.setContextProperty("f1TeamsPath", os.path.join(os.path.dirname(__file__), '..', 'assets', 'images', 'f1_teams').replace('\\', '/'))
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


from ui_qml import qml_code  # Load QML from external module
engine.loadData(qml_code.encode(), QUrl("inline.qml"))  # Provide a pseudo URL for better line numbers
if not engine.rootObjects():
    logger.error("QML root object creation failed (see earlier QML errors above).")
    print("QML load failed. Check console for Qt errors.")
    sys.exit(-1)
sys.exit(app.exec())