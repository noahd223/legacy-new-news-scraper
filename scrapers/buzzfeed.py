#!/usr/bin/env python3
from __future__ import annotations
import csv
import time
import logging
import xml.etree.ElementTree as ET
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

# ——— CONFIG ——————————————————————————————————————————————
SECTIONS = {
    "news":          "https://www.buzzfeed.com/news/",
    "entertainment": "https://www.buzzfeed.com/entertainment/",
    "tasty":         "https://www.buzzfeed.com/tasty/",
    "shopping":      "https://www.buzzfeed.com/shopping/",
    "travel":        "https://www.buzzfeed.com/travel/",
}

HEADERS       = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/15.1 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
SESSION       = requests.Session()
SESSION.headers.update(HEADERS)

CSV_FILE      = "buzzfeed_articles.csv"
BATCH_PER     = 50
SITEMAP_INDEX = "https://www.buzzfeed.com/sitemap.xml"
SITEMAP_NS    = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ——— PRELOAD SITEMAP ————————————————————————————————————
def load_sitemap_urls() -> set[str]:
    resp = SESSION.get(SITEMAP_INDEX, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    sitemap_urls = [
        loc.text.strip()
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS)
        if loc.text and loc.text.strip().endswith(".xml")
    ]

    pages: set[str] = set()
    for sm in sitemap_urls:
        try:
            r2 = SESSION.get(sm, timeout=15)
            r2.raise_for_status()
        except Exception:
            continue
        subroot = ET.fromstring(r2.content)
        for url_el in subroot.findall("sm:url/sm:loc", SITEMAP_NS):
            if url_el.text:
                pages.add(url_el.text.strip())

    logging.info("Loaded %d URLs from sitemap", len(pages))
    return pages

ALL_SITEMAP_URLS = load_sitemap_urls()


# ——— HELPERS —————————————————————————————————————————————
def load_existing_urls(path: str) -> set[str]:
    if not Path(path).exists():
        return set()
    seen = set()
    with open(path, newline="", encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            seen.add(row["URL"])
    return seen


def get_section_links(section_url: str, label: str) -> list[str]:
    # 1) Try RSS discovery
    try:
        page = SESSION.get(section_url, timeout=10)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        rss_tag = soup.find("link", {"type": "application/rss+xml"})
        feed_url = rss_tag["href"].strip() if (rss_tag and rss_tag.get("href")) else section_url.rstrip("/") + ".xml"
        logging.info("Fetching RSS for %s: %s", label, feed_url)
        r = SESSION.get(feed_url, timeout=10)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        links = [e.link.strip() for e in feed.entries if getattr(e, "link", None)]
        if links:
            logging.info("→ %d RSS links from %s", len(links), label)
            return links
    except Exception as e:
        logging.warning("RSS failed for %s: %s", label, e)

    # 2) Fallback to sitemap
    prefix = f"https://www.buzzfeed.com/{label}/"
    matched = [
        u for u in ALL_SITEMAP_URLS
        if u.startswith(prefix)
        and "-" in urlparse(u).path.rstrip("/").split("/")[-1]
    ]
    logging.info("→ %d sitemap links for %s", len(matched), label)
    return sorted(matched)


def get_soup(url: str) -> BeautifulSoup:
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def count_links(soup: BeautifulSoup, article_url: str) -> tuple[int,int]:
    """Count internal vs external <a> links in the <article> element."""
    base = urlparse(article_url).netloc
    container = soup.select_one("article") or soup

    internal = 0
    external = 0
    for a in container.select("a[href]"):
        dom = urlparse(urljoin(article_url, a["href"])).netloc
        if dom == "" or base in dom:
            internal += 1
        else:
            external += 1

    return internal, external


# ——— PARSER —————————————————————————————————————————————
def parse_article(url: str) -> dict:
    soup = get_soup(url)

    # Publication Date
    pub = soup.find("meta", {"property": "article:published_time"})
    pub_date = pub["content"].strip() if (pub and pub.get("content")) else ""

    # Headline
    h1 = soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""
    hl_len = len(headline.split())

    # Body & word count
    paras = soup.select("article p")
    text = " ".join(p.get_text(" ", strip=True) for p in paras)
    wc = len(text.split())

    # Link counts
    il, el = count_links(soup, url)

    # Scrape timestamp
    sd = datetime.now(timezone.utc).isoformat()

    return {
        "Source":           "BuzzFeed",
        "URL":              url,
        "Section":          None,  # set below
        "Publication Date": pub_date,
        "Headline":         headline,
        "Headline Length":  hl_len,
        "Word Count":       wc,
        "Internal Links":   il,
        "External Links":   el,
        "Article Text":     text,
        "Scrape Date":      sd,
    }


# ——— MAIN ———————————————————————————————————————————————
def main(limit_per_section: int | None = None):
    seen = load_existing_urls(CSV_FILE)
    new_rows: list[dict] = []

    for label, sec_url in SECTIONS.items():
        urls = get_section_links(sec_url, label)
        if limit_per_section:
            urls = urls[:limit_per_section]

        for u in tqdm(urls, desc=label, unit="url"):
            if u in seen:
                continue
            try:
                rec = parse_article(u)
                rec["Section"] = label
                new_rows.append(rec)
                seen.add(u)
            except Exception as ex:
                logging.warning("parse failed %s: %s", u, ex)
            time.sleep(0.5)

    write_hdr = not Path(CSV_FILE).exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=[
            "Source","URL","Section","Publication Date",
            "Headline","Headline Length","Word Count",
            "Internal Links","External Links",
            "Article Text","Scrape Date"
        ])
        if write_hdr:
            w.writeheader()
        for r in new_rows:
            w.writerow(r)

    logging.info("Done – appended %d rows", len(new_rows))


if __name__ == "__main__":
    main(limit_per_section=BATCH_PER)
