#!/bin/bash
set -e
set -o pipefail

# Trap to handle interrupts gracefully
trap 'log "Setup interrupted by user"; exit 1' INT TERM

# SpaceX Dashboard Setup Script for Raspberry Pi Ubuntu 25.04 with Qt 6.8.x
# This script is specifically designed for Qt 6.8.x compatibility
# Qt 6.9.x and later versions have known GLOzone issues with WebEngine

USER="${SUDO_USER:-harrison}"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"
REPO_URL="https://github.com/hwpaige/spacex-dashboard"
REPO_DIR="$HOME_DIR/Desktop/project"

log() {
    echo "$@" | tee -a "$LOG_FILE"
}

error_exit() {
    echo "ERROR: $*" | tee -a "$LOG_FILE"
    exit 1
}

setup_user() {
    if id "$USER" &>/dev/null; then
        log "User $USER already exists"
        return
    fi
    
    log "Creating user $USER..."
    adduser --disabled-password --gecos "" "$USER" || error_exit "Failed to create user"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers.d/"$USER"
    chmod 0440 /etc/sudoers.d/"$USER"
    passwd -d "$USER"
    
    # Setup X authority and permissions
    sudo -u "$USER" touch "$HOME_DIR/.Xauthority"
    sudo -u "$USER" chmod 600 "$HOME_DIR/.Xauthority"
    # Add to groups for GPU and network control (netdev used with polkit rule below)
    usermod -aG render,video,tty,input,netdev "$USER"
    usermod -s /bin/bash "$USER"
}

setup_gpu_permissions() {
    log "Setting comprehensive GPU device permissions and DMA buffer fixes..."
    
    # Remove any existing rules first
    rm -f /etc/udev/rules.d/99-gpu-permissions.rules
    rm -f /etc/udev/rules.d/99-dmabuf-permissions.rules
    
    # Comprehensive GPU device permissions
    cat << 'EOF' > /etc/udev/rules.d/99-gpu-permissions.rules
# GPU device permissions for Chromium
SUBSYSTEM=="drm", KERNEL=="card*", GROUP="video", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", GROUP="render", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="controlD*", GROUP="video", MODE="0660"
EOF
    
    # Enhanced DMA buffer permissions for Chromium GPU memory mapping
    cat << 'EOF' > /etc/udev/rules.d/99-dmabuf-permissions.rules
# DMA buffer permissions for GPU memory mapping
SUBSYSTEM=="dma_heap", GROUP="video", MODE="0660"
KERNEL=="dmabuf", GROUP="video", MODE="0660"
SUBSYSTEM=="dma_buf", GROUP="video", MODE="0660"
# Additional DMA buffer device permissions
KERNEL=="udmabuf", GROUP="video", MODE="0660"
SUBSYSTEM=="udmabuf", GROUP="video", MODE="0660"
EOF
    
    # Memory limits for the user with GPU memory support
    cat << EOF > /etc/security/limits.d/99-app-limits.conf
$USER soft memlock 1G
$USER hard memlock 2G
$USER soft nofile 65536
$USER hard nofile 65536
EOF
    
    # Reload udev rules
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=drm
    udevadm trigger --subsystem-match=dma_heap
    udevadm trigger --subsystem-match=dma_buf
    
    log "GPU permissions configured and udev rules reloaded"
}

update_system() {
    log "Updating system packages..."
    if ! apt-get update -y; then
        log "WARNING: apt-get update failed, continuing..."
    fi
    if ! apt-get upgrade -y --no-install-recommends; then
        log "WARNING: apt-get upgrade failed, continuing..."
    fi
    if ! apt-get install -y software-properties-common; then
        log "WARNING: Could not install software-properties-common, continuing..."
    fi
    add-apt-repository universe -y 2>/dev/null || log "WARNING: Could not add universe repository"
}

