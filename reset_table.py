import psycopg2
from psycopg2 import Error


DB_NAME = "postgres"
DB_HOST = "del-article-data.cg36wwi2cch3.us-east-1.rds.amazonaws.com"

DB_USER = "del25"
# Username of postgres server

DB_PASSWORD = "TjhFeeB4YPE7UACe7fdV"
# database password (DO NOT PUSH TO GIT HUB USE ENV VARS FILE)

DB_PORT = "5432"
# Default for PostgreSQL. Confirm in RDS console.

def test_pg_connection():
    """Tests the connection to the RDS PostgreSQL database."""
    connection = None
    try:
        connection = psycopg2.connect(
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        print("SUCCESS: Connection to PostgreSQL RDS DB successful!")
        cursor = connection.cursor()
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS articles (
            source_name VARCHAR(255) NOT NULL,
            article_url TEXT PRIMARY KEY,
            article_section VARCHAR(255),
            publication_date TIMESTAMP,
            headline_text TEXT NOT NULL,
            headline_word_count INTEGER,
            article_word_count INTEGER,
            scrape_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            num_internal_links INTEGER DEFAULT 0,
            num_external_links INTEGER DEFAULT 0,
            num_internal_links_within_body INTEGER DEFAULT 0,
            num_external_links_within_body INTEGER DEFAULT 0,
            num_images INTEGER DEFAULT 0,
            num_images_within_body INTEGER DEFAULT 0,
            article_full_text TEXT
        );
        """
        cursor.execute("DROP TABLE IF EXISTS articles;")  # Optional: Drop table prior to creating new one
        cursor.execute(create_table_sql)
        connection.commit()
        print("SUCCESS: Articles table created (or already exists).")

    except Error as e:
        print("ERROR: Unable to connect to the PostgreSQL RDS DB.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    test_pg_connection()