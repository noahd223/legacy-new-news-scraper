from bs4 import BeautifulSoup, SoupStrainer
import requests
import csv
import re
from datetime import datetime
from urllib.parse import urlparse

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
        
        # Domain set for internal link checking
        main_domain = "abcnews.go.com"

        # Iterate over all 'a' tags within the article body (paragraphs)
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


        return [
            "ABC News",
            url,
            section,
            pub_date,
            headline,
            headline_length,
            article_word_count,
            internal_links,
            external_links,
            datetime.now().isoformat(),
            body_text 
        ]
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

if __name__ == "__main__":
    all_links = set()
    for section, url in SECTIONS.items():
        print(f"Scraping {section} section...")
        all_links.update(get_article_links(url, section))
        print(f"Finished scraping {section} section.\n")

    all_links_list = list(all_links)
    total = len(all_links_list)

    with open("abcnews_article_links.csv", 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow([
            'Source', 'Article URL', 'Article Section', 'Publication Date',
            'Headline (Text)', 'Headline Length', 'Article Word Count',
            'Number of Internal Links', 'Number of External Links', 'Scrape Date',
            'Article Body Text'
        ])
        for i, (section, article_url) in enumerate(all_links_list, start=1):
            print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
            data = extract_article_data(section, article_url)
            if data:
                csv_writer.writerow(data)
