from __future__ import annotations

import argparse

from .recovery_version_scraper import (
    DEFAULT_BOOK_DELAY_SECONDS,
    DEFAULT_CHAPTER_DELAY_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    NEW_TESTAMENT_BOOKS,
    OLD_TESTAMENT_BOOKS,
    build_fetcher,
    get_site_base_url,
    scrape_books,
)


def build_parser(testament: str, site: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Scrape the {testament.upper()} from the {site} Recovery Version site")
    parser.add_argument("--output-dir", required=True, help="Directory to write book JSON files into")
    parser.add_argument(
        "--chapter-delay",
        type=float,
        default=DEFAULT_CHAPTER_DELAY_SECONDS,
        help="Delay between chapter requests in seconds",
    )
    parser.add_argument(
        "--book-delay",
        type=float,
        default=DEFAULT_BOOK_DELAY_SECONDS,
        help="Delay between books in seconds",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-request timeout in seconds",
    )
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
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip books whose output JSON already exists",
    )
    return parser


def main(testament: str, site: str = "en", argv: list[str] | None = None) -> int:
    args = build_parser(testament, site).parse_args(argv)
    books = NEW_TESTAMENT_BOOKS if testament == "nt" else OLD_TESTAMENT_BOOKS
    fetcher = build_fetcher(
        timeout=args.timeout,
        max_retries=args.retries,
        retry_backoff_seconds=args.retry_backoff,
    )
    paths = scrape_books(
        books=books,
        output_dir=args.output_dir,
        fetcher=fetcher,
        base_url=get_site_base_url(site),
        chapter_delay_seconds=args.chapter_delay,
        book_delay_seconds=args.book_delay,
        skip_existing=args.skip_existing,
        language_code=site,
    )
    for path in paths:
        print(path)
    return 0
