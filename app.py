import sys
import threading
import requests
from dash import Dash, html, dcc, Input, Output, State
import plotly.express as px
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz
import pandas as pd
import calendar
import time
from dash.exceptions import PreventUpdate

# Set up logging
logging.basicConfig(level=logging.DEBUG, filename='/tmp/dash.log')
logger = logging.getLogger(__name__)

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP,
    'https://fonts.cdnfonts.com/css/d-din',
    '/assets/custom.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
])

# Cache for launch data
launch_cache = {'previous': {'data': None, 'timestamp': None}, 'upcoming': {'data': None, 'timestamp': None}}
CACHE_DURATION = timedelta(minutes=120)

f1_cache = None

# Fetch SpaceX launch data from LL2 API
def fetch_launches():
    global launch_cache
    current_time = datetime.now(pytz.UTC)
    current_date_str = current_time.strftime('%Y-%m-%d')
    current_year = current_time.year

    # Fetch previous launches for plot
    if (launch_cache['previous']['data'] is not None and
            launch_cache['previous']['timestamp'] is not None and
            current_time - launch_cache['previous']['timestamp'] < CACHE_DURATION):
        logger.debug("Returning cached previous launch data")
        previous_launches = launch_cache['previous']['data']
    else:
        try:
            url = f'https://ll.thespacedevs.com/2.3.0/launches/previous/?lsp__name=SpaceX&net__gte={current_year}-01-01&net__lte={current_date_str}&limit=100'
            previous_launches = []
            while url:
                print(f"Fetching previous launches: {url}")  # Debug print
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                previous_launches.extend(data['results'])
                url = data.get('next')
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
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')  # Extract video_url
                }
                for launch in previous_launches
            ]
            logger.debug(f"Fetched {len(previous_launches)} previous launches from LL2 API")
            launch_cache['previous']['data'] = previous_launches
            launch_cache['previous']['timestamp'] = current_time
        except Exception as e:
            logger.error(f"LL2 API error for previous launches: {e}")
            previous_launches = [
                {'mission': 'Starship Flight 7', 'date': '2025-01-15', 'time': '12:00:00', 'net': '2025-01-15T12:00:00Z', 'status': 'Success', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': 'https://www.youtube.com/embed/Pn6e1O5bEyA?loop=1&playlist=Pn6e1O5bEyA&rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1'},
                {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
                {'mission': 'Starship Flight 8', 'date': '2025-03-06', 'time': '15:45:00', 'net': '2025-03-06T15:45:00Z', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': ''},
                {'mission': 'Transporter-13', 'date': '2025-04-10', 'time': '07:30:00', 'net': '2025-04-10T07:30:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40', 'video_url': ''},
                {'mission': 'Starship Flight 9', 'date': '2025-05-27', 'time': '14:30:00', 'net': '2025-05-27T14:30:00Z', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': ''}
            ]

    # Fetch upcoming launches for list
    if (launch_cache['upcoming']['data'] is not None and
            launch_cache['upcoming']['timestamp'] is not None and
            current_time - launch_cache['upcoming']['timestamp'] < CACHE_DURATION):
        logger.debug("Returning cached upcoming launch data")
        upcoming_launches = launch_cache['upcoming']['data']
    else:
        try:
            url = 'https://ll.thespacedevs.com/2.3.0/launches/upcoming/?lsp__name=SpaceX&limit=100'
            upcoming_launches = []
            while url:
                print(f"Fetching upcoming launches: {url}")  # Debug print
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                upcoming_launches.extend(data['results'])
                url = data.get('next')
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
                    'video_url': launch.get('vidURLs', [{}])[0].get('url', '')  # Extract video_url
                }
                for launch in upcoming_launches
            ]
            logger.debug(f"Fetched {len(upcoming_launches)} upcoming launches from LL2 API")
            launch_cache['upcoming']['data'] = upcoming_launches
            launch_cache['upcoming']['timestamp'] = current_time
        except Exception as e:
            logger.error(f"LL2 API error for upcoming launches: {e}")
            upcoming_launches = [
                {'mission': 'Transporter-14', 'date': '2025-06-25', 'time': '06:54:00', 'net': '2025-06-25T06:54:00Z', 'status': 'Go for Launch', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40', 'video_url': ''},
                {'mission': 'Axiom Mission 4', 'date': '2025-06-28', 'time': 'TBD', 'net': '2025-06-28T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
                {'mission': 'Dragonfly (Titan)', 'date': '2025-07-01', 'time': 'TBD', 'net': '2025-07-01T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon Heavy', 'orbit': 'Heliocentric', 'pad': 'LC-39A', 'video_url': ''},
                {'mission': 'TRACERS', 'date': '2025-07-15', 'time': 'TBD', 'net': '2025-07-15T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'SLC-40', 'video_url': ''},
                {'mission': 'Crew-11', 'date': '2025-07-31', 'time': 'TBD', 'net': '2025-07-31T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A', 'video_url': ''},
                {'mission': 'Starship Flight 10', 'date': '2025-09-20', 'time': '13:00:00', 'net': '2025-09-20T13:00:00Z', 'status': 'TBD', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase', 'video_url': ''},
                {'mission': 'Europa Clipper', 'date': '2025-10-10', 'time': 'TBD', 'net': '2025-10-10T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon Heavy', 'orbit': 'Heliocentric', 'pad': 'LC-39A', 'video_url': ''},
                {'mission': 'Transporter-15', 'date': '2025-11-05', 'time': '08:00:00', 'net': '2025-11-05T08:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40', 'video_url': ''}
            ]
    return {'previous': previous_launches, 'upcoming': upcoming_launches}

# Hardcoded F1 2025 sessions (partial, as in original; merged with fetched schedule)
hardcoded_sessions = [
    {"meeting_key":1253,"session_key":9683,"location":"Sakhir","date_start":"2025-02-26T07:00:00+00:00","date_end":"2025-02-26T16:00:00+00:00","session_type":"Practice","session_name":"Day 1","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1253,"session_key":9684,"location":"Sakhir","date_start":"2025-02-27T07:00:00+00:00","date_end":"2025-02-27T16:00:00+00:00","session_type":"Practice","session_name":"Day 2","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    {"meeting_key":1253,"session_key":9685,"location":"Sakhir","date_start":"2025-02-28T07:00:00+00:00","date_end":"2025-02-28T16:00:00+00:00","session_type":"Practice","session_name":"Day 3","country_key":36,"country_code":"BRN","country_name":"Bahrain","circuit_key":63,"circuit_short_name":"Sakhir","gmt_offset":"03:00:00","year":2025},
    # ... (your full hardcoded_sessions list here; omitted for brevity, but keep as-is in code)
]

# Fetch F1 data from Ergast API (replaces OpenF1/hardcoded)
def fetch_f1_data():
    global f1_cache
    if f1_cache is not None:
        return f1_cache
    year = 2025
    try:
        # Fetch schedule
        schedule_url = f"https://ergast.com/api/f1/{year}.json"
        schedule_resp = requests.get(schedule_url, timeout=10)
        schedule_resp.raise_for_status()
        schedule_data = schedule_resp.json()['MRData']['RaceTable']['Races']
        meetings = [
            {
                "meeting_key": i+1,  # Simple key
                "circuit_key": r['Circuit']['circuitId'],
                "circuit_short_name": r['Circuit']['circuitName'],
                "meeting_code": r['Circuit']['Location']['country'][:3].upper(),
                "location": r['Circuit']['Location']['locality'],
                "country_key": "",  # Not in Ergast, omit or map
                "country_code": r['Circuit']['Location']['country'][:3].upper(),
                "country_name": r['Circuit']['Location']['country'],
                "meeting_name": r['raceName'],
                "meeting_official_name": r['raceName'],
                "gmt_offset": "",  # Not in Ergast, use hardcoded if needed
                "date_start": f"{r['date']}T{r['time']}" if 'time' in r else f"{r['date']}T00:00:00Z",
                "year": year
            } for i, r in enumerate(schedule_data)
        ]

        # Merge hardcoded sessions (by meeting_key or name match)
        for meeting in meetings:
            meeting['sessions'] = [s for s in hardcoded_sessions if s['meeting_key'] == meeting['meeting_key'] or s['circuit_short_name'] == meeting['circuit_short_name']]

        # Determine current round
        current_time = datetime.now(pytz.UTC)
        current_round = max([i+1 for i, r in enumerate(schedule_data) if parse(r['date']).date() < current_time.date()] or [0])

        # Fetch driver standings (current)
        driver_url = f"https://ergast.com/api/f1/{year}/driverStandings.json?limit=30"
        driver_resp = requests.get(driver_url, timeout=10)
        driver_resp.raise_for_status()
        driver_data = driver_resp.json()['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings'] if driver_resp.json()['MRData']['StandingsTable']['StandingsLists'] else []
        driver_standings = [
            {
                'position': int(d['position']),
                'points': int(d['points']),
                'Driver': {'givenName': d['Driver']['givenName'], 'familyName': d['Driver']['familyName']}
            } for d in driver_data
        ]

        # Fetch constructor standings
        constructor_url = f"https://ergast.com/api/f1/{year}/constructorStandings.json"
        constructor_resp = requests.get(constructor_url, timeout=10)
        constructor_resp.raise_for_status()
        constructor_data = constructor_resp.json()['MRData']['StandingsTable']['StandingsLists'][0]['ConstructorStandings'] if constructor_resp.json()['MRData']['StandingsTable']['StandingsLists'] else []
        constructor_standings = [
            {
                'position': int(c['position']),
                'points': int(c['points']),
                'Constructor': {'name': c['Constructor']['name']}
            } for c in constructor_data
        ]

        # Fetch cumulative driver points for plot (top 5 current drivers)
        top_drivers = [d['Driver']['familyName'] for d in driver_standings[:5]]
        cumulative_points = {driver: [] for driver in top_drivers}
        rounds = []
        for round_num in range(1, current_round + 1):
            round_url = f"https://ergast.com/api/f1/{year}/{round_num}/driverStandings.json"
            round_resp = requests.get(round_url, timeout=10)
            if round_resp.status_code == 200:
                round_data = round_resp.json()['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']
                rounds.append(f"Round {round_num}")
                for driver in top_drivers:
                    points = next((int(s['points']) for s in round_data if s['Driver']['familyName'] == driver), 0)
                    cumulative_points[driver].append(points)

        f1_cache = {
            'schedule': meetings,
            'driver_standings': driver_standings,
            'constructor_standings': constructor_standings,
            'cumulative_points': cumulative_points,
            'rounds': rounds
        }
        return f1_cache
    except Exception as e:
        logger.error(f"Ergast API error: {e}")
        # Fallback hardcoded (your original)
        f1_cache = {
            'schedule': hardcoded_f1_schedule,  # Your hardcoded
            'driver_standings': [
                {'position': 1, 'points': 234, 'Driver': {'givenName': 'Oscar', 'familyName': 'Piastri'}},
                {'position': 2, 'points': 226, 'Driver': {'givenName': 'Lando', 'familyName': 'Norris'}},
                {'position': 3, 'points': 165, 'Driver': {'givenName': 'Max', 'familyName': 'Verstappen'}},
                # Add more as needed
            ],
            'constructor_standings': [
                {'position': 1, 'points': 460, 'Constructor': {'name': 'McLaren'}},
                {'position': 2, 'points': 165, 'Constructor': {'name': 'Red Bull'}},
                # Add more
            ],
            'cumulative_points': {  # Hypothetical fallback
                'Piastri': [25, 50, 68, 93, 118, 143, 161, 186, 211, 229, 234],
                'Norris': [18, 36, 54, 72, 90, 108, 126, 151, 176, 194, 226],
                # Etc.
            },
            'rounds': [f"Round {i}" for i in range(1, 13)]
        }
        for meeting in f1_cache['schedule']:
            meeting['sessions'] = [s for s in hardcoded_sessions if s['meeting_key'] == meeting['meeting_key']]
        return f1_cache

# Fetch weather data from Open-Meteo API
def fetch_weather(lat, lon, location):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover&timezone=UTC"
        print(f"Fetching weather for {location}: {url}")  # Debug print
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"API response for {location}: {data}")  # Debug print
        now = datetime.now(pytz.UTC)
        hourly = data['hourly']
        times = [datetime.strptime(t, '%Y-%m-%dT%H:%M') for t in hourly['time']]
        closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - now))
        weather = {
            'temperature_c': hourly['temperature_2m'][closest_idx],
            'temperature_f': hourly['temperature_2m'][closest_idx] * 9/5 + 32,
            'wind_speed_ms': hourly['wind_speed_10m'][closest_idx],
            'wind_speed_kts': hourly['wind_speed_10m'][closest_idx] * 1.94384,
            'wind_direction': hourly['wind_direction_10m'][closest_idx],
            'cloud_cover': hourly['cloud_cover'][closest_idx]
        }
        logger.debug(f"Fetched weather data for {location}: {weather}")
        return weather
    except Exception as e:
        logger.error(f"Open-Meteo API error for {location}: {e}")
        fallback_values = {
            'Starbase': {'temperature_c': 28, 'temperature_f': 82.4, 'wind_speed_ms': 6, 'wind_speed_kts': 11.7, 'wind_direction': 120, 'cloud_cover': 60},
            'Vandy': {'temperature_c': 20, 'temperature_f': 68, 'wind_speed_ms': 4, 'wind_speed_kts': 7.8, 'wind_direction': 270, 'cloud_cover': 40},
            'Cape': {'temperature_c': 26, 'temperature_f': 78.8, 'wind_speed_ms': 5.5, 'wind_speed_kts': 10.7, 'wind_direction': 90, 'cloud_cover': 70},
            'Hawthorne': {'temperature_c': 22, 'temperature_f': 71.6, 'wind_speed_ms': 3.5, 'wind_speed_kts': 6.8, 'wind_direction': 180, 'cloud_cover': 30}
        }
        return fallback_values.get(location, {
            'temperature_c': 25,
            'temperature_f': 77,
            'wind_speed_ms': 5,
            'wind_speed_kts': 9.7,
            'wind_direction': 90,
            'cloud_cover': 50
        })

# Initial weather data
def initialize_weather():
    weather_data = {}
    for location, settings in location_settings.items():
        weather_data[location] = fetch_weather(settings['lat'], settings['lon'], location)
    print(f"Initialized weather data: {weather_data}")  # Debug print
    return weather_data

# Initial launches
launches = fetch_launches()
previous_launches = launches['previous']
upcoming_launches = launches['upcoming']

# Process launch data for line chart
def prepare_chart_data(launches):
    df = pd.DataFrame(launches)
    df['date'] = pd.to_datetime(df['date'])
    current_year = datetime.now(pytz.UTC).year
    df = df[(df['date'].dt.year == current_year)]
    rocket_types = ['Starship', 'Falcon 9', 'Falcon Heavy']
    df = df[df['rocket'].isin(rocket_types)]
    df_grouped = df.groupby(['date', 'rocket']).size().reset_index(name='Launches')
    df_pivot = df_grouped.pivot(index='date', columns='rocket', values='Launches').fillna(0).reset_index()
    for col in rocket_types:
        if col not in df_pivot.columns:
            df_pivot[col] = 0
    for col in rocket_types:
        df_pivot[col] = df_pivot[col].cumsum()
    df_melt = pd.melt(df_pivot, id_vars=['date'], value_vars=rocket_types,
                      var_name='Rocket', value_name='Cumulative Launches')
    return df_melt, df_pivot

# Create line chart
chart_data, df_pivot = prepare_chart_data(previous_launches)
color_map = {'Starship': '#FF5733', 'Falcon 9': '#33CFFF', 'Falcon Heavy': '#FFC107'}
totals = {rocket: int(df_pivot[rocket].iloc[-1]) if rocket in df_pivot.columns else 0 for rocket in color_map.keys()}
fig = px.line(
    chart_data,
    x='date',
    y='Cumulative Launches',
    color='Rocket',
    title=None,
    labels={'date': 'Date', 'Cumulative Launches': 'Cumulative Launches', 'Rocket': 'Rocket Type'},
    color_discrete_map=color_map
)
current_date = datetime.now(pytz.UTC)
last_day = calendar.monthrange(current_date.year, current_date.month)[1]
end_date = datetime(current_date.year, current_date.month, last_day).strftime('%Y-%m-%d')
fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='D-DIN, sans-serif', color='#ffffff'),
    font_color='#ffffff',
    xaxis=dict(
        title_font=dict(size=12, color='#ffffff', family='D-DIN, sans-serif'),
        tickfont=dict(size=10, color='#ffffff', family='D-DIN, sans-serif'),
        gridcolor='rgba(128,128,128,0.2)',
        title=None,
        range=[f'{current_date.year}-01-01', end_date],
        dtick='M1',
        griddash='dash'
    ),
    yaxis=dict(
        title_font=dict(size=12, color='#ffffff', family='D-DIN, sans-serif'),
        tickfont=dict(size=10, color='#ffffff', family='D-DIN, sans-serif'),
        gridcolor='rgba(128,128,128,0.2)',
        title='Cumulative Launches'
    ),
    showlegend=False,
    margin=dict(l=20, r=20, t=20, b=20),
    height=300
)
fig.update_traces(line=dict(width=2))
print(f"Chart font set to: D-DIN, color: #ffffff")  # Debug print

# Custom legend
custom_legend = html.Div([
    html.Div([
        html.Span('■', style={'color': color_map[rocket], 'marginRight': '5px', 'fontSize': '20px'}),
        html.Span(f"{rocket}: {totals[rocket]}", style={'color': 'var(--text-color-secondary)', 'fontSize': '11px'})
    ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '15px'})
    for rocket in color_map.keys()
], style={'display': 'flex', 'justifyContent': 'center', 'marginTop': '10px', 'padding': '0 15px'})

# Categorize launches
today = datetime.now(pytz.UTC).date()
this_week_end = today + timedelta(days=7)
last_week_start = today - timedelta(days=7)
today_datetime = datetime.now(pytz.UTC)

# Location settings
location_settings = {
    'Starbase': {'lat': 25.997, 'lon': -97.155, 'timezone': 'America/Chicago'},
    'Vandy': {'lat': 34.632, 'lon': -120.611, 'timezone': 'America/Los_Angeles'},
    'Cape': {'lat': 28.392, 'lon': -80.605, 'timezone': 'America/New_York'},
    'Hawthorne': {'lat': 33.916, 'lon': -118.352, 'timezone': 'America/Los_Angeles'}
}

# Radar URLs
radar_locations = {
    'Starbase': 'https://embed.windy.com/embed2.html?lat=25.997&lon=-97.155&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=25.997&detailLon=-97.155&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
    'Vandy': 'https://embed.windy.com/embed2.html?lat=34.632&lon=-120.611&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=34.632&detailLon=-120.611&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
    'Cape': 'https://embed.windy.com/embed2.html?lat=28.392&lon=-80.605&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=28.392&detailLon=-80.605&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
    'Hawthorne': 'https://embed.windy.com/embed2.html?lat=33.916&lon=-118.352&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=33.916&detailLon=-118.352&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1'
}

# Styles with CSS variables
column_style = {
    'height': '85vh',
    'padding': '0',
    'borderRadius': '8px',
    '-webkit-border-radius': '8px',
    '-moz-border-radius': '8px',
    'backgroundColor': 'var(--card-bg)',
    'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
    'fontFamily': 'D-DIN, sans-serif',
    'margin': '5px',
    'display': 'flex',
    'flexDirection': 'column',
    'overflow': 'visible'
}

title_style = {
    'fontSize': '14px',
    'fontWeight': 'normal',
    'textTransform': 'uppercase',
    'color': 'var(--text-color-secondary)',
    'letterSpacing': '1.5px',
    'marginBottom': '0',
    'fontFamily': 'D-DIN, sans-serif',
    'position': 'relative',
    'top': '0',
    'backgroundColor': 'var(--card-bg)',
    'zIndex': '10',
    'padding': '10px 15px',
    'borderBottom': '1px solid var(--text-color-secondary)'
}

launch_card_style = {
    'backgroundColor': 'var(--card-bg)',
    'borderRadius': '6px',
    '-webkit-border-radius': '6px',
    '-moz-border-radius': '6px',
    'padding': '10px',
    'marginBottom': '10px',
    'boxShadow': '0 1px 4px rgba(0,0,0,0.05)',
    'transition': 'transform 0.2s',
    ':hover': {'transform': 'scale(1.02)'}
}

category_style = {
    'fontSize': '13px',
    'fontWeight': 'bold',
    'color': 'var(--text-color)',
    'margin': '10px 0 5px 0',
    'borderBottom': '1px solid var(--text-color-secondary)',
    'paddingBottom': '5px'
}

# Render launches
def render_launches(launches, timezone='America/Chicago', event_type='upcoming'):
    tz = pytz.timezone(timezone)
    if event_type == 'upcoming':
        launches = sorted(launches, key=lambda x: parse(x['net']))
        today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
        this_week_launches = [l for l in launches if today < parse(l['net']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
        later_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() > this_week_end]
        return html.Div([
            html.Div('Today', style=category_style) if today_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in today_launches],
            html.Div('This Week', style=category_style) if this_week_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in this_week_launches],
            html.Div('Later', style=category_style) if later_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in later_launches]
        ], style={'padding': '0 15px'})
    else:
        launches = sorted(launches, key=lambda x: parse(x['net']), reverse=True)
        today_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today]
        last_week_launches = [l for l in launches if last_week_start <= parse(l['net']).replace(tzinfo=pytz.UTC).date() < today]
        earlier_launches = [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() < last_week_start]
        return html.Div([
            html.Div('Today', style=category_style) if today_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in today_launches],
            html.Div('Last Week', style=category_style) if last_week_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in last_week_launches],
            html.Div('Earlier', style=category_style) if earlier_launches else None,
            *[html.Div([
                html.H4(launch['mission'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                html.P([
                    html.I(className='fas fa-rocket', style={'marginRight': '5px'}),
                    f"Rocket: {launch['rocket']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-globe', style={'marginRight': '5px'}),
                    f"Orbit: {launch['orbit']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P([
                    html.I(className='fas fa-map-marker-alt', style={'marginRight': '5px'}),
                    f"Pad: {launch['pad']}"
                ], style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(f"Date: {launch['date']} {launch['time']} UTC", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                html.P(
                    f"{timezone.split('/')[-1]}: {parse(launch['net']).astimezone(tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                    style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
                ),
                html.P(f"Status: {launch['status']}", style={
                    'fontSize': '12px',
                    'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                    'margin': '0'
                })
            ], style=launch_card_style) for launch in earlier_launches]
        ], style={'padding': '0 15px'})

# Render races with accordion
def render_races(races, event_type='upcoming'):
    if event_type == 'upcoming':
        races = sorted(races, key=lambda x: parse(x['date_start']))
        today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
        this_week_races = [r for r in races if today < parse(r['date_start']).replace(tzinfo=pytz.UTC).date() <= this_week_end]
        later_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() > this_week_end]
        def create_accordion(category_races):
            if not category_races:
                return None
            items = [
                dmc.AccordionItem(
                    [
                        dmc.AccordionControl(
                            html.Div([
                                html.H4(r['meeting_name'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                                html.P(f"Circuit: {r['circuit_short_name']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                                html.P(f"Date: {r['date_start']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                            ])
                        ),
                        dmc.AccordionPanel(
                            html.Div([
                                html.Div([
                                    html.H5(s['session_name'], style={'fontSize': '13px', 'margin': '0', 'color': 'var(--text-color)'}),
                                    html.P(f"Start: {s['date_start']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '2px 0'}),
                                    html.P(f"End: {s.get('date_end', 'N/A')}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '2px 0'}),
                                ], style={'marginBottom': '10px'}) for s in sorted(r.get('sessions', []), key=lambda x: parse(x['date_start']))
                            ]) if r.get('sessions') else "No session info available"
                        ),
                    ],
                    value=str(idx)
                ) for idx, r in enumerate(category_races)
            ]
            return dmc.Accordion(
                children=items,
                multiple=True,
                variant="contained",
                chevronPosition="left",
                disableChevronRotation=False
            )

        return html.Div([
            html.Div('Today', style=category_style) if today_races else None,
            create_accordion(today_races),
            html.Div('This Week', style=category_style) if this_week_races else None,
            create_accordion(this_week_races),
            html.Div('Later', style=category_style) if later_races else None,
            create_accordion(later_races)
        ], style={'padding': '0 15px'})
    else:
        races = sorted(races, key=lambda x: parse(x['date_start']), reverse=True)
        today_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() == today]
        last_week_races = [r for r in races if last_week_start <= parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < today]
        earlier_races = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC).date() < last_week_start]
        def create_accordion(category_races):
            if not category_races:
                return None
            items = [
                dmc.AccordionItem(
                    [
                        dmc.AccordionControl(
                            html.Div([
                                html.H4(r['meeting_name'], style={'fontSize': '14px', 'margin': '0', 'color': 'var(--text-color)'}),
                                html.P(f"Circuit: {r['circuit_short_name']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                                html.P(f"Date: {r['date_start']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
                            ])
                        ),
                        dmc.AccordionPanel(
                            html.Div([
                                html.Div([
                                    html.H5(s['session_name'], style={'fontSize': '13px', 'margin': '0', 'color': 'var(--text-color)'}),
                                    html.P(f"Start: {s['date_start']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '2px 0'}),
                                    html.P(f"End: {s.get('date_end', 'N/A')}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '2px 0'}),
                                ], style={'marginBottom': '10px'}) for s in sorted(r.get('sessions', []), key=lambda x: parse(x['date_start']))
                            ]) if r.get('sessions') else "No session info available"
                        ),
                    ],
                    value=str(idx)
                ) for idx, r in enumerate(category_races)
            ]
            return dmc.Accordion(
                children=items,
                multiple=True,
                variant="contained",
                chevronPosition="left",
                disableChevronRotation=False
            )

        return html.Div([
            html.Div('Today', style=category_style) if today_races else None,
            create_accordion(today_races),
            html.Div('Last Week', style=category_style) if last_week_races else None,
            create_accordion(last_week_races),
            html.Div('Earlier', style=category_style) if earlier_races else None,
            create_accordion(earlier_races)
        ], style={'padding': '0 15px'})

# Initial content for columns
column1_initial = [
    html.Div('Launch Trends', style=title_style),
    html.Div([
        dcc.Graph(id='chart1', figure=fig, style={'margin': '0', 'height': 'calc(100% - 50px)'}),
        custom_legend
    ], style={'overflowY': 'auto', 'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'marginTop': '0'})
]

column2_initial = [
    html.Div('Radar', style=title_style),
    html.Iframe(
        id='radar-iframe',
        src=radar_locations['Starbase'],
        style={
            'width': '100%',
            'height': '100%',
            'border': 'none',
            'marginTop': '0'
        },
        allow='encrypted-media; fullscreen'
    )
]

# For column3 initial
launches_data = fetch_launches()
selected = launches_data['upcoming']
initial_timezone = location_settings['Starbase']['timezone']
initial_event_type = 'upcoming'
initial_launch_table = render_launches(selected, initial_timezone, initial_event_type)
column3_initial = [
    html.Div([
        html.Span('Launches', style={'fontSize': '14px', 'fontWeight': 'normal', 'textTransform': 'uppercase', 'color': 'var(--text-color-secondary)', 'letterSpacing': '1.5px', 'fontFamily': 'D-DIN, sans-serif'}),
        dmc.SegmentedControl(
            id='event-type-toggle',
            value='upcoming',
            data=[
                {'label': 'Upcoming', 'value': 'upcoming'},
                {'label': 'Past', 'value': 'past'}
            ],
            size='xs',
            style={'width': '130px', 'fontFamily': 'D-DIN, sans-serif', 'fontSize': '10px', 'height': '22px'}
        )
    ], style={**title_style, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '0'}),
    html.Div(id='launch-table', children=initial_launch_table, style={'overflowY': 'auto', 'flex': '1', 'marginTop': '0'})
]

column4_initial = [
    html.Div('Videos', style=title_style),
    html.Iframe(
        id='youtube-iframe',
        src='https://www.youtube.com/embed/videoseries?list=PLBQ5P5txVQr9_jeZLGa0n5EIYvsOJFAnY&autoplay=1&mute=1&loop=1&controls=1&rel=0&enablejsapi=1',
        style={
            'width': '100%',
            'height': '100%',
            'border': 'none',
            'marginTop': '0'
        },
        allow='encrypted-media; autoplay; fullscreen; picture-in-picture'
    )
]

# Column definitions with initial children
column1 = html.Div(id='column1', children=column1_initial, style=column_style)

column2 = html.Div(id='column2', children=column2_initial, style=column_style)

column3 = html.Div(id='column3', children=column3_initial, style=column_style)

column4 = html.Div(id='column4', children=column4_initial, style=column_style)

# Theme store and toggles
theme_store = dcc.Store(id='theme-store', data='dark')
weather_store = dcc.Store(id='weather-store', data=initialize_weather())
mode_store = dcc.Store(id='mode-store', data='spacex')
time_interval = dcc.Interval(id='time-interval', interval=1000, n_intervals=0)
weather_interval = dcc.Interval(id='weather-interval', interval=5*60*1000, n_intervals=0)  # 5 minutes

dark_mode_toggle = dmc.SegmentedControl(
    id='dark-mode-toggle',
    value='dark',
    data=[
        {'label': 'Light', 'value': 'light'},
        {'label': 'Dark', 'value': 'dark'}
    ],
    style={
        'width': '120px',
        'fontFamily': 'D-DIN, sans-serif',
        'fontSize': '14px',
        'backgroundColor': 'var(--bar-bg)',
        'padding': '4px',
        'borderRadius': '6px'
    }
)
location_toggle = dmc.SegmentedControl(
    id='location-toggle',
    value='Starbase',
    data=[
        {'label': 'Starbase', 'value': 'Starbase'},
        {'label': 'Vandy', 'value': 'Vandy'},
        {'label': 'Cape', 'value': 'Cape'},
        {'label': 'Hawthorne', 'value': 'Hawthorne'}
    ],
    style={
        'width': '240px',
        'fontFamily': 'D-DIN, sans-serif',
        'fontSize': '10px',
        'backgroundColor': 'var(--bar-bg)',
        'padding': '2px',
        'borderRadius': '6px',
        'marginLeft': '10px'
    }
)
print(f"Location toggle data: {location_toggle.data}")  # Debug print

# Layout with MantineProvider
app.layout = dmc.MantineProvider(
    theme={"fontFamily": "D-DIN, sans-serif"},
    children=html.Div(
        id='root',
        children=[
            theme_store,
            weather_store,
            mode_store,
            time_interval,
            weather_interval,
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Col(column1, width=3),
                            dbc.Col(column2, width=3),
                            dbc.Col(column3, width=3),
                            dbc.Col(column4, width=3),
                        ],
                        style={'margin': '0', 'padding': '5px', 'overflow': 'visible'}
                    ),
                    html.Div(
                        id='bottom-bar-container',
                        children=[
                            html.Div(
                                id='left-bar',
                                children=[
                                    html.Span(id='current-time', style={'fontSize': '12px', 'marginRight': '10px'}),
                                    html.Span(id='current-weather', style={'fontSize': '10px', 'color': 'var(--text-color-secondary)', 'marginRight': '10px'}),
                                    location_toggle
                                ],
                                style={
                                    'display': 'flex',
                                    'alignItems': 'center',
                                    'height': '5vh',
                                    'flex': '1',
                                    'minWidth': '400px',
                                    'backgroundColor': 'var(--bar-bg)',
                                    'borderRadius': '20px',
                                    'padding': '0 10px',
                                    'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                                    'fontFamily': 'D-DIN, sans-serif',
                                    'marginRight': '10px'
                                }
                            ),
                            html.Img(
                                id='logo',
                                src='/assets/spacex-logo.png',
                                style={'width': '80px', 'margin': '0 10px', 'cursor': 'pointer'}
                            ),
                            html.Div(
                                id='right-bar',
                                children=[
                                    html.Span(id='countdown', style={'fontSize': '12px', 'marginRight': '10px'}),
                                    dark_mode_toggle
                                ],
                                style={
                                    'display': 'flex',
                                    'alignItems': 'center',
                                    'justifyContent': 'flex-end',
                                    'height': '5vh',
                                    'flex': '1',
                                    'minWidth': '400px',
                                    'backgroundColor': 'var(--bar-bg)',
                                    'borderRadius': '20px',
                                    'padding': '0 10px',
                                    'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                                    'fontFamily': 'D-DIN, sans-serif',
                                    'marginLeft': '10px'
                                }
                            )
                        ],
                        style={
                            'display': 'flex',
                            'justifyContent': 'center',
                            'alignItems': 'center',
                            'width': '100%',
                            'height': '5vh',
                            'padding': '0 10px'
                        }
                    )
                ],
                fluid=True,
                style={'width': '100vw', 'height': '100vh', 'margin': '0', 'padding': '0', 'overflow': 'visible'}
            )
        ]
    )
)

app.layout.children.children.append(dcc.Interval(id='interval', interval=720000, n_intervals=0))
app.layout.children.children.append(dcc.Store(id='location-store', data='Starbase'))

# Callbacks
@app.callback(
    Output('theme-store', 'data'),
    Input('dark-mode-toggle', 'value')
)
def update_theme(toggle_value):
    return toggle_value

@app.callback(
    Output('root', 'className'),
    Input('theme-store', 'data')
)
def update_theme_class(theme):
    return f'theme-{theme}'

@app.callback(
    Output('mode-store', 'data'),
    Input('logo', 'n_clicks'),
    State('mode-store', 'data')
)
def toggle_mode(n_clicks, mode):
    if n_clicks is None:
        raise PreventUpdate
    return 'f1' if mode == 'spacex' else 'spacex'

@app.callback(
    Output('logo', 'src'),
    Input('mode-store', 'data')
)
def update_logo(mode):
    return '/assets/f1-logo.png' if mode == 'f1' else '/assets/spacex-logo.png'

@app.callback(
    Output('column1', 'children'),
    Input('mode-store', 'data')
)
def update_column1(mode):
    if mode == 'spacex':
        return column1_initial
    else:
        data = fetch_f1_data()
        ds = data['driver_standings']
        table = html.Table([
            html.Thead(html.Tr([html.Th('Pos'), html.Th('Driver'), html.Th('Points')])),
            html.Tbody([html.Tr([html.Td(d['position']), html.Td(d['Driver']['givenName'] + ' ' + d['Driver']['familyName']), html.Td(d['points'])]) for d in ds])
        ], style={'width': '100%', 'color': 'white', 'fontSize': '12px'})
        return [
            html.Div('Driver Standings', style=title_style),
            html.Div(table, style={'overflowY': 'auto', 'flex': '1', 'padding': '15px'})
        ]

@app.callback(
    Output('column2', 'children'),
    Input('mode-store', 'data')
)
def update_column2(mode):
    if mode == 'spacex':
        return column2_initial
    else:
        data = fetch_f1_data()
        cumulative = data['cumulative_points']
        rounds = data['rounds']
        df = pd.DataFrame(cumulative, index=rounds).T.reset_index()
        df_melt = pd.melt(df, id_vars=['index'], value_vars=rounds, var_name='Round', value_name='Points')
        color_map_f1 = {'Piastri': '#FF8700', 'Norris': '#FF5733', 'Verstappen': '#0600EF', 'Russell': '#00A3FF', 'Leclerc': '#DC0000'}  # Example colors
        fig = px.line(
            df_melt,
            x='Round',
            y='Points',
            color='index',
            title=None,
            labels={'Round': 'Round', 'Points': 'Cumulative Points', 'index': 'Driver'},
            color_discrete_map=color_map_f1
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='D-DIN, sans-serif', color='#ffffff'),
            xaxis=dict(gridcolor='rgba(128,128,128,0.2)', title=None),
            yaxis=dict(gridcolor='rgba(128,128,128,0.2)', title='Cumulative Points'),
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
            height=300
        )
        fig.update_traces(line_width=2)
        custom_legend_f1 = html.Div([
            html.Div([
                html.Span('■', style={'color': color_map_f1[driver]}, 'marginRight': '5px', 'fontSize': '20px'}),
                html.Span(f"{driver}: {cumulative[driver][-1]}", style={'color': 'var(--text-color-secondary)', 'fontSize': '11px'})
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '15px'})
            for driver in cumulative.keys()
        ], style={'display': 'flex', 'justifyContent': 'center', 'marginTop': '10px', 'padding': '0 15px'})
        return [
            html.Div('Driver Points Over Time', style=title_style),
            html.Div([
                dcc.Graph(figure=fig, style={'height': 'calc(100% - 50px)'}),
                custom_legend_f1
            ], style={'overflowY': 'auto', 'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'marginTop': '0'})
        ]

@app.callback(
    Output('column3', 'children'),
    Input('mode-store', 'data')
)
def update_column3(mode):
    if mode == 'spacex':
        return [
            html.Div([
                html.Span('Launches', style={'fontSize': '14px', 'fontWeight': 'normal', 'textTransform': 'uppercase', 'color': 'var(--text-color-secondary)', 'letterSpacing': '1.5px', 'fontFamily': 'D-DIN, sans-serif'}),
                dmc.SegmentedControl(
                    id='event-type-toggle',
                    value='upcoming',
                    data=[
                        {'label': 'Upcoming', 'value': 'upcoming'},
                        {'label': 'Past', 'value': 'past'}
                    ],
                    size='xs',
                    style={'width': '130px', 'fontFamily': 'D-DIN, sans-serif', 'fontSize': '10px', 'height': '22px'}
                )
            ], style={**title_style, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '0'}),
            html.Div(id='launch-table', style={'overflowY': 'auto', 'flex': '1', 'marginTop': '0'})
        ]
    else:
        return [
            html.Div([
                html.Span('Races', style={'fontSize': '14px', 'fontWeight': 'normal', 'textTransform': 'uppercase', 'color': 'var(--text-color-secondary)', 'letterSpacing': '1.5px', 'fontFamily': 'D-DIN, sans-serif'}),
                dmc.SegmentedControl(
                    id='event-type-toggle',
                    value='upcoming',
                    data=[
                        {'label': 'Upcoming', 'value': 'upcoming'},
                        {'label': 'Past', 'value': 'past'}
                    ],
                    size='xs',
                    style={'width': '130px', 'fontFamily': 'D-DIN, sans-serif', 'fontSize': '10px', 'height': '22px'}
                )
            ], style={**title_style, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '0'}),
            html.Div(id='launch-table', style={'overflowY': 'auto', 'flex': '1', 'marginTop': '0'})
        ]

@app.callback(
    Output('column4', 'children'),
    Input('mode-store', 'data')
)
def update_column4(mode):
    if mode == 'spacex':
        return column4_initial
    else:
        next_race = get_next_race()
        if next_race:
            # Extended hardcoded coordinates for circuits
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
                'Montreal': {'lat': 45.5, 'lon': -73.5228},
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
                'Lusail': {'lat': 25.49, 'lon': 51.4542},
                'Abu Dhabi': {'lat': 24.4672, 'lon': 54.6031}
            }
            coords = circuit_coords.get(next_race['circuit_short_name'], {'lat': 0, 'lon': 0})
            df_map = pd.DataFrame({'lat': [coords['lat']], 'lon': [coords['lon']], 'name': [next_race['circuit_short_name']]})
            fig = px.scatter_mapbox(df_map, lat='lat', lon='lon', hover_name='name', zoom=10, mapbox_style="open-street-map")
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            return [
                html.Div('Next Race Location', style=title_style),
                dcc.Graph(figure=fig, style={'height': '100%', 'marginTop': '0'})
            ]
        else:
            return [
                html.Div('Next Race Location', style=title_style),
                html.Div('No upcoming races', style={'color': 'white', 'padding': '15px'})
            ]

@app.callback(
    Output('launch-table', 'children'),
    [Input('interval', 'n_intervals'),
     Input('location-store', 'data'),
     Input('event-type-toggle', 'value'),
     Input('mode-store', 'data')]
)
def update_events(n, location, event_type, mode):
    if mode == 'spacex':
        launches_data = fetch_launches()
        if event_type == 'upcoming':
            selected = launches_data['upcoming']
        else:
            selected = launches_data['previous']
        timezone = location_settings.get(location, {}).get('timezone', 'America/Chicago')
        return render_launches(selected, timezone, event_type)
    else:
        f1 = fetch_f1_data()
        races = f1['schedule']
        return render_races(races, event_type)

@app.callback(
    Output('weather-store', 'data'),
    Input('weather-interval', 'n_intervals')
)
def update_weather_cache(n):
    return initialize_weather()

@app.callback(
    Output('current-weather', 'children'),
    [Input('location-toggle', 'value'),
     Input('weather-store', 'data')]
)
def update_weather(location, weather_data):
    weather = weather_data.get(location, fetch_weather(location_settings[location]['lat'], location_settings[location]['lon'], location))
    print(f"Updating weather for {location}: {weather}")  # Debug print
    return html.Span(
        f"Wind {weather['wind_speed_kts']:.1f} kts / {weather['wind_speed_ms']:.1f} m/s, {weather['wind_direction']}° | "
        f"Temp {weather['temperature_f']:.1f}°F / {weather['temperature_c']:.1f}°C | "
        f"Clouds {weather['cloud_cover']}%"
    )

app.clientside_callback(
    """
    function(location) {
        const radarLocations = {
            'Starbase': 'https://embed.windy.com/embed2.html?lat=25.997&lon=-97.155&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=25.997&detailLon=-97.155&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
            'Vandy': 'https://embed.windy.com/embed2.html?lat=34.632&lon=-120.611&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=34.632&detailLon=-120.611&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
            'Cape': 'https://embed.windy.com/embed2.html?lat=28.392&lon=-80.605&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=28.392&detailLon=-80.605&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1',
            'Hawthorne': 'https://embed.windy.com/embed2.html?lat=33.916&lon=-118.352&zoom=8&level=surface&overlay=radar&menu=&message=&marker=&calendar=&pressure=&type=map&location=coordinates&detail=&detailLat=33.916&detailLon=-118.352&metricWind=mph&metricTemp=%C2%B0F&radarRange=-1'
        };
        const newSrc = radarLocations[location] + '&rand=' + Math.random();
        return newSrc;
    }
    """,
    Output('radar-iframe', 'src'),
    Input('location-toggle', 'value')
)

app.clientside_callback(
    """
    function(n, location) {
        const timezones = {
            'Starbase': 'America/Chicago',
            'Vandy': 'America/Los_Angeles',
            'Cape': 'America/New_York',
            'Hawthorne': 'America/Los_Angeles'
        };
        const tz = timezones[location] || 'America/Chicago';
        const now = new Date().toLocaleString('en-US', { timeZone: tz, hour12: false });
        const [date, time] = now.split(', ');
        const [hours, minutes, seconds] = time.split(':');
        return `${hours}:${minutes}:${seconds}`;
    }
    """,
    Output('current-time', 'children'),
    [Input('time-interval', 'n_intervals'),
     Input('location-toggle', 'value')]
)

def get_next_launch():
    current_time = datetime.now(pytz.UTC)
    valid_launches = [l for l in upcoming_launches if l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
    if not valid_launches:
        return None
    return min(valid_launches, key=lambda x: parse(x['net']))

def get_next_race():
    data = fetch_f1_data()
    races = data['schedule']
    current = datetime.now(pytz.UTC)
    upcoming = [r for r in races if parse(r['date_start']).replace(tzinfo=pytz.UTC) > current]
    if upcoming:
        return min(upcoming, key=lambda r: parse(r['date_start']))
    return None

def calculate_countdown():
    next_launch = get_next_launch()
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

@app.callback(
    Output('countdown', 'children'),
    Input('time-interval', 'n_intervals'),
    State('mode-store', 'data')
)
def update_countdown(n, mode):
    if mode == 'spacex':
        return calculate_countdown()
    else:
        next_race = get_next_race()
        if not next_race:
            return "No upcoming races"
        time_str = next_race['date_start']
        launch_time = parse(time_str).replace(tzinfo=pytz.UTC)
        current_time = datetime.now(pytz.UTC)
        if launch_time <= current_time:
            return "Race in progress"
        delta = launch_time - current_time
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"T- {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s to {next_race['meeting_name']}"

def run_dash():
    app.run(host='0.0.0.0', port=8050, debug=False, use_reloader=False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Dash in PyQt5')
        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl('http://localhost:8050'))
        self.setCentralWidget(self.browser)
        self.showFullScreen()

if __name__ == '__main__':
    dash_thread = threading.Thread(target=run_dash, daemon=True)
    dash_thread.start()
    time.sleep(3)  # Wait for Dash server to start
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(qt_app.exec_())