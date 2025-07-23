from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import time as time_module
import copy
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

SECTIONS = {
    "Politics": "https://www.cbsnews.com/politics/",
    "World": "https://www.cbsnews.com/world/",
    "U.S.": "https://www.cbsnews.com/us/",
    "Entertainment": "https://www.cbsnews.com/entertainment/",
    "Health": "https://www.cbsnews.com/health/",
    "MoneyWatch": "https://www.cbsnews.com/moneywatch/",
    "Science": "https://www.cbsnews.com/science/",
    "Sports": "https://www.cbsnews.com/sports/"
}

# regex
article_link_regex = re.compile(
    r"^https://www\.cbsnews\.com/(?:news|politics|world|us|entertainment|health|moneywatch|science|sports)/[^/]+(?:-[a-z0-9-]+)+(?:/)?$"
)

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
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

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

def random_sleep():
    """Add fixed delay to speed up the process"""
    try:
        time_module.sleep(0.75)
    except Exception as e:
        print(f"Error in random_sleep: {e}")
        pass

def get_article_links(page, url, section_name):
    try:
        # set realistic viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        # navigate to page
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        
        # wait for main content to load with shorter timeout
        print("Waiting for content to load...")
        try:
            page.wait_for_selector('main, div[class*="content"], div[class*="article"]', timeout=5000)
        except:
            print("Timeout waiting for content, proceeding anyway...")
        
        random_sleep()

        # load more content with fewer scrolls
        print("Scrolling to load more content...")
        for i in range(2): # changed from 3 to 2
            page.evaluate('window.scrollBy(0, window.innerHeight)')
            random_sleep()
            print(f"Scroll {i+1}/2 completed")

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')
        links_found = set()
        
        print("Searching for article containers...")
        # look for article links in various html containers
        article_selectors = [
            'article a[href]',
            'div[class*="article"] a[href]',
            'div[class*="story"] a[href]',
            'div[class*="item"] a[href]',
            'div[class*="card"] a[href]',
            'div[class*="content"] a[href]',
            'div[class*="feed"] a[href]',
            'div[class*="list"] a[href]'
        ]
        
        for selector in article_selectors:
            elements = soup.select(selector)
            print(f"Found {len(elements)} elements with selector: {selector}")
            for element in elements:
                href = element.get('href', '')
                if href.startswith('/'):
                    full_link = "https://www.cbsnews.com" + href
                else:
                    full_link = href
                
                # check article link
                if (article_link_regex.match(full_link) and 
                    not any(section.lower() in full_link.lower() for section in SECTIONS.keys()) and
                    not any(exclude in full_link.lower() for exclude in ['/2/', '/3/', '/4/', '/5/', '/6/', '/7/', '/8/', '/9/', '/10/']) and
                    len(full_link.split('/')) > 4):  # make sure its not just a section page
                    links_found.add((section_name, full_link))
                    print(f"Added article link: {full_link}")
        
        print(f"Found {len(links_found)} potential articles on {url}")
        return links_found
    except Exception as e:
        print(f"Error getting article links from {url}: {e}")
        return set()

def clean_article_text(soup, article_body):
    """Extract clean article text by filtering out unwanted elements"""
    if not article_body:
        return ""
    
    # clean text
    unwanted_selectors = [
        'div[class*="author"]', 'div[class*="bio"]', 'div[class*="credit"]',
        'div[class*="caption"]', 'div[class*="related"]', 'div[class*="more"]',
        'div[class*="social"]', 'div[class*="share"]', 'div[class*="footer"]',
        'div[class*="copyright"]', 'div[class*="advertisement"]',
        'aside', 'nav', 'footer', 'header',
        'div[class*="video"]', 'div[class*="embed"]',
        'div[class*="newsletter"]', 'div[class*="subscription"]'
    ]
    
    # create copy
    try:
        clean_body = copy.deepcopy(article_body)
    except Exception as e:
        print(f"Error copying article body: {e}")
        clean_body = article_body
    
    # remove unwanted
    for selector in unwanted_selectors:
        for element in clean_body.select(selector):
            element.decompose()
    
    # remove elements based on text patterns
    for element in clean_body.find_all(text=True):
        if hasattr(element, 'parent') and element.parent:
            text = element.strip()
            # remove image captions, author bios, copyright notices, etc.
            if any(pattern in text.lower() for pattern in [
                '📹', '©', 'read full bio', 'more from cbs news', 
                'updated on:', 'cbs news', 'all rights reserved',
                'contributed to this report', 'getty images', 'afp'
            ]):
                element.parent.decompose()
    
    # extract clean text
    clean_text = clean_body.get_text(separator=' ', strip=True)
    
    # clean up extra whitespace and normalize
    clean_text = re.sub(r'\s+', ' ', clean_text)
    clean_text = clean_text.strip()
    
    return clean_text

