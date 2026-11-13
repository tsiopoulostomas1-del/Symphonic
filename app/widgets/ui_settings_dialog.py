from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from app.themes import THEMES
from app.translations import translate


class UISettingsDialog(QDialog):
    def __init__(self, current_theme, language="en", parent=None):
        super().__init__(parent)
        self.language = language
        self.setObjectName("settingsDialog")
        self.setWindowTitle(translate(language, "ui_settings"))
        self.setFixedSize(400, 230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        title = QLabel(translate(language, "ui_settings"))
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        theme_label = QLabel(translate(language, "color_theme"))
        theme_label.setObjectName("inputLabel")
        layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("languageSelector")
        for theme_id, theme in THEMES.items():
            self.theme_combo.addItem(theme["label"], theme_id)
        selected_index = self.theme_combo.findData(current_theme)
        self.theme_combo.setCurrentIndex(max(0, selected_index))
        layout.addWidget(self.theme_combo)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton(translate(language, "cancel"))
        cancel_button.setObjectName("dialogCancelBtn")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.setFixedHeight(38)
        cancel_button.clicked.connect(self.reject)
        apply_button = QPushButton(translate(language, "apply"))
        apply_button.setObjectName("dialogSaveBtn")
        apply_button.setCursor(Qt.PointingHandCursor)
        apply_button.setFixedHeight(38)
        apply_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(apply_button)
        layout.addLayout(buttons)

    @property
    def selected_theme(self) -> str:
        return self.theme_combo.currentData()
