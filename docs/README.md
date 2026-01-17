# SpaceX Dashboard

A launch monitoring and F1 racing companion application built with PyQt6 and QML, featuring real-time data visualization, interactive 3D globe rendering, and optimized touchscreen deployment for mission control environments.

## Windows setup notes

This app uses PyQt6 add-on modules for WebEngine and Charts. On Windows, these are published on PyPI as separate wheels:

- PyQt6 provides the core Qt bindings
- PyQt6-WebEngine provides `PyQt6.QtWebEngineQuick`
- PyQt6-Charts provides `PyQt6.QtCharts`

Install all dependencies (inside your virtual environment):

```powershell
python -m pip install -r requirements.txt
```

If you only need the Qt packages:

```powershell
python -m pip install PyQt6==6.7.1 PyQt6-WebEngine==6.7.0 PyQt6-Charts==6.7.0
```

Troubleshooting tips:

- Ensure you are using a 64-bit Python that matches your OS. PyQt6 wheels are 64-bit only.
- If behind a corporate proxy, set `HTTPS_PROXY` before installing.
- After installation, you should be able to import:
  - `from PyQt6.QtWebEngineQuick import QtWebEngineQuick`
  - `from PyQt6.QtCharts import QChartView, QLineSeries, QDateTimeAxis, QValueAxis`



     




## Trajectory and orbit visualization

The dashboard shows an illustrative ascent trajectory and an orbital ground track for upcoming launches. It is not a physically precise orbital propagator. Key assumptions:

- Ascent path is rendered as a smooth Bézier arc from the launch site toward a representative azimuth based on orbit type and site.
- Orbital path now reflects an inclination approximation:
  - LEO-Equatorial: ~site latitude (e.g., ~28.6° from Cape Canaveral)
  - LEO-Polar (Vandenberg): ~97°
  - ISS references: 51.6°
  - GTO: near site latitude
  - Suborbital: short arc without full orbit
- The ground track is generated to pass near the ascent end point and advances longitude at a rate scaled by cos(inclination). This creates a visually inclined orbit with polar vs. low-inclination differences.

Caching: Generated trajectory/orbit points are cached in cache/trajectory_cache.json with a versioned key that includes launch site, orbit class, and assumed inclination. Delete this file if you want to force regeneration after changing logic.

## FAQ

### Why does Linux WiFi scanning poll multiple times?

On Linux, the app uses wpa_supplicant via `wpa_cli`. After a scan is triggered, `scan_results` is populated incrementally as the driver roams across channels and applies dwell times and regulatory constraints (some channels require passive scanning). If results are read after a fixed short delay, you often get only a partial set of SSIDs. The app therefore polls `scan_results` for a short stabilization window and accepts the list once the number of unique SSIDs stops increasing.

Tuning:
- SPACEX_WIFI_SCAN_STABILIZE_MAXWAIT (seconds, default 8)
- SPACEX_WIFI_SCAN_STABILIZE_INTERVAL (seconds, default 1)

Set these environment variables if you want a shorter or longer stabilization period on your hardware.

## Raspberry Pi Setup

The project includes setup scripts for different display configurations on Raspberry Pi (optimized for Ubuntu 25.04).

### Supported Displays

1.  **Waveshare 11.9inch LCD (1480x320)**
    - Use the standard setup script:
      ```bash
      sudo bash scripts/setup_pi.sh
      ```
2.  **DFR1125 14 inch Bar Display (2560x734 2K Mode)**
    - Use the dedicated setup script (optimized for 2560x734 for better performance on Pi 5):
      ```bash
      sudo bash scripts/setup_pi_dfr1125.sh
      ```

The setup scripts handle system dependencies, display timings, Kiosk mode configuration, and boot splash screen setup.
