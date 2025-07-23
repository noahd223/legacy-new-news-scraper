from bs4 import BeautifulSoup, SoupStrainer
import requests
import re
from datetime import datetime
from urllib.parse import urlparse
import psycopg2
from psycopg2 import Error
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Database connection details
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "5432")
print(DB_NAME, DB_HOST, DB_USER, DB_PASSWORD, DB_PORT)

SECTIONS = {
    "Politics": "https://abcnews.go.com/Politics",
    "World": "https://abcnews.go.com/International",
    "US": "https://abcnews.go.com/US",
    "Technology": "https://abcnews.go.com/Technology",
    "Health": "https://abcnews.go.com/Health",
    "Sports": "https://abcnews.go.com/Sports",
    "Entertainment": "https://abcnews.go.com/Entertainment",
    "Business": "https://abcnews.go.com/Business",
    "Lifestyle": "https://abcnews.go.com/Lifestyle",
}

article_link_regex = re.compile(
    r"^(?!.*(?:/video/|/photos/|/Live|/Shop|#|hulu\.com|disneyprivacycenter\.com|disneytermsofuse\.com|nielsen\.com|/contact)).*\/story(?:\?id=.*)?$|.*\/wireStory\/.*|.*\/thought\/.*|.*\/made-america\/.*"
)

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
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

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
        print(f"Error inserting article data: {e}")
        connection.rollback()
        return False

