from __future__ import annotations

import json
import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Callable
from urllib import error, parse, request


ENGLISH_BASE_URL = "https://text.recoveryversion.bible/"
SPANISH_BASE_URL = "https://texto.versionrecobro.org/"
BASE_URL = ENGLISH_BASE_URL
DEFAULT_CHAPTER_DELAY_SECONDS = 1.5
DEFAULT_BOOK_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_RETRIES = 4
DEFAULT_RETRY_BACKOFF_SECONDS = 5.0
DEFAULT_HEADERS = {
    "User-Agent": "scripture-translation-mvp/0.1 (+authorized-use)",
}
SITE_BASE_URLS = {
    "en": ENGLISH_BASE_URL,
    "es": SPANISH_BASE_URL,
}

BOOK_ALIASES = {
    "genesis": ["genesis", "gen"],
    "exodus": ["exodus", "exo"],
    "leviticus": ["leviticus", "lev"],
    "numbers": ["numbers", "num"],
    "deuteronomy": ["deuteronomy", "deut"],
    "joshua": ["joshua", "josh"],
    "judges": ["judges", "judg"],
    "ruth": ["ruth"],
    "1samuel": ["1samuel", "1sam"],
    "2samuel": ["2samuel", "2sam"],
    "1kings": ["1kings"],
    "2kings": ["2kings"],
    "1chronicles": ["1chronicles", "1chron"],
    "2chronicles": ["2chronicles", "2chron"],
    "ezra": ["ezra"],
    "nehemiah": ["nehemiah", "neh"],
    "esther": ["esther", "esth"],
    "job": ["job"],
    "psalms": ["psalms", "psalm", "psa"],
    "proverbs": ["proverbs", "prov"],
    "ecclesiastes": ["ecclesiastes", "eccl"],
    "songofsongs": ["songofsongs", "songofsongs", "ss"],
    "isaiah": ["isaiah", "isa"],
    "jeremiah": ["jeremiah", "jer"],
    "lamentations": ["lamentations", "lam"],
    "ezekiel": ["ezekiel", "ezek"],
    "daniel": ["daniel", "dan"],
    "hosea": ["hosea"],
    "joel": ["joel"],
    "amos": ["amos"],
    "obadiah": ["obadiah", "obad"],
    "jonah": ["jonah"],
    "micah": ["micah"],
    "nahum": ["nahum"],
    "habakkuk": ["habakkuk", "hab"],
    "zephaniah": ["zephaniah", "zeph"],
    "haggai": ["haggai", "hag"],
    "zechariah": ["zechariah", "zech"],
    "malachi": ["malachi", "mal"],
    "matthew": ["matthew", "matt"],
    "mark": ["mark"],
    "luke": ["luke"],
    "john": ["john"],
    "acts": ["acts"],
    "romans": ["romans", "rom"],
    "1corinthians": ["1corinthians", "1cor"],
    "2corinthians": ["2corinthians", "2cor"],
    "galatians": ["galatians", "gal"],
    "ephesians": ["ephesians", "eph"],
    "philippians": ["philippians", "phil"],
    "colossians": ["colossians", "col"],
    "1thessalonians": ["1thessalonians", "1thes"],
    "2thessalonians": ["2thessalonians", "2thes"],
    "1timothy": ["1timothy", "1tim"],
    "2timothy": ["2timothy", "2tim"],
    "titus": ["titus"],
    "philemon": ["philemon", "philem"],
    "hebrews": ["hebrews", "heb"],
    "james": ["james"],
    "1peter": ["1peter", "1pet"],
    "2peter": ["2peter", "2pet"],
    "1john": ["1john"],
    "2john": ["2john"],
    "3john": ["3john"],
    "jude": ["jude"],
    "revelation": ["revelation", "rev"],
}

OLD_TESTAMENT_BOOKS = [
    "Genesis",
    "Exodus",
    "Leviticus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1Samuel",
    "2Samuel",
    "1Kings",
    "2Kings",
    "1Chronicles",
    "2Chronicles",
    "Ezra",
    "Nehemiah",
    "Esther",
    "Job",
    "Psalms",
    "Proverbs",
    "Ecclesiastes",
    "SongofSongs",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
]

NEW_TESTAMENT_BOOKS = [
    "Matthew",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1Corinthians",
    "2Corinthians",
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1Thessalonians",
    "2Thessalonians",
    "1Timothy",
    "2Timothy",
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1Peter",
    "2Peter",
    "1John",
    "2John",
    "3John",
    "Jude",
    "Revelation",
]

INDEX_LINK_RE = re.compile(r'<a[^>]+href="(?P<href>\d{2}_[^"]+_1\.htm)"[^>]*>(?P<label>.*?)</a>', re.IGNORECASE)
CHAPTER_LINK_RE = re.compile(r'<a href="(?P<href>\d{2}_[^"]+_(?P<chapter>\d+)\.htm)">\d+</a>', re.IGNORECASE)
TITLE_RE = re.compile(
    r"<title>\s*(?P<title>.*?)\s+(?:Recovery Version|Versi[oó]n Recobro)\s*</title>",
    re.IGNORECASE | re.DOTALL,
)
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


