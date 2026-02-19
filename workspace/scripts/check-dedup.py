#!/usr/bin/env python3
"""
Check if a job URL or company+title already exists in the dedup index.

Usage:
  python3 scripts/check-dedup.py "https://some-url.com"
  python3 scripts/check-dedup.py "https://some-url.com" "Company Name" "Job Title"

Output:
  NEW                                    → not in dedup index
  DUPLICATE | Company | Title | Status | Date  → already exists

Also supports batch mode via stdin (one URL per line):
  echo -e "url1\nurl2\nurl3" | python3 scripts/check-dedup.py --batch
"""
import sys
import os

DEDUP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'dedup-index.md')

def load_dedup_index():
    """Load dedup index into URL set and company+title set."""
    urls = {}
    company_titles = {}

    if not os.path.exists(DEDUP_PATH):
        return urls, company_titles

    with open(DEDUP_PATH, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('URL'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 4:
                url = parts[0].lower()
                company = parts[1].lower()
                title = parts[2].lower()
                status = parts[3] if len(parts) > 3 else ''
                date = parts[4] if len(parts) > 4 else ''

                urls[url] = line
                key = f"{company}|||{title}"
                company_titles[key] = line

    return urls, company_titles

def check_one(url, company='', title='', urls=None, company_titles=None):
    """Check a single URL/company+title against the index."""
    if urls is None:
        urls, company_titles = load_dedup_index()

    # Check URL
    url_lower = url.lower().strip()
    # Also try without trailing slash
    url_variants = [url_lower, url_lower.rstrip('/'), url_lower + '/']
    for v in url_variants:
        if v in urls:
            return f"DUPLICATE {urls[v]}"

    # Check company+title
    if company and title:
        key = f"{company.lower().strip()}|||{title.lower().strip()}"
        if key in company_titles:
            return f"DUPLICATE {company_titles[key]}"

    return "NEW"

def main():
    args = sys.argv[1:]

    if '--batch' in args:
        # Batch mode: read URLs from stdin
        urls, company_titles = load_dedup_index()
        for line in sys.stdin:
            url = line.strip()
            if url:
                result = check_one(url, urls=urls, company_titles=company_titles)
                print(f"{url} → {result}")
        return

    if len(args) < 1:
        print("Usage: python3 check-dedup.py <url> [company] [title]")
        sys.exit(1)

    url = args[0]
    company = args[1] if len(args) > 1 else ''
    title = args[2] if len(args) > 2 else ''

    result = check_one(url, company, title)
    print(result)

if __name__ == '__main__':
    main()
