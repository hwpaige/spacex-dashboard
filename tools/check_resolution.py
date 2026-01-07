import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import Qt, QTimer

def check_resolution():
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
    print(f"DASHBOARD_WIDTH: {os.environ.get('DASHBOARD_WIDTH', 'Not Set (Default 1480)')}")
    print(f"DASHBOARD_HEIGHT: {os.environ.get('DASHBOARD_HEIGHT', 'Not Set (Default 320)')}")
    print(f"QT_SCREEN_SCALE_FACTORS: {os.environ.get('QT_SCREEN_SCALE_FACTORS', 'Not Set')}")
    print(f"QT_SCALE_FACTOR: {os.environ.get('QT_SCALE_FACTOR', 'Not Set')}")
    
    # Create a small window to check actual rendering
    window = QMainWindow()
    width = int(os.environ.get("DASHBOARD_WIDTH", 1480))
    height = int(os.environ.get("DASHBOARD_HEIGHT", 320))
    window.resize(width, height)
    window.setWindowTitle("Resolution Test")
    
    label = QLabel(f"Detected Screen: {size.width()}x{size.height()}\nRequested Window: {width}x{height}", window)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(label)
    
    print(f"--- Window Information ---")
    print(f"Requested Size: {width}x{height}")
    
    # Show window briefly and then exit
    QTimer.singleShot(100, lambda: (
        print(f"Actual Window Size: {window.width()}x{window.height()}"),
        print(f"Actual Window Geometry: {window.geometry().width()}x{window.geometry().height()}"),
        app.quit()
    ))
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    check_resolution()
