from __future__ import annotations

import argparse

from .recovery_version_scraper import parse_chapter_selection, scrape_book


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape verse text from text.recoveryversion.bible")
    parser.add_argument("--book", required=True, help="Book name, for example John")
    parser.add_argument(
        "--chapters",
        help="Optional chapter selection, for example '1', '1-3', or '1,3,5-7'",
    )
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between chapter requests in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    chapters = parse_chapter_selection(args.chapters)
    output_path = scrape_book(
        book=args.book,
        chapters=chapters,
        output_path=args.output,
        delay_seconds=args.delay,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
