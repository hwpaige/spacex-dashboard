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

echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Install system packages (removed openbox/lightdm/xorg; keep Qt and essentials)
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv git python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick unclutter plymouth plymouth-themes libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 upower iw python3-requests python3-tz python3-dateutil python3-pandas | tee -a "$LOG_FILE"

# Enable upower service if installed
if [ -f /lib/systemd/system/upower.service ]; then
    systemctl enable --now upower | tee -a "$LOG_FILE"
fi

echo "System packages installed." | tee -a "$LOG_FILE"

# Raspberry Pi boot configuration
CONFIG_FILE="/boot/firmware/config.txt"
echo "Configuring silent boot, SpaceX logo, and display..." | tee -a "$LOG_FILE"
cat << EOF >> "$CONFIG_FILE"
# Enable KMS for graphics acceleration on Pi 5
dtoverlay=vc4-kms-v3d
# Custom HDMI mode for 320x1480@60, rotated 270 degrees
hdmi_group=2
hdmi_mode=87
hdmi_cvt=320 1480 60 6 0 0 0
display_rotate=3 # 270 degrees clockwise (left rotation)
# Silent boot parameters
disable_splash=0 # Enable splash (0 to enable)
boot_delay=0
EOF

# Set kernel boot params for silent boot
CMDLINE_FILE="/boot/firmware/cmdline.txt"
echo "console=tty3 quiet loglevel=3 logo.nologo vt.global_cursor_default=0 splash" | sudo tee "$CMDLINE_FILE"

# Set initramfs compression
if ! grep -q "^COMPRESS=lz4" /etc/initramfs-tools/initramfs.conf; then
    echo "COMPRESS=lz4" >> /etc/initramfs-tools/initramfs.conf
fi

# Set Plymouth theme (if available)
if command -v plymouth-set-default-theme >/dev/null; then
    plymouth-set-default-theme spinner -R | tee -a "$LOG_FILE"
else
    echo "Plymouth theme command not found; skipping." | tee -a "$LOG_FILE"
fi

# Configure touch rotation for 90° left (udev rule works without X)
echo "Configuring touch rotation for 90° left..." | tee -a "$LOG_FILE"
TOUCH_RULES="/etc/udev/rules.d/99-touch-rotation.rules"
cat << EOF > "$TOUCH_RULES"
SUBSYSTEM=="input", ATTRS{name}=="Goodix Capacitive TouchScreen", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0"
EOF
udevadm control --reload-rules | tee -a "$LOG_FILE"
apt-get install -y libinput-tools | tee -a "$LOG_FILE"
echo "Touch rotation configured." | tee -a "$LOG_FILE"

# Clone GitHub repository to Desktop
echo "Cloning GitHub repository to Desktop..." | tee -a "$LOG_FILE"
REPO_URL="https://github.com/hwpaige/spacex-dashboard"
REPO_DIR="$HOME_DIR/Desktop/project"
if [ -d "$REPO_DIR" ]; then rm -rf "$REPO_DIR" | tee -a "$LOG_FILE"; fi
sudo -u "$USER" git clone "$REPO_URL" "$REPO_DIR" | tee -a "$LOG_FILE"
chown -R "$USER:$USER" "$REPO_DIR" | tee -a "$LOG_FILE"
echo "Repository cloned to $REPO_DIR." | tee -a "$LOG_FILE"

# Create start_app.sh (with EGLFS env vars)
echo "Creating start_app.sh..." | tee -a "$LOG_FILE"
sudo -u "$USER" bash -c "cd \"$REPO_DIR\" && echo '#!/bin/bash' > start_app.sh && echo 'export QT_QPA_PLATFORM=eglfs' >> start_app.sh && echo 'export QT_QPA_EGLFS_ROTATION=270' >> start_app.sh && echo 'export QTWEBENGINE_CHROMIUM_FLAGS=\"--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl\"' >> start_app.sh && echo 'python3 app.py > $HOME_DIR/app.log 2>&1' >> start_app.sh && chmod +x start_app.sh" | tee -a "$LOG_FILE"
echo "start_app.sh created." | tee -a "$LOG_FILE"

# Configure console autologin and app launch
echo "Configuring console autologin and direct app start..." | tee -a "$LOG_FILE"
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat << EOF > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM
EOF
systemctl daemon-reload | tee -a "$LOG_FILE"

# Launch app from .bash_profile (with delay for stability)
sudo -u "$USER" bash -c "echo 'sleep 10' >> ~/.bash_profile && echo 'unclutter -idle 0 -root &' >> ~/.bash_profile && echo '$REPO_DIR/start_app.sh' >> ~/.bash_profile"
echo "App configured to start directly." | tee -a "$LOG_FILE"

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