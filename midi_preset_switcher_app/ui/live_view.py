from __future__ import annotations

from collections.abc import Callable

import tkinter as tk

from ..models import PluginConfig, ToggleButtonConfig
from ..plugin_utils import plugin_amp_labels, plugin_program_grid, plugin_toggle_buttons
from .state import ToggleUiBinding


class LiveViewManager:
    def __init__(
        self,
        root: tk.Tk,
        port_var: tk.StringVar,
        log_callback: Callable[[str], None],
        trigger_program_callback: Callable[[PluginConfig, int, str, str, tk.IntVar, tk.StringVar, tk.StringVar], None],
        toggle_callback: Callable[[PluginConfig, ToggleButtonConfig, tk.StringVar, tk.StringVar, tk.IntVar, tk.Button], None],
    ) -> None:
        self.root = root
        self.port_var = port_var
        self.log_callback = log_callback
        self.trigger_program_callback = trigger_program_callback
        self.toggle_callback = toggle_callback
        self.live_windows: dict[str, tk.Toplevel] = {}
        self.live_toggle_bindings: dict[str, list[ToggleUiBinding]] = {}

    def open_live_view(
        self,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        bank_msb_var: tk.StringVar,
        bank_lsb_var: tk.StringVar,
        update_toggle_label: Callable[[tk.StringVar, ToggleButtonConfig, str], None],
        apply_toggle_button_style: Callable[[tk.Button, str], None],
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
        self.live_toggle_bindings.pop(plugin_name, None)
        window.protocol("WM_DELETE_WINDOW", lambda: self.close_live_window(plugin_name, window))

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

        self._build_program_grid(left_panel, plugin, channel_var, bank_msb_var, bank_lsb_var)
        self._build_toggle_panel(
            right_panel,
            plugin,
            channel_var,
            update_toggle_label,
            apply_toggle_button_style,
        )

    def close_live_window(self, plugin_name: str, window: tk.Toplevel) -> None:
        self.live_windows.pop(plugin_name, None)
        self.live_toggle_bindings.pop(plugin_name, None)
        window.destroy()

    def sync_program_toggle_state(
        self,
        plugin: PluginConfig,
        program: int,
        update_toggle_label: Callable[[tk.StringVar, ToggleButtonConfig, str], None],
        apply_toggle_button_style: Callable[[tk.Button, str], None],
    ) -> None:
        bindings = self.live_toggle_bindings.get(plugin.name)
        if not bindings:
            return

        state_map = plugin.program_toggle_states.get(str(program))
        if state_map is None:
            for binding in bindings:
                binding.state_var.set("unknown")
                update_toggle_label(binding.label_var, binding.toggle, "unknown")
                apply_toggle_button_style(binding.button, "unknown")
            self.log_callback(
                f"{plugin.name}: stomp states set to UNKNOWN after PC {program:02d}. "
                "Add program_toggle_states in the config to restore exact pedal states."
            )
            return

        known_count = 0
        for binding in bindings:
            toggle_state = state_map.get(binding.toggle.label)
            if toggle_state is None:
                binding.state_var.set("unknown")
                update_toggle_label(binding.label_var, binding.toggle, "unknown")
                apply_toggle_button_style(binding.button, "unknown")
                continue
            known_count += 1
            binding.state_var.set("on" if toggle_state else "off")
            update_toggle_label(binding.label_var, binding.toggle, binding.state_var.get())
            apply_toggle_button_style(binding.button, binding.state_var.get())

        self.log_callback(
            f"{plugin.name}: restored stomp snapshot for PC {program:02d} "
            f"({known_count}/{len(bindings)} toggles defined)."
        )

    def _build_program_grid(
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
                    command=lambda p=plugin, pc=program_number, amp=amp_label, name=label, c=channel_var, msb=bank_msb_var, lsb=bank_lsb_var: self.trigger_program_callback(
                        p, pc, amp, name, c, msb, lsb
                    ),
                ).grid(row=row_index + 1, column=col_index + 1, sticky="ew", padx=3, pady=4)

        grid_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_toggle_panel(
        self,
        parent: tk.Frame,
        plugin: PluginConfig,
        channel_var: tk.IntVar,
        update_toggle_label: Callable[[tk.StringVar, ToggleButtonConfig, str], None],
        apply_toggle_button_style: Callable[[tk.Button, str], None],
    ) -> None:
        tk.Label(parent, text="Pedalboard", font=("Segoe UI Semibold", 14), bg="#171717", fg="#f5f5f5").pack(anchor="w", pady=(0, 10))
        card = tk.Frame(parent, bg="#111111", padx=14, pady=14)
        card.pack(fill=tk.BOTH, expand=True)
        toggle_buttons = plugin_toggle_buttons(plugin)
        bindings: list[ToggleUiBinding] = []

        for column in range(2):
            card.grid_columnconfigure(column, weight=1)

        for index, toggle in enumerate(toggle_buttons):
            row = index // 2
            column = index % 2
            label_var = tk.StringVar()
            state_var = tk.StringVar(value="on" if toggle.initial_state else "off")
            update_toggle_label(label_var, toggle, state_var.get())
            button = tk.Button(card, textvariable=label_var, font=("Segoe UI Semibold", 14), padx=12, pady=26, relief=tk.RAISED, bd=3, wraplength=220)
            button.configure(
                command=lambda t=toggle, state=state_var, label=label_var, btn=button: self.toggle_callback(
                    plugin, t, state, label, channel_var, btn
                )
            )
            button.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            apply_toggle_button_style(button, state_var.get())
            bindings.append(ToggleUiBinding(toggle=toggle, state_var=state_var, label_var=label_var, button=button))

        self.live_toggle_bindings[plugin.name] = bindings
