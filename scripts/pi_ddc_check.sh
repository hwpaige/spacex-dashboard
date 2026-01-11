#!/bin/bash

# Script to check DDC/CI support for brightness control on Raspberry Pi
# This script is intended to be run on the Raspberry Pi.

set -e

echo "=== Starting DDC/CI Support Check ==="

# 1. Update package list and install ddcutil
echo "Updating package list and installing ddcutil..."
sudo apt update
sudo apt install ddcutil -y

# 2. Load the I2C module
echo "Loading I2C module (i2c-dev)..."
sudo modprobe i2c-dev

# Verify it's loaded
if lsmod | grep -q i2c_dev; then
    echo "I2C module loaded successfully."
else
    echo "Warning: I2C module might not be loaded. Checking with lsmod..."
    lsmod | grep i2c_dev
fi

# 3. Detect connected monitors
echo "Detecting connected monitors..."
sudo ddcutil detect

echo ""
echo "=== Detection Complete ==="
echo "Look for 'VCP version' in the output above for your DFR1125 display."
echo "If detected, note the I2C bus number (e.g., /dev/i2c-4)."
echo ""
echo "If a bus was found, you can run: sudo ddcutil capabilities --bus=X"
echo "(Replace X with the actual bus number)"
echo ""
echo "If brightness (code 10) is listed, you can test it with:"
echo "sudo ddcutil setvcp --bus=X 10 50"
echo ""
echo "Troubleshooting: If you see permission errors, run:"
echo "sudo usermod -aG i2c \$USER"
echo "Then log out and back in."
