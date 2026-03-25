from __future__ import annotations

import unittest

from project.inference import translate
from project.validation import run_validation


class InferenceTests(unittest.TestCase):
    def test_translation_is_deterministic(self) -> None:
        text = "In the beginning was the Word"
        first = translate(text, mode="bible", target_lang="es")
        second = translate(text, mode="bible", target_lang="es")
        self.assertEqual(first, second)

    def test_terminology_is_enforced(self) -> None:
        text = "God's economy is to dispense Himself into His chosen people."
        output = translate(text, mode="ministry", target_lang="es")
        self.assertIn("economía de Dios", output)
        self.assertIn("impartir", output)

    def test_modes_produce_distinct_behavior(self) -> None:
        text = "In the beginning was the Word"
        bible_output = translate(text, mode="bible", target_lang="es")
        ministry_output = translate(text, mode="ministry", target_lang="es")
        self.assertNotEqual(bible_output, ministry_output)

    def test_validation_suite_passes(self) -> None:
        results = run_validation()
        self.assertTrue(all(result.passed for result in results), results)


if __name__ == "__main__":
    unittest.main()
