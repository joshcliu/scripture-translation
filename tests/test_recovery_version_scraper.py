from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from project.recovery_version_scraper import (
    discover_chapter_urls,
    parse_chapter_page,
    parse_chapter_selection,
    scrape_book,
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


if __name__ == "__main__":
    unittest.main()
