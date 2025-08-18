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

echo "Updating and upgrading Ubuntu Server (kernel held)..." | tee -a "$LOG_FILE"
apt-mark hold linux-image-current-sunxi64 linux-dtb-current-sunxi64 wpasupplicant | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
#apt-get autoremove -y | tee -a "$LOG_FILE"
#apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv git xorg xserver-xorg-core openbox lightdm lightdm-gtk-greeter x11-xserver-utils xauth python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 accountsservice xinput python3-requests python3-tz python3-dateutil python3-pandas upower wireless-tools | tee -a "$LOG_FILE"
systemctl enable --now upower | tee -a "$LOG_FILE"
echo "System packages installed." | tee -a "$LOG_FILE"

echo "Ensuring xauth is installed..." | tee -a "$LOG_FILE"
apt-get install -y xauth | tee -a "$LOG_FILE"
echo "xauth ensured." | tee -a "$LOG_FILE"

CONFIG_FILE="/boot/armbianEnv.txt"
echo "Configuring silent boot, SpaceX logo, and display..." | tee -a "$LOG_FILE"

# Update extraargs with new parameters
if grep -q "^extraargs=" "$CONFIG_FILE"; then
    sed -i 's/^extraargs=.*/extraargs=vt.global_cursor_default=0 quiet splash plymouth.ignore-serial-consoles video=HDMI-A-1:320x1480@60,rotate=270/' "$CONFIG_FILE" || true
else
    echo "extraargs=vt.global_cursor_default=0 quiet splash plymouth.ignore-serial-consoles video=HDMI-A-1:320x1480@60,rotate=270" | tee -a "$CONFIG_FILE"
fi

# Add or update other boot parameters
sed -i '/^verbosity=/d' "$CONFIG_FILE"
echo "verbosity=0" >> "$CONFIG_FILE"
sed -i '/^console=/d' "$CONFIG_FILE"
echo "console=custom" >> "$CONFIG_FILE"
sed -i '/^consoleargs=/d' "$CONFIG_FILE"
echo "consoleargs=console=ttyS0,115200 console=tty7" >> "$CONFIG_FILE"
sed -i '/^stdout=/d' "$CONFIG_FILE"
echo "stdout=serial" >> "$CONFIG_FILE"

# Set initramfs compression for faster rebuilds
if ! grep -q "^COMPRESS=lz4" /etc/initramfs-tools/initramfs.conf; then
    echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
fi

# Set Plymouth theme to spinner and rebuild initramfs
plymouth-set-default-theme spinner -R | tee -a "$LOG_FILE"

XORG_CONF="/etc/X11/xorg.conf.d/20-waveshare.conf"
mkdir -p /etc/X11/xorg.conf.d | tee -a "$LOG_FILE"
cat << EOF > "$XORG_CONF"
Section "Device"
    Identifier "Card0"
    Driver "modesetting"
EndSection

Section "Monitor"
    Identifier "HDMI-1"
    Modeline "320x1480_60.00" 42.00 320 336 368 448 1480 1484 1492 1512 -hsync +vsync
    Option "PreferredMode" "320x1480_60.00"
    Option "Rotate" "left"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device "Card0"
    Monitor "HDMI-1"
    DefaultDepth 24
    SubSection "Display"
        Modes "320x1480_60.00"
    EndSubSection
EndSection
EOF
cat "$XORG_CONF" | tee -a "$LOG_FILE"
echo "Silent boot, logo, and display configured." | tee -a "$LOG_FILE"

echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
SUBSYSTEM=="input", ATTRS{name}=="Goodix Capacitive TouchScreen", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0"
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
sudo -u "$USER" bash -c "cd \"$REPO_DIR\" && echo '#!/bin/bash' > start_app.sh && echo 'export QT_QPA_PLATFORM=xcb' >> start_app.sh && echo 'dbus-run-session -- python3 app.py > $HOME_DIR/app.log 2>&1' >> start_app.sh && chmod +x start_app.sh" | tee -a "$LOG_FILE"
echo "start_app.sh created." | tee -a "$LOG_FILE"

echo "Configuring desktop auto-login, kiosk mode, and Xauth..." | tee -a "$LOG_FILE"
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
mkdir -p /etc/lightdm
cat << EOF > "$LIGHTDM_CONF"
[Seat:*]
autologin-user=$USER
autologin-session=openbox-session
xserver-command=/usr/bin/Xorg
greeter-session=lightdm-gtk-greeter
EOF
cat "$LIGHTDM_CONF" | tee -a "$LOG_FILE"
usermod -a -G nopasswdlogin "$USER" | tee -a "$LOG_FILE"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target | tee -a "$LOG_FILE"
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

echo "Configuring app to launch..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
sudo -u "$USER" bash -c "cat << EOF > \"$AUTOSTART_FILE\"
touch $HOME_DIR/autostart_test.txt
for i in {1..120}; do
    export DISPLAY=:0
    if xset -q >/dev/null 2>&1; then
        xset s off
        xset -dpms
        xset dpms 0 0 0
        xset s noblank
        unclutter -idle 0 -root &
        xauth generate :0 . trusted
        xauth add \$HOSTNAME/unix:0 . \$(mcookie)
        break
    fi
    sleep 1
done
$REPO_DIR/start_app.sh > $HOME_DIR/autostart_app.log 2>&1 &
EOF"
cat "$AUTOSTART_FILE" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$OPENBOX_DIR" | tee -a "$LOG_FILE"
echo "App configured to start." | tee -a "$LOG_FILE"

echo "Optimizing performance..." | tee -a "$LOG_FILE"
echo "Performance optimizations applied." | tee -a "$LOG_FILE"
echo "options brcmfmac p2p=0" | tee /etc/modprobe.d/brcmfmac.conf | tee -a "$LOG_FILE"
# Disable WiFi power saving to prevent drops after GUI start
iw dev wlan0 set power_save off | tee -a "$LOG_FILE" || true  # '|| true' in case interface name differs or not up yet
modprobe -r brcmfmac | tee -a "$LOG_FILE"
modprobe brcmfmac | tee -a "$LOG_FILE"
echo "Configuring persistent WiFi power save disable..." | tee -a "$LOG_FILE"
cat << EOF > /etc/rc.local
#!/bin/sh -e
sleep 10  # Wait for network to initialize
iw dev wlan0 set power_save off
exit 0
EOF
chmod +x /etc/rc.local
systemctl enable rc-local | tee -a "$LOG_FILE" || true
echo "WiFi power save disable configured." | tee -a "$LOG_FILE"
echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot