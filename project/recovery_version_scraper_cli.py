from __future__ import annotations

import argparse

from .recovery_version_scraper import (
    DEFAULT_CHAPTER_DELAY_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    build_fetcher,
    parse_chapter_selection,
    scrape_book,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape verse text from text.recoveryversion.bible")
    parser.add_argument("--book", required=True, help="Book name, for example John")
    parser.add_argument(
        "--chapters",
        help="Optional chapter selection, for example '1', '1-3', or '1,3,5-7'",
    )
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_CHAPTER_DELAY_SECONDS,
        help="Delay between chapter requests in seconds",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Per-request timeout in seconds")
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Number of fetch attempts per URL before failing",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
        help="Base backoff in seconds between retries",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    chapters = parse_chapter_selection(args.chapters)
    fetcher = build_fetcher(
        timeout=args.timeout,
        max_retries=args.retries,
        retry_backoff_seconds=args.retry_backoff,
    )
    output_path = scrape_book(
        book=args.book,
        chapters=chapters,
        output_path=args.output,
        fetcher=fetcher,
        delay_seconds=args.delay,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
