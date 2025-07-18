#!/bin/bash

# Banana Pi M4 Zero setup script for Armbian Ubuntu Server (e.g., 24.04 or 25.04)
# Configures SPI, WiFi, minimal GUI (Xorg, Openbox, LightDM), auto-login, kiosk mode, and launches PyQt-embedded SpaceX Dash app on boot
# Run with: sudo bash setup_ubuntu.sh (from /home/harrison/Desktop or any directory)
# Requires internet access, 5V 3A USB-C power supply, 16GB+ SD card (Samsung EVO Plus recommended)
# Logs to /home/harrison/setup_ubuntu.log
# Assumes user 'harrison' exists; creates if not. Prompts for WiFi if not configured.
# Note: Waveshare 11.9inch HDMI LCD settings are adapted but may need manual tweaking for full compatibility.

set -e

# Log file for debugging in the user's home directory
USER="harrison"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"
echo "Starting Banana Pi M4 Zero setup on Armbian Ubuntu Server at $(date)" | tee -a "$LOG_FILE"

# Step 0: Create user if not exists (non-interactive, no password for auto-login)
if ! id "$USER" &>/dev/null; then
    echo "Creating user $USER..." | tee -a "$LOG_FILE"
    adduser --disabled-password --gecos "" "$USER" | tee -a "$LOG_FILE"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers.d/"$USER"
    chmod 0440 /etc/sudoers.d/"$USER"
fi

# Step 1: Configure swap (512MB) for memory-intensive tasks
echo "Configuring 512MB swap file..." | tee -a "$LOG_FILE"
if [ ! -f /swapfile ]; then
    fallocate -l 512M /swapfile | tee -a "$LOG_FILE"
    chmod 600 /swapfile | tee -a "$LOG_FILE"
    mkswap /swapfile | tee -a "$LOG_FILE"
    swapon /swapfile | tee -a "$LOG_FILE"
    echo "/swapfile none swap sw 0 0" | tee -a /etc/fstab
fi
echo "Swap configured." | tee -a "$LOG_FILE"

# Step 2: Update and upgrade system, but freeze kernel to prevent WiFi breakage
echo "Updating and upgrading Ubuntu Server (kernel held)..." | tee -a "$LOG_FILE"
apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64 | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Step 3: Install required system packages (PyQt5, XCB, minimal GUI, Plymouth)
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pyqt5 python3-pyqt5.qtwebengine python3-pip python3-venv git xorg openbox lightdm lightdm-gtk-greeter x11-xserver-utils curl libxcb1 libxcb-xinerama0 libxcb-cursor0 libxcb-xinput0 libxcb-keysyms1 libxcb-shape0 libxcb-xfixes0 libxkbcommon-x11-0 libxcb-render0 libxcb-render-util0 libxcb-randr0 libxcb-sync1 libxcb-xkb1 libxcb-icccm4 libxkbcommon0 libqt5gui5 libqt5dbus5 libqt5core5a libqt5network5 libqt5widgets5 unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics armbian-firmware-full | tee -a "$LOG_FILE"
apt-get reinstall -y python3-pyqt5 python3-pyqt5.qtwebengine plymouth plymouth-themes | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

# Step 4: Enable SSH (already installed per error output)
echo "Enabling SSH..." | tee -a "$LOG_FILE"
systemctl enable ssh | tee -a "$LOG_FILE"
systemctl start ssh | tee -a "$LOG_FILE"
echo "SSH enabled." | tee -a "$LOG_FILE"

# Step 4.5: Enable SPI via Armbian overlay
echo "Enabling SPI..." | tee -a "$LOG_FILE"
CONFIG_FILE="/boot/armbianEnv.txt"
if ! grep -q "overlays=.*spi" "$CONFIG_FILE"; then
    if grep -q "^overlays=" "$CONFIG_FILE"; then
        sed -i 's/^overlays=\(.*\)/overlays=\1 spi-spidev/' "$CONFIG_FILE" || true
    else
        echo "overlays=spi-spidev" | tee -a "$CONFIG_FILE"
    fi
