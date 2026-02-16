#!/usr/bin/env python3
"""
Search for LinkedIn connections at a company using Brave Search API.
Returns mutual connections (alumni from your schools/companies).

Usage:
  python3 scripts/search-connections.py "Anthropic"
  python3 scripts/search-connections.py "Anthropic" --json

Output:
  CONNECTIONS at Anthropic:
  - John Doe (UChicago alum) — Senior Research Engineer | linkedin.com/in/johndoe
  - Jane Smith (Lenovo) — ML Engineer | linkedin.com/in/janesmith
  NO_CONNECTIONS — no mutual connections found at Company

The application agent can mention these in cover letters/essays.
"""
import sys
import os
import json
import re
import urllib.request
import urllib.parse

# Load API key
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(WORKSPACE, '.env')

def load_api_key():
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r') as f:
            for line in f:
                if line.startswith('BRAVE_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('BRAVE_API_KEY', '')

BRAVE_API_KEY = load_api_key()
BRAVE_ENDPOINT = 'https://api.search.brave.com/res/v1/web/search'

# Networks to search for — CUSTOMIZE with your schools and past employers
NETWORKS = [
    ('YourSchool', 'Your University Name'),
    ('PastEmployer', 'Past Employer Inc'),
    # Add more networks: ('Label', 'Search Term'),
]

def brave_search(query, count=10):
    """Search Brave API and return results."""
    params = urllib.parse.urlencode({'q': query, 'count': count})
    url = f"{BRAVE_ENDPOINT}?{params}"

    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('X-Subscription-Token', BRAVE_API_KEY)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get('web', {}).get('results', [])
    except Exception as e:
        return []

def extract_linkedin_profiles(results):
    """Extract LinkedIn profile info from search results."""
    profiles = []
    seen_urls = set()

    for r in results:
        url = r.get('url', '')
        title = r.get('title', '')
        description = r.get('description', '')

        # Only LinkedIn profile pages
        if 'linkedin.com/in/' not in url:
            continue

        # Skip Howard's own profile
        if 'howard-cheng' in url.lower() or 'howard cheng' in title.lower():
            continue

        # Deduplicate
        profile_id = url.split('linkedin.com/in/')[-1].strip('/')
        if profile_id in seen_urls:
            continue
        seen_urls.add(profile_id)

        # Extract name from title (typically "Name - Title - Company | LinkedIn")
        name = title.split(' - ')[0].strip() if ' - ' in title else title.split(' | ')[0].strip()
        name = name.replace(' | LinkedIn', '').strip()

        # Extract role from title
        role_parts = title.replace(' | LinkedIn', '').split(' - ')
        role = role_parts[1].strip() if len(role_parts) > 1 else ''

        profiles.append({
            'name': name,
            'role': role,
            'url': url,
            'description': description[:150],
            'profile_id': profile_id,
        })

    return profiles

def search_connections(company):
    """Search for connections at a company from Howard's networks."""
    all_connections = []

    for network_short, network_full in NETWORKS:
        query = f'site:linkedin.com/in/ "{company}" "{network_full}"'
        results = brave_search(query, count=5)
        profiles = extract_linkedin_profiles(results)

        for p in profiles:
            p['network'] = network_short
            all_connections.append(p)

    # Also search for general company employees
    query = f'site:linkedin.com/in/ "{company}" "AI" OR "ML" OR "Research"'
    results = brave_search(query, count=5)
    general_profiles = extract_linkedin_profiles(results)
    for p in general_profiles:
        if p['profile_id'] not in {c['profile_id'] for c in all_connections}:
            p['network'] = 'Industry'
            all_connections.append(p)

    return all_connections

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 search-connections.py \"Company Name\" [--json]")
        sys.exit(1)

    company = sys.argv[1]
    json_mode = '--json' in sys.argv

    if not BRAVE_API_KEY:
        print("ERROR: BRAVE_API_KEY not found in .env")
        sys.exit(1)

    connections = search_connections(company)

    if json_mode:
        print(json.dumps(connections, indent=2))
        return

    if not connections:
        print(f"NO_CONNECTIONS — no mutual connections found at {company}")
        return

    # Prioritize: network connections first
    network_conns = [c for c in connections if c['network'] != 'Industry']
    industry_conns = [c for c in connections if c['network'] == 'Industry']

    print(f"CONNECTIONS at {company}:")
    for c in network_conns:
        print(f"  [{c['network']}] {c['name']} — {c['role']} | {c['url']}")
    for c in industry_conns[:3]:  # Limit industry to top 3
        print(f"  [Industry] {c['name']} — {c['role']} | {c['url']}")

    if network_conns:
        print(f"\nSUGGESTED MENTION: \"I noticed [Name] from {network_conns[0]['network']} works at {company} — I'd love to connect about the team's work.\"")

if __name__ == '__main__':
    main()
