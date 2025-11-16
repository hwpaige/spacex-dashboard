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
    echo "ERROR: $@" | tee -a "$LOG_FILE"
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
    usermod -aG render,video,tty,input "$USER"
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
$USER soft memlock 128M
$USER hard memlock 256M
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
        xserver-xorg xinit x11-xserver-utils openbox libinput-tools imagemagick
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
curl -s --max-time 10 'https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5' | head -c 200 && echo -e '\nAPI reachable' || echo 'API unreachable'
echo ''
echo 'Testing Python requests to API with SSL debugging...'
python3 -c \"
import requests
import ssl
print('SSL version:', ssl.OPENSSL_VERSION)
try:
    response = requests.get('https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5', timeout=10, verify=True)
    print('SSL verified request successful:', response.status_code)
except Exception as e:
    print('SSL verified request failed:', str(e))
    try:
        response = requests.get('https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5', timeout=10, verify=False)
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
Environment=QTWEBENGINE_CHROMIUM_FLAGS=--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=256 --memory-reducer --gpu-memory-buffer-size-mb=64 --max-tiles-for-interest-area=256 --num-raster-threads=2 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows
Environment=PYQTGRAPH_QT_LIB=PyQt6
Environment=QT_DEBUG_PLUGINS=0
Environment=QT_LOGGING_RULES=qt.qpa.plugin=false
Environment=LIBGL_ALWAYS_SOFTWARE=0
Environment=GALLIUM_DRIVER=v3d
Environment=MESA_GL_VERSION_OVERRIDE=3.3
Environment=MESA_GLSL_VERSION_OVERRIDE=330
Environment=QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt6/plugins/platforms
WorkingDirectory=/home/$USER/Desktop/project/src
ExecStartPre=/bin/bash -c 'nmcli device wifi rescan; timeout 30 bash -c "until nmcli device | grep wifi | grep -q connected; do sleep 2; done"'
ExecStart=python3 app.py
Restart=always
RestartSec=5
MemoryLimit=512M
MemoryHigh=384M
MemoryMax=512M

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    # Note: NetworkManager-wait-online.service may not exist in Ubuntu 25.04
    systemctl enable NetworkManager-wait-online.service 2>/dev/null || log "WARNING: NetworkManager-wait-online.service not available"
    # Disable the systemd service since we use .xsession for direct app launch
    systemctl disable spacex-dashboard.service 2>/dev/null || true
}

configure_boot() {
    log "Configuring boot settings..."
    
    local config_file="/boot/firmware/config.txt"
    local cmdline_file="/boot/firmware/cmdline.txt"
    
    # Silent boot settings with enhanced memory optimizations
    # Note: Removed logo.nologo to allow Plymouth splash screen
    if ! grep -q "fbcon=map:2" "$cmdline_file"; then
        sed -i 's/$/ fbcon=map:2/' "$cmdline_file"
    fi
    
    # Display settings
    if ! grep -q "hdmi_mode=87" "$config_file"; then
        cat << EOF >> "$config_file"

# Custom display settings for Waveshare 11.9inch (1480x320 landscape, rotation via X11)
hdmi_force_hotplug=1
hdmi_ignore_edid=0xa5000080
hdmi_force_mode=1
hdmi_drive=1
max_framebuffer_height=320
hdmi_group=2
hdmi_mode=87
hdmi_timings=1480 0 80 16 32 320 0 16 4 12 0 0 0 60 0 42000000 3
dtoverlay=vc4-kms-v3d
dtoverlay=vc4-kms-v3d,cma-128
dtoverlay=vc4-kms-v3d-pi5
EOF
    fi
    
    # Initramfs settings
    grep -q "^COMPRESS=lz4" /etc/initramfs-tools/initramfs.conf || echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
    
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
    sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR"
    chown -R "$USER:$USER" "$REPO_DIR"
}
    
