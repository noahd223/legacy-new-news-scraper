#!/usr/bin/env python3
"""
Unified News Scraper - Runs all 4 scrapers in sequence
=====================================================

This script runs all four news scrapers:
1. ABC News Scraper
2. BuzzFeed Scraper  
3. CBS News Scraper
4. The Tab Scraper

Usage:
    python run_all_scrapers.py [--scrapers abc,buzzfeed,cbs,tab]

Arguments:
    --scrapers: Comma-separated list of scrapers to run (default: all)
"""

import argparse
import sys
import subprocess

def main():
    """Main function to parse arguments and run scrapers"""
    parser = argparse.ArgumentParser(
        description="Run all news scrapers in sequence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_scrapers.py                    # Run all scrapers
  python run_all_scrapers.py --scrapers abc,cbs # Run only ABC and CBS
        """
    )
    
    parser.add_argument(
        '--scrapers',
        type=str,
        default='abc,buzzfeed,cbs,tab',
        help='Comma-separated list of scrapers to run (default: all)'
    )
    
    args = parser.parse_args()
    
    # Parse scraper list
    scraper_list = [s.strip().lower() for s in args.scrapers.split(',')]
    
    # Validate scrapers
    valid_scrapers = ['abc', 'buzzfeed', 'cbs', 'tab']
    invalid_scrapers = [s for s in scraper_list if s not in valid_scrapers]
    
    if invalid_scrapers:
        print(f"Invalid scrapers: {', '.join(invalid_scrapers)}")
        print(f"Valid scrapers: {', '.join(valid_scrapers)}")
        sys.exit(1)
    
    # Run scrapers
    for scraper in scraper_list:
        print(f"\n{'='*50}")
        print(f"Running {scraper.upper()} scraper...")
        print(f"{'='*50}")
        
        if scraper == 'abc':
            subprocess.run([sys.executable, 'abc_news_scraper.py'])
        elif scraper == 'buzzfeed':
            subprocess.run([sys.executable, 'buzzfeed.py'])
        elif scraper == 'cbs':
            subprocess.run([sys.executable, 'cbs_news_scraper.py'])
        elif scraper == 'tab':
            subprocess.run([sys.executable, 'the_tab_scraper.py'])
        
        print(f"\n{scraper.upper()} scraper completed.\n")

if __name__ == "__main__":
    main() 