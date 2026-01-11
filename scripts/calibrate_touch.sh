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

# Find the touch device name
DEVICE_NAME=$(xinput list --name-only | grep -iE "touch|goodix|waveshare" | head -n 1)

if [ -z "$DEVICE_NAME" ]; then
    echo "ERROR: Touch device not found!"
    exit 1
fi

echo "Calibrating device: $DEVICE_NAME"

# We need DISPLAY to be set
export DISPLAY=${DISPLAY:-:0}

# Run calibrator and capture the Xorg snippet
# The --verbose flag helps ensure we get output even if it's already calibrated
CALIB_OUTPUT=$(xinput_calibrator --device "$DEVICE_NAME" --output-type xorg.conf.d)

if [ -z "$CALIB_OUTPUT" ] || ! echo "$CALIB_OUTPUT" | grep -q "Section \"InputClass\""; then
    echo "Calibration cancelled or failed to produce output."
    exit 1
fi

# Save to the config file
sudo mkdir -p "$XORG_CONF_DIR"
echo "$CALIB_OUTPUT" | sudo tee "$XORG_CALIB_FILE" > /dev/null

echo "SUCCESS: Calibration saved to $XORG_CALIB_FILE"
echo "Restarting the X session or rebooting is recommended."
