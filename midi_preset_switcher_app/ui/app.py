from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
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
    plugin_program_grid,
    plugin_toggle_buttons,
    plugin_ui_mode,
    validate_range,
)
from ..runtime import KEYBOARD_IMPORT_ERROR, MIDO_IMPORT_ERROR
from ..services.hotkey_manager import HotkeyManager
from ..services.midi_controller import MidiController


@dataclass
class PluginUiState:
    plugin: PluginConfig
    channel_var: tk.IntVar
    bank_msb_var: tk.StringVar
    bank_lsb_var: tk.StringVar
    hotkey_vars: list[tk.StringVar]
    amp_var: tk.StringVar | None = None
    preset_var: tk.StringVar | None = None


class PresetSwitcherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x840")
        self.root.minsize(980, 720)

        self.config_data: AppConfig = self._load_config_with_fallback()
        self.plugin_ui_states: list[PluginUiState] = []
        self.live_windows: dict[str, tk.Toplevel] = {}

        self.port_var = tk.StringVar(value=self.config_data.midi_output_port)
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
        ttk.Button(buttons, text="Refresh Ports", style="Action.TButton", command=self.refresh_ports).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Test Port", style="Action.TButton", command=self.test_port).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Panic", style="Danger.TButton", command=self.send_panic).pack(side=tk.LEFT)
        ttk.Label(
            frame,
            text="Select a loopMIDI output port here. Channels are shown as 1-16 in the UI and converted internally.",
            wraplength=760,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
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
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        self.plugins_container = content
        self.rebuild_plugin_sections()
        return wrapper

    def rebuild_plugin_sections(self) -> None:
        for child in self.plugins_container.winfo_children():
            child.destroy()
        self.plugin_ui_states.clear()
        for row_index, plugin in enumerate(self.config_data.plugins):
            state = self._build_plugin_section(self.plugins_container, plugin)
            frames = self.plugins_container.grid_slaves(row=row_index, column=0)
            if frames:
                frames[0].grid_configure(pady=(0, 10))
            self.plugin_ui_states.append(state)

    def _build_plugin_section(self, parent: ttk.Frame, plugin: PluginConfig) -> PluginUiState:
        frame = ttk.LabelFrame(parent, text=plugin.name, style="Section.TLabelframe")
        frame.grid(row=len(self.plugin_ui_states), column=0, sticky="ew")
        frame.columnconfigure(5, weight=1)
        channel_var = tk.IntVar(value=plugin.channel)
        bank_msb_var = tk.StringVar(value="" if plugin.bank_msb is None else str(plugin.bank_msb))
        bank_lsb_var = tk.StringVar(value="" if plugin.bank_lsb is None else str(plugin.bank_lsb))
        hotkey_vars: list[tk.StringVar] = []
        amp_var: tk.StringVar | None = None
        preset_var: tk.StringVar | None = None
        next_row = 2
        mode = plugin_ui_mode(plugin)

        ttk.Label(frame, text="Channel").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(frame, from_=1, to=16, textvariable=channel_var, width=6).grid(row=1, column=0, sticky="w")
        ttk.Label(frame, text="Bank MSB").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Entry(frame, textvariable=bank_msb_var, width=8).grid(row=1, column=1, sticky="w", padx=(8, 0))
        ttk.Label(frame, text="Bank LSB").grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Entry(frame, textvariable=bank_lsb_var, width=8).grid(row=1, column=2, sticky="w", padx=(8, 0))

        if mode == "program_grid":
            ttk.Label(
                frame,
                text="Use the dedicated ML5 Live View for preset buttons and pedalboard toggles.",
                wraplength=760,
            ).grid(row=next_row, column=0, columnspan=6, sticky="w", pady=(8, 4))
            next_row += 1
        elif mode == "digit_matrix":
            amp_var, preset_var, next_row = self._build_digit_matrix_controls(frame, plugin, channel_var, bank_msb_var, bank_lsb_var, next_row)

        presets = plugin.presets
        if presets and mode != "program_grid":
            ttk.Label(frame, text="Presets / Hotkeys").grid(row=0, column=3, columnspan=3, sticky="w", padx=(16, 0))
            next_row = self._build_preset_buttons(frame, plugin, presets, channel_var, bank_msb_var, bank_lsb_var, hotkey_vars, next_row)

        toggle_buttons = plugin_toggle_buttons(plugin)
        if toggle_buttons and mode != "program_grid":
            next_row = self._build_toggle_buttons(frame, plugin, toggle_buttons, channel_var, next_row)

        footer = ttk.Frame(frame)
        footer.grid(row=next_row, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        if mode == "program_grid":
            ttk.Button(
                footer,
                text="Open ML5 Live View",
                style="LiveOpen.TButton",
                command=lambda p=plugin, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.open_plugin_live_view(p, c, msb, lsb),
            ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Save Config", style="Action.TButton", command=self.save_config).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Open Config", style="Action.TButton", command=self.open_config).pack(side=tk.LEFT)
        return PluginUiState(plugin, channel_var, bank_msb_var, bank_lsb_var, hotkey_vars, amp_var, preset_var)

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
        for preset_index, preset in enumerate(presets):
            preset_row = start_row + preset_index
            label = preset.label or f"Preset {preset_index + 1}"
            program = preset.program
            hotkey_var = tk.StringVar(value=preset.hotkey)
            hotkey_vars.append(hotkey_var)
            ttk.Button(
                frame,
                text=f"{label}\nPC {program:02d}",
                style="Preset.TButton",
                command=lambda p=plugin, pr=preset, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_preset(p, pr, c, msb, lsb),
            ).grid(row=preset_row, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=(0, 8))
            ttk.Label(frame, text=f"Program {program:02d}").grid(row=preset_row, column=2, sticky="w", padx=(0, 8))
            ttk.Entry(frame, textvariable=hotkey_var, width=18).grid(row=preset_row, column=3, sticky="w")
            ttk.Label(frame, text="Global hotkey").grid(row=preset_row, column=4, sticky="w", padx=(6, 0))
        return start_row + len(presets)

    def _build_toggle_buttons(
        self,
        frame: ttk.LabelFrame,
        plugin: PluginConfig,
        toggle_buttons: list[ToggleButtonConfig | dict[str, Any]],
        channel_var: tk.IntVar,
        start_row: int,
    ) -> int:
        ttk.Label(frame, text="Pedalboard Toggles").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(8, 2))
        ttk.Label(frame, text="These send assignable CC footswitch values only. Set each CC number in the config file.", wraplength=760).grid(
            row=start_row + 1, column=0, columnspan=6, sticky="w", pady=(0, 8)
        )
        toggles_frame = ttk.Frame(frame)
        toggles_frame.grid(row=start_row + 2, column=0, columnspan=6, sticky="ew")
        for index in range(3):
            toggles_frame.columnconfigure(index, weight=1)
        for index, toggle in enumerate(toggle_buttons):
            row = index // 3
            column = index % 3
            label_var = tk.StringVar()
            state_var = tk.BooleanVar(value=bool(toggle.initial_state if isinstance(toggle, ToggleButtonConfig) else toggle.get("initial_state", False)))
            self._update_toggle_label(label_var, toggle, state_var.get())
            button = tk.Button(toggles_frame, textvariable=label_var, font=("Segoe UI Semibold", 10), padx=10, pady=12, relief=tk.RAISED, bd=2)
            button.configure(command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.toggle_plugin_switch(plugin, t, state, label, channel_var, btn))
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
            self._apply_toggle_button_style(button, state_var.get())
        return start_row + 3 + ((len(toggle_buttons) + 2) // 3)

    def _build_digit_matrix_controls(
        self,
        frame: ttk.LabelFrame,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        start_row: int,
    ) -> tuple[tk.StringVar, tk.StringVar, int]:
        amp_labels = plugin_amp_labels(plugin)
        preset_labels = plugin_preset_labels(plugin)
        if not amp_labels or not preset_labels:
            ttk.Label(frame, text="Digit matrix mode requires amp_labels and preset_labels in the config.").grid(
                row=start_row, column=0, columnspan=6, sticky="w", pady=(4, 8)
            )
            return tk.StringVar(value=""), tk.StringVar(value=""), start_row + 1
        amp_var = tk.StringVar(value=amp_labels[0])
        preset_var = tk.StringVar(value=preset_labels[0])
        ttk.Label(frame, text="ML5 Program Change Map").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(4, 2))
        ttk.Label(frame, text="Left digit = amp, right digit = preset. Example: amp 1 + preset 0 sends PC 10.", wraplength=700).grid(
            row=start_row + 1, column=0, columnspan=6, sticky="w", pady=(0, 10)
        )
        ttk.Label(frame, text="Amp").grid(row=start_row + 2, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=amp_var, values=amp_labels, state="readonly", width=24).grid(row=start_row + 3, column=0, columnspan=2, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Preset").grid(row=start_row + 2, column=2, sticky="w")
        ttk.Combobox(frame, textvariable=preset_var, values=preset_labels, state="readonly", width=24).grid(row=start_row + 3, column=2, columnspan=2, sticky="ew", padx=(0, 8))
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
        ttk.Spinbox(frame, from_=1, to=16, textvariable=self.manual_channel_var, width=8).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Program").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_program_var, width=8).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Bank MSB").grid(row=0, column=2, sticky="w")
        ttk.Entry(frame, textvariable=self.manual_bank_msb_var, width=10).grid(row=1, column=2, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Bank LSB").grid(row=0, column=3, sticky="w")
        ttk.Entry(frame, textvariable=self.manual_bank_lsb_var, width=10).grid(row=1, column=3, sticky="ew")
        ttk.Button(frame, text="Send Program Change", style="Action.TButton", command=self.send_manual_program_change).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 12))
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        ttk.Label(frame, text="CC Number").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_cc_number_var, width=8).grid(row=5, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="CC Value").grid(row=4, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.manual_cc_value_var, width=8).grid(row=5, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(frame, text="Send CC", style="Action.TButton", command=self.send_manual_cc).grid(row=5, column=2, columnspan=2, sticky="ew")
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
        except Exception as exc:
            self.handle_exception("Failed to send ML5 grid preset change.", exc)

    def open_plugin_live_view(
        self,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        plugin_name = plugin.name
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
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_live_window(plugin_name, window))

        header = tk.Frame(window, bg="#111111", padx=18, pady=14)
        header.pack(fill=tk.X)
        tk.Label(header, text=plugin_name, font=("Segoe UI Semibold", 18), bg="#111111", fg="#f5f5f5").pack(side=tk.LEFT)
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

    def _close_live_window(self, plugin_name: str, window: tk.Toplevel) -> None:
        self.live_windows.pop(plugin_name, None)
        window.destroy()

    def _build_live_program_grid(
        self,
        parent: tk.Frame,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
    ) -> None:
        amp_labels = plugin_amp_labels(plugin)
        program_grid = plugin_program_grid(plugin)
        tk.Label(parent, text="Preset Grid", font=("Segoe UI Semibold", 14), bg="#171717", fg="#f5f5f5").pack(anchor="w", pady=(0, 10))
        canvas = tk.Canvas(parent, bg="#171717", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        grid_frame = tk.Frame(canvas, bg="#171717")
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        for col in range(11):
            grid_frame.grid_columnconfigure(col, weight=1 if col else 0)
        tk.Label(grid_frame, text="AMP", font=("Segoe UI Semibold", 10), bg="#171717", fg="#e5e5e5").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        for col in range(10):
            tk.Label(grid_frame, text=str(col), font=("Segoe UI Semibold", 10), bg="#171717", fg="#d4d4d4").grid(row=0, column=col + 1, sticky="ew", padx=3, pady=(0, 8))
        for row_index, amp_label in enumerate(amp_labels):
            tk.Label(grid_frame, text=amp_label, font=("Segoe UI Semibold", 10), bg="#171717", fg="#f5f5f5", width=14, anchor="w").grid(
                row=row_index + 1, column=0, sticky="w", padx=(0, 8), pady=4
            )
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
                    command=lambda p=plugin, pc=program_number, amp=amp_label, name=label, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_program_grid_button(p, pc, amp, name, c, msb, lsb),
                ).grid(row=row_index + 1, column=col_index + 1, sticky="ew", padx=3, pady=4)
        grid_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_live_toggle_panel(self, parent: tk.Frame, plugin: PluginConfig, channel_var: tk.IntVar) -> None:
        tk.Label(parent, text="Pedalboard", font=("Segoe UI Semibold", 14), bg="#171717", fg="#f5f5f5").pack(anchor="w", pady=(0, 10))
        card = tk.Frame(parent, bg="#111111", padx=14, pady=14)
        card.pack(fill=tk.BOTH, expand=True)
        toggle_buttons = plugin_toggle_buttons(plugin)
        for column in range(2):
            card.grid_columnconfigure(column, weight=1)
        for index, toggle in enumerate(toggle_buttons):
            row = index // 2
            column = index % 2
            label_var = tk.StringVar()
            state_var = tk.BooleanVar(value=bool(toggle.initial_state))
            self._update_toggle_label(label_var, toggle, state_var.get())
            button = tk.Button(card, textvariable=label_var, font=("Segoe UI Semibold", 14), padx=12, pady=26, relief=tk.RAISED, bd=3, wraplength=220)
            button.configure(command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.toggle_plugin_switch(plugin, t, state, label, channel_var, btn))
            button.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            self._apply_toggle_button_style(button, state_var.get())

    def toggle_plugin_switch(
        self,
        plugin: PluginConfig,
        toggle: ToggleButtonConfig | dict[str, Any],
        state_var: tk.BooleanVar,
        label_var: tk.StringVar,
        channel_var: tk.IntVar,
        button: tk.Button,
    ) -> None:
        try:
            cc_number_raw = toggle.cc if isinstance(toggle, ToggleButtonConfig) else toggle.get("cc")
            if cc_number_raw is None:
                label = toggle.label if isinstance(toggle, ToggleButtonConfig) else toggle.get("label", "toggle")
                raise ValueError(f"CC not assigned for {label}. Set it in the config file.")
            new_state = not state_var.get()
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
            state_var.set(new_state)
            self._update_toggle_label(label_var, toggle, new_state)
            self._apply_toggle_button_style(button, new_state)
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

    def _update_toggle_label(self, label_var: tk.StringVar, toggle: ToggleButtonConfig | dict[str, Any], is_on: bool) -> None:
        status = "ON" if is_on else "OFF"
        cc_value = toggle.cc if isinstance(toggle, ToggleButtonConfig) else toggle.get("cc")
        label = toggle.label if isinstance(toggle, ToggleButtonConfig) else toggle.get("label", "Toggle")
        cc_text = f"CC {cc_value}" if cc_value is not None else "CC not set"
        label_var.set(f"{label}\n{status} | {cc_text}")

    def _apply_toggle_button_style(self, button: tk.Button, is_on: bool) -> None:
        if is_on:
            button.configure(bg="#98f5e1", activebackground="#7be0cb", fg="#0f172a")
        else:
            button.configure(bg="#30343b", activebackground="#454b54", fg="#f5f5f5")

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
