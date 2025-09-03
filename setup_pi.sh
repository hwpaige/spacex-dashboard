#!/bin/bash
set -e
set -o pipefail

# SpaceX Dashboard Setup Script for Raspberry Pi 5 with Ubuntu 24.04
# This script prioritizes system PyQt6 (which you've been using successfully)
# and only falls back to virtual environment if system PyQt6 is incomplete
#
# IMPORTANT: If you encounter "Bus error" during setup, this is likely due to
# Qt library conflicts betw            python -m pip install pyqtgraph --upgrade --force-reinstall 2>/dev/null || trueen system and virtual environment PyQt6.
# The script will continue and try to use system PyQt6 instead.

USER="harrison"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"

echo "Starting Raspberry Pi 5 setup on Ubuntu Server at $(date)" | tee -a "$LOG_FILE"

# Create user if not exists
if ! id "$USER" &>/dev/null; then
    echo "Creating user $USER..." | tee -a "$LOG_FILE"
    adduser --disabled-password --gecos "" "$USER" | tee -a "$LOG_FILE"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers.d/"$USER"
    chmod 0440 /etc/sudoers.d/"$USER"
    # Set blank password for autologin (only on creation)
    sudo passwd -d "$USER" | tee -a "$LOG_FILE"
fi

echo "Creating .Xauthority file to avoid initial xauth notice..." | tee -a "$LOG_FILE"
sudo -u "$USER" touch "$HOME_DIR/.Xauthority"
sudo -u "$USER" chmod 600 "$HOME_DIR/.Xauthority"

# Add user to graphics and console groups for DRM/EGLFS/X access
usermod -aG render,video,tty,input "$USER" | tee -a "$LOG_FILE"

# Ensure GPU device permissions are correct
echo "Setting GPU device permissions..." | tee -a "$LOG_FILE"
GPU_RULES="/etc/udev/rules.d/99-gpu-permissions.rules"
cat << EOF > "$GPU_RULES"
# Allow video group access to GPU devices
SUBSYSTEM=="drm", KERNEL=="card*", GROUP="video", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", GROUP="render", MODE="0660"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
udevadm trigger | tee -a "$LOG_FILE"

# Set user's default shell to bash
usermod -s /bin/bash "$USER" | tee -a "$LOG_FILE"

# Enable universe repository and update system
echo "Enabling universe repository and updating system..." | tee -a "$LOG_FILE"
apt-get install -y software-properties-common | tee -a "$LOG_FILE"
add-apt-repository universe -y | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
echo "System updated." | tee -a "$LOG_FILE"

# Install all system packages in one go
echo "Installing all system packages..." | tee -a "$LOG_FILE"
PACKAGES="
  python3 python3-pip python3-full git
  python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick
  python3-requests python3-dateutil python3-pandas python3-tz python3-pytz
  python3-numpy python3-scipy python3-matplotlib python3-opengl python3-pyqtgraph
  unclutter plymouth plymouth-themes
  libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers
  htop libgbm1 libdrm2 upower iw net-tools
  qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls
  qml6-module-qtquick-layouts qml6-module-qtcharts qml6-module-qtwebengine
  lz4 plymouth-theme-spinner
  xserver-xorg xinit x11-xserver-utils openbox libinput-tools
  ubuntu-raspi-settings xserver-xorg-video-modesetting
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
  libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1
  libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 python3-xdg
  libqt6webenginecore6 libqt6webenginequick6 libnss3 libatk-bridge2.0-0
  libdrm2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1
  libasound2t64 libgtk-3-0
"

if apt-get install -y $PACKAGES 2>&1 | tee -a "$LOG_FILE"; then
    echo "All packages installed successfully." | tee -a "$LOG_FILE"
else
    echo "Some packages failed to install, but continuing..." | tee -a "$LOG_FILE"
fi

# Install version-specific python venv package
echo "Installing Python venv package for current Python version..." | tee -a "$LOG_FILE"
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if apt-get install -y "python${PYTHON_VERSION}-venv" 2>&1 | tee -a "$LOG_FILE"; then
    echo "Python venv package for version $PYTHON_VERSION installed successfully." | tee -a "$LOG_FILE"
