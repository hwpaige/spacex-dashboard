#!/bin/bash
# fix_resolution.sh - Diagnostic and fix tool for DFR1125 4K Bar Display resolution issues

set -e

USER="${SUDO_USER:-$USER}"
HOME_DIR="/home/$USER"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONFIG_FILE="/boot/firmware/config.txt"

echo "--- SpaceX Dashboard Resolution Fixer ---"

# 1. Detect HDMI outputs
echo "Detecting connected displays..."
if ! command -v xrandr >/dev/null 2>&1; then
    echo "Error: xrandr not found. Are you running this in a GUI session?"
    echo "Try: export DISPLAY=:0; xrandr"
    exit 1
fi

CONNECTED_OUTPUTS=$(xrandr | grep " connected" | cut -d' ' -f1)
if [ -z "$CONNECTED_OUTPUTS" ]; then
    echo "Error: No connected displays detected by xrandr."
    exit 1
fi

echo "Detected connected outputs:"
echo "$CONNECTED_OUTPUTS"

# Pick the first one for now, or HDMI-1 if it exists
HDMI_OUT=$(echo "$CONNECTED_OUTPUTS" | grep "HDMI" | head -n 1)
if [ -z "$HDMI_OUT" ]; then
    HDMI_OUT=$(echo "$CONNECTED_OUTPUTS" | head -n 1)
fi
echo "Targeting output: $HDMI_OUT"

# 2. Add custom mode to xrandr
MODE_NAME="3840x1100_60.00"
# Modeline for 3840x1100 @ 60Hz (297MHz pixel clock)
MODELINE="297.00  3840 4016 4104 4400  1100 1103 1113 1125 -hsync +vsync"

echo "Adding custom mode $MODE_NAME to xrandr..."
set +e
xrandr --newmode "$MODE_NAME" $MODELINE 2>/dev/null
xrandr --addmode "$HDMI_OUT" "$MODE_NAME" 2>/dev/null
set -e

echo "Applying resolution $MODE_NAME..."
if ! xrandr --output "$HDMI_OUT" --mode "$MODE_NAME" --rotate normal; then
    echo "Warning: Failed to apply mode via xrandr. It might be rejected by the driver if the clock is too high for the cable."
else
    echo "✓ Resolution applied successfully via xrandr."
fi

# 3. Update cmdline.txt for persistence
if [ -f "$CMDLINE_FILE" ]; then
    echo "Updating $CMDLINE_FILE for persistent resolution..."
    # Convert xrandr name (HDMI-1) to kernel name (HDMI-A-1)
    K_CONNECTOR="HDMI-A-1"
    if [[ "$HDMI_OUT" == *"HDMI-2"* ]] || [[ "$HDMI_OUT" == *"HDMI-A-2"* ]]; then
        K_CONNECTOR="HDMI-A-2"
    fi
    
    # Backup
    sudo cp "$CMDLINE_FILE" "${CMDLINE_FILE}.bak"
    
    # Remove existing video= parameters
    sudo sed -i 's/ video=[^ ]*//g' "$CMDLINE_FILE"
    
    # Add new video parameter
    # We use 'D' to force digital output and 'e' to force enabled
    sudo sed -i "s/$/ video=$K_CONNECTOR:3840x1100M@60D/" "$CMDLINE_FILE"
    echo "✓ Updated $CMDLINE_FILE with video=$K_CONNECTOR:3840x1100M@60D"
fi

# 4. Update config.txt to ensure KMS and ignore EDID if necessary
if [ -f "$CONFIG_FILE" ]; then
    echo "Verifying $CONFIG_FILE settings..."
    if ! grep -q "hdmi_ignore_edid=0xa5000080" "$CONFIG_FILE"; then
        echo "Adding hdmi_ignore_edid to $CONFIG_FILE..."
        sudo sed -i '/# BEGIN SPACEX DASHBOARD/a hdmi_ignore_edid=0xa5000080' "$CONFIG_FILE"
    fi
    # Ensure correct overlay for Pi 5
    if ! grep -q "dtoverlay=vc4-kms-v3d-pi5" "$CONFIG_FILE"; then
        echo "Ensuring dtoverlay=vc4-kms-v3d-pi5 in $CONFIG_FILE..."
        sudo sed -i '/# BEGIN SPACEX DASHBOARD/a dtoverlay=vc4-kms-v3d-pi5' "$CONFIG_FILE"
    fi
fi

# 5. Update .xsession to make it permanent in the session
XSESSION="$HOME_DIR/.xsession"
if [ -f "$XSESSION" ]; then
    echo "Updating $XSESSION to include xrandr force commands..."
    # Create a temporary file with the xrandr commands
    cat << EOF > /tmp/xrandr_fix.sh
# Force 3840x1100 resolution
xrandr --newmode "$MODE_NAME" $MODELINE 2>/dev/null || true
xrandr --addmode $HDMI_OUT "$MODE_NAME" 2>/dev/null || true
xrandr --output $HDMI_OUT --mode "$MODE_NAME" --rotate normal || true
EOF
    
    # Insert before the application start
    if ! grep -q "$MODE_NAME" "$XSESSION"; then
        sudo sed -i "/# Set display settings/r /tmp/xrandr_fix.sh" "$XSESSION"
        echo "✓ Updated $XSESSION"
    fi
    rm /tmp/xrandr_fix.sh
fi

echo "----------------------------------------"
echo "Fix applied. Please reboot your Raspberry Pi for all changes to take effect."
echo "If the screen goes black, you can revert cmdline.txt using the backup at ${CMDLINE_FILE}.bak"
echo "----------------------------------------"
