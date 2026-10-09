"""One-shot X11 capture. Only the selected crop survives the selector."""
from __future__ import annotations

from datetime import datetime
import math
import os
import sys

from PySide6.QtCore import QBuffer, QIODevice, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QInputDialog

from screen_assistant.types import LoadedImage, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS


def capture_unavailable_reason():
    if (sys.platform != "linux" or QGuiApplication.platformName() != "xcb"
            or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
            or os.environ.get("WAYLAND_DISPLAY")):
        return "Capture area currently requires Linux X11. On other sessions, take a screenshot and use Open image."
    return ""


def choose_screen(parent):
    screens = QGuiApplication.screens()
    if not screens:
        raise ValueError("No display is available. Use Open image.")
    if len(screens) == 1:
        return screens[0]
    labels = [f"{i + 1}: {s.name()} ({s.geometry().width()} × {s.geometry().height()})"
              for i, s in enumerate(screens)]
    choice, ok = QInputDialog.getItem(parent, "Capture area", "Choose a display:", labels, 0, False)
    return screens[labels.index(choice)] if ok else None


def crop_snapshot(frame, selection, logical_size, label):
    """Map logical selection edges to physical pixels, including fractional scaling."""
    bounds = QRectF(0, 0, logical_size.width(), logical_size.height())
    rect = QRectF(selection).normalized().intersected(bounds)
    if rect.width() < 2 or rect.height() < 2 or frame.isNull():
        raise ValueError("Drag an area at least 2 × 2 pixels wide.")
    sx, sy = frame.width() / bounds.width(), frame.height() / bounds.height()
    left, top = math.floor(rect.left() * sx), math.floor(rect.top() * sy)
    right, bottom = math.ceil(rect.right() * sx), math.ceil(rect.bottom() * sy)
    pixels = QRect(left, top, right - left, bottom - top).intersected(frame.rect())
    if pixels.width() * pixels.height() > MAX_IMAGE_PIXELS:
        raise ValueError("The selection exceeds 25 million pixels. Select a smaller area.")
    crop = frame.copy(pixels)
    crop.setDevicePixelRatio(1)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not crop.save(buffer, "PNG"):
        raise ValueError("Could not encode the capture. Try again.")
    data = bytes(buffer.data())
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("The capture exceeds 20 MiB. Select a smaller area.")
    return LoadedImage(path=label, bytes_=data, pixmap=crop)


class RegionSelector(QDialog):
    def __init__(self, frame, geometry, parent=None):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.frame = frame
        self.selection = QRectF()
        self.origin = None
        self.setWindowTitle("Drag to select — Escape to cancel")
        self.setAccessibleName("Screen region selector. Drag an area; Escape cancels.")
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(geometry)
        self.setModal(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.frame)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if not self.selection.isEmpty():
            painter.save()
            painter.setClipRect(self.selection)
            painter.drawPixmap(self.rect(), self.frame)
            painter.restore()
            painter.setPen(QPen(QColor("#68bcff"), 2))
            painter.drawRect(self.selection)
        painter.fillRect(QRect(10, 10, min(500, self.width() - 20), 40), QColor("#20262e"))
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(QRect(20, 10, self.width() - 40, 40),
                         Qt.AlignmentFlag.AlignVCenter, "Drag an area • Release to preview • Esc to cancel")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.reject()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position()
            self.selection = QRectF()
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.selection = QRectF(self.origin, event.position()).normalized().intersected(QRectF(self.rect()))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.origin is not None:
            self.mouseMoveEvent(event)
            self.origin = None
            if self.selection.width() >= 2 and self.selection.height() >= 2:
                self.accept()


def select_region(screen, parent):
    if screen not in QGuiApplication.screens():
        raise ValueError("The selected display disconnected. Choose a display again.")
    geometry = screen.geometry()
    ratio = screen.devicePixelRatio()
    if geometry.width() * geometry.height() * ratio * ratio > MAX_IMAGE_PIXELS:
        raise ValueError("This display exceeds the 25 million pixel capture limit. Use Open image.")
    frame = screen.grabWindow(0)
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    if frame.isNull():
        raise ValueError("Screen capture is unavailable. Use Open image.")
    if frame.width() * frame.height() > MAX_IMAGE_PIXELS:
        raise ValueError("This display exceeds the capture size limit. Use Open image.")
    selector = RegionSelector(frame, geometry, parent)
    # Display removal or scaling changes invalidate this frozen screen selection.
    def invalidate(*args):
        selector.reject()
    screen.geometryChanged.connect(invalidate)
    QGuiApplication.instance().screenRemoved.connect(invalidate)
    try:
        if selector.exec() != QDialog.DialogCode.Accepted:
            return None
        if screen not in QGuiApplication.screens() or screen.geometry() != geometry:
            raise ValueError("The display changed. Capture again.")
        label = f"Capture {captured_at} · {screen.name().replace('/', '_')}"
        return crop_snapshot(frame, selector.selection, geometry.size(), label)
    finally:
        try:
            screen.geometryChanged.disconnect(invalidate)
        except RuntimeError:
            pass
        QGuiApplication.instance().screenRemoved.disconnect(invalidate)
        selector.frame = QPixmap()
        selector.close()
        selector.deleteLater()
