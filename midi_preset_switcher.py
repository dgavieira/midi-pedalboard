from __future__ import annotations

from midi_preset_switcher_app import main as packaged_main

if __name__ == "__main__":
    packaged_main()
    raise SystemExit

import copy
import json
import os
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "MIDI Preset Switcher"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "midi_preset_switcher_config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "midi_output_port": "GuitarPresetControl",
    "plugins": [
        {
            "name": "Archetype Petrucci",
            "channel": 1,
            "bank_msb": None,
            "bank_lsb": None,
            "presets": [
                {"label": "Clean", "program": 0, "hotkey": "ctrl+alt+1"},
                {"label": "Rhythm", "program": 1, "hotkey": "ctrl+alt+2"},
                {"label": "Lead", "program": 2, "hotkey": "ctrl+alt+3"},
            ],
        },
        {
            "name": "ML Sound Lab ML5",
            "ui_mode": "program_grid",
            "channel": 2,
            "bank_msb": None,
            "bank_lsb": None,
            "amp_labels": [
                "ML5 Fat",
                "ML5 Clean",
                "ML5 Tweed",
                "ML5 Edge",
                "ML5 Crunch",
                "ML1",
                "ML2C+",
                "ML4",
                "ML5 Extreme"
            ],
            "program_grid": [
                ["Fat Clean", "Fat Ambience", "Clean Delay", "PC 03", "PC 04", "PC 05", "PC 06", "PC 07", "PC 08", "PC 09"],
                ["Pristine Clean", "Ambient Clean", "Dotted Delay", "PC 13", "PC 14", "PC 15", "PC 16", "PC 17", "PC 18", "PC 19"],
                ["Tweed Drive", "Boosted Tweed", "Edge Of Breakup", "PC 23", "PC 24", "PC 25", "PC 26", "PC 27", "PC 28", "PC 29"],
                ["Edgy Rock", "Pushed Edge", "Spanky Lead", "PC 33", "PC 34", "PC 35", "PC 36", "PC 37", "PC 38", "PC 39"],
                ["Rock Rhythm", "Beefy Gain", "Squishy Lead", "PC 43", "PC 44", "PC 45", "PC 46", "PC 47", "PC 48", "PC 49"],
                ["Latin Lead", "Single Notes", "Thicc Rhythm", "PC 53", "PC 54", "PC 55", "PC 56", "PC 57", "PC 58", "PC 59"],
                ["Tight Rhythm", "Liquid Lead", "T-Rex Rhythm", "Metropolis", "PC 64", "PC 65", "PC 66", "PC 67", "PC 68", "PC 69"],
                ["Dream Rhythm", "Sustain Lead", "Chocolate Cake", "PC 73", "PC 74", "PC 75", "PC 76", "PC 77", "PC 78", "PC 79"],
                ["Balanced Rhythm", "Smooth Lead", "Extreme Boost", "PC 83", "PC 84", "PC 85", "PC 86", "PC 87", "PC 88", "PC 89"]
            ],
            "presets": [
                {"label": "ML5 Fat / Fat Clean", "program": 0, "hotkey": "ctrl+alt+4"},
                {"label": "ML5 Clean / Pristine Clean", "program": 10, "hotkey": "ctrl+alt+5"}
            ],
            "toggle_buttons": [
                {"label": "Noise Gate", "cc": 2, "off_value": 0, "on_value": 127},
                {"label": "Compressor", "cc": 5, "off_value": 0, "on_value": 127},
                {"label": "Drive", "cc": 1, "off_value": 0, "on_value": 127},
                {"label": "Chorus", "cc": 6, "off_value": 0, "on_value": 127},
                {"label": "Delay", "cc": 3, "off_value": 0, "on_value": 127},
                {"label": "Reverb", "cc": 4, "off_value": 0, "on_value": 127}
            ]
        },
        {
            "name": "AmpliTube",
            "channel": 3,
            "bank_msb": None,
            "bank_lsb": None,
            "presets": [
                {"label": "AT Clean", "program": 20, "hotkey": "ctrl+alt+6"},
                {"label": "AT Solo", "program": 21, "hotkey": "ctrl+alt+7"},
            ],
        },
    ],
}

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


def deep_default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def merge_with_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = deep_default_config()
    merged["midi_output_port"] = config.get("midi_output_port", merged["midi_output_port"])
    incoming_plugins = config.get("plugins")
    if isinstance(incoming_plugins, list) and incoming_plugins:
        merged["plugins"] = incoming_plugins
    return merged


def parse_optional_int(value: str) -> int | None:
    cleaned = value.strip()
    if cleaned == "":
        return None
    return int(cleaned)


def validate_range(value: int, minimum: int, maximum: int, field_name: str) -> int:
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def plugin_ui_mode(plugin: dict[str, Any]) -> str:
    return str(plugin.get("ui_mode") or "preset_buttons").strip().lower()


def plugin_amp_labels(plugin: dict[str, Any]) -> list[str]:
    labels = plugin.get("amp_labels")
    if not isinstance(labels, list):
        return []
    return [str(label) for label in labels]


def plugin_preset_labels(plugin: dict[str, Any]) -> list[str]:
    labels = plugin.get("preset_labels")
    if not isinstance(labels, list):
        return []
    return [str(label) for label in labels]


def plugin_program_grid(plugin: dict[str, Any]) -> list[list[str]]:
    rows = plugin.get("program_grid")
    if not isinstance(rows, list):
        return []
    normalized_rows: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        normalized_rows.append([str(cell) for cell in row])
    return normalized_rows


