"""Persist window geometry only; content and observation are never restored."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QObject, QSettings

ORGANIZATION = "ScreenAssistant"
APPLICATION = "ScreenAssistant"
SETTINGS_GEOMETRY = "geometry"


def new_settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


class AppConfig(QObject):
    def __init__(self, parent=None, *, settings=None):
        super().__init__(parent)
        self._settings = settings if settings is not None else new_settings()
        # Migrate the old foundation key without discarding window geometry.
        self._settings.remove("observations_on")
        self._settings.sync()

    def restore_geometry(self, widget) -> bool:
        raw = self._settings.value(SETTINGS_GEOMETRY)
        if not isinstance(raw, (QByteArray, bytes, bytearray)) or not raw:
            return False
        return bool(widget.restoreGeometry(QByteArray(raw)))

    def save_geometry(self, widget) -> None:
        self._settings.setValue(SETTINGS_GEOMETRY, widget.saveGeometry())
        self._settings.sync()

    def is_observation_enabled(self) -> bool:
        return False
