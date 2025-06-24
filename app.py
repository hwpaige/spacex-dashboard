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

# Cache for launch and weather data
launch_cache = {'data': None, 'timestamp': None}
weather_cache = {'data': {}, 'timestamp': {}}
CACHE_DURATION = timedelta(minutes=12)
WEATHER_CACHE_DURATION = timedelta(minutes=15)

# Fetch SpaceX launch data from LL2 API
def fetch_launches():
    global launch_cache
    current_time = datetime.now(pytz.UTC)

    if (launch_cache['data'] is not None and
            launch_cache['timestamp'] is not None and
            current_time - launch_cache['timestamp'] < CACHE_DURATION):
        logger.debug("Returning cached launch data")
        return launch_cache['data']

    try:
        upcoming = requests.get('https://ll.thespacedevs.com/2.3.0/launches/upcoming/?lsp__name=SpaceX&limit=5', timeout=5).json()['results']
        past = requests.get('https://ll.thespacedevs.com/2.3.0/launches/previous/?lsp__name=SpaceX&limit=3&ordering=-net', timeout=5).json()['results']
        launches = [
                       {
                           'mission': launch['name'],
                           'date': launch['net'].split('T')[0],
                           'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
                           'net': launch['net'],
                           'status': launch['status']['name'],
                           'rocket': launch['rocket']['configuration']['name'],
                           'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                           'pad': launch['pad']['name']
                       }
                       for launch in upcoming
                   ] + [
                       {
                           'mission': launch['name'],
                           'date': launch['net'].split('T')[0],
                           'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
                           'net': launch['net'],
                           'status': launch['status']['name'],
                           'rocket': launch['rocket']['configuration']['name'],
                           'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                           'pad': launch['pad']['name']
                       }
                       for launch in past
                   ]
        logger.debug(f"Fetched {len(launches)} launches from LL2 API")
        launch_cache['data'] = launches
        launch_cache['timestamp'] = current_time
        return launches
    except Exception as e:
        logger.error(f"LL2 API error: {e}")
        if launch_cache['data'] is not None:
            logger.debug("Returning cached launch data due to API failure")
            return launch_cache['data']
        return [
            {'mission': 'Transporter-14', 'date': '2025-06-22', 'time': '06:54:00', 'net': '2025-06-22T06:54:00Z', 'status': 'Go for Launch', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40'},
            {'mission': 'Axiom Mission 4', 'date': '2025-06-25', 'time': 'TBD', 'net': '2025-06-25T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Dragonfly (Titan)', 'date': '2025-07-01', 'time': 'TBD', 'net': '2025-07-01T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon Heavy', 'orbit': 'Heliocentric', 'pad': 'LC-39A'},
            {'mission': 'TRACERS', 'date': '2025-07-15', 'time': 'TBD', 'net': '2025-07-15T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'SLC-40'},
            {'mission': 'Crew-11', 'date': '2025-07-31', 'time': 'TBD', 'net': '2025-07-31T00:00:00Z', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Starship Flight 9', 'date': '2025-05-27', 'time': '14:30:00', 'net': '2025-05-27T14:30:00Z', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase'},
            {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'net': '2025-03-14T09:00:00Z', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Starship Flight 8', 'date': '2025-03-06', 'time': '15:45:00', 'net': '2025-03-06T15:45:00Z', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase'}
        ]

# Fetch weather data from Open-Meteo API
def fetch_weather(lat, lon, location):
    global weather_cache
    current_time = datetime.now(pytz.UTC)

    cache_key = f"{lat},{lon}"
    if (cache_key in weather_cache['data'] and
            cache_key in weather_cache['timestamp'] and
            current_time - weather_cache['timestamp'][cache_key] < WEATHER_CACHE_DURATION):
        logger.debug(f"Returning cached weather data for {location}")
        return weather_cache['data'][cache_key]

    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,cloud_cover&timezone=UTC"
        response = requests.get(url, timeout=5).json()
        now = datetime.now(pytz.UTC)
        hourly = response['hourly']
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
        weather_cache['data'][cache_key] = weather
        weather_cache['timestamp'][cache_key] = current_time
        return weather
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

# Initial launches
launches = fetch_launches()

# Process launch data for line chart
def prepare_chart_data(launches):
    df = pd.DataFrame(launches)
    df['date'] = pd.to_datetime(df['date'])
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
    return df_melt

# Create line chart
chart_data = prepare_chart_data(launches)
fig = px.line(
    chart_data,
    x='date',
    y='Cumulative Launches',
    color='Rocket',
    title=None,
    labels={'date': 'Date', 'Cumulative Launches': 'Cumulative Launches', 'Rocket': 'Rocket Type'},
    color_discrete_map={'Starship': '#FF5733', 'Falcon 9': '#33CFFF', 'Falcon Heavy': '#FFC107'}
)
fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font_color='var(--text-color)',
    xaxis=dict(
        title_font_size=12,
        tickfont_size=10,
        gridcolor='rgba(128,128,128,0.2)'
    ),
    yaxis=dict(
        title_font_size=12,
        tickfont_size=10,
        gridcolor='rgba(128,128,128,0.2)'
    ),
    legend=dict(
        font_size=10,
        orientation='h',
        yanchor='bottom',
        y=1.02,
        xanchor='center',
        x=0.5
    ),
    margin=dict(l=20, r=20, t=20, b=20),
    height=300
)
fig.update_traces(line=dict(width=2))

# Categorize launches
today = datetime(2025, 6, 23).date()
this_week_end = today + timedelta(days=7)
today_datetime = datetime(2025, 6, 23, 0, 0, tzinfo=pytz.UTC)

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
    'backgroundColor': 'var(--card-bg)',
    'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
    'fontFamily': 'D-DIN, sans-serif',
    'margin': '5px',
    'display': 'flex',
    'flexDirection': 'column'
}

