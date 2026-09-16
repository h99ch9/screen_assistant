"""The application's single About dialog."""
import platform

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from screen_assistant import __version__


def show_about(parent=None) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("About Screen Assistant")
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    body = QLabel(
        f"Screen Assistant {__version__}\n\n"
        "Ask a local Ollama model a text question, or attach an image for a vision model. "
        "The app does not capture your screen or keep a conversation history.\n\n"
        f"Python {platform.python_version()} · PySide6 {PySide6.__version__} · Qt {qVersion()}"
    )
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setWordWrap(True)
    body.setMinimumWidth(320)
    layout.addWidget(body)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    dialog.exec()
    dialog.deleteLater()
