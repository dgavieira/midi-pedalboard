from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..models import PluginConfig
from ..runtime import KEYBOARD_IMPORT_ERROR, keyboard


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
        plugins: list[PluginConfig],
        callback: Callable[[PluginConfig, object], None],
    ) -> None:
        self.clear()
        if keyboard is None:
            if KEYBOARD_IMPORT_ERROR is not None:
                self.log_callback(f"Global hotkeys unavailable: {KEYBOARD_IMPORT_ERROR}")
            return
        for plugin in plugins:
            for preset in plugin.presets:
                hotkey = preset.hotkey.strip()
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
                        f"Registered hotkey '{hotkey}' for {plugin.name} / {preset.label}"
                    )
                except Exception as exc:
                    self.log_callback(f"Failed to register hotkey '{hotkey}' for {plugin.name}: {exc}")
