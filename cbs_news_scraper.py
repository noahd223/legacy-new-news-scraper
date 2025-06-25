from bs4 import BeautifulSoup
import csv
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import time as time_module
import copy

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
        
        body_selectors = [
            'div.article__body',
            'div.content__body',
            'div[data-testid="article-body"]',
            'article'
        ]
        
        for selector in body_selectors:
            article_body = soup.select_one(selector)
            if article_body:
                print(f"  Found article body with selector: {selector}")
                # extract clean article text
                full_article_text = clean_article_text(soup, article_body)
                
                # extract paragraphs for body text
                paragraphs = article_body.find_all('p')
                body_text = ' '.join(p.get_text().strip() for p in paragraphs if p.get_text().strip())
                
                # ccount internal and external links
                all_links = article_body.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '')
                    if href.startswith('/') or href.startswith('https://www.cbsnews.com'):
                        internal_links += 1
                    elif href.startswith('http'):
                        external_links += 1
                break

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

        print(f"  Article extraction completed successfully")
        return [
            "CBS News",
            url,
            section,
            pub_date,
            headline,
            headline_length,
            article_word_count,
            internal_links,
            external_links,
            full_article_text,
            datetime.now().isoformat()
        ]
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

        all_links_list = list(all_links)
        total = len(all_links_list)
        print(f"Total articles found: {total}")

        with open("cbs_article_links.csv", 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([
                'Source', 'Article URL', 'Article Section', 'Publication Date',
                'Headline (Text)', 'Headline Length', 'Article Word Count', 'Internal Links',
                'External Links', 'Full Article Text', 'Scrape Date'
            ])
            
            successful_scrapes = 0
            failed_scrapes = 0
            
            for i, (section, article_url) in enumerate(all_links_list, start=1):
                try:
                    print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
                    
                    data = extract_article_data(page, section, article_url)
                    if data:
                        csv_writer.writerow(data)
                        successful_scrapes += 1
                        print(f"✅ Successfully scraped article: {data[4]}")  # print headlines so its easier to see in terminal
                    else:
                        failed_scrapes += 1
                        print(f"❌ Failed to scrape article: {article_url}") # print headlines so its easier to see in terminal
                except Exception as e:
                    failed_scrapes += 1
                    print(f"❌ Error processing article {article_url}: {e}") # print headlines so its easier to see in terminal
                
                # add delay between articles
                if i < total:  # don't sleep after last article
                    random_sleep()
            
            print(f"\n📊 Scraping Summary:")
            print(f"✅ Successful scrapes: {successful_scrapes}")
            print(f"❌ Failed scrapes: {failed_scrapes}")
            print(f"📈 Success rate: {(successful_scrapes/total)*100:.1f}%")
        
        browser.close() 