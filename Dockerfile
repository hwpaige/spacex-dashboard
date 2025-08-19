# Use Ubuntu 25.10 arm64 base image to match host OS
FROM arm64v8/ubuntu:25.10

# Set environment variables for non-interactive install and X11
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:0
ENV QT_QPA_PLATFORM=xcb

# Install system dependencies (mirroring your setup script for PyQt6, Xorg, Mesa/GPU, and app reqs)
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    xorg \
    xserver-xorg-core \
    openbox \
    lightdm \
    lightdm-gtk-greeter \
    x11-xserver-utils \
    xauth \
    python3-pyqt6 \
    python3-pyqt6.qtwebengine \
    python3-pyqt6.qtcharts \
    python3-pyqt6.qtquick \
    unclutter \
    plymouth \
    plymouth-themes \
    xserver-xorg-input-libinput \
    xserver-xorg-input-synaptics \
    libgl1-mesa-dri \
    libgles2 \
    libopengl0 \
    mesa-utils \
    libegl1 \
    libgbm1 \
    mesa-vulkan-drivers \
    htop \
    libdrm2 \
    accountsservice \
    python3-requests \
    python3-tz \
    python3-dateutil \
    python3-pandas \
    upower \
    iw \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the application code into the container
COPY . /app

# Set working directory
WORKDIR /app

# Install any Python dependencies via pip (if your app has a requirements.txt; add it if needed)
# RUN pip3 install -r requirements.txt  # Uncomment and create requirements.txt if necessary

# Expose any needed ports (optional, if app has networking beyond host)
# EXPOSE 80

# Run the app (matches your start_app.sh)
CMD ["python3", "app.py"]