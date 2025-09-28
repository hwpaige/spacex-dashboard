#!/bin/bash
set -e
set -o pipefail

# Trap to handle interrupts gracefully
trap 'log "Setup interrupted by user"; exit 1' INT TERM

# SpaceX Dashboard Setup Script for Raspberry Pi Ubuntu 24.04
# Optimized with modular functions and better error handling

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
    local packages=(
        # Python and core
        python3 python3-pip python3-full python3-venv git
        
        # PyQt6 and related
        python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick
        qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls
        qml6-module-qtquick-layouts qml6-module-qtcharts qml6-module-qtwebengine
        
        # Data and utilities
        python3-requests python3-dateutil python3-pandas python3-tz python3-pytz
        python3-numpy python3-scipy python3-matplotlib python3-opengl python3-pyqtgraph
        python3-psutil
        
        # System utilities
        unclutter plymouth plymouth-themes htop libgbm1 libdrm2 upower iw net-tools network-manager
        xserver-xorg xinit x11-xserver-utils openbox libinput-tools imagemagick
        ubuntu-raspi-settings xserver-xorg-video-modesetting
        
        # Graphics and display
        libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 mesa-vulkan-drivers
        mesa-opencl-icd ocl-icd-opencl-dev libgles2-mesa-dev libegl-mesa0
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1
        libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 python3-xdg
        
        # WebEngine dependencies
        libqt6webenginecore6 libqt6webenginequick6 libnss3 libatk-bridge2.0-0
        libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1
        libasound2t64 libgtk-3-0 lz4 plymouth-theme-spinner
    )
    
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

setup_python_environment() {
    log "Setting up Python environment..."

    if python3 -c "import PyQt6, requests, pandas, psutil, fastf1, plotly" 2>/dev/null; then
        log "System Python with all dependencies working (including fastf1 and plotly)"
        return
    fi

    log "Installing missing Python packages system-wide..."
    apt-get install -y python3-psutil python3-pyqt6 python3-requests python3-pandas

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
python3 -c 'import PyQt6, pyqtgraph, requests, pandas, psutil; print(\"✓ System packages working\")' 2>/dev/null || echo '✗ System Python failed'
python3 -c 'import fastf1; print(\"✓ fastf1 available\")' 2>/dev/null || echo '✗ fastf1 not available'
echo ''
echo '=== Network Tests ==='
echo 'Testing internet connectivity...'
ping -c 3 8.8.8.8 2>/dev/null && echo '✓ Internet connectivity OK' || echo '✗ No internet connectivity'
echo ''
echo 'Testing SpaceX API...'
curl -s --max-time 10 'https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5' | head -c 200 && echo -e '\n✓ API reachable' || echo '✗ API unreachable'
echo ''
echo 'Testing Python requests to API with SSL debugging...'
python3 -c "
import requests
import ssl
print('SSL version:', ssl.OPENSSL_VERSION)
try:
    # First try with SSL verification
    response = requests.get('https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5', timeout=10, verify=True)
    print(f'✓ SSL verified request successful: {response.status_code}')
except Exception as e:
    print(f'✗ SSL verified request failed: {e}')
    try:
        # Try without SSL verification as fallback
        response = requests.get('https://ll.thespacedevs.com/2.0.0/launch/upcoming/?lsp__name=SpaceX&limit=5', timeout=10, verify=False)
        print(f'✓ Non-SSL request successful: {response.status_code}')
    except Exception as e2:
        print(f'✗ Non-SSL request also failed: {e2}')
" 2>/dev/null || echo '✗ Python SSL test failed'
echo ''
echo '=== GPU/DMA Buffer Status ==='
echo \"GPU devices:\"
ls -la /dev/dri/ 2>/dev/null || echo 'No GPU devices found'
echo \"DMA heap:\"
ls -la /dev/dma_heap/ 2>/dev/null || echo 'No DMA heap found'
echo \"GPU memory info:\"
cat /proc/meminfo | grep -E \"(MemTotal|MemAvailable|Buffers|Cached|SwapTotal|SwapFree)\" 2>/dev/null || echo 'Memory info unavailable'
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
After=network.target display-manager.service
Requires=display-manager.service

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=QT_QPA_PLATFORM=xcb
Environment=XAUTHORITY=/home/$USER/.Xauthority
Environment=QTWEBENGINE_CHROMIUM_FLAGS=--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-web-security --allow-running-insecure-content --gpu-testing-vendor-id=0xFFFF --gpu-testing-device-id=0xFFFF --disable-gpu-driver-bug-workarounds
Environment=PYQTGRAPH_QT_LIB=PyQt6
Environment=QT_DEBUG_PLUGINS=0
Environment=QT_LOGGING_RULES=qt.qpa.plugin=false
Environment=LIBGL_ALWAYS_SOFTWARE=0
Environment=GALLIUM_DRIVER=v3d
Environment=MESA_GL_VERSION_OVERRIDE=3.3
Environment=MESA_GLSL_VERSION_OVERRIDE=330
Environment=EGL_PLATFORM=drm
WorkingDirectory=/home/$USER/Desktop/project/src
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
}