configure_networkmanager() {
    log "Ensuring NetworkManager is the active network stack (Netplan)…"

    # Detect if netplan is available
    if ! command -v netplan >/dev/null 2>&1; then
        log "WARNING: netplan command not found; skipping renderer switch and proceeding"
        # Still try to enable NetworkManager so nmcli can be used if present
        systemctl enable NetworkManager 2>/dev/null || log "WARNING: Could not enable NetworkManager"
        systemctl start NetworkManager 2>/dev/null || log "WARNING: Could not start NetworkManager"
        return
    fi

    mkdir -p /etc/netplan

    # Detect if we're running over an SSH session to avoid dropping connectivity
    local is_ssh_session=0
    # Primary detection via SSH_* vars (may be cleared by sudo)
    if [ -n "$SSH_CONNECTION" ] || [ -n "$SSH_TTY" ] || [ -n "$SSH_CLIENT" ]; then
        is_ssh_session=1
    else
        # Heuristic: if controlling TTY is /dev/pts/*, likely a remote/pty session
        if tty 1>/dev/null 2>&1; then
            if tty | grep -qE "^/dev/pts/"; then
                is_ssh_session=1
            fi
        fi
    fi
    if [ "$SAFE_MODE" = "ssh" ] || [ "$SAFEMODE" = "ssh" ]; then
        is_ssh_session=1
    fi
    if [ $is_ssh_session -eq 1 ]; then
        log "Environment: remote/SSH-like session (will avoid disruptive networking changes until reboot)"
    else
        log "Environment: local/console session"
    fi

    # Check current renderer from existing netplan YAMLs
    local current_renderer=""
    if grep -RiqE "^\s*renderer:\s*NetworkManager\b" /etc/netplan/*.yaml 2>/dev/null; then
        current_renderer="NetworkManager"
    elif grep -RiqE "^\s*renderer:\s*networkd\b" /etc/netplan/*.yaml 2>/dev/null; then
        current_renderer="networkd"
    else
        current_renderer="unknown"
    fi
    log "Detected current netplan renderer: ${current_renderer}"

    # Only (over)write 99-network-manager.yaml if renderer is not already NetworkManager
    if [ "$current_renderer" != "NetworkManager" ]; then
        log "Writing /etc/netplan/99-network-manager.yaml to set renderer: NetworkManager"
        cat > /etc/netplan/99-network-manager.yaml << 'EOF'
network:
  version: 2
  renderer: NetworkManager
EOF
        # Fix permissions as netplan requires strict perms
        chown root:root /etc/netplan/99-network-manager.yaml 2>/dev/null || true
        chmod 600 /etc/netplan/99-network-manager.yaml 2>/dev/null || true
    else
        log "Netplan already configured for NetworkManager; will regenerate/apply to ensure consistency"
        # Ensure all netplan YAMLs have strict permissions to avoid warnings and failures
        chown root:root /etc/netplan/*.yaml 2>/dev/null || true
        chmod 600 /etc/netplan/*.yaml 2>/dev/null || true
    fi

    # Generate netplan and attempt to apply with a timeout to prevent hangs
    if netplan generate 2>&1 | tee -a "$LOG_FILE"; then
        log "netplan generate completed"
    else
        log "WARNING: netplan generate failed (continuing; changes may take effect after reboot)"
    fi

    local applied_ok=0
    if [ $is_ssh_session -eq 1 ]; then
        # Avoid applying immediately over SSH to prevent disconnecting the session
        log "SSH session detected: skipping immediate 'netplan apply' to avoid dropping the connection; changes will take effect after reboot"
    else
        if command -v timeout >/dev/null 2>&1; then
            log "Applying netplan with timeout (12s) to avoid long blocks…"
            if timeout 12 netplan apply 2>&1 | tee -a "$LOG_FILE"; then
                applied_ok=1
                log "✓ netplan apply succeeded"
            else
                log "WARNING: netplan apply failed or timed out; deferring full effect to reboot"
            fi
        else
            log "Applying netplan (no timeout utility available)…"
            if netplan apply 2>&1 | tee -a "$LOG_FILE"; then
                applied_ok=1
                log "✓ netplan apply succeeded"
            else
                log "WARNING: netplan apply failed; deferring full effect to reboot"
            fi
        fi
    fi

    # Enable NetworkManager and optionally disable systemd-networkd if apply worked
    if systemctl enable NetworkManager 2>/dev/null; then
        log "Enabled NetworkManager to start at boot"
    else
        log "WARNING: Could not enable NetworkManager"
    fi

    # Start NetworkManager now only if we successfully applied netplan locally (to avoid conflicts)
    if [ $applied_ok -eq 1 ] && [ $is_ssh_session -eq 0 ]; then
        if systemctl start NetworkManager 2>/dev/null; then
            log "Started NetworkManager"
        else
            log "WARNING: Could not start NetworkManager"
        fi
    else
        log "Deferring NetworkManager start until reboot (enabled for next boot)"
    fi

    # Ensure systemd-resolved is enabled and resolv.conf is properly linked
    configure_resolver_integration

    # Wait (bounded) for NetworkManager to become active
    local waited=0
    while [ $waited -lt 15 ]; do
        if systemctl is-active --quiet NetworkManager; then
            log "NetworkManager is active"
            break
        fi
        sleep 1
        waited=$((waited+1))
    done
    if [ $waited -ge 15 ]; then
        log "WARNING: NetworkManager did not become active within 15s (continuing)"
    fi

    # Quick DNS sanity check; if DNS broken, attempt to set fallback servers on active connection (Wi‑Fi/Ethernet)
    if command -v resolvectl >/dev/null 2>&1; then
        if ! timeout 5s resolvectl query github.com >/dev/null 2>&1; then
            log "WARNING: DNS query failed after NM start; attempting to set fallback DNS servers (1.1.1.1, 8.8.8.8) on active connection"
            active_name=$(nmcli -t -f NAME,TYPE,DEVICE con show --active 2>/dev/null | awk -F: '$2=="wifi" || $2=="ethernet" {print $1; exit}')
            if [ -n "$active_name" ]; then
                nmcli connection modify "$active_name" ipv4.dns "1.1.1.1 8.8.8.8" ipv4.ignore-auto-dns yes 2>/dev/null || true
                nmcli connection up "$active_name" 2>/dev/null || true
                sleep 2
            else
                log "No active Wi‑Fi/Ethernet NM connection found to modify DNS; skipping fallback DNS setup"
            fi
        fi
    fi

    # Only stop systemd-networkd if netplan apply succeeded; otherwise avoid disrupting current session
    if [ $applied_ok -eq 1 ]; then
        systemctl disable --now systemd-networkd 2>/dev/null || true
        log "systemd-networkd disabled (and stopped) since netplan apply succeeded"
    else
        # Do not stop it now to avoid hangs; optionally disable for next boot
        systemctl disable systemd-networkd 2>/dev/null || true
        log "systemd-networkd disabled for next boot (not stopped now due to netplan apply issues)"
    fi
}

configure_nm_polkit() {
    log "Configuring PolicyKit to allow Wi‑Fi control without root for netdev group…"
    mkdir -p /etc/polkit-1/rules.d
    cat > /etc/polkit-1/rules.d/10-networkmanager.rules << 'EOF'
polkit.addRule(function(action, subject) {
    if (subject.isInGroup("netdev") && action && action.id &&
        action.id.indexOf("org.freedesktop.NetworkManager.") === 0) {
        return polkit.Result.YES;
    }
});
EOF
}

install_packages() {
    log "Installing system packages..."
    
    # Define the packages array with system packages (restored from git history)
    local packages=(
        python3 python3-pip python3-full python3-venv git
        python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick python3-pyqt6.qtwebchannel
        qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls
        qml6-module-qtquick-layouts qml6-module-qtcharts qml6-module-qtwebengine
        qt6-base-dev qt6-declarative-dev qt6-webengine-dev qt6-charts-dev
        python3-requests python3-dateutil python3-pandas python3-tz python3-pytz
        python3-numpy python3-scipy python3-matplotlib python3-opengl python3-pyqtgraph
        python3-psutil
        unclutter plymouth plymouth-themes htop libgbm1 libdrm2 upower iw net-tools network-manager
        xserver-xorg xinit x11-xserver-utils openbox matchbox-window-manager libinput-tools imagemagick
        ubuntu-raspi-settings xserver-xorg-video-modesetting lightdm
        libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 mesa-vulkan-drivers
        mesa-opencl-icd ocl-icd-opencl-dev libgles2-mesa-dev
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1
        libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 python3-xdg
        libqt6webenginecore6 libqt6webenginequick6 libnss3 libatk-bridge2.0-0t64
        libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1
        libasound2t64 libgtk-3-0t64 lz4 plymouth-theme-spinner
        qt6-webengine-dev-tools libxcb-cursor0
    )
    
    # First try to install all packages at once for speed
    if apt-get install -y --no-install-recommends "${packages[@]}"; then
        log "✓ All packages installed successfully in one batch"
        return
    fi
    
    # If batch install failed, try individual installs to identify problematic packages
    log "Batch install failed, trying individual package installs..."
    local failed_packages=""
    for package in "${packages[@]}"; do
        if ! apt-get install -y --no-install-recommends "$package" 2>/dev/null; then
            failed_packages="$failed_packages $package"
            log "WARNING: Failed to install $package"
        fi
    done
    
    if [ -n "$failed_packages" ]; then
        log "WARNING: Some packages failed to install:$failed_packages"
        log "This may affect functionality, but continuing setup..."
    else
        log "All packages installed successfully"
    fi
}

# Ensure NetworkManager <-> systemd-resolved integration and resolv.conf link are correct
configure_resolver_integration() {
    # Make sure systemd-resolved is enabled and started
    if systemctl enable --now systemd-resolved 2>/dev/null; then
        log "systemd-resolved enabled and started"
    else
        log "WARNING: could not enable/start systemd-resolved"
    fi

    # Ensure NetworkManager uses systemd-resolved for DNS
    mkdir -p /etc/NetworkManager
    if [ -f /etc/NetworkManager/NetworkManager.conf ]; then
        if ! grep -qE '^\s*dns\s*=\s*systemd-resolved\s*$' /etc/NetworkManager/NetworkManager.conf; then
            # Append/ensure [main] section has dns=systemd-resolved
            if grep -q "^\[main\]" /etc/NetworkManager/NetworkManager.conf; then
                sed -i '/^\[main\]/a dns=systemd-resolved' /etc/NetworkManager/NetworkManager.conf || true
            else
                printf "[main]\ndns=systemd-resolved\n" >> /etc/NetworkManager/NetworkManager.conf || true
            fi
            log "Configured NetworkManager to use systemd-resolved for DNS"
            systemctl restart NetworkManager 2>/dev/null || true
        fi
    else
        cat > /etc/NetworkManager/NetworkManager.conf << 'EOF'
[main]
dns=systemd-resolved
plugins=keyfile

[logging]
level=INFO
EOF
        log "Created /etc/NetworkManager/NetworkManager.conf with dns=systemd-resolved"
        systemctl restart NetworkManager 2>/dev/null || true
    fi

    # Fix /etc/resolv.conf symlink to systemd-resolved stub if needed
    if [ -L /etc/resolv.conf ]; then
        target=$(readlink -f /etc/resolv.conf)
        if [ "$target" != "/run/systemd/resolve/stub-resolv.conf" ] && [ "$target" != "/run/systemd/resolve/resolv.conf" ]; then
            rm -f /etc/resolv.conf
            ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf || ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf || true
            log "Re-linked /etc/resolv.conf to systemd-resolved stub"
        fi
    else
        rm -f /etc/resolv.conf
        ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf || ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf || true
        log "Linked /etc/resolv.conf to systemd-resolved stub"
    fi

    # Brief wait for resolver to be ready
    sleep 1
}

check_qt_version() {
    log "Checking Qt version compatibility..."
    log "Note: This setup is optimized for Qt 6.8.x - Qt 6.9.x+ has GLOzone WebEngine issues"
    
    # Check PyQt6 version
    local pyqt_version=$(python3 -c "import PyQt6; print(PyQt6.QtCore.PYQT_VERSION_STR)" 2>/dev/null || echo "unknown")
    log "PyQt6 version: $pyqt_version"
    
    # Check Qt6 WebEngine version
    local qt_version=$(python3 -c "import PyQt6.QtWebEngine; print(PyQt6.QtWebEngine.PYQT_WEBENGINE_VERSION_STR)" 2>/dev/null || echo "unknown")
    log "Qt WebEngine version: $qt_version"
    
    # Extract major.minor version for comparison
    local qt_major_minor=""
    if [[ $qt_version =~ ^([0-9]+\.[0-9]+) ]]; then
        qt_major_minor="${BASH_REMATCH[1]}"
    fi
    
    # Check if we're using Qt 6.8.x (known working version)
    if [[ $qt_major_minor == "6.8" ]]; then
        log "✓ Qt $qt_version detected - this version is known to work with the SpaceX dashboard"
    elif [[ $qt_major_minor == "6.9" ]]; then
        log "⚠ WARNING: Qt $qt_version detected - this version (6.9.x) has known GLOzone issues with WebEngine"
        log "⚠ It is recommended to use Ubuntu 25.04 with Qt 6.8.x for best compatibility"
        log "⚠ The app may not start or may crash with GLOzone errors"
    elif [[ $qt_major_minor == "6.10" ]] || [[ $qt_major_minor == "6.11" ]] || [[ $qt_major_minor == "6.12" ]]; then
        log "⚠ WARNING: Qt $qt_version detected - this version is newer than tested versions"
        log "⚠ Compatibility is unknown - the app may not work correctly"
    else
        log "⚠ WARNING: Unable to determine Qt version or using untested version: $qt_version"
        log "⚠ This may cause issues with the SpaceX dashboard"
    fi
}

setup_python_environment() {
    log "Setting up Python environment..."

    if python3 -c "import PyQt6, requests, pandas, psutil, fastf1, plotly" 2>/dev/null; then
        log "System Python with all dependencies working (including fastf1 and plotly)"
        return
    fi

    log "Installing missing Python packages system-wide..."
    # Note: Core Python packages (python3-psutil, python3-pyqt6, python3-requests, python3-pandas) 
    # are now installed via the packages array in install_packages()

    # Install emoji fonts for proper emoji display in the app
    log "Installing emoji fonts for app display..."
    apt-get install -y fonts-noto-color-emoji

    # Install build tools needed for compiling packages
    log "Installing build tools for pip packages..."
    apt-get install -y build-essential python3-dev

    # Install pip packages that aren't available via apt
    # Use pip with system packages to avoid virtual environment complexity
    log "Installing pip packages..."
    export PIP_BREAK_SYSTEM_PACKAGES=1
    pip3 install --ignore-installed fastf1 plotly==5.24.1 cryptography || log "WARNING: Failed to install pip packages"

    # Verify installation
    if python3 -c "import PyQt6, pyqtgraph, requests, pandas, psutil, fastf1, plotly, cryptography" 2>/dev/null; then
        log "✓ All Python packages installed successfully"
    else
        log "⚠ Some packages may still be missing, but continuing..."
    fi
}

create_debug_script() {
    log "Creating debug script..."
    sudo -u "$USER" bash -c "cat << 'EOF' > $HOME_DIR/debug_x.sh
#!/bin/bash
echo '=== System Status ==='
echo \"User: \$(whoami) | Display: \$DISPLAY\"
echo \"Python: \$(python3 --version 2>/dev/null || echo 'Not found')\"
echo ''
echo '=== Package Tests ==='
python3 -c 'import PyQt6, pyqtgraph, requests, pandas, psutil; print(\"System packages working\")' 2>/dev/null || echo 'System Python failed'
python3 -c 'import fastf1; print(\"fastf1 available\")' 2>/dev/null || echo 'fastf1 not available'
echo ''
echo '=== Qt/GPU Debug Info ==='
echo 'Qt6 Platform Plugins:'
ls -la /usr/lib/aarch64-linux-gnu/qt6/plugins/platforms/ 2>/dev/null || echo 'Qt6 plugins not found'
echo ''
echo 'Qt6 WebEngine Libraries:'
ls -la /usr/lib/aarch64-linux-gnu/ | grep qt6webengine 2>/dev/null || echo 'Qt6 WebEngine libs not found'
echo ''
echo 'EGL/GLES Libraries:'
ls -la /usr/lib/aarch64-linux-gnu/ | grep -E \"egl\|gles\" 2>/dev/null || echo 'EGL/GLES libs not found'
echo ''
echo 'Mesa Libraries:'
ls -la /usr/lib/aarch64-linux-gnu/ | grep mesa 2>/dev/null || echo 'Mesa libs not found'
echo ''
echo 'Environment Variables:'
echo \"QT_QPA_PLATFORM: \$QT_QPA_PLATFORM\"
echo \"QTWEBENGINE_CHROMIUM_FLAGS: \$QTWEBENGINE_CHROMIUM_FLAGS\"
echo \"EGL_PLATFORM: \$EGL_PLATFORM\"
echo \"GALLIUM_DRIVER: \$GALLIUM_DRIVER\"
echo \"LIBGL_ALWAYS_SOFTWARE: \$LIBGL_ALWAYS_SOFTWARE\"
echo ''
echo '=== GPU Device Info ==='
echo 'GPU devices:'
ls -la /dev/dri/ 2>/dev/null || echo 'No GPU devices found'
echo ''
echo 'GPU memory info:'
cat /proc/meminfo | grep -E \"MemTotal\|MemAvailable\|Buffers\|Cached\" 2>/dev/null || echo 'Memory info unavailable'
echo ''
echo '=== Qt Platform Test ==='
python3 -c \"
import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_DEBUG_PLUGINS'] = '1'
try:
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    print('Qt xcb platform works')
    app.quit()
except Exception as e:
    print('Qt xcb platform failed: ' + str(e))
\" 2>/dev/null
echo ''
echo '=== WebEngine Test ==='
python3 -c \"
import os
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu --no-sandbox'
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    view = QWebEngineView()
    print('Qt WebEngine basic import works')
    app.quit()
except Exception as e:
    print('Qt WebEngine failed: ' + str(e))
\" 2>/dev/null
echo ''
echo '=== Plymouth Status ==='
echo 'Plymouth version:'
plymouth --version 2>/dev/null || echo 'Plymouth not found'
echo ''
echo 'Current Plymouth theme:'
plymouth-set-default-theme 2>/dev/null || echo 'Cannot determine theme'
echo ''
echo 'Plymouth theme files:'
ls -la /usr/share/plymouth/themes/spacex/ 2>/dev/null || echo 'SpaceX theme not found'
echo ''
echo 'Initramfs Plymouth config:'
cat /etc/initramfs-tools/conf.d/plymouth 2>/dev/null || echo 'Plymouth initramfs config not found'
echo ''
echo '=== Network Tests ==='
echo 'Testing internet connectivity...'
ping -c 3 8.8.8.8 2>/dev/null && echo 'Internet connectivity OK' || echo 'No internet connectivity'
echo ''
echo 'Testing SpaceX API...'
curl -s --max-time 10 'https://launch-narrative-api-dafccc521fb8.herokuapp.com/launches' | head -c 200 && echo -e '\nAPI reachable' || echo 'API unreachable'
echo ''
echo 'Testing Python requests to API with SSL debugging...'
python3 -c \"
import requests
import ssl
print('SSL version:', ssl.OPENSSL_VERSION)
try:
    response = requests.get('https://launch-narrative-api-dafccc521fb8.herokuapp.com/launches', timeout=10, verify=True)
    print('SSL verified request successful:', response.status_code)
except Exception as e:
    print('SSL verified request failed:', str(e))
    try:
        response = requests.get('https://launch-narrative-api-dafccc521fb8.herokuapp.com/launches', timeout=10, verify=False)
        print('Non-SSL request successful:', response.status_code)
    except Exception as e2:
        print('Non-SSL request also failed:', str(e2))
\" 2>/dev/null || echo 'Python SSL test failed'
echo ''
echo '=== GPU/DMA Buffer Status ==='
echo \"GPU devices:\"
ls -la /dev/dri/ 2>/dev/null || echo 'No GPU devices found'
echo \"DMA heap:\"
ls -la /dev/dma_heap/ 2>/dev/null || echo 'No DMA heap found'
echo \"GPU memory info:\"
cat /proc/meminfo | grep -E \"MemTotal\|MemAvailable\|Buffers\|Cached\|SwapTotal\|SwapFree\" 2>/dev/null || echo 'Memory info unavailable'
echo \"System memory usage:\"
free -h 2>/dev/null || echo 'free command not available'
echo \"GPU cgroup status:\"
ls -la /sys/fs/cgroup/memory/gpu/ 2>/dev/null || echo 'GPU cgroup not configured'
EOF"
    sudo -u "$USER" chmod +x "$HOME_DIR/debug_x.sh"
}

configure_system() {
    log "Configuring system services..."
    
    # Enable SSH for debugging
    systemctl enable --now ssh
    
    # Note: NetworkManager is left enabled by default
    # systemctl disable NetworkManager
    # systemctl stop NetworkManager
    
    # Remove problematic driver
    apt-get remove --purge xserver-xorg-video-fbdev -y || true
    
    # Configure Xorg
    mkdir -p /etc/X11/xorg.conf.d
    cat << EOF > /etc/X11/xorg.conf.d/99-vc4.conf
Section "OutputClass"
    Identifier "vc4"
    MatchDriver "vc4"
    Driver "modesetting"
    Option "PrimaryGPU" "true"
EndSection
EOF
    
    # Enable upower if available
    [ -f /lib/systemd/system/upower.service ] && systemctl enable --now upower
    
    # Memory management sysctl settings
    cat << EOF > /etc/sysctl.d/99-memory.conf
# Memory management optimizations for Chromium
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.min_free_kbytes = 32768
EOF
    sysctl -p /etc/sysctl.d/99-memory.conf 2>/dev/null || log "WARNING: Could not apply sysctl settings"
    
    # Create systemd service for the app with memory limits
    cat << EOF > /etc/systemd/system/spacex-dashboard.service
[Unit]
Description=SpaceX Dashboard Application
After=network-online.target display-manager.service
Requires=display-manager.service

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=QT_QPA_PLATFORM=xcb
Environment=XAUTHORITY=/home/$USER/.Xauthority
Environment=QTWEBENGINE_CHROMIUM_FLAGS=--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=1024 --memory-reducer --gpu-memory-buffer-size-mb=256 --max-tiles-for-interest-area=256 --num-raster-threads=2 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --autoplay-policy=no-user-gesture-required --no-user-gesture-required-for-fullscreen
Environment=PYQTGRAPH_QT_LIB=PyQt6
Environment=QT_DEBUG_PLUGINS=0
Environment=QT_LOGGING_RULES=qt.qpa.plugin=false
Environment=DASHBOARD_WIDTH=1480
Environment=DASHBOARD_HEIGHT=320
Environment=LIBGL_ALWAYS_SOFTWARE=0
Environment=GALLIUM_DRIVER=v3d
Environment=MESA_GL_VERSION_OVERRIDE=3.3
Environment=MESA_GLSL_VERSION_OVERRIDE=330
Environment=QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt6/plugins/platforms
WorkingDirectory=/home/$USER/Desktop/project/src

ExecStart=python3 app.py
Restart=always
RestartSec=5
MemoryLimit=2.5G
MemoryHigh=2G
MemoryMax=3G

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    # Note: NetworkManager-wait-online.service may not exist in Ubuntu 25.04
    systemctl enable NetworkManager-wait-online.service 2>/dev/null || log "WARNING: NetworkManager-wait-online.service not available"
    # Disable the systemd service since we use .xsession for direct app launch
    systemctl disable spacex-dashboard.service 2>/dev/null || true
}

configure_eglfs_service() {
    log "Creating optional EGLFS (no X/LightDM) systemd service for pure kiosk mode…"
    cat << EOF > /etc/systemd/system/spacex-dashboard-eglfs.service
[Unit]
Description=SpaceX Dashboard (Qt EGLFS direct framebuffer)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Environment=QT_QPA_PLATFORM=eglfs
Environment=DASHBOARD_WIDTH=1480
Environment=DASHBOARD_HEIGHT=320
Environment=QTWEBENGINE_CHROMIUM_FLAGS=--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --autoplay-policy=no-user-gesture-required --no-user-gesture-required-for-fullscreen
WorkingDirectory=/home/$USER/Desktop/project/src
ExecStart=/usr/bin/python3 /home/$USER/Desktop/project/src/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    log "EGLFS service created (disabled by default). To use EGLFS: systemctl disable lightdm; systemctl enable --now spacex-dashboard-eglfs"
}

configure_boot() {
    log "Configuring boot settings..."
    
    local config_file="/boot/firmware/config.txt"
    local cmdline_file="/boot/firmware/cmdline.txt"
    
    # Display settings - use a marked block for idempotency and clean updates
    log "Applying display settings to $config_file..."
    # Clean up old block or any existing individual lines that might conflict
    sed -i '/# BEGIN SPACEX DASHBOARD/,/# END SPACEX DASHBOARD/d' "$config_file"
    # Also remove individual lines if they exist outside a block to avoid duplication
    for key in hdmi_force_hotplug hdmi_ignore_edid hdmi_force_mode hdmi_drive max_framebuffer_height hdmi_group hdmi_mode hdmi_timings disable_splash; do
        sed -i "/^$key=/d" "$config_file"
    done
    # Remove specific overlays that we are about to add
    sed -i '/dtoverlay=vc4-kms-v3d/d' "$config_file"

    cat << EOF >> "$config_file"

# BEGIN SPACEX DASHBOARD
# Custom display settings for Waveshare 11.9inch (1480x320 landscape, rotation via X11)
hdmi_force_hotplug=1
hdmi_ignore_edid=0xa5000080
hdmi_force_mode=1
hdmi_drive=1
max_framebuffer_height=320
hdmi_group=2
hdmi_mode=87
hdmi_timings=1480 0 80 16 32 320 0 16 4 12 0 0 0 60 0 42000000 3
dtoverlay=vc4-kms-v3d,cma-128
disable_splash=1
# END SPACEX DASHBOARD
EOF
    
    # Initramfs settings - ensure LZ4 compression is used
    if grep -q "^#\?COMPRESS=" /etc/initramfs-tools/initramfs.conf; then
        sed -i 's/^#\?COMPRESS=.*/COMPRESS=lz4/' /etc/initramfs-tools/initramfs.conf
    else
        echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
    fi
    
    # Add required modules
    for module in drm vc4; do
        grep -qxF "$module" /etc/initramfs-tools/modules || echo "$module" >> /etc/initramfs-tools/modules
    done
}

