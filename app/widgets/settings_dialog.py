from PySide6.QtWidgets import (
    QComboBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QTimer, QEasingCurve
from app.settings import save_settings
from app.subsonic import SubsonicClient
from app.translations import LANGUAGE_NAMES, translate

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.current_language = current_settings.get("language", "en")
        self.current_theme = current_settings.get("theme", "midnight")
        if self.current_language not in LANGUAGE_NAMES:
            self.current_language = "en"
        self.setFixedSize(420, 400) # Slightly wider and taller
        self.setObjectName("settingsDialog")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.title_messages = [f"settings_tagline_{index}" for index in range(1, 11)]
        self.title_index = 0
        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        self.title_label.setMinimumHeight(30)
        self.title_opacity = QGraphicsOpacityEffect(self.title_label)
        self.title_label.setGraphicsEffect(self.title_opacity)

        title_layout = QHBoxLayout()
        title_layout.addWidget(self.title_label, stretch=1)
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.setToolTip(translate(self.current_language, "language"))
        for language_code, language_name in LANGUAGE_NAMES.items():
            self.language_combo.addItem(language_name, language_code)
        self.language_combo.setCurrentIndex(
            self.language_combo.findData(self.current_language)
        )
        title_layout.addWidget(self.language_combo)
        layout.addLayout(title_layout)

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
        self.url_label = QLabel()
        self.url_label.setObjectName("inputLabel")
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("http://192.168.1.100:4533")
        self.server_input.setText(current_settings.get("server", ""))
        self.server_input.setFixedHeight(50) # Force height
        layout.addWidget(self.url_label)
        layout.addWidget(self.server_input)

        # Username
        self.user_label = QLabel()
        self.user_label.setObjectName("inputLabel")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Username")
        self.user_input.setText(current_settings.get("username", ""))
        self.user_input.setFixedHeight(42) # Force height
        layout.addWidget(self.user_label)
        layout.addWidget(self.user_input)

        # Password
        self.pass_label = QLabel()
        self.pass_label.setObjectName("inputLabel")
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Password")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setText(current_settings.get("password", ""))
        self.pass_input.setFixedHeight(42) # Force height
        layout.addWidget(self.pass_label)
        layout.addWidget(self.pass_input)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton()
        self.btn_cancel.setObjectName("dialogCancelBtn")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(45) # Good button height
        
        self.btn_save = QPushButton()
        self.btn_save.setObjectName("dialogSaveBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(45) # Good button height
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self.validate_and_save)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

        self.language_combo.currentIndexChanged.connect(self.update_language)
        self.update_language()

    def rotate_title(self):
        if self.title_animation.state() == QPropertyAnimation.Running:
            return
        self.title_change_timer.start(self.title_animation.duration() // 2)
        self.title_animation.start()

    def show_next_title(self):
        self.title_index = (self.title_index + 1) % len(self.title_messages)
        self.title_label.setText(
            translate(self.current_language, self.title_messages[self.title_index])
        )

    def update_language(self, index=None):
        self.current_language = self.language_combo.currentData() or "en"
        self.setWindowTitle(translate(self.current_language, "settings_title"))
        self.language_combo.setToolTip(
            translate(self.current_language, "language")
        )
        self.title_label.setText(
            translate(self.current_language, self.title_messages[self.title_index])
        )
        self.url_label.setText(translate(self.current_language, "server_url"))
        self.user_label.setText(translate(self.current_language, "username"))
        self.user_input.setPlaceholderText(
            translate(self.current_language, "username")
        )
        self.pass_label.setText(translate(self.current_language, "password"))
        self.pass_input.setPlaceholderText(
            translate(self.current_language, "password")
        )
        self.btn_cancel.setText(translate(self.current_language, "cancel"))
        self.btn_save.setText(translate(self.current_language, "save_connect"))

    def schedule_next_title(self):
        self.title_change_timer.stop()

    def validate_and_save(self):
        url = self.server_input.text().strip()
        user = self.user_input.text().strip()
        pwd = self.pass_input.text()

        if not url or not user or not pwd:
            QMessageBox.warning(
                self,
                translate(self.current_language, "error"),
                translate(self.current_language, "fill_fields"),
            )
            return

        self.btn_save.setText(translate(self.current_language, "connecting"))
        self.btn_save.setEnabled(False)
        
        client = SubsonicClient(url, user, pwd)
        if client.ping():
            save_settings(
                url, user, pwd, self.current_language, self.current_theme
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                translate(self.current_language, "connection_failed"),
                translate(self.current_language, "could_not_connect").format(
                    error=client.ping_error
                ),
            )
            self.btn_save.setText(translate(self.current_language, "save_connect"))
            self.btn_save.setEnabled(True)