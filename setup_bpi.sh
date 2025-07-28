#!/bin/bash

set -e

USER="harrison"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_ubuntu.log"
echo "Starting Banana Pi M4 Zero setup on Armbian Ubuntu Server at $(date)" | tee -a "$LOG_FILE"

if ! id "$USER" &>/dev/null; then
    echo "Creating user $USER..." | tee -a "$LOG_FILE"
    adduser --disabled-password --gecos "" "$USER" | tee -a "$LOG_FILE"
    echo "$USER ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers.d/"$USER"
    chmod 0440 /etc/sudoers.d/"$USER"
fi

echo "Configuring 512MB swap file..." | tee -a "$LOG_FILE"
if [ ! -f /swapfile ]; then
    fallocate -l 512M /swapfile | tee -a "$LOG_FILE"
    chmod 600 /swapfile | tee -a "$LOG_FILE"
    mkswap /swapfile | tee -a "$LOG_FILE"
    swapon /swapfile | tee -a "$LOG_FILE"
    echo "/swapfile none swap sw 0 0" | tee -a /etc/fstab
fi
echo "Swap configured." | tee -a "$LOG_FILE"

echo "Updating and upgrading Ubuntu Server (kernel held)..." | tee -a "$LOG_FILE"
apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64 | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv python3.12-venv git xorg openbox lightdm lightdm-gtk-greeter x11-xserver-utils python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtchart python3-pyqt5.qtquick unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics linux-firmware libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 wpasupplicant | tee -a "$LOG_FILE"
apt-get reinstall -y plymouth plymouth-themes | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

echo "Installing Docker and Buildx..." | tee -a "$LOG_FILE"
apt-get install -y docker.io docker-buildx | tee -a "$LOG_FILE"
systemctl enable --now docker | tee -a "$LOG_FILE"
usermod -aG docker "$USER" | tee -a "$LOG_FILE"
docker buildx install | tee -a "$LOG_FILE"
docker buildx create --name mybuilder --use | tee -a "$LOG_FILE"
echo "Docker and Buildx installed." | tee -a "$LOG_FILE"

CONFIG_FILE="/boot/armbianEnv.txt"

echo "Configuring silent boot, SpaceX logo, and display..." | tee -a "$LOG_FILE"
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
    Option "AccelMethod" "none"
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
        Modes "1480x320"
    EndSubSection
EndSection
EOF
cat "$XORG_CONF" | tee -a "$LOG_FILE"
echo "Silent boot, logo, and display configured." | tee -a "$LOG_FILE"

echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 1 0 -1 0 1"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
echo "Touch rotation configured." | tee -a "$LOG_FILE"

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

echo "Creating start_app.sh on host..." | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cd \"$REPO_DIR\" && echo '#!/bin/bash' > start_app.sh && echo 'python3 app.py' >> start_app.sh && chmod +x start_app.sh" | tee -a "$LOG_FILE"
echo "start_app.sh created." | tee -a "$LOG_FILE"

echo "Configuring desktop auto-login, kiosk mode, and Xauth..." | tee -a "$LOG_FILE"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
mkdir -p /etc/lightdm
cat << EOF > "$LIGHTDM_CONF"
[Seat:*]
autologin-user=$USER
autologin-session=openbox
xserver-command=X -nocursor
EOF
cat "$LIGHTDM_CONF" | tee -a "$LOG_FILE"
usermod -a -G nopasswdlogin "$USER" | tee -a "$LOG_FILE"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "export DISPLAY=:0 && xauth generate :0 . trusted && xauth add \$HOSTNAME/unix:0 . \$(mcookie) && xhost +local:docker" | tee -a "$LOG_FILE"
echo "Desktop auto-login, kiosk mode, and Xauth configured." | tee -a "$LOG_FILE"

echo "Configuring Wi-Fi if not set..." | tee -a "$LOG_FILE"
if ! ip addr show wlan0 | grep -q "inet "; then
    echo "No WiFi connection detected. Launching armbian-config..." | tee -a "$LOG_FILE"
    armbian-config
    if ip addr show wlan0 | grep -q "inet "; then
        echo "WiFi configured via armbian-config." | tee -a "$LOG_FILE"
    else
        echo "Warning: WiFi setup failed. Falling back to manual config..." | tee -a "$LOG_FILE"
        read -p "Enter WiFi SSID: " SSID
        read -p "Enter WiFi password: " -s PASSWORD
        echo
        cat << EOF > /etc/wpa_supplicant.conf
network={
    ssid="$SSID"
    psk="$PASSWORD"
}
EOF
        wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf | tee -a "$LOG_FILE"
        dhclient wlan0 | tee -a "$LOG_FILE"
        if ip addr show wlan0 | grep -q "inet "; then
            echo "WiFi configured manually." | tee -a "$LOG_FILE"
        else
            echo "Error: WiFi setup failed. Check hardware." | tee -a "$LOG_FILE"
            exit 1
        fi
    fi
else
    echo "WiFi already configured." | tee -a "$LOG_FILE"
fi

echo "Configuring Docker container to launch..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
echo "Building Docker image with Buildx..." | tee -a "$LOG_FILE"
sudo -u "$USER" docker buildx build --platform linux/arm64 -t spacex-dashboard:latest "$REPO_DIR" | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cat << EOF > \"$AUTOSTART_FILE\"
touch $HOME_DIR/autostart_test.txt
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &
xrandr --output HDMI-1 --rotate left
for i in {1..60}; do
    export DISPLAY=:0
    if xset -q >/dev/null 2>&1; then
        xhost +local:docker
        break
    fi
    sleep 1
done
docker start spacex-dashboard-app || docker run -d --name spacex-dashboard-app --restart unless-stopped \\
  -e DISPLAY=:0 \\
  -v /tmp/.X11-unix:/tmp/.X11-unix \\
  -v $HOME_DIR/.Xauthority:/app/.Xauthority \\
  -e XAUTHORITY=/app/.Xauthority \\
  -v /dev/dri:/dev/dri \\
  -v /dev/fb0:/dev/fb0 \\
  --device /dev/input/event0 \\
  --network host \\
  --security-opt seccomp=unconfined \\
  --privileged \\
  -v $HOME_DIR/Desktop/project:/app \\
  spacex-dashboard:latest
EOF"
cat "$AUTOSTART_FILE" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$OPENBOX_DIR" | tee -a "$LOG_FILE"
echo "Docker container configured to start." | tee -a "$LOG_FILE"

echo "Optimizing performance..." | tee -a "$LOG_FILE"
systemctl disable bluetooth | tee -a "$LOG_FILE"
echo "Performance optimizations applied." | tee -a "$LOG_FILE"

echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot