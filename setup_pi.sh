#!/bin/bash

set -e

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
fi

# Set blank password for autologin
sudo passwd -d "$USER" | tee -a "$LOG_FILE"

# Update and upgrade system
echo "Updating and upgrading Ubuntu Server..." | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
#apt-get autoremove -y | tee -a "$LOG_FILE"
#apt-get autoclean -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Install system packages (ensure iw is included; no wireless-tools or raspberrypi-sys-mods)
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv git xorg xserver-xorg-core openbox lightdm lightdm-gtk-greeter x11-xserver-utils xauth python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick unclutter plymouth plymouth-themes xserver-xorg-input-libinput xserver-xorg-input-synaptics libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 accountsservice xinput python3-requests python3-tz python3-dateutil python3-pandas upower iw | tee -a "$LOG_FILE"
# Enable upower service if installed and exists
if [ -f /lib/systemd/system/upower.service ]; then
    systemctl enable --now upower | tee -a "$LOG_FILE"
fi
echo "System packages installed." | tee -a "$LOG_FILE"

# Ensure xauth is installed
echo "Ensuring xauth is installed..." | tee -a "$LOG_FILE"
apt-get install -y xauth | tee -a "$LOG_FILE"
echo "xauth ensured." | tee -a "$LOG_FILE"

# Raspberry Pi boot configuration (use /boot/firmware/config.txt)
CONFIG_FILE="/boot/firmware/config.txt"
echo "Configuring silent boot, SpaceX logo, and display..." | tee -a "$LOG_FILE"

# Add or update config.txt parameters for Raspberry Pi 5
cat << EOF >> "$CONFIG_FILE"
# Enable KMS for graphics acceleration on Pi 5
dtoverlay=vc4-kms-v3d

# Custom HDMI mode for 320x1480@60, rotated 270 degrees
hdmi_group=2
hdmi_mode=87
hdmi_cvt=320 1480 60 6 0 0 0
display_rotate=3  # 270 degrees clockwise (left rotation)

# Silent boot parameters
disable_splash=0  # Enable splash (0 to enable)
boot_delay=0
EOF

# Set kernel boot params for silent boot in cmdline.txt
CMDLINE_FILE="/boot/firmware/cmdline.txt"
echo "console=tty3 quiet loglevel=3 logo.nologo vt.global_cursor_default=0 splash" | sudo tee -a "$CMDLINE_FILE"

# Set initramfs compression for faster rebuilds
if ! grep -q "^COMPRESS=lz4" /etc/initramfs-tools/initramfs.conf; then
    echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
fi

# Set Plymouth theme to spinner and rebuild initramfs (ensure command exists or skip)
if command -v plymouth-set-default-theme >/dev/null; then
    plymouth-set-default-theme spinner -R | tee -a "$LOG_FILE"
else
    echo "Plymouth theme command not found; skipping theme set." | tee -a "$LOG_FILE"
fi

# Xorg configuration for Waveshare display
XORG_CONF="/etc/X11/xorg.conf.d/20-waveshare.conf"
mkdir -p /etc/X11/xorg.conf.d | tee -a "$LOG_FILE"
cat << EOF > "$XORG_CONF"
Section "Device"
    Identifier "Card0"
    Driver "modesetting"
    Option "kmsdev" "/dev/dri/card1"  # Use card1 for Raspberry Pi 5 V3D
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

# Configure touch rotation for 90° left
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

# Clone GitHub repository to Desktop
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

# Create start_app.sh
echo "Creating start_app.sh on host..." | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cd \"$REPO_DIR\" && echo '#!/bin/bash' > start_app.sh && echo 'export QT_QPA_PLATFORM=xcb' >> start_app.sh && echo 'dbus-run-session -- python3 app.py > $HOME_DIR/app.log 2>&1' >> start_app.sh && chmod +x start_app.sh" | tee -a "$LOG_FILE"
echo "start_app.sh created." | tee -a "$LOG_FILE"

