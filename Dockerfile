FROM ubuntu:24.04
RUN apt-get update && apt-get install -y python3 python3-pip git pyqt5-dev-tools python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtchart python3-pyqt5.qtquick libqt5widgets5 libqt5gui5 libqt5core5a libqt5dbus5 libqt5network5 libqt5svg5 libqt5webenginewidgets5 libgl1-mesa-dri libgles2 libopengl0 mesa-utils libegl1 libgbm1 mesa-vulkan-drivers x11-apps x11-xserver-utils xserver-xorg-input-libinput xserver-xorg-input-synaptics unclutter linux-firmware libdrm2 libgbm1 htop libxcb1 libxcb-xinerama0 libxcb-xinput0 libxcb-xfixes0 libxcb-shape0 libxcb-render-util0 libxcb-randr0 libxcb-keysyms1 libxkbcommon-x11-0 libxcb-icccm4 libxcb-cursor0 libx11-6 libxext6 libxi6 libxtst6 libxrender1 libfontconfig1 libfreetype6 libjpeg-turbo8 libpng16-16 '^libxcb.*-dev' libx11-xcb-dev libglu1-mesa-dev libxrender-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN rm -f /usr/lib/python3.*/EXTERNALLY-MANAGED
WORKDIR /app
COPY . .
RUN pip3 install --upgrade --ignore-installed pip setuptools wheel && pip3 install -r requirements.txt
RUN chown -R 1000:1000 /app
USER 1000
ENV QT_OPENGL=desktop
ENV QTWEBENGINE_CHROMIUM_FLAGS="--enable-gpu --ignore-gpu-blacklist --enable-accelerated-video-decode --enable-webgl --enable-logging --v=1 --log-level=0"
ENV QT_LOGGING_RULES="qt.webenginecontext=true;qt5ct.debug=false"
ENV QTWEBENGINE_DISABLE_SANDBOX=1
ENV DISPLAY=:0
RUN echo '#!/bin/bash' > start_app.sh && echo 'python3 app.py' >> start_app.sh && chmod +x start_app.sh
CMD ["/app/start_app.sh"]