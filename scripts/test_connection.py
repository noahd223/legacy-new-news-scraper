# for debugging
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# load environment variables
load_dotenv()

def test_connection():  
    # get database credentials from environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_host, db_port, db_name, db_user, db_password]):
        print("Error: Missing database credentials in .env file")
        return False
    
    # create database connection string
    connection_string = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        engine = create_engine(connection_string)
        
        # test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Database connection successful")
        
        # check the articles table
        try:
            # check if table exists and get count
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM articles"))
                count = result.fetchone()[0]
                print(f"articles table: {count} total articles")
                
                # get count by source
                result = conn.execute(text("SELECT source_name, COUNT(*) FROM articles GROUP BY source_name"))
                source_counts = result.fetchall()
                print("   Articles by source:")
                for source, count in source_counts:
                    print(f"     - {source}: {count} articles")
                
                if count > 0:
                    # get sample data
                    sample = pd.read_sql_query("SELECT * FROM articles LIMIT 1", engine)
                    print(f"   Sample headline: {sample['headline_text'].iloc[0][:50]}...")
                    
        except Exception as e:
            print(f"articles table: Error - {e}")
        
        print("\nDatabase test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection() 