fi
echo "SPI enabled." | tee -a "$LOG_FILE"

# Step 5: Configure display rotation (using xrandr, as Armbian lacks config.txt)
echo "Configuring display rotation for 90° left (Waveshare 11.9inch HDMI LCD)..." | tee -a "$LOG_FILE"
# Note: HDMI timings for Waveshare may need manual adjustment; using xrandr for rotation
# Create Xorg config for display setup
XORG_CONF="/etc/X11/xorg.conf.d/20-waveshare.conf"
mkdir -p /etc/X11/xorg.conf.d | tee -a "$LOG_FILE"
cat << EOF > "$XORG_CONF"
Section "Monitor"
    Identifier "HDMI-1"
    Option "Rotate" "left"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "Card0"
    Monitor "HDMI-1"
    DefaultDepth 24
    SubSection "Display"
        Modes "320x1480"
    EndSubSection
EndSection
EOF
cat "$XORG_CONF" | tee -a "$LOG_FILE"
echo "Display rotation configured (check resolution/timings if display issues occur)." | tee -a "$LOG_FILE"

# Step 5.5: Configure clean boot splash (quiet mode)
echo "Configuring clean boot splash..." | tee -a "$LOG_FILE"
CMDLINE_FILE="/boot/armbianEnv.txt"
if ! grep -q "extraargs=.*quiet" "$CMDLINE_FILE"; then
    if grep -q "^extraargs=" "$CMDLINE_FILE"; then
        sed -i 's/^extraargs=\(.*\)/extraargs=\1 quiet splash plymouth.ignore-serial-consoles/' "$CMDLINE_FILE" || true
    else
        echo "extraargs=quiet splash plymouth.ignore-serial-consoles" | tee -a "$CMDLINE_FILE"
    fi
fi
cat "$CMDLINE_FILE" | tee -a "$LOG_FILE"
echo "Clean boot splash configured." | tee -a "$LOG_FILE"

# Step 5.6: Configure touch rotation (for Waveshare touchscreen)
echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 1 0 -1 0 1"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
echo "Touch rotation configured (verify touchscreen ID if not working)." | tee -a "$LOG_FILE"

# Step 6: Clone GitHub repository to Desktop
echo "Cloning GitHub repository to Desktop..." | tee -a "$LOG_FILE"
REPO_URL="https://github.com/hwpaige/spacex-dashboard"
REPO_DIR="$HOME_DIR/Desktop/project"
if [ -d "$REPO_DIR" ]; then
    rm -rf "$REPO_DIR" | tee -a "$LOG_FILE"
fi
sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$REPO_DIR" | tee -a "$LOG_FILE"
if [ ! -d "$REPO_DIR" ]; then
    echo "Error: Failed to clone repository to $REPO_DIR" | tee -a "$LOG_FILE"
    exit 1
fi
echo "Repository cloned to $REPO_DIR." | tee -a "$LOG_FILE"

# Step 6.5: Apply custom SpaceX boot logo after cloning
echo "Applying custom SpaceX boot logo..." | tee -a "$LOG_FILE"
LOGO_SRC="$HOME_DIR/Desktop/project/spacex_logo.png"
THEME_DIR="/usr/share/plymouth/themes/armbian"
LOGO_DEST="$THEME_DIR/armbian_logo.png"
mkdir -p "$THEME_DIR" | tee -a "$LOG_FILE"
if [ -f "$LOGO_SRC" ]; then
    cp "$LOGO_SRC" "$LOGO_DEST" | tee -a "$LOG_FILE"
    # Set armbian theme as default (Armbian uses its own theme)
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_DIR/armbian.plymouth" 150 | tee -a "$LOG_FILE"
    update-alternatives --set default.plymouth "$THEME_DIR/armbian.plymouth" | tee -a "$LOG_FILE"
    update-initramfs -u | tee -a "$LOG_FILE"
    echo "Custom SpaceX boot logo applied using armbian theme." | tee -a "$LOG_FILE"
