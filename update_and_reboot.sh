#!/bin/bash

# SpaceX Dashboard Update and Reboot Script for Raspberry Pi
# This script pulls the latest changes from the git repository and reboots the device

set -e  # Exit on any error

echo "=== SpaceX Dashboard Update Script ==="
echo "Starting update process..."

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
echo "Pulling latest changes from repository..."
git fetch origin
git pull origin master

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

echo "Update complete. Rebooting system in 5 seconds..."
echo "Press Ctrl+C to cancel reboot."

# Countdown before reboot
for i in {5..1}; do
    echo "Rebooting in $i..."
    sleep 1
done

echo "Rebooting now..."
sudo reboot