configure_plymouth() {
    log "Configuring Plymouth..."
    
    # Install Plymouth if not already installed
    if ! command -v plymouth &> /dev/null; then
        apt-get install -y plymouth plymouth-themes
    fi
    
    # Create custom SpaceX Plymouth theme
    THEME_DIR="/usr/share/plymouth/themes/spacex"
    mkdir -p "$THEME_DIR"
    
    # Copy the SpaceX logo
    cp "$REPO_DIR/assets/images/spacex_logo.png" "$THEME_DIR/spacex_logo.png"
    
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
    
    # Create the script file for the theme
    cat > "$THEME_DIR/spacex.script" << 'EOF'
# SpaceX Plymouth Theme Script
# Matches the Qt app loading screen exactly

# Set background color to match Qt dark theme (#1c2526)
Window.SetBackgroundTopColor(0.11, 0.145, 0.149);
Window.SetBackgroundBottomColor(0.11, 0.145, 0.149);

# Load the SpaceX logo
logo.image = Image("spacex_logo.png");

# Scale the logo to 300x300 pixels while preserving aspect ratio
logo.width = 300;
logo.height = 300;
logo.image = logo.image.Scale(logo.width, logo.height);

# Center the logo on screen
logo.x = Window.GetWidth() / 2 - logo.width / 2;
logo.y = Window.GetHeight() / 2 - logo.height / 2;

# Initialize bouncing dots animation
dot1.y_offset = 0;
dot2.y_offset = 0;
dot3.y_offset = 0;
dot1.animation_phase = 0;
dot2.animation_phase = 0.33;  # Offset phases for staggered animation
dot3.animation_phase = 0.66;

fun refresh_callback ()
{
    # Clear screen with background color
    Plymouth.FillScreen(0.11, 0.145, 0.149);
    
    # Draw the logo
    logo.image.Draw(logo.x, logo.y);
    
    # Calculate dot positions (below logo, matching Qt layout)
    dot_y_base = logo.y + logo.height + 30;  # 30px below logo
    dot_spacing = 20;  # Space between dots
    dot_size = 12;
    
    # Calculate animation offsets for bouncing effect
    time = Plymouth.GetTime() / 1000.0;  # Convert to seconds
    
    # Dot 1 animation (bounce every 1.4 seconds)
    dot1.animation_phase = (time * 1.4) % 1.0;
    if (dot1.animation_phase < 0.5) {
        dot1.y_offset = -10 * Plymouth.Sin(dot1.animation_phase * 3.14159);
    } else {
        dot1.y_offset = -10 * Plymouth.Sin((1.0 - dot1.animation_phase) * 3.14159);
    }
    
    # Dot 2 animation (offset by 0.33)
    dot2.animation_phase = ((time * 1.4) + 0.33) % 1.0;
    if (dot2.animation_phase < 0.5) {
        dot2.y_offset = -10 * Plymouth.Sin(dot2.animation_phase * 3.14159);
    } else {
        dot2.y_offset = -10 * Plymouth.Sin((1.0 - dot2.animation_phase) * 3.14159);
    }
    
    # Dot 3 animation (offset by 0.66)
    dot3.animation_phase = ((time * 1.4) + 0.66) % 1.0;
    if (dot3.animation_phase < 0.5) {
        dot3.y_offset = -10 * Plymouth.Sin(dot3.animation_phase * 3.14159);
    } else {
        dot3.y_offset = -10 * Plymouth.Sin((1.0 - dot3.animation_phase) * 3.14159);
    }
    
    # Draw the three bouncing dots
    center_x = Window.GetWidth() / 2;
    
    # Dot 1 (left)
    Plymouth.FillCircle(center_x - dot_spacing - dot_size/2, dot_y_base + dot1.y_offset, dot_size/2, 1.0, 1.0, 1.0, 1.0);
    
    # Dot 2 (center)
    Plymouth.FillCircle(center_x, dot_y_base + dot2.y_offset, dot_size/2, 1.0, 1.0, 1.0, 1.0);
    
    # Dot 3 (right)
    Plymouth.FillCircle(center_x + dot_spacing + dot_size/2, dot_y_base + dot3.y_offset, dot_size/2, 1.0, 1.0, 1.0, 1.0);
}

Plymouth.SetRefreshFunction(refresh_callback);
EOF
    
    # Set permissions
    chmod 644 "$THEME_DIR/spacex.plymouth"
    chmod 755 "$THEME_DIR/spacex.script"
    chmod 644 "$THEME_DIR/spacex_logo.png"
    
    # Install and set the custom theme
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_DIR/spacex.plymouth" 200
    update-alternatives --set default.plymouth "$THEME_DIR/spacex.plymouth"
    
    # Enable Plymouth in initramfs
    echo "FRAMEBUFFER=y" > /etc/initramfs-tools/conf.d/plymouth
    echo "plymouth plymouth/themes/select select spacex" | debconf-set-selections
    
    # Rebuild initramfs
    if ! update-initramfs -u; then
        log "WARNING: Initramfs rebuild failed"
    else
        log "✓ Initramfs rebuilt successfully with Plymouth support"
    fi
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
        <action name=\"ShowMenu\">
          <menu>client-menu</menu>
        </action>
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
        <action name=\"ShowMenu\">
          <menu>client-menu</menu>
        </action>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"Focus\"/>
        <action name=\"Raise\"/>
        <action name=\"ShowMenu\">
          <menu>client-menu</menu>
        </action>
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
        <action name=\"ShowMenu\">
          <menu>client-list-combined-menu</menu>
        </action>
      </mousebind>
      <mousebind button=\"Right\" action=\"Press\">
        <action name=\"ShowMenu\">
          <menu>root-menu</menu>
        </action>
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

echo "Starting openbox at $(date)" > ~/xinitrc.log
exec openbox-session
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
user-session=openbox
greeter-enable=false
xserver-command=X -core
EOF
    
    # Also create lightdm.conf.d configuration for better compatibility
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat << EOF > /etc/lightdm/lightdm.conf.d/50-autologin.conf
[Seat:*]
autologin-user=$USER
autologin-user-timeout=0
user-session=openbox
greeter-enable=false
EOF
    
    # Create X session script for LightDM
    mkdir -p /usr/share/xsessions
    cat << EOF > /usr/share/xsessions/openbox.desktop
[Desktop Entry]
Name=Openbox
Comment=Openbox window manager
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
xrandr --output HDMI-1 --rotate left 2>&1 | tee -a ~/xrandr.log

# Set X settings
xset s off
xset -dpms
xset s noblank

# Hide cursor
unclutter -idle 0 -root &

# Set environment variables
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS=\"--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=256 --memory-reducer --gpu-memory-buffer-size-mb=64 --max-tiles-for-interest-area=256 --num-raster-threads=2 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows\"
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
    check_qt_version
    setup_python_environment
    create_debug_script
    configure_system
    configure_boot
    setup_repository
    configure_plymouth
    configure_touch_rotation
    create_xinitrc
    configure_autologin
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