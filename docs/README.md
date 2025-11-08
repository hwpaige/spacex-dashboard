# SpaceX Dashboard

A comprehensive SpaceX launch dashboard built with PyQt6 and QML, featuring real-time launch data, 3D globe visualization, F1 racing integration, and more.

## Features

- **Real-time SpaceX Data**: Live launch schedules, mission details, and rocket information
- **3D Globe Visualization**: Interactive WebGL globe showing launch sites and orbital data
- **F1 Integration**: Formula 1 race schedules and track information
- **Weather Integration**: Local weather data for launch sites
- **WiFi Management**: Network connectivity tools for deployment
- **Responsive UI**: Optimized for various screen sizes and touch interfaces
- **Caching System**: Efficient data caching to reduce API calls
- **Cross-platform**: Runs on Windows, Linux, and Raspberry Pi

## Project Structure

```
spacex-dashboard/
├── src/                    # Source code
│   ├── app.py             # Main application
│   ├── globe.html         # WebGL globe visualization
│   ├── plotly_charts.py   # Chart generation utilities
│   └── track_generator.py # F1 track map generation
├── assets/                # Static assets
│   ├── images/           # Images and icons
│   │   └── flags/        # Country flags
│   ├── fonts/            # Font files
│   └── css/              # Stylesheets
├── cache/                # Cached data (gitignored)
│   └── tracks/           # Generated track images
├── scripts/              # Setup and utility scripts
├── docs/                 # Documentation
├── tools/                # Development utilities
│   ├── old_f1_app/      # Legacy F1 application
│   └── utility_files/   # Development tools
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
└── .gitignore          # Git ignore rules
```

## Requirements

- Python 3.8+
- PyQt6
- Qt WebEngine
- FastF1 (for F1 data)
- Requests
- Other dependencies listed in `requirements.txt`

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hwpaige/spacex-dashboard.git
   cd spacex-dashboard
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python src/app.py
   ```

## Deployment on Raspberry Pi

The application is optimized for Raspberry Pi deployment with touchscreens. Use the scripts in the `scripts/` directory for setup:

- `setup_pi.sh`: Initial Raspberry Pi configuration
- `update_and_reboot.sh`: Update and restart script
- Various configuration files for display and touch settings

## Development

- Main application code is in `src/`
- Utility scripts and tools are in `tools/`
- Cached data is stored in `cache/` (gitignored)
- Static assets are organized in `assets/`

## API Integration

The application integrates with several APIs:
- SpaceX API for launch data
- Ergast F1 API for racing data
- OpenWeatherMap for weather data
- Various mapping services for location data

## Troubleshooting

### YouTube Embed Issues (Error 153)

If you encounter YouTube embed error 153 or videos not loading, this is due to YouTube's recent changes to embed requirements. The application uses privacy-enhanced embeds (`youtube-nocookie.com`) to comply with YouTube's policies.

**Symptoms:**
- Error 153 in console logs
- YouTube videos show "Video unavailable" or don't load
- Autoplay fails

**Solution:**
The application has been updated to use `https://www.youtube-nocookie.com/embed/` instead of `https://www.youtube.com/embed/`. This bypasses referer header requirements that desktop applications cannot satisfy.

If issues persist:
1. Check your internet connection
2. Ensure Qt WebEngine is properly installed
3. Verify the YouTube playlist URL in `docs/youtube_url.txt` is accessible

## License
     