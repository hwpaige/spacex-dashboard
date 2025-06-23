import sys
import threading
from dash import Dash, html, dcc, Input, Output, dash
import plotly.express as px
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import requests
from datetime import datetime, timedelta
import logging
from dateutil.parser import parse
import pytz

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
launch_cache = {'data': None, 'timestamp': None}
CACHE_DURATION = timedelta(minutes=12)

# Sample chart data
data = {'Category': ['A', 'B', 'C', 'D'], 'Values': [10, 20, 15, 25]}
fig = px.bar(data, x='Category', y='Values', title=None)

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

# Initial launches
launches = fetch_launches()

# Categorize launches
today = datetime(2025, 6, 23).date()
this_week_end = today + timedelta(days=7)
today_datetime = datetime(2025, 6, 23, 0, 10, tzinfo=pytz.UTC)
this_week_end_datetime = datetime.combine(this_week_end, datetime.min.time(), tzinfo=pytz.UTC)

# Styles with CSS variables
column_style = {
    'height': '85vh',
    'padding': '15px',
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
    'padding': '5px 0'
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
    html.Div('Chart', style=title_style),
    html.Div([
        dcc.Graph(id='chart1', figure=fig, style={'margin': '0'}),
        html.P('Sample chart widget.', style={'fontSize': '12px', 'color': 'var(--text-color-secondary)'})
    ], style={'overflowY': 'auto', 'flex': '1'})
], style=column_style)

column2 = html.Div([
    html.Div('Weather Radar', style=title_style),
    html.Iframe(
        id='radar-iframe',
        src='https://www.radaromega.com/radar?lat=25.9972&lon=-97.1553&zoom=8',
        style={
            'width': '100%',
            'flex': '1',
            'border': 'none',
            'borderRadius': '8px'
        }
    ),
    dmc.SegmentedControl(
        id='radar-theme-control',
        value='Dark',
        data=[
            {'label': 'Starbase', 'value': 'Starbase'},
            {'label': 'Cape', 'value': 'Cape'},
            {'label': 'Vandenberg', 'value': 'Vandenberg'},
            {'label': 'Light', 'value': 'Light'},
            {'label': 'Dark', 'value': 'Dark'}
        ],
        style={
            'marginTop': '10px',
            'width': '100%',
            'fontFamily': 'D-DIN, sans-serif'
        }
    )
], style={**column_style, 'paddingBottom': '50px'})

def render_launches(launches):
    cdt_tz = pytz.timezone('America/Chicago')
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
                f"CDT: {parse(launch['net']).astimezone(cdt_tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
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
                f"CDT: {parse(launch['net']).astimezone(cdt_tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
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
                f"CDT: {parse(launch['net']).astimezone(cdt_tz).strftime('%Y-%m-%d %H:%M:%S') if launch['time'] != 'TBD' else 'TBD'}",
                style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}
            ),
            html.P(f"Status: {launch['status']}", style={
                'fontSize': '12px',
                'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD', 'Go for Launch'] else 'var(--status-failure)',
                'margin': '0'
            })
        ], style=launch_card_style) for launch in later_launches]
    ], style={'padding': '0'})

column3 = html.Div([
    html.Div('Launches', style=title_style),
    dcc.Interval(id='interval', interval=720000, n_intervals=0),
    html.Div(id='launch-table', children=render_launches(launches), style={'overflowY': 'auto', 'flex': '1'})
], style=column_style)

column4 = html.Div([
    html.Div('Videos', style=title_style),
    html.Div(
        html.Iframe(
            src='https://www.youtube.com/embed/Pn6e1O5bEyA?rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1',
            style={
                'width': '100%',
                'height': '100%',
                'border': 'none',
                'borderRadius': '8px',
                'position': 'absolute',
                'top': '0',
                'left': '0'
            },
            allow='encrypted-media; autoplay; fullscreen; picture-in-picture'
        ),
        style={
            'position': 'relative',
            'width': '100%',
            'height': '95%',
            'overflow': 'hidden',
            'borderRadius': '8px'
        }
    ),
    html.P('Starship Flight 7 video.', style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'marginTop': '5px'})
], style=column_style)

# Theme store
theme_store = dcc.Store(id='theme-store', data='dark')
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

# Layout
app.layout = html.Div(
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
                                html.Span('Weather: Sunny, 25°C', style={'fontSize': '12px'})
                            ],
                            style={
                                'display': 'flex',
                                'alignItems': 'center',
                                'height': '5vh',
                                'flex': '1',
                                'minWidth': '400px',
                                'backgroundColor': 'var(--bar-bg)',
                                'borderRadius': '20px',
                                'padding': '0 15px',
                                'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
                                'fontFamily': 'D-DIN, sans-serif',
                                'marginRight': '10px'
                            }
                        ),
                        html.Img(
                            src='/assets/spacex-logo.png',
                            style={'width': '80px', 'opacity': '0.3', 'margin': '0 10px'}
                        ),
                        html.Div(
                            id='right-bar',
                            children=[
                                html.Span(id='countdown', style={'fontSize': '12px', 'marginRight': '10px'})
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
                                'padding': '0 15px',
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

# Callbacks
@app.callback(
    Output('theme-store', 'data'),
    Output('radar-iframe', 'src'),
    Input('radar-theme-control', 'value')
)
def update_radar_and_theme(value):
    radar_urls = {
        'Starbase': 'https://www.radaromega.com/radar?lat=25.9972&lon=-97.1553&zoom=8',
        'Cape': 'https://www.radaromega.com/radar?lat=28.4889&lon=-80.5774&zoom=8',
        'Vandenberg': 'https://www.radaromega.com/radar?lat=34.7320&lon=-120.5681&zoom=8'
    }
    if value in ['Light', 'Dark']:
        theme = 'light' if value == 'Light' else 'dark'
        return theme, dash.no_update
    return dash.no_update, radar_urls.get(value, radar_urls['Starbase'])

@app.callback(
    Output('root', 'className'),
    Input('theme-store', 'data')
)
def update_theme_class(theme):
    return f'theme-{theme}'

app.clientside_callback(
    """
    function(n) {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        return `${hours}:${minutes}:${seconds}`;
    }
    """,
    Output('current-time', 'children'),
    Input('time-interval', 'n_intervals')
)

@app.callback(
    Output('launch-table', 'children'),
    Input('interval', 'n_intervals')
)
def update_launches(n):
    global launches
    launches = fetch_launches()
    return render_launches(launches)

@app.callback(
    Output('countdown', 'children'),
    Input('time-interval', 'n_intervals')
)
def update_countdown(n):
    return calculate_countdown()

def run_dash():
    app.run(host='0.0.0.0', port=8050, debug=True, use_reloader=False)

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