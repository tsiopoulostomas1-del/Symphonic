import sys
from PySide6.QtWidgets import QApplication
from app.branding import app_icon
from app.main_window import MainWindow
from app.settings import load_settings
from app.themes import build_stylesheet


def load_stylesheet(app, theme="midnight"):
    try:
        app.setStyleSheet(build_stylesheet(theme))
    except FileNotFoundError:
        print("Warning: style.qss not found.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    load_stylesheet(app, load_settings().get("theme", "midnight"))
    
    window = MainWindow()
    window.showMaximized()
    
    sys.exit(app.exec())