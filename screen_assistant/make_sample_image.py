# -*- coding: utf-8 -*-
"""Create a small sample PNG that represents terminal build output.

Used only by the automated checks to exercise the image pipeline. This
image contains no sensitive content.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QFont
from PySide6.QtCore import Qt
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE / "sample_terminal.png"

FONT_FAMILY = "monospace"
BACKGROUND = QColor("#0d1117")
FOREGROUND = QColor("#f8f8f2")
ERROR_COLOR = QColor("#ff7b72")
LINE_SPACING = 22
LEFT_MARGIN = 24
TOP_MARGIN = 20


def create_sample_terminal_image() -> Path:
    """Create or overwrite the sample terminal screenshot and return its path."""
    width = 480
    height = TOP_MARGIN + 6 * LINE_SPACING + 10

    pixmap = QPixmap(width, height)
    pixmap.fill(BACKGROUND)

    painter = QPainter(pixmap)
    try:
        font = QFont(FONT_FAMILY)
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(FOREGROUND)

        lines = [
            ("user@host:~$ make build", FOREGROUND),
            ("  CC   main.c", FOREGROUND),
            ("  CC   util.c", FOREGROUND),
            ("  LD   screen-assistant", FOREGROUND),
            ("/usr/bin/ld: cannot find -lz", ERROR_COLOR),
            ("make: *** [Makefile:12] Error 1", ERROR_COLOR),
        ]
        y = TOP_MARGIN
        for text, color in lines:
            pen = QPen(color)
            painter.setPen(pen)
            painter.drawText(LEFT_MARGIN, y, text)
            y += LINE_SPACING
    finally:
        painter.end()

    pixmap.save(str(PATH), "PNG")
    return PATH


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    print(create_sample_terminal_image())