def extract_article_data(page, section, url):
    """Extract article data using the provided page"""
    try:
        print(f"  Starting to extract data from: {url}")
        
        # find article
        print(f"  Navigating to article...")
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        
        print(f"  Calling random_sleep...")
        random_sleep()
        print(f"  random_sleep completed")

        print(f"  Getting page content...")
        content = page.content()
        print(f"  Content length: {len(content)}")
        
        print(f"  Parsing with BeautifulSoup...")
        soup = BeautifulSoup(content, 'html.parser')
        print(f"  BeautifulSoup parsing completed")

        # get headline
        print(f"  Extracting headline...")
        headline = ""
        headline_selectors = [
            'h1.article__title',
            'h1.content__title',
            'h1[data-testid="article-title"]',
            'h1'
        ]
        for selector in headline_selectors:
            headline_tag = soup.select_one(selector)
            if headline_tag:
                headline = headline_tag.get_text(strip=True)
                print(f"  Found headline: {headline[:50]}...")
                break

        if not headline:
            print(f"Warning: No headline found on {url}")
            return None

        headline_length = len(headline.split())

        # get article body and extract links
        print(f"  Extracting article body...")
        body_text = ""
        full_article_text = ""
        internal_links = 0
        external_links = 0
        internal_links_within_body = 0
        external_links_within_body = 0
        num_images = 0
        num_images_within_body = 0
        
        # count all links on the entire page
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            if href.startswith('/') or href.startswith('https://www.cbsnews.com'):
                internal_links += 1
            elif href.startswith('http'):
                external_links += 1
        
        # count all images on the entire page
        all_images = soup.find_all('img')
        num_images = len(all_images)


        
        article_body = soup.select_one('article')
        print(f"  Found article body with selector: {selector}")
        # extract clean article text
        full_article_text = clean_article_text(soup, article_body)
        
        # extract paragraphs for body text
        paragraphs = article_body.find_all('p')
        body_text = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
        

        
        # count links only within paragraphs (article text)
        for p in paragraphs:
            links_in_paragraph = p.find_all('a', href=True)
            for link in links_in_paragraph:
                href = link.get('href', '')
                if href.startswith('/') or href.startswith('https://www.cbsnews.com'):
                    internal_links_within_body += 1
                elif href.startswith('http'):
                    external_links_within_body += 1
        
        
        
        # count images that are embedded in the article body
        content_images = article_body.find_all('span', class_='img embed__content')
        num_images_within_body = len(content_images)
        print(f"  Found {num_images} total images, {num_images_within_body} within body")
            

        article_word_count = len(body_text.split()) if body_text else 0

        # get pub date
        print(f"  Extracting publication date...")
        pub_date = ""
        date_selectors = [
            'time[datetime]',
            'time.article__date',
            'span.article__date',
            'div.article__date'
        ]
        for selector in date_selectors:
            date_element = soup.select_one(selector)
            if date_element:
                if date_element.name == 'time':
                    pub_date = date_element.get('datetime', '')
                else:
                    pub_date = date_element.get_text(strip=True)
                print(f"  Found publication date: {pub_date}")
                break

        # Parse publication date
        try:
            if pub_date:
                # Try to parse ISO format first
                if 'T' in pub_date:
                    pub_date_parsed = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                else:
                    # Try common date formats
                    pub_date_parsed = datetime.now()  # fallback
            else:
                pub_date_parsed = datetime.now()
        except:
            pub_date_parsed = datetime.now()

        print(f"  Article extraction completed successfully")
        
        # Return data in the order expected by the database schema
        return (
            "CBS News",                    # source_name
            url,                          # article_url
            section,                      # article_section
            pub_date_parsed,              # publication_date
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
            full_article_text             # article_full_text
        )
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_browser_context(playwright):
    """Create a new browser context with optimized settings"""
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security',
            '--disable-site-isolation-trials',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-images',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding'
        ]
    )
    
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        locale='en-US',
        timezone_id='America/New_York',
        geolocation={'latitude': 40.7128, 'longitude': -74.0060},
        permissions=['geolocation']
    )
    
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    return browser, context, page

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

    with sync_playwright() as p:
        # launch browser with optimized settings for speed
        browser, context, page = create_browser_context(p)
        
        all_links = set()
        for section, url in SECTIONS.items():
            print(f"Scraping {section} section...")
            section_links = get_article_links(page, url, section)
            print(f"Found {len(section_links)} articles in {section}")
            all_links.update(section_links)
            print(f"Finished scraping {section} section.\n")
            random_sleep()

        # Filter out links that are already in the database
        new_links = [(section, article_url) for (section, article_url) in all_links if article_url not in existing_urls]
        total = len(new_links)
        print(f"Total new articles to process: {total}")

        successful_inserts = 0
        failed_inserts = 0
        
        for i, (section, article_url) in enumerate(new_links, start=1):
            try:
                print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
                
                data = extract_article_data(page, section, article_url)
                if data:
                    if insert_article_data(connection, data):
                        successful_inserts += 1
                        print(f"✅ Successfully inserted article: {data[4][:50]}...")  # Show first 50 chars of headline
                    else:
                        failed_inserts += 1
                        print(f"❌ Failed to insert article: {article_url}")
                else:
                    failed_inserts += 1
                    print(f"❌ Failed to scrape article: {article_url}")
            except Exception as e:
                failed_inserts += 1
                print(f"❌ Error processing article {article_url}: {e}")
            
            # add delay between articles
            if i < total:  # don't sleep after last article
                random_sleep()
        
        print(f"\n📊 Scraping Summary:")
        print(f"✅ Successfully inserted: {successful_inserts} articles")
        print(f"❌ Failed: {failed_inserts} articles")
        print(f"📈 Success rate: {(successful_inserts/total)*100:.1f}%" if total > 0 else "📈 No new articles to process")
        
        browser.close()
    
    # Close database connection
    connection.close()
    print("Database connection closed.") 