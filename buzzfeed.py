#!/usr/bin/env python3
from __future__ import annotations
import csv
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# —————— CONFIGURATION ——————
SECTIONS = {
    "news":          "https://www.buzzfeed.com/news/",
    "entertainment": "https://www.buzzfeed.com/entertainment/",
    "tasty":         "https://www.buzzfeed.com/tasty/",
    "shopping":      "https://www.buzzfeed.com/shopping/",
    "travel":        "https://www.buzzfeed.com/travel/",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/15.1 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

CSV_FILE  = "buzzfeed_articles.csv"
BATCH_PER = 50   # How many per section each run


# —————— HELPERS ——————
def load_existing_urls(path: str) -> set[str]:
    if not Path(path).exists():
        return set()
    seen = set()
    with open(path, newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            seen.add(row["URL"])
    return seen


def get_section_links_rss(section_url: str, label: str) -> list[str]:
    """
    Discover the section’s RSS feed via the HTML <link> tag,
    then parse it to get article URLs.
    Falls back to section_url.rstrip('/') + '.xml' if not found.
    """
    # 1) Fetch the section landing page
    logging.info("Discovering RSS for %s via HTML", label)
    page = SESSION.get(section_url, timeout=10)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")

    # 2) Look for <link type="application/rss+xml">
    rss_link = soup.find("link", {"type": "application/rss+xml"})
    if rss_link and rss_link.get("href"):
        feed_url = rss_link["href"].strip()
    else:
        # fallback heuristic
        feed_url = section_url.rstrip("/") + ".xml"

    logging.info("Using feed URL for %s: %s", label, feed_url)
    resp = SESSION.get(feed_url, timeout=10)
    resp.raise_for_status()

    feed = feedparser.parse(resp.content)
    links = [
        entry.link.strip()
        for entry in feed.entries
        if getattr(entry, "link", None)
    ]
    logging.info("→ Found %d RSS links in %s", len(links), label)
    return links


def get_soup(url: str) -> BeautifulSoup:
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def count_links(soup: BeautifulSoup, article_url: str) -> tuple[int,int]:
    base = urlparse(article_url).netloc
    container = soup.select_one("article") or soup
    internal = external = 0
    for a in container.select("a[href]"):
        dom = urlparse(urljoin(article_url, a["href"])).netloc
        if dom == "" or dom == base:
            internal += 1
        else:
            external += 1
    return internal, external


# —————— PARSER ——————
def parse_article(url: str) -> dict:
    soup = get_soup(url)

    # Publication Date
    pub_date = ""
    meta_pub = soup.find("meta", {"property": "article:published_time"})
    if meta_pub and meta_pub.get("content"):
        pub_date = meta_pub["content"].strip()

    # Headline
    h1 = soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""
    headline_len = len(headline.split())

    # Body text & word count
    paras = soup.select("article p")
    article_text = " ".join(p.get_text(" ", strip=True) for p in paras)
    word_count = len(article_text.split())

    # Link counts
    internal_links, external_links = count_links(soup, url)

    # Scrape timestamp
    scrape_date = datetime.now(timezone.utc).isoformat()

    return {
        "Source":            "BuzzFeed",
        "URL":               url,
        "Section":           None,  # filled in below
        "Publication Date":  pub_date,
        "Headline":          headline,
        "Headline Length":   headline_len,
        "Word Count":        word_count,
        "Internal Links":    internal_links,
        "External Links":    external_links,
        "Article Text":      article_text,
        "Scrape Date":       scrape_date,
    }


# —————— MAIN ——————
def main(limit_per_section: int | None = None):
    seen = load_existing_urls(CSV_FILE)
    new_rows: list[dict] = []

    for label, section_url in SECTIONS.items():
        urls = get_section_links_rss(section_url, label)
        if limit_per_section:
            urls = urls[:limit_per_section]

        for url in tqdm(urls, desc=label, unit="url"):
            if url in seen:
                continue
            try:
                data = parse_article(url)
                data["Section"] = label
                new_rows.append(data)
                seen.add(url)
            except Exception as exc:
                logging.warning("Failed to parse %s: %s", url, exc)
            time.sleep(0.5)

    write_header = not Path(CSV_FILE).exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=[
            "Source", "URL", "Section", "Publication Date",
            "Headline", "Headline Length", "Word Count",
            "Internal Links", "External Links",
            "Article Text", "Scrape Date"
        ])
        if write_header:
            writer.writeheader()
        for row in new_rows:
            writer.writerow(row)

    logging.info("Done – wrote %d new rows to %s", len(new_rows), CSV_FILE)


if __name__ == "__main__":
    main(limit_per_section=BATCH_PER)
