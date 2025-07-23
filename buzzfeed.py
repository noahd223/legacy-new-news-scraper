#!/usr/bin/env python3
from __future__ import annotations
import time
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
import feedparser
from bs4 import BeautifulSoup
from tqdm import tqdm
import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ——— CONFIG ——————————————————————————————————————————————
# Database connection details
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "5432")

SECTIONS = {
    "news":          "https://www.buzzfeed.com/in-the-news",
    "entertainment": "https://www.buzzfeed.com/entertainment/",
    "tasty":         "https://www.buzzfeed.com/tasty/",
    "shopping":      "https://www.buzzfeed.com/shopping/",
    "travel":        "https://www.buzzfeed.com/travel/",
    "food":          "https://www.buzzfeed.com/food/",
    "music":         "https://www.buzzfeed.com/music/",
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



# ——— DATABASE FUNCTIONS ——————————————————————————————————
def connect_to_database():
    """Establish connection to the PostgreSQL database."""
    try:
        connection = psycopg2.connect(
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return connection
    except Error as e:
        logging.error(f"Error connecting to PostgreSQL database: {e}")
        return None

def get_existing_article_urls(connection):
    """Fetch all article URLs currently in the database."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT article_url FROM articles;")
        rows = cursor.fetchall()
        return set(row[0] for row in rows)
    except Error as e:
        logging.error(f"Error fetching existing article URLs: {e}")
        return set()

def insert_article_data(connection, article_data):
    """Insert article data into the PostgreSQL database."""
    try:
        cursor = connection.cursor()
        insert_sql = """
        INSERT INTO articles (
            source_name, article_url, article_section, publication_date,
            headline_text, headline_word_count, article_word_count,
            scrape_date, num_internal_links, num_external_links,
            num_internal_links_within_body, num_external_links_within_body,
            num_images, num_images_within_body, article_full_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (article_url) DO NOTHING;
        """
        cursor.execute(insert_sql, article_data)
        connection.commit()
        return True
    except Error as e:
        logging.error(f"Error inserting article data: {e}")
        connection.rollback()
        return False



# ——— HELPERS —————————————————————————————————————————————
def get_section_links(section_url: str, label: str) -> list[str]:
    """Get article links from RSS feed for a given section."""
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
        else:
            logging.warning("No RSS links found for %s", label)
            return []
    except Exception as e:
        logging.warning("RSS failed for %s: %s", label, e)
        return []

def get_soup(url: str) -> BeautifulSoup:
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def count_links(soup: BeautifulSoup, article_url: str) -> tuple[int,int,int,int]:
    """Count internal vs external <a> links in the article content and within body text."""
    
    main_domain = "buzzfeed.com"
    
    def is_internal_link(href: str) -> bool:
        if not href:
            return False
        parsed_href = urlparse(href)
        return parsed_href.netloc == "" or main_domain in parsed_href.netloc

    # Count all links on the page
    all_links = soup.find_all("a", href=True)
    internal = 0
    external = 0
    
    for a in all_links:
        href = a['href']
        if is_internal_link(href):
            internal += 1
        else:
            external += 1

    # Count links within article body - look for links within subbuzz elements
    # which contain the actual article content
    subbuzzes = soup.select(".subbuzz")
    
    internal_within_body = 0
    external_within_body = 0
    
    for subbuzz in subbuzzes:
        # Find all links within this subbuzz element
        links = subbuzz.find_all("a", href=True)
        for link in links:
            href = link['href']
            if is_internal_link(href):
                internal_within_body += 1
            else:
                #print("External link: ", href)
                external_within_body += 1

    return internal, external, internal_within_body, external_within_body

# ——— PARSER —————————————————————————————————————————————
def parse_article(url: str, section: str) -> tuple:
    soup = get_soup(url)

    # Publication Date
    pub = soup.find("meta", {"property": "article:published_time"})
    pub_date_str = pub["content"].strip() if (pub and pub.get("content")) else ""
    
    # Parse publication date
    try:
        if pub_date_str:
            pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00'))
        else:
            pub_date = datetime.now()
    except:
        pub_date = datetime.now()

    # Headline
    h1 = soup.find("h1")
    headline = h1.get_text(strip=True) if h1 else ""
    hl_len = len(headline.split())

    # Body & word count - BuzzFeed uses subbuzz structure
    text_parts = []
    
    # Look for subbuzz elements which contain the article content
    subbuzzes = soup.select(".subbuzz")
    
    for subbuzz in subbuzzes:
        # Get the header/title text from subbuzz elements
        header = subbuzz.select_one("h2.subbuzz__title, .js-subbuzz__title-text")
        if header:
            header_text = header.get_text(strip=True)
            if header_text:
                text_parts.append(header_text)
        
        # Get text from subbuzz descriptions (main article text)
        descriptions = subbuzz.select(".subbuzz__description")
        for desc in descriptions:
            desc_text = desc.get_text(strip=True)
            if desc_text:
                text_parts.append(desc_text)
        
        # Get text from paragraphs within subbuzz elements (for text-only subbuzzes)
        paragraphs = subbuzz.select("p")
        for p in paragraphs:
            # Skip if this paragraph is already counted in descriptions
            if p.find_parent(".subbuzz__description"):
                continue
            p_text = p.get_text(strip=True)
            if p_text:
                text_parts.append(p_text)
    
    
    # Join all text parts
    text = " ".join(text_parts)
    wc = len(text.split())

    # Link counts
    il, el, il_body, el_body = count_links(soup, url)

    # Image counts - count unique image sources
    all_img_elements = soup.find_all("img")
    unique_image_sources = set()
    for img in all_img_elements:
        src = img.get("src", "")
        if src:
            unique_image_sources.add(src)
    all_images = len(unique_image_sources)
    
    # Count images within article body - look for images within subbuzz elements
    # which contain the actual article content
    articles = soup.select("article")
    num_images_within_body = 0
    if articles:
        article_img_elements = articles[0].find_all("img")
        unique_article_image_sources = set()
        for img in article_img_elements:
            src = img.get("src", "")
            if src:
                unique_article_image_sources.add(src)
        num_images_within_body = len(unique_article_image_sources)

    
    sd = datetime.now()

    # Return data in the order expected by the database schema
    return (
        "BuzzFeed",                    # source_name
        url,                          # article_url
        section,                      # article_section
        pub_date,                     # publication_date
        headline,                     # headline_text
        hl_len,                       # headline_word_count
        wc,                           # article_word_count
        sd,                           # scrape_date
        il,                           # num_internal_links
        el,                           # num_external_links
        il_body,                      # num_internal_links_within_body
        el_body,                      # num_external_links_within_body
        all_images,                   # num_images
        num_images_within_body,       # num_images_within_body
        text                          # article_full_text
    )

# ——— MAIN ———————————————————————————————————————————————
def main():
    # Connect to database
    connection = connect_to_database()
    if not connection:
        logging.error("Failed to connect to database. Exiting.")
        exit(1)

    logging.info("Connected to PostgreSQL database successfully!")
    
    # Fetch existing article URLs
    existing_urls = get_existing_article_urls(connection)
    logging.info(f"Found {len(existing_urls)} existing articles in the database.")

    successful_inserts = 0
    failed_inserts = 0
    skipped_articles = 0

    for label, sec_url in SECTIONS.items():
        urls = get_section_links(sec_url, label)

        # Filter out URLs that are already in the database
        new_urls = [u for u in urls if u not in existing_urls]
        logging.info(f"Section '{label}': {len(new_urls)} new articles to process out of {len(urls)} total")

        for u in tqdm(new_urls, desc=label, unit="url"):
            try:
                article_data = parse_article(u, label)
                if insert_article_data(connection, article_data):
                    successful_inserts += 1
                    logging.info(f"Successfully inserted: {article_data[4][:50]}...")  # Show first 50 chars of headline
                else:
                    failed_inserts += 1
                    logging.warning(f"Failed to insert article: {u}")
            except Exception as ex:
                failed_inserts += 1
                logging.warning("parse failed %s: %s", u, ex)
            time.sleep(0.5)

    # Close database connection
    connection.close()
    
    logging.info("Done – successfully inserted %d articles, failed %d articles", successful_inserts, failed_inserts)

if __name__ == "__main__":
    main()
