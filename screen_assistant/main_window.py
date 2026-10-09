"""Native desktop UI for questions with an optional image and one local answer."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTextEdit,
    QToolBar, QVBoxLayout, QWidget,
)

from screen_assistant.about_dialog import show_about
from screen_assistant.config import AppConfig
from screen_assistant.capture import RegionSelector, capture_unavailable_reason, choose_screen, select_region
from screen_assistant.image_loader import (
    image_description, load_image_from_path, open_image_file_dialog, preview_pixmap,
)
from screen_assistant.ollama_client import OllamaClient
from screen_assistant.state import AppState
from screen_assistant.styles import STYLESHEET
from screen_assistant.types import AnalysisSnapshot


class MainWindow(QMainWindow):
    def __init__(self, parent=None, *, client=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Screen Assistant")
        self.resize(960, 620)
        self.setMinimumSize(620, 440)
        self._config = config if config is not None else AppConfig(self)
        self._client = client if client is not None else OllamaClient(self)
        self._state = AppState()
        self._closing = False
        self._capturing = False
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(self._finish_capture)
        self._capture_screen = None
        self._build_ui()
        self._build_menu()
        self._bind_client()
        self.setStyleSheet(STYLESHEET)
        self._config.restore_geometry(self)
        self._update_controls()

    @staticmethod
    def _label(text=""):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        return label

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)
        self._central_stack = QStackedWidget()
        root.addWidget(self._central_stack, 1)

        self._empty_state = self._label(
            "Check connection, choose an installed local model, and type a question. "
            "No image is required.\n\n"
            "To ask about an image, open a PNG or JPEG and choose a vision model. "
            "Clear image returns to text questions. Ask sends your question and any "
            "attached image to Ollama on this computer. Each question is independent.\n\n"
            "Screen observation is off. Capture area takes one screenshot on request; review the preview before pressing Ask."
        )
        self._empty_state.setProperty("role", "empty-state")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._empty_scroll = QScrollArea()
        self._empty_scroll.setWidgetResizable(True)
        self._empty_scroll.setWidget(self._empty_state)
        self._central_stack.addWidget(self._empty_scroll)

        self._preview_area = QWidget()
        layout = QVBoxLayout(self._preview_area)
        layout.setContentsMargins(0, 0, 0, 0)
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(1, 1)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._preview_label.setStyleSheet("background-color: #e9ecef;")
        self._preview_label.installEventFilter(self)
        layout.addWidget(self._preview_label, 1)
        self._image_info = self._label()
        layout.addWidget(self._image_info)
        self._central_stack.addWidget(self._preview_area)

        self._answer_view = QWidget()
        layout = QVBoxLayout(self._answer_view)
        layout.setContentsMargins(0, 0, 0, 0)
        self._answer_text = QTextEdit()
        self._answer_text.setReadOnly(True)
        layout.addWidget(self._answer_text, 1)
        self._answer_meta = self._label()
        layout.addWidget(self._answer_meta)
        self._central_stack.addWidget(self._answer_view)

        image_row = QHBoxLayout()
        self.open_image_button = QPushButton("Open image")
        self.open_image_button.clicked.connect(self._on_open_image)
        self.capture_button = QPushButton("Capture area")
        self.capture_button.clicked.connect(self._on_capture_area)
        self.clear_image_button = QPushButton("Clear image")
        self.clear_image_button.clicked.connect(self._on_clear_image)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel_pressed)
        for button in (self.open_image_button, self.capture_button, self.clear_image_button, self.cancel_button):
            image_row.addWidget(button)
        image_row.addStretch()
        root.addLayout(image_row)

        model_row = QHBoxLayout()
        model_label = self._label("Model:")
        model_row.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumContentsLength(12)
        self.model_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.addItem("—", None)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_label.setBuddy(self.model_combo)
        model_row.addWidget(self.model_combo, 1)
        self.check_connection_button = QPushButton("Check connection")
        self.check_connection_button.clicked.connect(self._on_check_connection_pressed)
        model_row.addWidget(self.check_connection_button)
        root.addLayout(model_row)
        self.connection_status = self._label("Ollama connection has not been checked.")
        root.addWidget(self.connection_status)

        question_row = QHBoxLayout()
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("Type a question — no image needed…")
        self.question_input.setAccessibleName("Question")
        self.question_input.textChanged.connect(self._update_controls)
        self.question_input.returnPressed.connect(self._on_ask_pressed)
        question_row.addWidget(self.question_input, 1)
        self.ask_button = QPushButton("Ask")
        self.ask_button.setObjectName("askButton")
        self.ask_button.clicked.connect(self._on_ask_pressed)
        question_row.addWidget(self.ask_button)
        root.addLayout(question_row)

        status_row = QHBoxLayout()
        status_row.addWidget(self._label("Source:"))
        self.source_indicator = QLabel("Text only — no image")
        self.source_indicator.setTextFormat(Qt.TextFormat.PlainText)
        self.source_indicator.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status_row.addWidget(self.source_indicator, 1)
        self.observation_indicator = self._label("Observation off")
        status_row.addWidget(self.observation_indicator)
        root.addLayout(status_row)

    def _build_menu(self):
        menu = self.menuBar().addMenu("&File")
        self.open_image_action = QAction("&Open image…", self)
        self.open_image_action.setShortcut("Ctrl+O")
        self.open_image_action.triggered.connect(self._on_open_image)
        menu.addAction(self.open_image_action)
        self.capture_action = QAction("Capture &area…", self)
        self.capture_action.setShortcut("Ctrl+Shift+A")
        self.capture_action.triggered.connect(self._on_capture_area)
        menu.addAction(self.capture_action)
        self.clear_image_action = QAction("C&lear image", self)
        self.clear_image_action.setShortcut("Ctrl+Shift+Delete")
        self.clear_image_action.triggered.connect(self._on_clear_image)
        menu.addAction(self.clear_image_action)
        menu.addSeparator()
        self.quit_action = QAction("&Quit", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)
        menu.addAction(self.quit_action)
        self.about_action = QAction("&About Screen Assistant", self)
        self.about_action.triggered.connect(lambda: show_about(self))
        self.menuBar().addMenu("&Help").addAction(self.about_action)
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.about_action)
        self.addToolBar(toolbar)

    def _bind_client(self):
        self._client.connection_checked.connect(self._on_connection_checked)
        self._client.models_refreshed.connect(self._on_models_refreshed)
        self._client.model_verified.connect(self._on_model_verified)
        self._client.analysis_started.connect(self._on_analysis_started)
        self._client.analysis_finished.connect(self._on_analysis_finished)
        self._client.analysis_failed.connect(self._on_analysis_failed)
        self._client.analysis_cancelled.connect(self._on_analysis_cancelled)

    def _clear_result_view(self):
        self._answer_text.clear()
        self._answer_meta.clear()
        self._central_stack.setCurrentWidget(
            self._preview_area if self._state.image else self._empty_scroll)

    def _on_open_image(self):
        path = open_image_file_dialog(self)
        if not path:
            return
        try:
            image = load_image_from_path(path)
        except ValueError as exc:
            QMessageBox.warning(self, "Could not open image", str(exc))
            return
        self._attach_image(image)

    def _attach_image(self, image):
        self._client.cancel_analysis()
        self._state.set_image(image)
        self._clear_result_view()
        self._image_info.setText(image_description(image))
        self._update_preview()
        self._update_controls()

    def _on_capture_area(self):
        if self._capturing or self._closing:
            return
        reason = capture_unavailable_reason()
        if reason:
            QMessageBox.information(self, "Capture unavailable", reason)
            return
        try:
            screen = choose_screen(self)
        except ValueError as exc:
            QMessageBox.warning(self, "Capture unavailable", str(exc))
            return
        if screen is None:
            return
        self._client.cancel_analysis()
        self._capturing = True
        self._capture_screen = screen
        self._update_controls()
        self.hide()
        # Let the desktop repaint without the assistant before taking the snapshot.
        self._capture_timer.start(300)

    def _finish_capture(self):
        if self._closing:
            return
        error = None
        try:
            image = select_region(self._capture_screen, self)
            if image is not None and not self._closing:
                self._attach_image(image)
        except (ValueError, RuntimeError) as exc:
            error = str(exc)
        finally:
            self._capture_screen = None
            self._capturing = False
            if not self._closing:
                self.show()
                self.raise_()
                self.activateWindow()
                self._update_controls()
                if error:
                    QMessageBox.warning(self, "Could not capture area", error)

    def _on_clear_image(self):
        self._client.cancel_analysis()
        self._state.set_image(None)
        self._preview_label.clear()
        self._image_info.clear()
        self._clear_result_view()
        self._update_controls()

    def _on_check_connection_pressed(self):
        self._client.cancel_analysis()
        self._state.set_selected_model(None)
        self._on_models_refreshed([])
        self.connection_status.setText("Checking Ollama…")
        self.check_connection_button.setEnabled(False)
        self._client.check_connection()

    def _on_models_refreshed(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("Choose a model…" if models else "—", None)
        for model in models:
            self.model_combo.addItem(model.name, model.name)
        self.model_combo.setEnabled(bool(models))
        self.model_combo.blockSignals(False)
        self._state.set_selected_model(None)
        self._clear_result_view()
        self._update_controls()

    def _on_connection_checked(self, ok, message):
        self.check_connection_button.setEnabled(True)
        self.connection_status.setText(message)

    def _on_model_changed(self, index):
        self._client.cancel_analysis()
        self._client.invalidate_model()
        self._state.set_selected_model(None)
        self._clear_result_view()
        self._update_controls()
        name = self.model_combo.currentData()
        self.connection_status.setText("Checking model capabilities…" if name else "Choose a model.")
        if name:
            self._client.verify_model(name)

    def _on_model_verified(self, info, ok, message):
        if info.name != self.model_combo.currentData() or self._closing:
            return
        self._state.set_selected_model(info if ok else None)
        self.connection_status.setText(message)
        self._update_controls()

    def _ready(self):
        return not self._ask_disabled_reason()

    def _ask_disabled_reason(self):
        if self._capturing:
            return "Finish or cancel the area selection first."
        if self._state.request_active:
            return "Wait for the current answer or press Cancel."
        if not self._state.has_verified_model:
            return "Check connection and select an installed text or vision model."
        if self._state.image is not None and not self._state.has_verified_vision_model:
            return "This model does not support images. Clear the image or choose a vision model."
        if not self.question_input.text().strip():
            return "Type a question."
        return ""

    def _on_ask_pressed(self):
        if not self._ready():
            return
        self._client.run_analysis(AnalysisSnapshot(
            image=self._state.image, question=self.question_input.text().strip(),
            model_name=self._state.selected_model.name))

    def _on_cancel_pressed(self):
        self._client.cancel_analysis()

    def _on_analysis_started(self):
        self._state.start_request()
        self._central_stack.setCurrentWidget(self._answer_view)
        self._answer_text.setPlainText("Waiting for Ollama…")
        self._answer_meta.clear()
        self._update_controls()

    def _on_analysis_cancelled(self):
        self._state.cancel_request()
        self._answer_text.setPlainText("Request cancelled.")
        self._answer_meta.clear()
        self._update_controls()

    def _on_analysis_finished(self, answer, model_name, duration_ms):
        if self._closing or not self._state.request_active:
            return
        self._state.finish_request()
        self._state.set_answer(answer, model_name, duration_ms)
        self._answer_text.setPlainText(answer)
        self._answer_meta.setText(f"Model: {model_name} · Elapsed: {duration_ms / 1000:.2f} s")
        self._update_controls()

    def _on_analysis_failed(self, message):
        if self._closing:
            return
        self._state.finish_request()
        self._state.set_error(message)
        self._central_stack.setCurrentWidget(self._answer_view)
        self._answer_text.setPlainText("Request failed.\n\n" + message)
        self._answer_meta.clear()
        self._update_controls()

    def _update_controls(self):
        reason = self._ask_disabled_reason()
        has_image = self._state.image is not None
        self.capture_button.setEnabled(not self._capturing)
        self.capture_action.setEnabled(not self._capturing)
        self.ask_button.setEnabled(not reason)
        self.ask_button.setToolTip(reason or (
            "Send this question and image." if has_image else "Send this text question."))
        self.cancel_button.setEnabled(self._state.request_active)
        self.question_input.setEnabled(not self._state.request_active)
        self.question_input.setPlaceholderText(
            "Type your question about this image…" if has_image
            else "Type a question — no image needed…")
        self.clear_image_button.setEnabled(has_image)
        self.clear_image_action.setEnabled(has_image)
        if self._state.has_verified_model:
            if has_image and not self._state.has_verified_vision_model:
                self.connection_status.setText(
                    "This model does not support images. Clear the image or choose a vision model.")
            else:
                self.connection_status.setText(
                    "Ready for image questions." if has_image else "Ready for text questions.")
        self._update_source()

    def _update_source(self):
        text = self._state.image.filename if self._state.image else "Text only — no image"
        self.source_indicator.setToolTip(text)
        self.source_indicator.setText(self.source_indicator.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideMiddle, max(1, self.source_indicator.width())))

    def _update_preview(self):
        if self._state.image:
            self._preview_label.setPixmap(preview_pixmap(
                self._state.image, self._preview_label.contentsRect()))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and watched is self._preview_label:
            self._update_preview()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_source()

    def closeEvent(self, event):
        self._closing = True
        self._capture_timer.stop()
        for selector in self.findChildren(RegionSelector):
            selector.reject()
        self._capture_screen = None
        self._client.close()
        self._state.cancel_request()
        self._state.set_image(None)
        self._state.set_selected_model(None)
        self._preview_label.clear()
        self.question_input.clear()
        self._answer_text.clear()
        self._answer_meta.clear()
        self._config.save_geometry(self)
        super().closeEvent(event)
