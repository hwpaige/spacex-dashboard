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
    width: 1480
    height: 320
    title: "SpaceX Dashboard"
    onActiveChanged: {
        if (active) {
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                   try { globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();"); } catch (e) {}
                }
            }
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                   try { plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();"); } catch (e) {}
                }
            }
        }
    }
    // Use the same background color as the globe view for visual consistency
    color: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
    Behavior on color { ColorAnimation { duration: 300 } }

    property bool isWindyFullscreen: false
    property bool autoFullScreen: false
    // Track the currently selected YouTube URL for the video card.
    // Initialized to the default playlist URL provided by the backend context property.
    property url currentVideoUrl: videoUrl

    // Alignment guide removed after calibration; margins are now fixed below.

    // Helper to enforce rounded corners inside WebEngine pages themselves.
    // This injects CSS into the page to round and clip at the document level,
    // which works even when the scene-graph clipping is ignored by Chromium.
    function _injectRoundedCorners(webView, radiusPx) {
        if (!webView || !webView.runJavaScript) return;
        if (typeof backend !== 'undefined' && backend.wifiConnecting) return; // Prevent JS during connection
        var r = Math.max(0, radiusPx|0);
        var js = "(function(){try{" +
                 "var r=" + r + ";" +
                 "var apply=function(){var h=document.documentElement, b=document.body;" +
                 " if(h){h.style.borderRadius=r+'px'; h.style.overflow='hidden'; h.style.background='transparent'; h.style.clipPath='inset(0 round '+r+'px)';}" +
                 " if(b){b.style.borderRadius=r+'px'; b.style.overflow='hidden'; b.style.background='transparent'; b.style.clipPath='inset(0 round '+r+'px)';}" +
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

    Component.onCompleted: {
        console.log("Window created - bottom bar should be visible")
        // Connect web content reload signal
        backend.reloadWebContent.connect(function() {
            console.log("Reloading web content after WiFi connection...")
            // Smooth globe handling: avoid full reloads to prevent freeze/replot.
            // Instead, nudge animation loops to resume if they paused.
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) {
                if (!(backend && backend.wifiConnecting)) {
                    try {
                        globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
                    } catch (e) { console.log("Globe view JS resume failed:", e); }
                }
            }
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
        if (typeof globeView !== 'undefined' && globeView.runJavaScript) {
            try { globeView.runJavaScript(guardJs) } catch(e) { console.log("Failed to set globeAutospinGuard on globeView:", e) }
        }
        if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) {
            try { plotGlobeView.runJavaScript(guardJs) } catch(e) { console.log("Failed to set globeAutospinGuard on plotGlobeView:", e) }
        }
        // Resume spin on key backend signals
        backend.launchCacheReady.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.updateGlobeTrajectory.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.loadingFinished.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        backend.firstOnline.connect(function(){
            if (backend.wifiConnecting) return;
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) globeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript("(function(){try{if(window.forceResumeSpin)forceResumeSpin();else if(window.resumeSpin)resumeSpin();}catch(e){}})();")
        })
        // Keep guard value in sync if changed at runtime
        backend.globeAutospinGuardChanged.connect(function(){
            if (backend.wifiConnecting) return;
            var guard2 = backend.globeAutospinGuard
            var guardJs2 = "window.globeAutospinGuard=" + (guard2 ? "true" : "false") + ";"
            if (typeof globeView !== 'undefined' && globeView.runJavaScript) globeView.runJavaScript(guardJs2)
            if (typeof plotGlobeView !== 'undefined' && plotGlobeView.runJavaScript) plotGlobeView.runJavaScript(guardJs2)
        })
    }

    Rectangle {
        id: loadingScreen
        anchors.fill: parent
        // Match app background to the globe background
        color: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
    // Keep this container visible during initial load OR while an update is in progress
    visible: !!(backend && (backend.isLoading || backend.updatingInProgress))
        z: 1

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 20

            Image {
                source: "file:///" + spacexLogoPath
                Layout.alignment: Qt.AlignHCenter
                width: 120
                height: 120
                sourceSize.width: 120
                sourceSize.height: 120
                fillMode: Image.PreserveAspectFit
            }

            Text {
                text: backend.loadingStatus
                Layout.alignment: Qt.AlignHCenter
                color: backend.theme === "dark" ? "#ffffff" : "#000000"
                font.pixelSize: 16
                font.family: "D-DIN"
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // Update progress overlay (shown during in-app update)
        Rectangle {
            id: updateOverlay
            anchors.fill: parent
            visible: backend && backend.updatingInProgress
            color: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
            opacity: 0.98
            z: 9999

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

                // Progress text area showing tail of updater log
                Rectangle {
                    width: parent.width
                    height: 140
                    radius: 8
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                            color: backend.theme === "dark" ? "#9ad1d4" : "#2a2e2e"
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
        anchors.rightMargin: 12

        ColumnLayout {
            id: centralContent
            anchors.fill: parent
            anchors.leftMargin: 5
            // No rightMargin here — safeArea already reduces width on the right
            anchors.topMargin: 5
            anchors.bottomMargin: 5
            spacing: 5
            visible: !!(!backend || !backend.isLoading)

            RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 5

            // Column 1: Launch Trends or Driver Standings
            Rectangle {
                id: plotCard
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                // When showing the globe inside this card, match the app background
                // so the globe appears to sit directly on the window background.
                color: plotCard.plotCardShowsGlobe
                       ? (backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8")
                       : (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0")
                radius: 8
                clip: false
                visible: !isWindyFullscreen
                // Toggle to switch between plot and globe within this card
                // Default to globe view on app load
                property bool plotCardShowsGlobe: true
                // Cache bar-toggle absolute position so overlay toggle can appear at the exact same spot
                property real toggleAbsX: 0
                property real toggleAbsY: 0
                function cacheToggleAbsPos() {
                    // If the bar toggle is visible, use its real position
                    if (globeToggle && globeToggle.visible) {
                        var pt = globeToggle.mapToItem(plotCard, 0, 0)
                        toggleAbsX = pt.x
                        toggleAbsY = pt.y
                    } else {
                        // Fallback for initial globe mode (bar hidden): compute exact position
                        // to match where the toggle would be inside the centered RowLayout.
                        // Row composition (as currently defined):
                        // - 5 chart buttons @ 40px each
                        // - RowLayout spacing: 6px between items (6 gaps before toggle)
                        // - spacer Item: 8px
                        // - toggle button: 40px (matches other buttons)
                        var btnCount = 5;
                        var btnW = 40;
                        var spacerW = 8;
                        var toggleW = 40;
                        var spacing = 6;
                        var gapsBeforeToggle = btnCount /*buttons*/ + 1 /*spacer*/; // number of items before toggle
                        var spacingBeforeToggle = gapsBeforeToggle * spacing; // gaps before toggle
                        var widthBeforeToggle = (btnCount * btnW) + spacerW + spacingBeforeToggle;
                        var totalRowWidth = widthBeforeToggle + toggleW + spacing; // include last spacing after toggle for symmetry (harmless)

                        // The RowLayout is centered in the bar, so compute its left edge
                        var rowLeftX = Math.max(0, (plotCard.width - totalRowWidth) / 2);
                        // Toggle's left X inside the card
                        toggleAbsX = rowLeftX + widthBeforeToggle;

                        // Vertically align within the (hidden) bar area at the bottom of the card
                        var pillH = 28; // match button height
                        var barH = 30;
                        toggleAbsY = Math.max(2, plotCard.height - barH + (barH - pillH) / 2);
                    }
                }
                Component.onCompleted: {
                    cacheToggleAbsPos()
                    // Defer once more to ensure layout metrics are finalized
                    Qt.callLater(cacheToggleAbsPos)
                }
                onWidthChanged: if (plotCard.plotCardShowsGlobe) cacheToggleAbsPos()
                onHeightChanged: if (plotCard.plotCardShowsGlobe) cacheToggleAbsPos()

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: !!backend

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 0
                            // Remove spacing in globe mode so no background strip remains
                            spacing: plotCard.plotCardShowsGlobe ? 0 : 5

                            // Plot view (default)
                            ChartItem {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                visible: !plotCard.plotCardShowsGlobe

                                chartType: backend.chartType
                                viewMode: backend.chartViewMode
                                series: backend.launchTrendsSeries
                                months: backend.launchTrendsMonths
                                maxValue: backend.launchTrendsMaxValue
                                theme: backend.theme

                                opacity: showAnimated

                                property real showAnimated: 0

                                Component.onCompleted: showAnimated = 1

                                Behavior on showAnimated {
                                    NumberAnimation {
                                        duration: 500
                                        easing.type: Easing.InOutQuad
                                    }
                                }
                            }

                            // Globe view (reuses the upcoming launch tray globe)
                            // Mask effect removed to avoid dependency on Qt5Compat.GraphicalEffects

                            WebEngineView {
                                id: plotGlobeView
                                // Ensure the globe view fills all available space in the layout
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                visible: plotCard.plotCardShowsGlobe
                                url: globeUrl
                                // Transparent so the card's color shows through rounded edges after DOM rounding
                                backgroundColor: "transparent"
                                zoomFactor: 1.0
                                layer.enabled: true
                                layer.smooth: true
                                settings.javascriptCanAccessClipboard: false
                                settings.allowWindowActivationFromJavaScript: false
                                // Disable any default context menu (long-press/right-click)
                                onContextMenuRequested: function(request) { request.accepted = true }

                                onLoadingChanged: function(loadRequest) {
                                    if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                        var trajectoryData = backend.get_launch_trajectory();
                                        if (trajectoryData) {
                                            plotGlobeView.runJavaScript("if(typeof updateTrajectory !== 'undefined') updateTrajectory(" + JSON.stringify(trajectoryData) + ");");
                                        }
                                        // Set initial theme
                                        plotGlobeView.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");

                                        // Enforce rounded corners inside the page itself
                                        if (typeof root !== 'undefined') root._injectRoundedCorners(plotGlobeView, 8)
                                        // Ensure the plot card globe animation loop starts/resumes on initial load
                                        try {
                                            plotGlobeView.runJavaScript("(function(){try{if(window.resumeSpin)resumeSpin();}catch(e){console.log('Plot globe animation start failed', e);}})();");
                                        } catch (e) { console.log("Plot globe JS nudge error:", e); }
                                    }
                                }

                                Connections {
                                    target: backend
                                    function onThemeChanged() {
                                        plotGlobeView.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");
                                    }
                                }
                            }
                        }
                    }

                    // Chart control buttons container (hidden in globe view)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: plotCard.plotCardShowsGlobe ? 0 : 30
                        Layout.maximumHeight: plotCard.plotCardShowsGlobe ? 0 : 30
                        Layout.alignment: Qt.AlignTop
                        color: "transparent"
                        visible: backend && !plotCard.plotCardShowsGlobe

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "bar", "icon": "\uf080", "tooltip": "Bar Chart"},
                                    {"type": "line", "icon": "\uf201", "tooltip": "Line Chart"},
                                    {"type": "area", "icon": "\uf1fe", "tooltip": "Area Chart"},
                                    {"type": "actual", "icon": "\uf201", "tooltip": "Monthly View"},
                                    {"type": "cumulative", "icon": "\uf0cb", "tooltip": "Cumulative View"}
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    color: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                           (backend.chartType === modelData.type ?
                                            (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                            (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")) :
                                           (backend.chartViewMode === modelData.type ?
                                            (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                            (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5"))
                                    radius: 14
                                    border.color: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                 (backend.chartType === modelData.type ?
                                                  (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                  (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")) :
                                                 (backend.chartViewMode === modelData.type ?
                                                  (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                  (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"))
                                    border.width: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                 (backend.chartType === modelData.type ? 2 : 1) :
                                                 (backend.chartViewMode === modelData.type ? 2 : 1)

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
                                        onClicked: (modelData.type === "bar" || modelData.type === "line" || modelData.type === "area") ?
                                                  backend.chartType = modelData.type :
                                                  backend.chartViewMode = modelData.type
                                    }

                                    ToolTip {
                                        text: modelData.tooltip
                                        delay: 500
                                    }
                                }
                            }

                            // Toggle button between Plot and Globe (matches bar button style)
                            Item { Layout.preferredWidth: 8; Layout.preferredHeight: 1 } // spacer
                            Rectangle {
                                id: globeToggle
                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 28
                                width: 40
                                height: 28
                                radius: 14
                                color: backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5"
                                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                                border.width: 1

                                Behavior on color { ColorAnimation { duration: 200 } }
                                Behavior on border.color { ColorAnimation { duration: 200 } }
                                Behavior on border.width { NumberAnimation { duration: 200 } }

                                Text {
                                    anchors.centerIn: parent
                                    // In plot view (globe hidden), show globe icon; if ever visible otherwise, show plot icon
                                    text: plotCard.plotCardShowsGlobe ? "\uf201" : "\uf0ac"
                                    font.pixelSize: 14
                                    font.family: "Font Awesome 5 Free"
                                    color: backend.theme === "dark" ? "white" : "black"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        // Cache absolute position before switching modes so overlay button can match position
                                        plotCard.cacheToggleAbsPos()
                                        plotCard.plotCardShowsGlobe = true
                                    }
                                    cursorShape: Qt.PointingHandCursor
                                }

                                ToolTip { text: "Show Globe"; delay: 500 }
                                // Keep cached position updated when layout changes while visible
                                onXChanged: plotCard.cacheToggleAbsPos()
                                onYChanged: plotCard.cacheToggleAbsPos()
                                onWidthChanged: plotCard.cacheToggleAbsPos()
                                onHeightChanged: plotCard.cacheToggleAbsPos()
                                onVisibleChanged: if (visible) plotCard.cacheToggleAbsPos()
                            }
                        }
                    }

                    // Overlay toggle button (same style as bar buttons), positioned absolutely using cached coordinates
                    Rectangle {
                        id: globeOverlayToggle
                        parent: plotCard
                        visible: backend && plotCard.plotCardShowsGlobe
                        x: plotCard.toggleAbsX
                        y: plotCard.toggleAbsY
                        width: 40
                        height: 28
                        radius: 14
                        color: backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                        border.width: 1
                        z: 1000

                        Behavior on color { ColorAnimation { duration: 200 } }
                        Behavior on border.color { ColorAnimation { duration: 200 } }
                        Behavior on border.width { NumberAnimation { duration: 200 } }

                        Text {
                            anchors.centerIn: parent
                            // In globe view (overlay visible), show plot icon to switch back
                            text: "\uf201"
                            font.pixelSize: 14
                            font.family: "Font Awesome 5 Free"
                            color: backend.theme === "dark" ? "white" : "black"
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                // Restore bar; cache position in case layout shifts back
                                plotCard.plotCardShowsGlobe = false
                                plotCard.cacheToggleAbsPos()
                            }
                            cursorShape: Qt.PointingHandCursor
                        }

                        ToolTip { text: "Show Plot"; delay: 500 }
                    }
                }
            }

            // Column 2: Radar
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                // Remove rounded corners/clipping for Windy card to restore animations
                radius: 0
                clip: false
                // Layers can remain enabled; no clipping applied
                layer.enabled: true
                layer.smooth: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                        SwipeView {
                            id: weatherSwipe
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            anchors.margins: 10
                            visible: !!backend
                            orientation: Qt.Vertical
                            // Do not clip; allow Windy WebGL to render freely
                            clip: false
                            // Keep layer enabled for performance but without clipping
                            layer.enabled: true
                            layer.smooth: true
                            interactive: true
                            currentIndex: 1
                            property int loadedMask: (1 << 1)
                            onCurrentIndexChanged: loadedMask |= (1 << currentIndex)

                        Component.onCompleted: {
                            console.log("SwipeView completed, count:", count);
                        }

                        Repeater {
                            model: ["radar", "wind", "gust", "clouds", "temp", "pressure"]

                            Item {
                                // Container without rounded corners or clipping for Windy views
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 0
                                    color: "transparent"
                                    clip: false
                                    // Layer can remain enabled
                                    layer.enabled: true
                                    layer.smooth: true

                                    // Mask effect removed to avoid dependency on Qt5Compat.GraphicalEffects

                                    Loader {
                                        id: webViewLoader
                                        anchors.fill: parent
                                        // Load current item and neighbors for smooth vertical swiping if they have been visited
                                        active: Math.abs(index - weatherSwipe.currentIndex) <= 1 && (weatherSwipe.loadedMask & (1 << index))
                                        visible: active

                                        sourceComponent: WebEngineView {
                                            id: webView
                                            objectName: "webView"
                                            anchors.fill: parent
                                            // Make the view itself a layer to cooperate with ancestor clipping
                                            layer.enabled: true
                                            layer.smooth: true
                                            // Avoid white square corners by letting parent background show through
                                            backgroundColor: "transparent"
                                            url: parent.visible ? backend.radarBaseUrl.replace("radar", modelData) + "&v=" + Date.now() : ""
                                            onUrlChanged: console.log("WebEngineView URL changed to:", url)
                                            settings.webGLEnabled: true
                                            settings.accelerated2dCanvasEnabled: true
                                            settings.allowRunningInsecureContent: true
                                            settings.javascriptEnabled: true
                                            settings.localContentCanAccessRemoteUrls: true
                                            onFullScreenRequested: function(request) {
                                                request.accept();
                                                root.visibility = Window.FullScreen
                                            }
                                            onLoadingChanged: function(loadRequest) {
                                                if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                                    console.log("WebEngineView load failed for", modelData, ":", loadRequest.errorString);
                                                } else if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                                    console.log("WebEngineView loaded successfully for", modelData);
                                                    // No rounding injection for Windy to preserve animations
                                                }
                                            }

                                            // Staggered reload for weather views
                                            Connections {
                                                target: backend
                                                function onReloadWebContent() {
                                                    // Stagger based on index to prevent freeze
                                                    var delay = 1500 + (index * 500)
                                                    reloadTimer.interval = delay
                                                    reloadTimer.start()
                                                }
                                            }
                                            Timer {
                                                id: reloadTimer
                                                repeat: false
                                                onTriggered: {
                                                    if (parent.visible) { // Only reload if visible or about to be? 
                                                        // Actually, reload all but staggered is safer.
                                                        webView.reload()
                                                        console.log("Weather view", index, "reloaded (staggered)")
                                                    } else {
                                                        // If not visible, just reload anyway, staggered.
                                                        webView.reload()
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    // overlay mask removed
                                }

                                // Removed top-center icon overlay for Windy views as requested

                                // Fullscreen button for weather views
                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.topMargin: 90
                                    anchors.right: parent.right
                                    anchors.rightMargin: 5
                                    width: 30
                                    height: 30
                                    color: "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: isWindyFullscreen ? "\uf066" : "\uf065"  // collapse or expand
                                        font.family: "Font Awesome 5 Free"
                                        font.pixelSize: 16
                                        color: "white"
                                        style: Text.Outline
                                        styleColor: "black"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: isWindyFullscreen = !isWindyFullscreen
                                    }
                                }
                            }
                        }
                    }


                    // Weather view buttons container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        Layout.maximumHeight: 30
                        Layout.alignment: Qt.AlignTop
                        color: "transparent"
                        visible: !!backend

                        RowLayout {
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
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 14
                                    border.color: weatherSwipe.currentIndex === index ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
                                    border.width: weatherSwipe.currentIndex === index ? 2 : 1

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
                                        onClicked: weatherSwipe.currentIndex = index
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

            // Column 3: Launches or Races
            Rectangle {
                id: launchCard
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true
                visible: !isWindyFullscreen
                property string launchViewMode: "list"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    StackLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: launchCard.launchViewMode === "calendar" ? 1 : 0
                        clip: true

                        // View 0: Existing List View
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            ListView {
                        anchors.fill: parent
                        model: backend.eventModel
                        clip: true
                        spacing: 5

                        delegate: Item {
                            width: ListView.view.width
                            height: model && model.isGroup ? 30 : launchColumn.height + 20

                            Rectangle { anchors.fill: parent; color: (model && model.isGroup) ? "transparent" : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"); radius: (model && model.isGroup) ? 0 : 6 }

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

                                Text { text: (model && model.mission) ? model.mission : ""; font.pixelSize: 12; font.bold: true; color: backend.theme === "dark" ? "white" : "black"; width: parent.width - 80; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                                Row { spacing: 5
                                    Text { text: "\uf135"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Rocket: " + ((model && model.rocket) ? model.rocket : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf0ac"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Orbit: " + ((model && model.orbit) ? model.orbit : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5
                                    Text { text: "\uf3c5"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Pad: " + ((model && model.pad) ? model.pad : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Row { spacing: 5; visible: !!(model && model.landingType)
                                    Text { text: "\uf5af"; font.family: "Font Awesome 5 Free"; font.pixelSize: 12; color: "#999999" }
                                    Text { text: "Landing: " + ((model && model.landingType) ? model.landingType : ""); font.pixelSize: 12; color: "#999999" }
                                }
                                Text { text: ((model && model.date) ? model.date : "") + ((model && model.time) ? (" " + model.time) : "") + " UTC"; font.pixelSize: 12; color: "#999999" }
                                Text { text: ((model && model.localTime) ? model.localTime + " " + backend.timezoneAbbrev : "TBD"); font.pixelSize: 12; color: "#999999" }
                            }

                            Rectangle {
                                width: statusText.implicitWidth + 16
                                height: 18
                                color: (model && model.status === "TBD") ? "#FF9800" : ((model && model.status) && (model.status === "Success" || model.status === "Go" || model.status === "Go for Launch")) ? "#4CAF50" : "#F44336"
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

                        }
                    }

                        } // End Item (List Container)

                        // View 1: Swipeable Calendar View
                        Item {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            visible: parent.currentIndex === 1
                            
                            id: calendarViewItem
                            property var currentMonth: new Date()
                            
                            property var popupLaunches: []
                            property string popupDateString: ""

                            function getMonthName(date) {
                                return date.toLocaleDateString(Qt.locale(), "MMMM yyyy")
                            }

                            function getStatusColor(status) {
                                if (status === 'TBD') return "#FF9800"
                                if (status === 'Success' || status === 'Go' || status === 'Go for Launch') return "#4CAF50"
                                return "#F44336"
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
                                    color: backend.theme === "dark" ? "#2a2e2e" : "#ffffff"
                                    radius: 12
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                                        delegate: Column {
                                            width: parent.width
                                            spacing: 1
                                            padding: 2
                                            
                                            Text { 
                                                width: parent.width
                                                text: modelData.mission 
                                                wrapMode: Text.Wrap
                                                font.bold: true 
                                                font.pixelSize: 12 
                                                color: backend.theme === "dark" ? "white" : "black" 
                                            }
                                            Text { text: modelData.rocket; font.pixelSize: 12; color: "#999999" }
                                            Text { text: modelData.time + " UTC"; font.pixelSize: 12; color: "#999999" }
                                            Row {
                                                spacing: 5
                                                Rectangle {
                                                   width: 10; height: 10; radius: 5
                                                   color: calendarViewItem.getStatusColor(modelData.status)
                                                   anchors.verticalCenter: parent.verticalCenter
                                                }
                                                Text { text: modelData.status; font.bold: true; font.pixelSize: 12; color: calendarViewItem.getStatusColor(modelData.status) }
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
                                    
                                    // Start a few months back to allow history, but center on "today" logically
                                    // Index 12 will be "current month" (relative offset 0)
                                    currentIndex: 12
                                    
                                    onCurrentIndexChanged: {
                                        var today = new Date()
                                        var offset = currentIndex - 12
                                        var newDate = new Date(today.getFullYear(), today.getMonth() + offset, 1)
                                        parent.parent.currentMonth = newDate
                                    }

                                    Repeater {
                                        model: 25 // Show range of +/- 12 months
                                        
                                        Item {
                                            id: monthPage
                                            property int monthOffset: index - 12
                                            property date pageDate: {
                                                var d = new Date()
                                                return new Date(d.getFullYear(), d.getMonth() + monthOffset, 1)
                                            }
                                            
                                            // Calculate grid logic
                                            property int daysInMonth: new Date(pageDate.getFullYear(), pageDate.getMonth() + 1, 0).getDate()
                                            property int startDayOfWeek: new Date(pageDate.getFullYear(), pageDate.getMonth(), 1).getDay()
                                            
                                            GridLayout {
                                                anchors.fill: parent
                                                anchors.margins: 5
                                                columns: 7
                                                rows: 6
                                                rowSpacing: 2
                                                columnSpacing: 2
                                                
                                                Repeater {
                                                    model: 42 // 6 rows * 7 cols
                                                    
                                                    Rectangle {
                                                        Layout.fillWidth: true
                                                        Layout.fillHeight: true
                                                        
                                                        property int dayNum: index - parent.parent.startDayOfWeek + 1
                                                        property bool isCurrentMonth: dayNum > 0 && dayNum <= parent.parent.daysInMonth
                                                        property date cellDate: new Date(parent.parent.pageDate.getFullYear(), parent.parent.pageDate.getMonth(), dayNum)
                                                        
                                                        color: "transparent"
                                                        visible: isCurrentMonth
                                                        
                                                        // Check for launches (find all on this day)
                                                        property var dayLaunches: {
                                                            var list = []
                                                            if (!isCurrentMonth || !backend || !backend.allLaunchData) return list
                                                            var dStr = cellDate.toISOString().substring(0,10)
                                                            var all = backend.allLaunchData
                                                            var check = function(arr, type) {
                                                                if(!arr) return;
                                                                for(var i=0; i<arr.length; i++) {
                                                                    if(arr[i].date === dStr) {
                                                                        var l = arr[i]; l.type = type;
                                                                        list.push(l)
                                                                    }
                                                                }
                                                            }
                                                            check(all.previous, 'past')
                                                            check(all.upcoming, 'upcoming')
                                                            return list
                                                        }
                                                        
                                                        // Selection/Highlight
                                                        Rectangle {
                                                            anchors.centerIn: parent
                                                            width: Math.min(parent.width, parent.height) - 4
                                                            height: width
                                                            radius: width/2
                                                            color: {
                                                                if (dayLaunches.length > 0) {
                                                                    return calendarViewItem.getStatusColor(dayLaunches[0].status)
                                                                }
                                                                // Today highlight
                                                                var today = new Date()
                                                                if (cellDate.toDateString() === today.toDateString()) return backend.theme === "dark" ? "#444" : "#ddd"
                                                                return "transparent"
                                                            }
                                                            opacity: dayLaunches.length > 0 ? 0.2 : 1.0
                                                            
                                                            border.color: dayLaunches.length > 0 ? calendarViewItem.getStatusColor(dayLaunches[0].status) : "transparent"
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
                                                                    color: calendarViewItem.getStatusColor(dayLaunches[index].status)
                                                                }
                                                            }
                                                            // Add small plus if more than 3? No space really.
                                                        }

                                                        Text {
                                                            anchors.centerIn: parent
                                                            anchors.verticalCenterOffset: -2
                                                            text: isCurrentMonth ? dayNum : ""
                                                            font.pixelSize: 12
                                                            color: backend.theme === "dark" ? "white" : "black"
                                                            font.bold: dayLaunches.length > 0
                                                        }
                                                        
                                                        // Simple Tooltip logic
                                                        ToolTip {
                                                            visible: ma.containsMouse && dayLaunches.length > 0
                                                            text: dayLaunches.length > 0 ? (dayLaunches.length + " Launch" + (dayLaunches.length > 1 ? "es" : "")) : ""
                                                            delay: 500
                                                        }
                                                        MouseArea {
                                                            id: ma
                                                            anchors.fill: parent
                                                            hoverEnabled: true
                                                            cursorShape: dayLaunches.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                            onClicked: {
                                                                if (dayLaunches.length > 0) {
                                                                    calendarViewItem.showPopup(dayLaunches, cellDate)
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
                        }
                    } // End StackLayout

                    // Launch view buttons container
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        Layout.maximumHeight: 30
                        Layout.alignment: Qt.AlignTop
                        color: "transparent"

                        RowLayout {
                            anchors.centerIn: parent
                            spacing: 6

                            Repeater {
                                model: [
                                    {"type": "upcoming", "icon": "\uf135", "tooltip": "Upcoming Launches"},
                                    {"type": "past", "icon": "\uf1da", "tooltip": "Past Launches"},
                                    {"type": "calendar", "icon": "\uf073", "tooltip": "Calendar View"} 
                                ]
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    // Highlight if:
                                    // 1. We are in 'calendar' mode and this button is the calendar button
                                    // 2. We are in 'list' mode and this button matches backend.eventType (upcoming/past)
                                    property bool isActive: (modelData.type === "calendar") ? 
                                                            (launchCard.launchViewMode === "calendar") : 
                                                            (launchCard.launchViewMode !== "calendar" && backend.eventType === modelData.type)
                                    
                                    color: isActive ?
                                           (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") :
                                           (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    radius: 14
                                    border.color: isActive ?
                                                 (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") :
                                                 (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
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
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                clip: true
                visible: !isWindyFullscreen

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

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
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 8
                        color: "transparent"
                        clip: true
                        layer.enabled: true
                        layer.smooth: true

                        // Mask effect removed to avoid dependency on Qt5Compat.GraphicalEffects

                        WebEngineView {
                            id: youtubeView
                            profile: youtubeProfile
                            anchors.fill: parent
                            // Ensure proper rounded clipping and avoid white corners
                            layer.enabled: true
                            layer.smooth: true
                            backgroundColor: "transparent"
                            url: parent.visible ? root.currentVideoUrl : ""
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
                                    if (typeof root !== 'undefined') root._injectRoundedCorners(youtubeView, 8)
                                    
                                    // Automatically trigger fullscreen if requested by a UI action (like pressing the LIVE button)
                                    // We only apply this to X.com (Twitter) streams as requested.
                                    var isX = loadRequest.url.toString().indexOf("x.com") !== -1 || loadRequest.url.toString().indexOf("twitter.com") !== -1;
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

                        // Overlay for quick-action buttons floating on top of the video
                        Item {
                            id: youtubeOverlay
                            anchors.fill: parent
                            z: 2
                            visible: backend && !isWindyFullscreen

                            RowLayout {
                                id: youtubePills
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 6
                                spacing: 6

                                // Starship playlist (current YouTube URL)
                                Rectangle {
                                    id: starshipBtn
                                    // Match highlight logic used by Windy/plot pills: compare as strings to avoid url vs string type mismatch
                                    property bool selected: (typeof videoUrl !== 'undefined' && videoUrl) ? (String(root.currentVideoUrl) === String(videoUrl)) : false
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    radius: 14
                                    color: selected ? (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") : (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    border.color: selected ? (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
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
                                            if (typeof videoUrl !== 'undefined' && videoUrl) {
                                                // Ensure currentVideoUrl updates as a string URL to keep comparison consistent
                                                root.currentVideoUrl = String(videoUrl)
                                            } else {
                                                console.log("videoUrl is not defined or empty")
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
                                    color: selected ? (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") : (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                                    border.color: selected ? (backend.theme === "dark" ? "#5a5e5e" : "#c0c0c0") : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0")
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
                                    property bool selected: (backend.liveLaunchUrl !== "" && String(root.currentVideoUrl) === backend.liveLaunchUrl)
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 28
                                    radius: 14
                                    color: selected ? "#FF0000" : (backend.liveLaunchUrl !== "" ? "#CC0000" : (backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"))
                                    border.color: selected ? "white" : (backend.liveLaunchUrl !== "" ? "transparent" : (backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"))
                                    border.width: selected ? 2 : 1
                                    opacity: backend.liveLaunchUrl !== "" ? 1.0 : 0.6

                                    Text {
                                        anchors.centerIn: parent
                                        text: "LIVE"
                                        font.pixelSize: 10
                                        font.bold: true
                                        color: "white"
                                    }
                                    MouseArea { 
                                        anchors.fill: parent
                                        cursorShape: backend.liveLaunchUrl !== "" ? Qt.PointingHandCursor : Qt.ArrowCursor
                                        onClicked: {
                                            if (backend.liveLaunchUrl !== "") {
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
                                    ToolTip { text: backend.liveLaunchUrl !== "" ? "Switch to current launch livestream (X.com)" : "No live stream available"; delay: 400 }
                                }
                            }
                        }
                    }
                }
            }
        }

        // Bottom bar - FIXED VERSION
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            color: "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                // Fixed padding to reflect calibrated right-edge inset (10 base + 6 measured = 16)
                anchors.rightMargin: 16
                spacing: 8

                // Left pill (time and weather) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.maximumWidth: 200
                    height: 28
                    radius: 14
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Row {
                        anchors.centerIn: parent
                        spacing: 10

                        Text {
                            text: backend.currentTime
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                        }
                        Text {
                            id: weatherText
                            text: {
                                var weather = backend.weather;
                                if (weather && weather.temperature_f !== undefined) {
                                    return "Wind " + (weather.wind_speed_kts || 0).toFixed(1) + " kts | " +
                                           (weather.temperature_f || 0).toFixed(1) + "°F";
                                }
                                return "Weather loading...";
                            }
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
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
                        radius: 14
                        color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                            // Fade out as tray expands (starts fading when tray is 2x ticker height)
                            opacity: 1.0 - Math.min(1.0, narrativeTray.height / 56.0)

                            SequentialAnimation on x {
                                loops: Animation.Infinite
                                NumberAnimation {
                                    from: tickerRect.width
                                    to: -tickerText.width + 400  // Pause with text still visible
                                    duration: 1600000
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
                        
                        onPressed: {
                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            // Ensure tray is ready
                            if (narrativeTray.height === 0) {
                                narrativeTray.height = 1
                            }
                            startHeight = narrativeTray.height
                            isDragging = true
                        }
                        
                        onPositionChanged: {
                            if (isDragging && pressed) {
                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                // Dragging UP (negative delta) increases height
                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                var newHeight = startHeight - deltaY
                                
                                newHeight = Math.max(0, Math.min(narrativeTray.expandedHeight, newHeight))
                                narrativeTray.height = newHeight
                            }
                        }
                        
                        onReleased: {
                            isDragging = false
                            if (narrativeTray.height > 50) {
                                narrativeTray.height = narrativeTray.expandedHeight
                            } else {
                                narrativeTray.height = 0
                            }
                        }
                    }

                    // Sliding Launch Narratives Tray (Bottom)
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
                        closePolicy: Popup.NoAutoClose
                        
                        property real expandedHeight: 220 // Taller list
                        opacity: height / expandedHeight // Fade in/out based on drag position
                        
                        Behavior on height {
                            NumberAnimation {
                                duration: 300
                                easing.type: Easing.OutCubic
                            }
                        }
                        
                        background: Item {
                            Rectangle {
                                id: trayBackground
                                anchors.fill: parent
                                // 90% opacity (E6 hex)
                                color: backend.theme === "dark" ? "#e62a2e2e" : "#e6f0f0f0"
                                radius: 14
                                border.width: 1
                                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            }
                        }
                        
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 4
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
                                    
                                    onPressed: {
                                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                        startHeight = narrativeTray.height
                                        isDragging = true
                                    }
                                    
                                    onPositionChanged: {
                                        if (isDragging && pressed) {
                                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            // Dragging DOWN (positive delta) decreases height since expanding from bottom
                                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                                            var newHeight = startHeight - deltaY
                                            
                                            newHeight = Math.max(0, Math.min(narrativeTray.expandedHeight, newHeight))
                                            narrativeTray.height = newHeight
                                        }
                                    }
                                    
                                    onReleased: {
                                        isDragging = false
                                        if (narrativeTray.height < narrativeTray.expandedHeight * 0.5) {
                                            narrativeTray.height = 0
                                        } else {
                                            narrativeTray.height = narrativeTray.expandedHeight
                                        }
                                    }
                                }
                            }
                            
                            // Narratives List
                            ListView {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.margins: 0
                                // Extend right to the bottom edge
                                Layout.bottomMargin: 0 
                                Layout.topMargin: 0
                                clip: true
                                model: backend.launchDescriptions
                                spacing: 0
                                
                                delegate: Item {
                                    width: ListView.view.width
                                    height: contentLayout.implicitHeight + 16
                                    
                                    Rectangle {
                                        anchors.fill: parent
                                        color: "transparent"
                                        
                                        RowLayout {
                                            id: contentLayout
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            spacing: 12
                                            
                                            Text {
                                                id: dateText
                                                // Handle both structured object and legacy string
                                                text: (typeof modelData === "object" && modelData.date) ? modelData.date : ""
                                                visible: text !== ""
                                                color: backend.theme === "dark" ? "#88ffffff" : "#88000000" // Muted opacity
                                                font.pixelSize: 13
                                                font.family: "D-DIN"
                                                font.bold: true
                                                Layout.alignment: Qt.AlignTop
                                                Layout.preferredWidth: implicitWidth
                                                Layout.fillHeight: true 
                                            }

                                            Text {
                                                id: narrativeText
                                                // Handle both structured object and legacy string
                                                text: (typeof modelData === "object" && modelData.text) ? modelData.text : modelData
                                                Layout.fillWidth: true
                                                Layout.alignment: Qt.AlignTop
                                                wrapMode: Text.Wrap
                                                color: backend.theme === "dark" ? "#dddddd" : "#333333"
                                                font.pixelSize: 13
                                                font.family: "D-DIN"
                                                lineHeight: 1.2
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
                                            color: backend.theme === "dark" ? "#33ffffff" : "#33000000"
                                            visible: ListView.view && index < ListView.view.count - 1
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
                    height: 32
                    radius: 16
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "\uf021"
                        font.family: "Font Awesome 5 Free"
                        font.pixelSize: 12
                        color: backend.theme === "dark" ? "white" : "black"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            console.log("Update clicked - showing update dialog")
                            backend.show_update_dialog()
                        }
                    }

                    ToolTip {
                        text: backend.updateAvailable ? "Update Available - Click to Update and Reboot" : "Update and Reboot"
                        delay: 500
                    }

                    // Red dot indicator for available updates
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: "#FF4444"
                        border.color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                        border.width: 1
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.topMargin: -2
                        anchors.rightMargin: -2
                        visible: !!(backend && backend.updateAvailable)
                    }
                }

                    // WiFi icon
                    Rectangle {
                        width: 28
                        height: 32
                        radius: 16
                        color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                        width: Math.max(80, locationLabel.implicitWidth + 24)
                        height: 32
                        radius: 16
                        color: locationDrawer.height > 10 ? 
                               (backend.theme === "dark" ? "#ee2a2e2e" : "#eef0f0f0") : 
                               (backend.theme === "dark" ? "#2a2e2e" : "#f5f5f5")
                        border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                        border.width: 1

                        // Location Drawer (Sliding up from button top)
                        Popup {
                            id: locationDrawer
                            x: 0
                            width: parent.width
                            height: 0
                            y: -height
                            modal: false
                            focus: false
                            visible: height > 0
                            closePolicy: Popup.NoAutoClose
                            padding: 0
                            topPadding: 0
                            bottomPadding: 0
                            leftPadding: 0
                            rightPadding: 0
                            
                            property real expandedHeight: 160
                            
                            Behavior on height {
                                NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                            }
                            
                            background: Item {
                                Rectangle {
                                    anchors.fill: parent
                                    color: backend.theme === "dark" ? "#ee2a2e2e" : "#eef0f0f0"
                                    radius: 12
                                    border.width: 1
                                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"

                                    // Visual Blending: Flatten BOTTOM corners and hide border when drawer is open
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.leftMargin: 1
                                        anchors.rightMargin: 1
                                        height: 12
                                        color: parent.color
                                        visible: locationDrawer.height > 10
                                    }
                                }
                            }
                            
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                anchors.bottomMargin: 4
                                anchors.topMargin: 0
                                spacing: 0
                                
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 32
                                    color: "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "\uf078"
                                        font.family: "Font Awesome 5 Free"
                                        font.pixelSize: 10
                                        color: backend.theme === "dark" ? "white" : "black"
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        
                                        property point startGlobalPos: Qt.point(0, 0)
                                        property real startHeight: 0
                                        property bool isDragging: false
                                        
                                        onPressed: {
                                            startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                            startHeight = locationDrawer.height
                                            isDragging = true
                                        }
                                        
                                        onPositionChanged: {
                                            if (isDragging && pressed) {
                                                var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                                var deltaY = currentGlobalPos.y - startGlobalPos.y
                                                var newHeight = startHeight - deltaY
                                                newHeight = Math.max(0, Math.min(locationDrawer.expandedHeight, newHeight))
                                                locationDrawer.height = newHeight
                                            }
                                        }
                                        
                                        onReleased: {
                                            isDragging = false
                                            if (locationDrawer.height < 120) {
                                                locationDrawer.height = 0
                                            } else {
                                                locationDrawer.height = locationDrawer.expandedHeight
                                            }
                                        }
                                        onClicked: locationDrawer.height = 0
                                    }
                                }
                                
                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    model: ["Starbase", "Vandy", "Cape", "Hawthorne"]
                                    spacing: 2
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 30
                                        color: backend.location === modelData ? 
                                               (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0") : 
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
                                            onClicked: backend.location = modelData
                                        }
                                    }
                                }
                            }
                        }

                        // Visual Blending: Flatten TOP corners of button and hide border when drawer is open
                        Rectangle {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 1
                            anchors.rightMargin: 1
                            height: 12
                            color: parent.color
                            visible: locationDrawer.height > 10
                        }

                        Text {
                            id: locationLabel
                            anchors.centerIn: parent
                            text: backend.location
                            color: backend.theme === "dark" ? "white" : "black"
                            font.pixelSize: 14
                            font.family: "D-DIN"
                            font.bold: true
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
                                if (locationDrawer.height === 0) locationDrawer.height = 1
                                startHeight = locationDrawer.height
                                isDragging = true
                                moved = false
                            }
                            
                            onPositionChanged: {
                                if (isDragging && pressed) {
                                    var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                                    var deltaY = currentGlobalPos.y - startGlobalPos.y
                                    if (Math.abs(deltaY) > 5) moved = true
                                    var newHeight = startHeight - deltaY
                                    newHeight = Math.max(0, Math.min(locationDrawer.expandedHeight, newHeight))
                                    locationDrawer.height = newHeight
                                }
                            }
                            
                            onReleased: {
                                isDragging = false
                                if (moved) {
                                    if (locationDrawer.height > 40) {
                                        locationDrawer.height = locationDrawer.expandedHeight
                                    } else {
                                        locationDrawer.height = 0
                                    }
                                }
                            }
                            
                            onClicked: {
                                if (!moved) {
                                    if (locationDrawer.height > 50) {
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

                    // Theme Toggle Switch (Matched to launch tray toggle)
                    Rectangle {
                        id: themeToggle
                        Layout.preferredWidth: 50
                        Layout.preferredHeight: 32
                        radius: 16
                        color: backend.theme === "dark" ? "#666666" : "#CCCCCC"

                        Text {
                            text: "\uf185" // Sun
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.theme === "light" ? (backend.theme === "dark" ? "white" : "black") : "#888888"
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: backend.theme === "light" ? 1.0 : 0.5
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                        }

                        Text {
                            text: "\uf186" // Moon
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 12
                            color: backend.theme === "dark" ? "white" : "#888888"
                            anchors.right: parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: backend.theme === "dark" ? 1.0 : 0.5
                            Behavior on opacity { NumberAnimation { duration: 200 } }
                        }

                        Rectangle {
                            id: themeThumb
                            width: 26
                            height: 26
                            radius: 13
                            color: backend.theme === "dark" ? "#44ffffff" : "#44000000"
                            border.color: backend.theme === "dark" ? "#33ffffff" : "#33000000"
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

                // Launch details tray toggle
                Rectangle {
                    visible: true
                    Layout.preferredWidth: 50
                    Layout.preferredHeight: 32
                    radius: 16
                    color: backend.launchTrayManualMode ?
                        "#FF3838" :
                        (backend.theme === "dark" ? "#666666" : "#CCCCCC")

                    Behavior on color { ColorAnimation { duration: 200 } }

                    Rectangle {
                        width: 26
                        height: 26
                        radius: 13
                        x: backend.launchTrayManualMode ? parent.width - width - 3 : 3
                        y: 3
                        color: "white"
                        border.color: backend.theme === "dark" ? "#333333" : "#E0E0E0"
                        border.width: 1

                        Behavior on x { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: backend.setLaunchTrayManualMode(!backend.launchTrayManualMode)
                        cursorShape: Qt.PointingHandCursor
                    }

                    ToolTip {
                        text: backend.launchTrayManualMode ? "Manual: Launch banner always shown" : "Auto: Show banner within 1 hour of launch"
                        delay: 500
                    }
                }

                Item { Layout.fillWidth: true }

                // Right pill (countdown, location, theme) - FIXED WIDTH
                Rectangle {
                    Layout.preferredWidth: 120
                    Layout.maximumWidth: 120
                    height: 32
                    radius: 16
                    color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                    border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                    border.width: 1


                    Text {
                        anchors.centerIn: parent
                        text: backend.countdown
                        color: backend.theme === "dark" ? "white" : "black"
                        font.pixelSize: 14
                        font.family: "D-DIN"
                        font.bold: true
                    }


                                
                }
            }
        }

        // WiFi popup
        Popup {
            id: wifiPopup
            width: 500
            height: 300
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            property string selectedNetwork: ""

            onOpened: backend.startWifiTimer()
            onClosed: backend.stopWifiTimer()

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 5

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
                    color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
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
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
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
                    Layout.preferredHeight: 22
                    onClicked: debugDialog.open()

                    background: Rectangle {
                        color: backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0"
                        radius: 3
                    }

                    contentItem: Text {
                        text: parent.text
                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                        font.pixelSize: 9
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

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 32
                        color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
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
                                    color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
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
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                            color: backend.theme === "dark" ? "#1a1e1e" : "#ffffff"
                            border.color: backend.theme === "dark" ? "#3a3e3e" : "#cccccc"
                            border.width: 1
                            radius: 3
                        }

                        color: backend.theme === "dark" ? "white" : "black"
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
                            color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                            radius: 3
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
                            color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
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
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
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
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
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
                            color: parent.pressed ? "#FF6B35" : (virtualKeyboard.numberMode ? (backend.theme === "dark" ? "#2a2e2e" : "#e0e0e0") : (virtualKeyboard.shiftPressed ? "#FF9800" : (backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0")))
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
                                color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0")
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
                            color: parent.pressed ? "#FF6B35" : (backend.theme === "dark" ? "#3a3e3e" : "#c0c0c0")
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
                            color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
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
            height: 280
            x: (parent.width - width) / 2
            y: (parent.height - height) / 2
            modal: true
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            background: Rectangle {
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 15
                spacing: 10

                // Title and last checked
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 10

                    Text {
                        text: "Update Available"
                        font.pixelSize: 16
                        font.bold: true
                        color: backend.theme === "dark" ? "white" : "black"
                    }

                    Text {
                        text: "• Last checked: " + backend.lastUpdateCheckTime
                        font.pixelSize: 10
                        color: backend.theme === "dark" ? "#cccccc" : "#666666"
                        Layout.alignment: Qt.AlignVCenter
                    }
                }

                // Current version - compact single line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 45
                    color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                    radius: 4

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Text {
                            text: "\uf126"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 14
                            color: "#2196F3"
                            Layout.preferredWidth: 20
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: "Current: " + (backend.currentVersionInfo.short_hash || "Unknown")
                                font.pixelSize: 11
                                font.bold: true
                                color: backend.theme === "dark" ? "white" : "black"
                            }

                            Text {
                                text: backend.currentVersionInfo.message || "Unable to retrieve current version"
                                font.pixelSize: 9
                                color: backend.theme === "dark" ? "#cccccc" : "#666666"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // Latest version - compact single line
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 45
                    color: backend.theme === "dark" ? "#1a1e1e" : "#e0e0e0"
                    radius: 4

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        Text {
                            text: "\uf062"
                            font.family: "Font Awesome 5 Free"
                            font.pixelSize: 14
                            color: "#4CAF50"
                            Layout.preferredWidth: 20
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: "Latest: " + (backend.latestVersionInfo.short_hash || "Unknown")
                                font.pixelSize: 11
                                font.bold: true
                                color: backend.theme === "dark" ? "white" : "black"
                            }

                            Text {
                                text: backend.latestVersionInfo.message || "Unable to retrieve latest version"
                                font.pixelSize: 9
                                color: backend.theme === "dark" ? "#cccccc" : "#666666"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // Status message - compact
                Text {
                    text: {
                        var current = backend.currentVersionInfo.hash
                        var latest = backend.latestVersionInfo.hash
                        if (!current || !latest) {
                            return "Unable to check for updates"
                        } else if (current === latest) {
                            return "✓ You are up to date!"
                        } else {
                            return "⬆ New version available!"
                        }
                    }
                    font.pixelSize: 12
                    font.bold: true
                    color: {
                        var current = backend.currentVersionInfo.hash
                        var latest = backend.latestVersionInfo.hash
                        if (!current || !latest) {
                            return "#F44336"
                        } else if (current === latest) {
                            return "#4CAF50"
                        } else {
                            return "#FF9800"
                        }
                    }
                    Layout.alignment: Qt.AlignHCenter
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
                                (backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0")
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
                        text: "Cancel"
                        Layout.preferredWidth: 70
                        Layout.preferredHeight: 28
                        onClicked: updatePopup.close()

                        background: Rectangle {
                            color: backend.theme === "dark" ? "#4a4e4e" : "#e0e0e0"
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
                        text: "Update Now"
                        Layout.preferredWidth: 90
                        Layout.preferredHeight: 28
                        visible: {
                            var current = backend.currentVersionInfo.hash
                            var latest = backend.latestVersionInfo.hash
                            return current && latest && current !== latest
                        }
                        onClicked: {
                            backend.runUpdateScript()
                            updatePopup.close()
                        }

                        background: Rectangle {
                            color: "#4CAF50"
                            radius: 3
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "white"
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
                updatePopup.open()
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
                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                radius: 8
                border.color: backend.theme === "dark" ? "#3a3e3e" : "#e0e0e0"
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
                            color: backend.theme === "dark" ? "#1a1e1e" : "#ffffff"
                            border.color: backend.theme === "dark" ? "#3a3e3e" : "#cccccc"
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
                        color: backend.theme === "dark" ? "#4a4e4e" : "#d0d0d0"
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
            height: 25  // Start with larger collapsed height
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

            property real expandedHeight: parent.height
            property real collapsedHeight: 25  // Increased for better visibility when collapsed
            property var nextLaunch: null
            property real colorFactor: (height - collapsedHeight) / (expandedHeight - collapsedHeight)
            property color collapsedColor: "#FF3838"
            property color expandedColor: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
            property string tMinus: ""

            Timer {
                interval: 1000  // Update every second for testing
                running: true
                repeat: true
                onTriggered: {
                    var next = backend.get_next_launch();
                    launchTray.nextLaunch = next;
                    // Use the backend's countdown calculation for consistency
                    launchTray.tMinus = backend.countdown;
                }
            }

            background: Rectangle {
                color: Qt.rgba(
                    launchTray.collapsedColor.r + launchTray.colorFactor * (launchTray.expandedColor.r - launchTray.collapsedColor.r),
                    launchTray.collapsedColor.g + launchTray.colorFactor * (launchTray.expandedColor.g - launchTray.collapsedColor.g),
                    launchTray.collapsedColor.b + launchTray.colorFactor * (launchTray.expandedColor.b - launchTray.collapsedColor.b),
                    0.7 + launchTray.colorFactor * 0.3  // Fade from 70% to 100% opacity
                )
                radius: 12
                border.width: 0

                Behavior on color {
                    ColorAnimation { duration: 300 }
                }
            }

            // Smooth animation for height changes
            Behavior on height {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.OutCubic
                }
            }

            // Bottom status text - T-minus on left, launch name on right
            Item {
                width: parent.width
                height: 20
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 3  // Moved up slightly for better centering
                z: -1  // Ensure this is behind the drag handle

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

            // Drag handle at bottom
            /*
            Rectangle {
                width: parent.width
                height: 60  // Reduced height for more compact touch area
                color: "transparent"
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 2  // Small gap to match original spacing
                z: 1  // Ensure this is on top for touch events

                // Double chevron indicator
                Item {
                    width: 60
                    height: 30
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: -3  // Moved down slightly for better centering
                    anchors.horizontalCenter: parent.horizontalCenter

                    Image {
                        source: "file:///" + chevronPath
                        width: 24
                        height: 24
                        anchors.centerIn: parent
                        rotation: launchTray.height > launchTray.collapsedHeight + 50 ? -90 : 90  // Point up when expanded, down when collapsed
                        Behavior on rotation {
                            NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent  // Now fills the larger 40px height area

                    property point startGlobalPos: Qt.point(0, 0)
                    property real startHeight: 0
                    property bool isDragging: false

                    onPressed: {
                        startGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                        startHeight = launchTray.height
                        isDragging = true
                    }

                    onPositionChanged: {
                        if (isDragging && pressed) {
                            var currentGlobalPos = mapToGlobal(Qt.point(mouse.x, mouse.y))
                            var deltaY = currentGlobalPos.y - startGlobalPos.y
                            var newHeight = startHeight + deltaY

                            // Constrain the height
                            newHeight = Math.max(launchTray.collapsedHeight, Math.min(launchTray.expandedHeight, newHeight))

                            launchTray.height = newHeight
                        }
                    }

                    onReleased: {
                        isDragging = false

                        // Snap based on drag distance from start position
                        var delta = launchTray.height - startHeight
                        var range = launchTray.expandedHeight - launchTray.collapsedHeight
                        var threshold = 0.15 * range

                        if (delta > threshold) {
                            // Dragged down enough, snap to expanded
                            launchTray.height = launchTray.expandedHeight
                        } else if (delta < -threshold) {
                            // Dragged up enough, snap to collapsed
                            launchTray.height = launchTray.collapsedHeight
                        } else {
                            // Not dragged enough, snap back to start
                            launchTray.height = startHeight
                        }
                    }
                }
            }
            */

            /*
            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 10
                anchors.bottomMargin: 10  // Reduced to bring content closer to bottom handle
                spacing: 10
                clip: true  // Ensure content doesn't overflow

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 15

                    RowLayout {
                        opacity: launchTray.colorFactor
                        visible: launchTray.height > launchTray.collapsedHeight + 10
                        Behavior on opacity { NumberAnimation { duration: 300 } }
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 10

                        Flickable {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            contentHeight: launchDetailsColumn.height
                            clip: true

                            Rectangle {
                                id: launchDetailsColumn
                                width: parent.width
                                radius: 12
                                color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                                implicitHeight: launchDetailsLayout.height

                                ColumnLayout {
                                    id: launchDetailsLayout
                                    anchors.fill: parent
                                    anchors.margins: 15
                                    spacing: 10

                                    ColumnLayout {
                                        spacing: 6

                                        Text {
                                            text: "🚀 MISSION: " + (launchTray.nextLaunch ? launchTray.nextLaunch.mission.toUpperCase() : "NO UPCOMING LAUNCHES")
                                            font.pixelSize: 18
                                            font.bold: true
                                            font.letterSpacing: 1
                                            color: "#FF6B35"
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }

                                        // Table-like layout for launch details
                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📅"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LAUNCH DATE:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.local_date : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "⏰"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LAUNCH TIME:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.local_time : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📡"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "NET:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.net : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "📊"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "STATUS:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.status.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: launchTray.nextLaunch && launchTray.nextLaunch.status.toLowerCase().includes("go") ? "#00FF88" : "#FF4444"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🚀"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "VEHICLE:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.rocket.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🛰️"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "ORBIT:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.orbit.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🏗️"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "PAD:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.pad.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            visible: launchTray.nextLaunch && launchTray.nextLaunch.landing_type
                                            Text {
                                                text: "🛬"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LANDING:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch && launchTray.nextLaunch.landing_type ? launchTray.nextLaunch.landing_type.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            visible: launchTray.nextLaunch && launchTray.nextLaunch.landing_location
                                            Text {
                                                text: "📍"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "LOC:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch && launchTray.nextLaunch.landing_location ? launchTray.nextLaunch.landing_location.toUpperCase() : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                            }
                                        }

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: "🎥"
                                                font.pixelSize: 14
                                                color: backend.theme === "dark" ? "black" : "white"
                                                Layout.preferredWidth: 20
                                            }
                                            Text {
                                                text: "STREAM:"
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                font.letterSpacing: 0.5
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.preferredWidth: 120
                                            }
                                            Text {
                                                text: launchTray.nextLaunch ? launchTray.nextLaunch.video_url : ""
                                                font.pixelSize: 14
                                                font.weight: Font.Medium
                                                color: backend.theme === "dark" ? "white" : "black"
                                                Layout.fillWidth: true
                                                wrapMode: Text.Wrap
                                                visible: !!launchTray.nextLaunch
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            radius: 0
                            // Match the app background so the globe appears to sit on the background
                            color: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"

                            WebEngineView {
                                id: globeView
                                anchors.fill: parent
                                anchors.margins: 0
                                url: globeUrl
                                backgroundColor: backend.theme === "dark" ? "#1a1e1e" : "#f8f8f8"
                                zoomFactor: 1.0
                                settings.javascriptCanAccessClipboard: false
                                settings.allowWindowActivationFromJavaScript: false
                                // Disable any default context menu (long-press/right-click)
                                onContextMenuRequested: function(request) { request.accepted = true }

                                onLoadingChanged: function(loadRequest) {
                                    console.log("WebEngineView loading changed:", loadRequest.status, loadRequest.url);
                                    if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                        console.log("Globe HTML loaded successfully");
                                        // Update trajectory when globe loads
                                        var trajectoryData = backend.get_launch_trajectory();
                                        if (trajectoryData) {
                                            globeView.runJavaScript("console.log('About to call updateTrajectory'); updateTrajectory(" + JSON.stringify(trajectoryData) + "); console.log('Called updateTrajectory');");
                                        }
                                        
                                        // Set initial theme
                                        globeView.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");

                                        // Ensure the globe animation loop starts/resumes on initial load
                                        try {
                                            globeView.runJavaScript("(function(){try{if(window.resumeSpin)resumeSpin();}catch(e){console.log('Globe animation start failed', e);}})();");
                                        } catch (e) { console.log("Globe JS nudge error:", e); }
                                    } else if (loadRequest.status === WebEngineView.LoadFailedStatus) {
                                        console.log("Globe HTML failed to load:", loadRequest.errorString);
                                    }
                                }

                                Connections {
                                    target: backend
                                    function onThemeChanged() {
                                        globeView.runJavaScript("if(typeof setTheme !== 'undefined') setTheme('" + backend.theme + "');");
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: launchTray.width / 3
                            Layout.fillHeight: true
                            radius: 12
                            color: backend.theme === "dark" ? "#2a2e2e" : "#f0f0f0"
                            clip: true
                            layer.enabled: true
                            layer.smooth: true

                            // Mask effect removed to avoid dependency on Qt5Compat.GraphicalEffects

                            WebEngineView {
                                id: xComView
                                anchors.fill: parent
                                anchors.margins: 5
                                layer.enabled: true
                                layer.smooth: true
                                backgroundColor: "transparent"
                                url: "https://x.com/SpaceX"
                                zoomFactor: 0.6
                                onLoadingChanged: function(loadRequest) {
                                    if (loadRequest.status === WebEngineView.LoadSucceededStatus) {
                                        if (typeof root !== 'undefined') root._injectRoundedCorners(xComView, 12)
                                    }
                                }

                                // Staggered reload for X.com view
                                Connections {
                                    target: backend
                                    function onReloadWebContent() {
                                        xComReloadTimer.start()
                                    }
                                }
                                Timer {
                                    id: xComReloadTimer
                                    interval: 4000
                                    repeat: false
                                    onTriggered: {
                                        xComView.reload()
                                        console.log("x.com view reloaded (staggered)")
                                    }
                                }
                            }
                        }
                    }
                }
            }
            */
        }

        }
    }
}
"""
