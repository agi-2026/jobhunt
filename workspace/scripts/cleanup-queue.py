#!/usr/bin/env python3
"""Clean up job queue: remove non-US, low-score bad fits, expired jobs."""
import re, sys

QUEUE_FILE = '/Users/howard/.openclaw/workspace/job-queue.md'

with open(QUEUE_FILE, 'r') as f:
    content = f.read()

# Split into header (before PENDING section) and job entries
pending_match = re.search(r'^## PENDING \(sorted by priority score, highest first\)\s*\n', content, re.MULTILINE)
if not pending_match:
    print("ERROR: Could not find PENDING section")
    sys.exit(1)

header = content[:pending_match.end()]
body = content[pending_match.end():]

# Parse individual job blocks
job_pattern = re.compile(r'^### \[(\d+)\] (.+?)$', re.MULTILINE)
jobs = []
matches = list(job_pattern.finditer(body))
for i, m in enumerate(matches):
    start = m.start()
    end = matches[i+1].start() if i+1 < len(matches) else len(body)
    block = body[start:end]
    score = int(m.group(1))
    title_line = m.group(2)
    jobs.append({
        'score': score,
        'title': title_line,
        'block': block,
        'start': start,
        'end': end,
    })

print(f"Total PENDING jobs parsed: {len(jobs)}")

# Non-US locations to flag
NON_US_LOCATIONS = [
    'london', 'tokyo', 'zurich', 'zürich', 'berlin', 'paris', 'seoul',
    'uae', 'dubai', 'singapore', 'toronto', 'copenhagen', 'grenoble',
    'krakow', 'kraków', 'bangalore', 'bengaluru', 'mumbai', 'hyderabad',
    'tel aviv', 'amsterdam', 'dublin', 'sydney', 'melbourne', 'vancouver',
    'montreal', 'ottawa', 'munich', 'hamburg', 'stockholm', 'oslo',
    'helsinki', 'vienna', 'brussels', 'warsaw', 'prague', 'budapest',
    'lisbon', 'madrid', 'barcelona', 'milan', 'rome', 'taipei',
    'hong kong', 'shanghai', 'beijing', 'shenzhen', 'delhi',
    'canada', 'uk', 'u.k.', 'united kingdom', 'germany', 'france',
    'japan', 'korea', 'india', 'australia', 'ireland', 'israel',
    'netherlands', 'switzerland', 'sweden', 'norway', 'finland',
    'denmark', 'austria', 'belgium', 'poland', 'czech', 'hungary',
    'portugal', 'spain', 'italy', 'taiwan', 'china',
    'são paulo', 'sao paulo', 'brazil', 'mexico city',
    'accra', 'nairobi', 'lagos', 'cape town',
]

US_INDICATORS = [
    'san francisco', 'sf', 'new york', 'nyc', 'seattle', 'mountain view',
    'palo alto', 'menlo park', 'sunnyvale', 'cupertino', 'san jose',
    'los angeles', 'la', 'chicago', 'boston', 'austin', 'denver',
    'washington', 'dc', 'd.c.', 'pittsburgh', 'atlanta', 'miami',
    'portland', 'philadelphia', 'san diego', 'santa clara', 'redmond',
    'bellevue', 'cambridge', 'somerville', 'brooklyn', 'manhattan',
    'raleigh', 'durham', 'research triangle', 'boulder', 'salt lake',
    'remote', 'usa', 'u.s.', 'united states', 'us-based',
    ', ca', ', ny', ', wa', ', tx', ', ma', ', co', ', il', ', ga',
    ', fl', ', pa', ', va', ', md', ', nc', ', or', ', az', ', ut',
    'california', 'texas', 'massachusetts', 'virginia', 'maryland',
    'north carolina', 'georgia', 'florida', 'colorado', 'arizona',
    'bay area', 'silicon valley',
]

# Companies to never remove
PROTECTED_COMPANIES = ['openai', 'databricks']

# Strong companies worth keeping even at low scores
STRONG_COMPANIES = [
    'openai', 'anthropic', 'google', 'deepmind', 'meta', 'apple', 'microsoft',
    'nvidia', 'databricks', 'scale ai', 'cohere', 'mistral', 'together ai',
    'anyscale', 'hugging face', 'stability ai', 'midjourney', 'runway',
    'inflection', 'character ai', 'perplexity', 'ramp', 'stripe', 'figma',
    'notion', 'vercel', 'replicate', 'modal', 'weights & biases', 'wandb',
    'liquid ai', 'magic ai', 'magic.dev', 'sesame', 'chai discovery',
    'patronus', 'black forest labs',
]

