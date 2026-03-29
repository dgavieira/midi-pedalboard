from __future__ import annotations

from typing import Any, Callable

from ..plugin_utils import validate_range
from ..runtime import MIDO_IMPORT_ERROR, mido


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
