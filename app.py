import sys
import requests
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton, QFrame)
from PyQt5.QtCore import Qt, QTimer, QUrl, QSize, QDateTime
from PyQt5.QtGui import QFont, QFontDatabase, QIcon, QColor, QPainter
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtChart import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PyQt5.QtGui import QSurfaceFormat
from PyQt5.QtQuick import QQuickWindow, QSGRendererInterface
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz
import pandas as pd
import time

# Force OpenGL backend for QtQuick (QtWebEngine uses this under the hood)
QQuickWindow.setSceneGraphBackend(QSGRendererInterface.GraphicsApi.OpenGL)

fmt = QSurfaceFormat()
fmt.setVersion(3, 1)  # GLES 3.2 supported by Mali G31
fmt.setProfile(QSurfaceFormat.NoProfile)  # GLES has no profiles; use NoProfile
fmt.setRenderableType(QSurfaceFormat.OpenGLES)  # Switch to GLES for ARM HW accel
fmt.setDepthBufferSize(24)
fmt.setStencilBufferSize(8)
fmt.setSwapInterval(1)  # Enable vsync to reduce tearing/lag spikes
QSurfaceFormat.setDefaultFormat(fmt)

# Environment variables for Qt and Chromium
# os.environ["QT_OPENGL"] = "desktop"  # Forces desktop OpenGL on Windows (ignores ANGLE); harmless on Linux
# os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu --ignore-gpu-blacklist --enable-accelerated-video-decode --enable-webgl --enable-logging --v=1 --log-level=0"
os.environ["QT_LOGGING_RULES"] = "qt.webenginecontext=true;qt5ct.debug=false"  # Logs OpenGL context creation
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"  # Fallback for ARM sandbox crashes

# Set up logging to console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/app_launch.log'),  # Banana Pi log path
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Cache for launch data
CACHE_REFRESH_INTERVAL = 720  # 12 minutes in seconds
CACHE_FILE_PREVIOUS = '/app/previous_launches_cache.json'
CACHE_FILE_UPCOMING = '/app/upcoming_launches_cache.json'
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

# Hardcoded F1 schedule (full from user)
hardcoded_f1_schedule = [
    {"meeting_key":1253,"circuit_key":63,"circuit_short_name":"Sakhir","meeting_code":"BRN","location":"Sakhir","country_key":36,"country_code":"BRN","country_name":"Bahrain","meeting_name":"Pre-Season Testing","meeting_official_name":"FORMULA 1 ARAMCO PRE-SEASON TESTING 2025","gmt_offset":"03:00:00","date_start":"2025-02-26T07:00:00+00:00","year":2025},
    {"meeting_key":1254,"circuit_key":10,"circuit_short_name":"Melbourne","meeting_code":"AUS","location":"Melbourne","country_key":5,"country_code":"AUS","country_name":"Australia","meeting_name":"Australian Grand Prix","meeting_official_name":"FORMULA 1 LOUIS VUITTON AUSTRALIAN GRAND PRIX 2025","gmt_offset":"11:00:00","date_start":"2025-03-14T01:30:00+00:00","year":2025},
    {"meeting_key":1255,"circuit_key":49,"circuit_short_name":"Shanghai","meeting_code":"CHN","location":"Shanghai","country_key":53,"country_code":"CHN","country_name":"China","meeting_name":"Chinese Grand Prix","meeting_official_name":"FORMULA 1 HEINEKEN CHINESE GRAND PRIX 2025","gmt_offset":"08:00:00","date_start":"2025-03-21T03:30:00+00:00","year":2025},
    {"meeting_key":1256,"circuit_key":46,"circuit_short_name":"Suzuka","meeting_code":"JPN","location":"Suzuka","country_key":4,"country_code":"JPN","country_name":"Japan","meeting_name":"Japanese Grand Prix","meeting_official_name":"FORMULA 1 LENOVO JAPANESE GRAND PRIX 2025 ","gmt_offset":"09:00:00","date_start":"2025-04-04T02:30:00+00:00","year":2025},
    {"meeting_key":1257,"circuit_key":63,"circuit_short_name":"Sakhir","meeting_code":"BRN","location":"Sakhir","country_key":36,"country_code":"BRN","country_name":"Bahrain","meeting_name":"Bahrain Grand Prix","meeting_official_name":"FORMULA 1 GULF AIR BAHRAIN GRAND PRIX 2025","gmt_offset":"03:00:00","date_start":"2025-04-11T11:30:00+00:00","year":2025},
    {"meeting_key":1258,"circuit_key":149,"circuit_short_name":"Jeddah","meeting_code":"KSA","location":"Jeddah","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","meeting_name":"Saudi Arabian Grand Prix","meeting_official_name":"FORMULA 1 STC SAUDI ARABIAN GRAND PRIX 2025","gmt_offset":"03:00:00","date_start":"2025-04-18T13:30:00+00:00","year":2025},
    {"meeting_key":1259,"circuit_key":151,"circuit_short_name":"Miami","meeting_code":"USA","location":"Miami","country_key":19,"country_code":"USA","country_name":"United States","meeting_name":"Miami Grand Prix","meeting_official_name":"FORMULA 1 CRYPTO.COM MIAMI GRAND PRIX 2025","gmt_offset":"-04:00:00","date_start":"2025-05-02T16:30:00+00:00","year":2025},
    {"meeting_key":1260,"circuit_key":6,"circuit_short_name":"Imola","meeting_code":"ITA","location":"Imola","country_key":13,"country_code":"ITA","country_name":"Italy","meeting_name":"Emilia Romagna Grand Prix","meeting_official_name":"FORMULA 1 AWS GRAN PREMIO DEL MADE IN ITALY E DELL'EMILIA-ROMAGNA 2025","gmt_offset":"02:00:00","date_start":"2025-05-16T11:30:00+00:00","year":2025},
    {"meeting_key":1261,"circuit_key":22,"circuit_short_name":"Monte Carlo","meeting_code":"MON","location":"Monaco","country_key":114,"country_code":"MON","country_name":"Monaco","meeting_name":"Monaco Grand Prix","meeting_official_name":"FORMULA 1 TAG HEUER GRAND PRIX DE MONACO 2025","gmt_offset":"02:00:00","date_start":"2025-05-23T11:30:00+00:00","year":2025},
    {"meeting_key":1262,"circuit_key":15,"circuit_short_name":"Catalunya","meeting_code":"ESP","location":"Barcelona","country_key":1,"country_code":"ESP","country_name":"Spain","meeting_name":"Spanish Grand Prix","meeting_official_name":"FORMULA 1 ARAMCO GRAN PREMIO DE ESPAÑA 2025","gmt_offset":"02:00:00","date_start":"2025-05-30T11:30:00+00:00","year":2025},
    {"meeting_key":1263,"circuit_key":23,"circuit_short_name":"Montreal","meeting_code":"CAN","location":"Montréal","country_key":46,"country_code":"CAN","country_name":"Canada","meeting_name":"Canadian Grand Prix","meeting_official_name":"FORMULA 1 PIRELLI GRAND PRIX DU CANADA 2025","gmt_offset":"-04:00:00","date_start":"2025-06-13T17:30:00+00:00","year":2025},
    {"meeting_key":1264,"circuit_key":19,"circuit_short_name":"Spielberg","meeting_code":"AUT","location":"Spielberg","country_key":17,"country_code":"AUT","country_name":"Austria","meeting_name":"Austrian Grand Prix","meeting_official_name":"FORMULA 1 MSC CRUISES AUSTRIAN GRAND PRIX 2025","gmt_offset":"02:00:00","date_start":"2025-06-27T11:30:00+00:00","year":2025},
    {"meeting_key":1277,"circuit_key":2,"circuit_short_name":"Silverstone","meeting_code":"GBR","location":"Silverstone","country_key":2,"country_code":"GBR","country_name":"United Kingdom","meeting_name":"British Grand Prix","meeting_official_name":"FORMULA 1 QATAR AIRWAYS BRITISH GRAND PRIX 2025","gmt_offset":"01:00:00","date_start":"2025-07-04T11:30:00+00:00","year":2025},
    {"meeting_key":1278,"circuit_key":7,"circuit_short_name":"Spa","meeting_code":"BEL","location":"Spa","country_key":20,"country_code":"BEL","country_name":"Belgium","meeting_name":"Belgian Grand Prix","meeting_official_name":"FORMULA 1 ROLEX BELGIAN GRAND PRIX 2025","gmt_offset":"02:00:00","date_start":"2025-07-25T11:30:00+00:00","year":2025},
    {"meeting_key":1279,"circuit_key":8,"circuit_short_name":"Hungaroring","meeting_code":"HUN","location":"Budapest","country_key":21,"country_code":"HUN","country_name":"Hungary","meeting_name":"Hungarian Grand Prix","meeting_official_name":"FORMULA 1 HUNGARIAN GRAND PRIX 2025","gmt_offset":"02:00:00","date_start":"2025-08-01T11:30:00+00:00","year":2025},
    {"meeting_key":1280,"circuit_key":150,"circuit_short_name":"Zandvoort","meeting_code":"NED","location":"Zandvoort","country_key":22,"country_code":"NED","country_name":"Netherlands","meeting_name":"Dutch Grand Prix","meeting_official_name":"FORMULA 1 DUTCH GRAND PRIX 2025","gmt_offset":"02:00:00","date_start":"2025-08-29T10:30:00+00:00","year":2025},
    {"meeting_key":1281,"circuit_key":3,"circuit_short_name":"Monza","meeting_code":"ITA","location":"Monza","country_key":13,"country_code":"ITA","country_name":"Italy","meeting_name":"Italian Grand Prix","meeting_official_name":"FORMULA 1 PIRELLI GRAN PREMIO D'ITALIA 2025","gmt_offset":"02:00:00","date_start":"2025-09-05T11:30:00+00:00","year":2025},
    {"meeting_key":1282,"circuit_key":152,"circuit_short_name":"Baku","meeting_code":"AZE","location":"Baku","country_key":23,"country_code":"AZE","country_name":"Azerbaijan","meeting_name":"Azerbaijan Grand Prix","meeting_official_name":"FORMULA 1 AZERBAIJAN GRAND PRIX 2025","gmt_offset":"04:00:00","date_start":"2025-09-19T09:30:00+00:00","year":2025},
    {"meeting_key":1283,"circuit_key":62,"circuit_short_name":"Singapore","meeting_code":"SGP","location":"Singapore","country_key":24,"country_code":"SGP","country_name":"Singapore","meeting_name":"Singapore Grand Prix","meeting_official_name":"FORMULA 1 SINGAPORE GRAND PRIX 2025","gmt_offset":"08:00:00","date_start":"2025-10-03T09:30:00+00:00","year":2025},
    {"meeting_key":1284,"circuit_key":4,"circuit_short_name":"Austin","meeting_code":"USA","location":"Austin","country_key":19,"country_code":"USA","country_name":"United States","meeting_name":"United States Grand Prix","meeting_official_name":"FORMULA 1 UNITED STATES GRAND PRIX 2025","gmt_offset":"-05:00:00","date_start":"2025-10-17T18:30:00+00:00","year":2025},
    {"meeting_key":1285,"circuit_key":32,"circuit_short_name":"Mexico City","meeting_code":"MEX","location":"Mexico City","country_key":25,"country_code":"MEX","country_name":"Mexico","meeting_name":"Mexican Grand Prix","meeting_official_name":"FORMULA 1 MEXICAN GRAND PRIX 2025","gmt_offset":"-06:00:00","date_start":"2025-10-24T19:30:00+00:00","year":2025},
    {"meeting_key":1286,"circuit_key":14,"circuit_short_name":"Sao Paulo","meeting_code":"BRA","location":"Sao Paulo","country_key":26,"country_code":"BRA","country_name":"Brazil","meeting_name":"Sao Paulo Grand Prix","meeting_official_name":"FORMULA 1 SAO PAULO GRAND PRIX 2025","gmt_offset":"-03:00:00","date_start":"2025-11-07T14:00:00+00:00","year":2025},
    {"meeting_key":1287,"circuit_key":153,"circuit_short_name":"Las Vegas","meeting_code":"USA","location":"Las Vegas","country_key":19,"country_code":"USA","country_name":"United States","meeting_name":"Las Vegas Grand Prix","meeting_official_name":"FORMULA 1 LAS VEGAS GRAND PRIX 2025","gmt_offset":"-08:00:00","date_start":"2025-11-20T06:00:00+00:00","year":2025},
    {"meeting_key":1288,"circuit_key":154,"circuit_short_name":"Lusail","meeting_code":"QAT","location":"Lusail","country_key":27,"country_code":"QAT","country_name":"Qatar","meeting_name":"Qatar Grand Prix","meeting_official_name":"FORMULA 1 QATAR GRAND PRIX 2025","gmt_offset":"03:00:00","date_start":"2025-11-28T13:30:00+00:00","year":2025},
    {"meeting_key":1289,"circuit_key":24,"circuit_short_name":"Abu Dhabi","meeting_code":"UAE","location":"Abu Dhabi","country_key":28,"country_code":"UAE","country_name":"United Arab Emirates","meeting_name":"Abu Dhabi Grand Prix","meeting_official_name":"FORMULA 1 ABU DHABI GRAND PRIX 2025","gmt_offset":"04:00:00","date_start":"2025-12-05T09:30:00+00:00","year":2025}
]

hardcoded_sessions = [
    {"meeting_key":1253,"session_key":9683,"location":"Sakhir","date_start":"2025-02-26T07:00:00+00:00","date_end":"2025-02-26T16:00:00+00:00","session_type":"Practice","session_name":"Day 1","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1253,"session_key":9684,"location":"Sakhir","date_start":"2025-02-27T07:00:00+00:00","date_end":"2025-02-27T16:00:00+00:00","session_type":"Practice","session_name":"Day 2","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1253,"session_key":9685,"location":"Sakhir","date_start":"2025-02-28T07:00:00+00:00","date_end":"2025-02-28T16:00:00+00:00","session_type":"Practice","session_name":"Day 3","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1254,"session_key":9686,"location":"Melbourne","date_start":"2025-03-14T01:30:00+00:00","date_end":"2025-03-14T02:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":5,"country_code":"AUS","country_name":"Australia","circuit_key":10,"circuit_short_name":"Melbourne","gmt_offset":"11:00:00","year":2025},
    {"meeting_key":1254,"session_key":9687,"location":"Melbourne","date_start":"2025-03-14T05:00:00+00:00","date_end":"2025-03-14T06:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":5,"country_code":"AUS","country_name":"Australia","circuit_key":10,"circuit_short_name":"Melbourne","gmt_offset":"11:00:00","year":2025},
    {"meeting_key":1254,"session_key":9688,"location":"Melbourne","date_start":"2025-03-15T01:30:00+00:00","date_end":"2025-03-15T02:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":5,"country_code":"AUS","country_name":"Australia","circuit_key":10,"circuit_short_name":"Melbourne","gmt_offset":"11:00:00","year":2025},
    {"meeting_key":1254,"session_key":9689,"location":"Melbourne","date_start":"2025-03-15T05:00:00+00:00","date_end":"2025-03-15T06:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":5,"country_code":"AUS","country_name":"Australia","circuit_key":10,"circuit_short_name":"Melbourne","gmt_offset":"11:00:00","year":2025},
    {"meeting_key":1254,"session_key":9693,"location":"Melbourne","date_start":"2025-03-16T04:00:00+00:00","date_end":"2025-03-16T06:00:00+00:00","session_type":"Race","session_name":"Race","country_key":5,"country_code":"AUS","country_name":"Australia","circuit_key":10,"circuit_short_name":"Melbourne","gmt_offset":"11:00:00","year":2025},
    {"meeting_key":1255,"session_key":9988,"location":"Shanghai","date_start":"2025-03-21T03:30:00+00:00","date_end":"2025-03-21T04:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":53,"country_code":"CHN","country_name":"China","circuit_key":49,"circuit_short_name":"Shanghai","gmt_offset":"08:00:00","year":2025},
    {"meeting_key":1255,"session_key":9989,"location":"Shanghai","date_start":"2025-03-21T07:30:00+00:00","date_end":"2025-03-21T08:14:00+00:00","session_type":"Qualifying","session_name":"Sprint Qualifying","country_key":53,"country_code":"CHN","country_name":"China","circuit_key":49,"circuit_short_name":"Shanghai","gmt_offset":"08:00:00","year":2025},
    {"meeting_key":1255,"session_key":9993,"location":"Shanghai","date_start":"2025-03-22T03:00:00+00:00","date_end":"2025-03-22T04:00:00+00:00","session_type":"Race","session_name":"Sprint","country_key":53,"country_code":"CHN","country_name":"China","circuit_key":49,"circuit_short_name":"Shanghai","gmt_offset":"08:00:00","year":2025},
    {"meeting_key":1255,"session_key":9994,"location":"Shanghai","date_start":"2025-03-22T07:00:00+00:00","date_end":"2025-03-22T08:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":53,"country_code":"CHN","country_name":"China","circuit_key":49,"circuit_short_name":"Shanghai","gmt_offset":"08:00:00","year":2025},
    {"meeting_key":1255,"session_key":9998,"location":"Shanghai","date_start":"2025-03-23T07:00:00+00:00","date_end":"2025-03-23T09:00:00+00:00","session_type":"Race","session_name":"Race","country_key":53,"country_code":"CHN","country_name":"China","circuit_key":49,"circuit_short_name":"Shanghai","gmt_offset":"08:00:00","year":2025},
    {"meeting_key":1256,"session_key":9999,"location":"Suzuka","date_start":"2025-04-04T02:30:00+00:00","date_end":"2025-04-04T03:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":4,"country_code":"JPN","country_name":"Japan","circuit_key":46,"circuit_short_name":"Suzuka","gmt_offset":"09:00:00","year":2025},
    {"meeting_key":1256,"session_key":10000,"location":"Suzuka","date_start":"2025-04-04T06:00:00+00:00","date_end":"2025-04-04T07:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":4,"country_code":"JPN","country_name":"Japan","circuit_key":46,"circuit_short_name":"Suzuka","gmt_offset":"09:00:00","year":2025},
    {"meeting_key":1256,"session_key":10001,"location":"Suzuka","date_start":"2025-04-05T02:30:00+00:00","date_end":"2025-04-05T03:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":4,"country_code":"JPN","country_name":"Japan","circuit_key":46,"circuit_short_name":"Suzuka","gmt_offset":"09:00:00","year":2025},
    {"meeting_key":1256,"session_key":10002,"location":"Suzuka","date_start":"2025-04-05T06:00:00+00:00","date_end":"2025-04-05T07:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":4,"country_code":"JPN","country_name":"Japan","circuit_key":46,"circuit_short_name":"Suzuka","gmt_offset":"09:00:00","year":2025},
    {"meeting_key":1256,"session_key":10006,"location":"Suzuka","date_start":"2025-04-06T05:00:00+00:00","date_end":"2025-04-06T07:00:00+00:00","session_type":"Race","session_name":"Race","country_key":4,"country_code":"JPN","country_name":"Japan","circuit_key":46,"circuit_short_name":"Suzuka","gmt_offset":"09:00:00","year":2025},
    {"meeting_key":1257,"session_key":10007,"location":"Sakhir","date_start":"2025-04-11T11:30:00+00:00","date_end":"2025-04-11T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1257,"session_key":10008,"location":"Sakhir","date_start":"2025-04-11T15:00:00+00:00","date_end":"2025-04-11T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1257,"session_key":10009,"location":"Sakhir","date_start":"2025-04-12T12:30:00+00:00","date_end":"2025-04-12T13:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1257,"session_key":10010,"location":"Sakhir","date_start":"2025-04-12T16:00:00+00:00","date_end":"2025-04-12T17:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1257,"session_key":10014,"location":"Sakhir","date_start":"2025-04-13T15:00:00+00:00","date_end":"2025-04-13T17:00:00+00:00","session_type":"Race","session_name":"Race","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1258,"session_key":10015,"location":"Jeddah","date_start":"2025-04-18T13:30:00+00:00","date_end":"2025-04-18T14:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","circuit_key":149,"circuit_short_name":"Jeddah","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1258,"session_key":10016,"location":"Jeddah","date_start":"2025-04-18T17:00:00+00:00","date_end":"2025-04-18T18:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","circuit_key":149,"circuit_short_name":"Jeddah","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1258,"session_key":10017,"location":"Jeddah","date_start":"2025-04-19T13:30:00+00:00","date_end":"2025-04-19T14:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","circuit_key":149,"circuit_short_name":"Jeddah","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1258,"session_key":10018,"location":"Jeddah","date_start":"2025-04-19T17:00:00+00:00","date_end":"2025-04-19T18:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","circuit_key":149,"circuit_short_name":"Jeddah","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1258,"session_key":10022,"location":"Jeddah","date_start":"2025-04-20T17:00:00+00:00","date_end":"2025-04-20T19:00:00+00:00","session_type":"Race","session_name":"Race","country_key":153,"country_code":"KSA","country_name":"Saudi Arabia","circuit_key":149,"circuit_short_name":"Jeddah","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1259,"session_key":10023,"location":"Miami","date_start":"2025-05-02T16:30:00+00:00","date_end":"2025-05-02T17:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":19,"country_code":"USA","country_name":"United States","circuit_key":151,"circuit_short_name":"Miami","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1259,"session_key":10024,"location":"Miami","date_start":"2025-05-02T20:30:00+00:00","date_end":"2025-05-02T21:14:00+00:00","session_type":"Qualifying","session_name":"Sprint Qualifying","country_key":19,"country_code":"USA","country_name":"United States","circuit_key":151,"circuit_short_name":"Miami","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1259,"session_key":10028,"location":"Miami","date_start":"2025-05-03T16:00:00+00:00","date_end":"2025-05-03T17:00:00+00:00","session_type":"Race","session_name":"Sprint","country_key":19,"country_code":"USA","country_name":"United States","circuit_key":151,"circuit_short_name":"Miami","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1259,"session_key":10029,"location":"Miami","date_start":"2025-05-03T20:00:00+00:00","date_end":"2025-05-03T21:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":19,"country_code":"USA","country_name":"United States","circuit_key":151,"circuit_short_name":"Miami","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1259,"session_key":10033,"location":"Miami","date_start":"2025-05-04T20:00:00+00:00","date_end":"2025-05-04T22:00:00+00:00","session_type":"Race","session_name":"Race","country_key":19,"country_code":"USA","country_name":"United States","circuit_key":151,"circuit_short_name":"Miami","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1260,"session_key":9980,"location":"Imola","date_start":"2025-05-16T11:30:00+00:00","date_end":"2025-05-16T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":13,"country_code":"ITA","country_name":"Italy","circuit_key":6,"circuit_short_name":"Imola","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1260,"session_key":9981,"location":"Imola","date_start":"2025-05-16T15:00:00+00:00","date_end":"2025-05-16T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":13,"country_code":"ITA","country_name":"Italy","circuit_key":6,"circuit_short_name":"Imola","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1260,"session_key":9982,"location":"Imola","date_start":"2025-05-17T10:30:00+00:00","date_end":"2025-05-17T11:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":13,"country_code":"ITA","country_name":"Italy","circuit_key":6,"circuit_short_name":"Imola","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1260,"session_key":9983,"location":"Imola","date_start":"2025-05-17T14:00:00+00:00","date_end":"2025-05-17T15:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":13,"country_code":"ITA","country_name":"Italy","circuit_key":6,"circuit_short_name":"Imola","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1260,"session_key":9987,"location":"Imola","date_start":"2025-05-18T13:00:00+00:00","date_end":"2025-05-18T15:00:00+00:00","session_type":"Race","session_name":"Race","country_key":13,"country_code":"ITA","country_name":"Italy","circuit_key":6,"circuit_short_name":"Imola","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1261,"session_key":9972,"location":"Monaco","date_start":"2025-05-23T11:30:00+00:00","date_end":"2025-05-23T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":114,"country_code":"MON","country_name":"Monaco","circuit_key":22,"circuit_short_name":"Monte Carlo","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1261,"session_key":9973,"location":"Monaco","date_start":"2025-05-23T15:00:00+00:00","date_end":"2025-05-23T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":114,"country_code":"MON","country_name":"Monaco","circuit_key":22,"circuit_short_name":"Monte Carlo","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1261,"session_key":9974,"location":"Monaco","date_start":"2025-05-24T10:30:00+00:00","date_end":"2025-05-24T11:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":114,"country_code":"MON","country_name":"Monaco","circuit_key":22,"circuit_short_name":"Monte Carlo","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1261,"session_key":9975,"location":"Monaco","date_start":"2025-05-24T14:00:00+00:00","date_end":"2025-05-24T15:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":114,"country_code":"MON","country_name":"Monaco","circuit_key":22,"circuit_short_name":"Monte Carlo","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1261,"session_key":9979,"location":"Monaco","date_start":"2025-05-25T13:00:00+00:00","date_end":"2025-05-25T15:00:00+00:00","session_type":"Race","session_name":"Race","country_key":114,"country_code":"MON","country_name":"Monaco","circuit_key":22,"circuit_short_name":"Monte Carlo","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1262,"session_key":9964,"location":"Barcelona","date_start":"2025-05-30T11:30:00+00:00","date_end":"2025-05-30T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":1,"country_code":"ESP","country_name":"Spain","circuit_key":15,"circuit_short_name":"Catalunya","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1262,"session_key":9965,"location":"Barcelona","date_start":"2025-05-30T15:00:00+00:00","date_end":"2025-05-30T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":1,"country_code":"ESP","country_name":"Spain","circuit_key":15,"circuit_short_name":"Catalunya","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1262,"session_key":9966,"location":"Barcelona","date_start":"2025-05-31T10:30:00+00:00","date_end":"2025-05-31T11:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":1,"country_code":"ESP","country_name":"Spain","circuit_key":15,"circuit_short_name":"Catalunya","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1262,"session_key":9967,"location":"Barcelona","date_start":"2025-05-31T14:00:00+00:00","date_end":"2025-05-31T15:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":1,"country_code":"ESP","country_name":"Spain","circuit_key":15,"circuit_short_name":"Catalunya","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1262,"session_key":9971,"location":"Barcelona","date_start":"2025-06-01T13:00:00+00:00","date_end":"2025-06-01T15:00:00+00:00","session_type":"Race","session_name":"Race","country_key":1,"country_code":"ESP","country_name":"Spain","circuit_key":15,"circuit_short_name":"Catalunya","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1263,"session_key":9956,"location":"Montréal","date_start":"2025-06-13T17:30:00+00:00","date_end":"2025-06-13T18:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":46,"country_code":"CAN","country_name":"Canada","circuit_key":23,"circuit_short_name":"Montreal","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1263,"session_key":9957,"location":"Montréal","date_start":"2025-06-13T21:00:00+00:00","date_end":"2025-06-13T22:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":46,"country_code":"CAN","country_name":"Canada","circuit_key":23,"circuit_short_name":"Montreal","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1263,"session_key":9958,"location":"Montréal","date_start":"2025-06-14T16:30:00+00:00","date_end":"2025-06-14T17:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":46,"country_code":"CAN","country_name":"Canada","circuit_key":23,"circuit_short_name":"Montreal","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1263,"session_key":9959,"location":"Montréal","date_start":"2025-06-14T20:00:00+00:00","date_end":"2025-06-14T21:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":46,"country_code":"CAN","country_name":"Canada","circuit_key":23,"circuit_short_name":"Montreal","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1263,"session_key":9963,"location":"Montréal","date_start":"2025-06-15T18:00:00+00:00","date_end":"2025-06-15T20:00:00+00:00","session_type":"Race","session_name":"Race","country_key":46,"country_code":"CAN","country_name":"Canada","circuit_key":23,"circuit_short_name":"Montreal","gmt_offset":"-04:00:00","year":2025},
    {"meeting_key":1264,"session_key":9948,"location":"Spielberg","date_start":"2025-06-27T11:30:00+00:00","date_end":"2025-06-27T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":17,"country_code":"AUT","country_name":"Austria","circuit_key":19,"circuit_short_name":"Spielberg","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1264,"session_key":9949,"location":"Spielberg","date_start":"2025-06-27T15:00:00+00:00","date_end":"2025-06-27T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":17,"country_code":"AUT","country_name":"Austria","circuit_key":19,"circuit_short_name":"Spielberg","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1264,"session_key":9950,"location":"Spielberg","date_start":"2025-06-28T10:30:00+00:00","date_end":"2025-06-28T11:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":17,"country_code":"AUT","country_name":"Austria","circuit_key":19,"circuit_short_name":"Spielberg","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1264,"session_key":9951,"location":"Spielberg","date_start":"2025-06-28T14:00:00+00:00","date_end":"2025-06-28T15:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":17,"country_code":"AUT","country_name":"Austria","circuit_key":19,"circuit_short_name":"Spielberg","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1264,"session_key":9955,"location":"Spielberg","date_start":"2025-06-29T13:00:00+00:00","date_end":"2025-06-29T15:00:00+00:00","session_type":"Race","session_name":"Race","country_key":17,"country_code":"AUT","country_name":"Austria","circuit_key":19,"circuit_short_name":"Spielberg","gmt_offset":"02:00:00","year":2025},
    {"meeting_key":1277,"session_key":9940,"location":"Silverstone","date_start":"2025-07-04T11:30:00+00:00","date_end":"2025-07-04T12:30:00+00:00","session_type":"Practice","session_name":"Practice 1","country_key":2,"country_code":"GBR","country_name":"United Kingdom","circuit_key":2,"circuit_short_name":"Silverstone","gmt_offset":"01:00:00","year":2025},
    {"meeting_key":1277,"session_key":9941,"location":"Silverstone","date_start":"2025-07-04T15:00:00+00:00","date_end":"2025-07-04T16:00:00+00:00","session_type":"Practice","session_name":"Practice 2","country_key":2,"country_code":"GBR","country_name":"United Kingdom","circuit_key":2,"circuit_short_name":"Silverstone","gmt_offset":"01:00:00","year":2025},
    {"meeting_key":1277,"session_key":9942,"location":"Silverstone","date_start":"2025-07-05T10:30:00+00:00","date_end":"2025-07-05T11:30:00+00:00","session_type":"Practice","session_name":"Practice 3","country_key":2,"country_code":"GBR","country_name":"United Kingdom","circuit_key":2,"circuit_short_name":"Silverstone","gmt_offset":"01:00:00","year":2025},
    {"meeting_key":1277,"session_key":9943,"location":"Silverstone","date_start":"2025-07-05T14:00:00+00:00","date_end":"2025-07-05T15:00:00+00:00","session_type":"Qualifying","session_name":"Qualifying","country_key":2,"country_code":"GBR","country_name":"United Kingdom","circuit_key":2,"circuit_short_name":"Silverstone","gmt_offset":"01:00:00","year":2025},
    {"meeting_key":1277,"session_key":9947,"location":"Silverstone","date_start":"2025-07-06T14:00:00+00:00","date_end":"2025-07-06T16:00:00+00:00","session_type":"Race","session_name":"Race","country_key":2,"country_code":"GBR","country_name":"United Kingdom","circuit_key":2,"circuit_short_name":"Silverstone","gmt_offset":"01:00:00","year":2025}
]

# Fetch SpaceX launch data
def fetch_launches(first_load=False):
    logger.info("Fetching SpaceX launch data")
    current_time = datetime.now(pytz.UTC)
    current_date_str = current_time.strftime('%Y-%m-%d')
    current_year = current_time.year

    # Load previous launches cache
    previous_cache = load_cache_from_file(CACHE_FILE_PREVIOUS)
    if not first_load and previous_cache and (current_time - previous_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL:
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
                    'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch[
                        'mission'] else 'Unknown',
                    'pad': launch['pad']['name'],
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')
                }
                for launch in data['results']
            ]
            save_cache_to_file(CACHE_FILE_PREVIOUS, previous_launches, current_time)
            logger.info("Successfully fetched and saved previous launches")
            time.sleep(1)  # Avoid rate limiting
        except Exception as e:
            logger.error(f"LL2 API error: {e}")
            previous_launches = [
                {'mission': 'Starship Flight 7', 'date': '2025-01-15', 'time': '12:00:00',
                 'net': '2025-01-15T12:00:00Z', 'status': 'Success', 'rocket': 'Starship', 'orbit': 'Suborbital',
                 'pad': 'Starbase', 'video_url': 'https://www.youtube.com/embed/Pn6e1O5bEyA'},
                {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z',
                 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A',
                 'video_url': ''},
            ]

    # Load upcoming launches cache
    upcoming_cache = load_cache_from_file(CACHE_FILE_UPCOMING)
    if not first_load and upcoming_cache and (current_time - upcoming_cache['timestamp']).total_seconds() < CACHE_REFRESH_INTERVAL:
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
                    'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch[
                        'mission'] else 'Unknown',
                    'pad': launch['pad']['name'],
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')
                }
                for launch in data['results']
            ]
            save_cache_to_file(CACHE_FILE_UPCOMING, upcoming_launches, current_time)
            logger.info("Successfully fetched and saved upcoming launches")
            time.sleep(1)  # Avoid rate limiting
        except Exception as e:
            logger.error(f"LL2 API error: {e}")
            upcoming_launches = [
                {'mission': 'Transporter-14', 'date': '2025-06-25', 'time': '06:54:00', 'net': '2025-06-25T06:54:00Z',
                 'status': 'Go for Launch', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40',
                 'video_url': ''},
                {'mission': 'Axiom Mission 4', 'date': '2025-06-28', 'time': 'TBD', 'net': '2025-06-28T00:00:00Z',
                 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
            ]
    return {'previous': previous_launches, 'upcoming': upcoming_launches}


# Fetch F1 data
def fetch_f1_data():
    logger.info("Fetching F1 data")
    global f1_cache
    if f1_cache:
        return f1_cache
    try:
        meetings = hardcoded_f1_schedule
        driver_standings = []
        constructor_standings = []
        for meeting in meetings:
            meeting['sessions'] = [s for s in hardcoded_sessions if s['meeting_key'] == meeting['meeting_key']]
            race_sessions = [s for s in meeting['sessions'] if s['session_name'] == 'Race']
            if race_sessions:
                session_key = race_sessions[0]['session_key']
                results_url = f"https://api.openf1.org/v1/results?session_key={session_key}&position<=20"
                response = requests.get(results_url, timeout=5)
                response.raise_for_status()
                results = response.json()
                points_map = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
                for result in results:
                    position = result['position']
                    driver_number = result['driver_number']
                    drivers_url = f"https://api.openf1.org/v1/drivers?session_key={session_key}&driver_number={driver_number}"
                    drivers_resp = requests.get(drivers_url, timeout=5)
                    drivers_resp.raise_for_status()
                    driver = drivers_resp.json()[0]
                    for ds in driver_standings:
                        if ds['Driver']['givenName'] == driver.get('first_name') and ds['Driver'][
                            'familyName'] == driver.get('last_name'):
                            ds['points'] += points_map.get(position, 0)
                            break
                    else:
                        driver_standings.append(
                            {'position': len(driver_standings) + 1, 'points': points_map.get(position, 0),
                             'Driver': {'givenName': driver.get('first_name', ''),
                                        'familyName': driver.get('last_name', '')}})
                    for cs in constructor_standings:
                        if cs['Constructor']['name'] == driver.get('team_name'):
                            cs['points'] += points_map.get(position, 0)
                            break
                    else:
                        constructor_standings.append(
                            {'position': len(constructor_standings) + 1, 'points': points_map.get(position, 0),
                             'Constructor': {'name': driver.get('team_name', '')}})
                time.sleep(1)  # Avoid rate limiting
        driver_standings.sort(key=lambda x: x['points'], reverse=True)
        for i, ds in enumerate(driver_standings):
            ds['position'] = i + 1
        constructor_standings.sort(key=lambda x: x['points'], reverse=True)
        for i, cs in enumerate(constructor_standings):
            cs['position'] = i + 1
        f1_cache = {'schedule': meetings, 'driver_standings': driver_standings,
                    'constructor_standings': constructor_standings}
        logger.info("Successfully fetched F1 data")
        return f1_cache
    except Exception as e:
        logger.error(f"OpenF1 API error: {e}")
        f1_cache = {
            'schedule': hardcoded_f1_schedule,
            'driver_standings': [
                {'position': 1, 'points': 575, 'Driver': {'givenName': 'Max', 'familyName': 'Verstappen'}},
                {'position': 2, 'points': 285, 'Driver': {'givenName': 'Sergio', 'familyName': 'Perez'}},
            ],
            'constructor_standings': [
                {'position': 1, 'points': 860, 'Constructor': {'name': 'Red Bull'}},
                {'position': 2, 'points': 409, 'Constructor': {'name': 'Mercedes'}},
            ]
        }
        for meeting in f1_cache['schedule']:
            meeting['sessions'] = [s for s in hardcoded_sessions if s['meeting_key'] == meeting['meeting_key']]
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


# Custom Segmented Control Widget
class SegmentedControl(QWidget):
    def __init__(self, options, default, callback, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.buttons = []
        self.callback = callback
        for opt in options:
            btn = QPushButton(opt['label'])
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2a2e2e; color: #ffffff; font-family: 'D-DIN', sans-serif;
                    font-size: 10px; padding: 4px; border-radius: 4px;
                }
                QPushButton:checked {
                    background-color: #4a4e4e; color: #ffffff;
                }
                QPushButton:hover {
                    background-color: #3a3e3e;
                }
            """)
            btn.clicked.connect(lambda checked, value=opt['value']: self.set_value(value))
            self.buttons.append((btn, opt['value']))
            self.layout.addWidget(btn)
        self.set_value(default)
        logger.info(f"Initialized SegmentedControl with default: {default}")

    def set_value(self, value):
        for btn, val in self.buttons:
            btn.setChecked(val == value)
        self.callback(value)


# Custom Launch/Race Card
class EventCard(QWidget):
    def __init__(self, event, event_type, tz, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("""
            QWidget {
                background-color: #2a2e2e; color: #ffffff; font-family: 'D-DIN', sans-serif;
                border-radius: 6px; padding: 10px;
            }
            QLabel { font-size: 12px; }
        """)
        title = QLabel(event['mission'] if event_type in ['upcoming', 'previous'] else event['meeting_name'])
        title.setStyleSheet("font-size: 14px; color: #ffffff;")
        layout.addWidget(title)

        if event_type in ['upcoming', 'previous']:
            rocket_label = QLabel(f"🚀 Rocket: {event['rocket']}")
            layout.addWidget(rocket_label)
            orbit_label = QLabel(f"🌍 Orbit: {event['orbit']}")
            layout.addWidget(orbit_label)
            pad_label = QLabel(f"📍 Pad: {event['pad']}")
            layout.addWidget(pad_label)
            layout.addWidget(QLabel(f"Date: {event['date']} {event['time']} UTC"))
            layout.addWidget(QLabel(
                f"{str(tz).split('/')[-1]}: {parse(event['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if event['time'] != 'TBD' else 'TBD'}"))
            status = QLabel(f"Status: {event['status']}")
            status.setStyleSheet(
                f"color: {'#00ff00' if event['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else '#ff0000'};")
            layout.addWidget(status)
        else:
            circuit_label = QLabel(f"🏎️ Circuit: {event['circuit_short_name']}")
            layout.addWidget(circuit_label)
            layout.addWidget(QLabel(f"Date: {parse(event['date_start']).astimezone(tz).strftime('%Y-%m-%d')}"))
            sessions = "\n".join(f"{s['session_name']}: {s['date_start']}" for s in
                                 sorted(event.get('sessions', []), key=lambda x: parse(x['date_start'])))
            layout.addWidget(QLabel(sessions if sessions else "No session info"))
        # logger.info(f"Created EventCard for {event_type}: {event.get('mission', event.get('meeting_name'))}")


# Main application
class SpaceXDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing SpaceXDashboard")
        self.setWindowTitle("SpaceX/F1 Dashboard")
        self.setGeometry(0, 0, 1480, 320)  # Match Waveshare 320x1480 rotated display
        self.setStyleSheet("""
            QMainWindow { background-color: #1c2526; }
            QLabel { color: #ffffff; font-family: 'D-DIN', sans-serif; }
            QListWidget { background-color: #2a2e2e; color: #ffffff; font-family: 'D-DIN', sans-serif; font-size: 12px; border: none; }
            QChartView { background-color: #2a2e2e; }
        """)
        self.load_fonts()
        # Initialize mode and weather_data before UI to avoid AttributeError
        self.mode = 'spacex'
        self.event_type = 'upcoming'
        self.weather_data = self.initialize_weather()
        # Fetch launch data at startup
        self.launch_data = fetch_launches(first_load=True)
        self.init_ui()
        # Set up timers for updates (replaces threads)
        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(300000)  # 5 minutes in ms
        self.launch_timer = QTimer(self)
        self.launch_timer.timeout.connect(self.update_launches_periodic)
        self.launch_timer.start(CACHE_REFRESH_INTERVAL * 1000)  # In ms
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)
        logger.info("Timers initialized")

    def closeEvent(self, event):
        # Stop timers to prevent warnings on exit
        self.weather_timer.stop()
        self.launch_timer.stop()
        self.time_timer.stop()
        self.countdown_timer.stop()
        super().closeEvent(event)

    def load_fonts(self):
        logger.info("Loading fonts")
        font_db = QFontDatabase()
        font_path = "/app/assets/D-DIN.ttf"  # Absolute path for Banana Pi
        if not os.path.exists(font_path):
            logger.error(f"Font file not found: {font_path}, falling back to Arial")
            self.setFont(QFont("Arial", 12))
        else:
            font_id = font_db.addApplicationFont(font_path)
            if font_id == -1:
                logger.error(f"Failed to load font: {font_path}, falling back to Arial")
                self.setFont(QFont("Arial", 12))
            else:
                self.setFont(QFont("D-DIN", 12))
                logger.info(f"Successfully loaded font: {font_path}")

    def init_ui(self):
        logger.info("Initializing UI")
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(5)
        self.column1 = QFrame()
        self.column2 = QFrame()
        self.column3 = QFrame()
        self.column4 = QFrame()
        for col in [self.column1, self.column2, self.column3, self.column4]:
            col.setFrameShape(QFrame.StyledPanel)
            col.setFixedHeight(int(0.85 * 320))  # 85% of 320px height
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col.setStyleSheet("background-color: #2a2e2e; border-radius: 8px;")
            columns_layout.addWidget(col, stretch=1)  # Equal width
        main_layout.addLayout(columns_layout)

        # Bottom bar (transparent container)
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(30)
        bottom_bar_layout = QHBoxLayout(bottom_bar)
        bottom_bar_layout.setContentsMargins(10, 0, 10, 0)
        bottom_bar.setStyleSheet("background-color: transparent;")

        # Left pill (time and weather)
        left_pill = QFrame()
        left_pill_layout = QHBoxLayout(left_pill)
        left_pill_layout.setContentsMargins(5, 0, 5, 0)
        left_pill.setStyleSheet("background-color: #2a2e2e; border-radius: 20px;")
        self.time_label = QLabel("00:00:00")
        self.weather_label = QLabel("")
        left_pill_layout.addWidget(self.time_label)
        left_pill_layout.addWidget(self.weather_label)
        bottom_bar_layout.addWidget(left_pill)

        # Logo
        self.mode_button = QPushButton()
        logo_path = "/app/assets/spacex-logo.png"  # Absolute path for Banana Pi
        if not os.path.exists(logo_path):
            logger.error(f"Logo file not found: {logo_path}")
        self.mode_button.setIcon(QIcon(logo_path))
        self.mode_button.setIconSize(QSize(80, 30))
        self.mode_button.clicked.connect(self.toggle_mode)
        self.mode_button.setFlat(True)
        bottom_bar_layout.addStretch()
        bottom_bar_layout.addWidget(self.mode_button)
        bottom_bar_layout.addStretch()

        # Right pill (countdown, location, theme)
        right_pill = QFrame()
        right_pill_layout = QHBoxLayout(right_pill)
        right_pill_layout.setContentsMargins(5, 0, 5, 0)
        right_pill.setStyleSheet("background-color: #2a2e2e; border-radius: 20px;")
        self.countdown_label = QLabel("No upcoming events")
        self.location_control = SegmentedControl(
            [{'label': loc, 'value': loc} for loc in ['Starbase', 'Vandy', 'Cape', 'Hawthorne']],
            'Starbase',
            self.update_weather_display
        )
        self.theme_control = SegmentedControl(
            [{'label': 'Light', 'value': 'light'}, {'label': 'Dark', 'value': 'dark'}],
            'dark',
            self.update_theme
        )
        right_pill_layout.addWidget(self.countdown_label)
        right_pill_layout.addWidget(self.location_control)
        right_pill_layout.addWidget(self.theme_control)
        bottom_bar_layout.addWidget(right_pill)

        main_layout.addWidget(bottom_bar)

        # Initialize content
        self.update_columns()
        logger.info("UI initialization complete")

    def update_theme(self, theme):
        logger.info(f"Updating theme to {theme}")
        if theme == 'light':
            self.setStyleSheet("""
                QMainWindow { background-color: #ffffff; }
                QLabel { color: #000000; font-family: 'D-DIN', sans-serif; }
                QListWidget { background-color: #f0f0f0; color: #000000; font-family: 'D-DIN', sans-serif; font-size: 12px; border: none; }
                QChartView { background-color: #f0f0f0; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #1c2526; }
                QLabel { color: #ffffff; font-family: 'D-DIN', sans-serif; }
                QListWidget { background-color: #2a2e2e; color: #ffffff; font-family: 'D-DIN', sans-serif; font-size: 12px; border: none; }
                QChartView { background-color: #2a2e2e; }
            """)

    def toggle_mode(self):
        self.mode = 'f1' if self.mode == 'spacex' else 'spacex'
        logo_path = f"/app/assets/{'f1' if self.mode == 'f1' else 'spacex'}-logo.png"
        if not os.path.exists(logo_path):
            logger.error(f"Logo file not found: {logo_path}")
        self.mode_button.setIcon(QIcon(logo_path))
        self.event_type = 'upcoming'
        self.update_columns()
        logger.info(f"Toggled mode to {self.mode}")

    def update_time(self):
        tz = pytz.timezone(location_settings[self.location_control.buttons[0][1]]['timezone'])
        now = datetime.now(tz).strftime('%H:%M:%S')
        self.time_label.setText(now)
        self.countdown_label.setText(self.calculate_countdown())
        logger.debug(f"Updated time: {now}")

    def initialize_weather(self):
        logger.info("Initializing weather data")
        weather_data = {}
        for location, settings in location_settings.items():
            weather_data[location] = fetch_weather(settings['lat'], settings['lon'], location)
        return weather_data

    def update_weather(self):
        logger.info("Updating weather data via timer")
        self.weather_data = self.initialize_weather()
        self.update_weather_display(self.location_control.buttons[0][1])  # Assuming first button is current location

    def update_launches_periodic(self):
        logger.info("Updating launch data via timer")
        self.launch_data = fetch_launches(first_load=False)
        self.update_columns()

    def update_countdown(self):
        self.countdown_label.setText(self.calculate_countdown())
        logger.debug("Updated countdown")

    def update_weather_display(self, location):
        logger.info(f"Updating weather display for {location}")
        weather = self.weather_data.get(location, fetch_weather(location_settings[location]['lat'],
                                                                location_settings[location]['lon'], location))
        self.weather_label.setText(
            f"Wind {weather['wind_speed_kts']:.1f} kts | {weather['wind_speed_ms']:.1f} m/s, {weather['wind_direction']}° | "
            f"Temp {weather['temperature_f']:.1f}°F | {weather['temperature_c']:.1f}°C | Clouds {weather['cloud_cover']}%"
        )
        logger.info(f"Updated weather display for {location}")

    def calculate_countdown(self):
        if self.mode == 'spacex':
            next_launch = self.get_next_launch()
            if not next_launch:
                logger.info("No upcoming launches for countdown")
                return "No upcoming launches"
            launch_time = parse(next_launch['net']).replace(tzinfo=pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            if launch_time <= current_time:
                logger.info("Launch in progress")
                return "Launch in progress"
            delta = launch_time - current_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            countdown = f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
            logger.debug(f"Countdown: {countdown}")
            return countdown
        else:
            next_race = self.get_next_race()
            if not next_race:
                logger.info("No upcoming races for countdown")
                return "No upcoming races"
            race_time = parse(next_race['date_start']).replace(tzinfo=pytz.UTC)
            current_time = datetime.now(pytz.UTC)
            if race_time <= current_time:
                logger.info("Race in progress")
                return "Race in progress"
            delta = race_time - current_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            countdown = f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s to {next_race['meeting_name']}"
            logger.debug(f"Countdown: {countdown}")
            return countdown

    def get_next_launch(self):
        current_time = datetime.now(pytz.UTC)
        valid_launches = [l for l in self.launch_data['upcoming'] if
                          l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
        if valid_launches:
            next_launch = min(valid_launches, key=lambda x: parse(x['net']))
            # logger.info(f"Next launch: {next_launch['mission']}")
            return next_launch
        logger.info("No valid upcoming launches")
        return None

    def get_next_race(self):
        data = fetch_f1_data()
        races = data['schedule']
        current = datetime.now(pytz.UTC)
        upcoming = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC) > current]
        if upcoming:
            next_race = min(upcoming, key=lambda r: parse(r['date_start']))
            # logger.info(f"Next race: {next_race['meeting_name']}")
            return next_race
        logger.info("No upcoming races")
        return None

    def update_columns(self):
        logger.info(f"Updating columns for mode: {self.mode}")
        # Clear existing layouts
        for col in [self.column1, self.column2, self.column3, self.column4]:
            while col.layout().count():
                item = col.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        if self.mode == 'spacex':
            # Column 1: Launch Trends (clustered vertical bar chart)
            title = QLabel("Launch Trends")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            chart = QChart()
            chart.setBackgroundBrush(QColor(0, 0, 0, 0))
            chart.legend().hide()
            launches = self.launch_data['previous']
            df = pd.DataFrame(launches)
            df['date'] = pd.to_datetime(df['date'])  # Ensure date is datetime
            current_year = datetime.now(pytz.UTC).year
            df = df[df['date'].dt.year == current_year]
            rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
            df = df[df['rocket'].isin(rocket_types)]
            df['month'] = df['date'].dt.to_period('M').astype(str)  # Group by month
            df_grouped = df.groupby(['month', 'rocket']).size().reset_index(name='Launches')
            df_pivot = df_grouped.pivot(index='month', columns='rocket', values='Launches').fillna(0)
            for col in rocket_types:
                if col not in df_pivot.columns:
                    df_pivot[col] = 0
            bar_series = QBarSeries()
            colors = {'Starship': QColor(255, 87, 51), 'Falcon 9': QColor(51, 207, 255),
                      'Falcon Heavy': QColor(255, 193, 7)}
            for rocket in rocket_types:
                bar_set = QBarSet(rocket)
                bar_set.setColor(colors[rocket])
                for value in df_pivot[rocket]:
                    bar_set.append(value)
                bar_series.append(bar_set)
            chart.addSeries(bar_series)
            axis_x = QBarCategoryAxis()
            axis_x.setCategories(df_pivot.index.tolist())
            axis_x.setTitleText("Month")
            axis_x.setTitleFont(QFont("D-DIN", 10))
            axis_x.setLabelsFont(QFont("D-DIN", 10))
            axis_x.setLabelsColor(QColor(255, 255, 255))
            chart.setAxisX(axis_x, bar_series)
            axis_y = QValueAxis()
            axis_y.setTitleText("Launches")
            axis_y.setTitleFont(QFont("D-DIN", 10))
            axis_y.setLabelsFont(QFont("D-DIN", 10))
            axis_y.setLabelsColor(QColor(255, 255, 255))
            axis_y.setRange(0, df_pivot.max().max() + 5)
            chart.setAxisY(axis_y, bar_series)
            chart_view = QChartView(chart)
            chart_view.setRenderHint(QPainter.Antialiasing)
            self.column1.layout().addWidget(title)
            self.column1.layout().addWidget(chart_view)

            # Custom legend
            legend_layout = QHBoxLayout()
            legend_layout.setContentsMargins(0, 0, 0, 0)
            color_map = {'Starship': '#FF5733', 'Falcon 9': '#33CFFF', 'Falcon Heavy': '#FFC107'}
            totals = {rocket: int(df_pivot[rocket].sum()) if rocket in df_pivot.columns else 0 for rocket in color_map.keys()}
            for rocket in color_map.keys():
                legend_item = QHBoxLayout()
                square = QLabel("■")
                square.setStyleSheet(f"color: {color_map[rocket]}; font-size: 20px;")
                label = QLabel(f"{rocket}: {totals[rocket]}")
                label.setStyleSheet("font-size: 11px; color: #999999;")
                legend_item.addWidget(square)
                legend_item.addWidget(label)
                legend_layout.addLayout(legend_item)
            legend_widget = QWidget()
            legend_widget.setLayout(legend_layout)
            self.column1.layout().addWidget(legend_widget)
            logger.info("Added Launch Trends chart")

            # Column 2: Radar
            title = QLabel("Radar")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            radar_view = QWebEngineView()
            radar_view.settings().setAttribute(QWebEngineSettings.WebGLEnabled, True)
            radar_view.settings().setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            radar_view.setUrl(QUrl(radar_locations['Starbase'] + f"&rand={time.time()}"))
            self.column2.layout().addWidget(title)
            self.column2.layout().addWidget(radar_view)
            logger.info("Added Radar view")

            # Column 3: Launches
            title = QFrame()
            title_layout = QHBoxLayout(title)
            title_label = QLabel("Launches")
            title_label.setStyleSheet("font-size: 14px; text-transform: uppercase; color: #999999;")
            self.launch_list = QListWidget()
            self.event_type_control = SegmentedControl(
                [{'label': 'Upcoming', 'value': 'upcoming'}, {'label': 'Past', 'value': 'previous'}],
                'upcoming',
                self.update_launches
            )
            title_layout.addWidget(title_label)
            title_layout.addWidget(self.event_type_control)
            self.update_launches('upcoming')
            self.column3.layout().addWidget(title)
            self.column3.layout().addWidget(self.launch_list)
            logger.info("Added Launches list")

            # Column 4: Videos
            title = QLabel("Videos")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            video_view = QWebEngineView()
            video_view.settings().setAttribute(QWebEngineSettings.WebGLEnabled, True)
            video_view.settings().setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            video_view.setUrl(QUrl(
                'https://www.youtube.com/embed/videoseries?list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY&autoplay=1&mute=1&loop=1&controls=1&rel=0&enablejsapi=1'))
            self.column4.layout().addWidget(title)
            self.column4.layout().addWidget(video_view)
            logger.info("Added Videos view")
        else:
            # Column 1: Driver Standings
            title = QLabel("Driver Standings")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            list_widget = QListWidget()
            data = fetch_f1_data()
            ds = data['driver_standings']
            for d in ds:
                item = QListWidgetItem()
                card = QWidget()
                layout = QVBoxLayout(card)
                layout.addWidget(QLabel(f"Pos: {d['position']}"))
                layout.addWidget(QLabel(f"{d['Driver']['givenName']} {d['Driver']['familyName']}"))
                layout.addWidget(QLabel(f"Points: {d['points']}"))
                card.setStyleSheet("background-color: #2a2e2e; border-radius: 6px; padding: 10px; color: #ffffff;")
                item.setSizeHint(card.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, card)
            self.column1.layout().addWidget(title)
            self.column1.layout().addWidget(list_widget)
            logger.info("Added Driver Standings list")

            # Column 2: Race Calendar
            title = QLabel("Race Calendar")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            list_widget = QListWidget()
            races = data['schedule']
            for r in sorted(races, key=lambda x: parse(x['date_start'])):
                item = QListWidgetItem()
                card = QWidget()
                layout = QVBoxLayout(card)
                layout.addWidget(QLabel(r['meeting_name']))
                layout.addWidget(QLabel(f"Circuit: {r['circuit_short_name']}"))
                layout.addWidget(QLabel(f"Date: {parse(r['date_start']).strftime('%Y-%m-%d')}"))
                card.setStyleSheet("background-color: #2a2e2e; border-radius: 6px; padding: 10px; color: #ffffff;")
                item.setSizeHint(card.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, card)
            self.column2.layout().addWidget(title)
            self.column2.layout().addWidget(list_widget)
            logger.info("Added Race Calendar list")

            # Column 3: Races
            title = QFrame()
            title_layout = QHBoxLayout(title)
            title_label = QLabel("Races")
            title_label.setStyleSheet("font-size: 14px; text-transform: uppercase; color: #999999;")
            self.race_list = QListWidget()
            self.event_type_control = SegmentedControl(
                [{'label': 'Upcoming', 'value': 'upcoming'}, {'label': 'Past', 'value': 'previous'}],
                'upcoming',
                self.update_races
            )
            title_layout.addWidget(title_label)
            title_layout.addWidget(self.event_type_control)
            self.update_races('upcoming')
            self.column3.layout().addWidget(title)
            self.column3.layout().addWidget(self.race_list)
            logger.info("Added Races list")

            # Column 4: Next Race Map
            title = QLabel("Next Race Location")
            title.setStyleSheet(
                "font-size: 14px; text-transform: uppercase; color: #999999; border-bottom: 1px solid #999999; padding: 10px;")
            map_view = QWebEngineView()
            map_view.settings().setAttribute(QWebEngineSettings.WebGLEnabled, True)
            map_view.settings().setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            next_race = self.get_next_race()
            if next_race:
                coords = circuit_coords.get(next_race['circuit_short_name'], {'lat': 0, 'lon': 0})
                map_url = f"https://www.openstreetmap.org/export/embed.html?bbox={coords['lon'] - 0.01},{coords['lat'] - 0.01},{coords['lon'] + 0.01},{coords['lat'] + 0.01}&layer=mapnik&marker={coords['lat']},{coords['lon']}"
                map_view.setUrl(QUrl(map_url))
                # logger.info(f"Added Next Race Map for {next_race['circuit_short_name']}")
            else:
                map_view = QLabel("No upcoming races")
                logger.info("No upcoming races for map")
            self.column4.layout().addWidget(title)
            self.column4.layout().addWidget(map_view)

    def update_launches(self, event_type):
        logger.info(f"Updating launches for {event_type}")
        tz = pytz.timezone(location_settings[self.location_control.buttons[0][1]]['timezone'])
        launches = self.launch_data['upcoming' if event_type == 'upcoming' else 'previous']
        today = datetime.now(pytz.UTC).date()
        this_week_end = today + timedelta(days=7)
        last_week_start = today - timedelta(days=7)

        if event_type == 'upcoming':
            launches = sorted(launches, key=lambda x: parse(x['net']))
            today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
            this_week_launches = [l for l in launches if
                                  today < parse(l['net']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
            later_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() > this_week_end]
            grouped = [('Today', today_launches), ('This Week', this_week_launches), ('Later', later_launches)]
        else:
            launches = sorted(launches, key=lambda x: parse(x['net']), reverse=True)
            today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
            last_week_launches = [l for l in launches if
                                  last_week_start <= parse(l['net']).replace(tzinfo=pytz.UTC).date() < today]
            earlier_launches = [l for l in launches if
                                parse(l['net']).replace(tzinfo=pytz.UTC).date() < last_week_start]
            grouped = [('Today', today_launches), ('Last Week', last_week_launches), ('Earlier', earlier_launches)]

        list_widget = self.launch_list
        list_widget.clear()
        for group_name, group in grouped:
            if group:
                item = QListWidgetItem(group_name)
                item.setFlags(Qt.NoItemFlags)
                item.setBackground(QColor(50, 50, 50))
                list_widget.addItem(item)
                for launch in group:
                    item = QListWidgetItem()
                    card = EventCard(launch, event_type, tz)
                    item.setSizeHint(card.sizeHint())
                    list_widget.addItem(item)
                    list_widget.setItemWidget(item, card)
        logger.info(f"Updated {event_type} launches")

    def update_races(self, event_type):
        logger.info(f"Updating races for {event_type}")
        tz = pytz.timezone(location_settings[self.location_control.buttons[0][1]]['timezone'])
        races = fetch_f1_data()['schedule']
        today = datetime.now(pytz.UTC).date()
        this_week_end = today + timedelta(days=7)
        last_week_start = today - timedelta(days=7)

        if event_type == 'upcoming':
            races = sorted(races, key=lambda x: parse(x['date_start']))
            today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
            this_week_races = [r for r in races if
                               today < parse(r['date_start']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
            later_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() > this_week_end]
            grouped = [('Today', today_races), ('This Week', this_week_races), ('Later', later_races)]
        else:
            races = sorted(races, key=lambda x: parse(x['date_start']), reverse=True)
            today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
            last_week_races = [r for r in races if
                               last_week_start <= parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < today]
            earlier_races = [r for r in races if
                             parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < last_week_start]
            grouped = [('Today', today_races), ('Last Week', last_week_races), ('Earlier', earlier_races)]

        list_widget = self.race_list
        list_widget.clear()
        for group_name, group in grouped:
            if group:
                item = QListWidgetItem(group_name)
                item.setFlags(Qt.NoItemFlags)
                item.setBackground(QColor(50, 50, 50))
                list_widget.addItem(item)
                for race in group:
                    item = QListWidgetItem()
                    card = EventCard(race, event_type, tz)
                    item.setSizeHint(card.sizeHint())
                    list_widget.addItem(item)
                    list_widget.setItemWidget(item, card)
        logger.info(f"Updated {event_type} races")


if __name__ == '__main__':
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu --ignore-gpu-blacklist"
    os.environ["QT_LOGGING_RULES"] = "qt5ct.debug=false;qt.webenginecontext=true"

    app = QApplication(sys.argv)
    try:
        logger.info("Starting SpaceXDashboard application")
        window = SpaceXDashboard()
        window.showFullScreen()  # Fullscreen for Banana Pi 320x1480 display
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        raise