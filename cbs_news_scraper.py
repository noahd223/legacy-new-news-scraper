from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import time
import random

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
    r"^https://www\.cbsnews\.com/(?:news|politics|world|us|entertainment|health|moneywatch|science|sports)/[^/]+(?:-[a-z0-9-]+)?(?:/)?$"
)

def random_sleep():
    """Add random delay to mimic human behavior"""
    time.sleep(random.uniform(1, 2))

def get_article_links(page, url, section_name):
    try:
        # set realistic viewport
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Navigate to the page with a more reliable wait strategy
        print(f"Navigating to {url}...")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        
        # wait for main content to load
        print("Waiting for content to load...")
        page.wait_for_selector('main, div[class*="content"], div[class*="article"]', timeout=10000)
        random_sleep()

        # load more content
        print("Scrolling to load more content...")
        for i in range(3):
            page.evaluate('window.scrollBy(0, window.innerHeight)')
            random_sleep()
            print(f"Scroll {i+1}/3 completed")

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
                
                print(f"Found link: {full_link}")
                
                # check article link
                if (article_link_regex.match(full_link) and 
                    not any(section.lower() in full_link.lower() for section in SECTIONS.keys())):
                    links_found.add((section_name, full_link))
                    print(f"Added article link: {full_link}")
                else:
                    print(f"Link did not match pattern: {full_link}")
        
        print(f"Found {len(links_found)} potential articles on {url}")
        return links_found
    except Exception as e:
        print(f"Error getting article links from {url}: {e}")
        return set()

def extract_article_data(page, section, url):
    try:
        # find article
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        random_sleep()

        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')

        # get headline
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
                break

        if not headline:
            print(f"Warning: No headline found on {url}")
            return None

        headline_length = len(headline.split())

        # get article body
        body_text = ""
        body_selectors = [
            'div.article__body',
            'div.content__body',
            'div[data-testid="article-body"]',
            'article'
        ]
        for selector in body_selectors:
            article_body = soup.select_one(selector)
            if article_body:
                paragraphs = article_body.find_all('p')
                body_text = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                break

        article_word_count = len(body_text.split()) if body_text else 0

        # get pub date
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
                break

        return [
            "CBS News",
            url,
            section,
            pub_date,
            headline,
            headline_length,
            article_word_count,
            datetime.now().isoformat()
        ]
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

if __name__ == "__main__":
    with sync_playwright() as p:
        # launch browsre
        browser = p.chromium.launch(
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
                '--disable-gpu'
            ]
        )
        
        # create new context
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
        
        all_links = set()
        for section, url in SECTIONS.items():
            print(f"Scraping {section} section...")
            section_links = get_article_links(page, url, section)
            print(f"Found {len(section_links)} articles in {section}")
            all_links.update(section_links)
            print(f"Finished scraping {section} section.\n")
            random_sleep()

        all_links_list = list(all_links)
        total = len(all_links_list)
        print(f"Total articles found: {total}")

        with open("cbs_article_links.csv", 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([
                'Source', 'Article URL', 'Article Section', 'Publication Date',
                'Headline (Text)', 'Headline Length', 'Article Word Count', 'Scrape Date'
            ])
            for i, (section, article_url) in enumerate(all_links_list, start=1):
                print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
                data = extract_article_data(page, section, article_url)
                if data:
                    csv_writer.writerow(data)
                    print(f"Successfully scraped article: {data[4]}")  # Print headline for successful scrapes
                random_sleep()
        
        browser.close() 