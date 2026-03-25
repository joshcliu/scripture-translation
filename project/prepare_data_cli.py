from __future__ import annotations

import argparse

from .config import MODE_TO_ADAPTER
from .data_pipeline import prepare_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare instruction-style training data")
    parser.add_argument("--mode", required=True, choices=sorted(MODE_TO_ADAPTER))
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--lang", required=True, default="es")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = prepare_dataset(
        mode=args.mode,
        source_path=args.source,
        target_path=args.target,
        target_lang=args.lang,
        output_path=args.output,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
