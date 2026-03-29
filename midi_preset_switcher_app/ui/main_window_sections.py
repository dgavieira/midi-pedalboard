from __future__ import annotations

from typing import Any

import tkinter as tk
from tkinter import ttk


class MainWindowSections:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build_ui(self) -> None:
        container = ttk.Frame(self.app.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(container)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.rowconfigure(1, weight=1)
        left_frame.columnconfigure(0, weight=1)

        self.build_port_section(left_frame).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.build_plugins_scroller(left_frame).grid(row=1, column=0, sticky="nsew")

        right_frame = ttk.Frame(container)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.rowconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)

        self.build_manual_section(right_frame).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.build_log_section(right_frame).grid(row=1, column=0, sticky="nsew")

    def build_port_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="MIDI Output", style="Section.TLabelframe")
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Output Port:", style="Title.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.app.port_combo = ttk.Combobox(frame, textvariable=self.app.port_var, state="readonly", width=48)
        self.app.port_combo.grid(row=0, column=1, sticky="ew")
        self.app.port_combo.bind("<<ComboboxSelected>>", lambda _event: self.app.on_port_selected())

        buttons = ttk.Frame(frame)
        buttons.grid(row=0, column=2, padx=(10, 0), sticky="e")
        ttk.Button(buttons, text="Refresh Ports", style="Action.TButton", command=self.app.refresh_ports).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Test Port", style="Action.TButton", command=self.app.test_port).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Panic", style="Danger.TButton", command=self.app.send_panic).pack(side=tk.LEFT)

        ttk.Label(
            frame,
            text="Select a loopMIDI output port here. Channels are shown as 1-16 in the UI and converted internally.",
            wraplength=760,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))
        return frame

    def build_plugins_scroller(self, parent: ttk.Frame) -> ttk.Frame:
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
        self.app.plugins_container = content
        self.app.rebuild_plugin_sections()
        return wrapper

    def build_manual_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Manual MIDI", style="Section.TLabelframe")
        for index in range(4):
            frame.columnconfigure(index, weight=1)
        ttk.Label(frame, text="Channel").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(frame, from_=1, to=16, textvariable=self.app.manual_channel_var, width=8).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Program").grid(row=0, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.app.manual_program_var, width=8).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Bank MSB").grid(row=0, column=2, sticky="w")
        ttk.Entry(frame, textvariable=self.app.manual_bank_msb_var, width=10).grid(row=1, column=2, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="Bank LSB").grid(row=0, column=3, sticky="w")
        ttk.Entry(frame, textvariable=self.app.manual_bank_lsb_var, width=10).grid(row=1, column=3, sticky="ew")
        ttk.Button(frame, text="Send Program Change", style="Action.TButton", command=self.app.send_manual_program_change).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 12))
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 12))
        ttk.Label(frame, text="CC Number").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.app.manual_cc_number_var, width=8).grid(row=5, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(frame, text="CC Value").grid(row=4, column=1, sticky="w")
        ttk.Spinbox(frame, from_=0, to=127, textvariable=self.app.manual_cc_value_var, width=8).grid(row=5, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(frame, text="Send CC", style="Action.TButton", command=self.app.send_manual_cc).grid(row=5, column=2, columnspan=2, sticky="ew")
        return frame

    def build_log_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Log", style="Section.TLabelframe")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.app.log_text = tk.Text(frame, height=18, wrap="word", state="disabled")
        self.app.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.app.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.app.log_text.configure(yscrollcommand=scrollbar.set)
        return frame
