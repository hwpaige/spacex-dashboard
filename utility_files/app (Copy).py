import sys
import threading
import requests
from dash import Dash, html, dcc, Input, Output
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

# Column definitions
column1 = html.Div([
    html.Div('Launch Trends', style=title_style),
    html.Div([
        dcc.Graph(id='chart1', figure=fig, style={'margin': '0', 'height': 'calc(100% - 50px)'}),
        custom_legend
    ], style={'overflowY': 'auto', 'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'marginTop': '0'})
], style=column_style)

column2 = html.Div([
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
], style=column_style)

def render_launches(launches, timezone='America/Chicago', launch_type='upcoming'):
    tz = pytz.timezone(timezone)
    if launch_type == 'upcoming':
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

column3 = html.Div([
    html.Div([
        html.Span('Launches', style={'fontSize': '14px', 'fontWeight': 'normal', 'textTransform': 'uppercase', 'color': 'var(--text-color-secondary)', 'letterSpacing': '1.5px', 'fontFamily': 'D-DIN, sans-serif'}),
        dmc.SegmentedControl(
            id='launch-type-toggle',
            value='upcoming',
            data=[
                {'label': 'Upcoming', 'value': 'upcoming'},
                {'label': 'Past', 'value': 'past'}
            ],
            size='xs',
            style={'width': '130px', 'fontFamily': 'D-DIN, sans-serif', 'fontSize': '10px', 'height': '22px'}
        )
    ], style={**title_style, 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '0'}),
    dcc.Interval(id='interval', interval=720000, n_intervals=0),
    dcc.Store(id='location-store', data='Starbase'),
    html.Div(id='launch-table', children=render_launches(upcoming_launches), style={'overflowY': 'auto', 'flex': '1', 'marginTop': '0'})
], style=column_style)

column4 = html.Div([
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
], style=column_style)

# Theme store and toggles
theme_store = dcc.Store(id='theme-store', data='dark')
weather_store = dcc.Store(id='weather-store', data=initialize_weather())
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
time_interval = dcc.Interval(id='time-interval', interval=1000, n_intervals=0)
weather_interval = dcc.Interval(id='weather-interval', interval=5*60*1000, n_intervals=0)  # 5 minutes

# Get next launch for countdown
def get_next_launch():
    current_time = datetime.now(pytz.UTC)
    valid_launches = [l for l in upcoming_launches if l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
    if not valid_launches:
        return None
    return min(valid_launches, key=lambda x: parse(x['net']))

# Calculate countdown
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

# Get the most recent historical launch video
def get_historical_video():
    valid_launches = [l for l in previous_launches if l['video_url'] and l['video_url'].startswith('https://www.youtube.com/')]
    if not valid_launches:
        return None
    return max(valid_launches, key=lambda x: parse(x['net']))

# Layout with MantineProvider
app.layout = dmc.MantineProvider(
    theme={"fontFamily": "D-DIN, sans-serif"},
    children=html.Div(
        id='root',
        children=[
            theme_store,
            weather_store,
            time_interval,
            weather_interval,
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Col(column1, width=3, style={'borderRadius': '8px', '-webkit-border-radius': '8px', '-moz-border-radius': '8px'}),
                            dbc.Col(column2, width=3, style={'borderRadius': '8px', '-webkit-border-radius': '8px', '-moz-border-radius': '8px'}),
                            dbc.Col(column3, width=3, style={'borderRadius': '8px', '-webkit-border-radius': '8px', '-moz-border-radius': '8px'}),
                            dbc.Col(column4, width=3, style={'borderRadius': '8px', '-webkit-border-radius': '8px', '-moz-border-radius': '8px'}),
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
                                src='/assets/spacex-logo.png',
                                style={'width': '80px', 'margin': '0 10px'}
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
    Output('location-store', 'data'),
    Input('location-toggle', 'value')
)
def update_location_store(location):
    print(f"Location toggle set to: {location}")  # Debug print
    return location

@app.callback(
    Output('launch-table', 'children'),
    [Input('interval', 'n_intervals'),
     Input('location-store', 'data'),
     Input('launch-type-toggle', 'value')]
)
def update_launches(n, location, launch_type):
    launches_data = fetch_launches()
    if launch_type == 'upcoming':
        selected_launches = launches_data['upcoming']
    else:
        selected_launches = launches_data['previous']
    timezone = location_settings.get(location, {}).get('timezone', 'America/Chicago')
    return render_launches(selected_launches, timezone, launch_type)

@app.callback(
    Output('weather-store', 'data'),
    Input('weather-interval', 'n_intervals')
)
def update_weather_cache(n):
    return initialize_weather()

@app.callback(
    Output('current-weather', 'children'),
    [Input('location-store', 'data'),
     Input('weather-store', 'data')]
)
def update_weather(location, weather_data):
    weather = weather_data.get(location, fetch_weather(location_settings[location]['lat'], location_settings[location]['lon'], location))
    print(f"Updating weather for {location}: {weather}")  # Debug print
    return html.Span(
        f"Wind {weather['wind_speed_kts']:.1f} kts | {weather['wind_speed_ms']:.1f} m/s, {weather['wind_direction']}° | "
        f"Temp {weather['temperature_f']:.1f}°F | {weather['temperature_c']:.1f}°C | "
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
     Input('location-store', 'data')]
)

@app.callback(
    Output('countdown', 'children'),
    Input('time-interval', 'n_intervals')
)
def update_countdown(n):
    return calculate_countdown()

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
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(qt_app.exec_())
