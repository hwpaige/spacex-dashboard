#!/usr/bin/env python3
"""
Interactive Plotly Chart Generator for F1 Data
Generates fully interactive Plotly charts as HTML for display in PyQt WebEngineView
"""

import plotly.graph_objects as go
from plotly.offline import plot
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional


def generate_f1_standings_chart(driver_data: List[Dict], chart_type: str = 'line', theme: str = 'dark') -> str:
    """
    Generate interactive F1 driver standings chart as HTML string

    Args:
        driver_data: List of driver data dictionaries with keys: 'driver', 'points', 'round'
        chart_type: 'line' or 'bar'
        theme: 'dark' or 'light'

    Returns:
        HTML string containing the interactive chart
    """
    fig = go.Figure()

    # Color palette matching your app's theme
    if theme == 'dark':
        colors = ['#00D4FF', '#FF6B6B', '#4ECDC4', '#FFD93D', '#FF8E53', '#A78BFA', '#F472B6', '#60A5FA']
        bg_color = 'rgba(42,46,46,1)'  # Match your card background
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
    else:
        colors = ['#0066CC', '#FF4444', '#00AA88', '#FFAA00', '#FF6600', '#8B5CF6', '#EC4899', '#3B82F6']
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'

    # Process data for cumulative standings
    df = pd.DataFrame(driver_data)
    if not df.empty:
        # Group by driver and round, sum points
        standings = df.groupby(['driver', 'round'])['points'].sum().reset_index()

        # Create cumulative standings
        standings = standings.sort_values(['driver', 'round'])
        standings['cumulative_points'] = standings.groupby('driver')['points'].cumsum()

        # Get unique drivers and rounds
        drivers = standings['driver'].unique()
        rounds = sorted(standings['round'].unique())

        for i, driver in enumerate(drivers):
            driver_standings = standings[standings['driver'] == driver]

            if chart_type == 'line':
                fig.add_trace(go.Scatter(
                    x=driver_standings['round'],
                    y=driver_standings['cumulative_points'],
                    mode='lines+markers',
                    name=driver,
                    line=dict(
                        color=colors[i % len(colors)],
                        width=3
                    ),
                    marker=dict(
                        size=8,
                        symbol='circle'
                    ),
                    hovertemplate=f'<b>{driver}</b><br>Round: %{{x}}<br>Points: %{{y}}<extra></extra>'
                ))
            elif chart_type == 'area':
                fig.add_trace(go.Scatter(
                    x=driver_standings['round'],
                    y=driver_standings['cumulative_points'],
                    mode='lines',
                    name=driver,
                    fill='tozeroy',
                    line=dict(
                        color=colors[i % len(colors)],
                        width=2
                    ),
                    hovertemplate=f'<b>{driver}</b><br>Round: %{{x}}<br>Points: %{{y}}<extra></extra>'
                ))
            elif chart_type == 'bar':
                # For bar charts, show points per round
                fig.add_trace(go.Bar(
                    x=driver_standings['round'],
                    y=driver_standings['points'],  # Use round points for bars
                    name=driver,
                    marker_color=colors[i % len(colors)],
                    hovertemplate=f'<b>{driver}</b><br>Round: %{{x}}<br>Points: %{{y}}<extra></extra>'
                ))

    # Update layout
    fig.update_layout(
        title=None,
        xaxis=dict(
            title='Round',
            showgrid=True,
            gridcolor=grid_color,
            tickcolor=text_color,
            tickfont=dict(color=text_color, size=10),
            title_font=dict(color=text_color, size=12)
        ),
        yaxis=dict(
            title='Points',
            showgrid=True,
            gridcolor=grid_color,
            tickcolor=text_color,
            tickfont=dict(color=text_color, size=10),
            title_font=dict(color=text_color, size=12)
        ),
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color),
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=25, r=25, t=15, b=40),
        height=None,  # Responsive height
        width=None
    )

    # Add range slider for time series
    # if chart_type == 'line':
    #     fig.update_xaxes(rangeslider_visible=True)

    # Generate HTML with embedded Plotly.js
    html_div = plot(fig, output_type='div', include_plotlyjs=True, config={
        'displayModeBar': False,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d'],
        'responsive': True
    })

    # Wrap in full HTML with dark background
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: {bg_color};
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}
            .plotly-notifier {{
                display: none !important;
            }}
        </style>
    </head>
    <body>
        {html_div}
    </body>
    </html>
    """

    return full_html


def generate_f1_telemetry_chart(telemetry_data: List[Dict], theme: str = 'dark', driver_num: Optional[int] = None) -> str:
    """
    Generate F1 telemetry charts (speed, RPM, throttle) as HTML string
    """
    title_suffix = f" (Driver {driver_num})" if driver_num else ""
    if not telemetry_data:
        return _get_placeholder_html(f"F1 Telemetry Data{title_suffix}", "No telemetry data available for this session.", theme)

    df = pd.DataFrame(telemetry_data)
    if df.empty or 'speed' not in df.columns:
        return _get_placeholder_html(f"F1 Telemetry Data{title_suffix}", "No telemetry data available.", theme)

    df['date'] = pd.to_datetime(df['date'])
    
    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
        colors = ['#00D4FF', '#FF6B6B', '#4ECDC4']
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'
        colors = ['#0066CC', '#FF4444', '#00AA88']

    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(f"Speed & DRS{title_suffix}", "RPM & Gear", "Throttle & Brake"),
        vertical_spacing=0.1,
        shared_xaxes=True
    )

    # Speed & DRS
    fig.add_trace(go.Scatter(x=df['date'], y=df['speed'], name="Speed", line=dict(color=colors[0], width=2)), row=1, col=1)
    if 'drs' in df.columns:
        fig.add_trace(go.Scatter(x=df['date'], y=df['drs'], name="DRS", line=dict(color=colors[2], width=1, dash='dash')), row=1, col=1)

    # RPM & Gear
    fig.add_trace(go.Scatter(x=df['date'], y=df['rpm'], name="RPM", line=dict(color=colors[1], width=2)), row=2, col=1)
    if 'n_gear' in df.columns:
        # Use a secondary y-axis for gear if possible, but for simplicity here we just add it
        fig.add_trace(go.Scatter(x=df['date'], y=df['n_gear'] * 1000, name="Gear (x1000)", line=dict(color=colors[2], width=1)), row=2, col=1)

    # Throttle & Brake
    fig.add_trace(go.Scatter(x=df['date'], y=df['throttle'], name="Throttle", line=dict(color=colors[0], width=2)), row=3, col=1)
    if 'brake' in df.columns:
        fig.add_trace(go.Scatter(x=df['date'], y=df['brake'], name="Brake", line=dict(color=colors[1], width=2)), row=3, col=1)

    fig.update_layout(
        height=None,  # Responsive height
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color, size=10),
        margin=dict(l=40, r=20, t=30, b=40),
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )

    fig.update_xaxes(showgrid=True, gridcolor=grid_color)
    fig.update_yaxes(showgrid=True, gridcolor=grid_color)

    return _generate_full_html(fig, bg_color)


def generate_f1_weather_chart(weather_data: List[Dict], theme: str = 'dark') -> str:
    """
    Generate F1 weather charts as HTML string
    """
    if not weather_data:
        return _get_placeholder_html("F1 Weather Data", "No weather data available for this session.", theme)

    df = pd.DataFrame(weather_data)
    if df.empty:
        return _get_placeholder_html("F1 Weather Data", "No weather data available.", theme)

    df['date'] = pd.to_datetime(df['date'])
    
    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
        colors = ['#00D4FF', '#FF6B6B', '#4ECDC4']
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'
        colors = ['#0066CC', '#FF4444', '#00AA88']

    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Temperatures (°C)", "Humidity & Pressure"),
        vertical_spacing=0.15,
        shared_xaxes=True
    )

    # Air Temperature
    fig.add_trace(
        go.Scatter(x=df['date'], y=df['air_temperature'], name="Air Temp",
                   line=dict(color=colors[0], width=2), mode='lines'),
        row=1, col=1
    )

    # Track Temperature
    fig.add_trace(
        go.Scatter(x=df['date'], y=df['track_temperature'], name="Track Temp",
                   line=dict(color=colors[1], width=2), mode='lines'),
        row=1, col=1
    )

    # Humidity
    fig.add_trace(
        go.Scatter(x=df['date'], y=df['humidity'], name="Humidity (%)",
                   line=dict(color=colors[2], width=2), mode='lines'),
        row=2, col=1
    )

    # Update layout
    fig.update_layout(
        height=None,  # Responsive height
        width=None,
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color, size=10),
        margin=dict(l=40, r=20, t=30, b=40),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )

    fig.update_xaxes(showgrid=True, gridcolor=grid_color, tickfont=dict(size=9))
    fig.update_yaxes(showgrid=True, gridcolor=grid_color, tickfont=dict(size=9))

    return _generate_full_html(fig, bg_color)


def generate_f1_wind_polar_chart(weather_data: List[Dict], theme: str = 'dark') -> str:
    """
    Generate F1 polar wind chart (direction and speed) as HTML string
    matching the original app's style.
    """
    if not weather_data:
        return _get_placeholder_html("F1 Wind Data", "No weather data available for this session.", theme)

    df = pd.DataFrame(weather_data)
    if df.empty or 'wind_direction' not in df.columns:
        return _get_placeholder_html("F1 Wind Data", "No wind data available.", theme)

    df['date'] = pd.to_datetime(df['date'])
    # Original app style: r is time of day, theta is wind direction
    df['time_digits'] = df['date'].dt.strftime('%H:%M')
    
    # Theme configuration
    if theme == 'dark':
        bg_color = '#2b2d30'  # Match original app background
        text_color = '#c9c9c9'
        grid_color = '#444444'
        trace_color = '#ef553b'
    else:
        bg_color = 'rgba(240,240,240,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'
        trace_color = '#0066CC'

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=df['time_digits'],
        theta=df['wind_direction'],
        mode='markers',
        name='Wind Direction',
        marker=dict(
            color=trace_color,
            size=6
        ),
        hovertemplate="Direction: %{theta}°<br>Time: %{r}<br>Speed: %{text} m/s<extra></extra>",
        text=df['wind_speed']
    ))

    fig.update_layout(
        height=None,  # Responsive height
        polar=dict(
            bgcolor=bg_color,
            radialaxis=dict(
                showticklabels=True, 
                tickfont=dict(size=9, color=text_color), 
                gridcolor=grid_color,
                nticks=5
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color=text_color), 
                rotation=90, 
                direction="clockwise", 
                gridcolor=grid_color
            )
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color, size=10),
        margin=dict(l=10, r=10, t=10, b=10),  # Tighten margins to remove empty space
        showlegend=False
    )

    return _generate_full_html(fig, bg_color)


def generate_f1_track_telemetry_chart(track_data: Dict, telemetry_data: List[Dict], theme: str = 'dark', driver_num: Optional[int] = None) -> str:
    """
    Generate F1 telemetry visualization over the race track
    """
    title_suffix = f" (Driver {driver_num})" if driver_num else ""
    if not track_data or not telemetry_data:
        return _get_placeholder_html(f"F1 Track Telemetry{title_suffix}", "No track or telemetry data available.", theme)

    fig = go.Figure()

    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        track_outline_color = 'rgba(255,255,255,0.2)'
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        track_outline_color = 'rgba(0,0,0,0.2)'

    # 1. Plot the track outline
    if 'x' in track_data and 'y' in track_data:
        fig.add_trace(go.Scatter(
            x=track_data['x'],
            y=track_data['y'],
            mode='lines',
            line=dict(color=track_outline_color, width=4),
            hoverinfo='skip',
            name='Track'
        ))

    # 2. Plot telemetry points
    df = pd.DataFrame(telemetry_data)
    if not df.empty and 'x' in df.columns and 'y' in df.columns:
        # Sort by date to ensure proper color flow if using lines
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')

        fig.add_trace(go.Scatter(
            x=df['x'],
            y=df['y'],
            mode='markers',
            marker=dict(
                color=df['speed'] if 'speed' in df.columns else None,
                colorscale='Inferno',
                size=5,
                showscale=True,
                colorbar=dict(title=f"Speed{title_suffix}", titleside="right")
            ),
            text=[f"Driver: {driver_num}<br>Speed: {s} km/h<br>RPM: {r}<br>Gear: {g}" for s, r, g in zip(
                df.get('speed', ['N/A']*len(df)), 
                df.get('rpm', ['N/A']*len(df)), 
                df.get('n_gear', ['N/A']*len(df))
            )],
            hoverinfo='text',
            name='Telemetry'
        ))

    fig.update_layout(
        height=None,  # Responsive height
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor='y', scaleratio=1),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor='x', scaleratio=1),
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color),
        margin=dict(l=20, r=20, t=30, b=20),
        showlegend=False
    )

    return _generate_full_html(fig, bg_color)


def _get_placeholder_html(title: str, message: str, theme: str) -> str:
    """Generate placeholder HTML for missing data"""
    bg_color = 'rgba(42,46,46,1)' if theme == 'dark' else 'rgba(240,240,240,1)'
    text_color = 'white' if theme == 'dark' else 'black'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background-color: {bg_color};
                color: {text_color};
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                text-align: center;
                display: flex;
                flex-direction: column;
                justify-content: center;
                height: 100vh;
            }}
            h2 {{ margin-top: 0; }}
        </style>
    </head>
    <body>
        <h2>{title}</h2>
        <p>{message}</p>
    </body>
    </html>
    """


