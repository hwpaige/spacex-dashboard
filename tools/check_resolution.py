import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import Qt, QTimer

import platform

def check_resolution():
    # Platform-aware defaults
    is_small_display = (os.environ.get("DASHBOARD_WIDTH") == "1480")
    if platform.system() == 'Windows' or is_small_display:
        default_w, default_h, default_s = 1480, 320, "1.0"
    else:
        # Default to large display resolution (3840x1100) and 2x scale for Linux
        default_w, default_h, default_s = 3840, 1100, "2.0"

    # Apply QT_SCALE_FACTOR if DASHBOARD_SCALE is set or use default
    dashboard_scale = os.environ.get("DASHBOARD_SCALE", default_s)
    if dashboard_scale != "1.0":
        os.environ["QT_SCALE_FACTOR"] = dashboard_scale

    app = QApplication(sys.argv)
    
    # Get primary screen
    screen = app.primaryScreen()
    size = screen.size()
    geometry = screen.geometry()
    logical_dpi = screen.logicalDotsPerInch()
    physical_dpi = screen.physicalDotsPerInch()
    device_pixel_ratio = screen.devicePixelRatio()
    
    print(f"--- Screen Information ---")
    print(f"Screen Name: {screen.name()}")
    print(f"Screen Size: {size.width()}x{size.height()}")
    print(f"Screen Geometry: {geometry.width()}x{geometry.height()} at {geometry.x()},{geometry.y()}")
    print(f"Logical DPI: {logical_dpi}")
    print(f"Physical DPI: {physical_dpi}")
    print(f"Device Pixel Ratio: {device_pixel_ratio}")
    print(f"--- Environment Variables ---")
    print(f"DASHBOARD_WIDTH: {os.environ.get('DASHBOARD_WIDTH', f'Not Set (Default {default_w})')}")
    print(f"DASHBOARD_HEIGHT: {os.environ.get('DASHBOARD_HEIGHT', f'Not Set (Default {default_h})')}")
    print(f"DASHBOARD_SCALE: {os.environ.get('DASHBOARD_SCALE', f'Not Set (Default {default_s})')}")
    print(f"QT_SCREEN_SCALE_FACTORS: {os.environ.get('QT_SCREEN_SCALE_FACTORS', 'Not Set')}")
    print(f"QT_SCALE_FACTOR: {os.environ.get('QT_SCALE_FACTOR', 'Not Set')}")
    
    # Create a small window to check actual rendering
    window = QMainWindow()
    width = int(os.environ.get("DASHBOARD_WIDTH", default_w))
    height = int(os.environ.get("DASHBOARD_HEIGHT", default_h))
    
    # Apply logical scaling if defined
    try:
        scale = float(os.environ.get("DASHBOARD_SCALE", default_s))
        if scale != 1.0:
            width = int(width / scale)
            height = int(height / scale)
            print(f"Applying logical scaling: {scale}x. Logical target: {width}x{height}")
    except (ValueError, TypeError):
        pass

    window.resize(width, height)
    window.setWindowTitle("Resolution Test")
    
    label = QLabel(f"Detected Screen: {size.width()}x{size.height()}\nRequested Window: {width}x{height}", window)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(label)
    
    print(f"--- Window Information ---")
    print(f"Requested Size: {width}x{height}")
    
    def on_timeout():
        actual_w = window.width()
        actual_h = window.height()
        print(f"Actual Window Size: {actual_w}x{actual_h}")
        print(f"Actual Window Geometry: {window.geometry().width()}x{window.geometry().height()}")
        
        if actual_w != width or actual_h != height:
            print("\n!!! WARNING: Render resolution does NOT match target resolution !!!")
            print("This often happens on Raspberry Pi 5 with KMS when the mode is not forced.")
            print("To fix this, please run:")
            print("sudo bash ../tools/fix_resolution.sh")
        
        app.quit()

    # Show window briefly and then exit
    QTimer.singleShot(500, on_timeout)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    check_resolution()
