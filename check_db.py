import os
import psycopg2
from psycopg2 import Error
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

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

def check_database_stats(connection):
    """Check overall database statistics."""
    try:
        cursor = connection.cursor()
        
        # Total number of articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        # Articles by source
        cursor.execute("""
            SELECT source_name, COUNT(*) as count 
            FROM articles 
            GROUP BY source_name 
            ORDER BY count DESC
        """)
        articles_by_source = cursor.fetchall()
        
        # Articles by section
        cursor.execute("""
            SELECT article_section, COUNT(*) as count 
            FROM articles 
            GROUP BY article_section 
            ORDER BY count DESC
        """)
        articles_by_section = cursor.fetchall()
        
        # Date range of scraped articles
        cursor.execute("""
            SELECT 
                MIN(scrape_date) as earliest_scrape,
                MAX(scrape_date) as latest_scrape
            FROM articles
        """)
        date_range = cursor.fetchone()
        
        cursor.close()
        
        print("=" * 60)
        print("DATABASE STATISTICS")
        print("=" * 60)
        print(f"Total Articles: {total_articles}")
        print(f"Date Range: {date_range[0]} to {date_range[1]}")
        
        print("\nArticles by Source:")
        for source, count in articles_by_source:
            print(f"  {source}: {count}")
        
        print("\nArticles by Section:")
        for section, count in articles_by_section:
            print(f"  {section}: {count}")
        
        return True
        
    except Error as e:
        print(f"ERROR: Failed to get database stats: {e}")
        return False

def get_most_recent_scrapes(connection, limit=10):
    """Get the most recently scraped articles."""
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                source_name,
                article_section,
                headline_text,
                article_url,
                scrape_date,
                publication_date,
                article_word_count
            FROM articles 
            ORDER BY scrape_date DESC 
            LIMIT %s
        """, (limit,))
        
        recent_articles = cursor.fetchall()
        cursor.close()
        
        print("\n" + "=" * 60)
        print(f"MOST RECENTLY SCRAPED ARTICLES (Last {limit})")
        print("=" * 60)
        
        for i, article in enumerate(recent_articles, 1):
            source, section, headline, url, scrape_date, pub_date, word_count = article
            
            print(f"\n{i}. {headline[:80]}...")
            print(f"   Source: {source} | Section: {section}")
            print(f"   URL: {url}")
            print(f"   Scraped: {scrape_date}")
            if pub_date:
                print(f"   Published: {pub_date}")
            print(f"   Word Count: {word_count}")
        
        return recent_articles
        
    except Error as e:
        print(f"ERROR: Failed to get recent scrapes: {e}")
        return []

def get_recent_scrapes_by_source(connection, source_name, limit=5):
    """Get the most recent scrapes for a specific source."""
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                article_section,
                headline_text,
                article_url,
                scrape_date,
                publication_date,
                article_word_count
            FROM articles 
            WHERE source_name = %s
            ORDER BY scrape_date DESC 
            LIMIT %s
        """, (source_name, limit))
        
        recent_articles = cursor.fetchall()
        cursor.close()
        
        print(f"\n" + "=" * 60)
        print(f"MOST RECENT SCRAPES FOR {source_name.upper()} (Last {limit})")
        print("=" * 60)
        
        for i, article in enumerate(recent_articles, 1):
            section, headline, url, scrape_date, pub_date, word_count = article
            
            print(f"\n{i}. {headline[:80]}...")
            print(f"   Section: {section}")
            print(f"   URL: {url}")
            print(f"   Scraped: {scrape_date}")
            if pub_date:
                print(f"   Published: {pub_date}")
            print(f"   Word Count: {word_count}")
        
        return recent_articles
        
    except Error as e:
        print(f"ERROR: Failed to get recent scrapes for {source_name}: {e}")
        return []

def check_scraping_frequency(connection, days=7):
    """Check scraping frequency over the last N days."""
    try:
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                DATE(scrape_date) as scrape_day,
                source_name,
                COUNT(*) as articles_scraped
            FROM articles 
            WHERE scrape_date >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(scrape_date), source_name
            ORDER BY scrape_day DESC, articles_scraped DESC
        """, (days,))
        
        frequency_data = cursor.fetchall()
        cursor.close()
        
        print(f"\n" + "=" * 60)
        print(f"SCRAPING FREQUENCY (Last {days} days)")
        print("=" * 60)
        
        if not frequency_data:
            print(f"No scraping activity in the last {days} days.")
            return
        
        current_day = None
        for scrape_day, source, count in frequency_data:
            if scrape_day != current_day:
                print(f"\n{scrape_day}:")
                current_day = scrape_day
            print(f"  {source}: {count} articles")
        
        return frequency_data
        
    except Error as e:
        print(f"ERROR: Failed to get scraping frequency: {e}")
        return []

def main():
    """Main function to run all database checks."""
    print("Connecting to database...")
    db_connection = get_db_connection()
    
    if not db_connection:
        print("ERROR: Database connection failed. Exiting.")
        return
    
    try:
        # Check overall database statistics
        check_database_stats(db_connection)
        
        # Get most recent scrapes
        get_most_recent_scrapes(db_connection, limit=10)
        
        # Check scraping frequency for last 7 days
        check_scraping_frequency(db_connection, days=7)
        
        # Get recent scrapes for specific sources (if they exist)
        sources = ["The Tab", "ABC News", "CBS News", "BuzzFeed"]
        for source in sources:
            get_recent_scrapes_by_source(db_connection, source, limit=3)
        
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
    
    finally:
        # Close database connection
        db_connection.close()
        print("\nDatabase connection closed.")

if __name__ == "__main__":
    main() 