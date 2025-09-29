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
if git diff HEAD~1 --name-only | grep -q "requirements.txt"; then
    echo "requirements.txt changed. Installing dependencies..."
    if command -v pip3 &> /dev/null; then
        pip3 install -r requirements.txt
    elif command -v pip &> /dev/null; then
        pip install -r requirements.txt
    else
        echo "Warning: pip not found, skipping dependency installation."
    fi
fi

# Clear the cache to ensure fresh data after update
echo "Clearing cache..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
rm -rf "$PROJECT_DIR/cache/*"

echo "Update complete. Rebooting system in 5 seconds..."
echo "Press Ctrl+C to cancel reboot."

# Countdown before reboot
for i in {5..1}; do
    echo "Rebooting in $i..."
    sleep 1
done

echo "Rebooting now..."
sudo reboot