from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import get_adapter_path, load_config


WORD_BOUNDARY = re.compile(r"(\W+)")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class TranslationBackend:
    def generate(self, prompt: str, source_text: str, target_lang: str) -> str:
        raise NotImplementedError


@dataclass
class LoadedModel:
    mode: str
    backend_name: str
    base_model_name: str
    adapter_path: Path
    backend: TranslationBackend

    def translate(self, prompt: str, source_text: str, target_lang: str) -> str:
        return self.backend.generate(prompt=prompt, source_text=source_text, target_lang=target_lang)


class MockTranslationBackend(TranslationBackend):
    COMMON_PHRASES = {
        "In the beginning was the Word, and the Word was with God, and the Word was God.": "En el principio era la Palabra, y la Palabra estaba con Dios, y la Palabra era Dios.",
        "He was in the beginning with God.": "Este estaba en el principio con Dios.",
        "All things came into being through Him, and apart from Him not one thing came into being which has come into being.": "Todas las cosas llegaron a existir por medio de Él, y sin Él ni una sola cosa llegó a existir de lo que ha llegado a existir.",
        "In the beginning was the Word": "En el principio era la Palabra",
        "God's economy is to dispense Himself into His chosen people.": "La economía de Dios consiste en impartirse a Sus escogidos.",
        "The spirit gives life, and the church expresses Christ in a living way.": "El espíritu da vida, y la iglesia expresa a Cristo de una manera viviente.",
        "in the beginning": "en el principio",
        "the word": "la Palabra",
        "with God": "con Dios",
        "was God": "era Dios",
        "all things": "todas las cosas",
        "came into being": "llegaron a existir",
        "through him": "por medio de Él",
        "without him": "sin Él",
        "not even one thing": "ni una sola cosa",
        "that has come into being": "que ha llegado a existir",
        "life": "vida",
        "light": "luz",
        "men": "los hombres",
        "God's economy": "economía de Dios",
        "economy of God": "economía de Dios",
        "chosen people": "pueblo escogido",
        "dispense": "impartir",
        "dispensing": "impartición",
        "spirit": "espíritu",
        "soul": "alma",
        "church": "iglesia",
    }
    COMMON_WORDS = {
        "and": "y",
        "the": "el",
        "was": "era",
        "is": "es",
        "of": "de",
        "to": "a",
        "into": "en",
        "his": "su",
        "himself": "sí mismo",
        "god": "Dios",
        "word": "Palabra",
        "people": "pueblo",
        "beginning": "principio",
        "through": "por medio de",
        "without": "sin",
    }
    MINISTRY_STYLE_REWRITES = {
        "En el principio": "Al principio",
        "era la Palabra": "estaba la Palabra",
        "es impartir": "consiste en impartir",
        "su pueblo escogido": "sus escogidos",
        "Sí mismo": "sí mismo",
    }

    def __init__(self, mode: str):
        self.mode = mode

    def generate(self, prompt: str, source_text: str, target_lang: str) -> str:
        if target_lang.lower() != "es":
            raise ValueError("The MVP currently supports Spanish ('es') only.")
        translated = self._translate_phrases(source_text)
        translated = self._translate_words(translated)
        translated = self._cleanup(translated)
        if self.mode == "ministry":
            for source, target in self.MINISTRY_STYLE_REWRITES.items():
                translated = translated.replace(source, target)
        return translated

    def _translate_phrases(self, text: str) -> str:
        translated = text
        for source, target in sorted(self.COMMON_PHRASES.items(), key=lambda item: len(item[0]), reverse=True):
            translated = re.sub(re.escape(source), target, translated, flags=re.IGNORECASE)
        return translated

    def _translate_words(self, text: str) -> str:
        tokens = WORD_BOUNDARY.split(text)
        converted: list[str] = []
        for token in tokens:
            lowered = token.lower()
            replacement = self.COMMON_WORDS.get(lowered)
            if replacement is None:
                converted.append(token)
                continue
            if token.isupper():
                converted.append(replacement.upper())
            elif token[:1].isupper():
                converted.append(replacement[:1].upper() + replacement[1:])
            else:
                converted.append(replacement)
        return "".join(converted)

    def _cleanup(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\bla Palabra\b", "la Palabra", text)
        if self.mode == "bible":
            text = text.replace("Al principio", "En el principio")
            text = text.replace("estaba la Palabra", "era la Palabra")
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text


class HuggingFaceTranslationBackend(TranslationBackend):
    def __init__(self, mode: str, adapter_path: Path, base_model_name: str):
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers, peft, and torch are required for real model loading") from exc

        self.mode = mode
        self._torch = torch
        self._device = self._select_device(torch)
        self._tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=self._select_dtype(torch, self._device),
            low_cpu_mem_usage=True,
        )
        self._model = PeftModel.from_pretrained(base_model, str(adapter_path))
        self._model.to(self._device)
        self._model.eval()

    def generate(self, prompt: str, source_text: str, target_lang: str) -> str:
        tokenizer = self._tokenizer
        model = self._model
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to(self._device) for key, value in inputs.items()}
        generation_config = self._generation_config(source_text=source_text)
        with self._torch.no_grad():
            output_tokens = model.generate(
                **inputs,
                max_new_tokens=generation_config["max_new_tokens"],
                do_sample=False,
                temperature=0.0,
                repetition_penalty=generation_config["repetition_penalty"],
                no_repeat_ngram_size=generation_config["no_repeat_ngram_size"],
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        decoded = tokenizer.decode(output_tokens[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
        return self._cleanup_generated_text(decoded=decoded, source_text=source_text)

    @staticmethod
    def _select_device(torch):
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    @staticmethod
    def _select_dtype(torch, device):
        if device.type == "cuda":
            return torch.float16
        if device.type == "mps":
            return torch.float16
        return torch.float32

    def _generation_config(self, source_text: str) -> dict[str, float | int]:
        source_words = max(1, len(source_text.split()))
        if self.mode == "bible":
            return {
                "max_new_tokens": min(96, max(24, int(source_words * 2.2))),
                "repetition_penalty": 1.18,
                "no_repeat_ngram_size": 4,
            }
        return {
            "max_new_tokens": min(192, max(48, int(source_words * 2.8))),
            "repetition_penalty": 1.1,
            "no_repeat_ngram_size": 5,
        }

    def _cleanup_generated_text(self, decoded: str, source_text: str) -> str:
        text = re.sub(r"\s+", " ", decoded).strip()
        text = re.sub(r"^(Output:\s*)", "", text, flags=re.IGNORECASE)
        text = re.split(r"\n\s*\n", text, maxsplit=1)[0].strip()

        if self.mode == "bible":
            text = _dedupe_adjacent_sentences(text)
            source_sentence_count = _sentence_count(source_text)
            if source_sentence_count:
                text = _limit_sentences(text, source_sentence_count)
            elif len(source_text.split()) <= 12:
                text = _limit_sentences(text, 1)
        return text.strip()


def _has_real_adapter_weights(adapter_path: Path) -> bool:
    return (adapter_path / "adapter_config.json").exists() and (adapter_path / "adapter_model.safetensors").exists()


def _load_manifest(adapter_path: Path) -> dict[str, object]:
    manifest_path = adapter_path / "adapter_manifest.json"
    if not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=2)
def load_model(mode: str) -> LoadedModel:
    config = load_config()
    adapter_path = get_adapter_path(mode)
    adapter_path.mkdir(parents=True, exist_ok=True)

    if _has_real_adapter_weights(adapter_path):
        try:
            backend = HuggingFaceTranslationBackend(
                mode=mode,
                adapter_path=adapter_path,
                base_model_name=config.base_model_name,
            )
        except RuntimeError as exc:
            if "transformers, peft, and torch are required" not in str(exc):
                raise
            manifest = _load_manifest(adapter_path)
            backend = MockTranslationBackend(mode=manifest.get("mode", mode))
            backend_name = "mock"
        else:
            backend_name = "huggingface+peft"
    else:
        manifest = _load_manifest(adapter_path)
        backend = MockTranslationBackend(mode=manifest.get("mode", mode))
        backend_name = "mock"

    return LoadedModel(
        mode=mode,
        backend_name=backend_name,
        base_model_name=config.base_model_name,
        adapter_path=adapter_path,
        backend=backend,
    )


def _dedupe_adjacent_sentences(text: str) -> str:
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    if not sentences:
        return text

    deduped: list[str] = []
    previous_normalized = ""
    for sentence in sentences:
        normalized = sentence.casefold()
        if normalized == previous_normalized:
            continue
        deduped.append(sentence)
        previous_normalized = normalized
    return " ".join(deduped)


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text))


def _limit_sentences(text: str, count: int) -> str:
    if count <= 0:
        return text
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    if not sentences:
        return text
    return " ".join(sentences[:count])
