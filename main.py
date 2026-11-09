import sys
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

def load_stylesheet(app):
    try:
        with open("style.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: style.qss not found.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_stylesheet(app)
    
    window = MainWindow()
    window.showMaximized()
    
    sys.exit(app.exec())