def build_fetcher(
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> Fetcher:
    def fetcher(url: str) -> str:
        return fetch_text(
            url=url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    return fetcher


def fetch_text(
    url: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> str:
    attempts = max(1, max_retries)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = request.Request(url, headers=DEFAULT_HEADERS)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except (TimeoutError, socket.timeout, ssl.SSLError, error.URLError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(retry_backoff_seconds * attempt)
    assert last_error is not None
    raise RuntimeError(f"Failed to fetch {url} after {attempts} attempts: {last_error}") from last_error


def normalize_book_name(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", book.lower())


def get_site_base_url(site: str) -> str:
    try:
        return SITE_BASE_URLS[site]
    except KeyError as exc:
        supported = ", ".join(sorted(SITE_BASE_URLS))
        raise ValueError(f"Unsupported site '{site}'. Expected one of: {supported}") from exc


def get_book_index(fetcher: Fetcher = fetch_text, base_url: str = BASE_URL) -> dict[str, str]:
    html = fetcher(base_url)
    mapping: dict[str, str] = {}
    for match in INDEX_LINK_RE.finditer(html):
        label = _clean_text(match.group("label"))
        href = match.group("href")
        url = parse.urljoin(base_url, href)
        if not label:
            continue
        mapping[normalize_book_name(label)] = url
        url_book_key = _book_key_from_href(href)
        if url_book_key:
            mapping[url_book_key] = url
    if not mapping:
        raise RuntimeError("Could not find any book links on the Recovery Version index page.")
    return mapping


def discover_chapter_urls(book: str, fetcher: Fetcher = fetch_text, base_url: str = BASE_URL) -> list[str]:
    book_links = get_book_index(fetcher=fetcher, base_url=base_url)
    book_key = _resolve_book_key(book, book_links)
    try:
        first_chapter_url = book_links[book_key]
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
    delay_seconds: float = DEFAULT_CHAPTER_DELAY_SECONDS,
    language_code: str = "en",
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
        verses.extend(parse_chapter_page(html, chapter_url, canonical_book=book))
        if delay_seconds and index < len(chapter_urls) - 1:
            time.sleep(delay_seconds)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump([asdict(verse) for verse in verses], handle, ensure_ascii=False, indent=2)
    return output


def scrape_books(
    books: list[str],
    output_dir: str | Path,
    fetcher: Fetcher = fetch_text,
    base_url: str = BASE_URL,
    chapter_delay_seconds: float = DEFAULT_CHAPTER_DELAY_SECONDS,
    book_delay_seconds: float = DEFAULT_BOOK_DELAY_SECONDS,
    skip_existing: bool = True,
    language_code: str = "en",
) -> list[Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for index, book in enumerate(books):
        output_path = output_root / f"recovery_version_{_slugify_book_name(book)}_{language_code}.json"
        if skip_existing and output_path.exists():
            written_paths.append(output_path)
            print(f"Skipping existing {output_path}")
            continue
        print(f"Scraping {book} -> {output_path}")
        written_paths.append(
            scrape_book(
                book=book,
                output_path=output_path,
                fetcher=fetcher,
                base_url=base_url,
                delay_seconds=chapter_delay_seconds,
                language_code=language_code,
            )
        )
        if book_delay_seconds and index < len(books) - 1:
            time.sleep(book_delay_seconds)
    return written_paths


def parse_chapter_page(html: str, source_url: str, canonical_book: str | None = None) -> list[VerseRecord]:
    title_match = TITLE_RE.search(html)
    if title_match is None and canonical_book is None:
        raise RuntimeError(f"Could not determine book title from {source_url}")
    book = _clean_text(title_match.group("title")) if title_match is not None else canonical_book or ""
    canonical_slug = _slugify_book_name(canonical_book or book)
    verses: list[VerseRecord] = []

    for match in VERSE_RE.finditer(html):
        chapter = int(match.group("chapter"))
        verse = int(match.group("verse"))
        body = match.group("body")
        body = re.sub(r"^\s*<b>.*?</b>\s*", "", body, count=1, flags=re.DOTALL)
        text = _clean_text(body)
        verses.append(
            VerseRecord(
                id=f"{canonical_slug}_{chapter}_{verse}",
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


def _book_key_from_href(href: str) -> str | None:
    match = re.search(r"^\d{2}_(?P<book>[^_]+)_(?:\d+|o)\.htm$", href)
    if match is None:
        return None
    return normalize_book_name(match.group("book"))


def _slugify_book_name(book: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", book.lower()).strip("_")


def _resolve_book_key(book: str, book_links: dict[str, str]) -> str:
    normalized = normalize_book_name(book)
    if normalized in book_links:
        return normalized

    aliases = BOOK_ALIASES.get(normalized, [])
    for alias in aliases:
        alias_key = normalize_book_name(alias)
        if alias_key in book_links:
            return alias_key

    for canonical, alias_values in BOOK_ALIASES.items():
        if normalized == canonical:
            continue
        if normalized in {normalize_book_name(value) for value in alias_values} and canonical in book_links:
            return canonical

    raise KeyError(normalized)



def _clean_text(raw_html: str) -> str:
    text = TAG_RE.sub("", raw_html)
    text = unescape(text)
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()
