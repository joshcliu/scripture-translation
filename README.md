# Recovery Version Translation MVP

This repository contains a working MVP for a domain-specific translation system for:

- the Recovery Version Bible
- Living Stream Ministry materials

The MVP keeps Bible and ministry translation fully separated through distinct adapter paths:

- `bible` -> `models/adapters/bible_adapter`
- `ministry` -> `models/adapters/ministry_adapter`

## What Is Included

- modular data loading for JSON, JSONL, text, and extracted PDF text exports
- Bible verse alignment by verse id
- ministry paragraph alignment by paragraph order
- cleaning and JSONL conversion for instruction-style fine-tuning
- `train_adapter(dataset_path, adapter_name)` with Tinker API hooks and a local mock mode
- `load_model(mode)` with dynamic adapter selection
- `translate(text, mode, target_lang)` with prompt construction and terminology enforcement
- a minimal CLI
- seed English/Spanish sample data for John 1 and one ministry text

## Quick Start

Prepare Bible training data:

```bash
python3 scripts/prepare_data.py \
  --mode bible \
  --source data/raw/bible_john_en.json \
  --target data/raw/bible_john_es.json \
  --lang Spanish \
  --output data/processed/bible_john_es.jsonl
```

Prepare ministry training data:

```bash
python3 scripts/prepare_data.py \
  --mode ministry \
  --source data/raw/ministry_en.txt \
  --target data/raw/ministry_es.txt \
  --lang Spanish \
  --output data/processed/ministry_es.jsonl
```

Run translation:

```bash
./translate --mode bible --lang es --text "In the beginning was the Word"
./translate --mode ministry --lang es --text "God's economy is to dispense Himself into His chosen people."
```

Trigger adapter training:

```bash
python3 scripts/train_adapter.py --dataset-path data/processed/bible_john_es.jsonl --adapter-name bible_adapter
python3 scripts/train_adapter.py --dataset-path data/processed/ministry_es.jsonl --adapter-name ministry_adapter
```

If `TINKER_API_BASE_URL` and `TINKER_API_TOKEN` are unset, training runs in local mock mode and writes seed adapter manifests. When real LoRA files are placed into each adapter directory, inference switches to `transformers` + `peft` automatically.

## Validation

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_mvp.py
```

## Notes

- Spanish is the only target language in this MVP.
- The local fallback translator is deterministic so repeated validation runs stay stable.
- Real model inference expects a Mistral-7B-Instruct-compatible adapter layout in each adapter folder.
