# News Webscraper and Visualization

This project is a visualization dashboard for news articles from four major news sources: ABC News, CBS News, The Tab, and BuzzFeed. The data is stored in an Amazon Aurora PostgreSQL database hosted on AWS RDS and is sourced through web scraping.

You can run the app locally by following the steps below.

## Features

- **Visualization Dashboard**: Built using Streamlit, the dashboard provides various visualizations, including:
  - Articles over time with daily breakdowns
  - Headline length and word count analysis by source
  - Link count distributions (internal and external links)
  - Section popularity trends over time
  - Day of week publication patterns
  - Interactive filtering by source, date range, and keywords
- **Data Filtering**: Users can filter articles by source, publication date, headline keywords, and article text keywords.
- **Real-time Updates**: Dashboard refreshes data every 5 minutes from the live AWS database.

## Data Pipeline

1. **Web Scraping**: Articles are scraped from ABC News, CBS News, The Tab, and BuzzFeed using custom scrapers.
2. **Database**: The scraped data is stored in an Amazon Aurora PostgreSQL database hosted on AWS RDS.
3. **Visualization**: The data is loaded into the Streamlit app for visualization and analysis.

## Requirements

- Python 3.8+
- Required Python libraries (listed in `requirements.txt`)

## Setup (for running locally)

1. Clone the repository:
   ```bash
   git clone 
   cd legacy-new-news-scraper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   # Copy the template and fill in your AWS database credentials
   cp env_template.txt .env
   # Edit .env with your actual database credentials
   ```

4. Test database connection (optional):
   ```bash
   python scripts/test_connection.py
   ```

5. Run the Streamlit app:
   ```bash
   streamlit run article-visualization/visualization_app.py
   ```

## Folder Structure

- `article-visualization/`: Contains the Streamlit app for visualization.
- `scripts/`: Contains utility scripts for database testing and debugging.
- `data/`: Contains CSV backup files from the original scraping process.
- `legacy/`: Contains the original web scrapers for ABC News, CBS News, The Tab, and BuzzFeed.
- `requirements.txt`: Lists the required Python libraries.
- `env_template.txt`: Template for environment variables.

## Notes

- The database is hosted on Amazon Aurora PostgreSQL via AWS RDS.
- The dashboard connects to a live database with over 7,300 articles collected over the past month.
- Data refreshes automatically every 5 minutes to show the latest articles.
- All AWS database credentials are managed through environment variables for security. 