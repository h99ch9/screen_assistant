"""Exercise the real widgets and Qt network client against a local fake server."""
from __future__ import annotations

import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import traceback
import zlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox

from screen_assistant.config import AppConfig
from screen_assistant.image_loader import load_image_from_path, open_image_file_dialog
from screen_assistant.main_window import MainWindow
from screen_assistant.ollama_client import OllamaClient
from screen_assistant.prompt import SYSTEM_PROMPT, TEXT_SYSTEM_PROMPT
from screen_assistant.testing import FakeOllamaServer, Response, VISION_MODEL, TEXT_MODEL, answer_response
from screen_assistant.types import AnalysisSnapshot, MAX_IMAGE_BYTES


def wait_until(predicate, timeout_ms=2000):
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(5)
    assert predicate(), f"Condition did not become true within {timeout_ms} ms"


@pytest.fixture(scope="session")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setQuitOnLastWindowClosed(False)
    return instance


@pytest.fixture(autouse=True)
def fail_on_qt_exception(monkeypatch, app):
    errors = []
    monkeypatch.setattr(sys, "excepthook",
                        lambda *args: errors.append("".join(traceback.format_exception(*args))))
    yield
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not errors, "\n".join(errors)


@pytest.fixture
def server():
    instance = FakeOllamaServer().start()
    yield instance
    instance.stop()


@pytest.fixture
def client(server):
    instance = OllamaClient(base_url=server.url)
    yield instance
    instance.close()
    instance.deleteLater()


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "rectangle.png"
    Image.new("RGB", (320, 160), "#2f80ed").save(path)
    return path


@pytest.fixture
def snapshot(image_path):
    return AnalysisSnapshot(load_image_from_path(str(image_path)), "What is visible?", VISION_MODEL)


