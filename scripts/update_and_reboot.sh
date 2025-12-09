#!/bin/bash

# SpaceX Dashboard Update and Reboot Script for Raspberry Pi
# This script pulls the latest changes from the git repository and reboots the device

set -e  # Exit on any error

echo "=== SpaceX Dashboard Update Script ==="
echo "Starting update process..."

# Stop any running instances of the app
echo "Checking for running app instances..."
if pgrep -f "python.*app.py" > /dev/null; then
    echo "Stopping running app instances..."
    pkill -f "python.*app.py"
    sleep 2  # Wait for processes to terminate
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository. Please run this script from the spacex-dashboard directory."
    exit 1
fi

# Check if there are any uncommitted changes
if ! git diff --quiet || ! git diff --staged --quiet; then
    echo "Warning: You have uncommitted changes. Stashing them..."
    git stash
fi

# Fetch and pull the latest changes
echo "Fetching latest changes from repository..."
git fetch origin

# Always reset to ensure clean deployment (safest for production)
echo "Resetting to latest remote version..."
git reset --hard origin/master

# Alternative: Try pull with merge, fallback to reset
# echo "Attempting to pull latest changes..."
# if git pull origin master 2>/dev/null; then
#     echo "Successfully pulled changes."
# else
#     echo "Pull failed, resetting to remote version..."
#     git reset --hard origin/master
# fi

# Check if the pull was successful
if [ $? -eq 0 ]; then
    echo "Successfully updated repository."
else
    echo "Error: Failed to update repository."
    exit 1
fi

# Optional: Install any new Python dependencies if requirements.txt changed
if git diff HEAD~1 --name-only | grep -q "^requirements.txt$"; then
    echo "requirements.txt changed. Installing dependencies in virtual environment..."

    # Resolve project directory for absolute paths
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

    # Find a Python interpreter
    PYTHON_BIN="$(command -v python3 || command -v python)"
    if [ -z "$PYTHON_BIN" ]; then
        echo "Error: Python is not installed. Cannot create virtual environment."
        exit 1
    fi

    VENV_DIR="$PROJECT_DIR/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        echo "Creating virtual environment at $VENV_DIR..."
        "$PYTHON_BIN" -m venv "$VENV_DIR" || {
            echo "Error: Failed to create virtual environment."; exit 1; }
    fi

    # Use the venv's python/pip to avoid PEP 668 issues on Debian/Ubuntu/Raspberry Pi
    VENV_PY="$VENV_DIR/bin/python"
    VENV_PIP="$VENV_DIR/bin/pip"

    if [ ! -x "$VENV_PY" ]; then
        echo "Error: Virtual environment python not found at $VENV_PY"
        exit 1
    fi

    echo "Upgrading pip, setuptools, and wheel in venv..."
    "$VENV_PY" -m pip install --upgrade pip setuptools wheel || {
        echo "Warning: Failed to upgrade pip tooling in venv"; }

    echo "Installing requirements from $PROJECT_DIR/requirements.txt ..."
    "$VENV_PIP" install -r "$PROJECT_DIR/requirements.txt" || {
        echo "Error: Failed to install Python dependencies in venv."; exit 1; }
fi

# Clear the cache to ensure fresh data after update, but keep relatively static caches
echo "Clearing cache (preserving previous launches and race caches)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# Remove contents safely even if directory is empty
if [ -d "$PROJECT_DIR/cache" ]; then
    # Preserve previous launch caches which are relatively static
    # Note: F1/race caches are stored under ~/.cache/spacex-dashboard and are not touched here
    find "$PROJECT_DIR/cache" \
        -mindepth 1 -maxdepth 1 \
        -not -name 'previous_launches_cache.json' \
        -not -name 'previous_launches_cache_backup.json' \
        -exec rm -rf {} + 2>/dev/null || true
fi

echo "Update complete. Rebooting system in 5 seconds..."
echo "Press Ctrl+C to cancel reboot."

# Countdown before reboot
for i in {5..1}; do
    echo "Rebooting in $i..."
    sleep 1
done

echo "Rebooting now..."
sudo reboot