#!/bin/bash

# Navigate to the project directory to ensure all relative paths
# (like for your other scraper files or .env) work correctly.
cd /home/ubuntu/legacy-new-news-scraper

# Activate the virtual environment.
# This makes sure the correct Python interpreter and installed libraries are used.
source venv_scraper/bin/activate

# Run the main Python scraper script.
# Your scraper_main.py should use python-dotenv to load credentials from .env.
python run_all_scrapers.py

# Deactivate the virtual environment (optional, but good practice to clean up the shell's environment).
deactivate
