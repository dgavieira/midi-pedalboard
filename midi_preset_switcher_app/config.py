from __future__ import annotations

import copy
import json
from typing import Any

from .defaults import CONFIG_PATH, DEFAULT_CONFIG
from .models import AppConfig


def deep_default_config() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def merge_with_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = deep_default_config()
    merged["midi_output_port"] = config.get("midi_output_port", merged["midi_output_port"])
    incoming_plugins = config.get("plugins")
    if isinstance(incoming_plugins, list) and incoming_plugins:
        merged["plugins"] = incoming_plugins
    return merged


def load_or_create_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        config = deep_default_config()
        save_config(config)
        return AppConfig.from_dict(config)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Config root must be an object.")
    return AppConfig.from_dict(merge_with_defaults(config))


def save_config(config: AppConfig | dict[str, Any]) -> None:
    payload = config.to_dict() if isinstance(config, AppConfig) else config
    CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