else
    echo "Failed to install python${PYTHON_VERSION}-venv, trying python3-venv..." | tee -a "$LOG_FILE"
    apt-get install -y python3-venv | tee -a "$LOG_FILE"
fi

# Clean up
echo "Cleaning up..." | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"

# Setup Python environment
echo "Setting up Python environment..." | tee -a "$LOG_FILE"

# Test system PyQt6
if python3 -c "import PyQt6, pyqtgraph, requests, pandas; print('System Python ready')" 2>/dev/null; then
    echo "System Python with all dependencies working - using system Python" | tee -a "$LOG_FILE"
    USE_SYSTEM_PYQT6=true
else
    echo "System Python incomplete - creating virtual environment..." | tee -a "$LOG_FILE"
    USE_SYSTEM_PYQT6=false

    # Create and setup virtual environment
    VENV_DIR="$HOME_DIR/.venv"
    python3 -m venv "$VENV_DIR" | tee -a "$LOG_FILE"
    sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && python -m pip install --upgrade pip" | tee -a "$LOG_FILE"
    sudo -u "$USER" bash -c "source $VENV_DIR/bin/activate && python -m pip install PyQt6 pyqtgraph requests python-dateutil pandas pytz" | tee -a "$LOG_FILE"
fi

# Create simple debug script
echo "Creating debug script..." | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cd $HOME_DIR && cat << 'EOF' > debug_x.sh
#!/bin/bash
echo \"=== System Status ===\"
echo \"User: $(whoami) | Display: $DISPLAY\"
echo \"Python: $(python3 --version 2>/dev/null || echo 'Not found')\"
echo \"\"
echo \"=== Package Tests ===\"
python3 -c 'import PyQt6, pyqtgraph, requests, pandas; print(\"✓ All packages working\")' 2>/dev/null || echo \"✗ System Python failed\"
echo \"\"
if [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate
    python -c 'import PyQt6, pyqtgraph, requests, pandas; print(\"✓ Virtual environment working\")' 2>/dev/null || echo \"✗ Virtual environment failed\"
else
    echo \"No virtual environment found\"
fi
EOF"
sudo -u "$USER" chmod +x "$HOME_DIR/debug_x.sh"
echo "Debug script created." | tee -a "$LOG_FILE"

# Enable SSH
echo "Enabling SSH..." | tee -a "$LOG_FILE"
systemctl enable --now ssh | tee -a "$LOG_FILE"

# Remove fbdev driver to prevent Xorg fallback error
echo "Removing incompatible fbdev driver..." | tee -a "$LOG_FILE"
apt remove --purge xserver-xorg-video-fbdev -y | tee -a "$LOG_FILE"

# Configure Xorg for vc4 modesetting to fix framebuffer mode error
echo "Configuring Xorg for vc4 modesetting..." | tee -a "$LOG_FILE"
mkdir -p /etc/X11/xorg.conf.d
cat << EOF > /etc/X11/xorg.conf.d/99-vc4.conf
Section "OutputClass"
    Identifier "vc4"
    MatchDriver "vc4"
    Driver "modesetting"
    Option "PrimaryGPU" "true"
EndSection
EOF

# Enable upower service if installed
if [ -f /lib/systemd/system/upower.service ]; then
    systemctl enable --now upower | tee -a "$LOG_FILE"
fi
echo "System packages installed." | tee -a "$LOG_FILE"

# Raspberry Pi boot configuration for landscape mode
CONFIG_FILE="/boot/firmware/config.txt"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
echo "Configuring silent boot, splash screen, and display..." | tee -a "$LOG_FILE"
if ! grep -q "quiet" "$CMDLINE_FILE"; then
    sed -i 's/$/ console=tty3 quiet splash loglevel=0 consoleblank=0 vt.global_cursor_default=0 plymouth.ignore-serial-consoles rd.systemd.show_status=false/' "$CMDLINE_FILE" || true
fi
if ! grep -q "hdmi_mode=87" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# Custom display settings for Waveshare 11.9inch (1480x320 landscape, rotation via X11)" >> "$CONFIG_FILE"
    echo "hdmi_force_hotplug=1" >> "$CONFIG_FILE"
    echo "hdmi_ignore_edid=0xa5000080" >> "$CONFIG_FILE"
    echo "hdmi_force_mode=1" >> "$CONFIG_FILE"
    echo "hdmi_drive=1" >> "$CONFIG_FILE"
    echo "max_framebuffer_height=320" >> "$CONFIG_FILE"
    echo "hdmi_group=2" >> "$CONFIG_FILE"
    echo "hdmi_mode=87" >> "$CONFIG_FILE"
    echo "hdmi_timings=1480 0 80 16 32 320 0 16 4 12 0 0 0 60 0 42000000 3" >> "$CONFIG_FILE"
    echo "dtoverlay=vc4-kms-v3d-pi5,cma-512" >> "$CONFIG_FILE"  # Pi5-specific with 512MB CMA for stability
    echo "# GPU memory settings for hardware acceleration" >> "$CONFIG_FILE"
    echo "gpu_mem=256" >> "$CONFIG_FILE"
    echo "gpu_mem_256=128" >> "$CONFIG_FILE"
    echo "gpu_mem_512=256" >> "$CONFIG_FILE"
    echo "gpu_mem_1024=512" >> "$CONFIG_FILE"
fi

# Set initramfs compression
if ! grep -q "^COMPRESS=lz4" /etc/initramfs-tools/initramfs.conf; then
    echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
fi

# Add modules for Plymouth to work with vc4-kms-v3d (avoid duplicates)
echo "Adding modules to initramfs for Plymouth splash..." | tee -a "$LOG_FILE"
grep -qxF "drm" /etc/initramfs-tools/modules || echo "drm" >> /etc/initramfs-tools/modules
grep -qxF "vc4" /etc/initramfs-tools/modules || echo "vc4" >> /etc/initramfs-tools/modules

# Clone GitHub repository to Desktop
echo "Cloning GitHub repository to Desktop..." | tee -a "$LOG_FILE"
REPO_URL="https://github.com/hwpaige/spacex-dashboard"
REPO_DIR="$HOME_DIR/Desktop/project"
if [ -d "$REPO_DIR" ]; then rm -rf "$REPO_DIR" | tee -a "$LOG_FILE"; fi
sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$REPO_DIR" | tee -a "$LOG_FILE"
echo "Repository cloned to $REPO_DIR." | tee -a "$LOG_FILE"

# Customize Plymouth spinner theme with SpaceX logo
echo "Customizing Plymouth spinner theme with SpaceX logo..." | tee -a "$LOG_FILE"
cp "$REPO_DIR/spacex_logo.png" /usr/share/plymouth/themes/spinner/bgrt-fallback.png

# Set Plymouth theme to spinner (default with custom logo)
echo "Setting Plymouth theme to spinner..." | tee -a "$LOG_FILE"
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth 100 | tee -a "$LOG_FILE"
update-alternatives --set default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth | tee -a "$LOG_FILE"

# Rebuild initramfs to include changes (with error handling)
echo "Rebuilding initramfs..." | tee -a "$LOG_FILE"
if update-initramfs -u 2>&1 | tee -a "$LOG_FILE"; then
    echo "Initramfs rebuilt successfully" | tee -a "$LOG_FILE"
else
    echo "WARNING: Initramfs rebuild failed - system may not boot properly" | tee -a "$LOG_FILE"
    echo "Consider running: update-initramfs -u -k \$(uname -r)" | tee -a "$LOG_FILE"
fi

# Configure touch for 90° CCW rotation (left)
echo "Configuring touch rotation for 90° CCW..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
SUBSYSTEM=="input", ATTRS{name}=="Goodix Capacitive TouchScreen", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
echo "Touch rotation configured." | tee -a "$LOG_FILE"

# Configure Openbox for borderless fullscreen kiosk mode
echo "Configuring Openbox for borderless fullscreen..." | tee -a "$LOG_FILE"
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
echo "Openbox configured." | tee -a "$LOG_FILE"

# Create .xinitrc for X11 start with rotation and no screen timeout
echo "Creating .xinitrc for X11 with rotation and no screen timeout..." | tee -a "$LOG_FILE"
cat > "$HOME_DIR/.xinitrc" << 'EOF'
#!/bin/bash
# Set proper shell environment
export SHELL=/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Start Openbox window manager
openbox-session &
sleep 2

# Configure display rotation (use HDMI-1 as per Xorg log; change if needed)
xrandr --output HDMI-1 --rotate left 2>&1 | tee ~/xrandr.log

# Disable screen timeout and blanking
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor
unclutter -idle 0 -root &

# Set Qt environment variables
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --enable-accelerated-video-decode"
export PYQTGRAPH_QT_LIB=PyQt6
export QT_DEBUG_PLUGINS=0
export QT_LOGGING_RULES="qt.qpa.plugin=false"

# Prefer system PyQt6 (as per your setup), but fallback to venv if needed
if python3 -c 'import PyQt6, pyqtgraph, requests, pandas; print("System ready")' 2>/dev/null; then
    echo "Using system PyQt6" | tee ~/xinitrc.log
elif [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate
    echo "Using virtual environment PyQt6" | tee ~/xinitrc.log
else
    echo "No working PyQt6 found, aborting" | tee ~/xinitrc.log
    exit 1
fi

# Test and run application
if python3 -c 'import pyqtgraph; print("Ready")' 2>/dev/null; then
    echo "Starting application..." | tee -a ~/xinitrc.log
    exec python3 ~/Desktop/project/app.py > ~/app.log 2>&1
else
    echo "pyqtgraph failed, trying virtual environment..." | tee -a ~/xinitrc.log
    if [ -f ~/.venv/bin/activate ]; then
        source ~/.venv/bin/activate
        echo "Starting application with virtual environment..." | tee -a ~/xinitrc.log
        exec python ~/Desktop/project/app.py > ~/app.log 2>&1
    else
        echo "No working environment found, aborting" | tee -a ~/xinitrc.log
        exit 1
    fi
fi
EOF
chown "$USER:$USER" "$HOME_DIR/.xinitrc"
chmod +x "$HOME_DIR/.xinitrc"
echo ".xinitrc created." | tee -a "$LOG_FILE"

# Allow any user to start X server (required for reliable autologin on Pi)
echo "Configuring Xwrapper for anybody..." | tee -a "$LOG_FILE"
echo "allowed_users=anybody" > /etc/X11/Xwrapper.config

# Configure console autologin and start X
echo "Configuring console autologin and start X..." | tee -a "$LOG_FILE"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat << EOF > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM
EOF
systemctl daemon-reload | tee -a "$LOG_FILE"

# Launch X from .profile only on tty1 (more reliable for autologin sourcing)
sudo -u "$USER" bash -c "cd $HOME_DIR && cat << 'EOF' > .profile
# Set default shell to bash
export SHELL=/bin/bash

# Autostart X on tty1 if not already running
if [ \"\$(tty)\" = \"/dev/tty1\" ] && [ -z \"\$DISPLAY\" ]; then
    echo \"Starting X on tty1...\" | tee ~/.xstart.log
    exec startx 2>&1 | tee ~/.xstart.log
fi
EOF"
echo "X configured to start directly on console." | tee -a "$LOG_FILE"

# WiFi and other optimizations
echo "options brcmfmac p2p=0" | tee /etc/modprobe.d/brcmfmac.conf | tee -a "$LOG_FILE"
iw dev wlan0 set power_save off || true | tee -a "$LOG_FILE"
modprobe -r brcmfmac || true | tee -a "$LOG_FILE"
modprobe brcmfmac | tee -a "$LOG_FILE"
cat << EOF > /etc/rc.local
#!/bin/sh -e
sleep 10
iw dev wlan0 set power_save off || true
exit 0
EOF
chmod +x /etc/rc.local

# Optimize performance
echo "Optimizing performance..." | tee -a "$LOG_FILE"
echo "Performance optimizations applied." | tee -a "$LOG_FILE"

echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot