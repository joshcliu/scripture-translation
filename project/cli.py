from __future__ import annotations

import argparse
import sys

from .config import MODE_TO_ADAPTER
from .inference import translate
from .training import train_adapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recovery Version translation MVP")
    subparsers = parser.add_subparsers(dest="command")

    translate_parser = subparsers.add_parser("translate", help="Translate text")
    translate_parser.add_argument("--mode", required=True, choices=sorted(MODE_TO_ADAPTER))
    translate_parser.add_argument("--lang", required=True, default="es")
    translate_parser.add_argument("--text", required=True)

    train_parser = subparsers.add_parser("train-adapter", help="Trigger adapter training")
    train_parser.add_argument("--dataset-path", required=True)
    train_parser.add_argument("--adapter-name", required=True, choices=sorted(MODE_TO_ADAPTER.values()))

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].startswith("--"):
        argv = ["translate", *argv]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "translate":
        print(translate(text=args.text, mode=args.mode, target_lang=args.lang))
        return 0

    if args.command == "train-adapter":
        job = train_adapter(dataset_path=args.dataset_path, adapter_name=args.adapter_name)
        print(f"{job.adapter_name} -> {job.status} ({job.adapter_path})")
        return 0

    if args.command is None:
        parser.print_help()
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