@pytest.fixture
def window(app, server, tmp_path):
    config = AppConfig(settings=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    w = MainWindow(client=OllamaClient(base_url=server.url), config=config)
    w.show()
    QTest.qWait(20)
    yield w
    w.close()
    w.deleteLater()


def verify(client, name=VISION_MODEL):
    results = []
    client.model_verified.connect(lambda *args: results.append(args))
    client.verify_model(name)
    wait_until(lambda: results)
    return results[-1]


def open_in_window(window, path, monkeypatch):
    monkeypatch.setattr("screen_assistant.main_window.open_image_file_dialog", lambda parent: str(path))
    QTest.mouseClick(window.open_image_button, Qt.MouseButton.LeftButton)


def ready_window(window, path, monkeypatch):
    open_in_window(window, path, monkeypatch)
    QTest.mouseClick(window.check_connection_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window.model_combo.count() == 3)
    window.model_combo.setCurrentIndex(1)
    wait_until(lambda: window._state.has_verified_vision_model)
    QTest.keyClicks(window.question_input, "Describe this image")
    assert window.ask_button.isEnabled()


def select_model(window, name):
    QTest.mouseClick(window.check_connection_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window.model_combo.findData(name) > 0)
    window.model_combo.setCurrentIndex(window.model_combo.findData(name))
    wait_until(lambda: window._state.has_verified_model)


def test_import_without_window_or_background_activity():
    code = ("from PySide6.QtWidgets import QApplication; "
            "import screen_assistant, screen_assistant.__main__; "
            "assert QApplication.instance() is None; print(screen_assistant.__version__)")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.4.0"


@pytest.mark.parametrize("format,suffix", [("PNG", ".png"), ("JPEG", ".jpg"), ("JPEG", ".jpeg")])
def test_image_formats_and_unchanged_file(tmp_path, format, suffix):
    path = tmp_path / ("sample" + suffix)
    Image.new("RGB", (120, 80)).save(path, format)
    before = path.read_bytes()
    loaded = load_image_from_path(str(path))
    assert (loaded.width, loaded.height) == (120, 80)
    assert loaded.bytes_ == before == path.read_bytes()


@pytest.mark.parametrize("kind", ["empty", "corrupt", "wrong-extension", "renamed-bmp", "missing"])
def test_invalid_images(tmp_path, kind):
    path = tmp_path / ("bad.txt" if kind == "wrong-extension" else "bad.png")
    if kind != "missing":
        path.write_bytes(b"" if kind == "empty" else b"not an image")
    if kind == "renamed-bmp":
        Image.new("RGB", (10, 10)).save(path, "BMP")
    with pytest.raises(ValueError):
        load_image_from_path(str(path))


def test_image_byte_limit_before_reading(tmp_path):
    path = tmp_path / "huge.png"
    with path.open("wb") as file:
        file.truncate(MAX_IMAGE_BYTES + 1)
    with pytest.raises(ValueError, match="20 MiB"):
        load_image_from_path(str(path))


def test_image_pixel_limit_before_decode(image_path):
    raw = bytearray(image_path.read_bytes())
    raw[16:24] = struct.pack(">II", 20000, 20000)
    raw[29:33] = struct.pack(">I", zlib.crc32(raw[12:29]))
    image_path.write_bytes(raw)
    with pytest.raises(ValueError, match="25 million"):
        load_image_from_path(str(image_path))


def test_file_dialog_cancel_uses_real_import(monkeypatch):
    monkeypatch.setattr("screen_assistant.image_loader.QFileDialog.getOpenFileName",
                        lambda *args: ("", ""))
    assert open_image_file_dialog() is None


def test_connection_and_models_use_real_ollama_schema(client, server):
    lists, statuses = [], []
    client.models_refreshed.connect(lists.append)
    client.connection_checked.connect(lambda *args: statuses.append(args))
    client.check_connection()
    wait_until(lambda: statuses)
    assert statuses[-1][0] is True
    assert [item.name for item in lists[-1]] == [VISION_MODEL, TEXT_MODEL]
    assert all(not item.is_vision for item in lists[-1])
    assert server.requests_to("/api/chat") == []


@pytest.mark.parametrize("models,ok", [([], True), ("broken", False), ([{}], False)])
def test_empty_or_invalid_model_list(client, server, models, ok):
    server.routes["/api/tags"] = Response({"models": models})
    results = []
    client.connection_checked.connect(lambda *args: results.append(args))
    client.check_connection()
    wait_until(lambda: results)
    assert results[-1][0] is ok


def test_connection_refused(app):
    # Reserve an ephemeral port, then close it; no fixed test port is assumed free.
    unused = FakeOllamaServer().start()
    url = unused.url
    unused.stop()
    client = OllamaClient(base_url=url, metadata_timeout_ms=500)
    results = []
    client.connection_checked.connect(lambda *args: results.append(args))
    client.check_connection()
    wait_until(lambda: results)
    assert results[-1][0] is False
    client.close()
    client.deleteLater()


@pytest.mark.parametrize("name,vision", [(VISION_MODEL, True), (TEXT_MODEL, False)])
def test_verified_capability_not_model_name(client, server, name, vision):
    info, result, message = verify(client, name)
    assert result is True and info.is_available and info.is_completion
    assert info.is_vision is vision
    request = server.requests_to("/api/show")[-1]
    assert request["body"] == {"model": name}
    assert request["headers"]["Content-Type"].startswith("application/json")


@pytest.mark.parametrize("payload", [
    {"capabilities": {"vision": True}},
    {"capabilities": []},
    {"capabilities": ["embedding"]},
    {"capabilities": ["vision"]},
    {"capabilities": ["completion", "vision"], "remote_host": "https://ollama.com"},
    {"capabilities": ["completion"], "remote_model": "remote"},
])
def test_unknown_or_remote_capabilities_fail_closed(client, server, payload):
    server.routes["/api/show"] = Response(payload)
    assert verify(client)[1] is False


@pytest.mark.parametrize("text_only", [False, True])
def test_unverified_analysis_sends_nothing(client, snapshot, server, text_only):
    if text_only:
        snapshot = replace(snapshot, image=None)
    errors = []
    client.analysis_failed.connect(errors.append)
    client.run_analysis(snapshot)
    assert errors and not client.analysis_active
    QTest.qWait(30)
    assert not server.requests


def test_analysis_payload_and_fragmented_response(client, snapshot, server):
    assert verify(client)[1]
    server.routes["/api/chat"] = answer_response("Visible: blue rectangle.", chunk_size=7, chunk_delay=.002)
    answers, errors = [], []
    client.analysis_finished.connect(lambda *args: answers.append(args))
    client.analysis_failed.connect(errors.append)
    client.run_analysis(snapshot)
    wait_until(lambda: answers or errors)
    assert not errors
    assert answers[0][0:2] == ("Visible: blue rectangle.", VISION_MODEL)
    assert answers[0][2] > 0
    request = server.requests_to("/api/chat")[0]["body"]
    assert request["stream"] is False
    assert request["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    user = request["messages"][1]
    assert snapshot.question in user["content"]
    assert base64.b64decode(user["images"][0]) == snapshot.image.bytes_
    assert len(request["messages"]) == 2
    assert "keep_context" not in request
    assert not client.analysis_active


@pytest.mark.parametrize("model", [TEXT_MODEL, VISION_MODEL])
def test_text_question_payload_omits_images(client, server, model):
    assert verify(client, model)[1]
    server.routes["/api/chat"] = answer_response("Four.")
    answers = []
    client.analysis_finished.connect(lambda *args: answers.append(args))
    client.run_analysis(AnalysisSnapshot(None, "  What is two plus two?  ", model))
    wait_until(lambda: answers)
    assert answers[0][0:2] == ("Four.", model)
    payload = server.requests_to("/api/chat")[0]["body"]
    assert payload["model"] == model
    assert payload["messages"] == [
        {"role": "system", "content": TEXT_SYSTEM_PROMPT},
        {"role": "user", "content": "What is two plus two?"},
    ]
    assert all("images" not in message for message in payload["messages"])


def test_text_model_rejects_image_without_sending(client, server, snapshot):
    assert verify(client, TEXT_MODEL)[1]
    errors = []
    client.analysis_failed.connect(errors.append)
    client.run_analysis(replace(snapshot, model_name=TEXT_MODEL))
    assert len(errors) == 1 and "does not support images" in errors[0]
    QTest.qWait(30)
    assert not server.requests_to("/api/chat") and not client.analysis_active


@pytest.mark.parametrize("text_only", [False, True])
def test_blank_question_is_rejected_before_request(client, server, snapshot, text_only):
    assert verify(client)[1]
    errors = []
    client.analysis_failed.connect(errors.append)
    client.run_analysis(replace(snapshot, image=None if text_only else snapshot.image, question="  "))
    assert len(errors) == 1 and "empty" in errors[0]
    assert not server.requests_to("/api/chat")


@pytest.mark.parametrize("text_only", [False, True])
@pytest.mark.parametrize("response,expected", [
    (answer_response("   "), "empty"),
    (Response(b"{invalid"), "invalid JSON"),
    (Response([], 200), "invalid JSON"),
    (Response({"message": {"content": "incomplete"}, "done": False}), "incomplete"),
    (Response({"error": "model load failed"}, 500), "model load failed"),
    (Response({}, 302, headers={"Location": "/other"}), "redirect"),
])
def test_analysis_failures_are_terminal(client, snapshot, server, response, expected, text_only):
    if text_only:
        snapshot = replace(snapshot, image=None)
    assert verify(client)[1]
    server.routes["/api/chat"] = response
    errors, answers = [], []
    client.analysis_failed.connect(errors.append)
    client.analysis_finished.connect(lambda *args: answers.append(args))
    client.run_analysis(snapshot)
    wait_until(lambda: errors)
    assert expected.lower() in errors[0].lower()
    assert len(errors) == 1 and not answers and not client.analysis_active
    assert not server.requests_to("/other")


@pytest.mark.parametrize("text_only", [False, True])
@pytest.mark.parametrize("trickle", [False, True])
def test_total_deadline_stops_slow_response(app, snapshot, server, trickle, text_only):
    if text_only:
        snapshot = replace(snapshot, image=None)
    client = OllamaClient(base_url=server.url, analysis_timeout_ms=120)
    assert verify(client)[1]
    server.routes["/api/chat"] = (
        answer_response(chunk_size=1, chunk_delay=.03) if trickle else answer_response(delay=.8)
    )
    errors, answers = [], []
    client.analysis_failed.connect(errors.append)
    client.analysis_finished.connect(lambda *args: answers.append(args))
    started = time.monotonic()
    client.run_analysis(snapshot)
    wait_until(lambda: errors, 1000)
    assert time.monotonic() - started < .8
    assert "timed out" in errors[0].lower() or "timeout" in errors[0].lower()
    QTest.qWait(160)
    assert len(errors) == 1 and not answers and not client.analysis_active
    client.close()
    client.deleteLater()


@pytest.mark.parametrize("text_only", [False, True])
@pytest.mark.parametrize("cancel_first", [True, False])
def test_cancel_and_late_reply_cannot_replace_new_answer(client, snapshot, server, cancel_first, text_only):
    if text_only:
        snapshot = replace(snapshot, image=None)
    assert verify(client)[1]
    server.routes["/api/chat"] = lambda request: (
        answer_response("old", delay=.3) if len(server.requests_to("/api/chat")) == 1
        else answer_response("new")
    )
    answers, errors, cancelled = [], [], []
    client.analysis_finished.connect(lambda *args: answers.append(args))
    client.analysis_failed.connect(errors.append)
    client.analysis_cancelled.connect(lambda: cancelled.append(True))
    client.run_analysis(snapshot)
    wait_until(lambda: len(server.requests_to("/api/chat")) == 1)
    if cancel_first:
        client.cancel_analysis()
        assert not client.analysis_active and cancelled == [True]
    client.run_analysis(snapshot)
    assert cancelled == [True]
    wait_until(lambda: answers)
    QTest.qWait(400)
    assert [a[0] for a in answers] == ["new"]
    assert not errors and not client.analysis_active


def test_superseded_model_verification_cannot_enable_old_model(client, server):
    server.routes["/api/show"] = lambda r: Response(
        {"capabilities": ["completion", "vision"] if r["body"]["model"] == VISION_MODEL
         else ["completion"]},
        delay=.25 if r["body"]["model"] == VISION_MODEL else 0)
    results = []
    client.model_verified.connect(lambda *args: results.append(args))
    client.verify_model(VISION_MODEL)
    wait_until(lambda: server.requests_to("/api/show"))
    client.verify_model(TEXT_MODEL)
    wait_until(lambda: results)
    QTest.qWait(300)
    assert len(results) == 1 and results[0][0].name == TEXT_MODEL and results[0][1] is True
    assert not results[0][0].is_vision


def test_foundation_startup_and_about_dialog(window, app, server):
    assert window.windowTitle() == "Screen Assistant"
    assert not window.ask_button.isEnabled()
    assert not window.cancel_button.isEnabled()
    assert window.question_input.isEnabled()
    assert window.observation_indicator.text() == "Observation off"
    assert window.source_indicator.text() == "Text only — no image"
    assert window._state.image is None
    seen = []
    def dismiss():
        dialog = app.activeModalWidget()
        if dialog is not None:
            seen.append(dialog.windowTitle())
            box = dialog.findChild(QDialogButtonBox)
            if box:
                QTest.mouseClick(box.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
            elif isinstance(dialog, QDialog):
                dialog.reject()
    # A second timer bounds the modal path if focus/layout delays the first.
    QTimer.singleShot(50, dismiss)
    QTimer.singleShot(300, dismiss)
    window.about_action.trigger()
    assert seen == ["About Screen Assistant"]
    assert app.activeModalWidget() is None
    assert not server.requests


def test_ui_open_select_type_ask_and_clear(window, image_path, monkeypatch, server):
    before = image_path.read_bytes()
    open_in_window(window, image_path, monkeypatch)
    assert window.clear_image_button.isEnabled()
    assert not window.ask_button.isEnabled()
    QTest.qWait(30)
    assert not server.requests
    QTest.mouseClick(window.check_connection_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window.model_combo.count() == 3)
    window.model_combo.setCurrentIndex(2)
    wait_until(lambda: "does not support" in window.connection_status.text())
    QTest.keyClicks(window.question_input, "Explain")
    assert not window.ask_button.isEnabled()
    window.model_combo.setCurrentIndex(1)
    wait_until(lambda: window.ask_button.isEnabled())
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window._state.answer is not None)
    assert "rectangle" in window._answer_text.toPlainText()
    assert "Elapsed:" in window._answer_meta.text()
    assert window.ask_button.isEnabled() and not window.cancel_button.isEnabled()
    QTest.mouseClick(window.clear_image_button, Qt.MouseButton.LeftButton)
    assert window._state.image is None and window._state.answer is None
    assert window.ask_button.isEnabled() and window.question_input.text() == "Explain"
    assert window._preview_label.pixmap().isNull()
    assert image_path.read_bytes() == before
    assert len(server.requests_to("/api/chat")) == 1


@pytest.mark.parametrize("model", [TEXT_MODEL, VISION_MODEL])
def test_ui_asks_without_image_and_without_history(window, server, model):
    server.routes["/api/chat"] = answer_response("A text answer.", delay=.04)
    window.question_input.setText("First question")
    assert not window.ask_button.isEnabled()
    select_model(window, model)
    window.question_input.setText("  ")
    assert not window.ask_button.isEnabled()
    window.question_input.setText("First question")
    assert window.ask_button.isEnabled()
    assert "text questions" in window.connection_status.text()
    assert "no image" in window.source_indicator.text()
    QTest.keyClick(window.question_input, Qt.Key.Key_Return)
    wait_until(lambda: window._state.answer is not None)
    assert window._answer_text.toPlainText() == "A text answer."
    window.question_input.setText("Second question")
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    assert not window.ask_button.isEnabled() and window.cancel_button.isEnabled()
    wait_until(lambda: not window._state.request_active)
    requests = server.requests_to("/api/chat")
    assert len(requests) == 2
    assert requests[-1]["body"]["messages"] == [
        {"role": "system", "content": TEXT_SYSTEM_PROMPT},
        {"role": "user", "content": "Second question"},
    ]
    assert window._state.image is None
    assert not window.clear_image_button.isEnabled()
    assert window.observation_indicator.text() == "Observation off"


def test_clear_image_allows_text_model_without_resending_image(window, server, image_path, monkeypatch):
    select_model(window, TEXT_MODEL)
    window.question_input.setText("Explain this")
    assert window.ask_button.isEnabled()
    open_in_window(window, image_path, monkeypatch)
    assert not window.ask_button.isEnabled()
    assert "Clear the image" in window.connection_status.text()
    assert not server.requests_to("/api/chat")
    QTest.mouseClick(window.clear_image_button, Qt.MouseButton.LeftButton)
    assert window.ask_button.isEnabled() and window.question_input.text() == "Explain this"
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window._state.answer is not None)
    messages = server.requests_to("/api/chat")[0]["body"]["messages"]
    assert all("images" not in message for message in messages)
    assert messages[-1]["content"] == "Explain this"


@pytest.mark.parametrize("action", ["cancel", "attach", "switch", "close"])
def test_text_request_invalidated_by_ui_change(window, server, image_path, monkeypatch, action):
    select_model(window, TEXT_MODEL)
    window.question_input.setText("A text question")
    server.routes["/api/chat"] = answer_response("obsolete text answer", delay=.25)
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: server.requests_to("/api/chat"))
    if action == "cancel":
        QTest.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
    elif action == "attach":
        open_in_window(window, image_path, monkeypatch)
    elif action == "switch":
        window.model_combo.setCurrentIndex(window.model_combo.findData(VISION_MODEL))
    else:
        window.close()
    QTest.qWait(350)
    assert window._state.answer is None and not window._state.request_active
    assert "obsolete text answer" not in window._answer_text.toPlainText()
    assert not window._client.analysis_active


