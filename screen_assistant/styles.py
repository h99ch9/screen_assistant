# -*- coding: utf-8 -*-
"""Centralized application styling.

Apply once on the main window with ``window.setStyleSheet(STYLESHEET)``.
The palette is deliberately restrained: light neutral background, dark text,
a single blue accent for interactive elements, and a clear disabled state so
unfinished controls read as disabled rather than broken.
"""

from __future__ import annotations

STYLESHEET = """
QMainWindow {
    background-color: #f7f8fa;
}

QLabel {
    color: #262626;
    font-size: 14px;
}

/* Larger heading-style labels used for section titles. */
QLabel[role="title"] {
    font-size: 13px;
    font-weight: 600;
    color: #3a3a3a;
}

/* The central empty-state label. */
QLabel[role="empty-state"] {
    color: #4a4a4a;
    font-size: 14px;
    background-color: #f7f8fa;
}

/* Keep text surfaces readable when the desktop supplies a dark Qt palette. */
QScrollArea {
    background-color: #f7f8fa;
    border: none;
}

QTextEdit, QComboBox, QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #262626;
    selection-background-color: #1a73e8;
    selection-color: #ffffff;
    font-size: 14px;
}

QComboBox {
    padding: 4px;
    border: 1px solid #cfd4da;
    border-radius: 4px;
}

QToolButton {
    color: #262626;
    background-color: #f7f8fa;
}

QLineEdit {
    padding: 8px 10px;
    border: 1px solid #cfd4da;
    border-radius: 6px;
    background-color: #ffffff;
    color: #262626;
    font-size: 14px;
}

QLineEdit:focus {
    border-color: #1a73e8;
    background-color: #ffffff;
}

QPushButton {
    padding: 8px 18px;
    background-color: #1a73e8;
    color: #ffffff;
    border: 1px solid #1557b0;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    min-width: 80px;
}

QPushButton:hover:enabled {
    background-color: #1557b0;
    border-color: #0d47a0;
}

QPushButton:pressed:enabled {
    background-color: #0d47a0;
    border-color: #0a3a82;
}

QPushButton:disabled {
    background-color: #eceff3;
    color: #9aa0a6;
    border: 1px solid #cfd4da;
}

/* The Ask button uses this sharper disabled appearance so its state is easy
   to recognize at a glance. */
QPushButton#askButton:disabled {
    background-color: #eef0f3;
    color: #8a9099;
    border: 1px dashed #b9c0c9;
}

QMenuBar {
    background-color: #f0f2f5;
    spacing: 2px;
    padding: 2px 4px;
}

QMenuBar::item {
    padding: 4px 8px;
    border-radius: 4px;
    color: #262626;
}

QMenuBar::item:selected {
    background-color: #d6dbdf;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #d4d7dc;
    border-radius: 4px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 10px;
    border-radius: 4px;
    color: #262626;
}

QMenu::item:selected {
    background-color: #e9edf2;
}

QDialog {
    background-color: #f7f8fa;
}

QStatusBar {
    background-color: #f0f2f5;
    color: #5f6368;
    font-size: 13px;
}

QToolBar {
    spacing: 6px;
    padding: 4px;
    background-color: #f7f8fa;
    border: none;
}

QToolBar QPushButton {
    min-width: 72px;
}
"""