def _generate_full_html(fig: go.Figure, bg_color: str) -> str:
    """Helper to generate full HTML from figure"""
    html_div = plot(fig, output_type='div', include_plotlyjs=True, config={
        'displayModeBar': False,
        'displaylogo': False,
        'responsive': True
    })

    return f"""
    <!DOCTYPE html>
    <html style="height: 100%; margin: 0; padding: 0;">
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: {bg_color};
                overflow: hidden;
                height: 100%;
                width: 100%;
                display: flex;
                flex-direction: column;
            }}
            .plotly-notifier {{ display: none !important; }}
            .plotly-graph-div {{
                flex: 1;
                width: 100% !important;
                height: 100% !important;
            }}
        </style>
    </head>
    <body>
        {html_div}
    </body>
    </html>
    """


def generate_f1_positions_chart(positions_data: List[Dict], theme: str = 'dark') -> str:
    """
    Generate F1 driver positions over time chart as HTML string
    """
    if not positions_data:
        return _get_placeholder_html("F1 Driver Positions", "No position data available for this session.", theme)

    df = pd.DataFrame(positions_data)
    if df.empty:
        return _get_placeholder_html("F1 Driver Positions", "No position data available.", theme)

    df['date'] = pd.to_datetime(df['date'])
    
    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
        colors = ['#00D4FF', '#FF6B6B', '#4ECDC4', '#FFD93D', '#FF8E53', '#A78BFA', '#F472B6', '#60A5FA']
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'
        colors = ['#0066CC', '#FF4444', '#00AA88', '#FFAA00', '#FF6600', '#8B5CF6', '#EC4899', '#3B82F6']

    fig = go.Figure()

    # Get unique drivers and sort them by their final position
    drivers = df['driver_number'].unique()
    
    for i, driver in enumerate(drivers):
        driver_df = df[df['driver_number'] == driver].sort_values('date')
        
        fig.add_trace(go.Scatter(
            x=driver_df['date'],
            y=driver_df['position'],
            mode='lines+markers',
            name=f"Driver {driver}",
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=4),
            hovertemplate=f"Driver {driver}<br>Time: %{{x}}<br>Position: %{{y}}<extra></extra>"
        ))

    fig.update_layout(
        height=None,  # Responsive height
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color, size=10),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            title="Time",
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(size=9)
        ),
        yaxis=dict(
            title="Position",
            autorange="reversed",
            showgrid=True,
            gridcolor=grid_color,
            dtick=1,
            tickfont=dict(size=9)
        ),
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=8)
        )
    )

    return _generate_full_html(fig, bg_color)