@pytest.mark.parametrize("action", ["cancel", "clear", "replace", "switch", "close"])
def test_ui_changes_cancel_pending_answer(window, image_path, monkeypatch, server, tmp_path, action):
    ready_window(window, image_path, monkeypatch)
    server.routes["/api/chat"] = answer_response("obsolete answer", delay=.3)
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: server.requests_to("/api/chat"))
    assert window.cancel_button.isEnabled()
    assert not window.ask_button.isEnabled()
    if action == "cancel":
        QTest.mouseClick(window.cancel_button, Qt.MouseButton.LeftButton)
    elif action == "clear":
        QTest.mouseClick(window.clear_image_button, Qt.MouseButton.LeftButton)
    elif action == "replace":
        replacement = tmp_path / "replacement.png"
        Image.new("RGB", (50, 70)).save(replacement)
        open_in_window(window, replacement, monkeypatch)
    elif action == "switch":
        window.model_combo.setCurrentIndex(2)
    else:
        window.close()
    QTest.qWait(400)
    assert window._state.answer is None
    assert "obsolete answer" not in window._answer_text.toPlainText()
    assert not window._client.analysis_active
    assert not window._state.request_active
    if action != "close":
        assert window.question_input.isEnabled()


def test_foundation_preview_resizes_without_growing_minimum(window, image_path, monkeypatch):
    open_in_window(window, image_path, monkeypatch)
    for width, height in [(1100, 800), (620, 440), (900, 600), (620, 440)]:
        window.resize(width, height)
        QTest.qWait(30)
        assert window.width() == width and window.height() == height
        pixmap = window._preview_label.pixmap()
        area = window._preview_label.contentsRect()
        assert pixmap.width() <= area.width() and pixmap.height() <= area.height()
        assert abs(pixmap.width() / pixmap.height() - 2) < .04
        for widget in (window.ask_button, window.open_image_button,
                       window.model_combo, window.observation_indicator):
            assert widget.isVisible()
            assert widget.width() > 0 and widget.height() > 0


@pytest.mark.parametrize("close_method", ["quit", "shortcut", "close"])
def test_foundation_geometry_and_clean_quit(app, tmp_path, close_method):
    settings = QSettings(str(tmp_path / "geometry.ini"), QSettings.Format.IniFormat)
    settings.setValue("observations_on", True)
    config = AppConfig(settings=settings)
    first = MainWindow(config=config)
    first.show()
    first.resize(750, 530)
    QTest.qWait(30)
    assert first.observation_indicator.text() == "Observation off"
    if close_method == "quit":
        first.quit_action.trigger()
    elif close_method == "shortcut":
        first.activateWindow()
        first.question_input.setFocus()
        QTest.qWait(30)
        QTest.keyClick(first.question_input, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    else:
        first.close()
    wait_until(lambda: not first.isVisible())
    assert not first._client.analysis_active
    assert settings.allKeys() == ["geometry"]
    second = MainWindow(config=AppConfig(settings=settings))
    second.show()
    QTest.qWait(20)
    assert second.size() == first.size()
    assert second.observation_indicator.text() == "Observation off"
    second.close()
    first.deleteLater()
    second.deleteLater()


def test_foundation_invalid_geometry_is_ignored(app, tmp_path):
    settings = QSettings(str(tmp_path / "bad.ini"), QSettings.Format.IniFormat)
    settings.setValue("geometry", "not geometry")
    window = MainWindow(config=AppConfig(settings=settings))
    assert window.size().width() == 960
    window.close()
    window.deleteLater()


def test_foundation_application_event_loop_exits_cleanly(tmp_path):
    code = '''
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from screen_assistant.main_window import MainWindow
app = QApplication([])
window = MainWindow()
window.show()
QTimer.singleShot(50, window.quit_action.trigger)
QTimer.singleShot(1500, lambda: app.exit(99))
raise SystemExit(app.exec())
'''
    result = subprocess.run([sys.executable, "-c", code], timeout=5, capture_output=True,
                            text=True, env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path)})
    assert result.returncode == 0, result.stderr