configure_boot() {
    log "Configuring boot settings..."
    
    local config_file="/boot/firmware/config.txt"
    local cmdline_file="/boot/firmware/cmdline.txt"
    
    # Silent boot settings with enhanced memory optimizations
    grep -q "quiet" "$cmdline_file" || 
        sed -i 's/$/ console=tty3 quiet splash loglevel=0 consoleblank=0 vt.global_cursor_default=0 plymouth.ignore-serial-consoles rd.systemd.show_status=false cma=512M coherent_pool=2M/' "$cmdline_file"
    
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
# Based on spinner theme but with centered, properly scaled logo

Window.SetBackgroundTopColor(0.0, 0.0, 0.0);
Window.SetBackgroundBottomColor(0.0, 0.0, 0.0);

# Load the SpaceX logo
logo.image = Image("spacex_logo.png");

# Scale the logo to 300x300 pixels while preserving aspect ratio
logo.width = 300;
logo.height = 300;
logo.image = logo.image.Scale(logo.width, logo.height);

# Center the logo on screen
logo.x = Window.GetWidth() / 2 - logo.width / 2;
logo.y = Window.GetHeight() / 2 - logo.height / 2;

# Draw the logo
logo.image.Draw(logo.x, logo.y);

# Optional: Add a subtle loading animation
spinner.radius = 50;
spinner.x = Window.GetWidth() / 2;
spinner.y = Window.GetHeight() / 2 + 200;
spinner.angle = 0;

fun refresh_callback ()
{
    # Clear and redraw logo
    logo.image.Draw(logo.x, logo.y);
    
    # Draw spinner if desired (comment out if not wanted)
    # spinner.angle = spinner.angle + 10;
    # Plymouth.DrawCircle(spinner.x, spinner.y, spinner.radius, 2, 1.0, 1.0, 1.0, 0.5);
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
    
    # Rebuild initramfs
    if ! update-initramfs -u; then
        log "WARNING: Initramfs rebuild failed"
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
    sudo -u "$USER" bash -c "cat << EOF > $HOME_DIR/.config/openbox/rc.xml
<openbox_config xmlns=\"http://openbox.org/3.4/rc\">
  <applications>
    <application class=\"*\">
      <decor>no</decor>
      <maximized>yes</maximized>
    </application>
  </applications>
</openbox_config>
EOF"
}

create_xinitrc() {
    log "Creating .xinitrc..."
    cat > "$HOME_DIR/.xinitrc" << 'EOF'
#!/bin/bash
export SHELL=/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "Starting openbox at $(date)" > ~/xinitrc.log
openbox-session &
sleep 2

echo "Rotating display" >> ~/xinitrc.log
xrandr --output HDMI-1 --rotate left 2>&1 | tee -a ~/xrandr.log
echo "Setting xset options" >> ~/xinitrc.log
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &

export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
# Hardware acceleration Chromium flags for Raspberry Pi with WebGL support
export QTWEBENGINE_CHROMIUM_FLAGS="--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=256 --memory-reducer --gpu-memory-buffer-size-mb=64 --max-tiles-for-interest-area=256 --num-raster-threads=2 --disable-background-timer-throttling --disable-renderer-backgrounding"
export PYQTGRAPH_QT_LIB=PyQt6
export QT_DEBUG_PLUGINS=0
export QT_LOGGING_RULES="qt.qpa.plugin=false"

cd ~/Desktop/project/src
echo "Changed to project src directory: $(pwd)" >> ~/xinitrc.log

if python3 -c 'import PyQt6, pyqtgraph, requests, pandas' 2>/dev/null; then
    echo "Using system PyQt6 at $(date)" | tee -a ~/xinitrc.log
    exec python3 app.py >> ~/app.log 2>&1
elif [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate
    echo "Using virtual environment PyQt6 at $(date)" | tee -a ~/xinitrc.log
    exec python app.py >> ~/app.log 2>&1
else
    echo "No working PyQt6 found, aborting at $(date)" | tee -a ~/xinitrc.log
    exit 1
fi
EOF
    chown "$USER:$USER" "$HOME_DIR/.xinitrc"
    chmod +x "$HOME_DIR/.xinitrc"
}

configure_autologin() {
    log "Configuring autologin..."
    
    echo "allowed_users=anybody" > /etc/X11/Xwrapper.config
    
    mkdir -p /etc/systemd/system/getty@tty1.service.d
    cat << EOF > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM
EOF
    systemctl daemon-reload
    
    sudo -u "$USER" bash -c "cat << 'EOF' > $HOME_DIR/.profile
export SHELL=/bin/bash
if [ \"\$(tty)\" = \"/dev/tty1\" ] && [ -z \"\$DISPLAY\" ]; then
    echo \"Starting X on tty1...\" | tee ~/.xstart.log
    exec startx 2>&1 | tee ~/.xstart.log
fi
EOF"
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
    setup_python_environment
    create_debug_script
    configure_system
    configure_boot
    setup_repository
    configure_plymouth
    configure_touch_rotation
    configure_openbox
    create_xinitrc
    configure_autologin
    optimize_performance
    
    # Note: Using autologin instead of systemd service to avoid conflicts
    # systemctl enable spacex-dashboard
    
    cleanup
    
    log "Setup complete. Rebooting in 10 seconds..."
    sleep 10
    reboot
}

main "$@"