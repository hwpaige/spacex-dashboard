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

log "Adding Ubuntu 25.04 (Plucky) and 24.04 (Noble) repositories..."
cat << EOF > /etc/apt/sources.list.d/rollback.list
deb http://ports.ubuntu.com/ubuntu-ports plucky main universe
deb http://ports.ubuntu.com/ubuntu-ports plucky-updates main universe
deb http://ports.ubuntu.com/ubuntu-ports plucky-security main universe
deb http://ports.ubuntu.com/ubuntu-ports noble main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-updates main universe
deb http://ports.ubuntu.com/ubuntu-ports noble-security main universe
EOF

log "Creating APT pinning policy for Qt 6.8 (Plucky)..."
cat << EOF > /etc/apt/preferences.d/pin-qt68
# Force upgrade and pin to Qt versions from Plucky (25.04) for Qt 6.8
Package: python3-pyqt6* libqt6* qt6-* qml6-module-*
Pin: release n=plucky-updates
Pin-Priority: 1002

Package: python3-pyqt6* libqt6* qt6-* qml6-module-*
Pin: release n=plucky
Pin-Priority: 1001

# Forcefully block Noble (24.04) versions to prevent ABI conflicts
Package: python3-pyqt6* libqt6* qt6-* qml6-module-*
Pin: release n=noble
Pin-Priority: -1

# Allow everything else to use Questing (25.10)
Package: *
Pin: release n=questing
Pin-Priority: 500
EOF

log "Updating package lists..."
apt-get update

log "Executing downgrade to Qt 6.x (this may take a few minutes)..."
# Forcefully clear existing Qt6 packages to resolve ABI conflicts
log "Purging existing Qt6 packages..."
apt-get purge -y "libqt6*" "qml6-module-qt*" "python3-pyqt6*" "qt6-*" || true
apt-get autoremove -y

log "Installing Qt 6.8 from Plucky..."
apt-get install -y --allow-downgrades \
    libqt6core6 \
    libqt6gui6 \
    libqt6widgets6 \
    libqt6network6 \
    libqt6dbus6 \
    libqt6opengl6 \
    libqt6openglwidgets6 \
    libqt6printsupport6 \
    libqt6sql6 \
    libqt6xml6 \
    libqt6qml6 \
    libqt6quick6 \
    libqt6webenginecore6 \
    libqt6webenginequick6 \
    libqt6webenginewidgets6 \
    libqt6webchannel6 \
    libqt6positioning6 \
    libqt6svg6 \
    python3-pyqt6 \
    python3-pyqt6.qtwebengine \
    python3-pyqt6.qtqml \
    python3-pyqt6.qtquick \
    python3-pyqt6.qtpositioning \
    python3-pyqt6.qtwebchannel \
    python3-pyqt6.qtsvg \
    python3-pyqt6.qtcharts \
    qml6-module-qtwebengine \
    qml6-module-qtquick \
    qml6-module-qtqml \
    qml6-module-qtquick-controls \
    qml6-module-qtquick-layouts \
    qml6-module-qtquick-window \
    qml6-module-qtpositioning \
    qml6-module-qtwebchannel \
    qml6-module-qtquick-shapes \
    qml6-module-qtquick-templates \
    qml6-module-qtqml-models \
    libqt6quickshapes6 \
    libqt6quicktemplates2-6 \
    libqt6webchannelquick6 \
    qml6-module-qtquick-dialogs \
    libqt6quickcontrols2-6

log "Installing common Qt dependencies..."
apt-get install -y libxcb-cursor0 libxkbcommon-x11-0

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

log "Disabling Wayland to force X11 usage..."
if [ -f /etc/gdm3/custom.conf ]; then
    sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf
    # Also handle cases where it might already be uncommented but set to true
    sed -i 's/^WaylandEnable=true/WaylandEnable=false/' /etc/gdm3/custom.conf
    log "Wayland disabled in /etc/gdm3/custom.conf"
elif [ -f /etc/gdm3/daemon.conf ]; then
    sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/daemon.conf
    log "Wayland disabled in /etc/gdm3/daemon.conf"
fi

log "Rollback complete. Please reboot your Pi to ensure all GPU buffers are cleared."
