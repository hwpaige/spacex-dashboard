#!/bin/bash

# SpaceX Dashboard Touch Calibration Script
# This script runs xinput_calibrator and saves the output to an X11 config file.

XORG_CONF_DIR="/etc/X11/xorg.conf.d"
XORG_CALIB_FILE="$XORG_CONF_DIR/99-calibration.conf"

echo "Starting Touchscreen Calibration..."

# Ensure xinput_calibrator is installed
if ! command -v xinput_calibrator &> /dev/null; then
    echo "xinput_calibrator not found. Installing..."
    sudo apt-get update && sudo apt-get install -y xinput-calibrator
fi

# We need DISPLAY and XAUTHORITY to be set correctly
export DISPLAY=${DISPLAY:-:0}
if [ -z "$XAUTHORITY" ]; then
    # Try to find XAUTHORITY if it's not set
    for user_home in /home/*; do
        if [ -f "$user_home/.Xauthority" ]; then
            export XAUTHORITY="$user_home/.Xauthority"
            break
        fi
    done
fi

echo "Environment: DISPLAY=$DISPLAY, XAUTHORITY=$XAUTHORITY, USER=$(whoami)"

# Find the touch device name
# Improved detection to handle cases with multiple similar names
DEVICE_NAME=$(xinput list --name-only | grep -iE "touch|goodix|waveshare" | sort -u | head -n 1)

if [ -z "$DEVICE_NAME" ]; then
    echo "ERROR: Touch device not found!"
    xinput list
    exit 1
fi

echo "Calibrating device: '$DEVICE_NAME'"

# Run calibrator and capture the Xorg snippet
# We use --verbose to get more info in logs if it fails
# We don't use --timeout as it might close before the user finishes
echo "Executing: xinput_calibrator --device \"$DEVICE_NAME\" --output-type xorg.conf.d"
CALIB_OUTPUT=$(xinput_calibrator --device "$DEVICE_NAME" --output-type xorg.conf.d 2>&1)
EXIT_CODE=$?

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
