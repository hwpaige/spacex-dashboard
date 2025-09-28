#!/usr/bin/env python3
"""
Interactive Plotly Chart Generator for F1 Data
Generates fully interactive Plotly charts as HTML for display in PyQt WebEngineView
"""

import plotly.graph_objects as go
from plotly.offline import plot
import pandas as pd
import numpy as np
from typing import List, Dict, Any


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
        height=200,
        width=350
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


def generate_f1_telemetry_chart(theme: str = 'dark') -> str:
    """
    Generate F1 telemetry charts (speed, RPM, throttle) as HTML string
    Placeholder - requires telemetry data
    """
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        text_color = 'white'
    else:
        bg_color = 'rgba(240,240,240,1)'
        text_color = 'black'

    html = f"""
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
            }}
        </style>
    </head>
    <body>
        <h2>F1 Telemetry Data</h2>
        <p>Telemetry plots require live session data from OpenF1 API.</p>
        <p>This feature is not yet implemented in the dashboard.</p>
    </body>
    </html>
    """
    return html


def generate_f1_weather_chart(theme: str = 'dark') -> str:
    """
    Generate F1 weather charts as HTML string
    Placeholder - requires weather data
    """
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        text_color = 'white'
    else:
        bg_color = 'rgba(240,240,240,1)'
        text_color = 'black'

    html = f"""
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
            }}
        </style>
    </head>
    <body>
        <h2>F1 Weather Data</h2>
        <p>Weather plots require live session data from OpenF1 API.</p>
        <p>This feature is not yet implemented in the dashboard.</p>
    </body>
    </html>
    """
    return html


def generate_f1_positions_chart(theme: str = 'dark') -> str:
    """
    Generate F1 driver positions over time chart as HTML string
    Placeholder - requires position data
    """
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        text_color = 'white'
    else:
        bg_color = 'rgba(240,240,240,1)'
        text_color = 'black'

    html = f"""
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
            }}
        </style>
    </head>
    <body>
        <h2>F1 Driver Positions</h2>
        <p>Position plots require live session data from OpenF1 API.</p>
        <p>This feature is not yet implemented in the dashboard.</p>
    </body>
    </html>
    """
    return html


def generate_f1_laps_chart(theme: str = 'dark') -> str:
    """
    Generate F1 lap time distributions chart as HTML string
    Placeholder - requires lap data
    """
    if theme == 'dark':
        bg_color = 'rgba(42,46,46,1)'
        text_color = 'white'
    else:
        bg_color = 'rgba(240,240,240,1)'
        text_color = 'black'

    html = f"""
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
            }}
        </style>
    </head>
    <body>
        <h2>F1 Lap Time Distributions</h2>
        <p>Lap time plots require live session data from OpenF1 API.</p>
        <p>This feature is not yet implemented in the dashboard.</p>
    </body>
    </html>
    """
    return html


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
        title={
            'text': track_data.get('circuit_name', 'F1 Track Map'),
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(size=16, color=text_color)
        },
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
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=False
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