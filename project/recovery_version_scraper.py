from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Callable
from urllib import parse, request


BASE_URL = "https://text.recoveryversion.bible/"
DEFAULT_HEADERS = {
    "User-Agent": "scripture-translation-mvp/0.1 (+authorized-use)",
}

INDEX_LINK_RE = re.compile(r'<a[^>]+href="(?P<href>\d{2}_[^"]+_1\.htm)"[^>]*>(?P<label>.*?)</a>', re.IGNORECASE)
CHAPTER_LINK_RE = re.compile(r'<a href="(?P<href>\d{2}_[^"]+_(?P<chapter>\d+)\.htm)">\d+</a>', re.IGNORECASE)
TITLE_RE = re.compile(r"<title>\s*(?P<title>.*?)\s+Recovery Version\s*</title>", re.IGNORECASE | re.DOTALL)
VERSE_RE = re.compile(
    r'<p[^>]+id="(?P<anchor>[A-Za-z0-9]+?(?P<chapter>\d+)-(?P<verse>\d+))"[^>]*class="verse"[^>]*>(?P<body>.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class VerseRecord:
    id: str
    book: str
    chapter: int
    verse: int
    text: str
    source_url: str


Fetcher = Callable[[str], str]


def fetch_text(url: str, timeout: int = 30) -> str:
    req = request.Request(url, headers=DEFAULT_HEADERS)
    with request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def normalize_book_name(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", book.lower())


def get_book_index(fetcher: Fetcher = fetch_text, base_url: str = BASE_URL) -> dict[str, str]:
    html = fetcher(base_url)
    mapping: dict[str, str] = {}
    for match in INDEX_LINK_RE.finditer(html):
        label = _clean_text(match.group("label"))
        href = match.group("href")
        if not label:
            continue
        mapping[normalize_book_name(label)] = parse.urljoin(base_url, href)
    if not mapping:
        raise RuntimeError("Could not find any book links on the Recovery Version index page.")
    return mapping


def discover_chapter_urls(book: str, fetcher: Fetcher = fetch_text, base_url: str = BASE_URL) -> list[str]:
    book_links = get_book_index(fetcher=fetcher, base_url=base_url)
    try:
        first_chapter_url = book_links[normalize_book_name(book)]
    except KeyError as exc:
        supported = ", ".join(sorted(book_links))
        raise ValueError(f"Unknown book '{book}'. Available normalized book keys include: {supported}") from exc

    html = fetcher(first_chapter_url)
    chapter_matches = CHAPTER_LINK_RE.findall(html)
    chapter_urls = [parse.urljoin(first_chapter_url, href) for href, _chapter in chapter_matches]
    if not chapter_urls:
        chapter_urls = [first_chapter_url]
    return chapter_urls


def scrape_book(
    book: str,
    output_path: str | Path,
    chapters: list[int] | None = None,
    fetcher: Fetcher = fetch_text,
    base_url: str = BASE_URL,
    delay_seconds: float = 0.0,
) -> Path:
    chapter_urls = discover_chapter_urls(book=book, fetcher=fetcher, base_url=base_url)
    if chapters is not None:
        allowed = set(chapters)
        chapter_urls = [url for url in chapter_urls if _chapter_from_url(url) in allowed]
    if not chapter_urls:
        raise ValueError(f"No chapter URLs found for book '{book}' and chapters '{chapters}'")

    verses: list[VerseRecord] = []
    for index, chapter_url in enumerate(chapter_urls):
        html = fetcher(chapter_url)
        verses.extend(parse_chapter_page(html, chapter_url))
        if delay_seconds and index < len(chapter_urls) - 1:
            time.sleep(delay_seconds)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump([asdict(verse) for verse in verses], handle, ensure_ascii=False, indent=2)
    return output


def parse_chapter_page(html: str, source_url: str) -> list[VerseRecord]:
    title_match = TITLE_RE.search(html)
    if title_match is None:
        raise RuntimeError(f"Could not determine book title from {source_url}")
    book = _clean_text(title_match.group("title"))
    verses: list[VerseRecord] = []

    for match in VERSE_RE.finditer(html):
        chapter = int(match.group("chapter"))
        verse = int(match.group("verse"))
        body = match.group("body")
        body = re.sub(r"^\s*<b>.*?</b>\s*", "", body, count=1, flags=re.DOTALL)
        text = _clean_text(body)
        verses.append(
            VerseRecord(
                id=f"{book.lower().replace(' ', '_')}_{chapter}_{verse}",
                book=book,
                chapter=chapter,
                verse=verse,
                text=text,
                source_url=source_url,
            )
        )

    if not verses:
        raise RuntimeError(f"No verse records found in {source_url}")
    return verses


def parse_chapter_selection(raw_value: str | None) -> list[int] | None:
    if raw_value is None or not raw_value.strip():
        return None

    chapters: set[int] = set()
    for part in raw_value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"Invalid chapter range '{item}'")
            chapters.update(range(start, end + 1))
        else:
            chapters.add(int(item))
    return sorted(chapters)


def _chapter_from_url(url: str) -> int:
    match = re.search(r"_(\d+)\.htm$", url)
    if match is None:
        raise ValueError(f"Could not parse chapter from URL '{url}'")
    return int(match.group(1))


def _clean_text(raw_html: str) -> str:
    text = TAG_RE.sub("", raw_html)
    text = unescape(text)
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()
