from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_RE = re.compile(r"\s+([,.;:!?])")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+", flags=re.MULTILINE)

BIBLE_INSTRUCTION = (
    "Translate the following verse into {target_lang} in a strictly literal and "
    "faithful manner, preserving structure and terminology."
)
MINISTRY_INSTRUCTION = (
    "Translate the following text into {target_lang} in a natural and readable way, "
    "preserving the spiritual meaning and tone."
)


@dataclass(frozen=True)
class RawRecord:
    id: str
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class AlignedPair:
    id: str
    source: str
    target: str
    metadata: dict[str, object]


def normalize_text(text: str) -> str:
    cleaned = WHITESPACE_RE.sub(" ", text.replace("\u00a0", " ")).strip()
    return PUNCTUATION_RE.sub(r"\1", cleaned)


def load_raw_records(path: str | Path) -> list[RawRecord]:
    file_path = Path(path)
    suffix = "".join(file_path.suffixes[-2:]) if len(file_path.suffixes) > 1 else file_path.suffix
    if suffix in {".json", ".pdf.json"}:
        return _load_json_records(file_path)
    if suffix in {".jsonl", ".pdf.jsonl"}:
        return _load_jsonl_records(file_path)
    if suffix in {".txt", ".pdf.txt"}:
        return _load_text_records(file_path)
    raise ValueError(f"Unsupported file type for {file_path}")


def _load_json_records(path: Path) -> list[RawRecord]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        if "records" in payload:
            raw_items = payload["records"]
        elif "paragraphs" in payload:
            raw_items = payload["paragraphs"]
        elif "text" in payload:
            raw_items = [payload]
        else:
            raw_items = list(payload.values())
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raise ValueError(f"Unsupported JSON payload in {path}")
    return [_record_from_mapping(item, index) for index, item in enumerate(raw_items, start=1)]


def _load_jsonl_records(path: Path) -> list[RawRecord]:
    records: list[RawRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            records.append(_record_from_mapping(payload, index))
    return records


def _load_text_records(path: Path) -> list[RawRecord]:
    content = path.read_text(encoding="utf-8")
    blocks = [block.strip() for block in PARAGRAPH_SPLIT_RE.split(content) if block.strip()]
    if not blocks:
        return []

    records: list[RawRecord] = []
    for index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) == 1 and "\t" in lines[0]:
            record_id, text = lines[0].split("\t", 1)
            metadata = {}
        elif lines and all("\t" in line for line in lines):
            record_id, text = lines[0].split("\t", 1)
            metadata = {"raw_lines": lines[1:]}
        else:
            text = normalize_text(" ".join(lines))
            record_id = f"{path.stem}_{index:04d}"
            metadata = {"format": "paragraph"}
        records.append(RawRecord(id=record_id.strip(), text=normalize_text(text), metadata=metadata))
    return records


def _record_from_mapping(item: dict, index: int) -> RawRecord:
    if not isinstance(item, dict):
        raise ValueError("Each JSON record must be an object")
    text = item.get("text") or item.get("source") or item.get("content")
    if text is None:
        raise ValueError(f"Missing text field in record {item}")
    record_id = item.get("id") or _canonical_verse_id(item) or f"record_{index:04d}"
    metadata = {
        key: value
        for key, value in item.items()
        if key not in {"id", "text", "source", "target", "content"}
    }
    return RawRecord(id=str(record_id), text=normalize_text(str(text)), metadata=metadata)


def _canonical_verse_id(record: dict) -> str | None:
    if {"book", "chapter", "verse"}.issubset(record):
        book = str(record["book"]).strip().lower().replace(" ", "_")
        chapter = str(record["chapter"]).strip()
        verse = str(record["verse"]).strip()
        return f"{book}_{chapter}_{verse}"
    return None


def align_bible_records(source_records: list[RawRecord], target_records: list[RawRecord]) -> list[AlignedPair]:
    target_map = {record.id: record for record in target_records}
    pairs: list[AlignedPair] = []
    for source in source_records:
        target = target_map.get(source.id)
        if target is None:
            continue
        pairs.append(
            AlignedPair(
                id=source.id,
                source=source.text,
                target=target.text,
                metadata={"source": source.metadata, "target": target.metadata},
            )
        )
    return clean_pairs(pairs, mode="bible")


def align_ministry_records(source_records: list[RawRecord], target_records: list[RawRecord]) -> list[AlignedPair]:
    pair_count = min(len(source_records), len(target_records))
    pairs: list[AlignedPair] = []
    for index in range(pair_count):
        source = source_records[index]
        target = target_records[index]
        pair_id = source.id if source.id == target.id else f"paragraph_{index + 1:04d}"
        pairs.append(
            AlignedPair(
                id=pair_id,
                source=source.text,
                target=target.text,
                metadata={"source": source.metadata, "target": target.metadata},
            )
        )
    return clean_pairs(pairs, mode="ministry")


def clean_pairs(pairs: list[AlignedPair], mode: str) -> list[AlignedPair]:
    cleaned: list[AlignedPair] = []
    for pair in pairs:
        source = normalize_text(pair.source)
        target = normalize_text(pair.target)
        if not source or not target:
            continue
        if _looks_misaligned(source, target, mode):
            continue
        cleaned.append(AlignedPair(id=pair.id, source=source, target=target, metadata=pair.metadata))
    return cleaned


def _looks_misaligned(source: str, target: str, mode: str) -> bool:
    source_words = max(1, len(source.split()))
    target_words = max(1, len(target.split()))
    ratio = max(source_words, target_words) / min(source_words, target_words)
    if ratio > 4.0:
        return True
    if mode == "bible" and ":" in source and ":" not in target:
        return True
    return False


def build_instruction(mode: str, target_lang: str) -> str:
    if mode == "bible":
        return BIBLE_INSTRUCTION.format(target_lang=target_lang)
    if mode == "ministry":
        return MINISTRY_INSTRUCTION.format(target_lang=target_lang)
    raise ValueError(f"Unsupported mode '{mode}'")


def pairs_to_training_examples(
    pairs: list[AlignedPair], mode: str, target_lang: str
) -> list[dict[str, str]]:
    instruction = build_instruction(mode, target_lang)
    return [
        {
            "instruction": instruction,
            "input": pair.source,
            "output": pair.target,
        }
        for pair in pairs
    ]


def write_jsonl(examples: list[dict[str, str]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False) + "\n")
    return path


def prepare_dataset(
    mode: str,
    source_path: str | Path,
    target_path: str | Path,
    target_lang: str,
    output_path: str | Path,
) -> Path:
    source_records = load_raw_records(source_path)
    target_records = load_raw_records(target_path)
    if mode == "bible":
        pairs = align_bible_records(source_records, target_records)
    elif mode == "ministry":
        pairs = align_ministry_records(source_records, target_records)
    else:
        raise ValueError(f"Unsupported mode '{mode}'")
    examples = pairs_to_training_examples(pairs, mode=mode, target_lang=target_lang)
    return write_jsonl(examples, output_path)
