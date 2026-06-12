#!/usr/bin/env python3
"""Collect and rank daily health AI news from RSS and Atom feeds."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


USER_AGENT = "HealthAINewsAgent/1.0"
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    source: str
    published: Optional[datetime]
    score: int = 0
    reasons: Sequence[str] = ()


def clean_text(value: str) -> str:
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", value or ""))).strip()


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        result = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def element_text(element: ET.Element, names: Sequence[str]) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] in names and child.text:
            return child.text
    return ""


def article_link(element: ET.Element) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        if child.get("href") and child.get("rel", "alternate") == "alternate":
            return child.get("href", "")
        if child.text:
            return child.text.strip()
    return ""


def parse_feed(payload: bytes, source: str) -> List[Article]:
    root = ET.fromstring(payload)
    articles = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] not in ("item", "entry"):
            continue
        title = clean_text(element_text(element, ("title",)))
        url = article_link(element)
        if not title or not url:
            continue
        summary = clean_text(
            element_text(element, ("description", "summary", "content"))
        )
        published = parse_date(
            element_text(element, ("pubDate", "published", "updated"))
        )
        articles.append(Article(title, url, summary, source, published))
    return articles


def fetch_feed(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context(cafile=find_ca_bundle())
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.read()


def find_ca_bundle() -> Optional[str]:
    """Prefer an explicit CA bundle; some macOS Python installs miss it by default."""
    candidates = (
        Path("/etc/ssl/cert.pem"),
        Path("/opt/homebrew/etc/ca-certificates/cert.pem"),
        Path("/usr/local/etc/openssl@3/cert.pem"),
    )
    return next((str(path) for path in candidates if path.is_file()), None)


def rank_article(article: Article, config: Dict[str, object]) -> Article:
    text = f"{article.title} {article.summary}".lower()
    score = 0
    reasons = []
    for keyword, weight in config["keywords"].items():
        if keyword.lower() in text:
            score += int(weight)
            reasons.append(keyword)
    for keyword, penalty in config.get("negative_keywords", {}).items():
        if keyword.lower() in text:
            score -= int(penalty)
    return Article(
        article.title,
        article.url,
        article.summary,
        article.source,
        article.published,
        score,
        tuple(reasons),
    )


def article_id(article: Article) -> str:
    normalized = article.url.split("#", 1)[0].rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate(articles: Iterable[Article]) -> List[Article]:
    result = {}
    for article in articles:
        # Google News appends the publisher to otherwise identical headlines.
        headline = article.title.rsplit(" - ", 1)[0]
        key = re.sub(r"\W+", " ", headline.lower()).strip()
        previous = result.get(key)
        if previous is None or article.score > previous.score:
            result[key] = article
    return list(result.values())


def load_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def render_digest(articles: Sequence[Article], generated_at: datetime) -> str:
    lines = [
        f"# Health-AI-News: {generated_at.date().isoformat()}",
        "",
        f"Erstellt: {generated_at.astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        "",
    ]
    if not articles:
        lines.append("Keine neuen relevanten Meldungen gefunden.")
        return "\n".join(lines) + "\n"

    for index, article in enumerate(articles, 1):
        published = (
            article.published.date().isoformat() if article.published else "unbekannt"
        )
        summary = article.summary[:500].rsplit(" ", 1)[0] if article.summary else ""
        lines.extend(
            [
                f"## {index}. [{article.title}]({article.url})",
                "",
                f"**Quelle:** {article.source} | **Datum:** {published} | "
                f"**Relevanz:** {article.score}",
                "",
                summary or "Keine Kurzbeschreibung verfügbar.",
                "",
                f"*Treffer: {', '.join(article.reasons[:8])}*",
                "",
            ]
        )
    return "\n".join(lines)


def collect(config: Dict[str, object], cutoff: datetime) -> List[Article]:
    collected = []
    for feed in config["feeds"]:
        try:
            payload = fetch_feed(feed["url"])
            articles = parse_feed(payload, feed["name"])
        except Exception as exc:
            print(f"Warnung: {feed['name']} konnte nicht geladen werden: {exc}", file=sys.stderr)
            continue
        for article in articles:
            if article.published and article.published < cutoff:
                continue
            ranked = rank_article(article, config)
            if ranked.score >= int(config.get("minimum_score", 4)):
                collected.append(ranked)
    return deduplicate(collected)


def main(argv: Optional[Sequence[str]] = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=base_dir / "config.json")
    parser.add_argument("--output-dir", type=Path, default=base_dir / "output")
    parser.add_argument("--state-file", type=Path, default=base_dir / "state" / "seen.json")
    parser.add_argument("--days", type=int, default=2, help="Maximum age of articles")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="Do not update seen state")
    args = parser.parse_args(argv)

    config = load_json(args.config, {})
    if not isinstance(config, dict) or not config.get("feeds") or not config.get("keywords"):
        parser.error("config must contain non-empty 'feeds' and 'keywords'")

    now = datetime.now(timezone.utc)
    articles = collect(config, now - timedelta(days=args.days))
    seen = set(load_json(args.state_file, []))
    fresh = [article for article in articles if article_id(article) not in seen]
    fresh.sort(
        key=lambda article: (article.score, article.published or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    fresh = fresh[: args.max_items]

    digest = render_digest(fresh, now)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{now.date().isoformat()}.md"
    output_path.write_text(digest, encoding="utf-8")

    if not args.dry_run:
        seen.update(article_id(article) for article in fresh)
        save_json(args.state_file, sorted(seen))

    print(output_path)
    print(f"{len(fresh)} neue relevante Meldung(en)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
