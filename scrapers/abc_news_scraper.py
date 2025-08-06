from bs4 import BeautifulSoup, SoupStrainer
import requests
import csv
import re
from datetime import datetime

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
        meta_pub = soup.find('meta', {'property': 'article:published_time'})
        if meta_pub and meta_pub.has_attr('content'):
            pub_date = meta_pub['content']

        return [
            "ABC News",
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
            'Headline (Text)', 'Headline Length', 'Article Word Count', 'Scrape Date'
        ])
        for i, (section, article_url) in enumerate(all_links_list, start=1):
            print(f"[{i}/{total}] Scraping article from section '{section}': {article_url}")
            data = extract_article_data(section, article_url)
            if data:
                csv_writer.writerow(data)
