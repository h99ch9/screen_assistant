"""Load one PNG/JPEG with limits checked before full decoding."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import QFileDialog

from screen_assistant.types import LoadedImage, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, SUPPORTED_IMAGE_EXTS


def supported_suffix(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_EXTS


def _decode(data: bytes) -> QImage:
    if not data:
        raise ValueError("The image file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("The image exceeds the 20 MiB file-size limit.")
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    if bytes(reader.format()).lower() not in (b"png", b"jpeg", b"jpg"):
        raise ValueError("Unsupported or corrupt image. Choose a PNG or JPEG.")
    size = reader.size()
    if not size.isValid() or size.isEmpty():
        raise ValueError("Could not read the image dimensions.")
    if size.width() * size.height() > MAX_IMAGE_PIXELS:
        raise ValueError("The image exceeds the 25 million pixel limit.")
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        raise ValueError("Could not decode the image; it may be corrupt.")
    if image.width() * image.height() > MAX_IMAGE_PIXELS:
        raise ValueError("The image exceeds the 25 million pixel limit.")
    return image


def validate_bytes(data: bytes) -> None:
    _decode(data)


def load_image_from_path(path: str) -> LoadedImage:
    file = Path(path).expanduser()
    if not supported_suffix(str(file)):
        raise ValueError("Choose a PNG or JPEG image (.png, .jpg, .jpeg).")
    try:
        if not file.is_file():
            raise ValueError("The selected file does not exist or is not a regular file.")
        if file.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("The image exceeds the 20 MiB file-size limit.")
        with file.open("rb") as source:
            data = source.read(MAX_IMAGE_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"Could not read the selected image: {exc.strerror or 'access failed'}") from exc
    image = _decode(data)
    return LoadedImage(path=str(file.resolve()), bytes_=data, pixmap=QPixmap.fromImage(image))


def open_image_file_dialog(parent=None) -> str | None:
    path, _ = QFileDialog.getOpenFileName(
        parent, "Open image", "", "Images (*.png *.jpg *.jpeg *.PNG *.JPG *.JPEG)"
    )
    return path or None


def preview_pixmap(image: LoadedImage, rect: QRect) -> QPixmap:
    return image.pixmap.scaled(
        max(1, rect.width()), max(1, rect.height()),
        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )


def image_description(image: LoadedImage) -> str:
    return f"{image.width} x {image.height} pixels · {len(image.bytes_) / 1024:.1f} KiB"
