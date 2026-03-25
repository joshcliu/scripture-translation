from __future__ import annotations

from .data_pipeline import BIBLE_INSTRUCTION, MINISTRY_INSTRUCTION
from .model_loader import load_model
from .terminology import apply_terminology


def build_prompt(text: str, mode: str, target_lang: str) -> str:
    if mode == "bible":
        instruction = BIBLE_INSTRUCTION.format(target_lang=target_lang)
    elif mode == "ministry":
        instruction = MINISTRY_INSTRUCTION.format(target_lang=target_lang)
    else:
        raise ValueError(f"Unsupported mode '{mode}'")
    return f"{instruction}\n\nInput:\n{text}\n\nOutput:"


def translate(text: str, mode: str, target_lang: str) -> str:
    model = load_model(mode)
    prompt = build_prompt(text=text, mode=mode, target_lang=target_lang)
    generated = model.translate(prompt=prompt, source_text=text, target_lang=target_lang)
    return apply_terminology(generated, mode=mode)