def get_existing_article_urls(connection):
    """Fetch all article URLs currently in the database."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT article_url FROM articles;")
        rows = cursor.fetchall()
        return set(row[0] for row in rows)
    except Error as e:
        print(f"Error fetching existing article URLs: {e}")
        return set()

def get_article_links(url, section_name):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve page: {response.status_code}")
        return set()
    links_found = set()
    for link_tag in BeautifulSoup(response.content, 'html.parser', parse_only=SoupStrainer('a')):
        if link_tag.has_attr('href'):
            href = link_tag['href']
            if href.startswith('/'):
                full_link = "https://abcnews.go.com" + href
            elif href.startswith('./'):
                full_link = url + href[1:]
            else:
                full_link = href
            if article_link_regex.match(full_link):
                links_found.add((section_name, full_link))
    return links_found

def extract_article_data(section, url):
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.content, 'html.parser')

        headline_tag = soup.find('h1')
        headline = headline_tag.get_text(strip=True) if headline_tag else ""
        headline_length = len(headline.split())

        paragraphs = soup.find_all('p')
        body_text = ' '.join(p.get_text() for p in paragraphs)
        article_word_count = len(body_text.split())

        pub_date = ""
        pub_element = soup.find('div', {'class': 'jTKbV zIIsP ZdbeE xAPpq QtiLO JQYD'})
        pub_text = pub_element.get_text(strip=True) if pub_element else ""
        pub_date = datetime.strptime(pub_text, "%B %d, %Y, %I:%M %p")

        # Links
        internal_links = 0
        external_links = 0
        internal_links_within_body = 0
        external_links_within_body = 0
        num_images = 0
        num_images_within_body = 0
        
        # Domain set for internal link checking
        main_domain = "abcnews.go.com"

        # Find article body container
        article_body = soup.find('div', class_='theme-e FITT_Article_main__body oBTii mrzah')
        
        # Count all links in the article body
        all_links = article_body.find_all('a', href=True)
        for link in all_links:
            href = link['href']
            
            if href.startswith('//'): 
                full_href = "https:" + href
            elif href.startswith('/'): # Absolute path relative to domain
                full_href = "https://" + main_domain + href
            elif not (href.startswith('http://') or href.startswith('https://')): # Relative path or other schemes
                # Handle relative paths based on current URL (less common in article body links)
                # Or skip non-http/s links if not relevant (e.g., mailto:, tel:)
                if url.endswith('/'): # If current URL ends with /, append directly
                    full_href = url + href
                else: # If current URL doesn't end with /, assume last segment is file, go up one level
                    full_href = url[:url.rfind('/') + 1] + href
            else: # Already a full http/s URL
                full_href = href

            parsed_link = urlparse(full_href)

            if parsed_link.netloc == main_domain:
                internal_links += 1
            elif parsed_link.netloc and parsed_link.scheme in ['http', 'https']: # Ensure it has a domain and is http/s
                external_links += 1

        # Count links only within paragraphs (article text)
        links_to_check = []
        for p in paragraphs:
            links_to_check.extend(p.find_all('a', href=True))

        for link in links_to_check:
            href = link['href']
            
            if href.startswith('//'): 
                full_href = "https:" + href
            elif href.startswith('/'): # Absolute path relative to domain
                full_href = "https://" + main_domain + href
            elif not (href.startswith('http://') or href.startswith('https://')): # Relative path or other schemes
                if url.endswith('/'): # If current URL ends with /, append directly
                    full_href = url + href
                else: # If current URL doesn't end with /, assume last segment is file, go up one level
                    full_href = url[:url.rfind('/') + 1] + href
            else: # Already a full http/s URL
                full_href = href

            parsed_link = urlparse(full_href)

            if parsed_link.netloc == main_domain:
                internal_links_within_body += 1
            elif parsed_link.netloc and parsed_link.scheme in ['http', 'https']: # Ensure it has a domain and is http/s
                external_links_within_body += 1

        # Count all images on the entire page
        all_images = soup.find_all('img')
        num_images = len(all_images)
        
        # Count images within the article body only using picture tags
        body_images = article_body.find_all('picture') if article_body else []
        num_images_within_body = len(body_images)
        print(f"Found {num_images} total images on page, {num_images_within_body} within article body")

        # Return data in the order expected by the database schema
        return (
            "ABC News",                    # source_name
            url,                          # article_url
            section,                      # article_section
            pub_date,                     # publication_date
            headline,                     # headline_text
            headline_length,              # headline_word_count
            article_word_count,           # article_word_count
            datetime.now(),               # scrape_date
            internal_links,               # num_internal_links
            external_links,               # num_external_links
            internal_links_within_body,   # num_internal_links_within_body
            external_links_within_body,   # num_external_links_within_body
            num_images,                   # num_images
            num_images_within_body,       # num_images_within_body
            body_text                     # article_full_text
        )
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

if __name__ == "__main__":
    # Connect to database
    connection = connect_to_database()
    if not connection:
        print("Failed to connect to database. Exiting.")
        exit(1)

    print("Connected to PostgreSQL database successfully!")
    
    # Fetch existing article URLs
    existing_urls = get_existing_article_urls(connection)
    print(f"Found {len(existing_urls)} existing articles in the database.")

    all_links = set()
    for section, url in SECTIONS.items():
        print(f"Scraping {section} section...")
        all_links.update(get_article_links(url, section))
        print(f"Finished scraping {section} section.\n")

    # Filter out links that are already in the database
    new_links = [(section, article_url) for (section, article_url) in all_links if article_url not in existing_urls]
    total = len(new_links)
    print(f"{total} new articles to scrape and insert.")
    successful_inserts = 0
    failed_inserts = 0

    for i, (section, article_url) in enumerate(new_links, start=1):
        print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
        data = extract_article_data(section, article_url)
        if data:
            if insert_article_data(connection, data):
                successful_inserts += 1
                print(f"Successfully inserted article: {data[4][:50]}...")  # Show first 50 chars of headline
            else:
                failed_inserts += 1
                print(f"Failed to insert article: {article_url}")
        else:
            failed_inserts += 1
            print(f"Failed to scrape article: {article_url}")

    # Close database connection
    connection.close()
    print(f"\nScraping completed!")
    print(f"Successfully inserted: {successful_inserts} articles")
    print(f"Failed: {failed_inserts} articles")
    print(f"Total processed: {total} new articles")