title_style = {
    'fontSize': '14px',
    'fontWeight': 'normal',
    'textTransform': 'uppercase',
    'color': 'var(--text-color-secondary)',
    'letterSpacing': '1.5px',
    'marginBottom': '10px',
    'fontFamily': 'D-DIN, sans-serif',
    'position': 'sticky',
    'top': '0',
    'backgroundColor': 'var(--card-bg)',
    'zIndex': '10',
    'padding': '10px 15px',
    'borderBottom': '1px solid var(--text-color-secondary)'
}

launch_card_style = {
    'backgroundColor': 'var(--card-bg)',
    'borderRadius': '6px',
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
        dcc.Graph(id='chart1', figure=fig, style={'margin': '0', 'height': '100%'}),
        html.P('Cumulative Starship, Falcon 9, and Falcon Heavy launches.', style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'padding': '15px'})
    ], style={'overflowY': 'auto', 'flex': '1', 'display': 'flex', 'flexDirection': 'column'})
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
            'borderRadius': '0 0 8px 8px'
        },
        allow='encrypted-media; fullscreen'
    )
], style=column_style)

def render_launches(launches, timezone='America/Chicago'):
    tz = pytz.timezone(timezone)
    today_launches = sorted(
        [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() == today],
        key=lambda x: parse(x['net'])
    )
    this_week_launches = sorted(
        [l for l in launches if today < parse(l['net']).replace(tzinfo=pytz.UTC).date() <= this_week_end],
        key=lambda x: parse(x['net'])
    )
    later_launches = sorted(
        [l for l in launches if parse(l['net']).replace(tzinfo=pytz.UTC).date() > this_week_end],
        key=lambda x: parse(x['net'])
    )
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

column3 = html.Div([
    html.Div('Launches', style=title_style),
    dcc.Interval(id='interval', interval=720000, n_intervals=0),
    dcc.Store(id='location-store', data='Starbase'),
    html.Div(id='launch-table', children=render_launches(launches), style={'overflowY': 'auto', 'flex': '1'})
], style=column_style)

column4 = html.Div([
    html.Div('Videos', style=title_style),
    html.P('Starship Flight 7 video.', style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '0 15px 6px'}),
    html.Iframe(
        id='youtube-iframe',
        src='https://www.youtube.com/embed/Pn6e1O5bEyA?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1',
        style={
            'width': '100%',
            'height': '100%',
            'border': 'none',
            'borderRadius': '0 0 8px 8px'
        },
        allow='encrypted-media; autoplay; fullscreen; picture-in-picture'
    )
], style=column_style)

# Theme store and toggle
theme_store = dcc.Store(id='theme-store', data='dark')
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
        'width': '200px',
        'fontFamily': 'D-DIN, sans-serif',
        'fontSize': '11px',
        'backgroundColor': 'var(--bar-bg)',
        'padding': '2px',
        'borderRadius': '6px',
        'marginLeft': '10px'
    }
)
print(f"Location toggle data: {location_toggle.data}")  # Debug print
time_interval = dcc.Interval(id='time-interval', interval=1000, n_intervals=0)

# Get next launch for countdown
def get_next_launch():
    current_time = datetime.now(pytz.UTC)
    valid_launches = [l for l in launches if l['time'] != 'TBD' and parse(l['net']).replace(tzinfo=pytz.UTC) > current_time]
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

# Layout with MantineProvider
app.layout = dmc.MantineProvider(
    theme={"fontFamily": "D-DIN, sans-serif"},
    children=html.Div(
        id='root',
        children=[
            theme_store,
            time_interval,
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Col(column1, width=3),
                            dbc.Col(column2, width=3),
                            dbc.Col(column3, width=3),
                            dbc.Col(column4, width=3),
                        ],
                        style={'margin': '0', 'padding': '5px'}
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
                style={'width': '100vw', 'height': '100vh', 'margin': '0', 'padding': '0', 'overflow': 'hidden'}
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
     Input('location-store', 'data')]
)
def update_launches(n, location):
    global launches
    launches = fetch_launches()
    timezone = location_settings.get(location, {}).get('timezone', 'America/Chicago')
    return render_launches(launches, timezone)

@app.callback(
    Output('current-weather', 'children'),
    Input('location-store', 'data')
)
def update_weather(location):
    settings = location_settings.get(location, location_settings['Starbase'])
    weather = fetch_weather(settings['lat'], settings['lon'], location)
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
        console.log('Updating radar to location: ' + location + ' with URL: ' + radarLocations[location]);
        const iframe = document.getElementById('radar-iframe');
        if (iframe) {
            iframe.src = radarLocations[location] + '&rand=' + Math.random();
            iframe.contentWindow.location.reload();
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('radar-iframe', 'id'),
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
        self.setWindowTitle('Dash in PyQt')
        self.browser = QWebEngineView()
        settings = self.browser.settings()
        settings.setAttribute(settings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(settings.WebAttribute.FullScreenSupportEnabled, True)
        self.setCentralWidget(self.browser)
        self.browser.setUrl(QUrl('http://localhost:8050'))
        self.showFullScreen()

if __name__ == '__main__':
    dash_thread = threading.Thread(target=run_dash, daemon=True)
    dash_thread.start()
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(qt_app.exec_())