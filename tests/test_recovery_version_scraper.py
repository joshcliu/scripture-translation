from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project.recovery_version_scraper import (
    NEW_TESTAMENT_BOOKS,
    OLD_TESTAMENT_BOOKS,
    build_fetcher,
    discover_chapter_urls,
    fetch_text,
    parse_chapter_page,
    parse_chapter_selection,
    scrape_book,
    scrape_books,
)


INDEX_HTML = """
<html><body>
<a class="gospels" href="43_John_1.htm">John</a>
<a class="gospels" href="42_Luke_1.htm">Luke</a>
</body></html>
"""

JOHN_1_HTML = """
<html>
<head><title>John Recovery Version</title></head>
<body>
<div class="chapter-links">
<a href="43_John_1.htm">1</a> <a href="43_John_2.htm">2</a>
</div>
<section id="verses">
<p id="Joh1-1" class="verse"><b><a href="43_John_1.htm">John 1</a><a href="43_John_1.htm">:1</a> </b>In the beginning was the Word.</p>
<p id="Joh1-2" class="verse"><b><a href="43_John_1.htm">John 1</a><a href="43_John_1.htm">:2</a> </b>He was in the beginning with God.</p>
</section>
</body>
</html>
"""

JOHN_2_HTML = """
<html>
<head><title>John Recovery Version</title></head>
<body>
<div class="chapter-links">
<a href="43_John_1.htm">1</a> <a href="43_John_2.htm">2</a>
</div>
<section id="verses">
<p id="Joh2-1" class="verse"><b><a href="43_John_2.htm">John 2</a><a href="43_John_2.htm">:1</a> </b>And the third day a wedding took place in Cana of Galilee.</p>
</section>
</body>
</html>
"""

LUKE_1_HTML = """
<html>
<head><title>Luke Recovery Version</title></head>
<body>
<div class="chapter-links">
<a href="42_Luke_1.htm">1</a>
</div>
<section id="verses">
<p id="Luk1-1" class="verse"><b><a href="42_Luke_1.htm">Luke 1</a><a href="42_Luke_1.htm">:1</a> </b>Since many have undertaken to draw up a narrative.</p>
</section>
</body>
</html>
"""


class RecoveryVersionScraperTests(unittest.TestCase):
    def test_parse_chapter_page_extracts_verse_records(self) -> None:
        verses = parse_chapter_page(JOHN_1_HTML, "https://text.recoveryversion.bible/43_John_1.htm")
        self.assertEqual(len(verses), 2)
        self.assertEqual(verses[0].id, "john_1_1")
        self.assertEqual(verses[0].text, "In the beginning was the Word.")

    def test_discover_chapter_urls_reads_book_index_and_chapters(self) -> None:
        responses = {
            "https://text.recoveryversion.bible/": INDEX_HTML,
            "https://text.recoveryversion.bible/43_John_1.htm": JOHN_1_HTML,
        }

        def fetcher(url: str) -> str:
            return responses[url]

        urls = discover_chapter_urls("John", fetcher=fetcher)
        self.assertEqual(
            urls,
            [
                "https://text.recoveryversion.bible/43_John_1.htm",
                "https://text.recoveryversion.bible/43_John_2.htm",
            ],
        )

    def test_discover_chapter_urls_supports_full_book_name_aliases(self) -> None:
        responses = {
            "https://text.recoveryversion.bible/": """
                <html><body><a class="gospels" href="40_Matthew_1.htm">Matt</a></body></html>
            """,
            "https://text.recoveryversion.bible/40_Matthew_1.htm": """
                <html><head><title>Matthew Recovery Version</title></head><body>
                <div class="chapter-links"><a href="40_Matthew_1.htm">1</a> <a href="40_Matthew_2.htm">2</a></div>
                <section id="verses"><p id="Mat1-1" class="verse"><b>x</b>Book of the generation of Jesus Christ.</p></section>
                </body></html>
            """,
        }

        def fetcher(url: str) -> str:
            return responses[url]

        urls = discover_chapter_urls("Matthew", fetcher=fetcher)
        self.assertEqual(
            urls,
            [
                "https://text.recoveryversion.bible/40_Matthew_1.htm",
                "https://text.recoveryversion.bible/40_Matthew_2.htm",
            ],
        )

    def test_scrape_book_writes_json_records(self) -> None:
        responses = {
            "https://text.recoveryversion.bible/": INDEX_HTML,
            "https://text.recoveryversion.bible/43_John_1.htm": JOHN_1_HTML,
            "https://text.recoveryversion.bible/43_John_2.htm": JOHN_2_HTML,
        }

        def fetcher(url: str) -> str:
            return responses[url]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "john.json"
            scrape_book("John", output_path=output_path, fetcher=fetcher)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload), 3)
            self.assertEqual(payload[2]["id"], "john_2_1")

    def test_parse_chapter_selection_supports_ranges(self) -> None:
        self.assertEqual(parse_chapter_selection("1,3,5-7"), [1, 3, 5, 6, 7])

    def test_scrape_books_writes_expected_filenames(self) -> None:
        responses = {
            "https://text.recoveryversion.bible/": INDEX_HTML,
            "https://text.recoveryversion.bible/43_John_1.htm": JOHN_1_HTML,
            "https://text.recoveryversion.bible/43_John_2.htm": JOHN_2_HTML,
            "https://text.recoveryversion.bible/42_Luke_1.htm": LUKE_1_HTML,
        }

        def fetcher(url: str) -> str:
            return responses[url]

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = scrape_books(
                books=["John", "Luke"],
                output_dir=temp_dir,
                fetcher=fetcher,
                chapter_delay_seconds=0.0,
                book_delay_seconds=0.0,
            )
            self.assertEqual([path.name for path in paths], ["recovery_version_john_en.json", "recovery_version_luke_en.json"])

    def test_testament_book_lists_include_expected_books(self) -> None:
        self.assertIn("Genesis", OLD_TESTAMENT_BOOKS)
        self.assertIn("John", NEW_TESTAMENT_BOOKS)
        self.assertEqual(len(OLD_TESTAMENT_BOOKS), 39)
        self.assertEqual(len(NEW_TESTAMENT_BOOKS), 27)

    def test_scrape_books_can_skip_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "recovery_version_john_en.json"
            existing.write_text("[]", encoding="utf-8")

            def fetcher(url: str) -> str:
                raise AssertionError(f"fetcher should not be called for existing outputs: {url}")

            paths = scrape_books(
                books=["John"],
                output_dir=temp_dir,
                fetcher=fetcher,
                chapter_delay_seconds=0.0,
                book_delay_seconds=0.0,
                skip_existing=True,
            )
            self.assertEqual(paths, [existing])


if __name__ == "__main__":
    unittest.main()