else
    echo "Warning: spacex_logo.png not found in project folder. Skipping custom logo." | tee -a "$LOG_FILE"
fi

# Step 7: Create virtual environment with Python 3, enable system site-packages for PyQt5
echo "Creating virtual environment and installing dependencies..." | tee -a "$LOG_FILE"
VENV_DIR="$REPO_DIR/venv"
if sudo -u "$USER" python3 -m venv --system-site-packages "$VENV_DIR" | tee -a "$LOG_FILE"; then
    sudo -u "$USER" "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel | tee -a "$LOG_FILE"
    if [ -f "$REPO_DIR/requirements.txt" ]; then
        sudo -u "$USER" "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt" | tee -a "$LOG_FILE"
    else
        echo "Error: requirements.txt not found in $REPO_DIR" | tee -a "$LOG_FILE"
        exit 1
    fi
else
    echo "Error: Failed to create virtual environment in $VENV_DIR" | tee -a "$LOG_FILE"
    exit 1
fi
echo "Virtual environment created and dependencies installed." | tee -a "$LOG_FILE"

# Step 8: Configure desktop auto-login and kiosk mode with LightDM
echo "Configuring desktop auto-login and kiosk mode..." | tee -a "$LOG_FILE"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
cat << EOF > "$LIGHTDM_CONF"
[Seat:*]
autologin-user=$USER
autologin-session=openbox
xserver-command=X -nocursor
EOF
cat "$LIGHTDM_CONF" | tee -a "$LOG_FILE"
usermod -a -G nopasswdlogin "$USER" | tee -a "$LOG_FILE"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target | tee -a "$LOG_FILE"
echo "Desktop auto-login and kiosk mode configured." | tee -a "$LOG_FILE"

# Step 9: Configure Wi-Fi if not set (using armbian-config for reliability)
echo "Configuring Wi-Fi if not set..." | tee -a "$LOG_FILE"
if ! ip addr show wlan0 | grep -q "inet "; then
    echo "No WiFi connection detected. Launching armbian-config for WiFi setup..." | tee -a "$LOG_FILE"
    armbian-config
    # Verify connection
    if ip addr show wlan0 | grep -q "inet "; then
        echo "WiFi configured via armbian-config." | tee -a "$LOG_FILE"
    else
        echo "Warning: WiFi setup may have failed. Please check armbian-config or configure manually." | tee -a "$LOG_FILE"
    fi
else
    echo "WiFi already configured." | tee -a "$LOG_FILE"
fi

# Step 10: Configure PyQt app to launch via Openbox autostart for kiosk mode
echo "Configuring PyQt kiosk mode via Openbox autostart..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
# Create wrapper script
WRAPPER_SCRIPT="$REPO_DIR/launch_app.sh"
cat << EOF > "$WRAPPER_SCRIPT"
#!/bin/bash
APP_LOG="$HOME_DIR/app_launch.log"
echo "Wrapper started at $(date)" > "\$APP_LOG"
env >> "\$APP_LOG"
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt5/plugins/platforms
export QT_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt5/plugins
"$VENV_DIR/bin/python" "$REPO_DIR/app.py" >> "\$APP_LOG" 2>&1 || {
    echo "App failed with exit code $?" >> "\$APP_LOG"
    exit 1
}
EOF
chmod +x "$WRAPPER_SCRIPT"
chown "$USER:$USER" "$WRAPPER_SCRIPT"
# Autostart config
sudo -u "$USER" bash -c "cat << EOF > "$AUTOSTART_FILE"
touch $HOME_DIR/autostart_test.txt
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &
xrandr --output HDMI-1 --rotate left
$WRAPPER_SCRIPT
EOF"
cat "$AUTOSTART_FILE" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$OPENBOX_DIR" | tee -a "$LOG_FILE"
echo "PyQt app configured to start in kiosk mode." | tee -a "$LOG_FILE"

# Step 11: Finalize and reboot
echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot
