from __future__ import annotations

from dataclasses import dataclass

from .inference import translate


@dataclass(frozen=True)
class ValidationResult:
    name: str
    passed: bool
    details: str


def run_validation() -> list[ValidationResult]:
    bible_text = "In the beginning was the Word"
    ministry_text = "God's economy is to dispense Himself into His chosen people."

    first = translate(bible_text, mode="bible", target_lang="es")
    second = translate(bible_text, mode="bible", target_lang="es")
    consistency = ValidationResult(
        name="consistency",
        passed=first == second,
        details=f"first='{first}' second='{second}'",
    )

    terminology_output = translate(ministry_text, mode="ministry", target_lang="es")
    terminology = ValidationResult(
        name="terminology",
        passed="economía de Dios" in terminology_output and "impartir" in terminology_output,
        details=terminology_output,
    )

    bible_style = translate(bible_text, mode="bible", target_lang="es")
    ministry_style = translate(bible_text, mode="ministry", target_lang="es")
    behavior = ValidationResult(
        name="mode_separation",
        passed=bible_style != ministry_style,
        details=f"bible='{bible_style}' ministry='{ministry_style}'",
    )

    return [consistency, terminology, behavior]
