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
    base_url_env: str
    token_env: str
    dataset_upload_path: str
    job_create_path: str
    job_status_path_template: str
    download_url_field: str


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
            base_url_env=tinker_payload["base_url_env"],
            token_env=tinker_payload["token_env"],
            dataset_upload_path=tinker_payload["dataset_upload_path"],
            job_create_path=tinker_payload["job_create_path"],
            job_status_path_template=tinker_payload["job_status_path_template"],
            download_url_field=tinker_payload["download_url_field"],
        ),
    )


def get_adapter_path(mode: str) -> Path:
    config = load_config()
    try:
        return config.adapter_paths[mode]
    except KeyError as exc:
        supported = ", ".join(sorted(config.adapter_paths))
        raise ValueError(f"Unsupported mode '{mode}'. Expected one of: {supported}") from exc


def get_tinker_credentials() -> tuple[str | None, str | None]:
    config = load_config()
    base_url = os.environ.get(config.tinker.base_url_env)
    token = os.environ.get(config.tinker.token_env)
    return base_url, token
