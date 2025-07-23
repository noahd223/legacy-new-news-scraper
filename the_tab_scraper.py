import os
import requests as re
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urlparse
import psycopg2
from psycopg2 import Error
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')


SOURCE = "The Tab"
BASE_URL = "https://thetab.com"
DOMAIN = urlparse(BASE_URL).netloc
SECTIONS = ["news", "entertainment", "trends", "gaming", "politics", "opinion", "guides"]

# Database configuration
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Create and return a database connection."""
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
        print(f"ERROR: Unable to connect to the PostgreSQL RDS DB: {e}")
        return None

def insert_article_to_db(connection, article_data):
    """Insert an article into the database."""
    try:
        cursor = connection.cursor()
        
        # Convert publication date string to timestamp if it exists
        pub_date = None
        if article_data['pub_date']:
            try:
                pub_date = datetime.fromisoformat(article_data['pub_date'].replace('Z', '+00:00'))
            except:
                pass
        
        # Convert scrape date string to timestamp
        scrape_date = datetime.fromisoformat(article_data['scrape_date'].replace('Z', '+00:00'))
        
        insert_sql = """
        INSERT INTO articles (
            source_name, article_url, article_section, publication_date,
            headline_text, headline_word_count, article_word_count, scrape_date,
            num_internal_links, num_external_links, num_internal_links_within_body,
            num_external_links_within_body, num_images, num_images_within_body, article_full_text
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (article_url) DO NOTHING
        """
        
        cursor.execute(insert_sql, (
            article_data['source'],
            article_data['url'],
            article_data['section'],
            pub_date,
            article_data['headline'],
            article_data['headline_len'],
            article_data['word_count'],
            scrape_date,
            article_data['internal_links'],
            article_data['external_links'],
            article_data['internal_links_within_body'],
            article_data['external_links_within_body'],
            article_data['num_images'],
            article_data['num_images_within_body'],
            article_data['article_text']
        ))
        
        connection.commit()
        cursor.close()
        return True
        
    except Error as e:
        print(f"ERROR: Failed to insert article {article_data['url']}: {e}")
        connection.rollback()
        return False

def check_url_exists_in_db(connection, url):
    """Check if an article URL already exists in the database."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM articles WHERE article_url = %s", (url,))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    except Error as e:
        print(f"ERROR: Failed to check URL existence: {e}")
        return False

db_connection = get_db_connection()
if not db_connection:
    print("ERROR: Database connection failed. Exiting.")
    exit(1)


for section in SECTIONS:
    section_url = f"{BASE_URL}/{section}"
    try:
        print(f"Scraping section: {section_url}")
        res = re.get(section_url, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")

        links = soup.select("a[href*='/202']")  # Find all 202x article links

        for link in links:
            article_url = link["href"]
            if not article_url.startswith("http"):
                article_url = BASE_URL + article_url

            # Check if URL exists in database
            if check_url_exists_in_db(db_connection, article_url):
                continue

            try:
                art_res = re.get(article_url, timeout=10)
                art_soup = BeautifulSoup(art_res.content, "html.parser")

                headline_tag = art_soup.find("h1")
                headline = headline_tag.get_text(strip=True) if headline_tag else None
                if not headline:
                    continue

                paragraphs = art_soup.find_all("p")
                article_text = " ".join(p.get_text(strip=True) for p in paragraphs)
                word_count = len(article_text.split())
                article_body = art_soup.find("div", class_="article__text")
                # Count internal and external links
                all_links = art_soup.find_all("a", href=True)
                internal_links = 0
                external_links = 0

                num_images = len(art_soup.find_all("img"))
                # Find images where the 'class' attribute exists and contains any class starting with 'wp-image-'
                # these are images embedded in the article text
                wp_images = art_soup.find_all('img', class_=lambda x: x and any(c.startswith('wp-image-') for c in x.split()))
                num_images_within_body = len(wp_images)

                internal_links_within_body = 0
                external_links_within_body = 0
                body_links = []
                for p in article_body.find_all("p"):
                    body_links.extend(p.find_all("a", href=True))

                # count links within body (article text)
                for a in body_links:
                    href = a['href']
                    parsed_href = urlparse(href)
                    if parsed_href.netloc == "" or DOMAIN in parsed_href.netloc:
                        internal_links_within_body += 1
                    else:
                        external_links_within_body += 1
                # count total links on the page
                for a in all_links:
                    href = a['href']
                    parsed_href = urlparse(href)
                    if parsed_href.netloc == "" or DOMAIN in parsed_href.netloc:
                        internal_links += 1
                    else:
                        external_links += 1
                
                meta_date = art_soup.find("meta", {"property": "article:published_time"})
                pub_date = meta_date["content"] if meta_date else None

                article_data = {
                    "source": SOURCE,
                    "url": article_url,
                    "section": section,
                    "pub_date": pub_date,
                    "headline": headline,
                    "headline_len": len(headline.split()),
                    "word_count": word_count,
                    "internal_links": internal_links,
                    "external_links": external_links,
                    "num_images": num_images,
                    "num_images_within_body": num_images_within_body,
                    "internal_links_within_body": internal_links_within_body,
                    "external_links_within_body": external_links_within_body,
                    "article_text": article_text,
                    "scrape_date": datetime.now().isoformat()
                }

                # Insert into database
                if insert_article_to_db(db_connection, article_data):
                    print(f"SUCCESS: Inserted article into database: {headline[:50]}...")
                    
                else:
                    print(f"FAILED: Could not insert article into database: {headline[:50]}...")

            except Exception as e:
                print(f"Error parsing article: {article_url} | {e}")

    except Exception as e:
        print(f"Failed to fetch section {section_url} | {e}")

# Close database connection
db_connection.close()
print("Database connection closed.")
print("Scraping complete.")
