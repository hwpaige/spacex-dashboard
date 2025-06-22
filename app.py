import sys
import threading
from dash import Dash, html, dcc, Input, Output
import plotly.express as px
import dash_bootstrap_components as dbc
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import requests
from datetime import datetime, timedelta
import logging

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

# Sample chart data
data = {'Category': ['A', 'B', 'C', 'D'], 'Values': [10, 20, 15, 25]}
fig = px.bar(data, x='Category', y='Values', title=None)

# Fetch SpaceX launch data from LL2 API
def fetch_launches():
    try:
        upcoming = requests.get('https://ll.thespacedevs.com/2.3.0/launches/upcoming/?lsp__name=SpaceX&limit=5', timeout=5).json()['results']
        past = requests.get('https://ll.thespacedevs.com/2.3.0/launches/previous/?lsp__name=SpaceX&limit=3&ordering=-net', timeout=5).json()['results']
        launches = [
                       {
                           'mission': launch['name'],
                           'date': launch['net'].split('T')[0],
                           'time': launch['net'].split('T')[1].split('Z')[0] if 'T' in launch['net'] else 'TBD',
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
                           'status': launch['status']['name'],
                           'rocket': launch['rocket']['configuration']['name'],
                           'orbit': launch['mission']['orbit']['name'] if launch['mission'] and 'orbit' in launch['mission'] else 'Unknown',
                           'pad': launch['pad']['name']
                       }
                       for launch in past
                   ]
        logger.debug(f"Fetched {len(launches)} launches from LL2 API")
        return launches
    except Exception as e:
        logger.error(f"LL2 API error: {e}")
        return [
            {'mission': 'Transporter-14', 'date': '2025-06-22', 'time': '06:54:00', 'status': 'Go', 'rocket': 'Falcon 9', 'orbit': 'Sun-Synchronous', 'pad': 'SLC-40'},
            {'mission': 'Axiom Mission 4', 'date': '2025-06-25', 'time': 'TBD', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Dragonfly (Titan)', 'date': '2025-07-01', 'time': 'TBD', 'status': 'TBD', 'rocket': 'Falcon Heavy', 'orbit': 'Heliocentric', 'pad': 'LC-39A'},
            {'mission': 'TRACERS', 'date': '2025-07-15', 'time': 'TBD', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'SLC-40'},
            {'mission': 'Crew-11', 'date': '2025-07-31', 'time': 'TBD', 'status': 'TBD', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Starship Flight 9', 'date': '2025-05-27', 'time': '14:30:00', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase'},
            {'mission': 'Crew-10', 'date': '2025-03-14', 'time': '09:00:00', 'status': 'Success', 'rocket': 'Falcon 9', 'orbit': 'Low Earth Orbit', 'pad': 'LC-39A'},
            {'mission': 'Starship Flight 8', 'date': '2025-03-06', 'time': '15:45:00', 'status': 'Failure', 'rocket': 'Starship', 'orbit': 'Suborbital', 'pad': 'Starbase'}
        ]

# Initial launches
launches = fetch_launches()

# Categorize launches
today = datetime(2025, 6, 22).date()
this_week_end = today + timedelta(days=7)
today_launches = [l for l in launches if l['date'] == today.strftime('%Y-%m-%d')]
this_week_launches = [l for l in launches if today.strftime('%Y-%m-%d') < l['date'] <= this_week_end.strftime('%Y-%m-%d')]
later_launches = [l for l in launches if l['date'] > this_week_end.strftime('%Y-%m-%d') or l['date'] < today.strftime('%Y-%m-%d')]

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
    html.Div('Controls', style=title_style),
    html.Div([
        dcc.Dropdown(
            id='dropdown1',
            options=[{'label': f'Option {i}', 'value': i} for i in range(1, 5)],
            value=1,
            style={'fontFamily': 'D-DIN, sans-serif'}
        ),
        html.P('Select an option.', style={'fontSize': '12px', 'color': 'var(--text-color-secondary)'})
    ], style={'overflowY': 'auto', 'flex': '1'})
], style=column_style)

def render_launches(launches):
    today_launches = [l for l in launches if l['date'] == today.strftime('%Y-%m-%d')]
    this_week_launches = [l for l in launches if today.strftime('%Y-%m-%d') < l['date'] <= this_week_end.strftime('%Y-%m-%d')]
    later_launches = [l for l in launches if l['date'] > this_week_end.strftime('%Y-%m-%d') or l['date'] < today.strftime('%Y-%m-%d')]
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
            html.P(f"Date: {launch['date']} {launch['time']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
            html.P(f"Status: {launch['status']}", style={
                'fontSize': '12px',
                'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD'] else 'var(--status-failure)',
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
            html.P(f"Date: {launch['date']} {launch['time']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
            html.P(f"Status: {launch['status']}", style={
                'fontSize': '12px',
                'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD'] else 'var(--status-failure)',
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
            html.P(f"Date: {launch['date']} {launch['time']}", style={'fontSize': '12px', 'color': 'var(--text-color-secondary)', 'margin': '5px 0'}),
            html.P(f"Status: {launch['status']}", style={
                'fontSize': '12px',
                'color': 'var(--status-success)' if launch['status'] in ['Success', 'Go', 'TBD'] else 'var(--status-failure)',
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

# Theme store and toggle
theme_store = dcc.Store(id='theme-store', data='light')
dark_mode_toggle = dbc.Switch(id='dark-mode-toggle', label='Dark Mode', value=False)
time_interval = dcc.Interval(id='time-interval', interval=1000, n_intervals=0)

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
                    id='bottom-bar',
                    children=[
                        html.Div(id='left-info', children=[
                            html.Span(id='current-time', style={'marginRight': '10px'}),
                            html.Span('Weather: Sunny, 25°C')  # Placeholder
                        ]),
                        html.Img(
                            src='/assets/spacex-logo.png',
                            style={'width': '80px', 'opacity': '0.3'}
                        ),
                        html.Div(id='right-info', children=[dark_mode_toggle])
                    ],
                    style={
                        'display': 'flex',
                        'justifyContent': 'space-between',
                        'alignItems': 'center',
                        'height': '5vh',
                        'width': '100%',
                        'backgroundColor': 'var(--bar-bg)',
                        'borderRadius': '20px',
                        'padding': '0 20px',
                        'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
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
    Input('dark-mode-toggle', 'value')
)
def update_theme(toggle_value):
    return 'dark' if toggle_value else 'light'

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
    return render_launches(fetch_launches())

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