from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk

from ..models import PluginConfig, PresetConfig, ToggleButtonConfig
from ..plugin_utils import plugin_amp_labels, plugin_preset_labels, plugin_toggle_buttons, plugin_ui_mode
from .state import PluginUiState


class PluginSectionBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def rebuild_plugin_sections(self) -> None:
        for child in self.app.plugins_container.winfo_children():
            child.destroy()
        self.app.plugin_ui_states.clear()
        for row_index, plugin in enumerate(self.app.config_data.plugins):
            state = self.build_plugin_section(self.app.plugins_container, plugin)
            frames = self.app.plugins_container.grid_slaves(row=row_index, column=0)
            if frames:
                frames[0].grid_configure(pady=(0, 10))
            self.app.plugin_ui_states.append(state)

    def build_plugin_section(self, parent: ttk.Frame, plugin: PluginConfig) -> PluginUiState:
        frame = ttk.LabelFrame(parent, text=plugin.name, style="Section.TLabelframe")
        frame.grid(row=len(self.app.plugin_ui_states), column=0, sticky="ew")
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
            amp_var, preset_var, next_row = self.build_digit_matrix_controls(frame, plugin, channel_var, bank_msb_var, bank_lsb_var, next_row)

        if plugin.presets and mode != "program_grid":
            ttk.Label(frame, text="Presets / Hotkeys").grid(row=0, column=3, columnspan=3, sticky="w", padx=(16, 0))
            next_row = self.build_preset_buttons(frame, plugin, plugin.presets, channel_var, bank_msb_var, bank_lsb_var, hotkey_vars, next_row)

        toggle_buttons = plugin_toggle_buttons(plugin)
        if toggle_buttons and mode != "program_grid":
            next_row = self.build_toggle_buttons(frame, plugin, toggle_buttons, channel_var, next_row)

        footer = ttk.Frame(frame)
        footer.grid(row=next_row, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        if mode == "program_grid":
            ttk.Button(
                footer,
                text="Open ML5 Live View",
                style="LiveOpen.TButton",
                command=lambda p=plugin, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.app.open_plugin_live_view(p, c, msb, lsb),
            ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Save Config", style="Action.TButton", command=self.app.save_config).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(footer, text="Open Config", style="Action.TButton", command=self.app.open_config).pack(side=tk.LEFT)
        return PluginUiState(plugin, channel_var, bank_msb_var, bank_lsb_var, hotkey_vars, amp_var, preset_var)

    def build_preset_buttons(
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
            hotkey_var = tk.StringVar(value=preset.hotkey)
            hotkey_vars.append(hotkey_var)
            ttk.Button(
                frame,
                text=f"{label}\nPC {preset.program:02d}",
                style="Preset.TButton",
                command=lambda p=plugin, pr=preset, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.app.trigger_preset(p, pr, c, msb, lsb),
            ).grid(row=preset_row, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=(0, 8))
            ttk.Label(frame, text=f"Program {preset.program:02d}").grid(row=preset_row, column=2, sticky="w", padx=(0, 8))
            ttk.Entry(frame, textvariable=hotkey_var, width=18).grid(row=preset_row, column=3, sticky="w")
            ttk.Label(frame, text="Global hotkey").grid(row=preset_row, column=4, sticky="w", padx=(6, 0))
        return start_row + len(presets)

    def build_toggle_buttons(
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
            initial_state = "on" if bool(toggle.initial_state if isinstance(toggle, ToggleButtonConfig) else toggle.get("initial_state", False)) else "off"
            state_var = tk.StringVar(value=initial_state)
            self.app._update_toggle_label(label_var, toggle, state_var.get())
            button = tk.Button(toggles_frame, textvariable=label_var, font=("Segoe UI Semibold", 10), padx=10, pady=12, relief=tk.RAISED, bd=2)
            button.configure(command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.app.toggle_plugin_switch(plugin, t, state, label, channel_var, btn))
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
            self.app._apply_toggle_button_style(button, state_var.get())
        return start_row + 3 + ((len(toggle_buttons) + 2) // 3)

    def build_digit_matrix_controls(
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
                preview_var.set(self.app.ml5_program_preview(plugin, amp_var.get(), preset_var.get()))
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
            command=lambda: self.app.trigger_digit_matrix_preset(plugin, amp_var, preset_var, channel_var, bank_msb_var, bank_lsb_var),
        ).grid(row=start_row + 3, column=5, sticky="ew")
        return amp_var, preset_var, start_row + 5
