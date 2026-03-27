# Recovery Version Translation MVP

This repository contains a working MVP for a domain-specific translation system for:

- the Recovery Version Bible
- Living Stream Ministry materials

The MVP keeps Bible and ministry translation fully separated through distinct adapter paths:

- `bible` -> `models/adapters/bible_adapter`
- `ministry` -> `models/adapters/ministry_adapter`

## What Is Included

- modular data loading for JSON, JSONL, text, and extracted PDF text exports
- Recovery Version Bible scraping into verse-level JSON from the official English and Spanish text-only sites
- Bible verse alignment by verse id
- ministry paragraph alignment by paragraph order
- cleaning and JSONL conversion for instruction-style fine-tuning
- `train_adapter(dataset_path, adapter_name)` with Tinker API hooks and a local mock mode
- `load_model(mode)` with dynamic adapter selection
- `translate(text, mode, target_lang)` with prompt construction and terminology enforcement
- a minimal CLI
- seed English/Spanish sample data for John 1 and one ministry text

## Quick Start

Scrape raw Recovery Version Bible text into verse JSON:

```bash
python3 scripts/scrape_recovery_version.py \
  --book John \
  --chapters 1-3 \
  --output data/raw/recovery_version_john_en.json
```

Scrape raw Spanish Recovery Version Bible text into verse JSON with matching verse ids:

```bash
python3 scripts/scrape_spanish_recovery_version.py \
  --book John \
  --chapters 1-3 \
  --output data/raw/recovery_version_john_es.json
```

Scrape the whole New Testament:

```bash
python3 scripts/scrape_new_testament.py --output-dir data/raw/nt
```

Scrape the whole Spanish New Testament:

```bash
python3 scripts/scrape_spanish_new_testament.py --output-dir data/raw/nt_es
```

Scrape the whole Old Testament:

```bash
python3 scripts/scrape_old_testament.py --output-dir data/raw/ot
```

Scrape the whole Spanish Old Testament:

```bash
python3 scripts/scrape_spanish_old_testament.py --output-dir data/raw/ot_es
```

These bulk scripts use slower default pacing:

- `1.5` seconds between chapter requests
- `3.0` seconds between books

Prepare Bible training data:

```bash
python3 scripts/prepare_data.py \
  --mode bible \
  --source data/raw/recovery_version_john_en.json \
  --target data/raw/recovery_version_john_es.json \
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
export TINKER_API_KEY=your_key_here
python3 scripts/train_adapter.py --dataset-path data/processed/bible_john_es.jsonl --adapter-name bible_adapter
python3 scripts/train_adapter.py --dataset-path data/processed/ministry_es.jsonl --adapter-name ministry_adapter
```

If `TINKER_API_KEY` is unset, or the `tinker` package is not installed, training runs in local mock mode and writes seed adapter manifests. With a real key, the trainer uses the official Tinker SDK, saves a sampler checkpoint, downloads the checkpoint archive, and extracts the LoRA files into the adapter directory.

You can keep `TINKER_API_KEY` in a local `.env` file at the repo root. The project will load it automatically for local runs.

Install the real training and inference dependencies with:

```bash
pip install -e '.[training,inference]'
```

## Validation

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_mvp.py
```

## Notes

- Spanish is the only target language in this MVP.
- The local fallback translator is deterministic so repeated validation runs stay stable.
- Real model inference expects a Mistral-7B-Instruct-compatible adapter layout in each adapter folder.
- Tinker setup uses `TINKER_API_KEY`, not a custom base URL.
- Use the Recovery Version scraper only where you have authorization to download and process the text.
