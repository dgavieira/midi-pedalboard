from __future__ import annotations

from typing import Any

from .models import PluginConfig, ToggleButtonConfig


def parse_optional_int(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned == "":
        return None
    return int(cleaned)


def validate_range(value: int, minimum: int, maximum: int, field_name: str) -> int:
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def plugin_ui_mode(plugin: PluginConfig | dict[str, Any]) -> str:
    if isinstance(plugin, PluginConfig):
        return plugin.ui_mode.strip().lower()
    return str(plugin.get("ui_mode") or "preset_buttons").strip().lower()


def plugin_amp_labels(plugin: PluginConfig | dict[str, Any]) -> list[str]:
    if isinstance(plugin, PluginConfig):
        return list(plugin.amp_labels)
    labels = plugin.get("amp_labels")
    if not isinstance(labels, list):
        return []
    return [str(label) for label in labels]


def plugin_preset_labels(plugin: PluginConfig | dict[str, Any]) -> list[str]:
    if isinstance(plugin, PluginConfig):
        return list(plugin.preset_labels)
    labels = plugin.get("preset_labels")
    if not isinstance(labels, list):
        return []
    return [str(label) for label in labels]


def plugin_program_grid(plugin: PluginConfig | dict[str, Any]) -> list[list[str]]:
    if isinstance(plugin, PluginConfig):
        return [list(row) for row in plugin.program_grid]
    rows = plugin.get("program_grid")
    if not isinstance(rows, list):
        return []
    normalized_rows: list[list[str]] = []
    for row in rows:
        if isinstance(row, list):
            normalized_rows.append([str(cell) for cell in row])
    return normalized_rows


def plugin_toggle_buttons(plugin: PluginConfig | dict[str, Any]) -> list[ToggleButtonConfig | dict[str, Any]]:
    if isinstance(plugin, PluginConfig):
        return list(plugin.toggle_buttons)
    buttons = plugin.get("toggle_buttons")
    if not isinstance(buttons, list):
        return []
    return [button for button in buttons if isinstance(button, dict)]
