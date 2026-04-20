qml_code = """
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import Charts 1.0
import QtWebEngine

// Qt5Compat.GraphicalEffects (OpacityMask) removed to avoid hard dependency

Window {
    id: root
    visible: true
    width: backend ? backend.width : 1480
    height: backend ? backend.height : 320
    title: "SpaceX Dashboard"
    // Ensure no scaling is applied to the window content
    // Qt should respect the exact pixel dimensions
    Component.onCompleted: {
        console.log("Window dimensions: " + width + "x" + height)
        console.log("Screen dimensions: " + Screen.width + "x" + Screen.height)
        console.log("Device pixel ratio: " + Screen.devicePixelRatio)
        console.log("Qt platform: " + Qt.platform.os)
        console.log("Window created - bottom bar should be visible")
        // Connect web content reload signal
        backend.reloadWebContent.connect(function() {
            console.log("Reloading web content after WiFi connection...")
            // Plot card globe view (left-most card) – also avoid reload
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                    try {
                        plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
                    } catch (e) { console.log("Plot globe view JS resume failed:", e); }
                }
            }
            // Debounce all other heavy reloads to a single update shortly after connect
            if (reloadCoalesceTimer.running) reloadCoalesceTimer.stop();
            reloadCoalesceTimer.start();
        })
        // Push globe autospin guard flag into globe pages
        var guard = backend.globeAutospinGuard
        var guardJs = "window.globeAutospinGuard=" + (guard ? "true" : "false") + ";"
        if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
            try { plotGlobeView.runJavaScript(guardJs) } catch(e) { console.log("Failed to set globeAutospinGuard on plotGlobeView:", e) }
        }
        // Resume spin on key backend signals
        backend.launchCacheReady.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.updateGlobeTrajectory.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.loadingFinished.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.firstOnline.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        // Keep guard value in sync if changed at runtime
        backend.globeAutospinGuardChanged.connect(function() {
            if (backend.wifiConnecting) return;
            var guard2 = backend.globeAutospinGuard
            var guardJs2 = "window.globeAutospinGuard=" + (guard2 ? "true" : "false") + ";"
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript(guardJs2)
        })
        // Handle touch calibration window visibility
        backend.calibrationStarted.connect(function() {
            console.log("Calibration started - hiding main window")
            root.visible = false
            if (typeof displaySettingsPopup !== 'undefined') displaySettingsPopup.close()
        })
        backend.calibrationFinished.connect(function() {
            console.log("Calibration finished - showing main window")
            root.visible = true
            root.requestActivate()
        })
    }

    function getStatusColor(status) {
        if (!status) return "#999999"
        var s = status.toString().toUpperCase()
        if (s === 'TBD' || s === 'TBC' || s.indexOf('DETERMINED') !== -1 || s.indexOf('CONFIRMED') !== -1) return "#FF9800"
        if (s.indexOf('SUCCESS') !== -1 || s.indexOf('GO') !== -1) return "#4CAF50"
        if (s.indexOf('PARTIAL FAILURE') !== -1) return "#FFC107"
        if (s.indexOf('FAILURE') !== -1) return "#F44336"
        if (s.indexOf('SCRUBBED') !== -1 || s.indexOf('CANCELLED') !== -1) return "#9E9E9E"
        return "#F44336" // Default to red for other unknown statuses
    }

    function openSettingsPopup(categoryIndex) {
        if (typeof displaySettingsPopup === 'undefined') return
        if (typeof settingsCategoryStack !== 'undefined') {
            settingsCategoryStack.currentIndex = categoryIndex
        }
        displaySettingsPopup.open()
    }
    onActiveChanged: {
        if (active) {
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                   try { plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();"); } catch (e) {}
                }
            }
        }
    }
    // Use the same background color as the globe view for visual consistency
    color: (backend && backend.theme === "dark") ? "#111111" : "#f8f8f8"
    Behavior on color { ColorAnimation { duration: 300 } }

    property bool autoFullScreen: false
    // Track the currently selected YouTube URL for the video card.
    // Initialized to the NSF Starbase Live stream by default.
    property url currentVideoUrl: backend ? "http://localhost:" + backend.httpPort + "/youtube_embed_nsf.html" : ""
    // Stores the video URL that was active before an automatic switch to the live feed.
    property url _preLiveVideoUrl: ""
    // True when the live feed switch was triggered automatically (not by the user).
    property bool _autoSwitchedToLive: false

    // UI Ready tracking
    property int _pendingCriticalLoads: (backend && backend.isHighResolution) ? 2 : 1
    function _onCriticalComponentLoaded() {
        _pendingCriticalLoads--;
        console.log("Critical UI component loaded. Pending: " + _pendingCriticalLoads);
        if (_pendingCriticalLoads <= 0) {
            _checkAndNotifyReady();
        }
    }
    function _checkAndNotifyReady() {
        if (backend && backend.isLoading) {
            console.log("All critical UI components loaded. Notifying backend.");
            backend.notifyUiReady();
        }
    }
    // Safety timer in case some component fails to load or we miscounted
    Timer {
        id: uiReadySafetyTimer
        interval: 5000 // 5 seconds after QML completion should be plenty
        running: true
        onTriggered: {
            console.log("UI ready safety timer triggered.");
            _checkAndNotifyReady();
        }
    }

    Connections {
        target: backend
        function onUiReady() {
            uiReadySafetyTimer.stop();
        }
    }

    // Alignment guide removed after calibration; margins are now fixed below.

    // Helper to enforce rounded corners inside WebEngine pages themselves.
    // This injects CSS into the page to round and clip at the document level,
    // which works even when the scene-graph clipping is ignored by Chromium.
    function _injectRoundedCorners(webView, radiusPx, customColor) {
        if (!webView || !webView.runJavaScript) return;
        if (typeof backend !== 'undefined' && backend && backend.wifiConnecting) return; // Prevent JS during connection
        var r = Math.max(0, radiusPx|0);
        // Default to transparent if no custom color provided, allowing the QML background to show through the corners.
        // If a specific color is needed (e.g. to hide artifacts), it can be passed in.
        var themeColor = customColor ? customColor : "transparent";
        var js = "(function(){try{" +
                 "var r=" + r + ";" +
                 "var themeColor='" + themeColor + "';" +
                 "var apply=function(){var h=document.documentElement, b=document.body;" +
                 " if(h){h.style.borderRadius=r+'px'; h.style.overflow='hidden'; h.style.clipPath='inset(0 round '+r+'px)'; h.style.backgroundColor=themeColor;}" +
                 " if(b){b.style.borderRadius=r+'px'; b.style.overflow='hidden'; b.style.clipPath='inset(0 round '+r+'px)'; b.style.backgroundColor=themeColor;}" +
                 "};" +
                 "apply();" +
                 "var i=0; var timer=setInterval(function(){try{apply(); if(++i>10) clearInterval(timer);}catch(e){clearInterval(timer);}}, 500);" +
                 "}catch(e){}})();";
        webView.runJavaScript(js);
    }

    // Debounce non-globe web content reloads so the globe keeps spinning smoothly
    // and other views refresh once after Wi‑Fi connection settles.
    Timer {
        id: reloadCoalesceTimer
        interval: 7000
        repeat: false
        running: false
        onTriggered: {
            // Lightweight backend refreshes - keep these here
            if (typeof backend !== 'undefined' && backend.update_countdown) {
                backend.update_countdown();
                console.log("Countdown refreshed (debounced)");
            }
            if (typeof backend !== 'undefined' && backend.update_weather) {
                backend.update_weather();
                console.log("Weather data refresh initiated (debounced)");
            }
            // Nudge globe(s) again after network-driven reloads completed
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                    try { globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();"); } catch(e){}
                }
            }
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                    try { plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();"); } catch(e){}
                }
            }
        }
    }

    Connections {
        target: backend
        function onVideoUrlChanged() {
            // Sync with backend video URL if it's a specific launch video (YouTube embed)
            // or if we are currently on a default/empty state.
            // This prevents background refreshes from overriding manual NSF/Live selections
            // while still allowing launch selection to work.
            var current = root.currentVideoUrl.toString()
            var next = backend.videoUrl.toString()
            
            // If the user has manually selected NSF or the Live stream, 
            // don't let background updates (like the placeholder) override it.
            var isManualLive = (backend.liveLaunchUrl !== "" && current === backend.liveLaunchUrl)
            // We check the URL directly for NSF as well (both legacy direct URL and local wrapper page)
            var nsfUrl = "https://www.youtube.com/embed/live_stream?channel=UCSUu1lih2njqoJ1zKgZpX6A&rel=0&controls=1&autoplay=1&mute=1&enablejsapi=1"
            var nsfLocalUrl = "http://localhost:" + backend.httpPort + "/youtube_embed_nsf.html"
            var isManualNsf = (current === nsfUrl || current === nsfLocalUrl)
            
            if (isManualLive || isManualNsf) {
                // Only allow override if 'next' is a specific YouTube video (not the placeholder)
                // and it's different from what we had.
                if (next.indexOf("youtube.com/embed/") !== -1 && !next.endsWith("/youtube_embed.html") && next !== current) {
                     console.log("Allowing manual override from list selection while on LIVE/NSF")
                     root.currentVideoUrl = next
                }
                return
            }
            
            if (next.indexOf("youtube.com/embed/") !== -1 || 
                current === "" || 
                current.endsWith("/youtube_embed.html") || 
                current === "about:blank") {
                root.currentVideoUrl = next
            }
        }
    }

    // (Removed duplicate Component.onCompleted block; logic merged above)

    Rectangle {
        id: loadingScreen
        anchors.fill: parent
        // Match app background to the globe background
        color: (backend && backend.theme === "dark") ? "#111111" : "#f8f8f8"
    // Keep this container visible during initial load OR while an update is in progress
    visible: !!(backend && (backend.isLoading || backend.updatingInProgress))
        z: 1

        Image {
            id: splashLogo
            source: "file:///" + spacexLogoPath
            width: 500
            height: 160
            sourceSize.width: 500
            sourceSize.height: 160
            fillMode: Image.PreserveAspectFit
            anchors.centerIn: parent
        }

        Text {
            text: backend ? backend.loadingStatus : "Initializing..."
            anchors.top: splashLogo.bottom
            anchors.topMargin: 20
            anchors.horizontalCenter: parent.horizontalCenter
            color: (backend && backend.theme === "dark") ? "#ffffff" : "#000000"
            font.pixelSize: 16
            font.family: "D-DIN"
            horizontalAlignment: Text.AlignHCenter
        }

        // Update progress overlay (shown during in-app update)
        Rectangle {
            id: updateOverlay
            anchors.fill: parent
            visible: backend && backend.updatingInProgress
            color: (backend && backend.theme === "dark") ? "#111111" : "#f8f8f8"
            opacity: 0.98
            z: 9999
            property bool showTerminalOutput: false
            onVisibleChanged: {
                if (visible) {
                    // Start each update session with details collapsed.
                    showTerminalOutput = false
                }
            }

            // Block all mouse/keyboard input to underlying UI while updating
            MouseArea { anchors.fill: parent; hoverEnabled: true }

            Column {
                anchors.centerIn: parent
                spacing: 16
                width: Math.min(parent.width * 0.8, 700)

                Image {
                    source: "file:///" + spacexLogoPath
                    width: 240
                    height: 48
                    fillMode: Image.PreserveAspectFit
                    anchors.horizontalCenter: parent.horizontalCenter
                }

                Rectangle {
                    width: parent.width
                    height: 36
                    radius: 8
                    color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: updateOverlay.showTerminalOutput ? "Hide terminal output" : "Show terminal output"
                        color: backend.theme === "dark" ? "#E0E0E0" : "#202020"
                        font.pixelSize: 13
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: updateOverlay.showTerminalOutput = !updateOverlay.showTerminalOutput
                    }
                }

                // Progress text area showing tail of updater log
                Rectangle {
                    visible: updateOverlay.showTerminalOutput
                    width: parent.width
                    height: 140
                    radius: 8
                    color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                    border.width: 1

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 10
                        clip: true
                        ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                        TextArea {
                            readOnly: true
                            text: backend && backend.updatingStatus ? backend.updatingStatus : "Preparing update…"
                            color: backend.theme === "dark" ? "#E0E0E0" : "#202020"
                            selectionColor: "transparent"
                            wrapMode: TextArea.Wrap
                            background: null
                        }
                    }
                }

                // Subtext
                Text {
                    text: "Updating application… the device will reboot automatically when complete."
                    color: backend.theme === "dark" ? "#C0C0C0" : "#404040"
                    font.pixelSize: 14
                    horizontalAlignment: Text.AlignHCenter
                    width: parent.width
                }

                // Minimal spinner imitation (animated dots)
                Row {
                    spacing: 6
                    anchors.horizontalCenter: parent.horizontalCenter
                    Repeater {
                        model: 3
                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: backend.theme === "dark" ? "#9ad1d4" : "#181818"
                            SequentialAnimation on opacity {
                                running: updateOverlay.visible
                                loops: Animation.Infinite
                                NumberAnimation { from: 0.2; to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
                                NumberAnimation { from: 1.0; to: 0.2; duration: 600; easing.type: Easing.InOutQuad }
                                // Use a dedicated PauseAnimation element; 'pause' is not a valid property
                                PauseAnimation { duration: index * 120 }
                            }
                        }
                    }
                }

                // Cancel button row
                Row {
                    spacing: 8
                    anchors.horizontalCenter: parent.horizontalCenter
                    // Keep some top margin from the log area
                    anchors.topMargin: 6

                    Rectangle {
                        id: cancelUpdateBtn
                        width: 140
                        height: 28
                        radius: 14
                        color: "#F44336"   // Red to match dropdown switch/error accent
                        border.color: backend.theme === "dark" ? "#b93b30" : "#d13c32"
                        border.width: 1
                        visible: backend && backend.updatingInProgress

                        Text {
                            anchors.centerIn: parent
                            text: "Cancel Update"
                            font.pixelSize: 12
                            font.bold: true
                            color: "white"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (backend && backend.cancelUpdate) {
                                    backend.cancelUpdate()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Alignment guide rectangle removed
    // Cache expensive / repeated lookups
    
    Connections {
        target: backend
        function onWeatherChanged() {
            // Reload loop removed to prevent race condition with radarBaseUrl binding.
            // Windy widget URL binding now handles updates reliably.
            // if (backend.mode === "spacex" && typeof weatherSwipe !== 'undefined') {
            //    for (var i = 0; i < weatherSwipe.count; i++) {
            //        var item = weatherSwipe.itemAt(i);
            //        if (!item) continue;
            //        var container = item.children && item.children.length > 0 ? item.children[0] : null;
            //        var webChild = null;
            //        if (container && container.children && container.children.length > 0) {
            //            for (var c = 0; c < container.children.length; c++) {
            //                var ch = container.children[c];
            //                if (ch && ch.reload && ch.url !== undefined) { webChild = ch; break; }
            //            }
            //        }
            //        if (webChild && webChild.reload) {
            //            try { webChild.reload(); console.log("Weather view", i, "reloaded (updateWeather)"); }
            //            catch (e) { console.log("Weather view", i, "reload failed:", e); }
            //        }
            //    }
            // }
        }
        function onUpdateGlobeTrajectory() {
            // Update trajectory when data loads
            var trajectoryData = backend.get_launch_trajectory();
            if (trajectoryData) {
                if (typeof globeView !== 'undefined' && globeView.runJavaScript) {
                    globeView.runJavaScript("if(typeof updateTrajectory !== 'undefined') updateTrajectory(" + JSON.stringify(trajectoryData) + ");");
                }
                if (typeof plotGlobeView !== 'undefined' && plotGlobeView && plotGlobeView.runJavaScript) {
                    plotGlobeView.runJavaScript("if(typeof updateTrajectory !== 'undefined') updateTrajectory(" + JSON.stringify(trajectoryData) + ");");
                }
            }
        }
    }

    // Safe area: pretend the right edge is closer by shrinking the usable width
    // This ensures all content is laid out as if the screen were narrower.
    Item {
        id: safeArea
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        // Fixed right inset after calibration (original 6px cutoff + 6px safety = 12px)
        anchors.rightMargin: (root.height > root.width) ? 0 : ((1.0 - backgroundWindy.progress) > 0 ? (1.0 - backgroundWindy.progress) * 12 : 0)
        // Fixed bottom inset for vertical mode after calibration (12px)
        anchors.bottomMargin: (root.height > root.width) ? ((1.0 - backgroundWindy.progress) > 0 ? (1.0 - backgroundWindy.progress) * 12 : 0) : 0
        
        /* Binding {
            target: backgroundWindy
            property: "anchors.right"
            value: videoCard.left
            when: (typeof videoCard !== 'undefined' && videoCard !== null)
        } */

        // Expanded Windy/Radar Background (Tesla Style)
        Item {
            id: backgroundWindy
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: (root.height > root.width) ? undefined : parent.bottom
            // Keep right anchor only in portrait; in landscape width binding drives expansion.
            anchors.right: (root.height > root.width) ? parent.right : undefined
            // Use anchors.rightMargin/bottomMargin to handle the safeArea logic directly on the background
            anchors.rightMargin: (root.height > root.width) ? 0 : ((1.0 - progress) > 0 ? (1.0 - progress) * 12 : 0)
            anchors.bottomMargin: (root.height > root.width) ? ((1.0 - progress) > 0 ? (1.0 - progress) * 12 : 0) : 0
            
            property bool isDragging: false
            property real manualWidth: minSize
            property real expansionFactor: 0.0
            property bool isLocked: true

            readonly property bool isHighRes: backend && backend.isHighResolution

            // Dimension logic: handles both horizontal (width) and vertical (height) expansion
            width: (root.height > root.width) ? parent.width : (isDragging ? manualWidth : (minSize + expansionFactor * (root.width - minSize)))
            height: (root.height > root.width) ? (isDragging ? manualWidth : (minSize + expansionFactor * (root.height - minSize))) : parent.height
            z: 0 // Behind centralContent
            visible: !!(!backend || !backend.isLoading)
            clip: true

            // Slightly widen the default (collapsed) landscape weather panel.
            readonly property real minSize: (root.height > root.width) ? ((root.height / 4) + (isHighRes ? 120 : 250)) : ((root.width / 4) + (isHighRes ? 245 : 375))
            
            // Reset expansion on orientation change
            property bool isVerticalOrientation: root.height > root.width
            onIsVerticalOrientationChanged: {
                expansionFactor = 0.0
                isLocked = true
            }

            readonly property real progress: (root.height > root.width) 
                                            ? Math.max(0, Math.min(1, (height - minSize) / Math.max(1, root.height - minSize)))
                                            : Math.max(0, Math.min(1, (width - minSize) / Math.max(1, root.width - minSize)))
            onWidthChanged: {
                if (!isDragging && widthAnimation && widthAnimation.running) {
                    // Force re-evaluation of dependent properties if needed
                }
            }

            Behavior on width {
                id: widthBehavior
                enabled: !backgroundWindy.isDragging && (root.height <= root.width)
                NumberAnimation { 
                    id: widthAnimation
                    duration: 400
                    easing.type: Easing.OutCubic 
                } 
            }
            
            Behavior on height {
                id: heightBehavior
                enabled: !backgroundWindy.isDragging && (root.height > root.width)
                NumberAnimation { 
                    id: heightAnimation
                    duration: 400
                    easing.type: Easing.OutCubic 
                } 
            }

            SwipeView {
                id: weatherSwipe
                anchors.fill: parent
                visible: !!backend
                orientation: Qt.Vertical
                clip: false
                layer.enabled: true
                layer.smooth: true
                interactive: !backgroundWindy.isLocked
                currentIndex: 1
                property int loadedMask: (1 << 1)
                onCurrentIndexChanged: loadedMask |= (1 << currentIndex)

                // Cache some constants for the web views to avoid per-frame lookups
                readonly property real maxTextureWidth: root.width
                readonly property real maxTextureHeight: root.height

                Repeater {
                    model: ["radar", "wind", "gust", "clouds", "temp", "pressure"]
                    Item {
                        Rectangle {
                            anchors.fill: parent
                            color: (backend && backend.theme === "dark") ? "#111111" : "#f8f8f8"
                            clip: false
                            Loader {
                                id: webViewLoader
                                anchors.fill: parent
                                active: (weatherSwipe.loadedMask & (1 << index))
                                visible: index === weatherSwipe.currentIndex
                                sourceComponent: WebEngineView {
                                    id: webView
                                    objectName: "webView"
                                    anchors.fill: parent
                                    layer.enabled: backgroundWindy.isDragging || (widthAnimation && widthAnimation.running) || (heightAnimation && heightAnimation.running)
                                    layer.smooth: true
                                    // layer.renderTarget removed due to compatibility issues with older Qt versions
                                    // layer.renderTarget: Item.FramebufferObject
                                    layer.textureSize: (backgroundWindy.isDragging || (widthAnimation && widthAnimation.running) || (heightAnimation && heightAnimation.running))
                                                        ? Qt.size(weatherSwipe.maxTextureWidth, weatherSwipe.maxTextureHeight) 
                                                        : Qt.size(width > 0 ? width : 1, height > 0 ? height : 1)
                                    enabled: !backgroundWindy.isLocked
                                    backgroundColor: (backend && backend.theme === "dark") ? "#111111" : "#f8f8f8"
                                    url: parent.visible && backend ? backend.radarBaseUrl.replace("radar", modelData) + "&v=" + Date.now() : ""
                                    settings.webGLEnabled: true
                                    settings.accelerated2dCanvasEnabled: true
                                    settings.allowRunningInsecureContent: true
                                    settings.javascriptEnabled: true
                                    settings.localContentCanAccessRemoteUrls: true

                                    Connections {
                                        target: backend
                                        function onReloadWebContent() {
                                            var delay = 1500 + (index * 500)
                                            reloadTimer.interval = delay
                                            reloadTimer.start()
                                        }
                                    }
                                    Timer {
                                        id: reloadTimer
                                        repeat: false
                                        onTriggered: webView.reload()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Right/Bottom side fade effect
            Rectangle {
                anchors.top: (root.height > root.width) ? undefined : parent.top
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                anchors.left: (root.height > root.width) ? parent.left : undefined
                width: (root.height > root.width) ? undefined : 250 
                height: (root.height > root.width) ? 250 : undefined
                opacity: 1.0 - backgroundWindy.progress
                visible: opacity > 0
                gradient: Gradient {
                    orientation: (root.height > root.width) ? Gradient.Vertical : Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 1.0; color: root.color }
                }
            }
        }

        ColumnLayout {
            id: centralContent
            anchors.fill: parent
            z: 1  // Ensure cards sit on top of background Windy view
            anchors.leftMargin: 5
            // No rightMargin here — safeArea already reduces width on the right
            anchors.topMargin: 5
            anchors.bottomMargin: 40
            spacing: 5
            visible: !!(!backend || !backend.isLoading)

            GridLayout {
                id: mainRowLayout
                Layout.fillWidth: true
                Layout.fillHeight: true
                columnSpacing: 5
                rowSpacing: 5
                columns: root.height > root.width ? 1 : 4
                rows: root.height > root.width ? 4 : 1

            // Column 1: Radar (Transparent Spacer with UI Overlay)
            Rectangle {
                id: radarColumn
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: root.height > root.width ? -1 : 1.0
                Layout.preferredHeight: root.height > root.width ? 1.0 : -1
                color: "transparent"
                radius: 0
                clip: false

                Item {
                    anchors.fill: parent

                    // Tesla-style drag expansion MouseArea
                    MouseArea {
                        id: expansionGestureArea
                        anchors.fill: parent
                        z: 5 // Below buttons but above the spacer
                        enabled: backgroundWindy.isLocked
                        
                        property real startPos: 0
                        property real initialSize: 0
                        
                        onPressed: (mouse) => {
                            var currentPos = (root.height > root.width) ? mapToItem(safeArea, mouse.x, mouse.y).y : mapToItem(safeArea, mouse.x, mouse.y).x
                            startPos = currentPos
                            initialSize = (root.height > root.width) ? backgroundWindy.height : backgroundWindy.width
                            backgroundWindy.manualWidth = initialSize
                            backgroundWindy.isDragging = true
                        }
                        
                        onPositionChanged: (mouse) => {
                            if (backgroundWindy.isDragging) {
                                var currentPos = (root.height > root.width) ? mapToItem(safeArea, mouse.x, mouse.y).y : mapToItem(safeArea, mouse.x, mouse.y).x
                                var delta = currentPos - startPos
                                backgroundWindy.manualWidth = Math.max(backgroundWindy.minSize, Math.min((root.height > root.width ? root.height : root.width), initialSize + delta))
                            }
                        }
                        
                        onReleased: (mouse) => {
                            if (backgroundWindy.isDragging) {
                                // Snap logic: if moved more than 15% (was 20%) from the starting state, snap to the other state.
                                var p = backgroundWindy.progress
                                var threshold = 0.12 // Slightly more sensitive threshold
                                if (backgroundWindy.expansionFactor === 0.0) {
                                    backgroundWindy.expansionFactor = (p > threshold) ? 1.0 : 0.0
                                } else {
                                    backgroundWindy.expansionFactor = (p < (1.0 - threshold)) ? 0.0 : 1.0
                                }
                                
                                backgroundWindy.isDragging = false
                            }
                        }
                        
                        onCanceled: {
                            if (backgroundWindy.isDragging) {
                                backgroundWindy.isDragging = false
                            }
                        }
                    }

                    // Weather view buttons container (YouTube style overlay)
                    Rectangle {
                        id: weatherButtonsOverlay
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 15
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: weatherButtonsRow.implicitWidth + 20
                        height: 34
                        color: backend.theme === "dark" ? "#cc181818" : "#ccf5f5f5"
                        radius: 17
                        visible: !!backend && opacity > 0
                        z: 10
                        opacity: 1.0
                        layer.enabled: backgroundWindy.isDragging || widthAnimation.running || videoCard.isDragging || videoWidthAnimation.running
                        layer.smooth: true

                        RowLayout {
                            id: weatherButtonsRow
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "radar", "icon": "\uf7c0", "tooltip": "Weather Radar"},
                                    {"type": "wind", "icon": "\uf72e", "tooltip": "Wind Speed"},
                                    {"type": "gust", "icon": "\uf72e", "tooltip": "Wind Gusts"},
                                    {"type": "clouds", "icon": "\uf0c2", "tooltip": "Cloud Cover"},
                                    {"type": "temp", "icon": "\uf2c7", "tooltip": "Temperature"},
                                    {"type": "pressure", "icon": "\uf6c4", "tooltip": "Pressure"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    color: weatherSwipe.currentIndex === index ?
                                           (backend.theme === "dark" ? "#303030" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#181818" : "#f5f5f5")
                                    radius: 14
                                    border.color: weatherSwipe.currentIndex === index ?
                                                 (backend.theme === "dark" ? "#3a3a3a" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                                    border.width: weatherSwipe.currentIndex === index ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        font.weight: Font.Black
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: weatherSwipe.currentIndex = index
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
                                }
                            }

                            // Interaction Lock/Unlock Button
                            Rectangle {
                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 28
                                color: (backend.theme === "dark" ? "#181818" : "#f5f5f5")
                                radius: 14
                                border.color: (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 200 } }
                                Behavior on border.color { ColorAnimation { duration: 200 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: backgroundWindy.isLocked ? "\uf023" : "\uf09c"
                                    font.pixelSize: 14
                                    font.family: "Font Awesome 5 Free"
                                    font.weight: Font.Black
                                    color: backgroundWindy.isLocked ? "#F44336" : "#4CAF50"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: backgroundWindy.isLocked = !backgroundWindy.isLocked
                                }

                                ToolTip {
                                    text: backgroundWindy.isLocked ? "Unlock Interaction" : "Lock Interaction"
                                    delay: 500
                                }
                            }
                        }
                    }
                }
            }

            // Column 2: Globe Card (Now simplified, Plot moved to Launch Card)
            Rectangle {
                id: plotCard
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: plotCard.isHighResolution ? 0 : (root.height > root.width ? -1 : (1.0 - backgroundWindy.progress))
                Layout.preferredHeight: plotCard.isHighResolution ? 0 : (root.height > root.width ? 1.0 : -1)
                // When showing the globe inside this card, match the app background
                color: "transparent"
                radius: 8
                clip: false
                opacity: (1.0 - backgroundWindy.progress)
                visible: opacity > 0 && !plotCard.isHighResolution
                property bool isHighResolution: backend && backend.isHighResolution

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !!backend

                        // Globe view
                        Item {
                            id: plotGlobeView
                            anchors.fill: parent
                            property bool _loaded: false
                            function runJavaScript(script) {
                                if (plotGlobeLoader.item) plotGlobeLoader.item.runJavaScript(script)
                            }
                            Loader {
                                id: plotGlobeLoader
                                anchors.fill: parent
                                active: true || plotGlobeView._loaded
                                sourceComponent: WebEngineView {
                                    id: plotGlobeViewInner
                                    anchors.fill: parent
                                    url: globeUrl
                                    backgroundColor: "transparent"
                                    onBackgroundColorChanged: {
                                        if (typeof root !== 'undefined') root._injectRoundedCorners(plotGlobeViewInner, 8)
                                    }
                                    zoomFactor: 1.0
                                    layer.enabled: true
                                    layer.smooth: true
                                    layer.textureSize: Qt.size(width > 0 ? width : 1, height > 0 ? height : 1)
                                    settings.javascriptCanAccessClipboard: false
                                    settings.allowWindowActivationFromJavaScript: false
                                    onContextMenuRequested: function(request) { request.accepted = true }

                                    onLoadingChanged: function(loadRequest) {
                                        if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                            if (!plotGlobeView._loaded) {
                                                plotGlobeView._loaded = true;
                                                if (typeof root !== 'undefined') root._onCriticalComponentLoaded();
                                            }
                                            var trajectoryData = backend ? backend.get_launch_trajectory() : null;
                                            if (trajectoryData) {
                                                plotGlobeViewInner.runJavaScript("if(typeof updateTrajectory !== 'undefined') updateTrajectory(" + JSON.stringify(trajectoryData) + ");");
                                            }
                                            if (backend) {
                                                plotGlobeViewInner.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");
                                            }
                                            if (typeof root !== 'undefined') root._injectRoundedCorners(plotGlobeViewInner, 8)
                                            try {
                                                plotGlobeViewInner.runJavaScript("(function(){try{if(window.resumeSpin)resumeSpin();}catch(e){console.log('Plot globe animation start failed', e);}})();");
                                            } catch (e) { console.log("Plot globe JS nudge error:", e); }
                                        }
                                    }

                                    Connections {
                                        target: backend
                                        function onThemeChanged() {
                                            if (backend) {
                                                plotGlobeViewInner.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Column 3: Launches or Races
            Rectangle {
                id: launchCard
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: root.height > root.width ? -1 : (1.0 - backgroundWindy.progress)
                Layout.preferredHeight: root.height > root.width ? 1.0 : -1
                // When in high-resolution mode, the globe is shown at the top, so we make the background 
                // transparent to allow the globe to sit directly on the app background/Windy view.
                color: (isHighResolution) ? "transparent" : (backend.theme === "dark" ? "#181818" : "#f0f0f0")
                radius: 8
                clip: true
                opacity: (1.0 - backgroundWindy.progress)
                visible: opacity > 0
                property string launchViewMode: "list"
                property bool calendarLoaded: false
                property bool chartLoaded: false

                // Check if this is a high resolution display
                property bool isHighResolution: backend && backend.isHighResolution

                Item {
                    anchors.fill: parent
                    anchors.margins: 0

                    StackLayout {
                        anchors.fill: parent
                        currentIndex: launchCard.launchViewMode === "calendar" ? 1 : (launchCard.launchViewMode === "chart" ? 2 : 0)
                        clip: true
                        // Ensure it takes all space including what was ColumnLayout spacing
                        anchors.bottomMargin: 0 

                    // View 0: Existing List View
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: backend.eventModel
                            clip: true
                            spacing: 5
                            interactive: true
                            boundsBehavior: Flickable.StopAtBounds
                            flickableDirection: Flickable.VerticalFlick
                            cacheBuffer: 1500
                            layer.enabled: true
                            layer.smooth: true
                            layer.textureSize: Qt.size(width, height)
                            // Use a fixed height for delegates to help with performance
                            property real delegateHeight: 120
                            reuseItems: true

                        delegate: Item {
                            width: ListView.view.width
                            height: model && model.isGroup ? 30 : launchColumn.height + 20

                            Rectangle { 
                                anchors.fill: parent; 
                                color: (model && model.isGroup) ? "transparent" : 
                                       (backend && backend.selectedLaunch === model.mission ? 
                                        (backend && backend.theme === "dark" ? "#4a5a5a" : "#c0d0d0") : 
                                        (backend && backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")); 
                                radius: (model && model.isGroup) ? 0 : 6;
                                border.width: (model && !model.isGroup && backend && backend.selectedLaunch === model.mission) ? 2 : 0;
                                border.color: (backend && backend.theme === "dark") ? "#6a8a8a" : "#80a0a0";
                            }

                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 15
                                anchors.verticalCenter: parent.verticalCenter
                                text: (model && model.isGroup) ? (model.groupName ? model.groupName : "") : ""
                                font.pixelSize: 14; font.bold: true; color: "#999999"; visible: !!(model && model.isGroup)
                            }

                            Column {
                                id: launchColumn
                                anchors.top: parent.top; anchors.topMargin: 5
                                anchors.left: parent.left; anchors.leftMargin: 10
                                anchors.right: parent.right; anchors.rightMargin: 10
                                spacing: 5
                                visible: !!(model && !model.isGroup && typeof model === 'object')

                                Column {
                                    spacing: 0
                                    width: parent.width - statusPill.width - 5
                                    Text { 
                                        text: {
                                            var m = (model && model.mission) ? model.mission : "";
                                            var idx = m.indexOf("|");
                                            return idx !== -1 ? m.substring(idx + 1).trim() : m;
                                        }
                                        font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; 
                                        color: (backend && backend.theme === "dark") ? "white" : "black"
                                        width: parent.width
                                        wrapMode: Text.Wrap
                                    }
                                    Text { 
                                        text: {
                                            var m = (model && model.mission) ? model.mission : "";
                                            var idx = m.indexOf("|");
                                            return idx !== -1 ? m.substring(0, idx).trim() : "";
                                        }
                                        visible: text !== ""
                                        font.family: "D-DIN"; font.pixelSize: 11; font.bold: false;
                                        color: (backend && backend.theme === "dark") ? "#cccccc" : "#666666"
                                        width: parent.width
                                        wrapMode: Text.Wrap
                                    }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf0ac"; font.family: "Font Awesome 5 Free"; font.pixelSize: 14; color: "#999999"; width: 20; horizontalAlignment: Text.AlignHCenter }
                                    Text { text: "Orbit: " + ((model && model.orbit) ? model.orbit : ""); font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf3c5"; font.family: "Font Awesome 5 Free"; font.pixelSize: 14; color: "#999999"; width: 20; horizontalAlignment: Text.AlignHCenter }
                                    Text { text: "Pad: " + ((model && model.pad) ? model.pad : ""); font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; color: "#999999" }
                                }
                                Row { spacing: 5; visible: !!(model && model.landingType)
                                    Text { text: "\uf5af"; font.family: "Font Awesome 5 Free"; font.pixelSize: 14; color: "#999999"; width: 20; horizontalAlignment: Text.AlignHCenter }
                                    Text { text: "Landing: " + ((model && model.landingType) ? model.landingType : ""); font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf017"; font.family: "Font Awesome 5 Free"; font.pixelSize: 14; color: "#999999"; width: 20; horizontalAlignment: Text.AlignHCenter }
                                    Text { 
                                        text: ((model && model.localTime && backend) ? model.localTime + " " + backend.timezoneAbbrev : "TBD") + " / " + 
                                              ((model && model.date) ? model.date : "") + ((model && model.time) ? (" " + model.time) : "") + " UTC"
                                        font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; color: "#999999" 
                                    }
                                }
                            }

                            Rectangle {
                                id: statusPill
                                width: statusText.implicitWidth + 16
                                height: 18
                                color: root.getStatusColor(model ? model.status : "")
                                radius: 10
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.margins: 5
                                visible: !!(model && !model.isGroup)
                                Text {
                                    id: statusText
                                    text: ((model && model.status) ? model.status : "")
                                    font.pixelSize: 13
                                    font.bold: true
                                    color: "white"
                                    anchors.centerIn: parent
                                }
                            }

                            // Click handler for launch selection
                            MouseArea {
                                anchors.fill: parent
                                enabled: !!(model && !model.isGroup)
                                onClicked: {
                                    if (model && !model.isGroup) {
                                        // Load trajectory for this specific launch
                                        backend.loadLaunchTrajectory(model.mission, model.pad, model.orbit, model.landingType || "")
                                        
                                        // Prefer X video URL if available for SpaceX launches, fallback to converted YouTube URL
                                        var xUrl = model.xVideoUrl || "";
                                        var convertedXUrl = backend.getConvertedVideoUrl(xUrl);
                                        var convertedUrl = backend.getConvertedVideoUrl(model.videoUrl || "");
                                        
                                        if (xUrl !== "") {
                                            console.log("Launch selected: Using X.com stream:", convertedXUrl)
                                            root.currentVideoUrl = convertedXUrl
                                        } else if (convertedUrl !== "") {
                                            console.log("Launch selected: Using YouTube embed:", convertedUrl)
                                            root.currentVideoUrl = convertedUrl;
                                        } else {
                                            // Clear the video view if no video is available for this launch
                                            console.log("Launch selected: No video available")
                                            root.currentVideoUrl = "about:blank";
                                        }
                                        
                                        console.log("Launch selected:", model.mission, "from", model.pad, "video:", model.videoUrl || "none")
                                    }
                                }
                                cursorShape: Qt.PointingHandCursor
                            }

                        }
                    }

                        // View 1: Swipeable Calendar View (Loaded Lazily)
                        Loader {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            active: launchCard.launchViewMode === "calendar" || launchCard.calendarLoaded
                            onActiveChanged: if (active) launchCard.calendarLoaded = true
                            asynchronous: false // Synchronous to ensure properties like currentIndex are applied before render
                            sourceComponent: Item {
                            
                            id: calendarViewItem
                            property var launchesMapping: backend.launchesByDate
                            property var todayDateString: Qt.formatDate(new Date(), "yyyy-MM-dd")
                            property var currentMonth: new Date()
                            
                            property var popupLaunches: []
                            property string popupDateString: ""
                            
                            property bool staggeredLoadActive: false
                            property Item hoveredCell: null
                            property int hoveredLaunchesCount: 0
                            
                            Timer {
                                id: staggeredTimer
                                interval: 400
                                running: true
                                onTriggered: calendarViewItem.staggeredLoadActive = true
                            }
                            
                            ToolTip {
                                id: sharedToolTip
                                visible: calendarViewItem.hoveredCell !== null
                                text: calendarViewItem.hoveredLaunchesCount > 0 ? (calendarViewItem.hoveredLaunchesCount + " Launch" + (calendarViewItem.hoveredLaunchesCount > 1 ? "es" : "")) : ""
                                parent: calendarViewItem.hoveredCell
                                delay: 500
                            }

                            Component {
                                id: monthGridComponent
                                GridLayout {
                                    id: grid
                                    property date pageDate
                                    property int daysInMonth
                                    property int startDayOfWeek
                                    
                                    property var gridData: {
                                        if (!pageDate || isNaN(pageDate.getTime())) return [];
                                        var data = [];
                                        var year = pageDate.getFullYear();
                                        var month = pageDate.getMonth();
                                        for (var i = 0; i < 42; i++) {
                                            var dayNum = i - startDayOfWeek + 1;
                                            var isCurrent = dayNum > 0 && dayNum <= daysInMonth;
                                            var d = new Date(year, month, dayNum);
                                            data.push({
                                                day: d.getDate(),
                                                dateString: isCurrent ? Qt.formatDate(d, "yyyy-MM-dd") : "",
                                                isCurrentMonth: isCurrent,
                                                fullDate: d
                                            });
                                        }
                                        return data;
                                    }

                                    anchors.fill: parent
                                    columns: 7
                                    rows: 6
                                    rowSpacing: 2
                                    columnSpacing: 2
                                    
                                    Repeater {
                                        model: grid.gridData
                                        
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            
                                            property bool isCurrentMonth: modelData.isCurrentMonth
                                            property string dateString: modelData.dateString
                                            
                                            color: "transparent"
                                            
                                            // Check for launches (optimized via backend mapping)
                                            property var dayLaunches: (isCurrentMonth && calendarViewItem.launchesMapping) ? 
                                                                      (calendarViewItem.launchesMapping[dateString] || []) : []
                                            
                                            // Selection/Highlight
                                            Rectangle {
                                                anchors.centerIn: parent
                                                width: Math.min(parent.width, parent.height) - 4
                                                height: width
                                                radius: width/2
                                                color: {
                                                    if (dayLaunches.length > 0) {
                                                        return root.getStatusColor(dayLaunches[0].status)
                                                    }
                                                    // Today highlight
                                                    if (isCurrentMonth && dateString === calendarViewItem.todayDateString) return backend.theme === "dark" ? "#444" : "#ddd"
                                                    return "transparent"
                                                }
                                                opacity: dayLaunches.length > 0 ? 0.2 : 1.0
                                                
                                                border.color: dayLaunches.length > 0 ? root.getStatusColor(dayLaunches[0].status) : "transparent"
                                                border.width: dayLaunches.length > 0 ? 1 : 0
                                            }

                                            // Inner Dots for launches
                                            Row {
                                                anchors.centerIn: parent
                                                anchors.verticalCenterOffset: 6
                                                spacing: 2
                                                visible: dayLaunches.length > 0
                                                
                                                Repeater {
                                                    model: Math.min(dayLaunches.length, 3) // Cap at 3
                                                    Rectangle {
                                                        width: 4; height: 4; radius: 2
                                                        color: root.getStatusColor(dayLaunches[index].status)
                                                    }
                                                }
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                anchors.verticalCenterOffset: -2
                                                text: modelData.day
                                                font.pixelSize: 12
                                                color: isCurrentMonth ? 
                                                       (backend.theme === "dark" ? "white" : "black") : 
                                                       (backend.theme === "dark" ? "#555555" : "#aaaaaa")
                                                font.bold: isCurrentMonth && dayLaunches.length > 0
                                            }
                                            
                                            MouseArea {
                                                id: ma
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: dayLaunches.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                onEntered: {
                                                    if (dayLaunches.length > 0) {
                                                        calendarViewItem.hoveredLaunchesCount = dayLaunches.length
                                                        calendarViewItem.hoveredCell = ma
                                                    }
                                                }
                                                onExited: calendarViewItem.hoveredCell = null
                                                onClicked: {
                                                    if (dayLaunches.length > 0) {
                                                        calendarViewItem.showPopup(dayLaunches, modelData.fullDate)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            function getMonthName(date) {
                                if (!date || isNaN(date.getTime())) return "";
                                return date.toLocaleDateString(Qt.locale(), "MMMM yyyy")
                            }

                            function showPopup(launches, dateVal) {
                                popupLaunches = launches;
                                popupDateString = Qt.formatDate(dateVal, "MMM d, yyyy");
                                dayPopup.open();
                            }

                            Popup {
                                id: dayPopup
                                anchors.centerIn: parent
                                width: Math.min(parent.width * 0.9, 300)
                                height: Math.min(parent.height * 0.8, 400)
                                modal: true
                                focus: true
                                closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                                
                                background: Rectangle {
                                    color: backend.theme === "dark" ? "#181818" : "#ffffff"
                                    radius: 12
                                    border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                                    border.width: 1
                                }
                                
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 2
                                    
                                    Text {
                                        text: calendarViewItem.popupDateString
                                        font.bold: true
                                        font.pixelSize: 14
                                        color: backend.theme === "dark" ? "white" : "black"
                                        Layout.alignment: Qt.AlignHCenter
                                    }
                                    
                                    ListView {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        clip: true
                                        model: calendarViewItem.popupLaunches
                                        interactive: true
                                        boundsBehavior: Flickable.StopAtBounds
                                        flickableDirection: Flickable.VerticalFlick
                                        delegate: Column {
                                            width: parent.width
                                            spacing: 1
                                            padding: 2
                                            
                                            Column {
                                                spacing: 0
                                                width: parent.width
                                                Text { 
                                                    text: {
                                                        var m = modelData.mission;
                                                        var idx = m.indexOf("|");
                                                        return idx !== -1 ? m.substring(idx + 1).trim() : m;
                                                    }
                                                    font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; 
                                                    color: backend.theme === "dark" ? "white" : "black"
                                                    width: parent.width
                                                    wrapMode: Text.Wrap
                                                }
                                                Text { 
                                                    text: {
                                                        var m = modelData.mission;
                                                        var idx = m.indexOf("|");
                                                        return idx !== -1 ? m.substring(0, idx).trim() : "";
                                                    }
                                                    visible: text !== ""
                                                    font.family: "D-DIN"; font.pixelSize: 11; font.bold: false;
                                                    color: (backend && backend.theme === "dark") ? "#cccccc" : "#666666"
                                                    width: parent.width
                                                    wrapMode: Text.Wrap
                                                }
                                            }
                                            Text { 
                                                text: (modelData.localTime && backend ? modelData.localTime + " " + backend.timezoneAbbrev : "TBD") + " / " + 
                                                      (modelData.date ? modelData.date : "") + (modelData.time ? (" " + modelData.time) : "") + " UTC"
                                                font.family: "D-DIN"; font.pixelSize: 14; font.bold: true; color: "#999999" 
                                            }
                                            Row {
                                                spacing: 5
                                                Rectangle {
                                                   width: 10; height: 10; radius: 5
                                                   color: root.getStatusColor(modelData.status)
                                                   anchors.verticalCenter: parent.verticalCenter
                                                }
                                                Text { text: modelData.status; font.bold: true; font.pixelSize: 12; color: root.getStatusColor(modelData.status) }
                                            }
                                            Rectangle { width: parent.width; height: 1; color: "#333333"; opacity: 0.2; visible: index < calendarViewItem.popupLaunches.length - 1 }
                                        }
                                    }
                                    
                                    Button {
                                        text: "Close"
                                        Layout.alignment: Qt.AlignHCenter
                                        onClicked: dayPopup.close()
                                    }
                                }
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 0

                                // Month Header
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 30
                                    color: "transparent"
                                    
                                    RowLayout {
                                        anchors.fill: parent
                                        
                                        // Previous Month
                                        Text {
                                            text: "\uf053"
                                            font.family: "Font Awesome 5 Free"
                                            color: backend.theme === "dark" ? "#cccccc" : "#666666"
                                            font.pixelSize: 12
                                            Layout.preferredWidth: 30
                                            horizontalAlignment: Text.AlignHCenter
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: calendarSwipe.decrementCurrentIndex()
                                            }
                                        }

                                        Text {
                                            text: calendarViewItem.getMonthName(calendarViewItem.currentMonth)
                                            font.bold: true
                                            font.pixelSize: 18
                                            color: backend.theme === "dark" ? "white" : "black"
                                            Layout.fillWidth: true
                                            horizontalAlignment: Text.AlignHCenter
                                        }

                                        // Next Month
                                        Text {
                                            text: "\uf054"
                                            font.family: "Font Awesome 5 Free"
                                            color: backend.theme === "dark" ? "#cccccc" : "#666666"
                                            font.pixelSize: 12
                                            Layout.preferredWidth: 30
                                            horizontalAlignment: Text.AlignHCenter
                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: calendarSwipe.incrementCurrentIndex()
                                            }
                                        }
                                    }
                                }
                                
                                // Days of Week Header
                                Row {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 20
                                    Layout.leftMargin: 5
                                    Layout.rightMargin: 5
                                    Repeater {
                                        model: ["S", "M", "T", "W", "T", "F", "S"]
                                        Text {
                                            width: parent.width / 7
                                            text: modelData
                                            font.pixelSize: 10
                                            color: backend.theme === "dark" ? "#999999" : "#666666"
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                    }
                                }

                                // Calendar Swipe View
                                SwipeView {
                                    id: calendarSwipe
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    interactive: true
                                    
                                    // Start a few months back to allow history, but center on "today" logically
                                    // Index 12 will be "current month" (relative offset 0)
                                    currentIndex: 12
                                    
                                    Component.onCompleted: {
                                        // Jump to index 12 without animation on initial load
                                        if (contentItem) {
                                            var oldDuration = contentItem.highlightMoveDuration
                                            contentItem.highlightMoveDuration = 0
                                            currentIndex = 12
                                            contentItem.highlightMoveDuration = oldDuration
                                        }
                                    }
                                    
                                    onCurrentIndexChanged: {
                                        var today = new Date()
                                        var offset = currentIndex - 12
                                        var newDate = new Date(today.getFullYear(), today.getMonth() + offset, 1)
                                        calendarViewItem.currentMonth = newDate
                                    }

                                    Repeater {
                                        model: 25 // Show range of +/- 12 months
                                        
                                        Item {
                                            id: monthPage
                                            property int monthOffset: index - 12
                                            
                                            Loader {
                                                anchors.fill: parent
                                                anchors.margins: 5
                                                active: {
                                                    if (index === calendarSwipe.currentIndex) return true;
                                                    return calendarViewItem.staggeredLoadActive && Math.abs(index - calendarSwipe.currentIndex) <= 1;
                                                }
                                                asynchronous: true
                                                sourceComponent: monthGridComponent
                                                
                                                // Pass properties to the loaded item
                                                onLoaded: {
                                                    var d = new Date()
                                                    var pageDate = new Date(d.getFullYear(), d.getMonth() + monthOffset, 1)
                                                    item.pageDate = pageDate
                                                    item.daysInMonth = new Date(pageDate.getFullYear(), pageDate.getMonth() + 1, 0).getDate()
                                                    item.startDayOfWeek = pageDate.getDay()
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        }
                        
                        // View 2: Launch Trends Chart (Moved from Plot Card)
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            
                            ChartItem {
                                anchors.fill: parent
                                anchors.margins: 10
                                chartType: backend ? backend.chartType : "line"
                                viewMode: backend ? backend.chartViewMode : "actual"
                                series: backend ? backend.launchTrendsSeries : []
                                months: backend ? backend.launchTrendsMonths : []
                                maxValue: backend ? backend.launchTrendsMaxValue : 10
                                theme: backend ? backend.theme : "dark"
                                
                                opacity: launchCard.launchViewMode === "chart" ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: 250 } }
                            }
                        }
                    } // End StackLayout

                    // Launch view buttons overlay (Windy style)
                    Rectangle {
                        id: launchButtonsOverlay
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 10
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: launchPills.implicitWidth + 20
                        height: 34
                        color: backend.theme === "dark" ? "#cc181818" : "#ccf5f5f5"
                        radius: 17
                        z: 10
                        visible: !!backend
                        opacity: 1.0 - backgroundWindy.progress

                        RowLayout {
                            id: launchPills
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "upcoming", "icon": "\uf135", "tooltip": "Upcoming Launches"},
                                    {"type": "past", "icon": "\uf1da", "tooltip": "Past Launches"},
                                    {"type": "calendar", "icon": "\uf073", "tooltip": "Calendar View"},
                                    {"type": "chart", "icon": "\uf201", "tooltip": "Launch Trends"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    // Highlight if:
                                    // 1. We are in 'calendar' mode and this button is the calendar button
                                    // 2. We are in 'chart' mode and this button is the chart button
                                    // 3. We are in 'list' mode and this button matches backend.eventType (upcoming/past)
                                    property bool isActive: {
                                        if (modelData.type === "calendar") return launchCard.launchViewMode === "calendar"
                                        if (modelData.type === "chart") return launchCard.launchViewMode === "chart"
                                        return launchCard.launchViewMode === "list" && backend.eventType === modelData.type
                                    }
                                    
                                    color: isActive ?
                                           (backend.theme === "dark" ? "#303030" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#181818" : "#f5f5f5")
                                    radius: 14
                                    border.color: isActive ?
                                                 (backend.theme === "dark" ? "#3a3a3a" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                                    border.width: isActive ? 2 : 1
                                    
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.icon
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor

                                        onClicked: {
                                            if (modelData.type === "calendar") {
                                                launchCard.launchViewMode = "calendar"
                                            } else if (modelData.type === "chart") {
                                                launchCard.launchViewMode = "chart"
                                            } else {
                                                launchCard.launchViewMode = "list"
                                                backend.eventType = modelData.type
                                            }
                                        }
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Column 4: Videos or Next Race Location
            Rectangle {
                id: videoCard
                // Original width logic: 25% of screen when not expanded, 50% when expanded.
                // We use fixed width for dragging, but it must account for Windy expansion.
                readonly property real baseWidth: root.width / 4
                readonly property real baseHeight: root.height / 4
                readonly property real currentMinWidth: root.height > root.width ? baseHeight * (1.0 - backgroundWindy.progress) : baseWidth * (1.0 - backgroundWindy.progress)
                readonly property real currentMaxWidth: root.height > root.width ? Math.min(490, (root.height / 2) * (1.0 - backgroundWindy.progress)) : Math.min(490, (root.width / 2) * (1.0 - backgroundWindy.progress))

                width: (root.height > root.width) ? parent.width : (videoCard.isDragging ? videoCard.manualWidth : (currentMinWidth + videoCard.videoExpansionFactor * (currentMaxWidth - currentMinWidth)))
                height: (root.height > root.width) ? (videoCard.isDragging ? videoCard.manualWidth : (currentMinWidth + videoCard.videoExpansionFactor * (currentMaxWidth - currentMinWidth))) : parent.height
                Layout.fillWidth: root.height > root.width
                Layout.fillHeight: root.height <= root.width
                Layout.preferredWidth: (root.height > root.width) ? -1 : width
                Layout.preferredHeight: (root.height > root.width) ? 1.0 : -1
                color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                radius: 8
                clip: true
                opacity: 1.0 - backgroundWindy.progress
                visible: opacity > 0

                property bool isDragging: false
                property real manualWidth: currentMinWidth
                property real videoExpansionFactor: 0.0

                // Reset expansion on orientation change
                property bool isVerticalOrientation: root.height > root.width
                onIsVerticalOrientationChanged: {
                    videoExpansionFactor = 0.0
                }

                readonly property real progress: Math.max(0, Math.min(1, (width - currentMinWidth) / Math.max(1, currentMaxWidth - currentMinWidth)))

            Behavior on width { 
                enabled: !videoCard.isDragging
                NumberAnimation { 
                    id: videoWidthAnimation
                    duration: 400 
                    easing.type: Easing.OutCubic
                } 
            }

                Item {
                    anchors.fill: parent

                    WebEngineProfile {
                        id: youtubeProfile
                        storageName: "youtube_profile"
                        httpUserAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        httpAcceptLanguage: "en-US,en"
                        // Allow sending Referer headers for YouTube embeds
                        offTheRecord: false
                        persistentCookiesPolicy: WebEngineProfile.AllowPersistentCookies
                        httpCacheType: WebEngineProfile.DiskHttpCache
                    }

                    // Rounded-corner container to ensure YouTube/map view corners are clipped
                    Rectangle {
                        anchors.fill: parent
                        radius: 8
                        color: backend.theme === "dark" ? "#111111" : "#f8f8f8"
                        clip: true
                        // Performance: Enable layer during animations to keep it smooth
                        layer.enabled: videoCard.isDragging || videoWidthAnimation.running
                        layer.smooth: true

                        // Mask effect removed to avoid dependency on Qt5Compat.GraphicalEffects

                        WebEngineView {
                            id: youtubeView
                            profile: youtubeProfile
                            anchors.fill: parent
                            layer.enabled: videoCard.isDragging || (videoWidthAnimation && videoWidthAnimation.running)
                            layer.smooth: true
                            // layer.renderTarget: Item.FramebufferObject
                            layer.textureSize: (videoCard.isDragging || (videoWidthAnimation && videoWidthAnimation.running))
                                                ? Qt.size(videoCard.currentMaxWidth > 0 ? videoCard.currentMaxWidth : root.width / 2, height > 0 ? height : root.height)
                                                : Qt.size(width > 0 ? width : 1, height > 0 ? height : 1)
                            
                            // MouseArea for expansion gesture
                            MouseArea {
                                anchors.left: (root.height > root.width) ? parent.left : parent.left
                                anchors.right: (root.height > root.width) ? parent.right : undefined
                                anchors.top: parent.top
                                anchors.bottom: (root.height > root.width) ? undefined : parent.bottom
                                width: (root.height > root.width) ? undefined : 40
                                height: (root.height > root.width) ? 40 : undefined
                                z: 10
                                
                                property real startPos: 0
                                property real initialSize: 0
                                
                                onPressed: (mouse) => {
                                    startPos = (root.height > root.width) ? mapToItem(safeArea, mouse.x, mouse.y).y : mapToItem(safeArea, mouse.x, mouse.y).x
                                    initialSize = (root.height > root.width) ? videoCard.height : videoCard.width
                                    videoCard.manualWidth = initialSize
                                    videoCard.isDragging = true
                                }
                                
                                onPositionChanged: (mouse) => {
                                    if (videoCard.isDragging) {
                                        var currentPos = (root.height > root.width) ? mapToItem(safeArea, mouse.x, mouse.y).y : mapToItem(safeArea, mouse.x, mouse.y).x
                                        var delta = (root.height > root.width) ? (currentPos - startPos) : (startPos - currentPos) 
                                        videoCard.manualWidth = Math.max(videoCard.currentMinWidth, Math.min(videoCard.currentMaxWidth, initialSize + delta))
                                    }
                                }
                                
                                onReleased: (mouse) => {
                                    if (videoCard.isDragging) {
                                        var p = videoCard.progress
                                        var threshold = 0.12
                                        if (videoCard.videoExpansionFactor === 0.0) {
                                            videoCard.videoExpansionFactor = (p > threshold) ? 1.0 : 0.0
                                        } else {
                                            videoCard.videoExpansionFactor = (p < (1.0 - threshold)) ? 0.0 : 1.0
                                        }
                                        videoCard.isDragging = false
                                    }
                                }
                                
                                onCanceled: {
                                    if (videoCard.isDragging) {
                                        videoCard.isDragging = false
                                    }
                                }
                            }

                            backgroundColor: "black"
                            onBackgroundColorChanged: {
                                if (typeof root !== 'undefined') root._injectRoundedCorners(youtubeView, 8)
                            }
                            url: root.currentVideoUrl
                            onUrlChanged: {
                                if (url.toString() === "") {
                                    youtubeView.loadHtml("<html><body style='margin:0;padding:0;background:black;'></body></html>")
                                }
                            }

                            settings.webGLEnabled: true
                            settings.accelerated2dCanvasEnabled: true
                            settings.allowRunningInsecureContent: true
                            settings.javascriptEnabled: true
                            settings.localContentCanAccessRemoteUrls: true
                            settings.playbackRequiresUserGesture: false  // Allow autoplay
                            settings.pluginsEnabled: true
                            settings.javascriptCanOpenWindows: false
                            settings.javascriptCanAccessClipboard: false
                            settings.allowWindowActivationFromJavaScript: true
                            onFullScreenRequested: function(request) { request.accept(); root.visibility = Window.FullScreen }
                            onLoadingChanged: function(loadRequest) {
                                if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                    console.log("YouTube WebEngineView load failed:", loadRequest.errorString);
                                    console.log("Error code:", loadRequest.errorCode);
                                    console.log("Error domain:", loadRequest.errorDomain);
                                    
                                    // Handle specific error codes
                                    if (loadRequest.errorCode === 153) {
                                        console.log("ERR_MISSING_REFERER_HEADER detected - YouTube requires proper Referer header for embeds");
                                        console.log("This is a new YouTube policy requiring API client identification");
                                        console.log("Attempting to reload with proper headers...");
                                        
                                        // Auto-retry for Referer header errors
                                        youtubeRetryTimer.restart();
                                    } else if (loadRequest.errorCode === 2) {
                                        console.log("ERR_FAILED - Network or server error. Check your internet connection.");
                                    } else if (loadRequest.errorCode === 3) {
                                        console.log("ERR_ABORTED - Request was aborted. This may be due to page navigation.");
                                    } else if (loadRequest.errorCode === 6) {
                                        console.log("ERR_FILE_NOT_FOUND - Video not found. The YouTube video may have been removed.");
                                    } else if (loadRequest.errorCode === -3) {
                                        console.log("ERR_ABORTED_BY_USER - Loading was cancelled.");
                                    } else {
                                        console.log("Unknown error code:", loadRequest.errorCode, "- Check network connectivity and try the reload button.");
                                    }
                                    root.autoFullScreen = false;
                                } else if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                    console.log("YouTube WebEngineView loaded successfully");
                                    // Apply internal page rounding to ensure corners clip
                                    // Use black background for video views to avoid white/gray corner artifacts
                                    if (typeof root !== 'undefined') root._injectRoundedCorners(youtubeView, 8)
                                    
                                    // Automatically trigger fullscreen if requested by a UI action (like pressing the LIVE button)
                                    // We only apply this to X.com (Twitter) streams as requested.
                                    var isX = loadRequest.url.toString().indexOf("x.com") !== -1 || 
                                              loadRequest.url.toString().indexOf("twitter.com") !== -1 ||
                                              loadRequest.url.toString().indexOf("platform.twitter.com") !== -1;
                                    if (root.autoFullScreen && isX) {
                                        // X.com needs a bit of time to initialize its player, so we retry a few times.
                                        youtubeView.runJavaScript("(function(){" +
                                            "var attempts = 0;" +
                                            "var tryFS = function() {" +
                                            "  var el = document.querySelector('video') || document.querySelector('iframe') || document.documentElement;" +
                                            "  if(el && el.requestFullscreen) {" +
                                            "    el.requestFullscreen().catch(function(e){" +
                                            "      if(++attempts < 10) setTimeout(tryFS, 1000);" +
                                            "      else console.log('Auto-fullscreen failed:', e);" +
                                            "    });" +
                                            "  } else if (el && el.webkitRequestFullscreen) {" +
                                            "    el.webkitRequestFullscreen();" +
                                            "  } else if (++attempts < 10) {" +
                                            "    setTimeout(tryFS, 1000);" +
                                            "  }" +
                                            "};" +
                                            "tryFS();" +
                                        "})()");
                                    }
                                    root.autoFullScreen = false;
                                    
                                    youtubeRetryTimer.stop(); // Stop any pending retries
                                }
                            }

                            // Staggered global reload for YouTube view
                            Connections {
                                target: backend
                                function onReloadWebContent() {
                                    globalReloadTimer.start()
                                }
                            }
                            Timer {
                                id: globalReloadTimer
                                interval: 2500
                                repeat: false
                                onTriggered: {
                                    youtubeView.reload()
                                    console.log("YouTube/map view reloaded (staggered)")
                                }
                            }

                            // Auto-retry timer for content length mismatch
                            Timer {
                                id: youtubeRetryTimer
                                interval: 3000 // 3 seconds
                                repeat: false
                                onTriggered: {
                                    console.log("Attempting to reload YouTube video after error 153...");
                                    youtubeView.reload();
                                }
                            }
                        }

                        // Show "No Video" when there's no video URL
                        Text {
                            anchors.centerIn: parent
                            text: "No Video"
                            font.pixelSize: 24
                            font.bold: true
                            color: backend.theme === "dark" ? "#cccccc" : "#666666"
                            visible: !root.currentVideoUrl || root.currentVideoUrl === "" || root.currentVideoUrl === "about:blank"
                            z: 1
                        }

                        // Overlay for quick-action buttons floating on top of the video
                        Rectangle {
                            id: youtubeButtonsOverlay
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 10
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: youtubePills.implicitWidth + 20
                            height: 34
                            color: backend.theme === "dark" ? "#cc181818" : "#ccf5f5f5"
                            radius: 17
                            z: 2
                            opacity: 1.0 - backgroundWindy.progress
                            visible: backend && opacity > 0
                            layer.enabled: backgroundWindy.isDragging || widthAnimation.running || videoCard.isDragging || videoWidthAnimation.running
                            layer.smooth: true

                            RowLayout {
                                id: youtubePills
                                anchors.centerIn: parent
                                spacing: 6

                                // Starship playlist (current YouTube URL)
                                Rectangle {
                                    id: starshipBtn
                                    // Match highlight logic used by Windy/plot pills: compare as strings to avoid url vs string type mismatch
                                    property bool selected: (backend && backend.videoUrl) ? (String(root.currentVideoUrl) === String(backend.videoUrl)) : false
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    radius: 14
                                    color: selected ? (backend.theme === "dark" ? "#303030" : "#e0e0e0") : (backend.theme === "dark" ? "#181818" : "#f5f5f5")
                                    border.color: selected ? (backend.theme === "dark" ? "#3a3a3a" : "#c0c0c0") : (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                                    border.width: selected ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uf135"   // FontAwesome rocket icon to match launch list
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (backend && backend.videoUrl) {
                                                // Ensure currentVideoUrl updates as a string URL to keep comparison consistent
                                                root.currentVideoUrl = String(backend.videoUrl)
                                            } else {
                                                console.log("backend.videoUrl is not defined or empty")
                                            }
                                        }
                                    }

                                    ToolTip { text: "Starship Playlist"; delay: 500 }
                                }

                                // NSF Starbase Live stream
                                Rectangle {
                                    id: nsfBtn
                                    // Load via local wrapper page to match existing youtube_embed.html approach
                                    property string nsfStarbaseUrl: "http://localhost:" + backend.httpPort + "/youtube_embed_nsf.html"
                                    // Compare as strings to match Windy/plot highlight logic reliably
                                    property bool selected: String(root.currentVideoUrl) === nsfStarbaseUrl
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    radius: 14
                                    color: selected ? (backend.theme === "dark" ? "#303030" : "#e0e0e0") : (backend.theme === "dark" ? "#181818" : "#f5f5f5")
                                    border.color: selected ? (backend.theme === "dark" ? "#3a3a3a" : "#c0c0c0") : (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                                    border.width: selected ? 2 : 1

                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Behavior on border.color { ColorAnimation { duration: 200 } }
                                    Behavior on border.width { NumberAnimation { duration: 200 } }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uf519"  // FontAwesome broadcast-tower
                                        font.pixelSize: 14
                                        font.family: "Font Awesome 5 Free"
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            // Assign as string for consistent comparisons/updates
                                            root.currentVideoUrl = nsfBtn.nsfStarbaseUrl
                                        }
                                    }

                                    ToolTip { text: "NSF Starbase Live"; delay: 500 }
                                }

                                // Live button for current launch livestream (X.com)
                                Rectangle {
                                    id: liveBtn
                                    property bool selected: (backend.isNearLaunch && backend.liveLaunchUrl !== "" && String(root.currentVideoUrl) === backend.liveLaunchUrl)
                                    property bool active: backend.isNearLaunch && backend.liveLaunchUrl !== ""
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    radius: 14
                                    color: selected ? "#FF0000" : (active ? "#CC0000" : (backend.theme === "dark" ? "#181818" : "#f0f0f0"))
                                    border.color: selected ? "white" : (active ? "transparent" : (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"))
                                    border.width: selected ? 2 : 1
                                    opacity: active ? 1.0 : 0.6

                                    // Automatically switch to the live feed when the button becomes
                                    // active, and restore the previous feed when the launch ends.
                                    onActiveChanged: {
                                        if (active) {
                                            // Live button just became active — save the current feed
                                            // and switch to the live stream automatically.
                                            if (String(root.currentVideoUrl) !== String(backend.liveLaunchUrl)) {
                                                root._preLiveVideoUrl = root.currentVideoUrl
                                                root._autoSwitchedToLive = true
                                                root.currentVideoUrl = backend.liveLaunchUrl
                                                root.autoFullScreen = true
                                            }
                                        } else {
                                            // Live button became inactive (launch over) — restore the
                                            // feed that was showing before the automatic switch.
                                            if (root._autoSwitchedToLive && root._preLiveVideoUrl.toString() !== "") {
                                                root.currentVideoUrl = root._preLiveVideoUrl
                                            }
                                            root._preLiveVideoUrl = ""
                                            root._autoSwitchedToLive = false
                                            root.autoFullScreen = false
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "LIVE"
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: "white"
                                    }
                                    MouseArea { 
                                        anchors.fill: parent
                                        cursorShape: liveBtn.active ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: {
                                            if (liveBtn.active) {
                                                var isSame = (String(root.currentVideoUrl) === String(backend.liveLaunchUrl));
                                                root.currentVideoUrl = backend.liveLaunchUrl
                                                if (isSame) {
                                                    // If already on the live URL, just trigger fullscreen again with a few retries
                                                    youtubeView.runJavaScript("(function(){" +
                                                        "var attempts = 0;" +
                                                        "var tryFS = function() {" +
                                                        "  var el = document.querySelector('video') || document.querySelector('iframe') || document.documentElement;" +
                                                        "  if(el && el.requestFullscreen) {" +
                                                        "    el.requestFullscreen().catch(function(e){" +
                                                        "      if(++attempts < 5) setTimeout(tryFS, 1000);" +
                                                        "      else console.log('Manual auto-fullscreen failed:', e);" +
                                                        "    });" +
                                                        "  } else if (el && el.webkitRequestFullscreen) {" +
                                                        "    el.webkitRequestFullscreen();" +
                                                        "  } else if (++attempts < 5) {" +
                                                        "    setTimeout(tryFS, 1000);" +
                                                        "  }" +
                                                        "};" +
                                                        "tryFS();" +
                                                    "})()");
                                                } else {
                                                    root.autoFullScreen = true
                                                }
                                            }
                                        }
                                    }
                                    ToolTip { text: liveBtn.active ? "Switch to current launch livestream (X.com)" : "No live stream available"; delay: 400 }
                                }
                            }
                        }
                    }
                }
            }
        }

            // Bottom bar - FIXED VERSION
        Rectangle {
            id: bottomBar
            parent: root.contentItem
            anchors.left: parent.left
            anchors.leftMargin: 5
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 5
            height: 30
            color: "transparent"
            z: 3000

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                // Fixed padding to reflect calibrated right-edge inset (10 base + 6 measured = 16)
                anchors.rightMargin: 16
                spacing: 8

                // Left pill (time and weather) - FIXED WIDTH
                Rectangle {
                    id: weatherPill
                    Layout.preferredWidth: 300
                    Layout.maximumWidth: 300
                    height: 28
                    radius: 14
                    color: "transparent"
                    clip: false

                    // Fading background for the weather pill
                    Rectangle {
                        id: weatherPillBackground
                        anchors.fill: parent
                        radius: 14
                        color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                        border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1
                        z: 0
                        opacity: 1.0 - Math.min(1.0, weatherTray.height / 56.0)
                    }

                    RowLayout {
                        anchors.centerIn: parent
                        anchors.horizontalCenterOffset: 0
                        spacing: 0
                        opacity: 1.0 - Math.min(1.0, weatherTray.height / 56.0)

                        Item {
                            Layout.preferredWidth: 14
                            Layout.preferredHeight: 14
                            Layout.alignment: Qt.AlignVCenter
                            Layout.rightMargin: 8 // Space between indicator and time

                            Canvas {
                                id: weatherProgressRing
                                anchors.fill: parent
                                antialiasing: true

                                property real progress: {
                                    if (!backend || !backend.currentTime) return 0.0;
                                    var timeParts = backend.currentTime.split(':');
                                    if (timeParts.length < 3) return 0.0;
                                    var seconds = parseInt(timeParts[2]);
                                    return (seconds % 60) / 60.0;
                                }
                                onProgressChanged: requestPaint()

                                onPaint: {
                                    var ctx = getContext("2d");
                                    ctx.reset();

                                    var centerX = width / 2;
                                    var centerY = height / 2;
                                    var radius = Math.min(width, height) / 2 - 1;

                                    // Draw background ring (optional, faint)
                                    ctx.beginPath();
                                    ctx.strokeStyle = (backend && backend.theme === "dark") ? "#33ffffff" : "#33000000";
                                    ctx.lineWidth = 1.5;
                                    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
                                    ctx.stroke();

                                    // Draw progress arc
                                    ctx.beginPath();
                                    ctx.strokeStyle = weatherIndicator.color;
                                    ctx.lineWidth = 1.5;
                                    ctx.lineCap = "round";
                                    // Start from top (-90 degrees)
                                    var startAngle = -Math.PI / 2;
                                    var endAngle = startAngle + (2 * Math.PI * progress);
                                    ctx.arc(centerX, centerY, radius, startAngle, endAngle);
                                    ctx.stroke();
                                }
                            }

                            Rectangle {
                                id: weatherIndicator
                                anchors.centerIn: parent
                                width: 6
                                height: 6
                                radius: 3
                                color: {
                                    var weather = backend ? backend.weather : null;
                                    if (weather && weather.is_live_wind) {
                                        return "#4CAF50"; // Green (Live)
                                    }
                                    return "#F44336"; // Red (METAR)
                                }
                                visible: {
                                    var weather = backend ? backend.weather : null;
                                    return weather && weather.temperature_f !== undefined;
                                }
                            }
                        }
                        Text {
                            text: backend ? backend.currentTime : "--:--:--"
                            color: (backend && backend.theme === "dark") ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            font.bold: true
                            font.styleName: "Regular"
                            // Use tabular numbers to prevent jitter as the clock ticks
                            font.features: { "tnum": 1 }
                            Layout.alignment: Qt.AlignVCenter
                            Layout.preferredWidth: 58
                            Layout.rightMargin: 0 // Space between time and gauge
                            horizontalAlignment: Text.AlignLeft
                        }
                        // Graphical Wind Indicator
                        Item {
                            id: graphicalWindIndicator
                            width: 120
                            height: 28
                            Layout.alignment: Qt.AlignVCenter
                            visible: {
                                var weather = backend ? backend.weather : null;
                                return weather && weather.temperature_f !== undefined;
                            }

                            property real sustainedWind: {
                                var weather = backend ? backend.weather : null;
                                return weather ? (weather.wind_speed_kts || 0) : 0;
                            }
                            property real gustSpeed: {
                                var weather = backend ? backend.weather : null;
                                return weather ? (weather.wind_gusts_kts || 0) : 0;
                            }
                            property real maxScale: {
                                var baseMax = Math.max(sustainedWind, gustSpeed);
                                if (baseMax < 5) return 5;
                                return Math.ceil((baseMax + 0.1) / 5) * 5;
                            }

                            // Background bar
                            Rectangle {
                                x: 0; y: 4; width: 100; height: 10
                                radius: 5
                                color: (backend && backend.theme === "dark") ? "#333333" : "#E0E0E0"
                            }

                            // Sustained wind fill
                            Rectangle {
                                id: sustainedFill
                                x: 0; y: 4
                                height: 10
                                radius: 5
                                width: Math.min(100, (graphicalWindIndicator.sustainedWind / graphicalWindIndicator.maxScale) * 100)
                                visible: width > 0
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0.0; color: "#26A69A" }
                                    GradientStop { position: 1.0; color: "#FFB917" }
                                }
                            }

                            // Vertical gust bar
                            Rectangle {
                                x: 0 + Math.min(100, (graphicalWindIndicator.gustSpeed / graphicalWindIndicator.maxScale) * 100) - 1.5
                                y: 4.5
                                width: 3
                                height: 9
                                color: {
                                    var ratio = graphicalWindIndicator.gustSpeed / graphicalWindIndicator.maxScale;
                                    if (ratio < 0.33) return "#26A69A"; // Low wind color
                                    if (ratio < 0.66) return "#FFB917"; // Medium wind color
                                    return "#FB8A10"; // High wind (gust) color
                                }
                                visible: graphicalWindIndicator.gustSpeed > 0
                            }

                            // Scale labels and ticks
                            Repeater {
                                model: {
                                    var count = 4;
                                    var step = graphicalWindIndicator.maxScale / (count - 1);
                                    var labels = [];
                                    for (var i = 0; i < count; i++) {
                                        labels.push(Math.round(step * i));
                                    }
                                    return labels;
                                }
                                Item {
                                    property real xPos: 0 + (modelData / graphicalWindIndicator.maxScale) * 100
                                    
                                    // Scale labels
                                    Text {
                                        x: parent.xPos - width/2
                                        y: 14
                                        text: modelData
                                        font.pixelSize: 10
                                        font.family: "D-DIN"
                                        color: (backend && backend.theme === "dark") ? "#AAAAAA" : "#666666"
                                    }
                                }
                            }

                            // "kts" label aligned with bar
                            Text {
                                x: 98
                                y: 4
                                width: 18
                                height: 10
                                text: "kts"
                                font.pixelSize: 10
                                font.family: "D-DIN"
                                color: (backend && backend.theme === "dark") ? "#AAAAAA" : "#555555"
                                horizontalAlignment: Text.AlignRight
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        // Compass Rose for Wind Direction
                        Item {
                            width: 24
                            height: 24
                            Layout.alignment: Qt.AlignVCenter
                            Layout.leftMargin: 4
                            Layout.rightMargin: 4
                            visible: {
                                var weather = backend ? backend.weather : null;
                                return weather && weather.wind_direction_cardinal !== undefined;
                            }

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                color: "transparent"
                                border.color: (backend && backend.theme === "dark") ? "#66ffffff" : "#66000000"
                                border.width: 1

                                // Inner cardinal letter
                                Text {
                                    anchors.centerIn: parent
                                    text: {
                                        var weather = backend ? backend.weather : null;
                                        return weather ? (weather.wind_direction_cardinal || "") : "";
                                    }
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                    font.pixelSize: 10
                                    font.family: "D-DIN"
                                    font.bold: true
                                }

                                // Direction arrow/pointer
                                Item {
                                    anchors.centerIn: parent
                                    width: parent.width
                                    height: parent.height
                                    rotation: {
                                        var weather = backend ? backend.weather : null;
                                        return weather ? (weather.wind_direction || 0) : 0;
                                    }

                                    Text {
                                        anchors.top: parent.top
                                        anchors.topMargin: -2
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: "▼"
                                        font.pixelSize: 8
                                        color: "#4CAF50"
                                    }
                                }
                            }
                        }

                        Text {
                            text: {
                                var weather = backend ? backend.weather : null;
                                if (weather && weather.temperature_f !== undefined) {
                                    return (weather.temperature_f || 0).toFixed(1) + "°F";
                                }
                                return "";
                            }
                            color: (backend && backend.theme === "dark") ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            font.bold: true
                            Layout.alignment: Qt.AlignVCenter
                        }
                    }

                    Popup {
                        id: weatherTray
                        x: 0
                        width: parent.width
                        height: 0
                        y: parent.height - height
                        visible: height > 0
                        closePolicy: Popup.CloseOnPressOutside
                        onClosed: height = 0
                        padding: 0
                        
                        property real expandedHeight: 220
                        property bool isDragging: false
                        opacity: height / expandedHeight
                        
                        Behavior on height {
                            enabled: !weatherTray.isDragging && (weatherListView ? !weatherListView.dragging : true)
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                        
                        background: Item {
                            Rectangle {
                                anchors.fill: parent
                                color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                                radius: 14
                                border.width: 1
                                border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                            }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            spacing: 0
                            
                            // Drag Handle (Top of tray)
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 25
                                color: "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf078"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: 12
                                    color: backend.theme === "dark" ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    
                                    property point startGlobalPos: Qt.point(0, 0)
                                    property real startHeight: 0
                                    property bool isDragging: false
                                    property bool moved: false
                                    
                                    onPressed: {
                                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                        startHeight = weatherTray.height
                                        weatherTray.isDragging = true
                                        moved = false
                                    }
                                    
                                    onPositionChanged: {
                                        if (weatherTray.isDragging && pressed) {
                                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                                            if (Math.abs(deltaY) > 5) moved = true
                                            var newHeight = startHeight - deltaY
                                            newHeight = Math.max(0, Math.min(weatherTray.expandedHeight, newHeight))
                                            weatherTray.height = newHeight
                                        }
                                    }
                                    
                                    onReleased: {
                                        weatherTray.isDragging = false
                                        if (moved) {
                                            var threshold = weatherTray.expandedHeight * 0.2
                                            var closedThreshold = threshold
                                            var openThreshold = weatherTray.expandedHeight - threshold
                                            
                                            if (startHeight < weatherTray.expandedHeight * 0.5) {
                                                if (weatherTray.height > closedThreshold) {
                                                    weatherTray.height = weatherTray.expandedHeight
                                                } else {
                                                    weatherTray.height = 0
                                                }
                                            } else {
                                                if (weatherTray.height < openThreshold) {
                                                    weatherTray.height = 0
                                                } else {
                                                    weatherTray.height = weatherTray.expandedHeight
                                                }
                                            }
                                        }
                                    }
                                    onClicked: {
                                        if (!moved) {
                                            // Tap to close: if mostly open, close it.
                                            if (weatherTray.height > weatherTray.expandedHeight * 0.5) {
                                                weatherTray.height = 0
                                            } else {
                                                weatherTray.open()
                                                weatherTray.height = weatherTray.expandedHeight
                                            }
                                        }
                                    }
                                }
                            }

                            // Forecast Header
                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: backend ? backend.location + " Forecast" : "Forecast"
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 14
                                font.family: "D-DIN"
                                font.bold: true
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                color: backend.theme === "dark" ? "#33ffffff" : "#33000000"
                                Layout.leftMargin: 10
                                Layout.rightMargin: 10
                                Layout.topMargin: 5
                                Layout.bottomMargin: 5
                            }

                            // Forecast List
                            ListView {
                                id: weatherListView
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                Layout.bottomMargin: 6
                                model: backend ? backend.weatherForecastModel : null
                                clip: true
                                interactive: true
                                boundsBehavior: Flickable.StopAtBounds
                                flickableDirection: Flickable.VerticalFlick

                                property real dragStartY: 0

                                DragHandler {
                                    id: weatherListDrag
                                    target: null
                                    xAxis.enabled: false
                                    onActiveChanged: {
                                        if (active) {
                                            if (weatherListView.contentY <= 0) {
                                                weatherTray.isDragging = true
                                                weatherListView.dragStartY = centroid.scenePosition.y
                                            }
                                        } else {
                                            if (weatherTray.isDragging) {
                                                weatherTray.isDragging = false
                                                if (weatherTray.height < weatherTray.expandedHeight) {
                                                    if (weatherTray.height < weatherTray.expandedHeight * 0.8) {
                                                        weatherTray.height = 0
                                                    } else {
                                                        weatherTray.height = weatherTray.expandedHeight
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    onCentroidChanged: {
                                        if (weatherTray.isDragging) {
                                            var delta = centroid.scenePosition.y - weatherListView.dragStartY
                                            if (delta > 0) {
                                                weatherTray.height = Math.max(0, weatherTray.expandedHeight - delta)
                                            } else {
                                                weatherTray.height = weatherTray.expandedHeight
                                            }
                                        } else if (weatherListView.dragging && weatherListView.contentY <= 0 && centroid.scenePosition.y > weatherListView.dragStartY) {
                                            weatherTray.isDragging = true
                                            weatherListView.dragStartY = centroid.scenePosition.y
                                        }
                                    }
                                }
                                delegate: Item {
                                    width: ListView.view ? ListView.view.width : 0
                                    height: 30
                                    RowLayout {
                                        anchors.fill: parent
                                        spacing: 1
                                        Text {
                                            text: model.day
                                            Layout.preferredWidth: 30
                                            color: backend.theme === "dark" ? "#bbffffff" : "#bb000000"
                                            font.pixelSize: 12
                                            font.family: "D-DIN"
                                        }
                                        Text {
                                            text: model.tempLow + " / " + model.tempHigh
                                            Layout.preferredWidth: 60
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 12
                                            font.family: "D-DIN"
                                            font.bold: true
                                        }
                                        
                                        // Sparkline
                                        Canvas {
                                            id: sparkline
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 20
                                            Layout.leftMargin: 1
                                            Layout.rightMargin: 1
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                ctx.clearRect(0, 0, width, height)
                                                
                                                // 1. Draw Temperature Sparkline (Blue)
                                                var points = model.temps
                                                if (points && points.length >= 2) {
                                                    ctx.strokeStyle = backend.theme === "dark" ? "#4fc3f7" : "#0288d1"
                                                    ctx.lineWidth = 1.5
                                                    ctx.setLineDash([]) // Solid line
                                                    ctx.beginPath()
                                                    
                                                    var minTemp = Math.min.apply(Math, points)
                                                    var maxTemp = Math.max.apply(Math, points)
                                                    var range = maxTemp - minTemp
                                                    if (range === 0) range = 1
                                                    
                                                    for (var i = 0; i < points.length; i++) {
                                                        var x = (i / (points.length - 1)) * width
                                                        var y = height - 2 - ((points[i] - minTemp) / range) * (height - 4)
                                                        if (i === 0) ctx.moveTo(x, y)
                                                        else ctx.lineTo(x, y)
                                                    }
                                                    ctx.stroke()
                                                }

                                                // 2. Draw Wind Speed Sparkline (Red Dashed)
                                                var wPoints = model.winds
                                                if (wPoints && wPoints.length >= 2) {
                                                    ctx.strokeStyle = "#ff5252" // Bright red
                                                    ctx.lineWidth = 1.2
                                                    ctx.setLineDash([3, 2]) // Dashed line
                                                    ctx.beginPath()

                                                    var minWind = Math.min.apply(Math, wPoints)
                                                    var maxWind = Math.max.apply(Math, wPoints)
                                                    var wRange = maxWind - minWind
                                                    if (wRange === 0) wRange = 1

                                                    for (var j = 0; j < wPoints.length; j++) {
                                                        var wx = (j / (wPoints.length - 1)) * width
                                                        var wy = height - 2 - ((wPoints[j] - minWind) / wRange) * (height - 4)
                                                        if (j === 0) ctx.moveTo(wx, wy)
                                                        else ctx.lineTo(wx, wy)
                                                    }
                                                    ctx.stroke()
                                                    ctx.setLineDash([]) // Reset for next paint
                                                }
                                            }
                                            Component.onCompleted: requestPaint()
                                            Connections {
                                                target: backend
                                                function onWeatherChanged() { sparkline.requestPaint() }
                                            }
                                        }

                                        Text {
                                            text: model.wind
                                            Layout.preferredWidth: 50
                                            horizontalAlignment: Text.AlignRight
                                            color: backend.theme === "dark" ? "#bbffffff" : "#bb000000"
                                            font.pixelSize: 11
                                            font.family: "D-DIN"
                                        }
                                    }
                                }
                                // interactive: false removed to allow overscroll for closing
                            }
                        }
                        
                        // Bottom fade-out effect
                        Rectangle {
                            id: weatherBottomFade
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 30
                            z: 10
                            enabled: false
                            visible: weatherTray.height > 40
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "transparent" }
                                GradientStop { 
                                    position: 1.0; 
                                    color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0" 
                                }
                            }
                        }
                    }

                    // MouseArea for the pill to open the tray
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        
                        property point startGlobalPos: Qt.point(0, 0)
                        property real startHeight: 0
                        property bool moved: false

                        onPressed: {
                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            if (weatherTray.height === 0) {
                                weatherTray.open()
                                weatherTray.height = 1
                            }
                            startHeight = weatherTray.height
                            weatherTray.isDragging = true
                            moved = false
                        }

                        onPositionChanged: {
                            if (weatherTray.isDragging && pressed) {
                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                if (Math.abs(deltaY) > 5) moved = true
                                var newHeight = startHeight - deltaY
                                newHeight = Math.max(0, Math.min(weatherTray.expandedHeight, newHeight))
                                weatherTray.height = newHeight
                            }
                        }

                        onReleased: {
                            weatherTray.isDragging = false
                            if (moved) {
                                var threshold = weatherTray.expandedHeight * 0.2
                                var closedThreshold = threshold
                                var openThreshold = weatherTray.expandedHeight - threshold
                                
                                if (startHeight < weatherTray.expandedHeight * 0.5) {
                                    if (weatherTray.height > closedThreshold) {
                                        weatherTray.height = weatherTray.expandedHeight
                                    } else {
                                        weatherTray.height = 0
                                    }
                                } else {
                                    if (weatherTray.height < openThreshold) {
                                        weatherTray.height = 0
                                    } else {
                                        weatherTray.height = weatherTray.expandedHeight
                                    }
                                }
                            }
                        }

                        onClicked: {
                            if (!moved) {
                                // Toggle logic: if mostly closed, open it; if mostly open, close it.
                                if (weatherTray.height > weatherTray.expandedHeight * 0.5) {
                                    weatherTray.height = 0
                                } else {
                                    weatherTray.open()
                                    weatherTray.height = weatherTray.expandedHeight
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: spotifyPill
                    property real minDynamicWidth: 260
                    property real maxDynamicWidth: Math.max(minDynamicWidth, bottomBar.width - weatherPill.width - 24)
                    property real pillOpenStartY: 0
                    property real pillOpenStartHeight: 0
                    property bool pillOpenMoved: false
                    Layout.preferredWidth: Math.max(minDynamicWidth, Math.min(maxDynamicWidth, spotifyPillRow.implicitWidth + 6))
                    Layout.maximumWidth: maxDynamicWidth
                    height: 28
                    radius: 14
                    color: "transparent"
                    clip: true

                    function openFullscreenView() {
                        spotifyFullScreenTray.activeTab = 0
                        spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                    }

                    function beginPillOpen(globalY) {
                        pillOpenStartY = globalY
                        pillOpenMoved = false
                        spotifyFullScreenTray.activeTab = 0
                        if (spotifyFullScreenTray.height === 0) {
                            spotifyFullScreenTray.height = 1
                        }
                        pillOpenStartHeight = spotifyFullScreenTray.height
                        spotifyFullScreenTray.isDragging = true
                    }

                    function updatePillOpen(globalY) {
                        if (!spotifyFullScreenTray.isDragging) return
                        var delta = globalY - pillOpenStartY
                        if (Math.abs(delta) > 5) pillOpenMoved = true
                        var newHeight = pillOpenStartHeight - delta
                        newHeight = Math.max(0, Math.min(spotifyFullScreenTray.expandedHeight, newHeight))
                        spotifyFullScreenTray.height = newHeight
                    }

                    function endPillOpen() {
                        if (!spotifyFullScreenTray.isDragging) return
                        spotifyFullScreenTray.isDragging = false
                        if (!pillOpenMoved) {
                            openFullscreenView()
                            return
                        }
                        var threshold = spotifyFullScreenTray.expandedHeight * spotifyFullScreenTray.closeThresholdRatio
                        if (spotifyFullScreenTray.height < threshold) spotifyFullScreenTray.height = 0
                        else spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                    }

                    function cancelPillOpen() {
                        if (!spotifyFullScreenTray.isDragging) return
                        spotifyFullScreenTray.isDragging = false
                        if (spotifyFullScreenTray.height < spotifyFullScreenTray.expandedHeight * spotifyFullScreenTray.closeThresholdRatio) {
                            spotifyFullScreenTray.height = 0
                        } else {
                            spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: 14
                        color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                        border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1
                    }

                    // Keep pill-open gestures in one touch-friendly handler region (art + text only).
                    Item {
                        id: spotifyPillOpenGestureArea
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: Math.max(spotifyPill.height, Math.min(spotifyPill.width, spotifyPillTextColumn.x + spotifyPillTextColumn.width))
                        z: 5

                        TapHandler {
                            gesturePolicy: TapHandler.ReleaseWithinBounds
                            onTapped: spotifyPill.openFullscreenView()
                        }

                        DragHandler {
                            target: null
                            xAxis.enabled: false
                            yAxis.enabled: true
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen | PointerDevice.TouchPad

                            onActiveChanged: {
                                if (active) spotifyPill.beginPillOpen(centroid.scenePosition.y)
                                else spotifyPill.endPillOpen()
                            }

                            onCentroidChanged: {
                                if (active) spotifyPill.updatePillOpen(centroid.scenePosition.y)
                            }

                            onCanceled: spotifyPill.cancelPillOpen()
                        }
                    }

                    RowLayout {
                        id: spotifyPillRow
                        anchors.fill: parent
                        anchors.leftMargin: 0
                        anchors.rightMargin: 6
                        spacing: 2

                        Item {
                            id: spotifyPillArtItem
                            Layout.preferredWidth: spotifyPill.height
                            Layout.preferredHeight: spotifyPill.height
                            Layout.alignment: Qt.AlignVCenter
                            Rectangle {
                                anchors.fill: parent
                                radius: 0
                                color: "transparent"
                                clip: true
                                Image {
                                    id: spotifyPillAlbumArt
                                    anchors.fill: parent
                                    source: {
                                        var liveArt = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.album_art_url || "") : ""
                                        return liveArt || spotifyFallbackArtUrl || ""
                                    }
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf1bc"
                                    font.family: "Font Awesome 5 Brands"
                                    font.pixelSize: 10
                                    color: (backend && backend.theme === "dark") ? "#1DB954" : "#168d41"
                                    visible: spotifyPillAlbumArt.status === Image.Error
                                }
                            }
                        }

                        ColumnLayout {
                            id: spotifyPillTextColumn
                            Layout.fillWidth: false
                            Layout.preferredWidth: Math.min(
                                                    Math.max(80, spotifyPill.width - spotifyPill.height - (spotifyAuthControls.visible ? spotifyAuthControls.implicitWidth : (spotifyLoginButton.visible ? spotifyLoginButton.width : 0)) - 14),
                                                    Math.max(spotifyTrackText.implicitWidth, spotifyArtistText.implicitWidth)
                                                )
                            Layout.alignment: Qt.AlignVCenter
                            spacing: 0
                            Text {
                                id: spotifyTrackText
                                Layout.fillWidth: true
                                text: {
                                    if (!backend || !backend.spotifyPlayer) return "Spotify"
                                    if (!backend.spotifyPlayer.configured) return "Set SPOTIFY_CLIENT_ID"
                                    if (!backend.spotifyPlayer.authenticated) return "Login to Spotify"
                                    return backend.spotifyPlayer.track_name || "Nothing playing"
                                }
                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                font.pixelSize: 11
                                font.family: "D-DIN"
                                font.bold: true
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                            Text {
                                id: spotifyArtistText
                                Layout.fillWidth: true
                                text: backend && backend.spotifyPlayer ? (backend.spotifyPlayer.artist_name || backend.spotifyPlayer.status || "") : ""
                                color: (backend && backend.theme === "dark") ? "#bbbbbb" : "#666666"
                                font.pixelSize: 9
                                font.family: "D-DIN"
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }

                        Rectangle {
                            id: spotifyLoginButton
                            visible: backend && backend.spotifyPlayer && backend.spotifyPlayer.configured && !backend.spotifyPlayer.authenticated
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 20
                            radius: 10
                            color: "#1DB954"
                            Text {
                                anchors.centerIn: parent
                                text: "Login"
                                color: "white"
                                font.pixelSize: 10
                                font.family: "D-DIN"
                                font.bold: true
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: spotifyFullScreenTray.openLoginFlow()
                            }
                        }

                        RowLayout {
                            id: spotifyAuthControls
                            visible: backend && backend.spotifyPlayer && backend.spotifyPlayer.authenticated
                            property int buttonSize: 18
                            property int buttonIconSize: 12
                            spacing: 5
                            Layout.alignment: Qt.AlignVCenter

                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf049"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: backend.spotifyPreviousTrack()
                                }
                            }
                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: (backend && backend.spotifyPlayer && backend.spotifyPlayer.is_playing) ? "\uf04c" : "\uf04b"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: backend.spotifyTogglePlayPause()
                                }
                            }
                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf050"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: backend.spotifyNextTrack()
                                }
                            }

                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf6a9"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (backend) backend.setSpotifyVolume(0)
                                    }
                                }
                            }
                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf027"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (backend && backend.spotifyPlayer) {
                                            var currentVolume = Math.round(backend.spotifyPlayer.volume_percent || 0)
                                            backend.setSpotifyVolume(Math.max(0, currentVolume - 10))
                                        }
                                    }
                                }
                            }
                            Item {
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf028"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (backend && backend.spotifyPlayer) {
                                            var currentVolume = Math.round(backend.spotifyPlayer.volume_percent || 0)
                                            backend.setSpotifyVolume(Math.min(100, currentVolume + 10))
                                        }
                                    }
                                }
                            }
                            Item {
                                id: spotifyPillDeviceIcon
                                Layout.preferredWidth: spotifyAuthControls.buttonSize
                                Layout.preferredHeight: spotifyAuthControls.buttonSize
                                Layout.alignment: Qt.AlignVCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf26c"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: spotifyAuthControls.buttonIconSize
                                    font.weight: Font.Black
                                    color: (backend && backend.theme === "dark") ? "#9edfb6" : "#168d41"
                                }
                                TapHandler {
                                    gesturePolicy: TapHandler.ReleaseWithinBounds
                                    onTapped: spotifyFullScreenTray.openDevicePicker(spotifyPillDeviceIcon, "pill")
                                }
                            }
                        }

                    }

                    Item {
                        id: spotifyFullScreenTray
                        parent: root.contentItem
                        x: 0
                        width: root.width
                        height: 0
                        y: root.height - height
                        visible: height > 0
                        z: 2500

                        property bool isDragging: false
                        property real minExpandedHeight: 160
                        property real bottomBarInset: bottomBar.height
                        property real baseCornerRadius: 14
                        // Empirically tuned: exponent 1.45 delays early fade-in, then ramps opacity near full-open.
                        property real fadeCurveExponent: 1.45
                        property real maxHeightRatio: 1.0
                        property real closeThresholdRatio: 0.2
                        property int minSearchChars: 2
                        property int searchDebounceMs: 350
                        property int upNextListMaxHeight: 180
                        property real expandedHeight: root.height
                        property real openProgress: Math.max(0.0, Math.min(1.0, height / Math.max(1, expandedHeight)))
                        property int activeTab: 0
                        property int libraryCategory: 0
                        property var librarySelectedItem: null
                        property bool spotifyAuthenticated: backend && backend.spotifyPlayer && backend.spotifyPlayer.authenticated

                        function _playItem(item) {
                            if (!backend || !item) return
                            var itemUri = item.play_uri || item.uri || ""
                            if (!itemUri) return
                            if (item.type === "track") backend.spotifyPlayTrackUri(itemUri)
                            else backend.spotifyPlayContextUri(itemUri)
                        }

                        function refreshLibrary() {
                            if (!backend) return
                            backend.spotifyGetLibrary()
                        }

                        function openLibraryItem(item) {
                            if (!item) return
                            var t = item.type || ""
                            if (t === "album") {
                                librarySelectedItem = item
                                if (backend) backend.spotifyGetAlbumTracks(item.uri || "")
                            } else if (t === "playlist") {
                                librarySelectedItem = item
                                if (backend) backend.spotifyGetPlaylistTracks(item.uri || "")
                            } else if (t === "podcast") {
                                librarySelectedItem = item
                                if (backend) backend.spotifyGetPodcastEpisodes(item.uri || "")
                            } else {
                                _playItem(item)
                            }
                        }

                        function refreshSearch() {
                            if (!backend) return
                            var q = (spotifySearchField.text || "").trim()
                            backend.spotifySearch(q)
                        }
                        
                        function openLoginFlow() {
                            if (!backend) return
                            height = expandedHeight
                            activeTab = 0
                            if (!backend.spotifyAuthInProgress) backend.startSpotifyLogin()
                        }

                        function inlineDeviceListModel() {
                            var currentId = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.current_device_id || "") : ""
                            var currentName = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.current_device_name || "Current Device") : "Current Device"
                            var rawItems = (backend && backend.spotifyPlayer && backend.spotifyPlayer.devices) ? backend.spotifyPlayer.devices : []
                            var items = []
                            var hasCurrent = false

                            for (var i = 0; i < rawItems.length; i++) {
                                var item = rawItems[i]
                                if (!item) continue
                                if ((item.id || "") === currentId) hasCurrent = true
                                items.push({
                                    "id": item.id || "",
                                    "name": item.name || "Unknown Device",
                                    "type": item.type || "",
                                    "is_active": !!item.is_active || ((item.id || "") === currentId),
                                    "is_restricted": !!item.is_restricted
                                })
                            }

                            if (currentId && !hasCurrent) {
                                items.unshift({
                                    "id": currentId,
                                    "name": currentName,
                                    "type": "Current",
                                    "is_active": true,
                                    "is_restricted": false
                                })
                            }

                            items.sort(function(a, b) {
                                if (!!a.is_active !== !!b.is_active) return a.is_active ? -1 : 1
                                var aName = (a.name || "").toLowerCase()
                                var bName = (b.name || "").toLowerCase()
                                if (aName < bName) return -1
                                if (aName > bName) return 1
                                return 0
                            })

                            return items
                        }

                        property real devicePickerX: Math.max(10, root.width - 260)
                        property real devicePickerY: 44
                        property string devicePickerAnchorKey: ""

                        function openDevicePicker(anchorItem, anchorKey) {
                            var key = anchorKey || "default"
                            if (spotifyDevicesPopup.visible && devicePickerAnchorKey === key) {
                                spotifyDevicesPopup.close()
                                devicePickerAnchorKey = ""
                                return
                            }
                            if (!backend) return
                            backend.spotifyGetDevices()
                            var popupWidth = Math.max(150, Math.min(220, spotifyFullScreenTray.width * 0.24))
                            var popupHeight = 220
                            var defaultPoint = Qt.point(root.width - 18, 42)
                            var point = anchorItem ? anchorItem.mapToItem(root.contentItem, 0, anchorItem.height) : defaultPoint
                            var anchorWidth = anchorItem ? anchorItem.width : 0
                            var x = Math.max(10, Math.min(root.width - popupWidth - 10, point.x - popupWidth + anchorWidth + 4))
                            var y = point.y + 4
                            if (y + popupHeight > root.height - 6) y = Math.max(8, point.y - popupHeight - 6)
                            devicePickerX = x
                            devicePickerY = y
                            devicePickerAnchorKey = key
                            spotifyDevicesPopup.open()
                        }

                        opacity: Math.pow(openProgress, fadeCurveExponent)

                        Behavior on height {
                            enabled: !spotifyFullScreenTray.isDragging && (spotifyResultsList ? !spotifyResultsList.dragging : true)
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }

                        Rectangle {
                            anchors.fill: parent
                            // Corners square off as the tray approaches full-screen.
                            radius: spotifyFullScreenTray.baseCornerRadius * (1.0 - spotifyFullScreenTray.openProgress)
                            color: (backend && backend.theme === "dark") ? "#151515" : "#f5f5f5"
                        }

                        // Overlay drag handle – zero height so it doesn't push content down
                        Item {
                            anchors.top: parent.top
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width
                            height: 20
                            z: 10

                            Rectangle {
                                anchors.centerIn: parent
                                width: 36
                                height: 4
                                radius: 2
                                color: (backend && backend.theme === "dark") ? "#444444" : "#cccccc"
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.SizeVerCursor

                                property point startGlobalPos: Qt.point(0, 0)
                                property real startHeight: 0
                                property bool moved: false

                                onPressed: {
                                    startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                    startHeight = spotifyFullScreenTray.height
                                    spotifyFullScreenTray.isDragging = true
                                    moved = false
                                }

                                onPositionChanged: {
                                    if (!spotifyFullScreenTray.isDragging || !pressed) return
                                    var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                    var deltaY = currentGlobalPos.y - startGlobalPos.y
                                    if (Math.abs(deltaY) > 5) moved = true
                                    var newHeight = startHeight - deltaY
                                    newHeight = Math.max(0, Math.min(spotifyFullScreenTray.expandedHeight, newHeight))
                                    spotifyFullScreenTray.height = newHeight
                                }

                                onReleased: {
                                    spotifyFullScreenTray.isDragging = false
                                    if (!moved) {
                                        spotifyFullScreenTray.height = 0
                                        return
                                    }
                                    var threshold = spotifyFullScreenTray.expandedHeight * spotifyFullScreenTray.closeThresholdRatio
                                    if (spotifyFullScreenTray.height < threshold) spotifyFullScreenTray.height = 0
                                    else spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                                }
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            anchors.bottomMargin: 40
                            spacing: 0

                            RowLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 0

                                // Left: full-height album art

                                Item {
                                    id: spotifyAlbumArtPanel
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: spotifyAlbumArtPanel.height
                                    Layout.maximumWidth: Math.floor(spotifyFullScreenTray.width * 0.42)
                                    visible: spotifyFullScreenTray.spotifyAuthenticated

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "transparent"
                                    }

                                    Image {
                                        anchors.fill: parent
                                        source: {
                                            var liveArt = (backend && backend.spotifyPlayer)
                                                ? (backend.spotifyPlayer.album_art_url_large || backend.spotifyPlayer.album_art_url || "")
                                                : ""
                                            return liveArt || spotifyFallbackArtUrl || ""
                                        }
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                    }
                                }

                                // Right: now playing (left half) + library/search (right half)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 0

                                    Item {
                                        visible: spotifyFullScreenTray.spotifyAuthenticated
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 8
                                    }

                                    MouseArea {
                                        anchors.fill: root.contentItem
                                        visible: spotifyDevicesPopup.visible
                                        z: 2998
                                        onClicked: spotifyDevicesPopup.close()
                                    }

                                    Item {
                                        id: spotifyDevicesPopup
                                        parent: root.contentItem
                                        visible: false
                                        z: 2999
                                        width: Math.min(220, Math.max(150, spotifyFullScreenTray.width * 0.24))
                                        x: spotifyFullScreenTray.devicePickerX
                                        y: spotifyFullScreenTray.devicePickerY
                                        height: spotifyDevicesContent.implicitHeight + 14

                                        function open() { visible = true }
                                        function close() {
                                            visible = false
                                            spotifyFullScreenTray.devicePickerAnchorKey = ""
                                        }

                                        Rectangle {
                                            anchors.fill: parent
                                            radius: 8
                                            color: (backend && backend.theme === "dark") ? "#121212" : "#fafafa"
                                            border.width: 1
                                            border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#d7d7d7"
                                        }

                                        ColumnLayout {
                                            id: spotifyDevicesContent
                                            anchors.fill: parent
                                            anchors.margins: 7
                                            spacing: 5

                                            RowLayout {
                                                Layout.fillWidth: true
                                                Text {
                                                    text: "Playback Device"
                                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                                    font.family: "D-DIN"
                                                    font.pixelSize: 12
                                                    font.bold: true
                                                }
                                                Item { Layout.fillWidth: true }
                                                Text {
                                                    text: "\uf021"
                                                    font.family: "Font Awesome 5 Free"
                                                    font.pixelSize: 11
                                                    color: (backend && backend.theme === "dark") ? "#b5b5b5" : "#666666"
                                                    TapHandler {
                                                        gesturePolicy: TapHandler.ReleaseWithinBounds
                                                        onTapped: if (backend) backend.spotifyGetDevices()
                                                    }
                                                }
                                            }

                                            ListView {
                                                Layout.fillWidth: true
                                                property int maxVisibleDevices: 3
                                                Layout.preferredHeight: Math.min(contentHeight, (30 * maxVisibleDevices) + (spacing * Math.max(0, maxVisibleDevices - 1)))
                                                clip: true
                                                spacing: 3
                                                model: {
                                                    var base = [{"id": "", "name": "Auto (active device)", "type": "", "is_active": false, "is_restricted": false}]
                                                    var currentId = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.current_device_id || "") : ""
                                                    var currentName = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.current_device_name || "Current Device") : "Current Device"
                                                    var items = (backend && backend.spotifyPlayer && backend.spotifyPlayer.devices) ? backend.spotifyPlayer.devices : []
                                                    if (currentId) {
                                                        var exists = false
                                                        for (var i = 0; i < items.length; i++) {
                                                            if ((items[i].id || "") === currentId) {
                                                                exists = true
                                                                break
                                                            }
                                                        }
                                                        if (!exists) {
                                                            base.push({"id": currentId, "name": "Current: " + currentName, "type": "Current", "is_active": true, "is_restricted": false})
                                                        }
                                                    }
                                                    return base.concat(items)
                                                }

                                                delegate: Rectangle {
                                                    width: ListView.view.width
                                                    height: 30
                                                    radius: 6
                                                    property string selectedId: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.selected_device_id || "") : ""
                                                    property bool isSelected: (modelData.id || "") === selectedId || (!selectedId && !(modelData.id || ""))
                                                    color: isSelected
                                                        ? ((backend && backend.theme === "dark") ? "#2a2a2a" : "#dcdcdc")
                                                        : ((backend && backend.theme === "dark") ? "#181818" : "#f0f0f0")

                                                    RowLayout {
                                                        anchors.fill: parent
                                                        anchors.leftMargin: 8
                                                        anchors.rightMargin: 8
                                                        spacing: 6

                                                        Text {
                                                            text: modelData.name || "Unknown Device"
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            font.family: "D-DIN"
                                                            font.pixelSize: 11
                                                            elide: Text.ElideRight
                                                            Layout.fillWidth: true
                                                        }

                                                        Text {
                                                            text: (modelData.is_active ? "Active" : (modelData.type || ""))
                                                            color: (backend && backend.theme === "dark") ? "#9a9a9a" : "#666666"
                                                            font.family: "D-DIN"
                                                            font.pixelSize: 10
                                                        }
                                                    }

                                                    TapHandler {
                                                        gesturePolicy: TapHandler.ReleaseWithinBounds
                                                        onTapped: {
                                                            if (!backend) return
                                                            backend.spotifySelectDevice(modelData.id || "")
                                                            backend.spotifyGetDevices()
                                                            spotifyDevicesPopup.close()
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // Horizontal split: now playing (left) + library/search (right)
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        spacing: 0

                                        // Drag-to-close overlay for the entire tray content
                                        DragHandler {
                                            id: spotifyTrayDragToClose
                                            target: null
                                            xAxis.enabled: false

                                            property real dragStartY: 0
                                            property real dragDeltaY: 0
                                            property bool dragDownward: false

                                            onActiveChanged: {
                                                if (active) {
                                                    dragStartY = centroid.scenePosition.y
                                                    dragDeltaY = 0
                                                    dragDownward = false
                                                    spotifyFullScreenTray.isDragging = true
                                                } else {
                                                    spotifyFullScreenTray.isDragging = false
                                                    // If dragged down enough and we're at top of lists, close
                                                    if (dragDownward && dragDeltaY > 60) {
                                                        var canClose = true
                                                        // Check if we're in a scrollable list view
                                                        if (spotifyFullScreenTray.libraryCategory === -1) {
                                                            // Search results list
                                                            if (spotifyResultsList && spotifyResultsList.contentY > 0) {
                                                                canClose = false
                                                            }
                                                        } else {
                                                            // Library grid/list
                                                            if (spotifyLibraryItemGrid && spotifyLibraryItemGrid.contentY > 0) {
                                                                canClose = false
                                                            }
                                                            if (spotifyTrackListView && spotifyTrackListView.contentY > 0) {
                                                                canClose = false
                                                            }
                                                        }
                                                        if (canClose) {
                                                            spotifyFullScreenTray.height = 0
                                                        }
                                                    }
                                                }
                                            }

                                            onCentroidChanged: {
                                                if (!active) return
                                                var delta = centroid.scenePosition.y - dragStartY
                                                dragDeltaY = delta
                                                if (delta > 5) {
                                                    dragDownward = true
                                                }
                                            }
                                        }

                                        // Left: Now Playing
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            color: "transparent"
                                            clip: true

                                            StackLayout {
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                visible: spotifyFullScreenTray.spotifyAuthenticated
                                                currentIndex: 0

                                                // Tab 0: Now Playing
                                                ColumnLayout {
                                                    spacing: 8

                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        Layout.bottomMargin: 4
                                                        spacing: 14

                                                        ColumnLayout {
                                                            Layout.fillWidth: true
                                                            spacing: 2

                                                            Text {
                                                                text: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.track_name || "Nothing playing") : "Spotify"
                                                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 20
                                                                font.bold: true
                                                                elide: Text.ElideRight
                                                                Layout.fillWidth: true
                                                            }

                                                            Text {
                                                                text: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.artist_name || backend.spotifyPlayer.status || "") : ""
                                                                color: (backend && backend.theme === "dark") ? "#c0c0c0" : "#666666"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 14
                                                                elide: Text.ElideRight
                                                                Layout.fillWidth: true
                                                            }
                                                        }

                                                        RowLayout {
                                                            Layout.preferredWidth: Math.min(220, Math.max(150, spotifyFullScreenTray.width * 0.22))
                                                            Layout.alignment: Qt.AlignVCenter
                                                            spacing: 8

                                                            Text {
                                                                text: "\uf026"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 11
                                                                color: (backend && backend.theme === "dark") ? "#888888" : "#999999"
                                                            }
                                                            Slider {
                                                                Layout.fillWidth: true
                                                                from: 0; to: 100
                                                                value: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.volume_percent || 50) : 50
                                                                onMoved: backend.setSpotifyVolume(Math.round(value))
                                                            }
                                                            Text {
                                                                text: "\uf028"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 11
                                                                color: (backend && backend.theme === "dark") ? "#888888" : "#999999"
                                                            }
                                                        }
                                                    }

                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 6
                                                        visible: (backend && backend.spotifyPlayer && backend.spotifyPlayer.up_next_items) ? (backend.spotifyPlayer.up_next_items.length > 0) : false

                                                        Text {
                                                            Layout.fillWidth: true
                                                            text: "UP NEXT"
                                                            color: "white"
                                                            font.family: "D-DIN"
                                                            font.pixelSize: 18
                                                            font.bold: true
                                                        }

                                                        ListView {
                                                            Layout.fillWidth: true
                                                            Layout.preferredHeight: Math.min(spotifyFullScreenTray.upNextListMaxHeight, Math.max(0, contentHeight))
                                                            clip: true
                                                            spacing: 5
                                                            model: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.up_next_items || []) : []

                                                            delegate: Rectangle {
                                                                width: ListView.view.width
                                                                height: 46
                                                                radius: 8
                                                                color: (backend && backend.theme === "dark") ? "#171717" : "#f3f3f3"
                                                                border.width: 1
                                                                border.color: (backend && backend.theme === "dark") ? "#262626" : "#dddddd"

                                                                RowLayout {
                                                                    anchors.fill: parent
                                                                    anchors.leftMargin: 8
                                                                    anchors.rightMargin: 8
                                                                    spacing: 8

                                                                    Rectangle {
                                                                        width: 32
                                                                        height: 32
                                                                        radius: 4
                                                                        color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#d8d8d8"
                                                                        clip: true
                                                                        Image {
                                                                            anchors.fill: parent
                                                                            source: modelData.image_url || ""
                                                                            fillMode: Image.PreserveAspectCrop
                                                                            asynchronous: true
                                                                        }
                                                                    }

                                                                    ColumnLayout {
                                                                        Layout.fillWidth: true
                                                                        spacing: 1
                                                                        Text {
                                                                            text: modelData.title || ""
                                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                            font.family: "D-DIN"
                                                                            font.pixelSize: 11
                                                                            font.bold: true
                                                                            elide: Text.ElideRight
                                                                            Layout.fillWidth: true
                                                                        }
                                                                        Text {
                                                                            text: modelData.subtitle || ""
                                                                            color: (backend && backend.theme === "dark") ? "#9a9a9a" : "#666666"
                                                                            font.family: "D-DIN"
                                                                            font.pixelSize: 9
                                                                            elide: Text.ElideRight
                                                                            Layout.fillWidth: true
                                                                        }
                                                                    }

                                                                    Rectangle {
                                                                        width: 28
                                                                        height: 28
                                                                        radius: 14
                                                                        color: "#1DB954"

                                                                        Text {
                                                                            anchors.centerIn: parent
                                                                            text: "\uf04b"
                                                                            font.family: "Font Awesome 5 Free"
                                                                            font.pixelSize: 10
                                                                            color: "white"
                                                                        }

                                                                        MouseArea {
                                                                            anchors.fill: parent
                                                                            cursorShape: Qt.PointingHandCursor
                                                                            onClicked: {
                                                                                if (!backend) return
                                                                                var uri = modelData.uri || ""
                                                                                if (uri) backend.spotifyPlayTrackUri(uri)
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }

                                                    Item { Layout.fillHeight: true }

                                                    // Device picker trigger
                                                    ColumnLayout {
                                                        visible: spotifyFullScreenTray.spotifyAuthenticated
                                                        Layout.fillWidth: true
                                                        spacing: 6

                                                        Rectangle {
                                                            id: fullscreenDevicePickerButton
                                                            Layout.fillWidth: true
                                                            Layout.preferredHeight: 32
                                                            radius: 8
                                                            color: (backend && backend.theme === "dark") ? "#101010" : "#f4f4f4"
                                                            border.width: 1
                                                            border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#d7d7d7"

                                                            RowLayout {
                                                                anchors.fill: parent
                                                                anchors.leftMargin: 10
                                                                anchors.rightMargin: 10
                                                                spacing: 8

                                                                Text {
                                                                    text: {
                                                                        var selectedId = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.selected_device_id || "") : ""
                                                                        var currentName = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.current_device_name || "Current Device") : "Current Device"
                                                                        if (!selectedId) return currentName
                                                                        var items = (backend && backend.spotifyPlayer && backend.spotifyPlayer.devices) ? backend.spotifyPlayer.devices : []
                                                                        for (var i = 0; i < items.length; i++) {
                                                                            if ((items[i].id || "") === selectedId) return items[i].name || currentName
                                                                        }
                                                                        return currentName
                                                                    }
                                                                    color: (backend && backend.theme === "dark") ? "#9edfb6" : "#2f7d4c"
                                                                    font.family: "D-DIN"
                                                                    font.pixelSize: 12
                                                                    font.bold: true
                                                                    elide: Text.ElideRight
                                                                    Layout.fillWidth: true
                                                                }

                                                                Text {
                                                                    text: "\uf078"
                                                                    font.family: "Font Awesome 5 Free"
                                                                    font.pixelSize: 11
                                                                    color: (backend && backend.theme === "dark") ? "#b5b5b5" : "#666666"
                                                                }
                                                            }

                                                            TapHandler {
                                                                gesturePolicy: TapHandler.ReleaseWithinBounds
                                                                onTapped: spotifyFullScreenTray.openDevicePicker(fullscreenDevicePickerButton, "fullscreen")
                                                            }
                                                        }
                                                    }

                                                    // Playback controls: shuffle | prev | play/pause | next | repeat
                                                    RowLayout {
                                                        Layout.alignment: Qt.AlignHCenter
                                                        spacing: 22

                                                        Text {
                                                            text: "\uf074"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 16
                                                            color: (backend && backend.spotifyPlayer && backend.spotifyPlayer.shuffle_state) ? "#1DB954"
                                                                   : (backend && backend.theme === "dark") ? "#666666" : "#aaaaaa"
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: backend.spotifySetShuffle(!(backend.spotifyPlayer && backend.spotifyPlayer.shuffle_state))
                                                            }
                                                        }

                                                        Text {
                                                            text: "\uf048"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 22
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.spotifyPreviousTrack() }
                                                        }

                                                        Rectangle {
                                                            width: 48; height: 48
                                                            radius: 24
                                                            color: "#1DB954"
                                                            Text {
                                                                anchors.centerIn: parent
                                                                text: (backend && backend.spotifyPlayer && backend.spotifyPlayer.is_playing) ? "\uf04c" : "\uf04b"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 20
                                                                color: "white"
                                                            }
                                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.spotifyTogglePlayPause() }
                                                        }

                                                        Text {
                                                            text: "\uf051"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 22
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: backend.spotifyNextTrack() }
                                                        }

                                                        Text {
                                                            text: "\uf01e"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 16
                                                            color: (backend && backend.spotifyPlayer && backend.spotifyPlayer.repeat_state !== "off") ? "#1DB954"
                                                                   : (backend && backend.theme === "dark") ? "#666666" : "#aaaaaa"
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    var cur = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.repeat_state || "off") : "off"
                                                                    backend.spotifySetRepeat(cur === "off" ? "context" : cur === "context" ? "track" : "off")
                                                                }
                                                            }
                                                        }
                                                    }

                                                    // Progress bar + timestamps
                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 2

                                                        Slider {
                                                            id: spotifyProgressSlider
                                                            Layout.fillWidth: true
                                                            from: 0
                                                            to: Math.max(1, (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.duration_ms || 1) : 1)

                                                            Binding {
                                                                target: spotifyProgressSlider
                                                                property: "value"
                                                                value: (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.progress_ms || 0) : 0
                                                                when: !spotifyProgressSlider.pressed
                                                            }

                                                            onPressedChanged: {
                                                                if (!pressed) backend.spotifySeek(Math.round(value))
                                                            }

                                                            background: Rectangle {
                                                                x: spotifyProgressSlider.leftPadding
                                                                y: spotifyProgressSlider.topPadding + spotifyProgressSlider.availableHeight / 2 - height / 2
                                                                width: spotifyProgressSlider.availableWidth
                                                                height: 4
                                                                radius: 2
                                                                color: (backend && backend.theme === "dark") ? "#333333" : "#cccccc"
                                                                Rectangle {
                                                                    width: spotifyProgressSlider.visualPosition * parent.width
                                                                    height: parent.height
                                                                    radius: 2
                                                                    color: "#1DB954"
                                                                }
                                                            }

                                                            handle: Rectangle {
                                                                x: spotifyProgressSlider.leftPadding + spotifyProgressSlider.visualPosition * (spotifyProgressSlider.availableWidth - width)
                                                                y: spotifyProgressSlider.topPadding + spotifyProgressSlider.availableHeight / 2 - height / 2
                                                                width: 12; height: 12
                                                                radius: 6
                                                                color: spotifyProgressSlider.pressed ? "#1DB954" : "white"
                                                                border.color: "#1DB954"
                                                                border.width: 1
                                                            }
                                                        }

                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            Text {
                                                                text: {
                                                                    var ms = spotifyProgressSlider.value
                                                                    var s = Math.floor(ms / 1000)
                                                                    var m = Math.floor(s / 60)
                                                                    return m + ":" + (s % 60 < 10 ? "0" : "") + (s % 60)
                                                                }
                                                                color: (backend && backend.theme === "dark") ? "#888888" : "#999999"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 10
                                                            }
                                                            Item { Layout.fillWidth: true }
                                                            Text {
                                                                text: {
                                                                    var ms = (backend && backend.spotifyPlayer) ? (backend.spotifyPlayer.duration_ms || 0) : 0
                                                                    var s = Math.floor(ms / 1000)
                                                                    var m = Math.floor(s / 60)
                                                                    return m + ":" + (s % 60 < 10 ? "0" : "") + (s % 60)
                                                                }
                                                                color: (backend && backend.theme === "dark") ? "#888888" : "#999999"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 10
                                                            }
                                                        }
                                                    }
                                                }

                                            }

                                            // Login screen
                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 10
                                                visible: !spotifyFullScreenTray.spotifyAuthenticated

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.fillHeight: true
                                                    radius: 8
                                                    color: (backend && backend.theme === "dark") ? "#0f0f0f" : "white"
                                                    clip: true

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 10
                                                        spacing: 8

                                                        Item { Layout.fillHeight: true }

                                                        Rectangle {
                                                            Layout.alignment: Qt.AlignHCenter
                                                            Layout.preferredWidth: Math.min(parent.width - 20, parent.height - 20, 180)
                                                            Layout.preferredHeight: Layout.preferredWidth
                                                            radius: 8
                                                            color: "white"
                                                            clip: true
                                                            Image {
                                                                anchors.fill: parent
                                                                anchors.margins: 8
                                                                source: backend ? backend.spotifyAuthQrUrl : ""
                                                                fillMode: Image.PreserveAspectFit
                                                                asynchronous: true
                                                            }
                                                        }

                                                        Item { Layout.fillHeight: true }
                                                    }
                                                }
                                            }
                                        }

                                        // Divider
                                        Rectangle {
                                            width: 1
                                            Layout.fillHeight: true
                                            color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#d0d0d0"
                                        }

                                        // Right: Library (always visible)
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.fillHeight: true
                                            color: "transparent"
                                            clip: true

                                            Item {
                                                anchors.fill: parent
                                                anchors.margins: 10

                                                RowLayout {
                                                    id: spotifyLibraryNavRow
                                                    anchors.top: parent.top
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    visible: spotifyFullScreenTray.spotifyAuthenticated
                                                    spacing: 6

                                                    Repeater {
                                                        model: [
                                                            {"label": "Search", "category": -1},
                                                            {"label": "Playlists", "category": 0},
                                                            {"label": "Albums", "category": 1},
                                                            {"label": "Podcasts", "category": 3}
                                                        ]
                                                        Rectangle {
                                                            Layout.preferredHeight: 26
                                                            Layout.preferredWidth: Math.max(74, spotifyLibraryTabLabel.implicitWidth + 20)
                                                            radius: 13
                                                            color: spotifyFullScreenTray.libraryCategory === modelData.category
                                                                   ? ((backend && backend.theme === "dark") ? "#2f2f2f" : "#dcdcdc")
                                                                   : ((backend && backend.theme === "dark") ? "#1a1a1a" : "#ebebeb")

                                                            Text {
                                                                id: spotifyLibraryTabLabel
                                                                anchors.centerIn: parent
                                                                text: modelData.label
                                                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 11
                                                                font.bold: spotifyFullScreenTray.libraryCategory === modelData.category
                                                            }

                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: {
                                                                    spotifyFullScreenTray.librarySelectedItem = null
                                                                    spotifyFullScreenTray.libraryCategory = modelData.category
                                                                    if (modelData.category === -1) spotifyFullScreenTray.refreshSearch()
                                                                }
                                                            }
                                                        }
                                                    }

                                                    Item { Layout.fillWidth: true }
                                                }

                                                ColumnLayout {
                                                    anchors.top: spotifyLibraryNavRow.visible ? spotifyLibraryNavRow.bottom : parent.top
                                                    anchors.topMargin: spotifyLibraryNavRow.visible ? 8 : 0
                                                    anchors.left: parent.left
                                                    anchors.right: parent.right
                                                    anchors.bottom: parent.bottom
                                                    spacing: 8

                                                    // Search panel is now part of the right pane navigation.
                                                    ColumnLayout {
                                                        Layout.fillWidth: true
                                                        Layout.fillHeight: true
                                                        spacing: 8
                                                        visible: spotifyFullScreenTray.libraryCategory === -1 && !spotifyFullScreenTray.librarySelectedItem

                                                        TextField {
                                                            id: spotifySearchField
                                                            Layout.fillWidth: true
                                                            placeholderText: "Search songs, albums, artists, playlists"
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            placeholderTextColor: (backend && backend.theme === "dark") ? "#7c7c7c" : "#9a9a9a"
                                                            background: Rectangle {
                                                                radius: 8
                                                                color: (backend && backend.theme === "dark") ? "#1e1e1e" : "#f0f0f0"
                                                            }
                                                            onTextChanged: spotifySearchDebounce.restart()
                                                        }

                                                        Timer {
                                                            id: spotifySearchDebounce
                                                            interval: spotifyFullScreenTray.searchDebounceMs
                                                            repeat: false
                                                            onTriggered: spotifyFullScreenTray.refreshSearch()
                                                        }

                                                        ListView {
                                                            id: spotifyResultsList
                                                            Layout.fillWidth: true
                                                            Layout.fillHeight: true
                                                            clip: true
                                                            spacing: 4
                                                            model: backend ? backend.spotifySearchResults : []
                                                            delegate: Rectangle {
                                                                width: ListView.view.width
                                                                height: 48
                                                                radius: 8
                                                                color: (backend && backend.theme === "dark") ? "#1b1b1b" : "#f6f6f6"

                                                                RowLayout {
                                                                    anchors.fill: parent
                                                                    anchors.leftMargin: 8
                                                                    anchors.rightMargin: 8
                                                                    spacing: 8

                                                                    Rectangle {
                                                                        Layout.preferredWidth: 34
                                                                        Layout.preferredHeight: 34
                                                                        radius: 4
                                                                        color: (backend && backend.theme === "dark") ? "#252525" : "#e5e5e5"
                                                                        clip: true
                                                                        Image {
                                                                            anchors.fill: parent
                                                                            source: modelData.image_url || ""
                                                                            fillMode: Image.PreserveAspectCrop
                                                                            asynchronous: true
                                                                        }
                                                                    }

                                                                    ColumnLayout {
                                                                        Layout.fillWidth: true
                                                                        spacing: 0
                                                                        Text {
                                                                            text: modelData.title || ""
                                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                            font.family: "D-DIN"
                                                                            font.pixelSize: 12
                                                                            font.bold: true
                                                                            elide: Text.ElideRight
                                                                            Layout.fillWidth: true
                                                                        }
                                                                        Text {
                                                                            text: ((modelData.type || "").toUpperCase()) + " • " + (modelData.subtitle || "")
                                                                            color: (backend && backend.theme === "dark") ? "#b8b8b8" : "#666666"
                                                                            font.family: "D-DIN"
                                                                            font.pixelSize: 10
                                                                            elide: Text.ElideRight
                                                                            Layout.fillWidth: true
                                                                        }
                                                                    }
                                                                }

                                                                TapHandler {
                                                                    gesturePolicy: TapHandler.ReleaseWithinBounds
                                                                    onTapped: spotifyFullScreenTray._playItem(modelData)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                // Category items grid (drill-down)
                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    spacing: 6
                                                    visible: spotifyFullScreenTray.libraryCategory !== -1 && !spotifyFullScreenTray.librarySelectedItem

                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        spacing: 8

                                                        Item { Layout.fillWidth: true }

                                                        Text {
                                                            text: "\uf021"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 13
                                                            color: (backend && backend.theme === "dark") ? "#aaaaaa" : "#777777"
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: spotifyFullScreenTray.refreshLibrary()
                                                            }
                                                        }
                                                    }

                                                    GridView {
                                                        id: spotifyLibraryItemGrid
                                                        Layout.fillWidth: true
                                                        Layout.fillHeight: true
                                                        clip: true
                                                        property int cols: Math.max(2, Math.floor(width / 130))
                                                        cellWidth: Math.floor(width / cols)
                                                        cellHeight: cellWidth + 44
                                                        model: spotifyFullScreenTray.libraryCategory === 0 ? ((backend && backend.spotifyLibrary) ? (backend.spotifyLibrary.playlists || []) : [])
                                                               : spotifyFullScreenTray.libraryCategory === 1 ? ((backend && backend.spotifyLibrary) ? (backend.spotifyLibrary.albums || []) : [])
                                                               : ((backend && backend.spotifyLibrary) ? (backend.spotifyLibrary.podcasts || []) : [])

                                                        delegate: Item {
                                                            width: spotifyLibraryItemGrid.cellWidth
                                                            height: spotifyLibraryItemGrid.cellHeight

                                                            Rectangle {
                                                                anchors.fill: parent
                                                                anchors.margins: 4
                                                                radius: 10
                                                                color: (backend && backend.theme === "dark") ? "#1a1a1a" : "#f0f0f0"
                                                                clip: true

                                                                ColumnLayout {
                                                                    anchors.fill: parent
                                                                    spacing: 0

                                                                    Rectangle {
                                                                        Layout.fillWidth: true
                                                                        Layout.preferredHeight: spotifyLibraryItemGrid.cellWidth - 8
                                                                        color: (backend && backend.theme === "dark") ? "#252525" : "#e0e0e0"
                                                                        clip: true
                                                                        radius: 10
                                                                        Image {
                                                                            anchors.fill: parent
                                                                            source: modelData.image_url || ""
                                                                            fillMode: Image.PreserveAspectCrop
                                                                            asynchronous: true
                                                                        }
                                                                    }

                                                                    Text {
                                                                        text: modelData.title || ""
                                                                        color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                        font.family: "D-DIN"
                                                                        font.pixelSize: 11
                                                                        font.bold: true
                                                                        elide: Text.ElideRight
                                                                        Layout.fillWidth: true
                                                                        Layout.leftMargin: 6
                                                                        Layout.rightMargin: 6
                                                                        Layout.topMargin: 4
                                                                    }

                                                                    Text {
                                                                        text: modelData.subtitle || ""
                                                                        color: (backend && backend.theme === "dark") ? "#aaaaaa" : "#777777"
                                                                        font.family: "D-DIN"
                                                                        font.pixelSize: 9
                                                                        elide: Text.ElideRight
                                                                        Layout.fillWidth: true
                                                                        Layout.leftMargin: 6
                                                                        Layout.rightMargin: 6
                                                                        Layout.bottomMargin: 4
                                                                    }
                                                                }

                                                                TapHandler {
                                                                    gesturePolicy: TapHandler.ReleaseWithinBounds
                                                                    onTapped: spotifyFullScreenTray.openLibraryItem(modelData)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                // Track list (album/playlist drill-down)
                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    spacing: 0
                                                    visible: !!spotifyFullScreenTray.librarySelectedItem

                                                    RowLayout {
                                                        Layout.fillWidth: true
                                                        Layout.bottomMargin: 6
                                                        spacing: 10

                                                        Text {
                                                            text: "\uf060"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 14
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: spotifyFullScreenTray.librarySelectedItem = null
                                                            }
                                                        }

                                                        Rectangle {
                                                            width: 44; height: 44
                                                            radius: 6
                                                            color: (backend && backend.theme === "dark") ? "#252525" : "#e0e0e0"
                                                            clip: true
                                                            Image {
                                                                anchors.fill: parent
                                                                source: spotifyFullScreenTray.librarySelectedItem ? (spotifyFullScreenTray.librarySelectedItem.image_url || "") : ""
                                                                fillMode: Image.PreserveAspectCrop
                                                                asynchronous: true
                                                            }
                                                        }

                                                        ColumnLayout {
                                                            Layout.fillWidth: true
                                                            spacing: 2
                                                            Text {
                                                                text: spotifyFullScreenTray.librarySelectedItem ? (spotifyFullScreenTray.librarySelectedItem.title || "") : ""
                                                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 13
                                                                font.bold: true
                                                                elide: Text.ElideRight
                                                                Layout.fillWidth: true
                                                            }
                                                            Text {
                                                                text: spotifyFullScreenTray.librarySelectedItem ? (spotifyFullScreenTray.librarySelectedItem.subtitle || "") : ""
                                                                color: (backend && backend.theme === "dark") ? "#aaaaaa" : "#777777"
                                                                font.family: "D-DIN"
                                                                font.pixelSize: 10
                                                                elide: Text.ElideRight
                                                                Layout.fillWidth: true
                                                            }
                                                        }

                                                        Text {
                                                            text: "\uf144"
                                                            font.family: "Font Awesome 5 Free"
                                                            font.pixelSize: 22
                                                            color: "#1DB954"
                                                            MouseArea {
                                                                anchors.fill: parent
                                                                cursorShape: Qt.PointingHandCursor
                                                                onClicked: spotifyFullScreenTray._playItem(spotifyFullScreenTray.librarySelectedItem)
                                                            }
                                                        }
                                                    }

                                                    ListView {
                                                        id: spotifyTrackListView
                                                        Layout.fillWidth: true
                                                        Layout.fillHeight: true
                                                        clip: true
                                                        spacing: 3
                                                        model: backend ? backend.spotifyLibraryItemTracks : []

                                                        delegate: Rectangle {
                                                            width: ListView.view.width
                                                            height: 46
                                                            radius: 8
                                                            color: (backend && backend.theme === "dark") ? "#181818" : "#f4f4f4"

                                                            RowLayout {
                                                                anchors.fill: parent
                                                                anchors.leftMargin: 10
                                                                anchors.rightMargin: 10
                                                                spacing: 10

                                                                Text {
                                                                    text: (index + 1) + "."
                                                                    color: (backend && backend.theme === "dark") ? "#666666" : "#aaaaaa"
                                                                    font.family: "D-DIN"
                                                                    font.pixelSize: 11
                                                                    Layout.preferredWidth: 24
                                                                }

                                                                ColumnLayout {
                                                                    Layout.fillWidth: true
                                                                    spacing: 1
                                                                    Text {
                                                                        text: modelData.title || ""
                                                                        color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                        font.family: "D-DIN"
                                                                        font.pixelSize: 12
                                                                        font.bold: true
                                                                        elide: Text.ElideRight
                                                                        Layout.fillWidth: true
                                                                    }
                                                                    Text {
                                                                        text: modelData.subtitle || ""
                                                                        color: (backend && backend.theme === "dark") ? "#888888" : "#777777"
                                                                        font.family: "D-DIN"
                                                                        font.pixelSize: 10
                                                                        elide: Text.ElideRight
                                                                        Layout.fillWidth: true
                                                                    }
                                                                }
                                                            }

                                                            TapHandler {
                                                                gesturePolicy: TapHandler.ReleaseWithinBounds
                                                                onTapped: spotifyFullScreenTray._playItem(modelData)
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        DragHandler {
                            id: spotifyCloseDragHandler
                            target: null
                            // Top handle already provides drag-to-close; this global handler steals taps from lists.
                            enabled: false
                            xAxis.enabled: false

                            property real startY: 0
                            property real startHeight: 0
                            property bool draggingDown: false

                            onActiveChanged: {
                                if (active) {
                                    startY = centroid.scenePosition.y
                                    startHeight = spotifyFullScreenTray.height
                                    draggingDown = false
                                } else {
                                    if (!draggingDown) return
                                    spotifyFullScreenTray.isDragging = false
                                    var threshold = spotifyFullScreenTray.expandedHeight * spotifyFullScreenTray.closeThresholdRatio
                                    if (spotifyFullScreenTray.height < threshold) spotifyFullScreenTray.height = 0
                                    else spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                                }
                            }

                            onCentroidChanged: {
                                if (!active) return
                                var delta = centroid.scenePosition.y - startY
                                if (delta > 5 && !draggingDown) {
                                    draggingDown = true
                                    spotifyFullScreenTray.isDragging = true
                                    startHeight = spotifyFullScreenTray.height
                                    startY = centroid.scenePosition.y - 5
                                }
                                if (!draggingDown) return
                                var newHeight = startHeight - (centroid.scenePosition.y - startY)
                                newHeight = Math.max(0, Math.min(spotifyFullScreenTray.expandedHeight, newHeight))
                                spotifyFullScreenTray.height = newHeight
                            }
                        }

                        onVisibleChanged: {
                            if (visible) {
                                refreshLibrary()
                                if (libraryCategory === -1) refreshSearch()
                                if (backend) backend.spotifyGetDevices()
                            }
                        }
                        onHeightChanged: {
                            if (height === 0 && backend && backend.spotifyAuthInProgress) {
                                backend.cancelSpotifyLogin()
                            }
                        }
                    }

                    DragHandler {
                        id: spotifyPillDragHandler
                        target: null
                        // Only needed to drag-open from the collapsed pill.
                        // When the tray is open, leave taps to list delegates.
                        enabled: false
                        xAxis.enabled: false

                        property real dragStartY: 0
                        property real startHeight: 0

                        onActiveChanged: {
                            if (active) {
                                dragStartY = centroid.scenePosition.y
                                if (spotifyFullScreenTray.height === 0) {
                                    spotifyFullScreenTray.height = 1
                                }
                                startHeight = spotifyFullScreenTray.height
                                spotifyFullScreenTray.isDragging = true
                            } else {
                                if (!spotifyFullScreenTray.isDragging) return
                                spotifyFullScreenTray.isDragging = false
                                var threshold = spotifyFullScreenTray.expandedHeight * spotifyFullScreenTray.closeThresholdRatio
                                if (spotifyFullScreenTray.height < threshold) spotifyFullScreenTray.height = 0
                                else spotifyFullScreenTray.height = spotifyFullScreenTray.expandedHeight
                            }
                        }

                        onCentroidChanged: {
                            if (!active || !spotifyFullScreenTray.isDragging) return
                            var delta = centroid.scenePosition.y - dragStartY
                            var newHeight = startHeight - delta
                            newHeight = Math.max(0, Math.min(spotifyFullScreenTray.expandedHeight, newHeight))
                            spotifyFullScreenTray.height = newHeight
                        }
                    }
                }

                // Scrolling launch ticker
                Rectangle {
                    id: tickerRect
                    Layout.fillWidth: true
                    Layout.minimumWidth: 400
                    Layout.maximumHeight: 28
                    Layout.maximumWidth: 1500
                    height: 28
                    radius: 14
                    color: "transparent" // Color moved to background child
                    clip: false // Allow narrativeTray to expand beyond bounds

                    // Fading background for the ticker bar
                    Rectangle {
                        id: tickerBackground
                        anchors.fill: parent
                        radius: 16
                        color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1
                        z: 0
                        // Fade out as tray expands (starts fading when tray is 2x ticker height)
                        opacity: 1.0 - Math.min(1.0, narrativeTray.height / 56.0)
                    }

                    // Clipped container for scrolling text
                    Item {
                        anchors.fill: parent
                        clip: true
                        
                        Text {
                            id: tickerText
                            anchors.verticalCenter: parent.verticalCenter
                            text: {
                                var narratives = backend.launchDescriptions
                                var textList = []
                                for (var i = 0; i < narratives.length; i++) {
                                    var item = narratives[i]
                                    // Use 'full' if object, otherwise use item directly (legacy string)
                                    textList.push((typeof item === "object" && item.full) ? item.full : item)
                                }
                                return textList.join(" \\ ")
                            }
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            font.bold: true
                            // Fade out as tray expands (starts fading when tray is 2x ticker height)
                            opacity: 1.0 - Math.min(1.0, narrativeTray.height / 56.0)

                            onTextChanged: tickerScrollSequence.restart()

                            SequentialAnimation on x {
                                id: tickerScrollSequence
                                loops: Animation.Infinite
                                NumberAnimation {
                                    from: tickerRect.width
                                    to: -tickerText.width + 400  // Pause with text still visible
                                    // Duration scales with distance to keep scroll speed constant:
                                    // 0.025 px/ms = 25 px/s, so duration = distance / 0.025 ms.
                                    duration: Math.max(4000, (tickerRect.width + tickerText.width - 400) / 0.025)
                                }
                                PauseAnimation { duration: 4000 }  // 4 second pause
                                PropertyAnimation {
                                    to: tickerRect.width  // Reset to starting position
                                    duration: 0  // Instant reset
                                }
                            }
                        }
                    }
                    
                    // Slide-up handle for narrative tray
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        
                        property point startGlobalPos: Qt.point(0, 0)
                        property real startHeight: 0
                        property bool isDragging: false
                        property bool moved: false
                        
                        onPressed: {
                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            // Ensure tray is ready
                            if (narrativeTray.height === 0) {
                                narrativeTray.height = 1
                            }
                            startHeight = narrativeTray.height
                            isDragging = true
                            moved = false
                        }
                        
                        onPositionChanged: {
                            if (isDragging && pressed) {
                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                if (Math.abs(deltaY) > 5) moved = true
                                // Dragging UP (negative delta) increases height
                                var newHeight = startHeight - deltaY
                                
                                newHeight = Math.max(0, Math.min(narrativeTray.expandedHeight, newHeight))
                                narrativeTray.height = newHeight
                            }
                        }
                        
                        onReleased: {
                            isDragging = false
                            if (moved) {
                                // 20% threshold logic:
                                // If we started from closed (startHeight < expandedHeight * 0.5), we need 20% to open.
                                // If we started from open (startHeight > expandedHeight * 0.5), we need 20% travel to close.
                                var threshold = narrativeTray.expandedHeight * 0.2
                                var closedThreshold = threshold
                                var openThreshold = narrativeTray.expandedHeight - threshold
                                
                                if (startHeight < narrativeTray.expandedHeight * 0.5) {
                                    // Started closed, snap to open if we passed 20%
                                    if (narrativeTray.height > closedThreshold) {
                                        narrativeTray.height = narrativeTray.expandedHeight
                                    } else {
                                        narrativeTray.height = 0
                                    }
                                } else {
                                    // Started open, snap to closed if we dropped below 80% (20% travel)
                                    if (narrativeTray.height < openThreshold) {
                                        narrativeTray.height = 0
                                    } else {
                                        narrativeTray.height = narrativeTray.expandedHeight
                                    }
                                }
                            }
                        }

                        onClicked: {
                            if (!moved) {
                                // Toggle logic: if mostly closed, open it; if mostly open, close it.
                                if (narrativeTray.height > narrativeTray.expandedHeight * 0.5) {
                                    narrativeTray.height = 0
                                } else {
                                    narrativeTray.open()
                                    narrativeTray.height = narrativeTray.expandedHeight
                                }
                            }
                        }
                    }

                    Popup {
                        id: narrativeTray
                        // Now child of tickerRect, so x:0 aligns perfectly
                        x: 0
                        width: parent.width
                        height: 0
                        // Sit at the bottom and grow UP, covering the ticker area
                        y: parent.height - height
                        modal: false
                        focus: false
                        visible: height > 0
                        closePolicy: Popup.CloseOnPressOutside
                        onClosed: height = 0

                        padding: 0
                        leftPadding: 0
                        rightPadding: 0
                        topPadding: 0
                        bottomPadding: 0
                        
                        property real expandedHeight: 220 // Taller list
                        property bool isDragging: false
                        opacity: height / expandedHeight // Fade in/out based on drag position
                        
                        Behavior on height {
                            enabled: !narrativeTray.isDragging && (narrativeListView ? !narrativeListView.dragging : true)
                            NumberAnimation {
                                duration: 300
                                easing.type: Easing.OutCubic
                            }
                        }
                        
                        background: Item {
                            Rectangle {
                                id: trayBackground
                                anchors.fill: parent
                                color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                                radius: 14
                                border.width: 1
                                border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                            }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            spacing: 0
                            
                            // Drag Handle (Top of tray)
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 25
                                color: "transparent"
                                
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf078"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: 12
                                    color: backend.theme === "dark" ? "white" : "black"
                                }
                                
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    
                                    property point startGlobalPos: Qt.point(0, 0)
                                    property real startHeight: 0
                                    property bool isDragging: false
                                    property bool moved: false
                                    
                                    onPressed: {
                                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                        if (narrativeTray.height === 0) {
                                            narrativeTray.open()
                                            narrativeTray.height = 1
                                        }
                                        startHeight = narrativeTray.height
                                        narrativeTray.isDragging = true
                                        moved = false
                                    }
                                    
                                    onPositionChanged: {
                                        if (narrativeTray.isDragging && pressed) {
                                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            // Dragging DOWN (positive delta) decreases height since expanding from bottom
                                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                                            if (Math.abs(deltaY) > 5) moved = true
                                            var newHeight = startHeight - deltaY
                                            
                                            newHeight = Math.max(0, Math.min(narrativeTray.expandedHeight, newHeight))
                                            narrativeTray.height = newHeight
                                        }
                                    }
                                    
                                    onReleased: {
                                        narrativeTray.isDragging = false
                                        if (moved) {
                                            var threshold = narrativeTray.expandedHeight * 0.2
                                            var closedThreshold = threshold
                                            var openThreshold = narrativeTray.expandedHeight - threshold
                                            
                                            if (startHeight < narrativeTray.expandedHeight * 0.5) {
                                                if (narrativeTray.height > closedThreshold) {
                                                    narrativeTray.height = narrativeTray.expandedHeight
                                                } else {
                                                    narrativeTray.height = 0
                                                }
                                            } else {
                                                if (narrativeTray.height < openThreshold) {
                                                    narrativeTray.height = 0
                                                } else {
                                                    narrativeTray.height = narrativeTray.expandedHeight
                                                }
                                            }
                                        }
                                    }

                                    onClicked: {
                                        if (!moved) {
                                            // Tap to close: if mostly open, close it.
                                            if (narrativeTray.height > narrativeTray.expandedHeight * 0.5) {
                                                narrativeTray.height = 0
                                            } else {
                                                narrativeTray.height = narrativeTray.expandedHeight
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Narratives List
                            ListView {
                                id: narrativeListView
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.leftMargin: 6
                                Layout.rightMargin: 6
                                Layout.bottomMargin: 6
                                Layout.topMargin: 0
                                clip: true
                                model: backend.launchDescriptions
                                spacing: 0
                                interactive: true
                                boundsBehavior: Flickable.DragOverBounds
                                flickableDirection: Flickable.VerticalFlick
                                property real dragStartY: 0
                                // Collapse logic will be handled by ListView signals
                                /*
                                DragHandler {
                                    id: narrativeListDrag
                                    target: null
                                    xAxis.enabled: false
                                    grabPermissions: PointerHandler.CanTakeOverFromItems | PointerHandler.CanTakeOverFromHandlers | PointerHandler.ApprovesTakeOverByAnything
                                    onActiveChanged: {
                                        if (active) {
                                            narrativeListView.dragStartY = centroid.scenePosition.y
                                        } else {
                                            if (narrativeTray.isDragging) {
                                                narrativeTray.isDragging = false
                                                if (narrativeTray.height < narrativeTray.expandedHeight) {
                                                    if (narrativeTray.height < narrativeTray.expandedHeight * 0.8) {
                                                        narrativeTray.height = 0
                                                    } else {
                                                        narrativeTray.height = narrativeTray.expandedHeight
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    onCentroidChanged: {
                                        if (active) {
                                            if (!narrativeTray.isDragging) {
                                                if (narrativeListView.contentY <= 0 && centroid.scenePosition.y > narrativeListView.dragStartY + 20) {
                                                    // Start dragging tray down ONLY if at top and moving down significantly
                                                    narrativeTray.isDragging = true
                                                    narrativeListView.dragStartY = centroid.scenePosition.y
                                                }
                                            }

                                            if (narrativeTray.isDragging) {
                                                var delta = centroid.scenePosition.y - narrativeListView.dragStartY
                                                if (delta > 0) {
                                                    narrativeTray.height = Math.max(0, narrativeTray.expandedHeight - delta)
                                                } else {
                                                    narrativeTray.height = narrativeTray.expandedHeight
                                                }
                                            }
                                        }
                                    }
                                }
                                */
                                
                                onDraggingChanged: {
                                    if (dragging) {
                                        dragStartY = contentY
                                    } else {
                                        if (narrativeTray.isDragging) {
                                            narrativeTray.isDragging = false
                                            if (narrativeTray.height < narrativeTray.expandedHeight) {
                                                if (narrativeTray.height < narrativeTray.expandedHeight * 0.7) {
                                                    narrativeTray.height = 0
                                                } else {
                                                    narrativeTray.height = narrativeTray.expandedHeight
                                                }
                                            }
                                        }
                                    }
                                }

                                onContentYChanged: {
                                    if (dragging && !narrativeTray.isDragging) {
                                        if (contentY < -10 && contentY < dragStartY) {
                                            narrativeTray.isDragging = true
                                        }
                                    }
                                    
                                    if (narrativeTray.isDragging) {
                                        var delta = -contentY
                                        if (delta > 0) {
                                            narrativeTray.height = Math.max(0, narrativeTray.expandedHeight - delta)
                                        } else {
                                            // Ensure it stays at full height if user drags back up while still dragging
                                            narrativeTray.height = narrativeTray.expandedHeight
                                        }
                                    }
                                }

                                delegate: Item {
                                    width: ListView.view.width
                                    height: contentLayout.implicitHeight + 8
                                    
                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.leftMargin: 0
                                        anchors.rightMargin: 0
                                        color: ListView.isCurrentItem ? 
                                               (backend.theme === "dark" ? "#303030" : "#e0e0e0") : 
                                               "transparent"
                                        radius: 4
                                        
                                        RowLayout {
                                            id: contentLayout
                                            anchors.fill: parent
                                            anchors.margins: 0
                                            spacing: 8
                                            
                                            ColumnLayout {
                                                id: dateColumn
                                                Layout.alignment: Qt.AlignTop
                                                Layout.minimumWidth: 60
                                                Layout.maximumWidth: 60
                                                Layout.preferredWidth: 60
                                                spacing: 2
                                                visible: (typeof modelData === "object" && modelData.date) ? true : false

                                                Text {
                                                    id: timeText
                                                    // Extract time if it exists in the date string (e.g., "7/1 2104")
                                                    text: {
                                                        if (typeof modelData !== "object" || !modelData.date) return ""
                                                        var parts = modelData.date.split(' ')
                                                        return parts.length > 1 ? parts[1] : ""
                                                    }
                                                    visible: text !== ""
                                                    color: (backend && backend.theme === "dark") ? "#88ffffff" : "#88000000" // Muted opacity to match date
                                                    font.pixelSize: 14
                                                    font.family: "D-DIN"
                                                    font.bold: true
                                                    horizontalAlignment: Text.AlignRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    id: dayOfWeekText
                                                    text: (typeof modelData === "object" && modelData.day_of_week) ? modelData.day_of_week : ""
                                                    visible: text !== ""
                                                    color: (backend && backend.theme === "dark") ? "#88ffffff" : "#88000000" // Muted opacity
                                                    font.pixelSize: 14
                                                    font.family: "D-DIN"
                                                    font.bold: true
                                                    horizontalAlignment: Text.AlignRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    id: dateText
                                                    // Extract date part (e.g., "7/1")
                                                    text: {
                                                        if (typeof modelData !== "object" || !modelData.date) return ""
                                                        var parts = modelData.date.split(' ')
                                                        return parts[0]
                                                    }
                                                    color: (backend && backend.theme === "dark") ? "#88ffffff" : "#88000000" // Muted opacity
                                                    font.pixelSize: 14 // Increased to match time
                                                    font.family: "D-DIN"
                                                    font.bold: true
                                                    horizontalAlignment: Text.AlignRight
                                                    Layout.fillWidth: true
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                Layout.alignment: Qt.AlignTop
                                                spacing: 2

                                                Text {
                                                    id: missionNameText
                                                    text: {
                                                        if (typeof modelData !== "object" || !modelData.mission) return ""
                                                        var m = modelData.mission
                                                        var idx = m.indexOf("|")
                                                        return idx !== -1 ? m.substring(idx + 1).trim() : m
                                                    }
                                                    visible: text !== ""
                                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                                    font.pixelSize: 14
                                                    font.family: "D-DIN"
                                                    font.bold: true
                                                    width: parent.width
                                                    wrapMode: Text.Wrap
                                                }

                                                Text {
                                                    id: narrativeText
                                                    // Handle both structured object and legacy string
                                                    text: (typeof modelData === "object" && modelData.text) ? modelData.text : modelData
                                                    Layout.fillWidth: true
                                                    wrapMode: Text.Wrap
                                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                                    font.pixelSize: 14
                                                    font.family: "D-DIN"
                                                    font.bold: true
                                                    lineHeight: 1.2
                                                }

                                                Flow {
                                                    Layout.fillWidth: true
                                                    spacing: 6
                                                    visible: typeof modelData === "object" && (modelData.status || modelData.orbit || modelData.rocket || modelData.landing_location)

                                                    // Mission Status Tag
                                                    Rectangle {
                                                        width: statusLabel.implicitWidth + 12
                                                        height: 18
                                                        color: root.getStatusColor(modelData.status)
                                                        radius: 9
                                                        visible: !!modelData.status
                                                        Text {
                                                            id: statusLabel
                                                            text: modelData.status || ""
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: "white"
                                                            anchors.centerIn: parent
                                                        }
                                                    }

                                                    // Rocket Tag
                                                    Rectangle {
                                                        width: rocketLabel.implicitWidth + 12
                                                        height: 18
                                                        color: backend.theme === "dark" ? "#444444" : "#dddddd"
                                                        radius: 9
                                                        visible: !!modelData.rocket
                                                        Text {
                                                            id: rocketLabel
                                                            text: modelData.rocket || ""
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: backend.theme === "dark" ? "white" : "black"
                                                            anchors.centerIn: parent
                                                        }
                                                    }

                                                    // Orbit Tag
                                                    Rectangle {
                                                        width: orbitLabel.implicitWidth + 12
                                                        height: 18
                                                        color: backend.theme === "dark" ? "#444444" : "#dddddd"
                                                        radius: 9
                                                        visible: !!modelData.orbit
                                                        Text {
                                                            id: orbitLabel
                                                            text: modelData.orbit || ""
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: backend.theme === "dark" ? "white" : "black"
                                                            anchors.centerIn: parent
                                                        }
                                                    }

                                                    // Landing Location Tag
                                                    Rectangle {
                                                        width: landingLabel.implicitWidth + 12
                                                        height: 18
                                                        color: backend.theme === "dark" ? "#444444" : "#dddddd"
                                                        radius: 9
                                                        visible: !!modelData.landing_location
                                                        Text {
                                                            id: landingLabel
                                                            text: (modelData.landing_type ? (modelData.landing_type + ": ") : "") + (modelData.landing_location || "")
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: backend.theme === "dark" ? "white" : "black"
                                                            anchors.centerIn: parent
                                                        }
                                                    }

                                                    // Pad Tag
                                                    Rectangle {
                                                        width: padLabel.implicitWidth + 12
                                                        height: 18
                                                        color: backend.theme === "dark" ? "#444444" : "#dddddd"
                                                        radius: 9
                                                        visible: !!modelData.pad
                                                        Text {
                                                            id: padLabel
                                                            text: modelData.pad || ""
                                                            font.pixelSize: 10
                                                            font.bold: true
                                                            color: backend.theme === "dark" ? "white" : "black"
                                                            anchors.centerIn: parent
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        // Subtle separator
                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            height: 1
                                            color: (backend && backend.theme === "dark") ? "#33ffffff" : "#33000000"
                                            visible: ListView.view && index < ListView.view.count - 1
                                        }
                                    }
                                }

                                // Bottom fade-out effect
                                Rectangle {
                                    id: narrativeBottomFade
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 40
                                    z: 10
                                    enabled: false
                                    visible: narrativeTray.height > 60
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: "transparent" }
                                        GradientStop { 
                                            position: 1.0; 
                                            color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0" 
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Right side controls - consistent spacing
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    spacing: 8

                    Rectangle {
                    width: 28
                    height: 28
                    radius: 14
                    color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                    border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "\uf021"
                        font.family: "Font Awesome 5 Free"
                        font.pixelSize: 12
                        color: (backend && backend.theme === "dark") ? "white" : "black"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            console.log("Update clicked - showing update dialog")
                            if (backend) backend.show_update_dialog()
                        }
                    }

                    ToolTip {
                        text: (backend && backend.updateAvailable) ? "Update Available - Click to Update and Reboot" : "Update and Reboot"
                        delay: 500
                    }

                    // Red dot indicator for available updates
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: "#FF4444"
                        border.color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                        border.width: 1
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.topMargin: -2
                        anchors.rightMargin: -2
                        visible: !!(backend && backend.updateAvailable)
                    }
                }

                    // Display Settings icon (formerly Brightness)
                    Rectangle {
                        width: 28
                        height: 28
                        radius: 14
                        color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                        border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1
                        visible: !!(backend && backend.isHighResolution)

                        Text {
                            anchors.centerIn: parent
                            text: "\uf185"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            font.weight: Font.Black
                            color: (backend && backend.theme === "dark") ? "white" : "black"
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                openSettingsPopup(0)
                            }
                        }

                        Popup {
                            id: displaySettingsPopup
                            parent: root.contentItem
                            width: Math.min(760, Math.max(520, root.width - 24))
                            height: Math.min(420, Math.max(250, root.height - 24))
                            x: Math.max(12, Math.floor((root.width - width) / 2))
                            y: Math.max(12, Math.floor((root.height - height) / 2))
                            padding: 0
                            modal: true
                            focus: true
                            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                            readonly property color settingsTileColor: (backend && backend.theme === "dark") ? "#c0181818" : "#d9ebebeb"
                            readonly property color settingsTileBorder: "transparent"
                            background: Rectangle {
                                color: (backend && backend.theme === "dark") ? "#dd111111" : "#e8f5f5f5"
                                radius: 20
                                border.width: 0
                                layer.enabled: true
                            }

                            RowLayout {
                                anchors.fill: parent
                                spacing: 0

                                Rectangle {
                                    Layout.fillHeight: true
                                    Layout.preferredWidth: 180
                                    color: (backend && backend.theme === "dark") ? "#c0181818" : "#d9ebebeb"
                                    radius: 20

                                    Rectangle {
                                        anchors.right: parent.right
                                        height: parent.height
                                        width: 20
                                        color: parent.color
                                    }

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 8

                                        Text {
                                            text: "Settings"
                                            color: (backend && backend.theme === "dark") ? "#cccccc" : "#444"
                                            font.pixelSize: 13
                                            font.bold: true
                                            Layout.leftMargin: 8
                                            Layout.topMargin: 6
                                            Layout.bottomMargin: 8
                                        }

                                        Repeater {
                                            model: [
                                                { label: "Updates", icon: "\uf062", idx: 1 },
                                                { label: "Appearance", icon: "\uf53f", idx: 0 }
                                            ]

                                            delegate: Rectangle {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 44
                                                radius: 10
                                                color: settingsCategoryStack.currentIndex === modelData.idx ?
                                                       ((backend && backend.theme === "dark") ? "#2a2a2a" : "#dcdcdc") : "transparent"

                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.leftMargin: 12
                                                    anchors.rightMargin: 12
                                                    spacing: 10

                                                    Text {
                                                        text: modelData.icon
                                                        font.family: "Font Awesome 5 Free"
                                                        font.pixelSize: 14
                                                        font.weight: Font.Black
                                                        color: settingsCategoryStack.currentIndex === modelData.idx ? "#3e6ae1" : ((backend && backend.theme === "dark") ? "#888" : "#666")
                                                    }
                                                    Text {
                                                        text: modelData.label
                                                        color: settingsCategoryStack.currentIndex === modelData.idx ? ((backend && backend.theme === "dark") ? "white" : "black") : ((backend && backend.theme === "dark") ? "#bbbbbb" : "#555")
                                                        font.pixelSize: 13
                                                        font.bold: true
                                                    }
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    onClicked: settingsCategoryStack.currentIndex = modelData.idx
                                                }
                                            }
                                        }

                                        Item { Layout.fillHeight: true }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.margins: 20
                                    spacing: 12

                                    RowLayout {
                                        Layout.fillWidth: true

                                        Text {
                                            text: settingsCategoryStack.currentIndex === 0 ? "Appearance" : "Updates"
                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                            font.pixelSize: 22
                                            font.bold: true
                                        }

                                        Text {
                                            visible: settingsCategoryStack.currentIndex === 1
                                            text: "• Last checked: " + (backend ? backend.lastUpdateCheckTime : "Never")
                                            font.pixelSize: 10
                                            color: (backend && backend.theme === "dark") ? "#cccccc" : "#666666"
                                            Layout.leftMargin: 8
                                        }

                                        Item { Layout.fillWidth: true }

                                        Rectangle {
                                            width: 34
                                            height: 34
                                            radius: 17
                                            color: "transparent"

                                            Text {
                                                anchors.centerIn: parent
                                                text: "\uf00d"
                                                font.family: "Font Awesome 5 Free"
                                                font.pixelSize: 16
                                                font.weight: Font.Black
                                                color: (backend && backend.theme === "dark") ? "#888" : "#666"
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                onClicked: displaySettingsPopup.close()
                                            }
                                        }
                                    }

                                    StackLayout {
                                        id: settingsCategoryStack
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true

                                        ColumnLayout {
                                            spacing: 10

                                            Text {
                                                text: "Launch Banner"
                                                color: (backend && backend.theme === "dark") ? "#bfbfbf" : "#666"
                                                font.pixelSize: 12
                                                font.bold: true
                                            }

                                            GridLayout {
                                                columns: 1
                                                Layout.fillWidth: true
                                                columnSpacing: 8
                                                rowSpacing: 8

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 112
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 10

                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            spacing: 10

                                                            Text {
                                                                text: "\uf06e"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 15
                                                                color: "#FF9800"
                                                                Layout.preferredWidth: 18
                                                            }

                                                            ColumnLayout {
                                                                Layout.fillWidth: true
                                                                spacing: 1

                                                                Text {
                                                                    text: "Launch Banner Visibility"
                                                                    font.pixelSize: 12
                                                                    font.bold: true
                                                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                                                }
                                                                Text {
                                                                    text: backend.launchTrayMode === "always" ? "Always visible" : (backend.launchTrayMode === "hidden" ? "Always hidden" : "Show only when relevant")
                                                                    font.pixelSize: 10
                                                                    color: (backend && backend.theme === "dark") ? "#b3b3b3" : "#666"
                                                                }
                                                            }
                                                        }

                                                        Rectangle {
                                                            Layout.fillWidth: true
                                                            Layout.preferredHeight: 34
                                                            radius: 8
                                                            color: (backend && backend.theme === "dark") ? "#442d2d2d" : "#33bcbcbc"
                                                            border.width: 1
                                                            border.color: (backend && backend.theme === "dark") ? "#55ffffff" : "#33000000"

                                                            RowLayout {
                                                                anchors.fill: parent
                                                                anchors.margins: 2
                                                                spacing: 2

                                                                Repeater {
                                                                    model: [
                                                                        { label: "Always", value: "always" },
                                                                        { label: "Automatic", value: "automatic" },
                                                                        { label: "Hidden", value: "hidden" }
                                                                    ]

                                                                    delegate: Rectangle {
                                                                        Layout.fillWidth: true
                                                                        Layout.fillHeight: true
                                                                        radius: 6
                                                                        color: (backend && backend.launchTrayMode === modelData.value)
                                                                               ? ((backend && backend.theme === "dark") ? "#3e6ae1" : "#5f87f0")
                                                                               : "transparent"

                                                                        Text {
                                                                            anchors.centerIn: parent
                                                                            text: modelData.label
                                                                            font.pixelSize: 10
                                                                            font.bold: true
                                                                            color: (backend && backend.launchTrayMode === modelData.value)
                                                                                   ? "white"
                                                                                   : ((backend && backend.theme === "dark") ? "#c7c7c7" : "#555")
                                                                        }

                                                                        MouseArea {
                                                                            anchors.fill: parent
                                                                            cursorShape: Qt.PointingHandCursor
                                                                            onClicked: backend.setLaunchTrayMode(modelData.value)
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            Item { Layout.fillHeight: true }
                                        }

                                        ColumnLayout {
                                            spacing: 10

                                            GridLayout {
                                                columns: 3
                                                Layout.fillWidth: true
                                                columnSpacing: 10
                                                rowSpacing: 10

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 104
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf126"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                color: "#2196F3"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: "CURRENT"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#8faad8" : "#5577aa"
                                                            }
                                                        }

                                                        Text {
                                                            text: (backend && backend.currentVersionInfo ? (backend.currentVersionInfo.short_hash || "Unknown") : "Unknown")
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            elide: Text.ElideRight
                                                            Layout.fillWidth: true
                                                        }

                                                        Text {
                                                            text: "Installed build"
                                                            font.pixelSize: 10
                                                            color: (backend && backend.theme === "dark") ? "#a9a9a9" : "#666"
                                                        }
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 104
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf062"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                color: "#4CAF50"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: "LATEST"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#8fd3a2" : "#4f8e5d"
                                                            }
                                                        }

                                                        Text {
                                                            text: (backend && backend.latestVersionInfo ? (backend.latestVersionInfo.short_hash || "Unknown") : "Unknown")
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            elide: Text.ElideRight
                                                            Layout.fillWidth: true
                                                        }

                                                        Text {
                                                            text: (backend && backend.updateAvailable) ? "Ready to install" : "No newer build detected"
                                                            font.pixelSize: 10
                                                            color: (backend && backend.updateAvailable) ? "#4CAF50" : ((backend && backend.theme === "dark") ? "#a9a9a9" : "#666")
                                                        }
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 104
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf121"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                color: backend.targetBranch === "master" ? "#2196F3" : "#FF9800"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: "CHANNEL"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#c1a07e" : "#8a6442"
                                                            }
                                                        }

                                                        Text {
                                                            text: backend.targetBranch === "master" ? "Stable" : "Beta"
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                        }

                                                        Rectangle {
                                                            Layout.fillWidth: true
                                                            Layout.preferredHeight: 30
                                                            radius: 7
                                                            color: (backend && backend.theme === "dark") ? "#442d2d2d" : "#33bcbcbc"
                                                            border.width: 1
                                                            border.color: (backend && backend.theme === "dark") ? "#55ffffff" : "#33000000"

                                                            RowLayout {
                                                                anchors.fill: parent
                                                                anchors.margins: 2
                                                                spacing: 2

                                                                Repeater {
                                                                    model: [
                                                                        { label: "Stable", value: "master" },
                                                                        { label: "Beta", value: "beta" }
                                                                    ]

                                                                    delegate: Rectangle {
                                                                        Layout.fillWidth: true
                                                                        Layout.fillHeight: true
                                                                        radius: 5
                                                                        color: backend.targetBranch === modelData.value
                                                                               ? (modelData.value === "master" ? "#2196F3" : "#FF9800")
                                                                               : "transparent"

                                                                        Text {
                                                                            anchors.centerIn: parent
                                                                            text: modelData.label
                                                                            font.pixelSize: 10
                                                                            font.bold: true
                                                                            color: backend.targetBranch === modelData.value
                                                                                   ? "white"
                                                                                   : ((backend && backend.theme === "dark") ? "#c7c7c7" : "#555")
                                                                        }

                                                                        MouseArea {
                                                                            anchors.fill: parent
                                                                            cursorShape: Qt.PointingHandCursor
                                                                            onClicked: backend.setTargetBranch(modelData.value)
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 108
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10
                                                    opacity: (backend && backend.updateChecking) ? 0.82 : 1.0

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf021"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                font.weight: Font.Black
                                                                color: "#3e6ae1"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: backend.updateChecking ? "BUSY" : "ACTION"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#9fb1d9" : "#5670a8"
                                                            }
                                                        }

                                                        Text {
                                                            text: backend.updateChecking ? "Checking…" : "Check for Updates"
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            Layout.fillWidth: true
                                                            wrapMode: Text.WordWrap
                                                            maximumLineCount: 2
                                                        }

                                                        Text {
                                                            text: "Poll GitHub for the newest dashboard build"
                                                            font.pixelSize: 10
                                                            wrapMode: Text.WordWrap
                                                            color: (backend && backend.theme === "dark") ? "#a9a9a9" : "#666"
                                                            Layout.fillWidth: true
                                                        }
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: backend.updateChecking ? Qt.ArrowCursor : Qt.PointingHandCursor
                                                        enabled: !backend.updateChecking
                                                        onClicked: backend.checkForUpdatesNow()
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 108
                                                    color: (backend && backend.updateAvailable)
                                                           ? ((backend && backend.theme === "dark") ? "#2f4f3a" : "#4CAF50")
                                                           : displaySettingsPopup.settingsTileColor
                                                    border.color: (backend && backend.updateAvailable) ? "#4CAF50" : "transparent"
                                                    border.width: 1
                                                    radius: 10
                                                    opacity: {
                                                        var current = (backend && backend.currentVersionInfo) ? backend.currentVersionInfo.hash : ""
                                                        var latest = (backend && backend.latestVersionInfo) ? backend.latestVersionInfo.hash : ""
                                                        var ready = current && latest && current !== "Unknown" && latest !== "Unknown" && current !== latest
                                                        return ready ? 1.0 : 0.55
                                                    }

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf062"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                font.weight: Font.Black
                                                                color: "#4CAF50"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: "INSTALL"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#a6ddb4" : "#4f8e5d"
                                                            }
                                                        }

                                                        Text {
                                                            text: "Update Now"
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.updateAvailable)
                                                                   ? "white"
                                                                   : ((backend && backend.theme === "dark") ? "white" : "black")
                                                            Layout.fillWidth: true
                                                            wrapMode: Text.WordWrap
                                                            maximumLineCount: 2
                                                        }

                                                        Text {
                                                            text: (backend && backend.updateAvailable)
                                                                  ? "Install the latest checked build and close settings"
                                                                  : "Available after a newer build is found"
                                                            font.pixelSize: 10
                                                            wrapMode: Text.WordWrap
                                                            color: (backend && backend.updateAvailable) ? "#d9f2df" : ((backend && backend.theme === "dark") ? "#a9a9a9" : "#666")
                                                            Layout.fillWidth: true
                                                        }
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: {
                                                            var current = (backend && backend.currentVersionInfo) ? backend.currentVersionInfo.hash : ""
                                                            var latest = (backend && backend.latestVersionInfo) ? backend.latestVersionInfo.hash : ""
                                                            var ready = current && latest && current !== "Unknown" && latest !== "Unknown" && current !== latest
                                                            return ready ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                        }
                                                        enabled: {
                                                            var current = (backend && backend.currentVersionInfo) ? backend.currentVersionInfo.hash : ""
                                                            var latest = (backend && backend.latestVersionInfo) ? backend.latestVersionInfo.hash : ""
                                                            return current && latest && current !== "Unknown" && latest !== "Unknown" && current !== latest
                                                        }
                                                        onClicked: {
                                                            backend.runUpdateScript()
                                                            displaySettingsPopup.close()
                                                        }
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 108
                                                    color: displaySettingsPopup.settingsTileColor
                                                    border.color: displaySettingsPopup.settingsTileBorder
                                                    border.width: 1
                                                    radius: 10

                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: 12
                                                        spacing: 8

                                                        RowLayout {
                                                            Layout.fillWidth: true

                                                            Text {
                                                                text: "\uf011"
                                                                font.family: "Font Awesome 5 Free"
                                                                font.pixelSize: 13
                                                                font.weight: Font.Black
                                                                color: "#FF7043"
                                                            }

                                                            Item { Layout.fillWidth: true }

                                                            Text {
                                                                text: "DEVICE"
                                                                font.pixelSize: 9
                                                                font.bold: true
                                                                color: (backend && backend.theme === "dark") ? "#ddb39f" : "#996651"
                                                            }
                                                        }

                                                        Text {
                                                            text: "Restart"
                                                            font.pixelSize: 13
                                                            font.bold: true
                                                            color: (backend && backend.theme === "dark") ? "white" : "black"
                                                            Layout.fillWidth: true
                                                            wrapMode: Text.WordWrap
                                                            maximumLineCount: 2
                                                        }

                                                        Text {
                                                            text: "Reboot the device running the dashboard"
                                                            font.pixelSize: 10
                                                            wrapMode: Text.WordWrap
                                                            color: (backend && backend.theme === "dark") ? "#a9a9a9" : "#666"
                                                            Layout.fillWidth: true
                                                        }
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: backend.reboot_device()
                                                    }
                                                }
                                            }

                                            Item { Layout.fillHeight: true }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter
                        radius: 14
                        color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: backend.wifiConnected ? "\uf1eb" : "\uf071"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.wifiConnected ? "#4CAF50" : "#F44336"
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                console.log("WiFi clicked - opening popup")
                                wifiPopup.open()
                                console.log("WiFi popup opened, visible:", wifiPopup.visible)
                            }
                        }
                    }

                    // Location Selector (Relocated and Restyled)
                    Rectangle {
                        id: locationTrigger
                        Layout.preferredWidth: Math.max(80, locationLabel.implicitWidth + 24)
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter
                        radius: 14
                        color: "transparent"
                        clip: false

                        // Fading background for the location trigger bar
                        Rectangle {
                            id: locationTriggerBackground
                            anchors.fill: parent
                            radius: 14
                            color: backend.theme === "dark" ? "#181818" : "#f5f5f5"
                            border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                            border.width: 1
                            z: 0
                            // Fade out as drawer expands
                            opacity: 1.0 - Math.min(1.0, locationDrawer.height / 64.0)
                        }

                        // Sliding Location Selector Tray
                        Popup {
                            id: locationDrawer
                            x: 0
                            width: parent.width
                            height: 0
                            // Sit at the bottom and grow UP, covering the trigger area
                            y: parent.height - height
                            modal: false
                            focus: false
                            visible: height > 0
                            closePolicy: Popup.CloseOnPressOutside
                            onClosed: height = 0
                            padding: 0
                            
                            property real expandedHeight: 160
                            property bool isDragging: false
                            opacity: height / expandedHeight
                            
                            Behavior on height {
                                enabled: !locationDrawer.isDragging && (locationListView ? !locationListView.dragging : true)
                                NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                            }
                            
                            background: Item {
                                Rectangle {
                                    anchors.fill: parent
                                    color: (backend && backend.theme === "dark") ? "#181818" : "#f5f5f5"
                                    radius: 14
                                    border.width: 1
                                    border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                                }
                            }
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 0
                                spacing: 0
                                
                                // Drag Handle (Top of tray)
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 25
                                    color: "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uf078"
                                        font.family: "Font Awesome 5 Free"
                                        font.pixelSize: 12
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        
                                        property point startGlobalPos: Qt.point(0, 0)
                                        property real startHeight: 0
                                        property bool isDragging: false
                                        property bool moved: false
                                        
                                        onPressed: {
                                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            startHeight = locationDrawer.height
                                            locationDrawer.isDragging = true
                                            moved = false
                                        }
                                        
                                        onPositionChanged: {
                                            if (locationDrawer.isDragging && pressed) {
                                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                                // Dragging DOWN decreases height
                                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                                if (Math.abs(deltaY) > 5) moved = true
                                                var newHeight = startHeight - deltaY
                                                newHeight = Math.max(0, Math.min(locationDrawer.expandedHeight, newHeight))
                                                locationDrawer.height = newHeight
                                            }
                                        }
                                        
                                        onReleased: {
                                            locationDrawer.isDragging = false
                                            if (moved) {
                                                var threshold = locationDrawer.expandedHeight * 0.2
                                                var closedThreshold = threshold
                                                var openThreshold = locationDrawer.expandedHeight - threshold
                                                
                                                if (startHeight < locationDrawer.expandedHeight * 0.5) {
                                                    if (locationDrawer.height > closedThreshold) {
                                                        locationDrawer.height = locationDrawer.expandedHeight
                                                    } else {
                                                        locationDrawer.height = 0
                                                    }
                                                } else {
                                                    if (locationDrawer.height < openThreshold) {
                                                        locationDrawer.height = 0
                                                    } else {
                                                        locationDrawer.height = locationDrawer.expandedHeight
                                                    }
                                                }
                                            }
                                        }

                                        onClicked: {
                                            if (!moved) {
                                                // Tap to close: if mostly open, close it.
                                                if (locationDrawer.height > locationDrawer.expandedHeight * 0.5) {
                                                    locationDrawer.height = 0
                                                } else {
                                                    locationDrawer.height = locationDrawer.expandedHeight
                                                }
                                            }
                                        }
                                    }
                                }
                                
                                ListView {
                                    id: locationListView
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    Layout.margins: 0
                                    clip: true
                                    model: ["Starbase", "Vandy", "Cape", "Hawthorne"]
                                    spacing: 2
                                    interactive: true
                                    boundsBehavior: Flickable.StopAtBounds
                                    flickableDirection: Flickable.VerticalFlick

                                    property real dragStartY: 0

                                    DragHandler {
                                        id: locationListDrag
                                        target: null
                                        xAxis.enabled: false
                                        onActiveChanged: {
                                            if (active) {
                                                if (locationListView.contentY <= 0) {
                                                    locationDrawer.isDragging = true
                                                    locationListView.dragStartY = centroid.scenePosition.y
                                                }
                                            } else {
                                                if (locationDrawer.isDragging) {
                                                    locationDrawer.isDragging = false
                                                    if (locationDrawer.height < locationDrawer.expandedHeight) {
                                                        if (locationDrawer.height < locationDrawer.expandedHeight * 0.8) {
                                                            locationDrawer.height = 0
                                                        } else {
                                                            locationDrawer.height = locationDrawer.expandedHeight
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                        onCentroidChanged: {
                                            if (locationDrawer.isDragging) {
                                                var delta = centroid.scenePosition.y - locationListView.dragStartY
                                                if (delta > 0) {
                                                    locationDrawer.height = Math.max(0, locationDrawer.expandedHeight - delta)
                                                } else {
                                                    locationDrawer.height = locationDrawer.expandedHeight
                                                }
                                            } else if (locationListView.dragging && locationListView.contentY <= 0 && centroid.scenePosition.y > locationListView.dragStartY) {
                                                locationDrawer.isDragging = true
                                                locationListView.dragStartY = centroid.scenePosition.y
                                            }
                                        }
                                    }
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 30
                                        color: backend.location === modelData ? 
                                               (backend.theme === "dark" ? "#303030" : "#e0e0e0") : 
                                               "transparent"
                                        radius: 4
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 14
                                            font.family: "D-DIN"
                                            font.bold: true
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: {
                                                backend.location = modelData
                                                locationDrawer.height = 0
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Bottom fade-out effect
                            Rectangle {
                                id: locationBottomFade
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                height: 30
                                z: 10
                                enabled: false
                                visible: locationDrawer.height > 40
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: "transparent" }
                                    GradientStop { 
                                        position: 1.0; 
                                        color: (backend && backend.theme === "dark") ? "#181818" : "#f5f5f5"
                                    }
                                }
                            }
                        }

                        Text {
                            id: locationLabel
                            anchors.centerIn: parent
                            text: backend.location
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            font.bold: true
                            // Fade out as drawer expands
                            opacity: 1.0 - Math.min(1.0, locationDrawer.height / 64.0)
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            
                            property point startGlobalPos: Qt.point(0, 0)
                            property real startHeight: 0
                            property bool moved: false
                            
                            onPressed: {
                                startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                if (locationDrawer.height === 0) locationDrawer.height = 1
                                startHeight = locationDrawer.height
                                locationDrawer.isDragging = true
                                moved = false
                            }
                            
                            onPositionChanged: {
                                if (locationDrawer.isDragging && pressed) {
                                    var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                    var deltaY = currentGlobalPos.y - startGlobalPos.y
                                    if (Math.abs(deltaY) > 5) moved = true
                                    var newHeight = startHeight - deltaY
                                    newHeight = Math.max(0, Math.min(locationDrawer.expandedHeight, newHeight))
                                    locationDrawer.height = newHeight
                                }
                            }
                            
                            onReleased: {
                                locationDrawer.isDragging = false
                                if (moved) {
                                    var threshold = locationDrawer.expandedHeight * 0.2
                                    var closedThreshold = threshold
                                    var openThreshold = locationDrawer.expandedHeight - threshold
                                    
                                    if (startHeight < locationDrawer.expandedHeight * 0.5) {
                                        if (locationDrawer.height > closedThreshold) {
                                            locationDrawer.height = locationDrawer.expandedHeight
                                        } else {
                                            locationDrawer.height = 0
                                        }
                                    } else {
                                        if (locationDrawer.height < openThreshold) {
                                            locationDrawer.height = 0
                                        } else {
                                            locationDrawer.height = locationDrawer.expandedHeight
                                        }
                                    }
                                }
                            }
                            
                            onClicked: {
                                if (!moved) {
                                    // Toggle logic: if mostly closed, open it; if mostly open, close it.
                                    if (locationDrawer.height > locationDrawer.expandedHeight * 0.5) {
                                        locationDrawer.height = 0
                                    } else {
                                        locationDrawer.height = locationDrawer.expandedHeight
                                    }
                                }
                            }
                        }

                        ToolTip {
                            text: "Location: " + backend.location + " (Click or Drag up to change)"
                            delay: 500
                        }
                    }

                    // Theme Toggle Switch (Restyled to align with themes)
                    Rectangle {
                        id: themeToggle
                        Layout.preferredWidth: 50
                        Layout.preferredHeight: 28
                        radius: 14
                        color: backend.theme === "dark" ? "#1a1a1b" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#333" : "#e0e0e0"
                        border.width: 1
                        Behavior on color { ColorAnimation { duration: 200 } }

                        Text {
                            text: "\uf185" // Sun
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.theme === "light" ? "#f1c40f" : "#555555"
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: backend.theme === "light" ? 1.0 : 0.5
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }

                        Text {
                            text: "\uf186" // Moon
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.theme === "dark" ? "#f5f5f5" : "#888888"
                            anchors.right: parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: backend.theme === "dark" ? 1.0 : 0.5
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }

                        Rectangle {
                            id: themeThumb
                            width: 26
                            height: 26
                            radius: 13
                            color: "white"
                            border.color: backend.theme === "dark" ? "#444" : "#ccc"
                            border.width: 1
                            x: backend.theme === "dark" ? parent.width - width - 3 : 3
                            y: 3
                            Behavior on x { NumberAnimation { duration: 250; easing.type: Easing.InOutQuad } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: backend.theme = (backend.theme === "dark" ? "light" : "dark")
                        }

                        ToolTip {
                            text: backend.theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"
                            delay: 500
                        }
                    }

                }

                // Right pill (countdown) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 120
                    Layout.maximumWidth: 120
                    Layout.preferredHeight: 28
                    Layout.alignment: Qt.AlignVCenter
                    radius: 14
                    color: backend.isNearLaunch ? "#CC0000" : (backend.theme === "dark" ? "#181818" : "#f0f0f0")
                    border.color: backend.isNearLaunch ? "transparent" : (backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0")
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: backend.countdown
                        color: backend.isNearLaunch ? "white" : ((backend && backend.theme === "dark") ? "white" : "black")
                        font.pixelSize: 14
                        font.family: "D-DIN"
                        font.bold: true
                        // Use tabular numbers to prevent jitter as the clock ticks
                        font.features: { "tnum": 1 }
                        // Fade out as tray expands
                        opacity: 1.0 - Math.min(1.0, countdownTray.height / 56.0)
                    }

                    // Sliding Countdown Tray
                    Popup {
                        id: countdownTray
                        x: parent.width - width
                        width: parent.width
                        height: 0
                        y: parent.height - height
                        modal: false
                        focus: false
                        visible: height > 0
                        closePolicy: Popup.CloseOnPressOutside
                        onClosed: height = 0
                        padding: 0
                        
                        property real expandedHeight: 180
                        property bool isDragging: false
                        opacity: height / expandedHeight
                        
                        Behavior on height {
                            enabled: !countdownTray.isDragging
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                        
                        background: Item {
                            Rectangle {
                                anchors.fill: parent
                                color: (backend && backend.theme === "dark") ? "#181818" : "#f0f0f0"
                                radius: 14
                                border.width: 1
                                border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                            }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            spacing: 0
                            
                            // Drag Handle (Top of tray)
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 25
                                color: "transparent"
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uf078"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: 12
                                    color: backend.theme === "dark" ? "white" : "black"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    
                                    property point startGlobalPos: Qt.point(0, 0)
                                    property real startHeight: 0
                                    property bool moved: false
                                    
                                    onPressed: {
                                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                        startHeight = countdownTray.height
                                        countdownTray.isDragging = true
                                        moved = false
                                    }
                                    
                                    onPositionChanged: {
                                        if (countdownTray.isDragging && pressed) {
                                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                                            if (Math.abs(deltaY) > 5) moved = true
                                            var newHeight = startHeight - deltaY
                                            newHeight = Math.max(0, Math.min(countdownTray.expandedHeight, newHeight))
                                            countdownTray.height = newHeight
                                        }
                                    }
                                    
                                    onReleased: {
                                        countdownTray.isDragging = false
                                        if (moved) {
                                            var threshold = countdownTray.expandedHeight * 0.2
                                            if (startHeight < countdownTray.expandedHeight * 0.5) {
                                                countdownTray.height = countdownTray.height > threshold ? countdownTray.expandedHeight : 0
                                            } else {
                                                countdownTray.height = countdownTray.height < (countdownTray.expandedHeight - threshold) ? 0 : countdownTray.expandedHeight
                                            }
                                        }
                                    }
                                    onClicked: {
                                        if (!moved) {
                                            countdownTray.height = countdownTray.height > countdownTray.expandedHeight * 0.5 ? 0 : countdownTray.expandedHeight
                                        }
                                    }
                                }
                            }
                            
                            // Content
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.margins: 10
                                Layout.topMargin: 0
                                spacing: 10

                                Text {
                                    text: (backend.countdownBreakdown.prefix || "T-") + " " + (backend.countdownBreakdown.label || "LAUNCH")
                                    color: backend.theme === "dark" ? "#aaa" : "#666"
                                    font.pixelSize: 12
                                    font.family: "D-DIN"
                                    font.bold: true
                                    Layout.alignment: Qt.AlignHCenter
                                }

                                GridLayout {
                                    columns: 2
                                    Layout.fillWidth: true
                                    columnSpacing: 0
                                    rowSpacing: 10

                                    // Days
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            text: backend.countdownBreakdown.days
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 28
                                            font.family: "D-DIN"
                                            font.bold: true
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            text: "DAYS"
                                            color: backend.theme === "dark" ? "#888" : "#999"
                                            font.pixelSize: 10
                                            font.family: "D-DIN"
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                    // Hours
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            text: backend.countdownBreakdown.hours
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 28
                                            font.family: "D-DIN"
                                            font.bold: true
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            text: "HOURS"
                                            color: backend.theme === "dark" ? "#888" : "#999"
                                            font.pixelSize: 10
                                            font.family: "D-DIN"
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                    // Minutes
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            text: backend.countdownBreakdown.minutes
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 28
                                            font.family: "D-DIN"
                                            font.bold: true
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            text: "MINUTES"
                                            color: backend.theme === "dark" ? "#888" : "#999"
                                            font.pixelSize: 10
                                            font.family: "D-DIN"
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                    // Seconds
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            text: backend.countdownBreakdown.seconds
                                            color: backend.theme === "dark" ? "white" : "black"
                                            font.pixelSize: 28
                                            font.family: "D-DIN"
                                            font.bold: true
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                        Text {
                                            text: "SECONDS"
                                            color: backend.theme === "dark" ? "#888" : "#999"
                                            font.pixelSize: 10
                                            font.family: "D-DIN"
                                            Layout.alignment: Qt.AlignHCenter
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // MouseArea for the pill to open the tray
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        
                        property point startGlobalPos: Qt.point(0, 0)
                        property real startHeight: 0
                        property bool moved: false
                        
                        onPressed: {
                            if (countdownTray.height === 0) countdownTray.height = 1
                            startHeight = countdownTray.height
                            countdownTray.isDragging = true
                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            moved = false
                        }
                        
                        onPositionChanged: {
                            if (countdownTray.isDragging && pressed) {
                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                if (Math.abs(deltaY) > 5) moved = true
                                var newHeight = startHeight - deltaY
                                newHeight = Math.max(0, Math.min(countdownTray.expandedHeight, newHeight))
                                countdownTray.height = newHeight
                            }
                        }
                        
                        onReleased: {
                            countdownTray.isDragging = false
                            if (moved) {
                                var threshold = countdownTray.expandedHeight * 0.2
                                if (startHeight < countdownTray.expandedHeight * 0.5) {
                                    countdownTray.height = countdownTray.height > threshold ? countdownTray.expandedHeight : 0
                                } else {
                                    countdownTray.height = countdownTray.height < (countdownTray.expandedHeight - threshold) ? 0 : countdownTray.expandedHeight
                                }
                            }
                        }
                        onClicked: {
                            if (!moved) {
                                if (countdownTray.height > 0) countdownTray.height = 0
                                else countdownTray.height = countdownTray.expandedHeight
                            }
                        }
                    }
                }
            }
        }
    }

    // WiFi popup
        Popup {
            id: wifiPopup
            width: 450
            height: 240
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            property string selectedNetwork: ""

            onOpened: backend.startWifiTimer()
            onClosed: backend.stopWifiTimer()

            background: Rectangle {
                color: backend.theme === "dark" ? "#cc181818" : "#ccf5f5f5"
                topLeftRadius: 0
                topRightRadius: 8
                bottomLeftRadius: 0
                bottomRightRadius: 0
                // Inner shadow approximation
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    radius: parent.radius
                    border.color: Qt.rgba(0, 0, 0, 0.1)
                    border.width: 1
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                Text {
                    text: "WiFi Networks"
                    font.pixelSize: 16
                    font.bold: true
                    color: backend.theme === "dark" ? "white" : "black"
                    Layout.alignment: Qt.AlignHCenter
                }

                // Current connection status - compact
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    color: backend.theme === "dark" ? "#111111" : "#e0e0e0"
                    radius: 4

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 5
                        spacing: 5

                        Text {
                            text: backend.wifiConnected ? "\uf1eb" : "\uf6ab"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.wifiConnected ? "#4CAF50" : "#F44336"
                        }

                        Text {
                            text: backend.wifiConnected ? ("Connected: " + backend.currentWifiSsid) : "Not connected"
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 11
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        Button {
                            text: "Disconnect"
                            visible: !!(backend && backend.wifiConnected)
                            Layout.preferredWidth: 60
                            Layout.preferredHeight: 20
                            onClicked: {
                                backend.disconnectWifi()
                                wifiPopup.close()
                            }
                            background: Rectangle {
                                color: "#F44336"
                                radius: 3
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                font.pixelSize: 9
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // Scan button - compact
                Button {
                    text: backend.wifiScanInProgress ? "Scanning..." : (backend.wifiConnecting ? "Connecting..." : "Scan Networks")
                    Layout.fillWidth: true
                    Layout.preferredHeight: 25
                    enabled: !(backend.wifiScanInProgress || backend.wifiConnecting)
                    onClicked: backend.scanWifiNetworks()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#303030" : "#d0d0d0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 11
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Scanning spinner indicator
                BusyIndicator {
                    running: !!(backend && backend.wifiScanInProgress)
                    visible: running
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredHeight: 16
                    Layout.preferredWidth: 16
                }

                // Debug info button - compact
                Button {
                    text: "Interface Info"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 18
                    onClicked: debugDialog.open()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#2a2a2a" : "#c0c0c0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                // Networks list - compact single line layout
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: backend.wifiNetworks
                    clip: true
                    spacing: 2
                    interactive: true
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 28
                        color: backend.theme === "dark" ? "#111111" : "#e0e0e0"
                        radius: 3

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 5
                            spacing: 8

                            // Network icon
                            Text {
                                text: modelData.encrypted ? "\uf023" : "\uf09c"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 12
                                color: modelData.encrypted ? "#FF9800" : "#4CAF50"
                                Layout.preferredWidth: 16
                            }

                            // Network info in one line
                            Text {
                                text: modelData.ssid + " (" + modelData.signal + " dBm)"
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 12
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            // Remove button for remembered networks
                            Button {
                                text: "\uf2ed"
                                font.family: "Font Awesome 5 Free"
                                Layout.preferredWidth: 22
                                Layout.preferredHeight: 22
                                visible: {
                                    for (var i = 0; i < backend.rememberedNetworks.length; i++) {
                                        if (backend.rememberedNetworks[i].ssid === modelData.ssid) {
                                            return true
                                        }
                                    }
                                    return false
                                }
                                onClicked: {
                                    backend.remove_remembered_network(modelData.ssid)
                                }

                                background: Rectangle {
                                    color: "#F44336"
                                    radius: 3
                                }

                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    font.pixelSize: 10
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }

                                ToolTip {
                                    text: "Remove from remembered networks"
                                    delay: 500
                                }
                            }

                            // Connect button - compact
                            Button {
                                text: "Connect"
                                Layout.preferredWidth: 55
                                Layout.preferredHeight: 22
                                onClicked: {
                                    wifiPopup.selectedNetwork = modelData.ssid
                                    // Check if this network is remembered
                                    var isRemembered = false
                                    for (var i = 0; i < backend.rememberedNetworks.length; i++) {
                                        if (backend.rememberedNetworks[i].ssid === modelData.ssid) {
                                            isRemembered = true
                                            break
                                        }
                                    }
                                    if (isRemembered) {
                                        backend.connectToRememberedNetwork(modelData.ssid)
                                    } else {
                                        passwordDialog.open()
                                    }
                                }

                                background: Rectangle {
                                    color: backend.theme === "dark" ? "#303030" : "#d0d0d0"
                                    radius: 3
                                }

                                contentItem: Text {
                                    text: parent.text
                                    color: backend.theme === "dark" ? "white" : "black"
                                    font.pixelSize: 9
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
            }
        }

        // Password dialog
        Popup {
            id: passwordDialog
            width: 320
            height: 120
            x: (parent.width - width) / 2
            y: (parent.height - height - 200) / 2  // Leave room for keyboard
            modal: true
            focus: true
            // Keep the password dialog open while interacting with the custom on-screen keyboard
            // so that tapping outside (on the keyboard) does not close it.
            closePolicy: Popup.CloseOnEscape

            onOpened: {
                passwordField.focus = true
                passwordField.text = ""
            }

            background: Rectangle {
                color: backend.theme === "dark" ? "#cc181818" : "#ccf5f5f5"
                radius: 8
                border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "Password for " + wifiPopup.selectedNetwork
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 13
                    font.bold: true
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                RowLayout {
                    spacing: 5

                    TextField {
                        id: passwordField
                        placeholderText: "Enter password"
                        echoMode: TextField.Password
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28

                        background: Rectangle {
                            color: (backend && backend.theme === "dark") ? "#111111" : "#ffffff"
                            border.color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#cccccc"
                            border.width: 1
                            radius: 3
                        }

                        color: (backend && backend.theme === "dark") ? "white" : "black"
                    }

                    Button {
                        text: "👁"
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 28
                        onClicked: {
                            passwordField.echoMode = passwordField.echoMode === TextField.Password ? TextField.Normal : TextField.Password
                            passwordField.focus = true
                        }

                        background: Rectangle {
                            color: (backend && backend.theme === "dark") ? "#2a2a2a" : "#e0e0e0"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: (backend && backend.theme === "dark") ? "white" : "black"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Cancel"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 24
                        onClicked: {
                            passwordField.text = ""
                            passwordDialog.close()
                        }

                        background: Rectangle {
                            color: (backend && backend.theme === "dark") ? "#303030" : "#d0d0d0"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: (backend && backend.theme === "dark") ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Connect"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 24
                        onClicked: {
                            backend.connectToWifi(wifiPopup.selectedNetwork, passwordField.text)
                            passwordDialog.close()
                        }

                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "white"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // Virtual Keyboard for password entry
        Popup {
            id: virtualKeyboard
            width: 480
            height: 180
            x: passwordDialog.x + passwordDialog.width / 2 - width / 2
            y: passwordDialog.y + passwordDialog.height + 5
            modal: false
            focus: false
            visible: passwordDialog.visible
            // Prevent the keyboard from auto-closing when tapping outside or interacting with other controls
            closePolicy: Popup.NoAutoClose
            // Ensure the keyboard stays above other content
            z: 2000
            property bool shiftPressed: false
            property bool numberMode: false

            onOpened: {
                // Reset keyboard state when opened
                shiftPressed = false
                numberMode = false
            }

            background: Rectangle {
                color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 5

                // QWERTY keyboard rows
                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"] : (virtualKeyboard.shiftPressed ? ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"] : ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 33
                            Layout.preferredHeight: 30
                            // Avoid stealing focus from the password field
                            focusPolicy: Qt.NoFocus
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#303030" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            contentItem: Text {
                                text: parent.text
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")"] : (virtualKeyboard.shiftPressed ? ["A", "S", "D", "F", "G", "H", "J", "K", "L"] : ["a", "s", "d", "f", "g", "h", "j", "k", "l"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 33
                            Layout.preferredHeight: 30
                            // Avoid stealing focus from the password field
                            focusPolicy: Qt.NoFocus
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#303030" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            contentItem: Text {
                                text: parent.text
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460

                    Button {
                        text: "⇧"
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 30
                        enabled: !virtualKeyboard.numberMode
                        // Avoid stealing focus from the password field
                        focusPolicy: Qt.NoFocus
                        onClicked: {
                            virtualKeyboard.shiftPressed = !virtualKeyboard.shiftPressed
                        }

                        background: Rectangle {
                            color: parent.pressed ? "#FF6B35" : (virtualKeyboard.numberMode ? (backend.theme === "dark" ? "#181818" : "#e0e0e0") : (virtualKeyboard.shiftPressed ? "#FF9800" : (backend.theme === "dark" ? "#2a2a2a" : "#c0c0c0")))
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Repeater {
                        model: virtualKeyboard.numberMode ? ["-", "_", "+", "=", "{", "}", "[", "]", "|"] : (virtualKeyboard.shiftPressed ? ["Z", "X", "C", "V", "B", "N", "M"] : ["z", "x", "c", "v", "b", "n", "m"])
                        Button {
                            text: modelData
                            Layout.preferredWidth: 33
                            Layout.preferredHeight: 30
                            // Avoid stealing focus from the password field
                            focusPolicy: Qt.NoFocus
                            onClicked: passwordField.text += text

                            background: Rectangle {
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#303030" : "#d0d0d0")
                                radius: 3
                                Behavior on color { ColorAnimation { duration: 100 } }
                            }

                            contentItem: Text {
                                text: parent.text
                                color: backend.theme === "dark" ? "white" : "black"
                                font.pixelSize: 12
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    Button {
                        text: "⌫"
                        Layout.preferredWidth: 46
                        Layout.preferredHeight: 30
                        // Avoid stealing focus from the password field
                        focusPolicy: Qt.NoFocus
                        onClicked: passwordField.text = passwordField.text.slice(0, -1)

                        background: Rectangle {
                            color: parent.pressed ? "#D84315" : "#FF5722"
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "white"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                RowLayout {
                    spacing: 3
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 460

                    Button {
                        text: virtualKeyboard.numberMode ? "ABC" : "123"
                        Layout.preferredWidth: 53
                        Layout.preferredHeight: 30
                        // Avoid stealing focus from the password field
                        focusPolicy: Qt.NoFocus
                        onClicked: {
                            virtualKeyboard.numberMode = !virtualKeyboard.numberMode
                            virtualKeyboard.shiftPressed = false  // Reset shift when switching modes
                        }

                        background: Rectangle {
                            color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#2a2a2a" : "#c0c0c0")
                            radius: 3
                            Behavior on color { ColorAnimation { duration: 100 } }
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Space"
                        Layout.preferredWidth: 267
                        Layout.preferredHeight: 30
                        // Avoid stealing focus from the password field
                        focusPolicy: Qt.NoFocus
                        onClicked: passwordField.text += " "

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#303030" : "#d0d0d0"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Done"
                        Layout.preferredWidth: 67
                        Layout.preferredHeight: 30
                        onClicked: virtualKeyboard.visible = false

                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "white"
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        // Update popup
        Popup {
            id: updatePopup
            width: 450
            height: 220
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: (backend && backend.theme === "dark") ? "#cc181818" : "#ccf5f5f5"
                topLeftRadius: 0
                topRightRadius: 8
                bottomLeftRadius: 0
                bottomRightRadius: 0
                // Inner shadow approximation
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    radius: parent.radius
                    border.color: Qt.rgba(0, 0, 0, 0.1)
                    border.width: 1
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 6

                // Title and last checked
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10

                    Text {
                        text: (backend && backend.updateAvailable) ? "Update Available" : "Software Update"
                        font.pixelSize: 15
                        font.bold: true
                        color: (backend && backend.theme === "dark") ? "white" : "black"
                    }

                    Text {
                        text: "• Last checked: " + (backend ? backend.lastUpdateCheckTime : "Never")
                        font.pixelSize: 10
                        color: (backend && backend.theme === "dark") ? "#cccccc" : "#666666"
                        Layout.alignment: Qt.AlignVCenter
                    }
                }

                // Compact Quick Options Grid (Tesla style)
                GridLayout {
                    columns: 2
                    Layout.fillWidth: true
                    columnSpacing: 8
                    rowSpacing: 6

                    // Current version
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                        color: (backend && backend.theme === "dark") ? "#111111" : "#e0e0e0"
                        radius: 6

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 6

                            Text {
                                text: "\uf126"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 12
                                color: "#2196F3"
                                Layout.preferredWidth: 15
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Text {
                                    text: "Current"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "#aaa" : "#666"
                                }
                                Text {
                                    text: (backend && backend.currentVersionInfo ? (backend.currentVersionInfo.short_hash || "Unknown") : "Unknown")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: (backend && backend.currentVersionInfo) ? (backend.currentVersionInfo.message || "") : ""
                                    font.pixelSize: 8
                                    color: (backend && backend.theme === "dark") ? "#999999" : "#777777"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    visible: text !== ""
                                }
                            }
                        }
                    }

                    // Latest version
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                        color: (backend && backend.theme === "dark") ? "#111111" : "#e0e0e0"
                        radius: 6

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 6

                            Text {
                                text: "\uf062"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 12
                                color: "#4CAF50"
                                Layout.preferredWidth: 15
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Text {
                                    text: "Latest"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "#aaa" : "#666"
                                }
                                Text {
                                    text: (backend && backend.latestVersionInfo ? (backend.latestVersionInfo.short_hash || "Unknown") : "Unknown")
                                    font.pixelSize: 10
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: (backend && backend.latestVersionInfo) ? (backend.latestVersionInfo.message || "") : ""
                                    font.pixelSize: 8
                                    color: (backend && backend.theme === "dark") ? "#999999" : "#777777"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    visible: text !== ""
                                }
                            }
                        }
                    }

                    // Launch Banner visibility (segmented control)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 74
                        color: (backend && backend.theme === "dark") ? "#111111" : "#e0e0e0"
                        radius: 6

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 5

                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: "\uf06e"
                                    font.family: "Font Awesome 5 Free"
                                    font.pixelSize: 11
                                    color: "#FF9800"
                                    Layout.preferredWidth: 14
                                }

                                Text {
                                    text: "Banner"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: backend.launchTrayMode === "always" ? "Always" : (backend.launchTrayMode === "hidden" ? "Hidden" : "Automatic")
                                    font.pixelSize: 8
                                    color: (backend && backend.theme === "dark") ? "#aaa" : "#666"
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                Repeater {
                                    model: [
                                        { label: "Always", value: "always" },
                                        { label: "Auto", value: "automatic" },
                                        { label: "Hidden", value: "hidden" }
                                    ]

                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 22
                                        radius: 5
                                        color: (backend && backend.launchTrayMode === modelData.value)
                                               ? ((backend && backend.theme === "dark") ? "#3e6ae1" : "#5f87f0")
                                               : ((backend && backend.theme === "dark") ? "#332e2e2e" : "#26aaaaaa")

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            font.pixelSize: 8
                                            font.bold: true
                                            color: (backend && backend.launchTrayMode === modelData.value)
                                                   ? "white"
                                                   : ((backend && backend.theme === "dark") ? "#c7c7c7" : "#555")
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: backend.setLaunchTrayMode(modelData.value)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Stable/Beta Selector (Tesla style tile)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                        color: (backend && backend.theme === "dark") ? "#111111" : "#e0e0e0"
                        radius: 6

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 4

                            Text {
                                text: "\uf121"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 11
                                color: backend.targetBranch === "master" ? "#2196F3" : "#FF9800"
                                Layout.preferredWidth: 14
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Text {
                                    text: "Branch"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: (backend && backend.theme === "dark") ? "white" : "black"
                                }
                                Row {
                                    spacing: 0
                                    Rectangle {
                                        width: 45
                                        height: 18
                                        color: backend.targetBranch === "master" ? "#2196F3" : (backend.theme === "dark" ? "#303030" : "#d0d0d0")
                                        radius: 4
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Stable"
                                            color: backend.targetBranch === "master" ? "white" : (backend.theme === "dark" ? "#aaa" : "#555")
                                            font.pixelSize: 9
                                            font.bold: backend.targetBranch === "master"
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: backend.setTargetBranch("master")
                                        }
                                    }
                                    Rectangle {
                                        width: 45
                                        height: 18
                                        color: backend.targetBranch === "beta" ? "#FF9800" : (backend.theme === "dark" ? "#303030" : "#d0d0d0")
                                        radius: 4
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Beta"
                                            color: backend.targetBranch === "beta" ? "white" : (backend.theme === "dark" ? "#aaa" : "#555")
                                            font.pixelSize: 9
                                            font.bold: backend.targetBranch === "beta"
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: backend.setTargetBranch("beta")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Update Now button
                RowLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 15

                    // "Update Now"
                    Button {
                        text: "Update Now"
                        Layout.preferredWidth: 105
                        Layout.preferredHeight: 26
                        Layout.alignment: Qt.AlignVCenter
                        visible: {
                            var current = backend.currentVersionInfo.hash
                            var latest = backend.latestVersionInfo.hash
                            return current && latest && current !== "Unknown" && latest !== "Unknown" && current !== latest
                        }
                        onClicked: {
                            backend.runUpdateScript()
                            updatePopup.close()
                        }

                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 3
                        }

                        contentItem: Row {
                            spacing: 6
                            anchors.centerIn: parent
                            Text {
                                text: "\uf062"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 11
                                font.weight: Font.Black
                                color: "white"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: "Update Now"
                                color: "white"
                                font.pixelSize: 11
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }

                // Buttons - compact horizontal layout
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12

                    Button {
                        text: backend.updateChecking ? "Checking..." : "Check Now"
                        Layout.preferredWidth: 80
                        Layout.preferredHeight: 28
                        enabled: !backend.updateChecking
                        onClicked: backend.checkForUpdatesNow()

                        background: Rectangle {
                            color: backend.updateChecking ?
                                (backend.theme === "dark" ? "#666" : "#ccc") :
                                (backend.theme === "dark" ? "#303030" : "#e0e0e0")
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Restart"
                        Layout.preferredWidth: 85
                        Layout.preferredHeight: 28
                        onClicked: {
                            console.log("Restart clicked")
                            backend.reboot_device()
                        }

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#303030" : "#e0e0e0"
                            radius: 3
                        }

                        contentItem: Row {
                            spacing: 6
                            anchors.centerIn: parent
                            Text {
                                text: "\uf011"
                                font.family: "Font Awesome 5 Free"
                                font.pixelSize: 11
                                font.weight: Font.Black
                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: "Restart"
                                color: (backend && backend.theme === "dark") ? "white" : "black"
                                font.pixelSize: 11
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }

                    Button {
                        text: "Cancel"
                        Layout.preferredWidth: 70
                        Layout.preferredHeight: 28
                        onClicked: updatePopup.close()

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#303030" : "#e0e0e0"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 11
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        Connections {
            target: backend
            function onUpdateDialogRequested() {
                openSettingsPopup(1)
            }
        }

        // Debug info dialog
        Popup {
            id: debugDialog
            width: 450
            height: 250
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: backend.theme === "dark" ? "#181818" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#2a2a2a" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "WiFi Interface Information"
                    color: backend.theme === "dark" ? "white" : "black"
                    font.pixelSize: 14
                    font.bold: true
                    Layout.alignment: Qt.AlignHCenter
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    TextArea {
                        id: debugText
                        text: backend.getWifiInterfaceInfo()
                        readOnly: true
                        wrapMode: TextArea.Wrap
                        background: Rectangle {
                            color: backend.theme === "dark" ? "#111111" : "#ffffff"
                            border.color: backend.theme === "dark" ? "#2a2a2a" : "#cccccc"
                            border.width: 1
                            radius: 3
                        }
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 9
                        font.family: "Courier New"
                    }
                }

                Button {
                    text: "Refresh"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 24
                    onClicked: debugText.text = backend.getWifiInterfaceInfo()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#303030" : "#d0d0d0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 10
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

    // Sliding launch details tray
    Popup {
        id: launchTray
        width: parent.width
        height: 25  // Fixed banner height
        x: 0
        y: 0  // Position at top of screen
        modal: false
        focus: false
        visible: !!(backend && backend.launchTrayVisible)
        closePolicy: Popup.NoAutoClose

        leftPadding: 15
        rightPadding: 15
        topPadding: 0
        bottomPadding: 0
        leftMargin: 0
        rightMargin: 0
        topMargin: 0
        bottomMargin: 0

        property real expandedHeight: 25
        property real collapsedHeight: 25
        property var nextLaunch: null
        property string tMinus: ""

        Connections {
            target: backend
            function onCountdownChanged() {
                launchTray.tMinus = backend.countdown;
            }
        }

        Timer {
            interval: 1000
            running: true
            repeat: true
            onTriggered: {
                var next = backend.get_next_launch();
                launchTray.nextLaunch = next;
                launchTray.tMinus = backend.countdown;
            }
        }

        background: Rectangle {
            color: "#FF3838" // Use the red color for the banner
            radius: 12
            border.width: 0
            opacity: 0.8
        }

        // Bottom status text - T-minus on left, launch name on right
        Item {
            width: parent.width
            height: 20
            anchors.verticalCenter: parent.verticalCenter
            z: 1

            Text {
                text: launchTray.tMinus || "T-0"
                font.pixelSize: 14
                font.bold: true
                color: "white"
                anchors.left: parent.left
                anchors.leftMargin: 0
                anchors.right: parent.horizontalCenter
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignLeft
            }

            Text {
                text: launchTray.nextLaunch ? launchTray.nextLaunch.mission : "No upcoming launches"
                font.pixelSize: 14
                font.bold: true
                color: "white"
                elide: Text.ElideRight
                anchors.right: parent.right
                anchors.rightMargin: 0
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
            }
            }
        }
    }
}
"""
