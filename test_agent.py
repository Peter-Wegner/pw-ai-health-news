import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from agent import Article, deduplicate, parse_feed, rank_article, render_digest
from pdf_report import write_pdf


RSS = b"""<?xml version="1.0"?>
<rss><channel><item>
<title>AI improves clinical diagnosis</title>
<link>https://example.com/story</link>
<description><![CDATA[<b>A medical study</b> found better results.]]></description>
<pubDate>Thu, 11 Jun 2026 12:00:00 GMT</pubDate>
</item></channel></rss>"""


class AgentTest(unittest.TestCase):
    def test_parse_feed(self):
        article = parse_feed(RSS, "Test")[0]
        self.assertEqual(article.title, "AI improves clinical diagnosis")
        self.assertEqual(article.summary, "A medical study found better results.")
        self.assertEqual(article.published.day, 11)

    def test_rank_article(self):
        article = parse_feed(RSS, "Test")[0]
        ranked = rank_article(
            article,
            {"keywords": {"clinical": 3, "medical": 2}, "negative_keywords": {}},
        )
        self.assertEqual(ranked.score, 5)

    def test_deduplicate_keeps_higher_score(self):
        first = Article("Same title - Publisher A", "https://a", "", "A", None, 2)
        second = Article("Same title - Publisher B", "https://b", "", "B", None, 5)
        self.assertEqual(deduplicate([first, second])[0].score, 5)

    def test_render_digest(self):
        article = Article("Title", "https://a", "Summary", "Source", None, 7, ("AI",))
        result = render_digest([article], datetime(2026, 6, 12, tzinfo=timezone.utc))
        self.assertIn("# Health-AI-News: 2026-06-12", result)
        self.assertIn("[Title](https://a)", result)

    def test_write_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            markdown = Path(directory) / "report.md"
            pdf = Path(directory) / "report.pdf"
            markdown.write_text("# Health-AI\n\nÄrztliche KI-News", encoding="utf-8")
            write_pdf(markdown, pdf)
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-1.4"))


if __name__ == "__main__":
    unittest.main()
