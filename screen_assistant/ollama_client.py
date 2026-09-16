"""Bounded, asynchronous requests to one loopback Ollama server."""
from __future__ import annotations

import base64
import ipaddress
import json
import time
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Qt, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkReply, QNetworkRequest

from screen_assistant.prompt import build_prompt
from screen_assistant.types import AnalysisSnapshot, ModelInfo

OLLAMA_HOST = "http://127.0.0.1:11434"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
Completion = Callable[[dict | None, str | None], None]


@dataclass
class _Operation:
    reply: QNetworkReply
    timer: QTimer
    done: Completion
    body: bytearray = field(default_factory=bytearray)


class OllamaClient(QObject):
    connection_checked = Signal(bool, str)
    models_refreshed = Signal(list)
    model_verified = Signal(object, bool, str)
    analysis_started = Signal()
    analysis_finished = Signal(str, str, int)
    analysis_failed = Signal(str)
    analysis_cancelled = Signal()

    def __init__(self, parent=None, *, base_url=OLLAMA_HOST,
                 analysis_timeout_ms=180_000, metadata_timeout_ms=8_000):
        super().__init__(parent)
        url = QUrl(base_url)
        try:
            local = ipaddress.ip_address(url.host()).is_loopback
        except ValueError:
            local = False
        if (not url.isValid() or not local or url.scheme() != "http"
                or url.userName() or url.password() or url.hasQuery()
                or url.hasFragment() or url.path() not in ("", "/")):
            raise ValueError("Ollama must use an HTTP loopback address.")
        if analysis_timeout_ms <= 0 or metadata_timeout_ms <= 0:
            raise ValueError("Request deadlines must be positive.")
        self._base_url = base_url.rstrip("/")
        self._analysis_timeout_ms = analysis_timeout_ms
        self._metadata_timeout_ms = metadata_timeout_ms
        self._manager = QNetworkAccessManager(self)
        self._manager.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self._operations: dict[str, _Operation] = {}
        self._verified_models: dict[str, ModelInfo] = {}
        self._closed = False

    @property
    def analysis_active(self) -> bool:
        return "analysis" in self._operations

    def _detach(self, channel: str, operation: _Operation) -> bool:
        if self._operations.get(channel) is not operation:
            return False
        del self._operations[channel]
        operation.timer.stop()
        operation.timer.deleteLater()
        operation.reply.deleteLater()
        return True

    def _cancel(self, channel: str) -> bool:
        operation = self._operations.get(channel)
        if operation is None:
            return False
        # Invalidate before abort(), which can emit finished synchronously.
        self._detach(channel, operation)
        operation.reply.abort()
        return True

    def cancel_analysis(self) -> None:
        if self._cancel("analysis"):
            self.analysis_cancelled.emit()

    def invalidate_model(self) -> None:
        self._verified_models.clear()
        self._cancel("verification")

    def close(self) -> None:
        self._closed = True
        self._verified_models.clear()
        for channel in list(self._operations):
            self._cancel(channel)

    def _send(self, channel: str, path: str, payload: dict | None,
              timeout_ms: int, done: Completion) -> None:
        self._cancel(channel)
        if self._closed:
            done(None, "The client is closed.")
            return
        request = QNetworkRequest(QUrl(self._base_url + path))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        request.setTransferTimeout(timeout_ms)
        reply = (self._manager.get(request) if payload is None else
                 self._manager.post(request, json.dumps(payload).encode("utf-8")))
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        operation = _Operation(reply, timer, done)
        self._operations[channel] = operation

        def read_available() -> bool:
            if self._operations.get(channel) is not operation:
                return False
            remaining = MAX_RESPONSE_BYTES - len(operation.body)
            operation.body.extend(bytes(reply.read(remaining + 1)))
            if len(operation.body) > MAX_RESPONSE_BYTES:
                self._cancel(channel)
                done(None, "Ollama response exceeded the 8 MiB limit.")
                return False
            return True

        def finished() -> None:
            if not read_available() or not self._detach(channel, operation):
                return
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:
                data = json.loads(operation.body)
            except (ValueError, UnicodeError):
                data = None
            if status is not None and 300 <= int(status) < 400:
                done(None, "Ollama redirected the request; redirects are disabled.")
            elif reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
                message = data.get("error") if isinstance(data, dict) else None
                done(None, str(message or reply.errorString() or f"HTTP {status}"))
            elif not isinstance(data, dict):
                done(None, "Ollama returned invalid JSON; expected an object.")
            elif data.get("error"):
                done(None, str(data["error"]))
            else:
                done(data, None)

        def timed_out() -> None:
            if self._cancel(channel):
                done(None, f"Request timed out after {timeout_ms / 1000:g} seconds.")

        reply.readyRead.connect(read_available)
        reply.finished.connect(finished)
        timer.timeout.connect(timed_out)
        timer.start(timeout_ms)  # Total deadline, even for a trickling response.

    def check_connection(self) -> None:
        self.refresh_models()

    def refresh_models(self) -> None:
        self.invalidate_model()

        def completed(data, error):
            if error:
                self.models_refreshed.emit([])
                self.connection_checked.emit(False, f"Ollama unavailable: {error}")
                return
            tags = data.get("models")
            if not isinstance(tags, list) or any(
                not isinstance(tag, dict) or not isinstance(tag.get("name"), str)
                or not tag["name"].strip() for tag in tags
            ):
                self.models_refreshed.emit([])
                self.connection_checked.emit(False, "Ollama returned an invalid model list.")
                return
            models = [_model_info_from_tag(tag) for tag in tags]
            self.models_refreshed.emit(models)
            message = ("Ollama connected. Choose an installed model." if models
                       else "Ollama connected, but no models are installed.")
            self.connection_checked.emit(True, message)

        self._send("discovery", "/api/tags", None, self._metadata_timeout_ms, completed)

    def verify_model(self, name: str) -> None:
        self.invalidate_model()
        if not name:
            return

        def completed(data, error):
            vision = False
            completion = False
            if error is None:
                capabilities = data.get("capabilities")
                if not isinstance(capabilities, list) or not all(
                    isinstance(item, str) for item in capabilities
                ):
                    error = "Model capabilities are missing or invalid."
                elif name.lower().endswith(":cloud") or data.get("remote_host") or data.get("remote_model"):
                    error = "Cloud models are not supported. Choose a local model."
                elif "completion" not in capabilities:
                    error = "This model cannot generate answers. Choose a text or vision model."
                else:
                    completion = True
                    vision = "vision" in capabilities
            info = ModelInfo(name=name, is_available=completion, is_vision=vision,
                             extra=error or "Answer capability verified",
                             is_completion=completion)
            if completion:
                self._verified_models[name] = info
            kind = "Text and image model" if vision else "Text model"
            self.model_verified.emit(info, completion, error or f"{kind} ready: {name}")

        self._send("verification", "/api/show", {"model": name},
                   self._metadata_timeout_ms, completed)

    def run_analysis(self, snapshot: AnalysisSnapshot) -> None:
        self.cancel_analysis()
        model = self._verified_models.get(snapshot.model_name)
        if model is None:
            self.analysis_failed.emit("Select and verify an installed model first.")
            return
        if snapshot.image is not None and not model.is_vision:
            self.analysis_failed.emit(
                "This model does not support images. Clear the image or choose a vision model.")
            return
        try:
            system, user = build_prompt(snapshot.question, has_image=snapshot.image is not None)
        except ValueError as exc:
            self.analysis_failed.emit(str(exc))
            return
        user_message = {"role": "user", "content": user}
        if snapshot.image is not None:
            user_message["images"] = [base64.b64encode(snapshot.image.bytes_).decode("ascii")]
        payload = {
            "model": snapshot.model_name,
            "messages": [
                {"role": "system", "content": system},
                user_message,
            ],
            "stream": False,
        }
        model_name = snapshot.model_name
        started = time.monotonic()

        def completed(data, error):
            if error is None:
                answer = _extract_answer(data)
                if data.get("done") is not True:
                    error = "Ollama returned an incomplete non-streaming response."
                elif answer is None:
                    error = "Ollama returned an empty answer."
            if error:
                self.analysis_failed.emit(error)
            else:
                self.analysis_finished.emit(
                    answer, model_name, int((time.monotonic() - started) * 1000)
                )

        self.analysis_started.emit()
        self._send("analysis", "/api/chat", payload, self._analysis_timeout_ms, completed)


def _model_info_from_tag(tag: dict) -> ModelInfo:
    # /api/tags lists models; /api/show verifies answer and image support.
    return ModelInfo(name=tag["name"], is_available=True, is_vision=False, extra="Unverified")


def _extract_answer(payload: dict) -> str | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            part["text"] for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return (content.strip() or None) if isinstance(content, str) else None