def test_oversized_server_response_fails_once(client, snapshot, server):
    assert verify(client)[1]
    server.routes["/api/chat"] = Response(b"x" * (8 * 1024 * 1024 + 1))
    errors = []
    client.analysis_failed.connect(errors.append)
    client.run_analysis(snapshot)
    wait_until(lambda: errors)
    assert "8 MiB" in errors[0]
    assert len(errors) == 1 and not client.analysis_active


def test_cancelled_file_picker_preserves_current_image(window, image_path, monkeypatch, server):
    open_in_window(window, image_path, monkeypatch)
    previous = window._state.image
    monkeypatch.setattr("screen_assistant.main_window.open_image_file_dialog", lambda parent: None)
    QTest.mouseClick(window.open_image_button, Qt.MouseButton.LeftButton)
    assert window._state.image is previous
    assert not server.requests


@pytest.mark.parametrize("scale", [1, 1.25, 2])
def test_capture_crop_maps_pixels_and_encodes_same_preview(app, scale):
    from PySide6.QtCore import QRectF, QSize
    from PySide6.QtGui import QImage, QPixmap
    from screen_assistant.capture import crop_snapshot
    frame = QPixmap(int(200 * scale), int(100 * scale))
    frame.fill(Qt.GlobalColor.red)
    frame.setDevicePixelRatio(scale)
    image = crop_snapshot(frame, QRectF(20, 10, 40, 20), QSize(200, 100), "Capture test")
    assert (image.width, image.height) == ((50, 26) if scale == 1.25 else (int(40 * scale), int(20 * scale)))
    decoded = QImage.fromData(image.bytes_, "PNG")
    assert decoded == image.pixmap.toImage()
    assert decoded.pixelColor(0, 0) == Qt.GlobalColor.red


