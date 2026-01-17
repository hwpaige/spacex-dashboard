#!/bin/bash
# fix_resolution.sh - Diagnostic and fix tool for DFR1125 Bar Display resolution issues (2K Mode)

set -e

USER="${SUDO_USER:-$USER}"
HOME_DIR="/home/$USER"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
CONFIG_FILE="/boot/firmware/config.txt"

echo "--- SpaceX Dashboard Resolution Fixer ---"

# 1. Setup environment for xrandr
# We need to access the X display as root or via the user
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

if [ -z "$XAUTHORITY" ]; then
    if [ -f "$HOME_DIR/.Xauthority" ]; then
        export XAUTHORITY="$HOME_DIR/.Xauthority"
    fi
fi

# Function to run xrandr as the logged-in user to ensure display access
run_xrandr() {
    sudo -u "$USER" DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" xrandr "$@"
}

echo "Detecting connected displays..."
# Test if we can reach the display
if ! run_xrandr --query >/dev/null 2>&1; then
    # Fallback: try running as root directly if sudo -u failed
    if ! xrandr --query >/dev/null 2>&1; then
        echo "Error: Could not open display $DISPLAY."
        echo "This script needs access to your graphical session to detect displays."
        echo ""
        echo "Please try:"
        echo "1. Run this script from a terminal inside the desktop environment."
        echo "2. If using SSH, ensure you have a session running on :0 and try:"
        echo "   export DISPLAY=:0; export XAUTHORITY=/home/$USER/.Xauthority; sudo -E bash fix_resolution.sh"
        exit 1
    fi
    # If root's xrandr worked, we use a wrapper that doesn't use sudo -u
    use_root_xrandr=1
else
    use_root_xrandr=0
fi

_xrandr() {
    if [ "$use_root_xrandr" -eq 1 ]; then
        xrandr "$@"
    else
        run_xrandr "$@"
    fi
}

CONNECTED_OUTPUTS=$(_xrandr | grep " connected" | cut -d' ' -f1)
if [ -z "$CONNECTED_OUTPUTS" ]; then
    echo "Error: No connected displays detected by xrandr."
    exit 1
fi

echo "Detected connected outputs:"
echo "$CONNECTED_OUTPUTS"

# Pick the first HDMI output, or fallback to the first connected output
HDMI_OUT=$(echo "$CONNECTED_OUTPUTS" | grep "HDMI" | head -n 1)
if [ -z "$HDMI_OUT" ]; then
    HDMI_OUT=$(echo "$CONNECTED_OUTPUTS" | head -n 1)
fi
echo "Targeting output: $HDMI_OUT"

# 2. Add custom mode to xrandr
MODE_NAME="2560x734_60.00"
# Modeline for 2560x734 @ 60Hz
MODELINE="132.00 2560 2677 2736 2933 734 736 742 750 -hsync +vsync"

echo "Adding custom mode $MODE_NAME to xrandr..."
set +e
_xrandr --newmode "$MODE_NAME" $MODELINE 2>/dev/null
_xrandr --addmode "$HDMI_OUT" "$MODE_NAME" 2>/dev/null
set -e

echo "Applying resolution $MODE_NAME..."
if ! _xrandr --output "$HDMI_OUT" --mode "$MODE_NAME" --rotate normal; then
    echo "Warning: Failed to apply mode via xrandr. It might be rejected by the driver if the cable is too high for the cable."
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
    cp "$CMDLINE_FILE" "${CMDLINE_FILE}.bak"
    
    # Remove existing video= parameters
    sed -i 's/ video=[^ ]*//g' "$CMDLINE_FILE"
    
    # Add new video parameter
    # We use 'D' to force digital output and 'e' to force enabled
    sed -i "s/$/ video=$K_CONNECTOR:2560x734M@60D/" "$CMDLINE_FILE"
    echo "✓ Updated $CMDLINE_FILE with video=$K_CONNECTOR:2560x734M@60D"
fi

# 4. Update config.txt to ensure KMS and ignore EDID if necessary
if [ -f "$CONFIG_FILE" ]; then
    echo "Verifying $CONFIG_FILE settings..."
    if ! grep -q "hdmi_ignore_edid=0xa5000080" "$CONFIG_FILE"; then
        echo "Adding hdmi_ignore_edid to $CONFIG_FILE..."
        # If the block exists, add it there, otherwise just add to end
        if grep -q "# BEGIN SPACEX DASHBOARD" "$CONFIG_FILE"; then
            sed -i '/# BEGIN SPACEX DASHBOARD/a hdmi_ignore_edid=0xa5000080' "$CONFIG_FILE"
        else
            echo "hdmi_ignore_edid=0xa5000080" >> "$CONFIG_FILE"
        fi
    fi
    # Ensure correct overlay for Pi 5
    if ! grep -q "dtoverlay=vc4-kms-v3d-pi5" "$CONFIG_FILE"; then
        echo "Ensuring dtoverlay=vc4-kms-v3d-pi5 in $CONFIG_FILE..."
        if grep -q "# BEGIN SPACEX DASHBOARD" "$CONFIG_FILE"; then
            sed -i '/# BEGIN SPACEX DASHBOARD/a dtoverlay=vc4-kms-v3d-pi5' "$CONFIG_FILE"
        else
            echo "dtoverlay=vc4-kms-v3d-pi5" >> "$CONFIG_FILE"
        fi
    fi
fi

# 5. Update .xsession to make it permanent in the session
XSESSION="$HOME_DIR/.xsession"
if [ -f "$XSESSION" ]; then
    echo "Updating $XSESSION to include xrandr force commands..."
    # Create a temporary file with the xrandr commands
    cat << EOF > /tmp/xrandr_fix.sh
# Force 2560x734 resolution
xrandr --newmode "$MODE_NAME" $MODELINE 2>/dev/null || true
xrandr --addmode $HDMI_OUT "$MODE_NAME" 2>/dev/null || true
xrandr --output $HDMI_OUT --mode "$MODE_NAME" --rotate normal || true
EOF
    
    # Insert before the application start if not already there
    if ! grep -q "$MODE_NAME" "$XSESSION"; then
        if grep -q "# Set display settings" "$XSESSION"; then
            sed -i "/# Set display settings/r /tmp/xrandr_fix.sh" "$XSESSION"
        else
            # Prepend before the last line (usually exec ...)
            sed -i '$i\\' "$XSESSION"
            sed -i '$i# Force 2560x734 resolution' "$XSESSION"
            sed -i '$i'"xrandr --newmode \"$MODE_NAME\" $MODELINE 2>/dev/null || true" "$XSESSION"
            sed -i '$i'"xrandr --addmode $HDMI_OUT \"$MODE_NAME\" 2>/dev/null || true" "$XSESSION"
            sed -i '$i'"xrandr --output $HDMI_OUT --mode \"$MODE_NAME\" --rotate normal || true" "$XSESSION"
        fi
        echo "✓ Updated $XSESSION"
    fi
    rm -f /tmp/xrandr_fix.sh
fi

echo "----------------------------------------"
echo "Fix applied. Please reboot your Raspberry Pi for all changes to take effect."
echo "If the screen goes black, you can revert cmdline.txt using the backup at ${CMDLINE_FILE}.bak"
echo "----------------------------------------"
