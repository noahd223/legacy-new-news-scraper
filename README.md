# News Scraper Suite

A collection of news scrapers for various news sources, now with a unified runner script.

## Available Scrapers

1. **ABC News Scraper** (`abc_news_scraper.py`) - Scrapes ABC News articles from various sections
2. **BuzzFeed Scraper** (`buzzfeed.py`) - Scrapes BuzzFeed articles using RSS feeds
3. **CBS News Scraper** (`cbs_news_scraper.py`) - Scrapes CBS News articles using Playwright
4. **The Tab Scraper** (`the_tab_scraper.py`) - Scrapes The Tab articles from various sections

## Unified Scraper Runner

The `run_all_scrapers.py` script allows you to run all scrapers (or a subset) with a single command.

### Basic Usage

```bash
# Run all scrapers
python run_all_scrapers.py

# Run only specific scrapers
python run_all_scrapers.py --scrapers abc,cbs

# Limit BuzzFeed articles per section
python run_all_scrapers.py --limit-per-section 25
```

### Command Line Options

- `--scrapers`: Comma-separated list of scrapers to run (default: `abc,buzzfeed,cbs,tab`)
- `--limit-per-section`: Limit articles per section for BuzzFeed (default: 50)

### Examples

```bash
# Run all scrapers with default settings
python run_all_scrapers.py

# Run only ABC News and CBS News
python run_all_scrapers.py --scrapers abc,cbs

# Run BuzzFeed with only 10 articles per section
python run_all_scrapers.py --scrapers buzzfeed --limit-per-section 10

# Run ABC and The Tab scrapers
python run_all_scrapers.py --scrapers abc,tab
```

### Features

- **Sequential Execution**: Scrapers run one after another to avoid overwhelming the database
- **Comprehensive Logging**: All operations are logged to both console and timestamped log files
- **Error Handling**: Individual scraper failures don't stop the entire process
- **Progress Tracking**: Shows progress for each scraper and overall completion
- **Summary Report**: Provides a detailed summary of all operations at the end

### Output

The script provides:
- Real-time progress updates
- Detailed logging to `scraper_run_YYYYMMDD_HHMMSS.log`
- Summary statistics at the end
- Exit codes (0 for success, 1 if any scraper failed)

### Requirements

Make sure you have:
1. All required dependencies installed (`requirements.txt`)
2. A PostgreSQL database set up
3. A `database.env` file with your database credentials
4. Playwright browsers installed (for CBS News scraper)

### Individual Scraper Usage

You can still run individual scrapers directly:

```bash
python abc_news_scraper.py
python buzzfeed.py
python cbs_news_scraper.py
python the_tab_scraper.py
```

### Database Schema

All scrapers use the same database schema with the following table structure:

```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(255),
    article_url TEXT UNIQUE,
    article_section VARCHAR(255),
    publication_date TIMESTAMP,
    headline_text TEXT,
    headline_word_count INTEGER,
    article_word_count INTEGER,
    scrape_date TIMESTAMP,
    num_internal_links INTEGER,
    num_external_links INTEGER,
    num_internal_links_within_body INTEGER,
    num_external_links_within_body INTEGER,
    num_images INTEGER,
    num_images_within_body INTEGER,
    article_full_text TEXT
);
```

### Environment Setup

Create a `database.env` file with your database credentials:

```
DB_NAME=your_database_name
DB_HOST=localhost
DB_USER=your_username
DB_PASSWORD=your_password
DB_PORT=5432
``` 