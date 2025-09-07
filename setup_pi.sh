#!/bin/bash
set -e
set -o pipefail

# SpaceX Dashboard Setup Script for Raspberry Pi 5 with Ubuntu 24.04
# Optimized version with modular functions and better error handling

USER="${SUDO_USER:-harrison}"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"
REPO_URL="https://github.com/hwpaige/spacex-dashboard"
REPO_DIR="$HOME_DIR/Desktop/project"
VENV_DIR="$HOME_DIR/.venv"

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
    log "Setting GPU device permissions..."
    cat << EOF > /etc/udev/rules.d/99-gpu-permissions.rules
SUBSYSTEM=="drm", KERNEL=="card*", GROUP="video", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", GROUP="render", MODE="0660"
EOF
    udevadm control --reload-rules && udevadm trigger
}

update_system() {
    log "Updating system packages..."
    apt-get update -y && apt-get upgrade -y --no-install-recommends
    apt-get install -y software-properties-common
    add-apt-repository universe -y
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
        
        # System utilities
        unclutter plymouth plymouth-themes htop libgbm1 libdrm2 upower iw net-tools
        xserver-xorg xinit x11-xserver-utils openbox libinput-tools
        ubuntu-raspi-settings xserver-xorg-video-modesetting
        
        # Graphics and display
        libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 mesa-vulkan-drivers
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1
        libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 python3-xdg
        
        # WebEngine dependencies
        libqt6webenginecore6 libqt6webenginequick6 libnss3 libatk-bridge2.0-0
        libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1
        libasound2t64 libgtk-3-0 lz4 plymouth-theme-spinner
    )
    
    if ! apt-get install -y --no-install-recommends "${packages[@]}"; then
        log "WARNING: Some packages failed to install, continuing..."
    fi
}

setup_python_environment() {
    log "Setting up Python environment..."
    
    if python3 -c "import PyQt6, pyqtgraph, requests, pandas" 2>/dev/null; then
        log "System Python with all dependencies working"
        return
    fi
    
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR" || error_exit "Failed to create venv"
    sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && python -m pip install --upgrade pip"
    sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && pip install PyQt6 pyqtgraph requests python-dateutil pandas pytz psutil"
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
python3 -c 'import PyQt6, pyqtgraph, requests, pandas; print(\"✓ All packages working\")' 2>/dev/null || echo '✗ System Python failed'
echo ''
if [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate
    python -c 'import PyQt6, pyqtgraph, requests, pandas; print(\"✓ Virtual environment working\")' 2>/dev/null || echo '✗ Virtual environment failed'
else
    echo 'No virtual environment found'
fi
EOF"
    sudo -u "$USER" chmod +x "$HOME_DIR/debug_x.sh"
}

configure_system() {
    log "Configuring system services..."
    
    # Enable SSH
    systemctl enable --now ssh
    
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
}

configure_boot() {
    log "Configuring boot settings..."
    
    local config_file="/boot/firmware/config.txt"
    local cmdline_file="/boot/firmware/cmdline.txt"
    
    # Silent boot settings
    grep -q "quiet" "$cmdline_file" || 
        sed -i 's/$/ console=tty3 quiet splash loglevel=0 consoleblank=0 vt.global_cursor_default=0 plymouth.ignore-serial-consoles rd.systemd.show_status=false/' "$cmdline_file"
    
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
    
    [ -d "$REPO_DIR" ] && rm -rf "$REPO_DIR"
    sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR"
    chown -R "$USER:$USER" "$REPO_DIR"
}

configure_plymouth() {
    log "Configuring Plymouth..."
    
    # Copy custom logo
    cp "$REPO_DIR/spacex_logo.png" /usr/share/plymouth/themes/spinner/bgrt-fallback.png
    
    # Set theme
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth 100
    update-alternatives --set default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth
    
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

openbox-session &
sleep 2

xrandr --output HDMI-1 --rotate left 2>&1 | tee ~/xrandr.log
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &

export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --enable-accelerated-video-decode"
export PYQTGRAPH_QT_LIB=PyQt6
export QT_DEBUG_PLUGINS=0
export QT_LOGGING_RULES="qt.qpa.plugin=false"

if python3 -c 'import PyQt6, pyqtgraph, requests, pandas' 2>/dev/null; then
    echo "Using system PyQt6" | tee ~/xinitrc.log
elif [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate
    echo "Using virtual environment PyQt6" | tee ~/xinitrc.log
else
    echo "No working PyQt6 found, aborting" | tee ~/xinitrc.log
    exit 1
fi

if python3 -c 'import pyqtgraph' 2>/dev/null; then
    echo "Starting application..." | tee -a ~/xinitrc.log
    exec python3 ~/Desktop/project/app.py > ~/app.log 2>&1
else
    source ~/.venv/bin/activate
    echo "Starting application with virtual environment..." | tee -a ~/xinitrc.log
    exec python ~/Desktop/project/app.py > ~/app.log 2>&1
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
    cleanup
    
    log "Setup complete. Rebooting in 10 seconds..."
    sleep 10
    reboot
}

main "$@"