def plugin_toggle_buttons(plugin: dict[str, Any]) -> list[dict[str, Any]]:
    buttons = plugin.get("toggle_buttons")
    if not isinstance(buttons, list):
        return []
    return [button for button in buttons if isinstance(button, dict)]


@dataclass
class PluginUiState:
    plugin: dict[str, Any]
    channel_var: tk.IntVar
    bank_msb_var: tk.StringVar
    bank_lsb_var: tk.StringVar
    hotkey_vars: list[tk.StringVar]
    amp_var: tk.StringVar | None = None
    preset_var: tk.StringVar | None = None


class MidiController:
    def __init__(self, log_callback: Callable[[str], None]) -> None:
        self.log_callback = log_callback
        self.output_port_name: str | None = None
        self.output_port: Any | None = None

    @property
    def available(self) -> bool:
        return mido is not None

    def list_output_ports(self) -> list[str]:
        if mido is None:
            return []
        try:
            return list(mido.get_output_names())
        except Exception as exc:
            self.log_exception("Failed to list MIDI output ports.", exc)
            return []

    def set_output_port(self, port_name: str | None) -> bool:
        self.close()
        if not port_name:
            self.output_port_name = None
            self.log_callback("No MIDI output port selected.")
            return False
        if mido is None:
            self.log_callback(f"MIDI unavailable: {MIDO_IMPORT_ERROR}")
            return False
        try:
            self.output_port = mido.open_output(port_name)
            self.output_port_name = port_name
            self.log_callback(f"Connected to MIDI output port: {port_name}")
            return True
        except Exception as exc:
            self.output_port_name = None
            self.log_exception(f"Failed to open MIDI output port '{port_name}'.", exc)
            return False

    def ensure_port_ready(self) -> bool:
        if self.output_port is not None:
            return True
        if self.output_port_name:
            return self.set_output_port(self.output_port_name)
        self.log_callback("No MIDI output port is currently open.")
        return False

    def send_program_change(
        self,
        *,
        channel_ui: int,
        program: int,
        bank_msb: int | None = None,
        bank_lsb: int | None = None,
        source: str = "Program Change",
    ) -> None:
        if not self.ensure_port_ready():
            raise RuntimeError("Select and open a MIDI output port first.")
        midi_channel = validate_range(channel_ui, 1, 16, "MIDI channel") - 1
        validate_range(program, 0, 127, "Program number")
        if bank_msb is not None:
            validate_range(bank_msb, 0, 127, "Bank MSB")
            self._send_message(
                mido.Message("control_change", channel=midi_channel, control=0, value=bank_msb),
                f"{source}: CC0 Bank Select MSB={bank_msb} on channel {channel_ui}",
            )
        if bank_lsb is not None:
            validate_range(bank_lsb, 0, 127, "Bank LSB")
            self._send_message(
                mido.Message("control_change", channel=midi_channel, control=32, value=bank_lsb),
                f"{source}: CC32 Bank Select LSB={bank_lsb} on channel {channel_ui}",
            )
        self._send_message(
            mido.Message("program_change", channel=midi_channel, program=program),
            f"{source}: Program Change {program} on channel {channel_ui}",
        )

    def send_control_change(self, *, channel_ui: int, control: int, value: int, source: str = "CC") -> None:
        if not self.ensure_port_ready():
            raise RuntimeError("Select and open a MIDI output port first.")
        midi_channel = validate_range(channel_ui, 1, 16, "MIDI channel") - 1
        validate_range(control, 0, 127, "CC number")
        validate_range(value, 0, 127, "CC value")
        self._send_message(
            mido.Message("control_change", channel=midi_channel, control=control, value=value),
            f"{source}: CC{control} value={value} on channel {channel_ui}",
        )

    def panic(self) -> None:
        if not self.ensure_port_ready():
            raise RuntimeError("Select and open a MIDI output port first.")
        for channel_ui in range(1, 17):
            midi_channel = channel_ui - 1
            for control, label in ((120, "All Sound Off"), (123, "All Notes Off")):
                self._send_message(
                    mido.Message("control_change", channel=midi_channel, control=control, value=0),
                    f"Panic: {label} on channel {channel_ui}",
                )

    def close(self) -> None:
        if self.output_port is None:
            return
        try:
            self.output_port.close()
        except Exception as exc:
            self.log_exception("Failed to close MIDI output port.", exc)
        finally:
            self.output_port = None

    def _send_message(self, message: Any, log_message: str) -> None:
        if self.output_port is None:
            raise RuntimeError("No MIDI output port is open.")
        self.output_port.send(message)
        self.log_callback(log_message)

    def log_exception(self, prefix: str, exc: Exception) -> None:
        self.log_callback(f"{prefix} {exc}")


