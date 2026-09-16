"""Transient state for an optional image and one answer; no content persistence."""
from __future__ import annotations

from screen_assistant.types import LoadedImage, ModelInfo


class AppState:
    def __init__(self):
        self.image: LoadedImage | None = None
        self.selected_model: ModelInfo | None = None
        self.request_active = False
        self.request_cancelled = False
        self.answer: str | None = None
        self.answer_model_name: str | None = None
        self.answer_duration_ms: int | None = None
        self.error: str | None = None

    @property
    def has_verified_model(self) -> bool:
        model = self.selected_model
        return bool(model and model.is_available and model.is_completion)

    @property
    def has_verified_vision_model(self) -> bool:
        model = self.selected_model
        return bool(self.has_verified_model and model.is_vision)

    def clear_result(self) -> None:
        self.answer = self.answer_model_name = self.answer_duration_ms = None
        self.error = None

    def set_image(self, image: LoadedImage | None) -> None:
        self.image = image
        self.clear_result()

    def set_selected_model(self, model: ModelInfo | None) -> None:
        self.selected_model = model
        self.clear_result()

    def start_request(self) -> None:
        self.clear_result()
        self.request_active = True
        self.request_cancelled = False

    def cancel_request(self) -> None:
        self.request_active = False
        self.request_cancelled = True
        self.clear_result()

    def finish_request(self) -> None:
        self.request_active = False

    def set_answer(self, answer: str, model_name: str, duration_ms: int) -> None:
        self.clear_result()
        self.answer = answer
        self.answer_model_name = model_name
        self.answer_duration_ms = duration_ms

    def set_error(self, message: str) -> None:
        self.clear_result()
        self.error = message
