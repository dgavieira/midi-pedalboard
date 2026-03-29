from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PresetConfig:
    label: str
    program: int
    hotkey: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PresetConfig":
        return cls(
            label=str(data.get("label") or "Preset"),
            program=int(data.get("program", 0)),
            hotkey=str(data.get("hotkey") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToggleButtonConfig:
    label: str
    cc: int | None = None
    off_value: int = 0
    on_value: int = 127
    initial_state: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToggleButtonConfig":
        cc_value = data.get("cc")
        return cls(
            label=str(data.get("label") or "Toggle"),
            cc=None if cc_value is None else int(cc_value),
            off_value=int(data.get("off_value", 0)),
            on_value=int(data.get("on_value", 127)),
            initial_state=bool(data.get("initial_state", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PluginConfig:
    name: str
    channel: int
    bank_msb: int | None = None
    bank_lsb: int | None = None
    presets: list[PresetConfig] = field(default_factory=list)
    ui_mode: str = "preset_buttons"
    amp_labels: list[str] = field(default_factory=list)
    preset_labels: list[str] = field(default_factory=list)
    program_grid: list[list[str]] = field(default_factory=list)
    toggle_buttons: list[ToggleButtonConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginConfig":
        return cls(
            name=str(data.get("name") or "Plugin"),
            channel=int(data.get("channel", 1)),
            bank_msb=None if data.get("bank_msb") is None else int(data.get("bank_msb")),
            bank_lsb=None if data.get("bank_lsb") is None else int(data.get("bank_lsb")),
            presets=[PresetConfig.from_dict(item) for item in data.get("presets", []) if isinstance(item, dict)],
            ui_mode=str(data.get("ui_mode") or "preset_buttons"),
            amp_labels=[str(item) for item in data.get("amp_labels", []) if isinstance(item, str)],
            preset_labels=[str(item) for item in data.get("preset_labels", []) if isinstance(item, str)],
            program_grid=[
                [str(cell) for cell in row]
                for row in data.get("program_grid", [])
                if isinstance(row, list)
            ],
            toggle_buttons=[
                ToggleButtonConfig.from_dict(item)
                for item in data.get("toggle_buttons", [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "channel": self.channel,
            "bank_msb": self.bank_msb,
            "bank_lsb": self.bank_lsb,
            "ui_mode": self.ui_mode,
            "amp_labels": self.amp_labels,
            "preset_labels": self.preset_labels,
            "program_grid": self.program_grid,
            "presets": [preset.to_dict() for preset in self.presets],
            "toggle_buttons": [toggle.to_dict() for toggle in self.toggle_buttons],
        }


@dataclass
class AppConfig:
    midi_output_port: str
    plugins: list[PluginConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            midi_output_port=str(data.get("midi_output_port") or ""),
            plugins=[PluginConfig.from_dict(item) for item in data.get("plugins", []) if isinstance(item, dict)],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "midi_output_port": self.midi_output_port,
            "plugins": [plugin.to_dict() for plugin in self.plugins],
        }