# Keywords indicating good fit for Howard
FIT_KEYWORDS = [
    'reinforcement learning', 'rl ', 'grpo', 'dpo', 'rlhf', 'post-training',
    'autonomous agent', 'ai agent', 'agentic', 'on-device', 'edge ai',
    'inference optimization', 'diffusion', 'text-to-image', 'generative',
    'team lead', 'staff', 'founding engineer', 'research scientist',
    'research engineer', 'ml engineer', 'machine learning engineer',
]

removed = []
kept = []

for job in jobs:
    block_lower = job['block'].lower()
    title_lower = job['title'].lower()
    score = job['score']
    
    # Extract location line
    loc_match = re.search(r'\*\*Location:\*\*\s*(.+)', job['block'])
    location = loc_match.group(1).strip() if loc_match else ''
    loc_lower = location.lower()
    
    # Extract company name (before the —)
    company = job['title'].split('—')[0].strip().lower() if '—' in job['title'] else title_lower
    
    # Check if protected
    is_protected = any(p in company for p in PROTECTED_COMPANIES)
    if is_protected:
        kept.append(job)
        continue
    
    # Check if already applied/skipped
    status_match = re.search(r'\*\*Status:\*\*\s*(\S+)', job['block'])
    status = status_match.group(1).strip() if status_match else 'PENDING'
    if status != 'PENDING':
        kept.append(job)
        continue
    
    # --- Rule 1: Non-US location check ---
    has_us = any(us in loc_lower for us in US_INDICATORS)
    has_non_us = any(non_us in loc_lower for non_us in NON_US_LOCATIONS)
    
    # If location is explicitly non-US only
    if has_non_us and not has_us and loc_lower:
        removed.append((job, 'non-US location', location))
        continue
    
    # If no location listed, check title/block for non-US hints
    if not location or location == '—':
        # Ambiguous - keep it
        pass
    
    # --- Rule 2: Low score bad fit ---
    if score < 220 and score > 0:
        is_strong = any(s in company for s in STRONG_COMPANIES)
        is_fit = any(kw in block_lower or kw in title_lower for kw in FIT_KEYWORDS)
        
        if not is_strong and not is_fit:
            removed.append((job, 'low score bad fit', f'score={score}'))
            continue
    
    # Score 0 jobs - API-discovered, need review
    if score == 0:
        is_strong = any(s in company for s in STRONG_COMPANIES)
        is_fit = any(kw in block_lower or kw in title_lower for kw in FIT_KEYWORDS)
        
        # Check location for score-0 jobs too
        if has_non_us and not has_us and loc_lower:
            removed.append((job, 'non-US location', location))
            continue
        
        # Remove clear non-fits at score 0
        non_fit_keywords = [
            'security engineer', 'internal tools', 'developer relations',
            'devrel', 'technical writer', 'recruiter', 'people ops',
            'office manager', 'executive assistant', 'sales', 'account',
            'customer success', 'support engineer', 'solutions architect',
            'insert-job', 'kernel engineer', 'distributed systems engineer',
            'supercomputing platform', 'full-stack engineer',
        ]
        is_non_fit = any(nf in title_lower for nf in non_fit_keywords)
        
        if is_non_fit and not is_strong:
            removed.append((job, 'low score bad fit', f'score=0, non-fit title'))
            continue
        
        if not is_strong and not is_fit:
            removed.append((job, 'low score bad fit', f'score=0, no strong signal'))
            continue
    
    kept.append(job)

# Print summary
print(f"\n=== CLEANUP SUMMARY ===")
print(f"Removed: {len(removed)}")
print(f"Remaining: {len(kept)}")

by_reason = {}
for job, reason, detail in removed:
    by_reason.setdefault(reason, []).append(f"  [{job['score']}] {job['title']} ({detail})")

for reason, items in sorted(by_reason.items()):
    print(f"\n--- {reason} ({len(items)}) ---")
    for item in items:
        print(item)

# Rebuild file
new_body = '\n'.join(job['block'] for job in kept)

# Update stats
new_header = re.sub(
    r'Pending: \d+',
    f'Pending: {len(kept)}',
    header
)
new_header = re.sub(
    r'Last compaction: .+? CT',
    'Last compaction: 2026-02-15 21:17 CT',
    new_header
)

new_content = new_header + new_body

with open(QUEUE_FILE, 'w') as f:
    f.write(new_content)

print(f"\n✅ File updated. {len(kept)} jobs remaining.")