class HotkeyManager:
    def __init__(self, root: tk.Tk, log_callback: Callable[[str], None]) -> None:
        self.root = root
        self.log_callback = log_callback
        self.registered_hotkeys: list[int] = []

    @property
    def available(self) -> bool:
        return keyboard is not None

    def clear(self) -> None:
        if keyboard is None:
            self.registered_hotkeys.clear()
            return
        for hotkey_id in self.registered_hotkeys:
            try:
                keyboard.remove_hotkey(hotkey_id)
            except Exception as exc:
                self.log_callback(f"Failed to remove hotkey: {exc}")
        self.registered_hotkeys.clear()

    def register_hotkeys(
        self,
        plugins: list[dict[str, Any]],
        callback: Callable[[dict[str, Any], dict[str, Any]], None],
    ) -> None:
        self.clear()
        if keyboard is None:
            if KEYBOARD_IMPORT_ERROR is not None:
                self.log_callback(f"Global hotkeys unavailable: {KEYBOARD_IMPORT_ERROR}")
            return
        for plugin in plugins:
            for preset in plugin.get("presets", []):
                hotkey = str(preset.get("hotkey") or "").strip()
                if not hotkey:
                    continue
                try:
                    hotkey_id = keyboard.add_hotkey(
                        hotkey,
                        lambda p=plugin, pr=preset: self.root.after(0, lambda: callback(p, pr)),
                        suppress=False,
                        trigger_on_release=False,
                    )
                    self.registered_hotkeys.append(hotkey_id)
                    self.log_callback(
                        f"Registered hotkey '{hotkey}' for {plugin.get('name', 'Plugin')} / {preset.get('label', 'Preset')}"
                    )
                except Exception as exc:
                    self.log_callback(
                        f"Failed to register hotkey '{hotkey}' for {plugin.get('name', 'Plugin')}: {exc}"
                    )


class PresetSwitcherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x840")
        self.root.minsize(980, 720)

        self.config_data = self.load_or_create_config()
        self.plugin_ui_states: list[PluginUiState] = []
        self.live_windows: dict[str, tk.Toplevel] = {}

        self.port_var = tk.StringVar(value=str(self.config_data.get("midi_output_port") or ""))
        self.manual_channel_var = tk.IntVar(value=1)
        self.manual_program_var = tk.IntVar(value=0)
        self.manual_bank_msb_var = tk.StringVar(value="")
        self.manual_bank_lsb_var = tk.StringVar(value="")
        self.manual_cc_number_var = tk.IntVar(value=0)
        self.manual_cc_value_var = tk.IntVar(value=0)

        self.midi_controller = MidiController(self.log)
        self.hotkey_manager = HotkeyManager(root, self.log)

        self._build_styles()
        self._build_ui()
        self.refresh_ports(select_saved=True)
        self.register_hotkeys()
        self.report_startup_status()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 11))
        style.configure("Preset.TButton", font=("Segoe UI Semibold", 10), padding=(10, 10))
        style.configure("Action.TButton", font=("Segoe UI Semibold", 10), padding=(10, 8))
        style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(10, 8))
        style.configure("LiveOpen.TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("Section.TLabelframe", padding=10)
        style.configure("Section.TLabelframe.Label", font=("Segoe UI Semibold", 11))

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.rowconfigure(1, weight=1)
        left_frame.columnconfigure(0, weight=1)

        self._build_port_section(left_frame).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._build_plugins_scroller(left_frame).grid(row=1, column=0, sticky="nsew")

        right_frame = ttk.Frame(container)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.rowconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)

        self._build_manual_section(right_frame).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._build_log_section(right_frame).grid(row=1, column=0, sticky="nsew")

    def _build_port_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="MIDI Output", style="Section.TLabelframe")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Output Port:", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, state="readonly", width=48)
        self.port_combo.grid(row=0, column=1, sticky="ew")
        self.port_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_port_selected())

        buttons = ttk.Frame(frame)
        buttons.grid(row=0, column=2, padx=(10, 0), sticky="e")
        ttk.Button(buttons, text="Refresh Ports", style="Action.TButton", command=self.refresh_ports).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(buttons, text="Test Port", style="Action.TButton", command=self.test_port).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(buttons, text="Panic", style="Danger.TButton", command=self.send_panic).pack(side=tk.LEFT)

        help_text = (
            "Select a loopMIDI output port here. Channels are shown as 1-16 in the UI and converted internally."
        )
        ttk.Label(frame, text=help_text, wraplength=760).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        return frame

    def _build_plugins_scroller(self, parent: ttk.Frame) -> ttk.Frame:
        wrapper = ttk.Frame(parent)
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        canvas = tk.Canvas(wrapper, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas)
        content.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event: tk.Event[Any]) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event: tk.Event[Any]) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        self.plugins_container = content
        self.rebuild_plugin_sections()
        return wrapper

    def rebuild_plugin_sections(self) -> None:
        for child in self.plugins_container.winfo_children():
            child.destroy()
        self.plugin_ui_states.clear()

        for row_index, plugin in enumerate(self.config_data.get("plugins", [])):
            state = self._build_plugin_section(self.plugins_container, plugin)
            state_frame = self.plugins_container.grid_slaves(row=row_index, column=0)
            if state_frame:
                state_frame[0].grid_configure(pady=(0, 10))
            self.plugin_ui_states.append(state)

    def _build_plugin_section(self, parent: ttk.Frame, plugin: dict[str, Any]) -> PluginUiState:
        row_index = len(self.plugin_ui_states)
        frame = ttk.LabelFrame(parent, text=str(plugin.get("name") or "Plugin"), style="Section.TLabelframe")
        frame.grid(row=row_index, column=0, sticky="ew")
        frame.columnconfigure(5, weight=1)

        channel_var = tk.IntVar(value=int(plugin.get("channel", 1)))
        bank_msb_var = tk.StringVar(value="" if plugin.get("bank_msb") is None else str(plugin.get("bank_msb")))
        bank_lsb_var = tk.StringVar(value="" if plugin.get("bank_lsb") is None else str(plugin.get("bank_lsb")))

        ttk.Label(frame, text="Channel").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(frame, from_=1, to=16, textvariable=channel_var, width=6).grid(row=1, column=0, sticky="w")

        ttk.Label(frame, text="Bank MSB").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frame, textvariable=bank_msb_var, width=8).grid(row=1, column=1, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Bank LSB").grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Entry(frame, textvariable=bank_lsb_var, width=8).grid(row=1, column=2, sticky="w", padx=(8, 0))

        hotkey_vars: list[tk.StringVar] = []
        amp_var: tk.StringVar | None = None
        preset_var: tk.StringVar | None = None
        next_row = 2

        if plugin_ui_mode(plugin) == "program_grid":
            ttk.Label(
                frame,
                text="Use the dedicated ML5 Live View for preset buttons and pedalboard toggles.",
                wraplength=760,
            ).grid(row=next_row, column=0, columnspan=6, sticky="w", pady=(8, 4))
            next_row += 1
        elif plugin_ui_mode(plugin) == "digit_matrix":
            amp_var, preset_var, next_row = self._build_digit_matrix_controls(
                frame,
                plugin,
                channel_var,
                bank_msb_var,
                bank_lsb_var,
                start_row=next_row,
            )

        presets = plugin.get("presets", [])
        if presets and plugin_ui_mode(plugin) != "program_grid":
            ttk.Label(frame, text="Presets / Hotkeys").grid(row=0, column=3, columnspan=3, sticky="w", padx=(16, 0))
            next_row = self._build_preset_buttons(
                frame,
                plugin,
                presets,
                channel_var,
                bank_msb_var,
                bank_lsb_var,
                hotkey_vars,
                start_row=next_row,
            )

        toggle_buttons = plugin_toggle_buttons(plugin)
        if toggle_buttons and plugin_ui_mode(plugin) != "program_grid":
            next_row = self._build_toggle_buttons(
                frame,
                plugin,
                toggle_buttons,
                channel_var,
                start_row=next_row,
            )

        footer = ttk.Frame(frame)
        footer.grid(row=next_row, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        if plugin_ui_mode(plugin) == "program_grid":
            ttk.Button(
                footer,
                text="Open ML5 Live View",
                style="LiveOpen.TButton",
                command=lambda p=plugin, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.open_plugin_live_view(
                    p, c, msb, lsb
                ),
            ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Save Config", style="Action.TButton", command=self.save_config).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(footer, text="Open Config", style="Action.TButton", command=self.open_config).pack(side=tk.LEFT)

        return PluginUiState(
            plugin=plugin,
            channel_var=channel_var,
            bank_msb_var=bank_msb_var,
            bank_lsb_var=bank_lsb_var,
            hotkey_vars=hotkey_vars,
            amp_var=amp_var,
            preset_var=preset_var,
        )

    def _build_preset_buttons(
        self,
        frame: ttk.LabelFrame,
        plugin: dict[str, Any],
        presets: list[dict[str, Any]],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        hotkey_vars: list[tk.StringVar],
        start_row: int,
    ) -> int:
        for preset_index, preset in enumerate(presets):
            preset_row = start_row + preset_index
            label = str(preset.get("label") or f"Preset {preset_index + 1}")
            program = int(preset.get("program", 0))
            hotkey_var = tk.StringVar(value=str(preset.get("hotkey") or ""))
            hotkey_vars.append(hotkey_var)

            ttk.Button(
                frame,
                text=f"{label}\nPC {program:02d}",
                style="Preset.TButton",
                command=lambda p=plugin, pr=preset, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_preset(
                    p, pr, c, msb, lsb
                ),
            ).grid(row=preset_row, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=(0, 8))

            ttk.Label(frame, text=f"Program {program:02d}").grid(row=preset_row, column=2, sticky="w", padx=(0, 8))
            ttk.Entry(frame, textvariable=hotkey_var, width=18).grid(row=preset_row, column=3, sticky="w")
            ttk.Label(frame, text="Global hotkey").grid(row=preset_row, column=4, sticky="w", padx=(6, 0))

        return start_row + len(presets)

    def _build_program_grid_controls(
        self,
        frame: ttk.LabelFrame,
        plugin: dict[str, Any],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        start_row: int,
    ) -> int:
        amp_labels = plugin_amp_labels(plugin)
        program_grid = plugin_program_grid(plugin)

        ttk.Label(frame, text="ML5 Program Grid").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(4, 2))
        ttk.Label(
            frame,
            text="Rows are amps and columns are program slots 0-9. Clicking a button sends the matching PC from 00 to 89.",
            wraplength=760,
        ).grid(row=start_row + 1, column=0, columnspan=6, sticky="w", pady=(0, 10))

        if len(amp_labels) != 9 or len(program_grid) != 9:
            ttk.Label(frame, text="Program grid mode requires 9 amp labels and 9 rows in program_grid.").grid(
                row=start_row + 2,
                column=0,
                columnspan=6,
                sticky="w",
                pady=(0, 8),
            )
            return start_row + 3

        grid_frame = ttk.Frame(frame)
        grid_frame.grid(row=start_row + 2, column=0, columnspan=6, sticky="ew")

        grid_frame.columnconfigure(0, weight=0)
        for col in range(1, 11):
            grid_frame.columnconfigure(col, weight=1)

        ttk.Label(grid_frame, text="Amp", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        for col in range(10):
            ttk.Label(grid_frame, text=f"{col}", anchor="center").grid(row=0, column=col + 1, sticky="ew", padx=2, pady=(0, 6))

        for row_index, amp_label in enumerate(amp_labels):
            ttk.Label(grid_frame, text=amp_label, style="Title.TLabel").grid(
                row=row_index + 1, column=0, sticky="w", padx=(0, 8), pady=2
            )
            row_labels = program_grid[row_index] if row_index < len(program_grid) else []
            for col_index in range(10):
                label = row_labels[col_index] if col_index < len(row_labels) else f"PC {row_index}{col_index}"
                program_number = (row_index * 10) + col_index
                ttk.Button(
                    grid_frame,
                    text=f"{label}\n{program_number:02d}",
                    style="Preset.TButton",
                    command=lambda p=plugin, pc=program_number, amp=amp_label, name=label, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_program_grid_button(
                        p, pc, amp, name, c, msb, lsb
                    ),
                ).grid(row=row_index + 1, column=col_index + 1, sticky="ew", padx=2, pady=2)

        return start_row + 3

    def _build_toggle_buttons(
        self,
        frame: ttk.LabelFrame,
        plugin: dict[str, Any],
        toggle_buttons: list[dict[str, Any]],
        channel_var: tk.IntVar,
        start_row: int,
    ) -> int:
        ttk.Label(frame, text="Pedalboard Toggles").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(8, 2))
        ttk.Label(
            frame,
            text="These send assignable CC footswitch values only. Set each CC number in the config file.",
            wraplength=760,
        ).grid(row=start_row + 1, column=0, columnspan=6, sticky="w", pady=(0, 8))

        toggles_frame = ttk.Frame(frame)
        toggles_frame.grid(row=start_row + 2, column=0, columnspan=6, sticky="ew")
        for index in range(3):
            toggles_frame.columnconfigure(index, weight=1)

        for index, toggle in enumerate(toggle_buttons):
            row = index // 3
            column = index % 3
            label_var = tk.StringVar()
            state_var = tk.BooleanVar(value=bool(toggle.get("initial_state", False)))
            self._update_toggle_label(label_var, toggle, state_var.get())

            button = tk.Button(
                toggles_frame,
                textvariable=label_var,
                font=("Segoe UI Semibold", 10),
                padx=10,
                pady=12,
                relief=tk.RAISED,
                bd=2,
            )
            button.configure(
                command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.toggle_plugin_switch(
                    plugin, t, state, label, channel_var, btn
                )
            )
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
            self._apply_toggle_button_style(button, state_var.get())

        return start_row + 3 + ((len(toggle_buttons) + 2) // 3)

    def open_plugin_live_view(
        self,
        plugin: dict[str, Any],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        plugin_name = str(plugin.get("name") or "Plugin")
        existing = self.live_windows.get(plugin_name)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title(f"{plugin_name} Live View")
        window.geometry("1460x920")
        window.minsize(1200, 780)
        window.configure(bg="#171717")
        self.live_windows[plugin_name] = window

        def on_close() -> None:
            self.live_windows.pop(plugin_name, None)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", on_close)

        header = tk.Frame(window, bg="#111111", padx=18, pady=14)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=plugin_name,
            font=("Segoe UI Semibold", 18),
            bg="#111111",
            fg="#f5f5f5",
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"Channel {channel_var.get()}  |  Port: {self.port_var.get().strip() or 'Not selected'}",
            font=("Segoe UI", 10),
            bg="#111111",
            fg="#d4d4d4",
        ).pack(side=tk.RIGHT)

        content = tk.Frame(window, bg="#171717", padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        left_panel = tk.Frame(content, bg="#171717")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right_panel = tk.Frame(content, bg="#171717")
        right_panel.grid(row=0, column=1, sticky="nsew")

        self._build_live_program_grid(left_panel, plugin, channel_var, bank_msb_var, bank_lsb_var)
        self._build_live_toggle_panel(right_panel, plugin, channel_var)

    def _build_live_program_grid(
        self,
        parent: tk.Frame,
        plugin: dict[str, Any],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        amp_labels = plugin_amp_labels(plugin)
        program_grid = plugin_program_grid(plugin)

        tk.Label(
            parent,
            text="Preset Grid",
            font=("Segoe UI Semibold", 14),
            bg="#171717",
            fg="#f5f5f5",
        ).pack(anchor="w", pady=(0, 10))

        canvas = tk.Canvas(parent, bg="#171717", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        grid_frame = tk.Frame(canvas, bg="#171717")
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        for col in range(11):
            grid_frame.grid_columnconfigure(col, weight=1 if col else 0)

        tk.Label(
            grid_frame,
            text="AMP",
            font=("Segoe UI Semibold", 10),
            bg="#171717",
            fg="#e5e5e5",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        for col in range(10):
            tk.Label(
                grid_frame,
                text=str(col),
                font=("Segoe UI Semibold", 10),
                bg="#171717",
                fg="#d4d4d4",
            ).grid(row=0, column=col + 1, sticky="ew", padx=3, pady=(0, 8))

        for row_index, amp_label in enumerate(amp_labels):
            tk.Label(
                grid_frame,
                text=amp_label,
                font=("Segoe UI Semibold", 10),
                bg="#171717",
                fg="#f5f5f5",
                width=14,
                anchor="w",
            ).grid(row=row_index + 1, column=0, sticky="w", padx=(0, 8), pady=4)

            row_labels = program_grid[row_index] if row_index < len(program_grid) else []
            for col_index in range(10):
                label = row_labels[col_index] if col_index < len(row_labels) else f"PC {row_index}{col_index}"
                program_number = (row_index * 10) + col_index
                tk.Button(
                    grid_frame,
                    text=f"{label}\n{program_number:02d}",
                    font=("Segoe UI Semibold", 10),
                    bg="#252525",
                    activebackground="#323232",
                    fg="#f5f5f5",
                    activeforeground="#ffffff",
                    relief=tk.RAISED,
                    bd=2,
                    padx=8,
                    pady=14,
                    wraplength=110,
                    command=lambda p=plugin, pc=program_number, amp=amp_label, name=label, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_program_grid_button(
                        p, pc, amp, name, c, msb, lsb
                    ),
                ).grid(row=row_index + 1, column=col_index + 1, sticky="ew", padx=3, pady=4)

        grid_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_live_toggle_panel(
        self,
        parent: tk.Frame,
        plugin: dict[str, Any],
        channel_var: tk.IntVar,
    ) -> None:
        tk.Label(
            parent,
            text="Pedalboard",
            font=("Segoe UI Semibold", 14),
            bg="#171717",
            fg="#f5f5f5",
        ).pack(anchor="w", pady=(0, 10))

        card = tk.Frame(parent, bg="#111111", padx=14, pady=14)
        card.pack(fill=tk.BOTH, expand=True)

        toggle_buttons = plugin_toggle_buttons(plugin)
        for column in range(2):
            card.grid_columnconfigure(column, weight=1)

        for index, toggle in enumerate(toggle_buttons):
            row = index // 2
            column = index % 2
            label_var = tk.StringVar()
            state_var = tk.BooleanVar(value=bool(toggle.get("initial_state", False)))
            self._update_toggle_label(label_var, toggle, state_var.get())

            button = tk.Button(
                card,
                textvariable=label_var,
                font=("Segoe UI Semibold", 14),
                padx=12,
                pady=26,
                relief=tk.RAISED,
                bd=3,
                wraplength=220,
            )
            button.configure(
                command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.toggle_plugin_switch(
                    plugin, t, state, label, channel_var, btn
                )
            )
            button.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            self._apply_toggle_button_style(button, state_var.get())

    def _build_digit_matrix_controls(
        self,
        frame: ttk.LabelFrame,
        plugin: dict[str, Any],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        start_row: int,
    ) -> tuple[tk.StringVar, tk.StringVar, int]:
        amp_labels = plugin_amp_labels(plugin)
        preset_labels = plugin_preset_labels(plugin)
        if not amp_labels or not preset_labels:
            ttk.Label(frame, text="Digit matrix mode requires amp_labels and preset_labels in the config.").grid(
                row=start_row,
                column=0,
                columnspan=6,
                sticky="w",
                pady=(4, 8),
            )
            return tk.StringVar(value=""), tk.StringVar(value=""), start_row + 1

        amp_var = tk.StringVar(value=amp_labels[0])
        preset_var = tk.StringVar(value=preset_labels[0])

        ttk.Label(frame, text="ML5 Program Change Map").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(4, 2))
        ttk.Label(
            frame,
            text="Left digit = amp, right digit = preset. Example: amp 1 + preset 0 sends PC 10.",
            wraplength=700,
        ).grid(row=start_row + 1, column=0, columnspan=6, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Amp").grid(row=start_row + 2, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=amp_var, values=amp_labels, state="readonly", width=24).grid(
            row=start_row + 3, column=0, columnspan=2, sticky="ew", padx=(0, 8)
        )

        ttk.Label(frame, text="Preset").grid(row=start_row + 2, column=2, sticky="w")
        ttk.Combobox(frame, textvariable=preset_var, values=preset_labels, state="readonly", width=24).grid(
            row=start_row + 3, column=2, columnspan=2, sticky="ew", padx=(0, 8)
        )

        preview_var = tk.StringVar()

        def update_preview(*_args: str) -> None:
            try:
                preview_var.set(self.ml5_program_preview(plugin, amp_var.get(), preset_var.get()))
            except Exception:
                preview_var.set("PC --")

        amp_var.trace_add("write", update_preview)
        preset_var.trace_add("write", update_preview)
        update_preview()

        ttk.Label(frame, textvariable=preview_var, style="Title.TLabel").grid(row=start_row + 3, column=4, sticky="w")
        ttk.Button(
            frame,
            text="Send ML5 Preset",
            style="Action.TButton",
            command=lambda: self.trigger_digit_matrix_preset(plugin, amp_var, preset_var, channel_var, bank_msb_var, bank_lsb_var),
        ).grid(row=start_row + 3, column=5, sticky="ew")

        return amp_var, preset_var, start_row + 5

    def _build_manual_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Manual MIDI", style="Section.TLabelframe")
        for index in range(4):
            frame.columnconfigure(index, weight=1)

        ttk.Label(frame, text="Channel").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(frame, from_=1, to=16, textvariable=self.manual_channel_var, width=8).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )

        ttk.Label(frame, text="Program").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_program_var, width=8).grid(
            row=1, column=1, sticky="ew", padx=(0, 8)
        )

        ttk.Label(frame, text="Bank MSB").grid(row=0, column=2, sticky="w")
        ttk.Entry(frame, textvariable=self.manual_bank_msb_var, width=10).grid(row=1, column=2, sticky="ew", padx=(0, 8))

        ttk.Label(frame, text="Bank LSB").grid(row=0, column=3, sticky="w")
        ttk.Entry(frame, textvariable=self.manual_bank_lsb_var, width=10).grid(row=1, column=3, sticky="ew")

        ttk.Button(
            frame,
            text="Send Program Change",
            style="Action.TButton",
            command=self.send_manual_program_change,
        ).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 12))

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 12))

        ttk.Label(frame, text="CC Number").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_cc_number_var, width=8).grid(
            row=5, column=0, sticky="ew", padx=(0, 8)
        )

        ttk.Label(frame, text="CC Value").grid(row=4, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_cc_value_var, width=8).grid(
            row=5, column=1, sticky="ew", padx=(0, 8)
        )

        ttk.Button(frame, text="Send CC", style="Action.TButton", command=self.send_manual_cc).grid(
            row=5, column=2, columnspan=2, sticky="ew"
        )

        return frame

    def _build_log_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Log", style="Section.TLabelframe")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(frame, height=18, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        return frame

    def load_or_create_config(self) -> dict[str, Any]:
        if not CONFIG_PATH.exists():
            config = deep_default_config()
            CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
            return config
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("Config root must be an object.")
            return merge_with_defaults(config)
        except Exception as exc:
            messagebox.showwarning(
                APP_TITLE,
                "The config file could not be read. The default config will be loaded instead.",
            )
            print(f"Failed to load config from {CONFIG_PATH.name}: {exc}")
            return deep_default_config()

    def save_config(self) -> None:
        try:
            self.sync_ui_to_config()
            CONFIG_PATH.write_text(json.dumps(self.config_data, indent=2), encoding="utf-8")
            self.register_hotkeys()
            self.log(f"Saved config to {CONFIG_PATH.name}")
            messagebox.showinfo(APP_TITLE, "Configuration saved.")
        except Exception as exc:
            self.handle_exception("Failed to save the configuration.", exc)

    def sync_ui_to_config(self) -> None:
        self.config_data["midi_output_port"] = self.port_var.get().strip()
        for state in self.plugin_ui_states:
            plugin = state.plugin
            plugin["channel"] = validate_range(state.channel_var.get(), 1, 16, "MIDI channel")
            plugin["bank_msb"] = self._parse_optional_bank(state.bank_msb_var.get(), "Bank MSB")
            plugin["bank_lsb"] = self._parse_optional_bank(state.bank_lsb_var.get(), "Bank LSB")
            for preset, hotkey_var in zip(plugin.get("presets", []), state.hotkey_vars):
                preset["hotkey"] = hotkey_var.get().strip()

    def register_hotkeys(self) -> None:
        self.sync_ui_to_config()
        self.hotkey_manager.register_hotkeys(self.config_data.get("plugins", []), self.trigger_preset)

    def report_startup_status(self) -> None:
        self.log(f"App started. Config path: {CONFIG_PATH}")
        if sys.version_info >= (3, 14):
            self.log(
                "Python 3.14 detected. python-rtmidi may require a compiler on this version; Python 3.10 to 3.12 is the safest choice on Windows."
            )
        if MIDO_IMPORT_ERROR is not None:
            self.log(f"MIDI support unavailable until dependencies are installed: {MIDO_IMPORT_ERROR}")
            messagebox.showwarning(
                APP_TITLE,
                "MIDI libraries are not available yet. Install the dependencies from requirements.txt to enable MIDI.",
            )
        if KEYBOARD_IMPORT_ERROR is not None:
            self.log(f"Keyboard hotkeys unavailable: {KEYBOARD_IMPORT_ERROR}")

    def refresh_ports(self, select_saved: bool = False) -> None:
        ports = self.midi_controller.list_output_ports()
        self.port_combo["values"] = ports
        desired_port = self.port_var.get().strip() if select_saved else self.midi_controller.output_port_name

        if desired_port and desired_port in ports:
            self.port_var.set(desired_port)
            self.on_port_selected(show_error=False)
        elif ports:
            if not self.port_var.get().strip():
                self.port_var.set(ports[0])
            self.on_port_selected(show_error=False)
        else:
            self.midi_controller.close()
            self.log("No MIDI output ports detected.")

    def on_port_selected(self, show_error: bool = True) -> None:
        port_name = self.port_var.get().strip()
        if not port_name:
            return
        if not self.midi_controller.set_output_port(port_name) and show_error:
            messagebox.showerror(APP_TITLE, f"Could not open MIDI output port '{port_name}'.")

    def test_port(self) -> None:
        try:
            self.sync_ui_to_config()
            self.midi_controller.send_program_change(
                channel_ui=1,
                program=0,
                source="Test Port",
            )
        except Exception as exc:
            self.handle_exception("Failed to send the test Program Change.", exc)

    def trigger_preset(
        self,
        plugin: dict[str, Any],
        preset: dict[str, Any],
        channel_var: tk.IntVar | None = None,
        bank_msb_var: tk.StringVar | None = None,
        bank_lsb_var: tk.StringVar | None = None,
    ) -> None:
        try:
            channel = channel_var.get() if channel_var is not None else int(plugin.get("channel", 1))
            bank_msb = (
                self._parse_optional_bank(bank_msb_var.get(), "Bank MSB")
                if bank_msb_var is not None
                else plugin.get("bank_msb")
            )
            bank_lsb = (
                self._parse_optional_bank(bank_lsb_var.get(), "Bank LSB")
                if bank_lsb_var is not None
                else plugin.get("bank_lsb")
            )
            program = int(preset.get("program", 0))
            self.midi_controller.send_program_change(
                channel_ui=channel,
                program=program,
                bank_msb=bank_msb,
                bank_lsb=bank_lsb,
                source=f"{plugin.get('name', 'Plugin')} / {preset.get('label', 'Preset')}",
            )
        except Exception as exc:
            self.handle_exception("Failed to send preset change.", exc)

    def ml5_program_number(self, plugin: dict[str, Any], amp_label: str, preset_label: str) -> int:
        amp_labels = plugin_amp_labels(plugin)
        preset_labels = plugin_preset_labels(plugin)
        if amp_label not in amp_labels:
            raise ValueError(f"Unknown amp selection: {amp_label}")
        if preset_label not in preset_labels:
            raise ValueError(f"Unknown preset selection: {preset_label}")
        amp_index = amp_labels.index(amp_label)
        preset_index = preset_labels.index(preset_label)
        return validate_range((amp_index * 10) + preset_index, 0, 89, "ML5 Program number")

    def ml5_program_preview(self, plugin: dict[str, Any], amp_label: str, preset_label: str) -> str:
        return f"PC {self.ml5_program_number(plugin, amp_label, preset_label):02d}"

    def trigger_digit_matrix_preset(
        self,
        plugin: dict[str, Any],
        amp_var: tk.StringVar,
        preset_var: tk.StringVar,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        try:
            amp_label = amp_var.get().strip()
            preset_label = preset_var.get().strip()
            program = self.ml5_program_number(plugin, amp_label, preset_label)
            self.midi_controller.send_program_change(
                channel_ui=channel_var.get(),
                program=program,
                bank_msb=self._parse_optional_bank(bank_msb_var.get(), "Bank MSB"),
                bank_lsb=self._parse_optional_bank(bank_lsb_var.get(), "Bank LSB"),
                source=f"{plugin.get('name', 'Plugin')} / {amp_label} / {preset_label}",
            )
        except Exception as exc:
            self.handle_exception("Failed to send matrix preset change.", exc)

    def trigger_program_grid_button(
        self,
        plugin: dict[str, Any],
        program: int,
        amp_label: str,
        preset_label: str,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        try:
            self.midi_controller.send_program_change(
                channel_ui=channel_var.get(),
                program=program,
                bank_msb=self._parse_optional_bank(bank_msb_var.get(), "Bank MSB"),
                bank_lsb=self._parse_optional_bank(bank_lsb_var.get(), "Bank LSB"),
                source=f"{plugin.get('name', 'Plugin')} / {amp_label} / {preset_label}",
            )
        except Exception as exc:
            self.handle_exception("Failed to send ML5 grid preset change.", exc)

    def toggle_plugin_switch(
        self,
        plugin: dict[str, Any],
        toggle: dict[str, Any],
        state_var: tk.BooleanVar,
        label_var: tk.StringVar,
        channel_var: tk.IntVar,
        button: tk.Button,
    ) -> None:
        try:
            cc_number_raw = toggle.get("cc")
            if cc_number_raw is None:
                raise ValueError(f"CC not assigned for {toggle.get('label', 'toggle')}. Set it in the config file.")

            cc_number = validate_range(int(cc_number_raw), 0, 127, "CC number")
            new_state = not state_var.get()
            cc_value = toggle.get("on_value", 127) if new_state else toggle.get("off_value", 0)
            cc_value = validate_range(int(cc_value), 0, 127, "CC value")

            self.midi_controller.send_control_change(
                channel_ui=channel_var.get(),
                control=cc_number,
                value=cc_value,
                source=f"{plugin.get('name', 'Plugin')} / {toggle.get('label', 'Toggle')} {'On' if new_state else 'Off'}",
            )

            state_var.set(new_state)
            self._update_toggle_label(label_var, toggle, new_state)
            self._apply_toggle_button_style(button, new_state)
        except Exception as exc:
            self.handle_exception("Failed to toggle pedalboard switch.", exc)

    def _update_toggle_label(self, label_var: tk.StringVar, toggle: dict[str, Any], is_on: bool) -> None:
        status = "ON" if is_on else "OFF"
        cc_text = f"CC {toggle['cc']}" if toggle.get("cc") is not None else "CC not set"
        label_var.set(f"{toggle.get('label', 'Toggle')}\n{status} | {cc_text}")

    def _apply_toggle_button_style(self, button: tk.Button, is_on: bool) -> None:
        if is_on:
            button.configure(bg="#98f5e1", activebackground="#7be0cb", fg="#0f172a")
        else:
            button.configure(bg="#30343b", activebackground="#454b54", fg="#f5f5f5")

    def send_manual_program_change(self) -> None:
        try:
            self.midi_controller.send_program_change(
                channel_ui=self.manual_channel_var.get(),
                program=self.manual_program_var.get(),
                bank_msb=self._parse_optional_bank(self.manual_bank_msb_var.get(), "Bank MSB"),
                bank_lsb=self._parse_optional_bank(self.manual_bank_lsb_var.get(), "Bank LSB"),
                source="Manual MIDI",
            )
        except Exception as exc:
            self.handle_exception("Failed to send manual Program Change.", exc)

    def send_manual_cc(self) -> None:
        try:
            self.midi_controller.send_control_change(
                channel_ui=self.manual_channel_var.get(),
                control=self.manual_cc_number_var.get(),
                value=self.manual_cc_value_var.get(),
                source="Manual MIDI",
            )
        except Exception as exc:
            self.handle_exception("Failed to send manual CC.", exc)

    def send_panic(self) -> None:
        try:
            self.midi_controller.panic()
        except Exception as exc:
            self.handle_exception("Failed to send panic messages.", exc)

    def open_config(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(CONFIG_PATH)  # type: ignore[attr-defined]
            else:
                messagebox.showinfo(APP_TITLE, f"Open the config file at:\n{CONFIG_PATH}")
        except Exception as exc:
            self.handle_exception("Failed to open the config file.", exc)

    def _parse_optional_bank(self, value: str, field_name: str) -> int | None:
        parsed = parse_optional_int(value)
        if parsed is None:
            return None
        return validate_range(parsed, 0, 127, field_name)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def handle_exception(self, user_message: str, exc: Exception) -> None:
        self.log(f"{user_message} {exc}")
        self.log(traceback.format_exc())
        messagebox.showerror(APP_TITLE, f"{user_message}\n\n{exc}")

    def on_close(self) -> None:
        self.hotkey_manager.clear()
        self.midi_controller.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    PresetSwitcherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
