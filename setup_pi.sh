#!/bin/bash

# Raspberry Pi 4 setup script for Ubuntu Server (64-bit, e.g., 24.04 LTS)
# Configures Waveshare 11.9inch HDMI LCD with screen rotation, clones GitHub repo, sets up venv with Python 3.11, enables SSH and SPI,
# installs minimal GUI (Xorg, Openbox, LightDM), configures auto-login and kiosk mode, and launches PyQt-embedded Dash app on boot
# Run with: sudo bash setup_ubuntu.sh (from /home/harrison/Desktop or any directory)
# Requires internet access, 5V 3A power supply, and 16GB+ SD card (Samsung EVO Plus recommended)
# Displays command output in terminal and logs to /home/harrison/setup_ubuntu.log
# Assumes user 'harrison' exists; creates if not. For Wi-Fi, prompts if not configured.

set -e

# Log file for debugging in the user's home directory
USER="harrison"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"
echo "Starting Raspberry Pi 4 setup on Ubuntu Server at $(date)" | tee -a "$LOG_FILE"

# Step 0: Create user if not exists (non-interactive, no password for auto-login)
if ! id "$USER" &>/dev/null; then
    echo "Creating user $USER..." | tee -a "$LOG_FILE"
    adduser --disabled-password --gecos "" "$USER" | tee -a "$LOG_FILE"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers.d/"$USER"
fi

# Step 1: Configure swap (512MB) for memory-intensive tasks
echo "Configuring 512MB swap file..." | tee -a "$LOG_FILE"
fallocate -l 512M /swapfile | tee -a "$LOG_FILE"
chmod 600 /swapfile | tee -a "$LOG_FILE"
mkswap /swapfile | tee -a "$LOG_FILE"
swapon /swapfile | tee -a "$LOG_FILE"
echo "/swapfile none swap sw 0 0" | tee -a /etc/fstab
echo "Swap configured." | tee -a "$LOG_FILE"

# Step 2: Update and upgrade system
echo "Updating and upgrading Ubuntu Server..." | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Step 3: Install required system packages (including PyQt5, XCB dependencies, minimal GUI, and Plymouth)
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pyqt5 python3-pyqt5.qtwebengine python3-pip python3-venv git xorg openbox lightdm lightdm-gtk-greeter x11-xserver-utils curl libxcb1 libxcb-xinerama0 libxcb-cursor0 libxcb-xinput0 libxcb-keysyms1 libxcb-shape0 libxcb-xfixes0 libxkbcommon-x11-0 libxcb-render0 libxcb-render-util0 libxcb-randr0 libxcb-sync1 libxcb-xkb1 libxcb-icccm4 libxkbcommon0 libqt5gui5 libqt5dbus5 libqt5core5a libqt5network5 libqt5widgets5 unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics | tee -a "$LOG_FILE"
apt-get reinstall -y python3-pyqt5 python3-pyqt5.qtwebengine plymouth plymouth-themes | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

# Step 4: Enable SSH (if not already installed)
echo "Enabling SSH..." | tee -a "$LOG_FILE"
apt-get install -y openssh-server | tee -a "$LOG_FILE"
systemctl enable ssh | tee -a "$LOG_FILE"
systemctl start ssh | tee -a "$LOG_FILE"
echo "SSH enabled." | tee -a "$LOG_FILE"

# Step 4.5: Enable SPI
echo "Enabling SPI..." | tee -a "$LOG_FILE"
CONFIG_FILE="/boot/firmware/config.txt"
echo "dtparam=spi=on" | tee -a "$CONFIG_FILE"
echo "SPI enabled." | tee -a "$LOG_FILE"

