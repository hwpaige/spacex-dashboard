#!/bin/bash

# Banana Pi M4 Zero setup script for Armbian Ubuntu Server (e.g., 24.04 or 25.04)
# Configures silent boot with SpaceX logo (Plymouth), SPI, WiFi, minimal GUI (Xorg, Openbox, LightDM), auto-login, and containerized PyQt5 SpaceX/F1 app
# Run with: sudo bash setup_ubuntu.sh (from /home/harrison/Desktop)
# Requires internet access, 5V 3A USB-C power supply, 16GB+ SD card
# Logs to /home/harrison/setup_ubuntu.log
# Assumes user 'harrison' exists; creates if not. Prompts for WiFi if not configured.
# Uses 800x600 for performance; adjust if needed for Waveshare 11.9inch HDMI LCD.

set -e

# Log file
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

# Step 2: Update and upgrade system, freeze kernel
echo "Updating and upgrading Ubuntu Server (kernel held)..." | tee -a "$LOG_FILE"
apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64 | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Step 3: Install system packages (PyQt5, PyQtChart, minimal GUI, Plymouth)
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv git xorg openbox lightdm lightdm-gtk-greeter x11-xserver-utils \
    python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtchart unclutter plymouth plymouth-themes \
    xserver-xorg-input-libinput xserver-xorg-input-synaptics linux-firmware libgl1-mesa-dri libgles2 \
    libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 | tee -a "$LOG_FILE"
apt-get reinstall -y plymouth plymouth-themes | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

# Step 3.5: Install Docker and Buildx
echo "Installing Docker and Buildx..." | tee -a "$LOG_FILE"
apt-get install -y docker.io docker-buildx-plugin | tee -a "$LOG_FILE"
systemctl enable --now docker | tee -a "$LOG_FILE"
usermod -aG docker "$USER" | tee -a "$LOG_FILE"
docker buildx install | tee -a "$LOG_FILE"
docker buildx create --use | tee -a "$LOG_FILE"
echo "Docker and Buildx installed." | tee -a "$LOG_FILE"

# Step 4: Enable SSH
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

# Step 5: Configure silent boot with SpaceX logo and display
echo "Configuring silent boot with SpaceX logo and display..." | tee -a "$LOG_FILE"
if ! grep -q "extraargs=.*quiet" "$CONFIG_FILE"; then
    if grep -q "^extraargs=" "$CONFIG_FILE"; then
        sed -i 's/^extraargs=\(.*\)/extraargs=\1 quiet splash loglevel=0 console=blank vt.global_cursor_default=0 plymouth.ignore-serial-consoles/' "$CONFIG_FILE" || true
    else
        echo "extraargs=quiet splash loglevel=0 console=blank vt.global_cursor_default=0 plymouth.ignore-serial-consoles" | tee -a "$CONFIG_FILE"
    fi
fi
PLYMOUTH_CONF="/etc/plymouth/plymouth.conf"
mkdir -p /etc/plymouth
cat << EOF > "$PLYMOUTH_CONF"
[Daemon]
Theme=armbian
ShowDelay=0
DeviceTimeout=5
EOF
update-initramfs -u | tee -a "$LOG_FILE"
XORG_CONF="/etc/X11/xorg.conf.d/20-waveshare.conf"
mkdir -p /etc/X11/xorg.conf.d | tee -a "$LOG_FILE"
cat << EOF > "$XORG_CONF"
Section "Device"
    Identifier "Card0"
    Driver "modesetting"
    Option "AccelMethod" "glamor"
EndSection
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
        Modes "800x600"
    EndSubSection
EndSection
EOF
cat "$XORG_CONF" | tee -a "$LOG_FILE"
echo "Silent boot and display configured." | tee -a "$LOG_FILE"

# Step 5.5: Configure touch rotation
echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 1 0 -1 0 1"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
echo "Touch rotation configured." | tee -a "$LOG_FILE"

# Step 6: Clone GitHub repository
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

# Step 6.5: Apply SpaceX boot logo
echo "Applying custom SpaceX boot logo..." | tee -a "$LOG_FILE"
LOGO_SRC="$HOME_DIR/Desktop/project/spacex_logo.png"
THEME_DIR="/usr/share/plymouth/themes/armbian"
LOGO_DEST="$THEME_DIR/armbian_logo.png"
mkdir -p "$THEME_DIR" | tee -a "$LOG_FILE"
if [ -f "$LOGO_SRC" ]; then
    cp "$LOGO_SRC" "$LOGO_DEST" | tee -a "$LOG_FILE"
    update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_DIR/armbian.plymouth" 150 | tee -a "$LOG_FILE"
    update-alternatives --set default.plymouth "$THEME_DIR/armbian.plymouth" | tee -a "$LOG_FILE"
    update-initramfs -u | tee -a "$LOG_FILE"
    echo "Custom SpaceX boot logo applied." | tee -a "$LOG_FILE"
else
    echo "Warning: spacex_logo.png not found. Skipping custom logo." | tee -a "$LOG_FILE"
fi

# Step 7: Create virtual environment and install dependencies
echo "Creating virtual environment and install dependencies..." | tee -a "$LOG_FILE"
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

# Step 9: Configure Wi-Fi if not set
echo "Configuring Wi-Fi if not set..." | tee -a "$LOG_FILE"
if ! ip addr show wlan0 | grep -q "inet "; then
    echo "No WiFi connection detected. Launching armbian-config for WiFi setup..." | tee -a "$LOG_FILE"
    armbian-config
    if ip addr show wlan0 | grep -q "inet "; then
        echo "WiFi configured via armbian-config." | tee -a "$LOG_FILE"
    else
        echo "Warning: WiFi setup may have failed. Please check armbian-config or configure manually." | tee -a "$LOG_FILE"
    fi
else
    echo "WiFi already configured." | tee -a "$LOG_FILE"
fi

# Step 10: Configure Docker container to launch (replaces direct app launch)
echo "Configuring Docker container to launch..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
# Build Docker image if not exists
if ! docker image inspect spacex-dashboard:latest &>/dev/null; then
    echo "Building Docker image with Buildx..." | tee -a "$LOG_FILE"
    sudo -u "$USER" docker buildx build --platform linux/arm64 -t spacex-dashboard:latest "$REPO_DIR" | tee -a "$LOG_FILE"
fi
sudo -u "$USER" bash -c "cat << EOF > \"$AUTOSTART_FILE\"
# Wait for X server to be ready
for i in {1..30}; do
    export DISPLAY=:0
    if xset -q >/dev/null 2>&1; then
        xhost +local:docker
        break
    fi
    sleep 1
done
touch $HOME_DIR/autostart_test.txt
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &
xrandr --output HDMI-1 --rotate left
docker start spacex-dashboard-app || docker run -d --name spacex-dashboard-app --restart unless-stopped \
  -e DISPLAY=:0 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /dev/dri:/dev/dri \
  -v /dev/fb0:/dev/fb0 \
  --device /dev/input/event0 \
  --network host \
  -v $HOME_DIR/Desktop/project:/home/harrison/Desktop/project \
  spacex-dashboard:latest
EOF"
cat "$AUTOSTART_FILE" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$OPENBOX_DIR" | tee -a "$LOG_FILE"
echo "Docker container configured to start." | tee -a "$LOG_FILE"

# Step 11: Optimize performance
echo "Optimizing performance..." | tee -a "$LOG_FILE"
systemctl disable bluetooth cups | tee -a "$LOG_FILE"
echo "Performance optimizations applied." | tee -a "$LOG_FILE"

# Step 12: Finalize and reboot
echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot