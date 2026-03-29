from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import load_or_create_config, save_config
from ..defaults import APP_TITLE, CONFIG_PATH
from ..models import AppConfig, PluginConfig, PresetConfig, ToggleButtonConfig
from ..plugin_utils import (
    parse_optional_int,
    plugin_amp_labels,
    plugin_preset_labels,
    validate_range,
)
from ..runtime import KEYBOARD_IMPORT_ERROR, MIDO_IMPORT_ERROR
from ..services.hotkey_manager import HotkeyManager
from ..services.midi_controller import MidiController
from .live_view import LiveViewManager
from .main_window_sections import MainWindowSections
from .plugin_section_builder import PluginSectionBuilder
from .state import PluginUiState


class PresetSwitcherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x840")
        self.root.minsize(980, 720)

        self.config_data: AppConfig = self._load_config_with_fallback()
        self.plugin_ui_states: list[PluginUiState] = []

        self.port_var = tk.StringVar(value=self.config_data.midi_output_port)
        self.manual_channel_var = tk.IntVar(value=1)
        self.manual_program_var = tk.IntVar(value=0)
        self.manual_bank_msb_var = tk.StringVar(value="")
        self.manual_bank_lsb_var = tk.StringVar(value="")
        self.manual_cc_number_var = tk.IntVar(value=0)
        self.manual_cc_value_var = tk.IntVar(value=0)

        self.midi_controller = MidiController(self.log)
        self.hotkey_manager = HotkeyManager(root, self.log)
        self.live_view_manager = LiveViewManager(
            root=root,
            port_var=self.port_var,
            log_callback=self.log,
            trigger_program_callback=self.trigger_program_grid_button,
            toggle_callback=self.toggle_plugin_switch,
        )
        self.main_window_sections = MainWindowSections(self)
        self.plugin_section_builder = PluginSectionBuilder(self)

        self._build_styles()
        self._build_ui()
        self.refresh_ports(select_saved=True)
        self.register_hotkeys()
        self.report_startup_status()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _load_config_with_fallback(self) -> AppConfig:
        try:
            return load_or_create_config()
        except Exception as exc:
            messagebox.showwarning(
                APP_TITLE,
                "The config file could not be read. The default config will be loaded instead.",
            )
            print(f"Failed to load config from {CONFIG_PATH.name}: {exc}")
            from ..config import deep_default_config

            return AppConfig.from_dict(deep_default_config())

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
        self.main_window_sections.build_ui()

    def _build_port_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        return self.main_window_sections.build_port_section(parent)

    def _build_plugins_scroller(self, parent: ttk.Frame) -> ttk.Frame:
        return self.main_window_sections.build_plugins_scroller(parent)

    def rebuild_plugin_sections(self) -> None:
        self.plugin_section_builder.rebuild_plugin_sections()

    def _build_plugin_section(self, parent: ttk.Frame, plugin: PluginConfig) -> PluginUiState:
        return self.plugin_section_builder.build_plugin_section(parent, plugin)

    def _build_preset_buttons(
        self,
        frame: ttk.LabelFrame,
        plugin: PluginConfig,
        presets: list[PresetConfig],
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        hotkey_vars: list[tk.StringVar],
        start_row: int,
    ) -> int:
        return self.plugin_section_builder.build_preset_buttons(
            frame, plugin, presets, channel_var, bank_msb_var, bank_lsb_var, hotkey_vars, start_row
        )

    def _build_toggle_buttons(
        self,
        frame: ttk.LabelFrame,
        plugin: PluginConfig,
        toggle_buttons: list[ToggleButtonConfig | dict[str, Any]],
        channel_var: tk.IntVar,
        start_row: int,
    ) -> int:
        return self.plugin_section_builder.build_toggle_buttons(frame, plugin, toggle_buttons, channel_var, start_row)

    def _build_digit_matrix_controls(
        self,
        frame: ttk.LabelFrame,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        start_row: int,
    ) -> tuple[tk.StringVar, tk.StringVar, int]:
        return self.plugin_section_builder.build_digit_matrix_controls(
            frame, plugin, channel_var, bank_msb_var, bank_lsb_var, start_row
        )

    def _build_manual_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        return self.main_window_sections.build_manual_section(parent)

    def _build_log_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        return self.main_window_sections.build_log_section(parent)

    def save_config(self) -> None:
        try:
            self.sync_ui_to_config()
            save_config(self.config_data)
            self.register_hotkeys()
            self.log(f"Saved config to {CONFIG_PATH.name}")
            messagebox.showinfo(APP_TITLE, "Configuration saved.")
        except Exception as exc:
            self.handle_exception("Failed to save the configuration.", exc)

    def sync_ui_to_config(self) -> None:
        self.config_data.midi_output_port = self.port_var.get().strip()
        for state in self.plugin_ui_states:
            plugin = state.plugin
            plugin.channel = validate_range(state.channel_var.get(), 1, 16, "MIDI channel")
            plugin.bank_msb = self._parse_optional_bank(state.bank_msb_var.get(), "Bank MSB")
            plugin.bank_lsb = self._parse_optional_bank(state.bank_lsb_var.get(), "Bank LSB")
            for preset, hotkey_var in zip(plugin.presets, state.hotkey_vars):
                preset.hotkey = hotkey_var.get().strip()

    def register_hotkeys(self) -> None:
        self.sync_ui_to_config()
        self.hotkey_manager.register_hotkeys(self.config_data.plugins, self.trigger_preset)

    def report_startup_status(self) -> None:
        self.log(f"App started. Config path: {CONFIG_PATH}")
        if sys.version_info >= (3, 14):
            self.log("Python 3.14 detected. python-rtmidi may require a compiler on this version; Python 3.10 to 3.12 is the safest choice on Windows.")
        if MIDO_IMPORT_ERROR is not None:
            self.log(f"MIDI support unavailable until dependencies are installed: {MIDO_IMPORT_ERROR}")
            messagebox.showwarning(APP_TITLE, "MIDI libraries are not available yet. Install the dependencies from requirements.txt to enable MIDI.")
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
        if port_name and not self.midi_controller.set_output_port(port_name) and show_error:
            messagebox.showerror(APP_TITLE, f"Could not open MIDI output port '{port_name}'.")

    def test_port(self) -> None:
        try:
            self.sync_ui_to_config()
            self.midi_controller.send_program_change(channel_ui=1, program=0, source="Test Port")
        except Exception as exc:
            self.handle_exception("Failed to send the test Program Change.", exc)

    def trigger_preset(
        self,
        plugin: PluginConfig,
        preset: PresetConfig,
        channel_var: tk.IntVar | None = None,
        bank_msb_var: tk.StringVar | None = None,
        bank_lsb_var: tk.StringVar | None = None,
    ) -> None:
        try:
            channel = channel_var.get() if channel_var is not None else plugin.channel
            bank_msb = self._parse_optional_bank(bank_msb_var.get(), "Bank MSB") if bank_msb_var is not None else plugin.bank_msb
            bank_lsb = self._parse_optional_bank(bank_lsb_var.get(), "Bank LSB") if bank_lsb_var is not None else plugin.bank_lsb
            self.midi_controller.send_program_change(
                channel_ui=channel,
                program=preset.program,
                bank_msb=bank_msb,
                bank_lsb=bank_lsb,
                source=f"{plugin.name} / {preset.label}",
            )
            self._sync_program_toggle_state(plugin, preset.program)
        except Exception as exc:
            self.handle_exception("Failed to send preset change.", exc)

    def ml5_program_number(self, plugin: PluginConfig, amp_label: str, preset_label: str) -> int:
        amp_index = plugin_amp_labels(plugin).index(amp_label)
        preset_index = plugin_preset_labels(plugin).index(preset_label)
        return validate_range((amp_index * 10) + preset_index, 0, 89, "ML5 Program number")

    def ml5_program_preview(self, plugin: PluginConfig, amp_label: str, preset_label: str) -> str:
        return f"PC {self.ml5_program_number(plugin, amp_label, preset_label):02d}"

    def trigger_digit_matrix_preset(
        self,
        plugin: PluginConfig,
        amp_var: tk.StringVar,
        preset_var: tk.StringVar,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        try:
            program = self.ml5_program_number(plugin, amp_var.get().strip(), preset_var.get().strip())
            self.midi_controller.send_program_change(
                channel_ui=channel_var.get(),
                program=program,
                bank_msb=self._parse_optional_bank(bank_msb_var.get(), "Bank MSB"),
                bank_lsb=self._parse_optional_bank(bank_lsb_var.get(), "Bank LSB"),
                source=f"{plugin.name} / {amp_var.get().strip()} / {preset_var.get().strip()}",
            )
            self._sync_program_toggle_state(plugin, program)
        except Exception as exc:
            self.handle_exception("Failed to send matrix preset change.", exc)

    def trigger_program_grid_button(
        self,
        plugin: PluginConfig,
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
                source=f"{plugin.name} / {amp_label} / {preset_label}",
            )
            self._sync_program_toggle_state(plugin, program)
        except Exception as exc:
            self.handle_exception("Failed to send ML5 grid preset change.", exc)

    def open_plugin_live_view(
        self,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        self.live_view_manager.open_live_view(
            plugin,
            channel_var,
            bank_msb_var,
            bank_lsb_var,
            self._update_toggle_label,
            self._apply_toggle_button_style,
        )

    def toggle_plugin_switch(
        self,
        plugin: PluginConfig,
        toggle: ToggleButtonConfig | dict[str, Any],
        state_var: tk.StringVar,
        label_var: tk.StringVar,
        channel_var: tk.IntVar,
        button: tk.Button,
    ) -> None:
        try:
            cc_number_raw = toggle.cc if isinstance(toggle, ToggleButtonConfig) else toggle.get("cc")
            if cc_number_raw is None:
                label = toggle.label if isinstance(toggle, ToggleButtonConfig) else toggle.get("label", "toggle")
                raise ValueError(f"CC not assigned for {label}. Set it in the config file.")
            current_state = state_var.get().strip().lower()
            new_state = current_state != "on"
            on_value = toggle.on_value if isinstance(toggle, ToggleButtonConfig) else toggle.get("on_value", 127)
            off_value = toggle.off_value if isinstance(toggle, ToggleButtonConfig) else toggle.get("off_value", 0)
            label = toggle.label if isinstance(toggle, ToggleButtonConfig) else toggle.get("label", "Toggle")
            cc_value = on_value if new_state else off_value
            self.midi_controller.send_control_change(
                channel_ui=channel_var.get(),
                control=validate_range(int(cc_number_raw), 0, 127, "CC number"),
                value=validate_range(int(cc_value), 0, 127, "CC value"),
                source=f"{plugin.name} / {label} {'On' if new_state else 'Off'}",
            )
            state_var.set("on" if new_state else "off")
            self._update_toggle_label(label_var, toggle, state_var.get())
            self._apply_toggle_button_style(button, state_var.get())
        except Exception as exc:
            self.handle_exception("Failed to toggle pedalboard switch.", exc)

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
        return None if parsed is None else validate_range(parsed, 0, 127, field_name)

    def _update_toggle_label(self, label_var: tk.StringVar, toggle: ToggleButtonConfig | dict[str, Any], state: str) -> None:
        normalized_state = state.strip().lower()
        if normalized_state == "on":
            status = "ON"
        elif normalized_state == "off":
            status = "OFF"
        else:
            status = "UNKNOWN"
        cc_value = toggle.cc if isinstance(toggle, ToggleButtonConfig) else toggle.get("cc")
        label = toggle.label if isinstance(toggle, ToggleButtonConfig) else toggle.get("label", "Toggle")
        cc_text = f"CC {cc_value}" if cc_value is not None else "CC not set"
        label_var.set(f"{label}\n{status} | {cc_text}")

    def _apply_toggle_button_style(self, button: tk.Button, state: str) -> None:
        normalized_state = state.strip().lower()
        if normalized_state == "on":
            button.configure(bg="#98f5e1", activebackground="#7be0cb", fg="#0f172a")
        elif normalized_state == "off":
            button.configure(bg="#30343b", activebackground="#454b54", fg="#f5f5f5")
        else:
            button.configure(bg="#8a6d3b", activebackground="#9d8048", fg="#fff8e7")

    def _sync_program_toggle_state(self, plugin: PluginConfig, program: int) -> None:
        self.live_view_manager.sync_program_toggle_state(
            plugin,
            program,
            self._update_toggle_label,
            self._apply_toggle_button_style,
        )

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
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
