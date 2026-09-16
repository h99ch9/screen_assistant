# -*- coding: utf-8 -*-
"""Shared types and constants for questions with an optional image.

Everything here is application state used by the UI, the model client, and
the image handling code. No user content is logged here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from PySide6.QtGui import QPixmap

# Image handling limits.
MAX_IMAGE_BYTES: Final[int] = 20 * 1024 * 1024            # 20 MiB
MAX_IMAGE_PIXELS: Final[int] = 25_000_000                  # 25 million pixels

SUPPORTED_IMAGE_EXTS: Final[tuple[str, ...]] = (
    ".png",
    ".jpg",
    ".jpeg",
)

# ------------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------------


@dataclass(frozen=True)
class LoadedImage:
    """Immutable snapshot of a user-selected image for one analysis request.

    The preview and the model client use the same in-memory copy. The file
    on disk is never modified by the application.
    """

    path: str
    bytes_: bytes
    pixmap: QPixmap

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def width(self) -> int:
        return self.pixmap.width()

    @property
    def height(self) -> int:
        return self.pixmap.height()


@dataclass(frozen=True)
class ModelInfo:
    """Public description of one available Ollama model."""

    name: str
    is_available: bool
    is_vision: bool
    extra: str
    is_completion: bool = False


@dataclass(frozen=True)
class AnalysisSnapshot:
    """Immutable capture of the inputs for one analysis request.

    Taken at Ask press time so cancel / replace cannot detach the request
    from the image and question the user actually submitted.
    """

    image: LoadedImage | None
    question: str
    model_name: str
