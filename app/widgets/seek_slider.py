from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class ClickSeekSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        if handle.contains(event.pos()):
            super().mousePressEvent(event)
            return

        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        if not groove.contains(event.pos()):
            super().mousePressEvent(event)
            return

        groove_start = groove.x() + handle.width() // 2
        groove_length = max(0, groove.width() - handle.width())
        position = event.pos().x() - groove_start
        value = QStyle.sliderValueFromPosition(
            self.minimum(),
            self.maximum(),
            position,
            groove_length,
            option.upsideDown,
        )
        self.setSliderPosition(value)
        self.setValue(value)
        self.sliderMoved.emit(value)
        event.accept()
