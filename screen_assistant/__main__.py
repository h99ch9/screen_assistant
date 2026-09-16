# -*- coding: utf-8 -*-
"""Launch the Screen Assistant desktop application.

Usage from the project root (with the virtual environment active or via uv)::

    python -m screen_assistant

The module is safe to import: it does not create a QApplication or show a
window until ``main()`` is called.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from screen_assistant.main_window import MainWindow
from screen_assistant import __version__


def main() -> None:
    """Create the QApplication and show the main window."""
    app = QApplication(sys.argv)
    app.setApplicationName("Screen Assistant")
    app.setOrganizationName("ScreenAssistant")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
