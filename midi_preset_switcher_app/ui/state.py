from __future__ import annotations

from dataclasses import dataclass

import tkinter as tk

from ..models import PluginConfig, ToggleButtonConfig


@dataclass
class PluginUiState:
    plugin: PluginConfig
    channel_var: tk.IntVar
    bank_msb_var: tk.StringVar
    bank_lsb_var: tk.StringVar
    hotkey_vars: list[tk.StringVar]
    amp_var: tk.StringVar | None = None
    preset_var: tk.StringVar | None = None


@dataclass
class ToggleUiBinding:
    toggle: ToggleButtonConfig
    state_var: tk.StringVar
    label_var: tk.StringVar
    button: tk.Button