def test_capture_selector_reverse_drag_and_escape(app):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QPixmap
    from screen_assistant.capture import RegionSelector
    frame = QPixmap(200, 100)
    frame.fill(Qt.GlobalColor.blue)
    dialog = RegionSelector(frame, QRect(-200, 0, 200, 100))
    dialog.show()
    QTest.mousePress(dialog, Qt.MouseButton.LeftButton, pos=QPoint(150, 80))
    QTest.mouseRelease(dialog, Qt.MouseButton.LeftButton, pos=QPoint(30, 20))
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selection.width() == 120 and dialog.selection.height() == 60
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.deleteLater()


def fake_capture(monkeypatch, result):
    monkeypatch.setattr("screen_assistant.main_window.capture_unavailable_reason", lambda: "")
    monkeypatch.setattr("screen_assistant.main_window.choose_screen", lambda parent: object())
    def select(screen, parent):
        assert not parent.isVisible()
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr("screen_assistant.main_window.select_region", select)


def test_capture_preview_sends_only_on_ask_then_clear(window, server, monkeypatch, image_path):
    image = replace(load_image_from_path(str(image_path)), path="Capture test time")
    fake_capture(monkeypatch, image)
    select_model(window, VISION_MODEL)
    window.question_input.setText("Explain selected area")
    QTest.mouseClick(window.capture_button, Qt.MouseButton.LeftButton)
    assert window._capturing and not window.ask_button.isEnabled()
    wait_until(lambda: not window._capturing)
    assert window.isVisible() and window._state.image is image
    assert window._central_stack.currentWidget() is window._preview_area
    assert not server.requests_to("/api/chat")
    assert window.observation_indicator.text() == "Observation off"
    QTest.mouseClick(window.ask_button, Qt.MouseButton.LeftButton)
    wait_until(lambda: window._state.answer is not None)
    payload = server.requests_to("/api/chat")[-1]["body"]
    assert base64.b64decode(payload["messages"][-1]["images"][0]) == image.bytes_
    window._on_clear_image()
    window._on_ask_pressed()
    wait_until(lambda: window._state.answer is not None)
    assert "images" not in server.requests_to("/api/chat")[-1]["body"]["messages"][-1]


