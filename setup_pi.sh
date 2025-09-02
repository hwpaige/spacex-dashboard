#!/bin/bash
set -e
set -o pipefail

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

# Create udev rule for DMA heap access to fix Qt WebEngine hardware acceleration issues
echo "Creating udev rule for DMA heap access..." | tee -a "$LOG_FILE"
echo 'KERNEL=="dma_heap", MODE="0666"' > /etc/udev/rules.d/99-dma-heap.rules
udevadm control --reload-rules | tee -a "$LOG_FILE"
udevadm trigger | tee -a "$LOG_FILE"

# Enable universe repository
echo "Enabling universe repository..." | tee -a "$LOG_FILE"
apt-get install -y software-properties-common | tee -a "$LOG_FILE"
add-apt-repository universe -y | tee -a "$LOG_FILE"

# Update and upgrade system
echo "Updating and upgrading Ubuntu Server..." | tee -a "$LOG_FILE"
apt-get update -y | tee -a "$LOG_FILE"
apt-get upgrade -y | tee -a "$LOG_FILE"
apt-get dist-upgrade -y | tee -a "$LOG_FILE"
echo "System updated and upgraded." | tee -a "$LOG_FILE"

# Install system packages, including X11 for easy rotation and SSH
echo "Installing system packages..." | tee -a "$LOG_FILE"
apt-get install -y python3 python3-pip python3-venv git python3-pyqt6 python3-pyqt6.qtwebengine python3-pyqt6.qtcharts python3-pyqt6.qtquick unclutter plymouth plymouth-themes libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers htop libgbm1 libdrm2 upower iw python3-requests python3-tz python3-dateutil python3-pandas qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtquick-controls qml6-module-qtquick-layouts qml6-module-qtcharts qml6-module-qtwebengine lz4 plymouth-theme-spinner xserver-xorg xinit x11-xserver-utils openbox libinput-tools ubuntu-raspi-settings xserver-xorg-video-modesetting libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0 python3-xdg python3-pyqtgraph | tee -a "$LOG_FILE"

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

Section "Device"
    Identifier "vc4"
    Driver "modesetting"
    Option "AccelMethod" "glamor"
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
    echo "dtoverlay=vc4-kms-v3d-pi5,cma-768" >> "$CONFIG_FILE"  # Increased CMA to 768MB for better GPU memory allocation
    echo "gpu_mem=256" >> "$CONFIG_FILE"  # Dedicated GPU memory
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

# Modify app.py to add VizDisplayCompositor disable flag for hardware acceleration fix
echo "Modifying app.py to fix Qt WebEngine hardware acceleration..." | tee -a "$LOG_FILE"
sudo -u "$USER" sed -i 's/--enable-native-gpu-memory-buffers --enable-zero-copy/--enable-native-gpu-memory-buffers --enable-zero-copy --disable-features=VizDisplayCompositor/' "$REPO_DIR/app.py"

# Customize Plymouth spinner theme with SpaceX logo
echo "Customizing Plymouth spinner theme with SpaceX logo..." | tee -a "$LOG_FILE"
cp "$REPO_DIR/spacex_logo.png" /usr/share/plymouth/themes/spinner/bgrt-fallback.png

# Set Plymouth theme to spinner (default with custom logo)
echo "Setting Plymouth theme to spinner..." | tee -a "$LOG_FILE"
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth 100 | tee -a "$LOG_FILE"
update-alternatives --set default.plymouth /usr/share/plymouth/themes/spinner/spinner.plymouth | tee -a "$LOG_FILE"

# Rebuild initramfs to include changes
update-initramfs -u -k all | tee -a "$LOG_FILE"

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
sudo -u "$USER" bash -c "cat << EOF > ~/.xinitrc
openbox-session &
sleep 2
xrandr --output HDMI-1 --rotate left 2>&1 | tee ~/xrandr.log
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 -root &
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS=\"--enable-gpu --ignore-gpu-blocklist --enable-accelerated-video-decode --enable-webgl\"
export QT_LOGGING_RULES=\"qt.webenginecontext=true\"
export QTWEBENGINE_DISABLE_SANDBOX=\"1\"
export QSG_RHI_BACKEND=\"gl\"
export EGL_PLATFORM=\"drm\"
export MESA_GL_VERSION_OVERRIDE=\"3.3\"
export MESA_GLSL_VERSION_OVERRIDE=\"330\"
export LIBGL_ALWAYS_SOFTWARE=\"0\"
export LIBGL_DEBUG=\"0\"
export LIBGL_ALWAYS_INDIRECT=\"0\"
export DRI_PRIME=\"1\"
export VDPAU_DRIVER=\"vc4\"
export LIBVA_DRIVER_NAME=\"vc4\"
exec python3 $REPO_DIR/app.py > $HOME_DIR/app.log 2>&1
EOF"
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

# Create a more reliable auto-start script
sudo -u "$USER" bash -c "cat << EOF > ~/start_kiosk.sh
#!/bin/bash
# Kiosk auto-start script
echo \"Starting kiosk mode at \$(date)\" >> ~/kiosk_start.log

# Wait for system to be ready
sleep 5

# Start X if not already running
if [ -z \"\$DISPLAY\" ]; then
    echo \"Starting X11...\" >> ~/kiosk_start.log
    exec startx
fi
EOF"
chmod +x "$HOME_DIR/start_kiosk.sh" | tee -a "$LOG_FILE"

# Launch X from .profile only on tty1 (more reliable for autologin sourcing)
sudo -u "$USER" bash -c "cat << EOF > ~/.profile
# Auto-start X on tty1 for kiosk mode
if [ \"\$(tty)\" = \"/dev/tty1\" ] && [ -z \"\$DISPLAY\" ]; then
    echo \"Starting X11 on tty1...\" >> ~/x_start.log
    exec startx
fi
EOF"

# Also add to .bashrc as backup
sudo -u "$USER" bash -c "cat << EOF >> ~/.bashrc

# Kiosk mode backup start
if [ \"\$(tty)\" = \"/dev/tty1\" ] && [ -z \"\$DISPLAY\" ] && [ ! -f ~/x_started ]; then
    touch ~/x_started
    echo \"Starting kiosk from bashrc at \$(date)\" >> ~/kiosk_start.log
    exec ~/start_kiosk.sh
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