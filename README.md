# MIDI Preset Switcher

MIDI Preset Switcher is a Windows 11 desktop application built with Python and Tkinter for controlling guitar plugin presets and pedalboard toggles over MIDI through a selected loopMIDI output port.

It is designed for local live use on Windows:
- select a loopMIDI output
- trigger Program Changes and CC toggles
- send CC-based stomp toggles
- use a dedicated ML5 live-performance window

Recommended Python version on Windows: `3.10` to `3.12`.
Python `3.14` can require native build tools for `python-rtmidi`.

## Features

- Tkinter desktop UI for local Windows use
- MIDI output selection with refresh and test actions
- Program Change support for `0-127`
- UI channels shown as `1-16` and converted internally to Mido `0-15`
- Optional Bank Select before Program Change using `CC 0` and `CC 32`
- Manual Program Change and CC sending for testing
- Panic button that sends `All Sound Off` and `All Notes Off` on all 16 channels
- Auto-scrolling log view for sent MIDI messages and errors
- Optional global hotkeys through the `keyboard` package
- JSON config file beside the launcher script
- ML Sound Lab ML5 live view with:
  - preset grid for `PC 00` to `PC 89`
  - pedalboard stomp toggles for CC footswitch behavior

## Current Support

The project currently provides full workflow support for:
- `ML Sound Lab ML5`

The config still contains placeholder sections for:
- `Archetype Petrucci`
- `AmpliTube`

Those sections should currently be treated as generic MIDI examples, not as fully implemented or officially supported plugin integrations.

## Supported Workflow

### ML Sound Lab ML5

- the main window keeps only a compact launcher section
- the dedicated `Open ML5 Live View` window contains:
  - 9 amp rows
  - 10 Program Change slots per row
  - named stomp buttons for:
    - Noise Gate
    - Compressor
    - Drive
    - Chorus
    - Delay
    - Reverb

Current ML5 stomp CC defaults:
- Drive: `CC 1`
- Noise Gate: `CC 2`
- Delay: `CC 3`
- Reverb: `CC 4`
- Compressor: `CC 5`
- Chorus: `CC 6`

## Project Structure

- `main.py`
  Primary launcher entry point.

- `midi_preset_switcher.py`
  Legacy compatibility launcher and old monolithic source retained during refactoring.

- `midi_preset_switcher_config.json`
  User-editable runtime configuration.

- `midi_preset_switcher_app/defaults.py`
  App constants and default configuration data.

- `midi_preset_switcher_app/models.py`
  Typed configuration models:
  - `AppConfig`
  - `PluginConfig`
  - `PresetConfig`
  - `ToggleButtonConfig`

- `midi_preset_switcher_app/config.py`
  Config loading, merging, and saving.

- `midi_preset_switcher_app/runtime.py`
  Optional dependency detection for `mido` and `keyboard`.

- `midi_preset_switcher_app/plugin_utils.py`
  Shared validation and plugin helpers.

- `midi_preset_switcher_app/services/midi_controller.py`
  MIDI port and message sending logic.

- `midi_preset_switcher_app/services/hotkey_manager.py`
  Global hotkey registration and cleanup.

- `midi_preset_switcher_app/ui/app.py`
  Tkinter application coordinator.

- `midi_preset_switcher_app/ui/live_view.py`
  Dedicated ML5 live-view window manager.

- `midi_preset_switcher_app/ui/main_window_sections.py`
  Main window layout sections such as MIDI output, manual MIDI, and log panels.

- `midi_preset_switcher_app/ui/plugin_section_builder.py`
  Plugin section builders for preset buttons, plugin controls, and ML5 launcher rows.

- `midi_preset_switcher_app/ui/state.py`
  Tkinter UI state dataclasses.

## Architecture

The project now follows a package-based OOP structure instead of keeping all behavior in one file.

Core roles:
- `AppConfig` owns the full user configuration.
- `PluginConfig` represents one plugin section.
- `PresetConfig` represents one Program Change preset.
- `ToggleButtonConfig` represents one CC stomp toggle.
- `MidiController` owns MIDI port and message behavior.
- `HotkeyManager` owns global hotkey registration and cleanup.
- `PresetSwitcherApp` coordinates the Tkinter UI and uses the service layer.
- `LiveViewManager` owns the ML5 live-performance window and stomp-state syncing.
- `MainWindowSections` builds the shared main-window panels.
- `PluginSectionBuilder` builds plugin-specific UI sections while leaving behavior in the app layer.

This separation improves:
- readability
- testability
- future extension
- safer config handling
- separation of UI, state, and MIDI concerns

## Setup

### Virtual Environment

The local environment currently used in this project is:

```powershell
.\.venv312
```

Activate it in PowerShell:

