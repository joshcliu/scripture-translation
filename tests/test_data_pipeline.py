from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project.data_pipeline import prepare_dataset


class DataPipelineTests(unittest.TestCase):
    def test_prepare_bible_dataset_writes_instruction_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bible.jsonl"
            prepare_dataset(
                mode="bible",
                source_path="data/raw/bible_john_en.json",
                target_path="data/raw/bible_john_es.json",
                target_lang="Spanish",
                output_path=output_path,
            )

            lines = output_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 3)
            first = json.loads(lines[0])
            self.assertIn("strictly literal and faithful", first["instruction"])
            self.assertEqual(first["input"], "In the beginning was the Word, and the Word was with God, and the Word was God.")

    def test_prepare_ministry_dataset_uses_ordered_paragraph_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "ministry.jsonl"
            prepare_dataset(
                mode="ministry",
                source_path="data/raw/ministry_en.txt",
                target_path="data/raw/ministry_es.txt",
                target_lang="Spanish",
                output_path=output_path,
            )

            lines = output_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertIn("natural and readable", first["instruction"])
            self.assertEqual(first["output"], "La economía de Dios consiste en impartirse a Sus escogidos.")


if __name__ == "__main__":
    unittest.main()