@pytest.mark.parametrize("result", [None, ValueError("Display unavailable")])
def test_capture_cancel_or_error_preserves_image_and_question(window, server, monkeypatch, image_path, result):
    open_in_window(window, image_path, monkeypatch)
    old = window._state.image
    window.question_input.setText("Keep this question")
    fake_capture(monkeypatch, result)
    warnings = []
    monkeypatch.setattr("screen_assistant.main_window.QMessageBox.warning", lambda *args: warnings.append(args))
    window._on_capture_area()
    wait_until(lambda: not window._capturing)
    assert window.isVisible() and window._state.image is old
    assert window.question_input.text() == "Keep this question"
    assert bool(warnings) == isinstance(result, Exception)
    assert not server.requests


def test_close_before_capture_timer_does_not_reopen(window, monkeypatch, server):
    fake_capture(monkeypatch, None)
    calls = []
    monkeypatch.setattr("screen_assistant.main_window.select_region", lambda *args: calls.append(args))
    window._on_capture_area()
    window.close()
    QTest.qWait(350)
    assert not calls and not window.isVisible() and not server.requests


def test_capture_with_text_model_blocks_image_request(window, monkeypatch, image_path, server):
    select_model(window, TEXT_MODEL)
    fake_capture(monkeypatch, load_image_from_path(str(image_path)))
    window.question_input.setText("Explain")
    window._on_capture_area()
    wait_until(lambda: not window._capturing)
    assert not window.ask_button.isEnabled()
    window._on_ask_pressed()
    assert not server.requests_to("/api/chat")


