import paramiko
import sys

def run_diagnostics(host, user, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=10)
        
        print(f"--- System Resource Snapshot on {host} ---")
        
        commands = [
            ("Uptime & Load", "uptime"),
            ("Memory Usage", "free -h"),
            ("Swap Status", "swapon --show"),
            ("CPU Info", "lscpu | grep 'MHz'"),
            ("Top 10 Processes by CPU", "ps -eo pcpu,pmem,args --sort=-pcpu | head -n 11"),
            ("Top 10 Processes by Memory", "ps -eo pcpu,pmem,args --sort=-pmem | head -n 11"),
            ("Chromium/Qt Process Tree", "ps -eo pcpu,pmem,args | grep -E 'python3|QtWebEngine' | grep -v grep"),
            ("GPU Memory", "sudo /usr/bin/vcgencmd get_mem gpu || sudo /opt/vc/bin/vcgencmd get_mem gpu || echo 'vcgencmd not found'"),
            ("Throttling Status", "sudo /usr/bin/vcgencmd get_throttled || sudo /opt/vc/bin/vcgencmd get_throttled || echo 'vcgencmd not found'"),
            ("Temperature", "sudo /usr/bin/vcgencmd measure_temp || sudo /opt/vc/bin/vcgencmd measure_temp || echo 'vcgencmd not found'")
        ]
        
        for title, cmd in commands:
            print(f"\n>>> {title}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode('utf-8').strip())
            
        ssh.close()
    except Exception as e:
        print(f"Failed to run diagnostics: {e}")

def restart_app(host, user, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=10)
        print(f"--- Restarting Application on {host} ---")
        ssh.exec_command("sudo systemctl restart lightdm")
        ssh.close()
    except Exception as e:
        print(f"Failed to restart app: {e}")

def apply_performance_fixes(host, user, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=10)
        
        print(f"--- Applying Performance Fixes on {host} ---")
        
        # 1. Fix /dev/vcio permissions for vcgencmd
        print("Fixing /dev/vcio permissions...")
        ssh.exec_command("sudo mknod /dev/vcio c 100 0 2>/dev/null || true")
        ssh.exec_command("sudo chmod 666 /dev/vcio")
        ssh.close()
    except Exception as e:
        print(f"Failed to apply fixes: {e}")

def fix_xsession(host, user, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=user, password=password, timeout=10)
        
        print(f"--- Fixing .xsession on {host} with OPTIMIZED flags ---")
        
        xsession_content = f"""#!/bin/bash
export SHELL=/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "Starting X session at $(date)" > ~/xsession.log

# Clear any console text and switch to X tty
chvt 7 2>/dev/null || true
clear 2>/dev/null || true

# Set display settings
sleep 2
# Force 3840x1100 resolution for DFR1125
# Modeline: 3840x1100 @ 60Hz (297MHz pixel clock)
MODELINE="297.00  3840 4016 4104 4400  1100 1103 1113 1125 -hsync +vsync"
xrandr --newmode "3840x1100_60.00" $MODELINE 2>/dev/null || true
xrandr --addmode HDMI-1 "3840x1100_60.00" 2>/dev/null || true
xrandr --output HDMI-1 --mode 3840x1100_60.00 --rotate normal 2>&1 | tee -a ~/xrandr.log

# Set X settings
xset s off
xset -dpms
xset s noblank

# Hide cursor
unclutter -idle 0 -root &

# Start a lightweight window manager for kiosk (Matchbox)
matchbox-window-manager -use_titlebar no -use_cursor no &

# Set environment variables
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=~/.Xauthority
export QTWEBENGINE_CHROMIUM_FLAGS="--enable-gpu --ignore-gpu-blocklist --enable-webgl --disable-gpu-sandbox --no-sandbox --use-gl=egl --disable-dev-shm-usage --memory-pressure-off --max_old_space_size=1024 --memory-reducer --gpu-memory-buffer-size-mb=256 --max-tiles-for-interest-area=256 --num-raster-threads=1 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --autoplay-policy=no-user-gesture-required --no-user-gesture-required-for-fullscreen --disable-gpu-vsync --disable-smooth-scrolling --enable-zero-copy --disable-reading-from-canvas"
export PYQTGRAPH_QT_LIB=PyQt6
export QT_DEBUG_PLUGINS=0
export QT_LOGGING_RULES="qt.qpa.plugin=false"

# Change to app directory
cd ~/Desktop/project/src

# Truncate app log
if [ -f ~/app.log ]; then
    mv ~/app.log ~/app.log.old 2>/dev/null || true
fi
> ~/app.log

echo "Starting SpaceX Dashboard at $(date)" >> ~/app.log

# Start the application
exec python3 app.py >> ~/app.log 2>&1
"""
        # Write the file
        sftp = ssh.open_sftp()
        with sftp.file('/home/harrison/.xsession', 'w') as f:
            f.write(xsession_content)
        sftp.close()
        
        ssh.exec_command("chmod +x ~/.xsession")
        ssh.close()
    except Exception as e:
        print(f"Failed to fix .xsession: {e}")

if __name__ == "__main__":
    restart_app("pi.local", "harrison", "hpaige")
    print("Waiting 15 seconds for app to start...")
    import time
    time.sleep(15)
    run_diagnostics("pi.local", "harrison", "hpaige")