```powershell
.\.venv312\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run directly with:

```powershell
.\.venv312\Scripts\python.exe main.py
```

## loopMIDI Setup

1. Install and open loopMIDI.
2. Create a virtual MIDI port, for example `GuitarPresetControl`.
3. In your DAW or plugin host, make the plugin listen to that loopMIDI input.
4. In MIDI Preset Switcher, select the matching output port.

## Running the App

From PowerShell in the project folder:

```powershell
.\.venv312\Scripts\python.exe main.py
```

## Configuration

The app auto-creates `midi_preset_switcher_config.json` on first run if it does not exist.

Important config rules:
- channels use `1-16`
- Program Change values use `0-127`
- `bank_msb` and `bank_lsb` can be `null` or `0-127`
- hotkeys are optional
- ML5 stomp buttons use assignable CC numbers
- ML5 `program_grid` maps names to `PC 00-89`
- ML5 `program_toggle_states` can store the expected stomp on/off snapshot for each Program Change

Example excerpt:

```json
{
  "name": "ML Sound Lab ML5",
  "ui_mode": "program_grid",
  "channel": 2,
  "program_grid": [
    ["Fat Clean", "Fat Ambience", "Clean Delay", "PC 03", "PC 04", "PC 05", "PC 06", "PC 07", "PC 08", "PC 09"]
  ],
  "toggle_buttons": [
    {"label": "Drive", "cc": 1, "off_value": 0, "on_value": 127},
    {"label": "Noise Gate", "cc": 2, "off_value": 0, "on_value": 127}
  ],
  "program_toggle_states": {
    "0": {
      "Noise Gate": false,
      "Compressor": false,
      "Drive": true,
      "Chorus": false,
      "Delay": false,
      "Reverb": true
    }
  }
}
```

After editing the config, restart the app or use the built-in `Save Config` and `Open Config` actions.

### ML5 Stomp State Sync

ML5 preset loading over MIDI Program Change is one-way unless the plugin sends MIDI feedback back to the app. Because of that, the app cannot automatically read the real stompbox state from ML5 on its own.

To avoid showing stale pedal states:
- when you send an ML5 Program Change and there is no saved snapshot for that program, the live stomp buttons switch to `UNKNOWN`
- when `program_toggle_states` contains a snapshot for that program, the live stomp buttons restore those saved `ON` and `OFF` states

This keeps the UI honest while still letting you define known states where you want tighter live synchronization.

## User Interface Overview

### Main Window

- MIDI output selection
- refresh, test, and panic actions
- generic plugin/config sections
- manual MIDI section
- auto-scrolling log

### ML5 Main Section

The ML5 section in the main window is intentionally compact. It keeps:
- MIDI channel and bank controls
- configuration actions
- the `Open ML5 Live View` button

It does not keep the ML5 preset grid or stomp buttons anymore.

### ML5 Live View

The dedicated ML5 live window includes:
- the full preset grid
- pedalboard stomp toggles
- larger controls intended for fast live interaction

## Troubleshooting

### No MIDI Ports Listed

- make sure loopMIDI is running
- confirm the virtual port exists
- click `Refresh Ports`
- verify dependencies are installed

### Plugin Does Not React

- confirm the plugin listens to the same loopMIDI port
- confirm the MIDI channel matches
- check whether the plugin expects Program Change only or Bank Select plus Program Change
- use the Manual MIDI section to test exact values
- for plugins other than ML5, treat the current UI as generic MIDI sending rather than dedicated product support

### ML5 Stomp Buttons Do Not Work

- verify the CC assignments inside the ML5 plugin
- make sure the config uses the same CC numbers
- remember the stomp buttons send toggle-style CC values only
- default toggle values are usually `0` for off and `127` for on

### ML5 Stomp States Look Unknown After Preset Change

- this is expected when the selected Program Change has no `program_toggle_states` snapshot in the config
- add a snapshot for that PC number if you want the live view to restore the expected pedal states after loading the preset
- if ML5 does not transmit MIDI feedback, `UNKNOWN` is safer than showing stale `ON` or `OFF` states

### Hotkeys Do Not Work

- install the `keyboard` package
- avoid assigning the same hotkey to multiple presets
- some Windows environments may need elevated privileges for global keyboard hooks
- check the app log for registration errors

### `python-rtmidi` Installation Fails

- use Python `3.10`, `3.11`, or `3.12`
- if using Python `3.14`, install Visual C++ build tools or switch Python versions

## Development Notes

This project currently prioritizes:
- local Windows operation
- practical live-use controls
- readable architecture
- config-based customization
- ML5 as the primary supported plugin workflow

Potential next steps:
- scene or song mode
- multi-port routing
- tray mode
- packaging with PyInstaller
- unit tests around config parsing and MIDI message generation