def generate_f1_laps_chart(laps_data: List[Dict], theme: str = 'dark') -> str:
    """
    Generate F1 lap time distributions chart as HTML string
    """
    if not laps_data:
        return _get_placeholder_html("F1 Lap Times", "No lap data available for this session.", theme)

    df = pd.DataFrame(laps_data)
    if df.empty or 'lap_duration' not in df.columns:
        return _get_placeholder_html("F1 Lap Times", "No lap time data available.", theme)

    # Convert lap_duration to seconds if it's not already
    # OpenF1 returns duration in seconds (float)
    
    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
        colors = ['#00D4FF', '#FF6B6B', '#4ECDC4', '#FFD93D', '#FF8E53', '#A78BFA', '#F472B6', '#60A5FA']
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'
        colors = ['#0066CC', '#FF4444', '#00AA88', '#FFAA00', '#FF6600', '#8B5CF6', '#EC4899', '#3B82F6']

    fig = go.Figure()

    # Get unique drivers and sort them by median lap time
    drivers = df['driver_number'].unique()
    median_laps = []
    for d in drivers:
        median_laps.append({'driver': d, 'median': df[df['driver_number'] == d]['lap_duration'].median()})
    
    sorted_drivers_info = sorted(median_laps, key=lambda x: x['median'] if pd.notnull(x['median']) else 999)
    sorted_drivers = [d['driver'] for d in sorted_drivers_info]

    for i, driver in enumerate(sorted_drivers):
        driver_laps = df[df['driver_number'] == driver]['lap_duration'].dropna()
        if driver_laps.empty: continue
        
        fig.add_trace(go.Violin(
            x=driver_laps,
            name=f"D{driver}",
            line_color=colors[i % len(colors)],
            side='positive',
            width=2,
            points=False,
            orientation='h',
            meanline_visible=True
        ))

    fig.update_layout(
        height=None,  # Responsive height
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color, size=10),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            title="Lap Time (seconds)",
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(size=9)
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickfont=dict(size=8)
        ),
        showlegend=False,
        hovermode='closest'
    )

    return _generate_full_html(fig, bg_color)


def generate_f1_track_map(track_data: Dict, theme: str = 'dark') -> str:
    """
    Generate interactive F1 track map using Plotly

    Args:
        track_data: Dictionary with 'x', 'y' coordinates and track info
        theme: 'dark' or 'light'

    Returns:
        HTML string containing the interactive track map
    """
    fig = go.Figure()

    if theme == 'dark':
        track_color = '#00D4FF'
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
    else:
        track_color = '#0066CC'
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'

    # Add track outline
    if 'x' in track_data and 'y' in track_data:
        fig.add_trace(go.Scatter(
            x=track_data['x'],
            y=track_data['y'],
            mode='lines',
            name='Track',
            line=dict(color=track_color, width=3),
            hoverinfo='skip'
        ))

    # Update layout for track map
    fig.update_layout(
        title=None,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor='y',
            scaleratio=1
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor='x',
            scaleratio=1
        ),
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color),
        margin=dict(l=20, r=20, t=30, b=20),
        showlegend=False,
        height=None,  # Responsive height
        width=None
    )

    # Generate HTML
    html_div = plot(fig, output_type='div', include_plotlyjs=True, config={
        'displayModeBar': False,
        'responsive': True
    })

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: {bg_color};
            }}
            .plotly-notifier {{
                display: none !important;
            }}
        </style>
    </head>
    <body>
        {html_div}
    </body>
    </html>
    """

    return full_html


def generate_f1_strategy_chart(stints_data: List[Dict], pits_data: List[Dict], theme: str = 'dark') -> str:
    """
    Generate F1 stint and pit strategy chart as HTML string
    """
    if not stints_data:
        return _get_placeholder_html("F1 Strategy", "No strategy data available for this session.", theme)

    stints_df = pd.DataFrame(stints_data)
    pits_df = pd.DataFrame(pits_data) if pits_data else pd.DataFrame()

    # Theme configuration
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        paper_bg = 'rgba(0,0,0,0)'
        text_color = 'white'
        grid_color = 'rgba(255,255,255,0.1)'
    else:
        bg_color = 'rgba(240,240,240,1)'
        paper_bg = 'rgba(255,255,255,1)'
        text_color = 'black'
        grid_color = 'rgba(0,0,0,0.1)'

    compound_colors = {
        "SOFT": "#FF3333",
        "MEDIUM": "#FFFF33",
        "HARD": "#FFFFFF",
        "INTERMEDIATE": "#33FF33",
        "WET": "#3333FF",
        "UNKNOWN": "#888888"
    }

    fig = go.Figure()

    # Get unique drivers and sort them
    drivers = sorted(stints_df['driver_number'].unique())

    for driver in drivers:
        driver_stints = stints_df[stints_df['driver_number'] == driver]
        
        for stint in driver_stints.itertuples():
            compound = getattr(stint, 'compound', 'UNKNOWN')
            color = compound_colors.get(compound, compound_colors["UNKNOWN"])
            
            # Add stint trace
            fig.add_trace(go.Scatter(
                x=[stint.lap_start, stint.lap_end],
                y=[driver, driver],
                mode='lines+markers',
                name=f"D{driver} {compound}",
                line=dict(color=color, width=6),
                marker=dict(size=8, symbol='square'),
                showlegend=False,
                hovertemplate=f"Driver {driver}<br>Laps: {stint.lap_start}-{stint.lap_end}<br>Compound: {compound}<extra></extra>"
            ))

        # Add pit stops
        if not pits_df.empty and 'driver_number' in pits_df.columns:
            driver_pits = pits_df[pits_df['driver_number'] == driver]
            if not driver_pits.empty:
                fig.add_trace(go.Scatter(
                    x=driver_pits['lap_number'],
                    y=[driver] * len(driver_pits),
                    mode='markers',
                    name='Pit Stop',
                    marker=dict(color='white', size=10, symbol='x'),
                    showlegend=False,
                    hovertemplate=f"Driver {driver}<br>Pit Stop at Lap %{{x}}<extra></extra>"
                ))

    fig.update_layout(
        height=None,  # Responsive height
        plot_bgcolor=bg_color,
        paper_bgcolor=paper_bg,
        font=dict(color=text_color, size=10),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            title="Lap Number",
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(size=9)
        ),
        yaxis=dict(
            title="Driver Number",
            showgrid=True,
            gridcolor=grid_color,
            tickfont=dict(size=9),
            autorange="reversed"
        ),
        hovermode='closest'
    )

    return _generate_full_html(fig, bg_color)


# Example usage function
def demo_f1_charts():
    """Demo function showing how to use the chart generators"""
    # Sample F1 standings data
    sample_data = [
        {'driver': 'Max Verstappen', 'round': 1, 'points': 25},
        {'driver': 'Max Verstappen', 'round': 2, 'points': 18},
        {'driver': 'Lewis Hamilton', 'round': 1, 'points': 18},
        {'driver': 'Lewis Hamilton', 'round': 2, 'points': 25},
        {'driver': 'Charles Leclerc', 'round': 1, 'points': 15},
        {'driver': 'Charles Leclerc', 'round': 2, 'points': 12},
    ]

    # Generate interactive chart
    html_chart = generate_f1_standings_chart(sample_data, chart_type='line', theme='dark')

    # Save to file for testing
    with open('f1_chart_demo.html', 'w', encoding='utf-8') as f:
        f.write(html_chart)

    print("Interactive F1 chart saved to f1_chart_demo.html")
    return html_chart


if __name__ == "__main__":
    demo_f1_charts()