setup_repository() {
    log "Setting up repository..."
    
    mkdir -p "$HOME_DIR/Desktop"
    # Change to home directory before deleting project directory to avoid working directory issues
    cd "$HOME_DIR"
    [ -d "$REPO_DIR" ] && rm -rf "$REPO_DIR"
    # Check connectivity before cloning to avoid hard failure when DNS/network is not ready
    local can_reach=0
    if command -v curl >/dev/null 2>&1; then
        if timeout 6s curl -Is https://github.com 1>/dev/null 2>&1; then
            can_reach=1
        fi
    fi
    if [ $can_reach -eq 0 ] && command -v resolvectl >/dev/null 2>&1; then
        if timeout 5s resolvectl query github.com 1>/dev/null 2>&1; then
            can_reach=1
        fi
    fi
    if [ $can_reach -eq 0 ]; then
        log "WARNING: Network/DNS not ready; skipping git clone for now. You can rerun setup_repository later or run: git clone $REPO_URL $REPO_DIR"
    else
        # Temporarily disable 'exit on error' for clone, then restore
        set +e
        sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR"
        local clone_rc=$?
        set -e
        if [ $clone_rc -ne 0 ]; then
            log "WARNING: git clone failed (possibly transient network). You can clone manually later: git clone $REPO_URL $REPO_DIR"
        fi
    fi
    if [ -d "$REPO_DIR" ]; then
        chown -R "$USER:$USER" "$REPO_DIR"
    fi
    
    # Fix git permissions in case any operations were done as root
    if [ -d "$REPO_DIR/.git" ]; then
        # Ensure .git is owned by the desktop user and is writable
        chown -R "$USER:$USER" "$REPO_DIR/.git"
        chmod -R u+rwX,g+rX "$REPO_DIR/.git" || true

        # Mark the repo as safe for both root and the desktop user to avoid
        # "detected dubious ownership" when scripts are invoked with sudo.
        git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true
        sudo -u "$USER" -H git config --global --add safe.directory "$REPO_DIR" 2>/dev/null || true

        log "Git repository permissions and safe.directory configured"
    fi
}
    
