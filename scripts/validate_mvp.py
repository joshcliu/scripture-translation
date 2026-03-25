#!/usr/bin/env python3

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project.validation import run_validation


if __name__ == "__main__":
    results = run_validation()
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status}: {result.name}: {result.details}")
    raise SystemExit(0 if all(result.passed for result in results) else 1)
