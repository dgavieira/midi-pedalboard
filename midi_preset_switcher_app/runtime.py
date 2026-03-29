from __future__ import annotations


MIDO_IMPORT_ERROR: Exception | None = None
KEYBOARD_IMPORT_ERROR: Exception | None = None
mido = None
keyboard = None

try:
    import mido  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover
    MIDO_IMPORT_ERROR = exc

try:
    import keyboard  # type: ignore[assignment]
except Exception as exc:  # pragma: no cover
    KEYBOARD_IMPORT_ERROR = exc
