import psycopg2
from psycopg2 import Error
import csv
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DB_NAME = os.getenv("DB_NAME", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = os.getenv("DB_PORT", "5432")

def export_table_to_csv():
    """Exports the entire 'articles' table to a CSV file."""
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
        select_table_sql = "SELECT * FROM articles;"
        cursor.execute(select_table_sql)
        results = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]

        with open("articles_table_export.csv", "w", newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(column_names)
            writer.writerows(results)
        print("SUCCESS: Exported entire 'articles' table to 'articles_table_export.csv'.")
        cursor.close()
        connection.close()

    except Error as e:
        print("ERROR: Unable to connect to the PostgreSQL RDS DB or export table.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    export_table_to_csv()