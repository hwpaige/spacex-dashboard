#!/bin/bash

set -e

USER="harrison"
HOME_DIR="/home/$USER"
LOG_FILE="$HOME_DIR/setup_rpi.log"
echo "Starting Raspberry Pi 4 setup on Raspberry Pi OS at $(date)" | tee -a "$LOG_FILE"

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

echo "Updating and upgrading Raspberry Pi OS..." | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
apt-get autoremove -y | tee -a "$LOG_FILE"
apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv python3.12-venv git xorg xserver-xorg-core openbox lightdm lightdm-gtk-greeter x11-xserver-utils xauth python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtchart python3-pyqt5.qtquick unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 accountsservice | tee -a "$LOG_FILE"
apt-get reinstall -y plymouth plymouth-themes | tee -a "$LOG_FILE"
apt-get install --reinstall -y xserver-xorg-core xorg | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

echo "Ensuring xauth is installed..." | tee -a "$LOG_FILE"
apt-get install -y xauth | tee -a "$LOG_FILE"
echo "xauth ensured." | tee -a "$LOG_FILE"

echo "Installing Docker and Buildx..." | tee -a "$LOG_FILE"
apt-get install -y docker.io docker-buildx | tee -a "$LOG_FILE"
systemctl enable --now docker | tee -a "$LOG_FILE"
usermod -aG docker "$USER" | tee -a "$LOG_FILE"
docker buildx install | tee -a "$LOG_FILE"
docker buildx create --name mybuilder --use | tee -a "$LOG_FILE"
echo "Docker and Buildx installed." | tee -a "$LOG_FILE"

CONFIG_FILE="/boot/config.txt"
CMDLINE_FILE="/boot/cmdline.txt"

echo "Configuring silent boot, SpaceX logo, and display..." | tee -a "$LOG_FILE"
if ! grep -q "quiet" "$CMDLINE_FILE"; then
    sed -i 's/$/ quiet splash loglevel=0 consoleblank=0 vt.global_cursor_default=0 plymouth.ignore-serial-consoles/' "$CMDLINE_FILE" || true
fi

if ! grep -q "display_rotate=3" "$CONFIG_FILE"; then
    echo "" >> "$CONFIG_FILE"
    echo "# Custom display settings for 1480x320 rotated left" >> "$CONFIG_FILE"
    echo "hdmi_force_hotplug=1" >> "$CONFIG_FILE"
    echo "hdmi_group=2" >> "$CONFIG_FILE"
    echo "hdmi_mode=87" >> "$CONFIG_FILE"
    echo "hdmi_cvt=1480 320 60 3 0 0 0" >> "$CONFIG_FILE"
    echo "display_rotate=3" >> "$CONFIG_FILE"
    echo "dtoverlay=vc4-kms-v3d" >> "$CONFIG_FILE"
fi

PLYMOUTH_CONF="/etc/plymouth/plymouthd.conf"
mkdir -p /etc/plymouth
cat << EOF > "$PLYMOUTH_CONF"
[Daemon]
Theme=spinner
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
echo "Verifying multi-touch support..." | tee -a "$LOG_FILE"
apt-get install -y libinput-tools | tee -a "$LOG_FILE"
libinput list-devices | tee -a "$LOG_FILE"
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
sudo -u "$USER" bash -c "cd \"$REPO_DIR\" && echo '#!/bin/bash' > start_app.sh && echo 'dbus-run-session -- python3 app.py' >> start_app.sh && chmod +x start_app.sh" | tee -a "$LOG_FILE"
echo "start_app.sh created." | tee -a "$LOG_FILE"

echo "Configuring desktop auto-login, kiosk mode, and Xauth..." | tee -a "$LOG_FILE"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
mkdir -p /etc/lightdm
cat << EOF > "$LIGHTDM_CONF"
[Seat:*]
autologin-user=$USER
autologin-session=openbox
xserver-command=/usr/bin/Xorg
greeter-session=lightdm-gtk-greeter
EOF
cat "$LIGHTDM_CONF" | tee -a "$LOG_FILE"
usermod -a -G nopasswdlogin "$USER" | tee -a "$LOG_FILE"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "export DISPLAY=:0 && xauth generate :0 . trusted && xauth add \$HOSTNAME/unix:0 . \$(mcookie) && xhost +local:docker" | tee -a "$LOG_FILE"
echo "Desktop auto-login, kiosk mode, and Xauth configured." | tee -a "$LOG_FILE"

echo "Configuring LightDM startup delay..." | tee -a "$LOG_FILE"
mkdir -p /etc/systemd/system/lightdm.service.d
cat << EOF > /etc/systemd/system/lightdm.service.d/delay.conf
[Service]
ExecStartPre=/bin/sleep 5
EOF
systemctl daemon-reload | tee -a "$LOG_FILE"
echo "LightDM startup delay configured." | tee -a "$LOG_FILE"

echo "Configuring Openbox session file..." | tee -a "$LOG_FILE"
mkdir -p /usr/share/xsessions
cat << EOF > /usr/share/xsessions/openbox.desktop
[Desktop Entry]
Name=Openbox
Comment=Log in using the Openbox window manager (without a session manager)
Exec=openbox-session
TryExec=openbox-session
Type=Application
EOF
chmod 644 /usr/share/xsessions/openbox.desktop
echo "Openbox session file configured." | tee -a "$LOG_FILE"

echo "Ensuring X server symlink..." | tee -a "$LOG_FILE"
ln -s -f /usr/bin/Xorg /usr/bin/X
echo "X server symlink ensured." | tee -a "$LOG_FILE"

echo "Configuring Docker container to launch..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
echo "Building Docker image with Buildx..." | tee -a "$LOG_FILE"
sudo -u "$USER" docker buildx build --platform linux/arm64 -t spacex-dashboard:latest "$REPO_DIR" | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cat << EOF > \"$AUTOSTART_FILE\"
touch $HOME_DIR/autostart_test.txt
for i in {1..60}; do
    export DISPLAY=:0
    if xset -q >/dev/null 2>&1; then
        xset s off
        xset -dpms
        xset dpms 0 0 0
        xset s noblank
        unclutter -idle 0 -root &
        xrandr --output HDMI-1 --rotate left
        xauth generate :0 . trusted
        xauth add \$HOSTNAME/unix:0 . \$(mcookie)
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
  -v /dev/vchiq:/dev/vchiq \\
  -v /dev/vcsm:/dev/vcsm \\
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