from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import MODE_TO_ADAPTER, REPO_ROOT, get_adapter_path, get_tinker_credentials, load_config


TRAIN_DIR = REPO_ROOT / "train"


@dataclass(frozen=True)
class TrainingJob:
    job_id: str
    status: str
    adapter_name: str
    adapter_path: Path


class TinkerClient:
    def __init__(self) -> None:
        self.config = load_config()
        self.base_url, self.token = get_tinker_credentials()

    @property
    def is_mock(self) -> bool:
        return not self.base_url or not self.token

    def upload_dataset(self, dataset_path: str | Path) -> str:
        dataset_path = Path(dataset_path)
        if self.is_mock:
            return f"mock-dataset:{dataset_path.resolve()}"
        payload = {
            "filename": dataset_path.name,
            "content_base64": base64.b64encode(dataset_path.read_bytes()).decode("ascii"),
        }
        response = self._request_json(
            path=self.config.tinker.dataset_upload_path,
            payload=payload,
        )
        return str(response["dataset_id"])

    def trigger_fine_tuning_job(self, dataset_id: str, adapter_name: str) -> str:
        if self.is_mock:
            return f"mock-job:{adapter_name}"
        payload = {
            "dataset_id": dataset_id,
            "base_model": self.config.base_model_name,
            "adapter_name": adapter_name,
        }
        response = self._request_json(
            path=self.config.tinker.job_create_path,
            payload=payload,
        )
        return str(response["job_id"])

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        if self.is_mock:
            return {"job_id": job_id, "status": "completed"}
        path = self.config.tinker.job_status_path_template.format(job_id=job_id)
        return self._request_json(path=path, payload=None, method="GET")

    def download_lora_adapter(self, job_id: str, adapter_name: str) -> Path:
        adapter_path = get_adapter_path(_mode_from_adapter_name(adapter_name))
        adapter_path.mkdir(parents=True, exist_ok=True)

        if self.is_mock:
            manifest = {
                "adapter_name": adapter_name,
                "mode": _mode_from_adapter_name(adapter_name),
                "job_id": job_id,
                "backend": "mock",
                "status": "ready",
            }
            manifest_path = adapter_path / "adapter_manifest.json"
            with manifest_path.open("w", encoding="utf-8") as handle:
                json.dump(manifest, handle, ensure_ascii=False, indent=2)
            return adapter_path

        status_payload = self.get_job_status(job_id)
        download_url = status_payload[self.config.tinker.download_url_field]
        request.urlretrieve(download_url, adapter_path / "adapter_bundle.bin")
        manifest_path = adapter_path / "adapter_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(status_payload, handle, ensure_ascii=False, indent=2)
        return adapter_path

    def _request_json(self, path: str, payload: dict[str, Any] | None, method: str = "POST") -> dict[str, Any]:
        assert self.base_url is not None
        assert self.token is not None
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Tinker API request failed ({exc.code}): {body}") from exc


def train_adapter(dataset_path: str | Path, adapter_name: str) -> TrainingJob:
    client = TinkerClient()
    dataset_id = client.upload_dataset(dataset_path)
    job_id = client.trigger_fine_tuning_job(dataset_id=dataset_id, adapter_name=adapter_name)

    if not client.is_mock:
        while True:
            status_payload = client.get_job_status(job_id)
            status = str(status_payload.get("status", "")).lower()
            if status in {"completed", "succeeded", "ready"}:
                break
            if status in {"failed", "cancelled", "error"}:
                raise RuntimeError(f"Tinker fine-tuning job '{job_id}' failed with status '{status}'")
            time.sleep(10)

    adapter_path = client.download_lora_adapter(job_id=job_id, adapter_name=adapter_name)
    status = "completed" if client.is_mock else str(client.get_job_status(job_id)["status"])

    TRAIN_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = TRAIN_DIR / f"{adapter_name}_latest.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "dataset_path": str(Path(dataset_path).resolve()),
                "adapter_name": adapter_name,
                "job_id": job_id,
                "status": status,
                "adapter_path": str(adapter_path.resolve()),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    return TrainingJob(
        job_id=job_id,
        status=status,
        adapter_name=adapter_name,
        adapter_path=adapter_path,
    )


def _mode_from_adapter_name(adapter_name: str) -> str:
    for mode, configured_adapter in MODE_TO_ADAPTER.items():
        if configured_adapter == adapter_name:
            return mode
    raise ValueError(
        f"Unknown adapter '{adapter_name}'. Expected one of: {', '.join(sorted(MODE_TO_ADAPTER.values()))}"
    )
