from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer

LOGO_PATH = Path(__file__).parent / "img" / "logo.svg"


@lru_cache(maxsize=1)
def _logo_renderer() -> QSvgRenderer:
    renderer = QSvgRenderer(str(LOGO_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load app logo: {LOGO_PATH}")
    return renderer


@lru_cache(maxsize=8)
def logo_pixmap(size: int) -> QPixmap:
    render_size = size * 4
    rendered = QPixmap(render_size, render_size)
    rendered.fill(Qt.transparent)

    painter = QPainter(rendered)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    bounds = QRectF(0, 0, render_size, render_size)
    path.addRoundedRect(bounds, render_size * 0.18, render_size * 0.18)
    painter.setClipPath(path)
    _logo_renderer().render(painter, bounds)
    painter.end()
    return rendered.scaled(
        size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
    )


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(size))
    return icon
