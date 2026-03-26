from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs"
MODE_TO_ADAPTER = {
    "bible": "bible_adapter",
    "ministry": "ministry_adapter",
}


@dataclass(frozen=True)
class TinkerSettings:
    api_key_env: str
    lora_rank: int
    learning_rate: float
    batch_size: int
    epochs: int
    checkpoint_name: str


@dataclass(frozen=True)
class AppConfig:
    base_model_name: str
    default_target_lang: str
    adapter_paths: dict[str, Path]
    tinker: TinkerSettings


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_local_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    payload = _read_json(CONFIGS_DIR / "runtime.json")
    adapter_paths = {
        mode: REPO_ROOT / adapter_path
        for mode, adapter_path in payload["adapter_paths"].items()
    }
    tinker_payload = payload["tinker"]
    return AppConfig(
        base_model_name=payload["base_model_name"],
        default_target_lang=payload["default_target_lang"],
        adapter_paths=adapter_paths,
        tinker=TinkerSettings(
            api_key_env=tinker_payload["api_key_env"],
            lora_rank=int(tinker_payload["lora_rank"]),
            learning_rate=float(tinker_payload["learning_rate"]),
            batch_size=int(tinker_payload["batch_size"]),
            epochs=int(tinker_payload["epochs"]),
            checkpoint_name=str(tinker_payload["checkpoint_name"]),
        ),
    )


def get_adapter_path(mode: str) -> Path:
    config = load_config()
    try:
        return config.adapter_paths[mode]
    except KeyError as exc:
        supported = ", ".join(sorted(config.adapter_paths))
        raise ValueError(f"Unsupported mode '{mode}'. Expected one of: {supported}") from exc


def get_tinker_api_key() -> str | None:
    load_local_env()
    config = load_config()
    return os.environ.get(config.tinker.api_key_env)