configure_update_permissions() {
    log "Configuring update script permissions..."
    
    # Add specific sudo permissions for update script commands
    # The user already has NOPASSWD:ALL, but let's be explicit for clarity and security
    cat << EOF > /etc/sudoers.d/spacex-update
# Allow the SpaceX dashboard user to run update-related commands without password
$USER ALL=(ALL) NOPASSWD: /usr/sbin/reboot
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl
EOF
    chmod 0440 /etc/sudoers.d/spacex-update
    log "Update script sudo permissions configured"
}
    
configure_plymouth() {
    log "Configuring Plymouth boot splash screen..."

    # Install Plymouth if not already installed
    if ! command -v plymouth &> /dev/null; then
        apt-get install -y plymouth plymouth-themes
    fi

    # Create custom SpaceX Plymouth theme
    THEME_DIR="/usr/share/plymouth/themes/spacex"
    mkdir -p "$THEME_DIR"

    # Copy the SpaceX logo
    cp "$REPO_DIR/assets/images/spacex_logo.png" "$THEME_DIR/spacex_logo.png"

    # Rotate and scale the logo 90 degrees CCW (270 degrees CW) to match the 11.9" screen orientation
    # We also scale it down to fit nicely in the 1480x320 landscape view (max 500x160)
    # We do this here using ImageMagick because kernel-level rotation can be unreliable
    if command -v convert &> /dev/null; then
        log "Rotating and scaling logo 90 degrees CCW..."
        convert "$THEME_DIR/spacex_logo.png" -rotate 270 -resize 160x500 "$THEME_DIR/spacex_logo.png"
    else
        log "WARNING: ImageMagick 'convert' not found, logo will not be processed"
    fi

    # Create theme configuration file
    cat > "$THEME_DIR/spacex.plymouth" << 'EOF'
[Plymouth Theme]
Name=SpaceX
Description=A SpaceX themed Plymouth boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/spacex
ScriptFile=/usr/share/plymouth/themes/spacex/spacex.script
EOF

    # Create the script file for the theme (standardized version)
    cat > "$THEME_DIR/spacex.script" << 'EOF'
# SpaceX Plymouth Theme Script
# Use the same background color as the app for visual consistency (#1a1e1e)
Window.SetBackgroundTopColor(0.102, 0.118, 0.118);
Window.SetBackgroundBottomColor(0.102, 0.118, 0.118);

logo.image = Image("spacex_logo.png");
logo.sprite = Sprite(logo.image);

# Center the logo on screen
# The logo is pre-rotated 90 deg CCW and scaled down in the setup script for reliability
logo.x = Window.GetWidth() / 2 - logo.image.GetWidth() / 2;
logo.y = Window.GetHeight() / 2 - logo.image.GetHeight() / 2;
logo.sprite.SetX(logo.x);
logo.sprite.SetY(logo.y);

fun refresh_callback ()
{
    # Static logo, no animation needed
}

Plymouth.SetRefreshFunction(refresh_callback);
EOF

    # Set permissions
    chmod 644 "$THEME_DIR/spacex.plymouth"
    chmod 755 "$THEME_DIR/spacex.script"
    chmod 644 "$THEME_DIR/spacex_logo.png"

    # Set the default theme to our custom SpaceX theme
    log "Setting default Plymouth theme to 'spacex'..."
    if command -v plymouth-set-default-theme &> /dev/null; then
        plymouth-set-default-theme spacex
    elif [ -x /usr/sbin/plymouth-set-default-theme ]; then
        /usr/sbin/plymouth-set-default-theme spacex
    else
        log "plymouth-set-default-theme not found, using update-alternatives for spacex..."
        update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_DIR/spacex.plymouth" 200
        update-alternatives --set default.plymouth "$THEME_DIR/spacex.plymouth"
    fi

    # Rebuild initramfs with Plymouth embedded
    if ! update-initramfs -u; then
        log "WARNING: Initramfs rebuild failed"
    else
        log "✓ Initramfs rebuilt successfully with Plymouth support"
    fi

    # Copy initramfs to Raspberry Pi firmware directory (ensure it matches config.txt name)
    # The generic name 'initrd.img' is expected by our config.txt configuration
    local target_initrd="/boot/firmware/initrd.img"
    if [ -f /boot/initrd.img ]; then
        cp /boot/initrd.img "$target_initrd"
        log "✓ Initramfs copied to $target_initrd"
    else
        # Fallback: copy the newest versioned raspi initrd
        local newest_initrd=$(ls -t /boot/initrd.img-*-raspi 2>/dev/null | head -n 1)
        if [ -n "$newest_initrd" ]; then
            cp "$newest_initrd" "$target_initrd"
            log "✓ Newest initramfs ($newest_initrd) copied to $target_initrd"
        else
            log "WARNING: No initramfs images found in /boot/ to copy to $target_initrd"
        fi
    fi

    # Ensure firmware loads initramfs at boot (required for Plymouth to appear early)
    local cfg="/boot/firmware/config.txt"
    if [ -f "$cfg" ]; then
        # Use the generic initrd.img name to avoid version mismatch after kernel updates
        # flash-kernel automatically maintains this generic file in /boot/firmware/
        local initrd_file="initrd.img"
        
        # Remove any existing initramfs lines
        sed -i '/^initramfs /d' "$cfg"
        # Add the generic initramfs directive with followkernel
        echo "initramfs ${initrd_file} followkernel" >> "$cfg"
        log "✓ Enabled initramfs in config.txt: initramfs ${initrd_file} followkernel"
    fi

    # Configure kernel command line for Plymouth
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
    if [ -f "$CMDLINE_FILE" ]; then
        # Remove any existing Plymouth-related parameters and other potentially conflicting console settings
        # We want a clean slate for quiet splash boot to ensure only our desired console is used
        sed -i 's/ quiet//g; s/ splash//g; s/ loglevel=[0-9]//g; s/ vt\.global_cursor_default=[0-9]//g; s/ plymouth\.ignore-serial-consoles//g; s/ logo\.nologo//g; s/ rd\.systemd\.show_status=[a-z]*//g; s/ plymouth\.display-rotation=[0-9]//g; s/ fbcon=rotate:[0-9]//g' "$CMDLINE_FILE"
        sed -i 's/ console=tty[0-9]//g; s/ console=serial0,[0-9]*//g' "$CMDLINE_FILE"

        # Add Plymouth parameters
        if ! grep -q "splash" "$CMDLINE_FILE"; then
            sed -i 's/$/ quiet splash loglevel=3 vt.global_cursor_default=0 plymouth.ignore-serial-consoles logo.nologo rd.systemd.show_status=false/' "$CMDLINE_FILE"
        fi

        # Ensure console is moved to tty3 (avoid kernel logs on Plymouth tty)
        if ! grep -q "console=tty3" "$CMDLINE_FILE"; then
            sed -i 's/$/ console=tty3/' "$CMDLINE_FILE"
        fi

        # Ensure fbcon=map:0 for correct framebuffer mapping
        if ! grep -q "fbcon=map:0" "$CMDLINE_FILE"; then
            if grep -q "fbcon=map:[0-9]" "$CMDLINE_FILE"; then
                sed -i 's/fbcon=map:[0-9]/fbcon=map:0/g' "$CMDLINE_FILE"
            else
                sed -i 's/$/ fbcon=map:0/' "$CMDLINE_FILE"
            fi
        fi

        log "✓ Kernel command line updated for Plymouth"
    fi

    # Configure systemd to prevent getty from interfering with Plymouth
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Unit]
After=plymouth-start.service
EOF

    # Disable systemd status output on console
    mkdir -p /etc/systemd/system.conf.d
    cat > /etc/systemd/system.conf.d/quiet.conf << 'EOF'
