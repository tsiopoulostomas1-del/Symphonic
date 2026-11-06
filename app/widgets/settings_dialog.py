from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QEasingCurve
from app.settings import save_settings
from app.subsonic import SubsonicClient

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Settings")
        self.setFixedSize(420, 400) # Slightly wider and taller
        self.setObjectName("settingsDialog")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.title_messages = [
            "Connect to Navidrome",
            "Discover your music",
            "Stream your favorite tracks",
            "Symphonize your day!",
        ]
        self.title_index = 0
        self.title_label = QLabel(self.title_messages[self.title_index])
        self.title_label.setObjectName("dialogTitle")
        self.title_label.setMinimumHeight(30)
        self.title_opacity = QGraphicsOpacityEffect(self.title_label)
        self.title_label.setGraphicsEffect(self.title_opacity)
        layout.addWidget(self.title_label)

        self.title_animation = QPropertyAnimation(
            self.title_opacity, b"opacity", self
        )
        self.title_animation.setDuration(320)
        self.title_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.title_animation.setKeyValueAt(0.0, 1.0)
        self.title_animation.setKeyValueAt(0.45, 0.0)
        self.title_animation.setKeyValueAt(0.55, 0.0)
        self.title_animation.setKeyValueAt(1.0, 1.0)
        self.title_change_timer = QTimer(self)
        self.title_change_timer.setSingleShot(True)
        self.title_change_timer.timeout.connect(self.show_next_title)
        self.title_animation.finished.connect(self.schedule_next_title)
        self.title_cycle_timer = QTimer(self)
        self.title_cycle_timer.setInterval(2500)
        self.title_cycle_timer.timeout.connect(self.rotate_title)
        self.title_cycle_timer.start()
        layout.addSpacing(10)

        # Server URL
        url_label = QLabel("Server URL")
        url_label.setObjectName("inputLabel")
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("http://192.168.1.100:4533")
        self.server_input.setText(current_settings.get("server", ""))
        self.server_input.setFixedHeight(42) # Force height
        layout.addWidget(url_label)
        layout.addWidget(self.server_input)

        # Username
        user_label = QLabel("Username")
        user_label.setObjectName("inputLabel")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText(current_settings.get("username", ""))
        self.user_input.setFixedHeight(42) # Force height
        layout.addWidget(user_label)
        layout.addWidget(self.user_input)

        # Password
        pass_label = QLabel("Password")
        pass_label.setObjectName("inputLabel")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setText(current_settings.get("password", ""))
        self.pass_input.setFixedHeight(42) # Force height
        layout.addWidget(pass_label)
        layout.addWidget(self.pass_input)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("dialogCancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(38) # Good button height
        
        self.btn_save = QPushButton("Save & Connect")
        self.btn_save.setObjectName("dialogSaveBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(38) # Good button height
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.validate_and_save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def rotate_title(self):
        if self.title_animation.state() == QPropertyAnimation.Running:
            return
        self.title_change_timer.start(self.title_animation.duration() // 2)
        self.title_animation.start()

    def show_next_title(self):
        self.title_index = (self.title_index + 1) % len(self.title_messages)
        self.title_label.setText(self.title_messages[self.title_index])

    def schedule_next_title(self):
        self.title_change_timer.stop()

    def validate_and_save(self):
        url = self.server_input.text().strip()
        user = self.user_input.text().strip()
        pwd = self.pass_input.text()

        if not url or not user or not pwd:
            QMessageBox.warning(self, "Error", "Please fill out all fields.")
            return

        self.btn_save.setText("Connecting...")
        self.btn_save.setEnabled(False)
        
        client = SubsonicClient(url, user, pwd)
        if client.ping():
            save_settings(url, user, pwd)
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Connection Failed",
                "Could not connect to the server.\n"
                f"{client.ping_error}\n\n"
                "Check the URL, username, password, and server availability.",
            )
            self.btn_save.setText("Save & Connect")
            self.btn_save.setEnabled(True)