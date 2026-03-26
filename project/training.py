from __future__ import annotations

import json
import os
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request

from .config import MODE_TO_ADAPTER, REPO_ROOT, get_adapter_path, get_tinker_api_key, load_config


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
        self.api_key = get_tinker_api_key()
        self._tinker: Any | None = None
        self._service_client: Any | None = None

        if self.api_key:
            os.environ.setdefault(self.config.tinker.api_key_env, self.api_key)
            try:
                import tinker  # type: ignore
            except ImportError:
                self._tinker = None
            else:
                self._tinker = tinker
                self._service_client = tinker.ServiceClient()

    @property
    def is_mock(self) -> bool:
        return not self.api_key or self._tinker is None

    def upload_dataset(self, dataset_path: str | Path) -> list[dict[str, str]] | str:
        dataset_path = Path(dataset_path)
        if self.is_mock:
            return f"mock-dataset:{dataset_path.resolve()}"
        return _load_examples(dataset_path)

    def trigger_fine_tuning_job(self, dataset_id: list[dict[str, str]] | str, adapter_name: str) -> str:
        if self.is_mock:
            return f"mock-job:{adapter_name}"
        assert isinstance(dataset_id, list)
        assert self._service_client is not None
        assert self._tinker is not None

        self._ensure_supported_base_model()
        training_client = self._service_client.create_lora_training_client(
            base_model=self.config.base_model_name,
            rank=self.config.tinker.lora_rank,
            user_metadata={"adapter_name": adapter_name, "mode": _mode_from_adapter_name(adapter_name)},
        )
        tokenizer = training_client.get_tokenizer()
        data = [_example_to_datum(example, tokenizer, self._tinker) for example in dataset_id]
        adam_params = self._tinker.types.AdamParams(learning_rate=self.config.tinker.learning_rate)

        for _ in range(self.config.tinker.epochs):
            for batch in _batch(data, self.config.tinker.batch_size):
                fwdbwd_future = training_client.forward_backward(batch, "cross_entropy")
                optim_future = training_client.optim_step(adam_params)
                fwdbwd_future.result()
                optim_future.result()

        info = training_client.get_info()
        checkpoint_name = f"{adapter_name}_{self.config.tinker.checkpoint_name}"
        save_result = training_client.save_weights_for_sampler(checkpoint_name).result()

        job_id = _extract_job_id(info=info, fallback=save_result.path)
        self._write_training_metadata(job_id=job_id, checkpoint_path=save_result.path)
        return job_id

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        if self.is_mock:
            return {"job_id": job_id, "status": "completed"}
        metadata_path = TRAIN_DIR / f"{job_id}.json"
        if metadata_path.exists():
            with metadata_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["status"] = "completed"
            return payload
        return {"job_id": job_id, "status": "completed"}

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

        assert self._service_client is not None
        metadata = self.get_job_status(job_id)
        checkpoint_path = metadata["checkpoint_path"]
        rest_client = self._service_client.create_rest_client()
        checkpoint_response = rest_client.get_checkpoint_archive_url_from_tinker_path(checkpoint_path).result()

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "adapter.tar"
            request.urlretrieve(checkpoint_response.url, archive_path)
            with tarfile.open(archive_path, "r:*") as archive:
                archive.extractall(adapter_path)

        manifest_path = adapter_path / "adapter_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "adapter_name": adapter_name,
                    "mode": _mode_from_adapter_name(adapter_name),
                    "job_id": job_id,
                    "backend": "tinker",
                    "status": "ready",
                    "checkpoint_path": checkpoint_path,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        return adapter_path

    def _ensure_supported_base_model(self) -> None:
        assert self._service_client is not None
        capabilities = self._service_client.get_server_capabilities()
        supported = {item.model_name for item in capabilities.supported_models}
        if self.config.base_model_name not in supported:
            supported_preview = ", ".join(sorted(list(supported))[:10])
            raise RuntimeError(
                f"Configured base model '{self.config.base_model_name}' is not reported by Tinker. "
                f"Update configs/runtime.json to a supported model or verify your Tinker account has access. "
                f"Example supported models: {supported_preview}"
            )

    def _write_training_metadata(self, job_id: str, checkpoint_path: str) -> None:
        TRAIN_DIR.mkdir(parents=True, exist_ok=True)
        metadata_path = TRAIN_DIR / f"{job_id}.json"
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": job_id,
                    "checkpoint_path": checkpoint_path,
                    "base_model_name": self.config.base_model_name,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )


def train_adapter(dataset_path: str | Path, adapter_name: str) -> TrainingJob:
    client = TinkerClient()
    dataset_id = client.upload_dataset(dataset_path)
    job_id = client.trigger_fine_tuning_job(dataset_id=dataset_id, adapter_name=adapter_name)

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


def _load_examples(dataset_path: Path) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            examples.append(
                {
                    "instruction": str(payload["instruction"]),
                    "input": str(payload["input"]),
                    "output": str(payload["output"]),
                }
            )
    if not examples:
        raise ValueError(f"No training examples found in {dataset_path}")
    return examples


def _render_prompt(example: dict[str, str]) -> str:
    return (
        f"Instruction:\n{example['instruction']}\n\n"
        f"Input:\n{example['input']}\n\n"
        "Output:"
    )


def _example_to_datum(example: dict[str, str], tokenizer: Any, tinker_module: Any) -> Any:
    prompt = _render_prompt(example)
    prompt_tokens = tokenizer.encode(prompt, add_special_tokens=True)
    completion_tokens = tokenizer.encode(f" {example['output']}\n", add_special_tokens=False)

    tokens = prompt_tokens + completion_tokens
    weights = [0] * len(prompt_tokens) + [1] * len(completion_tokens)
    input_tokens = tokens[:-1]
    target_tokens = tokens[1:]
    shifted_weights = weights[1:]

    return tinker_module.types.Datum(
        model_input=tinker_module.types.ModelInput.from_ints(tokens=input_tokens),
        loss_fn_inputs={
            "target_tokens": target_tokens,
            "weights": shifted_weights,
        },
    )


def _batch(items: list[Any], batch_size: int) -> list[list[Any]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _extract_job_id(info: Any, fallback: str) -> str:
    model_data = getattr(info, "model_data", None)
    if model_data is not None:
        for attr in ("model_id", "training_run_id"):
            value = getattr(model_data, attr, None)
            if value:
                return str(value)
    return fallback.replace("tinker://", "").replace("/", "_")