# Step 5: Configure Waveshare 11.9inch HDMI LCD in /boot/firmware/config.txt with rotation
echo "Configuring Waveshare 11.9inch HDMI LCD settings with rotation..." | tee -a "$LOG_FILE"
cp "$CONFIG_FILE" "${CONFIG_FILE}.backup" | tee -a "$LOG_FILE"
cat << EOF >> "$CONFIG_FILE"
# Waveshare 11.9inch HDMI LCD configuration
max_framebuffer_height=1480
hdmi_group=2
hdmi_mode=87
hdmi_timings=320 0 80 16 32 1480 0 16 4 12 0 0 0 60 0 42000000 3
hdmi_force_hotplug=1
disable_overscan=1
disable_splash=1
display_rotate=3
EOF
# Add rotation to cmdline.txt (rotate=270 for 90° left, counterclockwise)
CMDLINE_FILE="/boot/firmware/cmdline.txt"
sed -i 's/video=HDMI[^ ]*//' "$CMDLINE_FILE" # Remove any existing video= param
sed -i 's/$/ video=HDMI-1:320x1480@60,rotate=270/' "$CMDLINE_FILE" || true
cat "$CMDLINE_FILE" | tee -a "$LOG_FILE"
echo "Waveshare monitor settings and rotation applied." | tee -a "$LOG_FILE"

# Step 5.5: Configure clean boot splash (quiet mode)
echo "Configuring clean boot splash..." | tee -a "$LOG_FILE"
sed -i 's/console=tty1/quiet splash plymouth.ignore-serial-consoles/' "$CMDLINE_FILE" || true
cat "$CMDLINE_FILE" | tee -a "$LOG_FILE"
echo "Clean boot splash configured." | tee -a "$LOG_FILE"

# Step 5.6: Configure touch rotation
echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 1 0 -1 0 1"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
echo "Touch rotation configured." | tee -a "$LOG_FILE"

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
THEME_DIR="/usr/share/plymouth/themes/ubuntu-logo"
LOGO_DEST="$THEME_DIR/ubuntu_logo.png"
mkdir -p "$THEME_DIR" | tee -a "$LOG_FILE"  # Usually exists, but ensure
if [ -f "$LOGO_SRC" ]; then
    cp "$LOGO_SRC" "$LOGO_DEST" | tee -a "$LOG_FILE"
    # Set ubuntu-logo as default theme via update-alternatives (Ubuntu method)
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_DIR/ubuntu_logo.plymouth" 150 | tee -a "$LOG_FILE"
    update-alternatives --set default.plymouth "$THEME_DIR/ubuntu_logo.plymouth" | tee -a "$LOG_FILE"
    update-initramfs -u | tee -a "$LOG_FILE"
    echo "Custom SpaceX boot logo applied using ubuntu-logo theme." | tee -a "$LOG_FILE"
else
    echo "Warning: spacex_logo.png not found in project folder. Skipping custom logo." | tee -a "$LOG_FILE"
fi

# Step 7: Create virtual environment with Python 3.11, enable system site-packages for PyQt5, and install dependencies
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

# Step 9: Configure Wi-Fi if not set (using netplan)
echo "Configuring Wi-Fi if not set..." | tee -a "$LOG_FILE"
NETPLAN_FILE="/etc/netplan/99-wifi.yaml"
if [ ! -f "$NETPLAN_FILE" ]; then
    read -p "Enter Wi-Fi SSID: " WIFI_SSID
    read -sp "Enter Wi-Fi password: " WIFI_PASS
    echo
    cat << EOF > "$NETPLAN_FILE"
network:
  version: 2
  wifis:
    wlan0:
      optional: true
      access-points:
        "$WIFI_SSID":
          password: "$WIFI_PASS"
      dhcp4: true
EOF
    chmod 600 "$NETPLAN_FILE"
    cat "$NETPLAN_FILE" | tee -a "$LOG_FILE"
    netplan apply | tee -a "$LOG_FILE"
    echo "Wi-Fi configured in $NETPLAN_FILE." | tee -a "$LOG_FILE"
fi
echo "Wi-Fi configured." | tee -a "$LOG_FILE"

# Step 10: Configure PyQt app to launch via Openbox autostart for kiosk mode (with fallback xrandr rotation)
echo "Configuring PyQt kiosk mode via Openbox autostart..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
# Create simplified wrapper script
WRAPPER_SCRIPT="$REPO_DIR/launch_app.sh"
cat << EOF > "$WRAPPER_SCRIPT"
#!/bin/bash
APP_LOG="$HOME_DIR/app_launch.log"
echo "Wrapper started at $(date)" > "\$APP_LOG"
env >> "\$APP_LOG"  # Dump environment for debugging
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
# Autostart config with fallback xrandr rotation
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