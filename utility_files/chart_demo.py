#!/usr/bin/env python3
"""
Enhanced Chart Demo - Tesla-inspired styling
This script demonstrates the new chart styling features
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import pyqtgraph as pg

# Sample data for demonstration
sample_data = [
    {'label': 'Starship', 'values': [1, 2, 3, 4, 5, 6, 7, 8]},
    {'label': 'Falcon 9', 'values': [6, 12, 18, 24, 30, 36, 42, 48]},
    {'label': 'Falcon Heavy', 'values': [0, 1, 1, 2, 2, 3, 3, 4]}
]

def demo_enhanced_charts():
    """Demonstrate the enhanced chart features"""
    app = QApplication(sys.argv)

    # Create main window
    win = pg.GraphicsLayoutWidget(show=True, title="Enhanced Charts Demo")
    win.resize(1200, 800)

    # Create plot
    plot = win.addPlot(title="Tesla-Inspired Launch Trends")

    # Enhanced styling
    plot.showGrid(x=True, y=True, alpha=0.3)

    # Modern color palette
    colors = [
        {'primary': '#00D4FF', 'secondary': '#0088CC'},  # Electric blue
        {'primary': '#FF6B6B', 'secondary': '#CC4444'},  # Energy red
        {'primary': '#4ECDC4', 'secondary': '#26A69A'}   # Cool teal
    ]

    # Add bars with enhanced styling
    bar_width = 0.25
    for i, series in enumerate(sample_data):
        color_scheme = colors[i % len(colors)]
        x_positions = [j + i * bar_width for j in range(len(series['values']))]

        # Create bars with gradient effect
        bars = pg.BarGraphItem(
            x=x_positions,
            height=series['values'],
            width=bar_width,
            brush=pg.mkBrush(color=color_scheme['primary']),
            pen=pg.mkPen(color=color_scheme['secondary'], width=1)
        )
        plot.addItem(bars)

        # Add value labels
        for j, (x, y) in enumerate(zip(x_positions, series['values'])):
            if y > 0:
                label = pg.TextItem(text=str(y), color=color_scheme['secondary'], anchor=(0.5, -0.5))
                label.setPos(x, y + 0.5)
                plot.addItem(label)

    # Enhanced axes
    plot.setLabel('left', 'Number of Launches', color='white', size='12pt', bold=True)
    plot.setLabel('bottom', 'Time Period', color='white', size='12pt', bold=True)

    # Set axis ranges
    plot.setXRange(-0.5, len(sample_data[0]['values']) - 0.5)
    plot.setYRange(0, 55)

    # Add legend
    legend = plot.addLegend(offset=(-10, 10))
    for i, series in enumerate(sample_data):
        color_scheme = colors[i % len(colors)]
        legend.addItem(pg.PlotDataItem(pen=pg.mkPen(color=color_scheme['primary'])), series['label'])

    print("Enhanced chart demo created!")
    print("Features demonstrated:")
    print("- Modern color palette inspired by Tesla")
    print("- Gradient effects and enhanced styling")
    print("- Value labels on bars")
    print("- Improved typography and spacing")
    print("- Professional legend positioning")

    # Auto-close after 10 seconds for demo
    QTimer.singleShot(10000, app.quit)

    return app.exec()

if __name__ == '__main__':
    demo_enhanced_charts()
