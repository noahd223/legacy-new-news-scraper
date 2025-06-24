#!/usr/bin/env python3
import requests, csv, json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

BASE_URL = "https://www.buzzfeed.com"
SOURCE = "BuzzFeed"
HEADERS = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                         "Version/15.1 Safari/605.1.15"}
CSV_FILE = "buzzfeed_articles.csv"
MAX_CANDIDATES = 100

def get_article_links():
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith("/"):
            href = urljoin(BASE_URL, href)
        if not href.startswith(BASE_URL):
            continue
        clean = href.split("?")[0].split("#")[0]
        last = urlparse(clean).path.rstrip("/").split("/")[-1]
        if "-" in last:
            links.add(clean)
    return list(links)[:MAX_CANDIDATES]

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def count_links(soup, article_url):
    base_domain = urlparse(article_url).netloc
    # find container
    body = None
    for sel in ("article","div.subbuzz__text","div.post-content","div[data-content-target='article-body']"):
        body = soup.select_one(sel)
        if body: break
    if not body: body = soup

    internal = external = 0
    # count <a>
    for a in body.select("a[href]"):
        dom = urlparse(urljoin(article_url, a["href"])).netloc
        if dom == "" or base_domain in dom:
            internal += 1
        else:
            external += 1
    # count <video> & <iframe>
    for tag in body.select("video[src], iframe[src]"):
        dom = urlparse(urljoin(article_url, tag["src"])).netloc
        if dom == "" or base_domain in dom:
            internal += 1
        else:
            external += 1

    return internal, external

def parse_article(url):
    soup = get_soup(url)
    # section
    sec = None
    m = soup.find("meta", {"property":"article:section"})
    if m and m.get("content"):
        sec = m["content"].strip()
    # pub_date
    pub = None
    m2 = soup.find("meta", {"property":"article:published_time"})
    if m2 and m2.get("content"):
        pub = m2["content"].strip()
    else:
        ld = soup.find("script", type="application/ld+json")
        if ld and ld.string:
            data = json.loads(ld.string)
            entries = data if isinstance(data, list) else [data]
            for e in entries:
                if e.get("datePublished"):
                    pub = e["datePublished"]
                    break
    # headline
    h1 = soup.find("h1")
    hd = h1.get_text(strip=True) if h1 else ""
    hl = len(hd.split())
    # body text
    body = None
    for sel in ("article","div.subbuzz__text","div.post-content","div[data-content-target='article-body']"):
        body = soup.select_one(sel)
        if body: break
    paras = body.find_all("p") if body else soup.find_all("p")
    text = " ".join(p.get_text(" ", strip=True) for p in paras)
    wc = len(text.split())
    # links
    il, el = count_links(soup, url)
    # scrape_date
    sd = datetime.now(timezone.utc).isoformat()
    return {
        "source": SOURCE, "url": url, "section": sec or "",
        "publication_date": pub or "", "headline": hd,
        "headline_length": hl, "word_count": wc,
        "internal_links": il, "external_links": el,
        "article_text": text, "scrape_date": sd
    }

if __name__=="__main__":
    # load existing
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            existing = {row[1] for row in csv.reader(f) if row and row[1]!="URL"}
    except FileNotFoundError:
        existing = set()

    urls = get_article_links()
    to_scrape = [u for u in urls if u not in existing]

    rows = []
    for u in to_scrape:
        info = parse_article(u)
        if info["headline_length"] and info["word_count"]:
            rows.append(info)

    write_header = not bool(existing)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        if write_header:
            w.writerow([
                "Source","URL","Section","Publication Date","Headline",
                "Headline Length","Word Count","Internal Links",
                "External Links","Article Text","Scrape Date"
            ])
        for r in rows:
            w.writerow([
                r["source"],r["url"],r["section"],r["publication_date"],
                r["headline"],r["headline_length"],r["word_count"],
                r["internal_links"],r["external_links"],
                r["article_text"],r["scrape_date"]
            ])
    print(f"Appended {len(rows)} new rows to {CSV_FILE}")