# Configure desktop auto-login, kiosk mode, and Xauth
echo "Configuring desktop auto-login, kiosk mode, and Xauth..." | tee -a "$LOG_FILE"
# Create nopasswdlogin group if it doesn't exist
if ! getent group nopasswdlogin > /dev/null; then
    groupadd nopasswdlogin | tee -a "$LOG_FILE"
fi
usermod -a -G nopasswdlogin "$USER" | tee -a "$LOG_FILE"

LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
mkdir -p /etc/lightdm
cat << EOF > "$LIGHTDM_CONF"
[Seat:*]
autologin-user=$USER
autologin-session=openbox-session
autologin-user-timeout=0
allow-guest=false
greeter-hide-users=true
xserver-command=/usr/bin/Xorg
greeter-session=lightdm-gtk-greeter
EOF
cat "$LIGHTDM_CONF" | tee -a "$LOG_FILE"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target | tee -a "$LOG_FILE"
echo "Desktop auto-login, kiosk mode, and Xauth configured." | tee -a "$LOG_FILE"

# Set user's session file (~/.dmrc)
sudo -u "$USER" bash -c "echo '[Desktop]' > ~/.dmrc && echo 'Session=openbox-session' >> ~/.dmrc && chmod 600 ~/.dmrc"

# Set default boot target to graphical
sudo systemctl set-default graphical.target | tee -a "$LOG_FILE"

# Configure LightDM startup delay (increased to 10s)
echo "Configuring LightDM startup delay..." | tee -a "$LOG_FILE"
mkdir -p /etc/systemd/system/lightdm.service.d
cat << EOF > /etc/systemd/system/lightdm.service.d/delay.conf
[Service]
ExecStartPre=/bin/sleep 10
EOF
systemctl daemon-reload | tee -a "$LOG_FILE"
echo "LightDM startup delay configured." | tee -a "$LOG_FILE"

# Reconfigure LightDM to apply changes
sudo dpkg-reconfigure lightdm | tee -a "$LOG_FILE"

# Configure Openbox session file
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

# Ensure X server symlink
echo "Ensuring X server symlink..." | tee -a "$LOG_FILE"
ln -s -f /usr/bin/Xorg /usr/bin/X
echo "X server symlink ensured." | tee -a "$LOG_FILE"

# Configure app to launch (increased loop to 180 for more delay)
echo "Configuring app to launch..." | tee -a "$LOG_FILE"
OPENBOX_DIR="$HOME_DIR/.config/openbox"
sudo -u "$USER" mkdir -p "$OPENBOX_DIR" | tee -a "$LOG_FILE"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"
sudo -u "$USER" rm -f "$AUTOSTART_FILE"
sudo -u "$USER" bash -c "cat << EOF > \"$AUTOSTART_FILE\"
touch $HOME_DIR/autostart_test.txt
for i in {1..180}; do
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

# Optimize performance
echo "Optimizing performance..." | tee -a "$LOG_FILE"
echo "Performance optimizations applied." | tee -a "$LOG_FILE"

# WiFi configuration
echo "options brcmfmac p2p=0" | tee /etc/modprobe.d/brcmfmac.conf | tee -a "$LOG_FILE"
# Disable WiFi power saving (non-fatal if interface not ready)
iw dev wlan0 set power_save off || true | tee -a "$LOG_FILE"
modprobe -r brcmfmac || true | tee -a "$LOG_FILE"
modprobe brcmfmac | tee -a "$LOG_FILE"
echo "Configuring persistent WiFi power save disable..." | tee -a "$LOG_FILE"
cat << EOF > /etc/rc.local
#!/bin/sh -e
sleep 10  # Wait for network to initialize
iw dev wlan0 set power_save off || true
exit 0
EOF
chmod +x /etc/rc.local
# No 'systemctl enable rc-local' as it's not needed; rc.local runs if executable
echo "WiFi power save disable configured." | tee -a "$LOG_FILE"

echo "Setup complete. Rebooting in 10 seconds..." | tee -a "$LOG_FILE"
sleep 10
reboot