[Manager]
ShowStatus=no
StatusUnitFormat=off
EOF

    # Create Plymouth configuration
    mkdir -p /etc/plymouth
    cat > /etc/plymouth/plymouthd.conf << EOF
[Daemon]
Theme=spacex
ShowDelay=0
DeviceTimeout=8
EOF

    log "✓ Plymouth configured with theme: spacex"

    # Make sure Plymouth units are enabled (usually pulled in by initramfs, but harmless to ensure)
    systemctl enable plymouth-start.service plymouth-quit.service plymouth-quit-wait.service 2>/dev/null || true
}

configure_touch_rotation() {
    log "Configuring touch rotation..."
    cat << EOF > /etc/udev/rules.d/99-touch-rotation.rules
SUBSYSTEM=="input", ATTRS{name}=="Goodix Capacitive TouchScreen", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0"
EOF
    udevadm control --reload-rules
}

configure_openbox() {
    log "Configuring Openbox..."
    sudo -u "$USER" mkdir -p "$HOME_DIR/.config/openbox"
    sudo -u "$USER" bash -c "cat << 'EOF' > $HOME_DIR/.config/openbox/rc.xml
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<openbox_config xmlns=\"http://openbox.org/3.4/rc\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://openbox.org/3.4/rc http://openbox.org/3.4/rc.xsd\">
  <resistance>
    <strength>0</strength>
    <screen_edge_strength>20</screen_edge_strength>
  </resistance>
  <focus>
    <focusNew>yes</focusNew>
    <followMouse>no</followMouse>
    <focusLast>yes</focusLast>
    <underMouse>no</underMouse>
    <focusDelay>200</focusDelay>
    <raiseOnFocus>no</raiseOnFocus>
  </focus>
  <placement>
    <policy>Smart</policy>
    <center>yes</center>
    <monitor>Any</monitor>
    <primaryMonitor>1</primaryMonitor>
  </placement>
  <theme>
    <name>Clearlooks</name>
    <titleLayout>NLIMC</titleLayout>
    <keepBorder>yes</keepBorder>
    <animateIconify>yes</animateIconify>
    <font place=\"ActiveWindow\">
      <name>sans</name>
      <size>8</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place=\"InactiveWindow\">
      <name>sans</name>
      <size>8</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place=\"MenuHeader\">
      <name>sans</name>
      <size>9</size>
      <weight>normal</weight>
      <slant>normal</slant>
    </font>
    <font place=\"MenuItem\">
      <name>sans</name>
      <size>9</size>
      <weight>normal</weight>
      <slant>normal</slant>
    </font>
    <font place=\"ActiveOnScreenDisplay\">
      <name>sans</name>
      <size>9</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
    <font place=\"InactiveOnScreenDisplay\">
      <name>sans</name>
      <size>9</size>
      <weight>bold</weight>
      <slant>normal</slant>
    </font>
  </theme>
  <desktops>
    <number>1</number>
    <firstdesk>1</firstdesk>
    <names>
      <name>desktop</name>
    </names>
    <popupTime>875</popupTime>
  </desktops>
  <resize>
    <drawContents>yes</drawContents>
    <popupShow>Nonpixel</popupShow>
    <popupPosition>Center</popupPosition>
  </resize>
  <margins>
    <top>0</top>
    <bottom>0</bottom>
    <left>0</left>
    <right>0</right>
  </margins>
  <dock>
    <position>TopLeft</position>
    <floatingX>0</floatingX>
    <floatingY>0</floatingY>
    <noStrut>no</noStrut>
    <stacking>Above</stacking>
    <direction>Vertical</direction>
    <autoHide>no</autoHide>
    <hideDelay>300</hideDelay>
    <showDelay>300</showDelay>
    <moveButton>Middle</moveButton>
  </dock>
  <keyboard>
    <chainQuitKey>C-g</chainQuitKey>
    <keybind key=\"A-F4\">
      <action name=\"Close\"/>
    </keybind>
    <keybind key=\"A-Escape\">
      <action name=\"Lower\"/>
      <action name=\"FocusToBottom\"/>
      <action name=\"Unfocus\"/>
    </keybind>
    <keybind key=\"A-space\">
      <action name=\"ShowMenu\">
        <menu>client-menu</menu>
      </action>
    </keybind>
  </keyboard>
  <mouse>
    <dragThreshold>1</dragThreshold>
    <doubleClickTime>500</doubleClickTime>
    <screenEdgeWarpTime>400</screenEdgeWarpTime>
    <screenEdgeWarpMouse>false</screenEdgeWarpMouse>
    <context name=\"Frame\">
      <mousebind button=\"A-Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"A-Left\" action=\"Click\">
        <action name=\"Unshade\"/>
      </mousebind>
      <mousebind button=\"A-Left\" action=\"Drag\">
        <action name=\"Move\"/>
      </mousebind>
      <mousebind button=\"A-Middle\" action=\"Press\">
        <action name=\"Lower\"/>
        <action name=\"FocusToBottom\"/>
        <action name=\"Unfocus\"/>
      </mousebind>
      <mousebind button=\"A-Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"ShowMenu\">
          <menu>client-menu</menu>
        </action>
      </mousebind>
    </context>
    <context name=\"Titlebar\">
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Move\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"DoubleClick\">
        <action name=\"ToggleMaximize\"/>
      </mousebind>
      <mousebind button=\"Up\" action=\"Click\">
        <action name=\"if\">
          <shaded>no</shaded>
          <then>
            <action name=\"Shade\"/>
            <action name=\"FocusToBottom\"/>
            <action name=\"Unfocus\"/>
            <action name=\"Lower\"/>
          </then>
        </action>
      </mousebind>
      <mousebind button=\"Down\" action=\"Click\">
        <action name=\"if\">
          <shaded>yes</shaded>
          <then>
            <action name=\"Unshade\"/>
            <action name=\"Raise\"/>
          </then>
        </action>
      </mousebind>
    </context>
    <context name=\"Titlebar Top Right Bottom Left TLCorner TRCorner BRCorner BLCorner\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"Unshade\"/>
      </mousebind>
      <mousebind button=\"Middle\" action=\"Press\">
        <action name=\"Lower\"/>
        <action name=\"FocusToBottom\"/>
        <action name=\"Unfocus\"/>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
    </context>
    <context name=\"Top\">
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Resize\">
          <edge>top</edge>
        </action>
      </mousebind>
    </context>
    <context name=\"Left\">
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Resize\">
          <edge>left</edge>
        </action>
      </mousebind>
    </context>
    <context name=\"Right\">
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Resize\">
          <edge>right</edge>
        </action>
      </mousebind>
    </context>
    <context name=\"Bottom\">
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Resize\">
          <edge>bottom</edge>
        </action>
      </mousebind>
    </context>
    <context name=\"TRCorner BRCorner TLCorner BLCorner\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"Unshade\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Drag\">
        <action name=\"Resize\"/>
      </mousebind>
    </context>
    <context name=\"Client\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Middle\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
    </context>
    <context name=\"Icon\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"Unshade\"/>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
    </context>
    <context name=\"AllDesktops\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"Unshade\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Click\">
        <action name=\"ToggleOmnipresent\"/>
      </mousebind>
    </context>
    <context name=\"Shade\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Click\">
        <action name=\"ToggleShade\"/>
      </mousebind>
    </context>
    <context name=\"Iconify\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Click\">
        <action name=\"Iconify\"/>
      </mousebind>
    </context>
    <context name=\"Maximize\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Click\">
        <action name=\"ToggleMaximize\"/>
      </mousebind>
    </context>
    <context name=\"Close\">
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Left\" action=\"Click\">
        <action name=\"Close\"/>
      </mousebind>
    </context>
    <context name=\"Desktop\">
      <mousebind button=\"Up\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>previous</to>
        </action>
      </mousebind>
      <mousebind button=\"Down\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>next</to>
        </action>
      </mousebind>
      <mousebind button=\"A-Up\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>previous</to>
        </action>
      </mousebind>
      <mousebind button=\"A-Down\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>next</to>
        </action>
      </mousebind>
      <mousebind button=\"C-A-Up\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>previous</to>
          <wrap>no</wrap>
        </action>
      </mousebind>
      <mousebind button=\"C-A-Down\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>next</to>
          <wrap>no</wrap>
        </action>
      </mousebind>
      <mousebind button=\"Left\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
      </mousebind>
    </context>
    <context name=\"Root\">
      <mousebind button=\"Middle\" action=\"Press\">
        <action name=\"Focus\"/>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
      </mousebind>
    </context>
    <context name=\"MoveResize\">
      <mousebind button=\"Up\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>previous</to>
        </action>
      </mousebind>
      <mousebind button=\"Down\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>next</to>
        </action>
      </mousebind>
      <mousebind button=\"A-Up\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>previous</to>
        </action>
      </mousebind>
      <mousebind button=\"A-Down\" action=\"Click\">
        <action name=\"GoToDesktop\">
          <to>next</to>
        </action>
      </mousebind>
    </context>
  </mouse>
  <menu>
    <file>menu.xml</file>
    <hideDelay>200</hideDelay>
    <middle>no</middle>
    <submenuShowDelay>100</submenuShowDelay>
    <submenuHideDelay>400</submenuHideDelay>
    <applicationIcons>yes</applicationIcons>
    <manageDesktops>yes</manageDesktops>
  </menu>
  <applications>
    <application class=\"*\">
      <decor>no</decor>
      <maximized>yes</maximized>
      <fullscreen>yes</fullscreen>
    </application>
  </applications>
</openbox_config>
EOF"


}

create_xinitrc() {
    log "Creating .xinitrc (fallback for manual startx)..."
    cat > "$HOME_DIR/.xinitrc" << 'EOF'
#!/bin/bash
export SHELL=/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "Starting X (matchbox session) at $(date)" > ~/xinitrc.log
# Defer to the same session script LightDM uses, which launches matchbox-window-manager and the app
exec "$HOME/.xsession"
EOF
    chown "$USER:$USER" "$HOME_DIR/.xinitrc"
    chmod +x "$HOME_DIR/.xinitrc"
}

configure_autologin() {
    log "Configuring LightDM autologin..."
    
    # Configure LightDM for autologin
    mkdir -p /etc/lightdm
    cat << EOF > /etc/lightdm/lightdm.conf
[Seat:*]
autologin-user=$USER
autologin-user-timeout=0
user-session=matchbox
greeter-enable=false
xserver-command=X -core
EOF
    
    # Also create lightdm.conf.d configuration for better compatibility
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat << EOF > /etc/lightdm/lightdm.conf.d/50-autologin.conf
[Seat:*]
autologin-user=$USER
autologin-user-timeout=0
user-session=matchbox
greeter-enable=false
EOF
    
    # Create X session entry for LightDM (matchbox session placeholder that calls ~/.xsession)
    mkdir -p /usr/share/xsessions
    cat << EOF > /usr/share/xsessions/matchbox.desktop
[Desktop Entry]
Name=Matchbox
Comment=Matchbox window manager session
Exec=/home/$USER/.xsession
TryExec=/home/$USER/.xsession
Type=Application
EOF
    
    # Create .xsession for the user
    sudo -u "$USER" bash -c "cat << 'EOF' > $HOME_DIR/.xsession
#!/bin/bash
export SHELL=/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo \"Starting X session at \$(date)\" > ~/xsession.log

# Clear any console text and switch to X tty
chvt 7 2>/dev/null || true
clear 2>/dev/null || true

# Set display settings
sleep 2

# Detect correct HDMI output name (HDMI-A-1 on Pi 5 KMS, HDMI-1 on others)
OUTPUT=$(xrandr | grep -E "^HDMI-A?-1 connected" | cut -d' ' -f1)
if [ -z "$OUTPUT" ]; then
    # Fallback to first connected output if HDMI-1/HDMI-A-1 not found
    OUTPUT=$(xrandr | grep " connected" | cut -d' ' -f1 | head -n1)
fi

echo "Using display output: $OUTPUT" >> ~/xsession.log

if [ -n "$OUTPUT" ]; then
    xrandr --output "$OUTPUT" --rotate left 2>&1 | tee -a ~/xrandr.log
else
    echo "ERROR: No connected display output found" >> ~/xsession.log
fi

# Set X settings
xset s off
xset -dpms
xset s noblank

# Hide cursor
unclutter -idle 0 -root &

# Start a lightweight window manager for kiosk (Matchbox)
matchbox-window-manager -use_titlebar no -use_cursor no &

# Set environment variables
export DASHBOARD_WIDTH=1480
export DASHBOARD_HEIGHT=320
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS=\"--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=1024 --memory-reducer --gpu-memory-buffer-size-mb=256 --max-tiles-for-interest-area=256 --num-raster-threads=2 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --autoplay-policy=no-user-gesture-required --no-user-gesture-required-for-fullscreen\"
export PYQTGRAPH_QT_LIB=PyQt6
export QT_DEBUG_PLUGINS=0
export QT_LOGGING_RULES=\"qt.qpa.plugin=false\"

# Change to app directory
cd ~/Desktop/project/src

# Truncate app log
if [ -f ~/app.log ]; then
    mv ~/app.log ~/app.log.old 2>/dev/null || true
fi
> ~/app.log

echo \"Starting SpaceX Dashboard at \$(date)\" >> ~/app.log

# Start the application
exec python3 app.py >> ~/app.log 2>&1
EOF"
    sudo -u "$USER" chmod +x "$HOME_DIR/.xsession"
    
    # Fix X authority permissions
    sudo -u "$USER" touch "$HOME_DIR/.Xauthority"
    sudo -u "$USER" chmod 600 "$HOME_DIR/.Xauthority"
    chown "$USER:$USER" "$HOME_DIR/.Xauthority"
    
    # Enable LightDM
    systemctl enable lightdm
    systemctl set-default graphical.target
    
    # Temporarily disable the systemd service to avoid conflicts during autologin testing
    systemctl disable spacex-dashboard
    
    # Start LightDM immediately to test autologin
    log "Starting LightDM to test autologin configuration..."
    systemctl start lightdm || log "WARNING: LightDM failed to start (this may be normal if X is already running)"
    
    # Remove old getty override if it exists
    rm -f /etc/systemd/system/getty@tty1.service.d/override.conf
}

optimize_performance() {
    log "Applying performance optimizations..."
    
    # WiFi power save off
    echo "options brcmfmac p2p=0" > /etc/modprobe.d/brcmfmac.conf
    iw dev wlan0 set power_save off 2>/dev/null || true
    modprobe -r brcmfmac 2>/dev/null || true
    modprobe brcmfmac 2>/dev/null || true
    
    cat << EOF > /etc/rc.local
#!/bin/sh -e
sleep 10
iw dev wlan0 set power_save off || true
exit 0
EOF
    chmod +x /etc/rc.local
}

cleanup() {
    log "Cleaning up..."
    apt-get autoremove -y
    apt-get autoclean -y
}

main() {
    mkdir -p "$HOME_DIR"
    log "Starting Raspberry Pi 5 setup on Ubuntu Server at $(date)"
    
    setup_user
    setup_gpu_permissions
    update_system
    install_packages
    configure_networkmanager
    configure_nm_polkit
    check_qt_version
    setup_python_environment
    create_debug_script
    configure_system
    configure_boot
    setup_repository
    configure_update_permissions
    configure_openbox
    configure_plymouth
    configure_touch_rotation
    create_xinitrc
    configure_autologin
    configure_eglfs_service
    optimize_performance
    
    # Note: Using LightDM autologin with .xsession for clean startup
    # The app is started directly by ~/.xsession
    # systemctl disable spacex-dashboard
    
    cleanup
    
    log "Setup complete. Rebooting in 10 seconds..."
    sleep 10
    reboot
}

main "$@"