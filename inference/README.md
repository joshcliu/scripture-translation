# Inference Notes

Inference selects the adapter by mode at runtime:

- `bible` -> `models/adapters/bible_adapter`
- `ministry` -> `models/adapters/ministry_adapter`

The package falls back to a deterministic mock backend when real LoRA weights are not present.
