#!/bin/bash

# SpaceX Dashboard Touch Calibration Script
# This script runs xinput_calibrator and saves the output to an X11 config file.

XORG_CONF_DIR="/etc/X11/xorg.conf.d"
XORG_CALIB_FILE="$XORG_CONF_DIR/99-calibration.conf"

echo "Starting Touchscreen Calibration..."

# Ensure required tools are installed
for tool in xinput xinput_calibrator; do
    if ! command -v $tool &> /dev/null; then
        echo "$tool not found. Attempting to install..."
        sudo apt-get update && sudo apt-get install -y $tool
    fi
done

# We need DISPLAY and XAUTHORITY to be set correctly
export DISPLAY=${DISPLAY:-:0}
if [ -z "$XAUTHORITY" ]; then
    # Try to find XAUTHORITY from common locations if not set
    # 1. Check if we can find it from the current user's home
    if [ -f "$HOME/.Xauthority" ]; then
        export XAUTHORITY="$HOME/.Xauthority"
    # 2. Try to find the user running X and check their home
    else
        X_USER=$(ps aux | grep -E 'Xorg|Xwayland|X' | grep -v grep | awk '{print $1}' | sort -u | head -n 1)
        if [ -n "$X_USER" ]; then
            X_USER_HOME=$(getent passwd "$X_USER" | cut -d: -f6)
            if [ -f "$X_USER_HOME/.Xauthority" ]; then
                export XAUTHORITY="$X_USER_HOME/.Xauthority"
            fi
        fi
    fi
    # 3. Fallback to the old method of checking all homes
    if [ -z "$XAUTHORITY" ]; then
        for user_home in /home/*; do
            if [ -f "$user_home/.Xauthority" ]; then
                export XAUTHORITY="$user_home/.Xauthority"
                break
            fi
        done
    fi
fi

# If we are root, try to allow access to the X server for the current user
if [ "$(id -u)" -eq 0 ] && [ -n "$DISPLAY" ]; then
    xhost +SI:localuser:root > /dev/null 2>&1 || true
fi

echo "Environment: DISPLAY=$DISPLAY, XAUTHORITY=$XAUTHORITY, USER=$(whoami)"

# Find the touch device name
# Improved detection to handle more common touch device names with prioritization
echo "Searching for touch devices..."
DEVICE_NAME=$(xinput list --name-only | grep -iE "touch" | head -n 1)
if [ -z "$DEVICE_NAME" ]; then
    DEVICE_NAME=$(xinput list --name-only | grep -iE "goodix|waveshare|atmel|elan|focal|syna|microtouch" | head -n 1)
fi
if [ -z "$DEVICE_NAME" ]; then
    # Fallback to anything with "pointer" that isn't the virtual core pointer
    DEVICE_NAME=$(xinput list --name-only | grep -iE "point" | grep -v "Virtual core" | head -n 1)
fi

if [ -z "$DEVICE_NAME" ]; then
    echo "WARNING: Explicit touch device not found by name. Attempting auto-detection..."
    # If we can't find it by name, let xinput_calibrator try to find it
    # We'll use a temporary variable for the command
    CALIB_CMD="xinput_calibrator --output-type xorg.conf.d"
else
    echo "Calibrating device: '$DEVICE_NAME'"
    CALIB_CMD="xinput_calibrator --device \"$DEVICE_NAME\" --output-type xorg.conf.d"
fi

echo "Executing: $CALIB_CMD"
# Run calibrator and capture the Xorg snippet
# Use a temporary file to avoid issues with subshell capturing if it affects GUI window
TMP_CALIB_OUT=$(mktemp)
eval "$CALIB_CMD" > "$TMP_CALIB_OUT" 2>&1
EXIT_CODE=$?
CALIB_OUTPUT=$(cat "$TMP_CALIB_OUT")
rm "$TMP_CALIB_OUT"

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: xinput_calibrator failed with exit code $EXIT_CODE"
    echo "Output: $CALIB_OUTPUT"
    exit 1
fi

if ! echo "$CALIB_OUTPUT" | grep -q "Section \"InputClass\""; then
    echo "ERROR: Calibration failed to produce a valid Xorg configuration snippet."
    echo "Output: $CALIB_OUTPUT"
    exit 1
fi

# Extract only the InputClass section from the output
CLEAN_OUTPUT=$(echo "$CALIB_OUTPUT" | sed -n '/Section "InputClass"/,/EndSection/p')

if [ -z "$CLEAN_OUTPUT" ]; then
    echo "ERROR: Failed to extract InputClass section from output."
    exit 1
fi

# Save to the config file
echo "Saving calibration to $XORG_CALIB_FILE..."
sudo mkdir -p "$XORG_CONF_DIR"
echo "$CLEAN_OUTPUT" | sudo tee "$XORG_CALIB_FILE" > /dev/null

echo "SUCCESS: Calibration saved to $XORG_CALIB_FILE"
echo "--- CALIBRATION DATA ---"
echo "$CLEAN_OUTPUT"
echo "------------------------"
echo "Restarting the X session or rebooting is recommended for changes to take effect."
