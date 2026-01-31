#!/bin/bash
set -e

# SpaceX Dashboard Rollback Script: Ubuntu 25.10 -> Qt 6.8 (Noble)
# This script pins Qt packages to the 25.04 (Noble) versions to avoid GLOzone issues.

log() {
    echo -e "\033[1;32m[ROLLBACK]\033[0m $1"
}

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

log "Adding Ubuntu 25.04 (Noble) repositories..."
cat << EOF > /etc/apt/sources.list.d/noble-rollback.list
deb http://ports.ubuntu.com/ubuntu-ports noble main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-updates main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-security main universe
EOF

log "Creating APT pinning policy for Qt 6.8..."
cat << EOF > /etc/apt/preferences.d/pin-qt68
# Force downgrade and pin to Qt 6.8 from Noble
Package: python3-pyqt6* libqt6* qt6-base*
Pin: release n=noble
Pin-Priority: 1001

Package: python3-pyqt6* libqt6* qt6-base*
Pin: release n=noble-updates
Pin-Priority: 1001

# Allow everything else to use Plucky (25.10)
Package: *
Pin: release n=plucky
Pin-Priority: 500
EOF

log "Updating package lists..."
apt-get update

log "Executing downgrade to Qt 6.8 (this may take a few minutes)..."
# We use dist-upgrade/full-upgrade to allow the pin-priority 1001 to trigger downgrades
apt-get full-upgrade -y

log "Verifying installed Qt version..."
INSTALLED_VER=$(python3 -c "from PyQt6.QtCore import QT_VERSION_STR; print(QT_VERSION_STR)" 2>/dev/null || echo "Unknown")
log "Currently active Qt version: $INSTALLED_VER"

if [[ "$INSTALLED_VER" == 6.8* ]]; then
    log "SUCCESS: Qt 6.8 is now active."
else
    log "WARNING: Qt version is $INSTALLED_VER. You may need to run 'sudo apt install python3-pyqt6/noble' manually."
fi

log "Ensuring XCB is enforced in environment..."
# Check if .xsession exists and contains the flag
XSESSION="/home/${SUDO_USER:-harrison}/.xsession"
if [ -f "$XSESSION" ]; then
    if ! grep -q "QT_QPA_PLATFORM=xcb" "$XSESSION"; then
        sed -i '/export DASHBOARD_HEIGHT/a export QT_QPA_PLATFORM=xcb' "$XSESSION"
        log "Added QT_QPA_PLATFORM=xcb to $XSESSION"
    fi
fi

log "Rollback complete. Please reboot your Pi to ensure all GPU buffers are cleared."