def test_capture_unsupported_session_does_not_hide_or_collect(window, monkeypatch, server):
    monkeypatch.setattr("screen_assistant.main_window.capture_unavailable_reason", lambda: "Use Open image.")
    messages = []
    monkeypatch.setattr("screen_assistant.main_window.QMessageBox.information", lambda *args: messages.append(args))
    window._on_capture_area()
    assert messages and window.isVisible() and not window._capturing
    assert not server.requests


def test_capture_crop_excludes_surrounding_pixels(app):
    from PySide6.QtCore import QRectF, QSize
    from PySide6.QtGui import QImage, QPixmap
    from screen_assistant.capture import crop_snapshot
    frame = QImage(100, 100, QImage.Format.Format_RGB32)
    frame.fill(Qt.GlobalColor.red)
    for x in range(30, 50):
        for y in range(40, 60):
            frame.setPixelColor(x, y, Qt.GlobalColor.blue)
    image = crop_snapshot(QPixmap.fromImage(frame), QRectF(30, 40, 20, 20), QSize(100, 100), "test")
    decoded = QImage.fromData(image.bytes_)
    assert decoded.size() == QSize(20, 20)
    assert all(decoded.pixelColor(x, y) == Qt.GlobalColor.blue for x in range(20) for y in range(20))


def test_capture_invalidates_pending_answer(window, server, monkeypatch, image_path):
    select_model(window, TEXT_MODEL)
    window.question_input.setText("Old question")
    server.routes["/api/chat"] = answer_response("obsolete reply", delay=.6)
    window._on_ask_pressed()
    wait_until(lambda: server.requests_to("/api/chat"))
    fake_capture(monkeypatch, load_image_from_path(str(image_path)))
    window._on_capture_area()
    wait_until(lambda: not window._capturing)
    QTest.qWait(400)
    assert window._state.answer is None
    assert "obsolete reply" not in window._answer_text.toPlainText()
    assert len(server.requests_to("/api/chat")) == 1


def test_close_rejects_active_selector(window):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QPixmap
    from screen_assistant.capture import RegionSelector
    frame = QPixmap(200, 100)
    frame.fill(Qt.GlobalColor.blue)
    selector = RegionSelector(frame, QRect(0, 0, 200, 100), window)
    QTimer.singleShot(10, window.close)
    assert selector.exec() == QDialog.DialogCode.Rejected
    assert not window.isVisible()
    selector.deleteLater()
