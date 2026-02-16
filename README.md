# JobHunt — Autonomous AI Job Search Agent

An open-source, fully autonomous job search agent that discovers jobs, applies to them, tracks your pipeline, and keeps you informed — all while you sleep.

Built on [OpenClaw](https://github.com/nichochar/openclaw), powered by Claude.

```
┌───────────────────────────────────────────────────────────────┐
│                    JobHunt Agent Architecture                 │
│                                                               │
│  ┌──────────────┐     job-queue.md      ┌───────────────────┐ │
│  │ Search Agent │ ──── (priority) ────▶│ Application Agent  │ │
│  │  (Producer)  │     sorted queue     │   (Consumer)       │ │
│  │              │                       │                   │ │
│  │ • Greenhouse │                      │ • Form Filler      │ │
│  │ • HN Hiring  │                      │ • Resume Upload    │ │
│  │ • Brave API  │                      │ • Essay Writer     │ │
│  │ • Browser    │                      │ • Submit + Log     │ │
│  └──────────────┘                       └───────────────────┘ │
│        │                                         │            │
│        │          ┌──────────────┐               │            │
│        └─────────▶│  Dashboard   │◀──────────────┘            │
│                   │  :8765       │                            │
│                   └──────┬───────┘                            │
│                          │                                    │
│  ┌──────────────┐  ┌─────┴─────┐  ┌──────────────┐            │
│  │Email Monitor │  │ Evening   │  │Health Monitor│            │
│  │  (2h cycle)  │  │ Summary   │  │ (30m cycle)  │            │
│  │              │  │ (9 PM)    │  │              │            │
│  │ Detect reply │  │ Pipeline  │  │ Error alerts │            │
│  │ Update stage │  │ report    │  │ Stuck agents │            │
│  └──────────────┘  └───────────┘  └──────────────┘            │
│                                                               │
│  ┌──────────────┐                   ┌─────────┐               │
│  │Analysis Agent│                   │WhatsApp │               │
│  │ (daily 8:30) │──────────────────▶│ (you)   │               │
│  │ Log analysis │                   └─────────┘               │
│  └──────────────┘                                             │
└───────────────────────────────────────────────────────────────┘
```

## What It Does

| Agent | Schedule | Model | Job |
|-------|----------|-------|-----|
| **Search Agent** | Every 5 min | Sonnet 4.5 | Discovers jobs via Greenhouse API, HN Hiring, Brave Search, browser scraping. Scores and ranks them. |
| **Application Agent** | Every 2 min | Opus 4.6 | Picks the highest-scored job, fills the form, writes essays, uploads resume, submits. Up to 5 per cycle. |
| **Email Monitor** | Every 2 hours | Haiku 4.5 | Scans Gmail for recruiter replies, interview invites, rejections. Updates pipeline stages. |
| **Evening Summary** | Daily 9 PM | Haiku 4.5 | Sends you a WhatsApp summary: jobs found, applied, pipeline health, action items. |
| **Analysis Agent** | Daily 8:30 PM | Haiku 4.5 | Parses cron logs, identifies failure patterns, suggests improvements. |
| **Health Monitor** | Every 30 min | Haiku 4.5 | Checks for stuck agents, consecutive errors, queue issues. Alerts only when something is wrong. |

**Typical daily output:** 15+ jobs discovered, 8+ applications submitted, all on autopilot.

## Features

### Intelligent Job Discovery
- **API-first search** — Greenhouse API, HN Who is Hiring (no browser overhead)
- **Browser scraping** — Ashby, Lever, LinkedIn, YC Work at a Startup
- **Brave Search API** — general web search for job listings
- **Priority scoring** (max ~400) = Recency + Salary + Company Stage + Role Match
- **Deduplication** — URL + company+title matching, auto-rebuilt index

### Autonomous Application
- **Deterministic form filler** — fills 40+ standard fields in ~1 second via browser JS injection
- **React-aware** — handles Greenhouse dropdowns, Ashby toggle buttons, Lever comboboxes
- **AI essay writer** — reads your SOUL.md persona, writes tailored 200-400 word responses
- **Resume upload** — programmatic file upload (no OS dialogs)
- **Email verification** — auto-fetches Greenhouse verification codes from Gmail
- **LinkedIn connections** — searches for alumni at target companies, mentions them in essays

### Smart Context Management
- **Multi-layer memory** — hot (~2KB always loaded), warm (on-demand), cold (archived)
- **Exec-based scripts** — agents call Python scripts instead of reading large files into context
- **Token-efficient** — reduced context window usage from ~30K to ~5K tokens per session

### Observability
- **Real-time dashboard** at `localhost:8765` — pipeline, queue, agent health, stage updates
- **WhatsApp notifications** — interview invites (instant), daily summaries, error alerts
- **Log analysis** — daily pattern detection, failure tracking, improvement suggestions
- **Health monitoring** — consecutive error alerts, stuck agent detection

## Supported ATS Platforms

| Platform | Auto-Fill | Auto-Submit | Notes |
|----------|-----------|-------------|-------|
| Greenhouse | Yes | Yes | Email verification auto-handled |
| Ashby | Yes | Yes | Toggle buttons with full event chain |
| Lever | Yes | Yes | Simple forms, direct submit |
| Generic HTML | Yes | Yes | Standard form detection |
| Workday | No | No | Multi-page, requires account — auto-skipped |
| BambooHR | No | No | Complex, often CAPTCHA — auto-skipped |

## Prerequisites

- **[OpenClaw](https://github.com/nichochar/openclaw)** v2026.2+ — the AI agent platform
- **Node.js** 20+ and **pnpm**
- **Python** 3.10+
- **Anthropic API key** (for Claude models)
- **Brave Search API key** ([get one free](https://brave.com/search/api/))
- **Gmail** account with [gog](https://github.com/nichochar/gog) CLI configured
- **WhatsApp** linked to OpenClaw (for notifications)
- **Tailscale** (optional — for Gmail push notifications via Funnel)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/agi-2026/jobhunt.git
cd jobhunt
```

### 2. Set up your profile

Copy the example files and fill in your details:

```bash
# API keys
cp .env.example workspace/.env
# Edit workspace/.env with your Brave API key

# Personal profile for essay writing
cp workspace/SOUL.md.example workspace/SOUL.md
# Edit workspace/SOUL.md with your background, achievements, talking points

# Form fields (name, email, phone, education, etc.)
cp workspace/form-fields.md.example workspace/form-fields.md
# Edit workspace/form-fields.md with your details

# Target companies
cp workspace/company-watchlist.md.example workspace/company-watchlist.md
# Edit with companies you want to monitor

# Search schedule
cp workspace/search-rotation.md.example workspace/search-rotation.md
# Configure which boards to search and how often

# Cron jobs
cp cron/jobs.json.example cron/jobs.json
# Update phone numbers, email, and model preferences
```

### 3. Update the form filler

Edit `workspace/scripts/form-filler.js` — replace the `PROFILE` object (lines 17-86) with your personal information. Every field matters:

```javascript
const PROFILE = {
  firstName: 'Your First Name',
  lastName: 'Your Last Name',
  email: 'you@example.com',
  phone: '+15555555555',
  linkedin: 'https://linkedin.com/in/you',
  // ... see file for all fields
};
```

### 4. Update the connection search

Edit `workspace/scripts/search-connections.py` — replace the `NETWORKS` list with your schools and past employers:

```python
NETWORKS = [
    ('MIT', 'Massachusetts Institute of Technology'),
    ('Google', 'Google'),
    # Add your schools and past employers
]
```

### 5. Add your resume

```bash
cp /path/to/your/resume.pdf workspace/resume/
```

Update the resume filename in `workspace/AGENTS.md` (Phase 3: Resume Upload section).

### 6. Install OpenClaw and set up workspace

```bash
# Install OpenClaw (see their docs for full setup)
git clone https://github.com/nichochar/openclaw.git ~/openclaw
cd ~/openclaw && pnpm install

# Link workspace
cp -r jobhunt/workspace/* ~/.openclaw/workspace/

# Import cron jobs
cp jobhunt/cron/jobs.json ~/.openclaw/cron/jobs.json

# Link WhatsApp
pnpm openclaw channels login --channel whatsapp --account default
```

### 7. Launch

```bash
./start.sh
```

Open `http://localhost:8765` to see your dashboard.

## Project Structure

```
jobhunt/
├── README.md                          # You are here
├── start.sh                           # Startup script (gateway + dashboard)
├── .env.example                       # API key template
│
├── dashboard/
│   └── server.py                      # Web dashboard (pipeline, queue, agents)
│
├── workspace/                         # → copies to ~/.openclaw/workspace/
│   ├── AGENTS.md                      # Agent instructions & workflows
│   ├── IDENTITY.md                    # Agent persona definition
│   ├── HEARTBEAT.md                   # Periodic health check tasks
│   ├── TOOLS.md                       # Environment-specific notes
│   ├── TODO.md                        # Improvement tracker
│   ├── ats-reference.md               # ATS platform edge cases
│   ├── SOUL.md.example                # ← Your persona template
│   ├── form-fields.md.example         # ← Your form data template
│   ├── search-rotation.md.example     # ← Search schedule template
│   ├── company-watchlist.md.example   # ← Target companies template
│   │
│   ├── scripts/
│   │   ├── form-filler.js             # Deterministic form filler (45KB)
│   │   ├── fill-custom-answers.js     # AI essay/custom question handler
│   │   ├── scrape-board.js            # Universal job board scraper
│   │   ├── scrape-ashby.js            # Ashby-specific scraper
│   │   ├── scrape-greenhouse.js       # Greenhouse-specific scraper
│   │   ├── scrape-lever.js            # Lever-specific scraper
│   │   ├── scrape-linkedin.js         # LinkedIn search scraper
│   │   ├── scrape-workatastartup.js   # YC Work at a Startup scraper
│   │   ├── add-to-queue.py            # Add job to priority queue
│   │   ├── check-dedup.py             # Deduplication checker
│   │   ├── build-dedup-index.py       # Rebuild dedup index from tracker
│   │   ├── compact-queue.py           # Archive old queue entries
│   │   ├── queue-summary.py           # Compact queue view (1 line/job)
│   │   ├── search-greenhouse-api.py   # Greenhouse API search (no browser)
│   │   ├── search-hn-hiring.py        # HN Who is Hiring scraper
│   │   ├── search-connections.py      # LinkedIn alumni search via Brave
│   │   ├── read-memory.py             # Multi-layer memory reader
│   │   ├── update-tracker-stage.py    # Update job stage in tracker
│   │   ├── health-check.py            # System health monitor
│   │   ├── analyze-logs.py            # Log analysis for improvements
│   │   └── ats-notes.md               # ATS behavior documentation
│   │
│   ├── memory/                        # Agent session memory (gitignored)
│   ├── resume/                        # Your resume PDF (gitignored)
│   └── analysis/                      # Daily analysis reports (gitignored)
│
└── cron/
    └── jobs.json.example              # Cron job configuration template
```

## How It Works

### The Producer-Consumer Loop

The system runs as a **producer-consumer pipeline**:

1. **Search Agent (Producer)** runs every 5 minutes:
   - Queries Greenhouse API, HN Hiring, Brave Search
   - Scrapes Ashby/Lever/LinkedIn boards via browser
   - Scores each job (0-400) based on recency, salary, company stage, and role match
   - Dedup-checks against existing applications
   - Adds new jobs to `job-queue.md` sorted by score

2. **Application Agent (Consumer)** runs every 2 minutes:
   - Reads queue summary (top 15 jobs, compact 1-line format)
   - Picks the highest-scored PENDING job
   - For high-value jobs (score >= 280): searches for LinkedIn alumni connections
   - Opens the job URL in a browser
   - Runs `form-filler.js` via `evaluate` — fills 40+ fields in ~1 second
   - For custom/essay questions: reads your SOUL.md, writes tailored responses
   - Uploads resume, submits, verifies confirmation
   - Logs results to `job-tracker.md`
   - Loops: up to 5 applications per cycle

3. **Supporting agents** handle monitoring, email, analysis, and health.

### Scoring Formula

Each job gets a score out of ~400:

```
Score = Recency + Salary + Company + Match

Recency:  100 (today) / 70 (1-3d) / 50 (4-7d) / 30 (1-2w) / 10 (older)
Salary:   100 ($300K+) / 80 ($200-300K) / 60 ($150-200K) / 30 (unlisted) / 0 (<$150K)
Company:  100 (top lab/unicorn) / 90 ($100M+) / 80 (Series B+) / 70 (Series A) / 50 (seed)
Match:    100 (exact title+skills) / 80 (strong) / 60 (partial) / 40 (adjacent)
```

### Context Window Optimization

Agents never read large files directly. Instead, they use exec scripts:

| Instead of reading... | Agents call... |
|----------------------|----------------|
| `dedup-index.md` (72KB) | `python3 scripts/check-dedup.py "<url>"` → "NEW" or "DUPLICATE" |
| `job-queue.md` (182KB) | `python3 scripts/queue-summary.py --top 10` → compact 1-line/job |
| `job-tracker.md` (114KB) | `python3 scripts/update-tracker-stage.py "Company" "Stage"` |

Memory is tiered:
- **Hot** (~2KB): Pipeline stats, today's activity, critical patterns — loaded every session
- **Warm** (on-demand): ATS patterns, company notes, failure logs — loaded only when needed
- **Cold** (archived): Past sessions, old analysis — never loaded

### The Form Filler

`form-filler.js` is the core engine that makes autonomous applications possible. It:

1. **Detects the ATS** from the page URL (Greenhouse, Ashby, Lever, etc.)
2. **Maps form fields** to your PROFILE data using label matching, name attributes, and placeholder text
3. **Fills everything deterministically** in a single pass — no AI calls needed for standard fields
4. **Handles React**: Uses `nativeInputValueSetter` + synthetic events to bypass React's controlled inputs
5. **Handles dropdowns**: Full pointer event chain for Ashby toggles, combobox interaction for Greenhouse
6. **Detects iframes**: If the form is in a cross-origin iframe, returns the iframe URL for redirect
7. **Returns unfilled fields**: Custom/essay questions are flagged for AI handling

Result: Standard form fill takes ~1 second instead of 5-10 minutes of per-field AI calls.

## Dashboard

The dashboard at `http://localhost:8765` provides:

- **Pipeline view** — Applied, Confirmed, Phone Screens, Interviews, Offers, Rejected (computed from actual tracker entries)
- **Agent status** — Running/OK/Error, last run time, next scheduled, consecutive errors
- **Job queue** — Pending (sorted by score), In Progress, Completed, Skipped
- **Stage updates** — One-click to update a job's stage (e.g., when you get a phone screen)
- **Dedup management** — Add URLs to prevent duplicate applications
- **Auto-refresh** every 30 seconds

## Customization

### Adding a New Greenhouse Company

1. Find the company's Greenhouse slug from their careers URL: `boards.greenhouse.io/<slug>/jobs`
2. Add to `search-rotation.md` under "Greenhouse Companies"
3. Add to `company-watchlist.md` under the appropriate tier
4. The slug goes in your Search Agent cron job's Greenhouse API command

### Adding a New Ashby/Lever Company

1. Find their job board URL (e.g., `jobs.ashbyhq.com/companyname`)
2. Add to `search-rotation.md` under "Ashby Boards" or "Lever Boards"
3. Add to `company-watchlist.md`
4. The browser scraper (`scrape-board.js`) auto-detects the ATS type

### Adjusting Search Frequency

Edit the cron expressions in `cron/jobs.json`:
- `*/5 * * * *` = every 5 minutes
- `*/15 * * * *` = every 15 minutes
- `0 */2 * * *` = every 2 hours

### Adding Companies to Skip

In `workspace/AGENTS.md`, add companies to the "DO NOT AUTO-APPLY" section. The Application Agent will skip them and notify you via WhatsApp.

### Model Selection

| Agent | Recommended Model | Why |
|-------|------------------|-----|
| Application Agent | Opus 4.6 | Needs judgment for essays and complex forms |
| Search Agent | Sonnet 4.5 | Mechanical scraping, scoring doesn't need deep reasoning |
| Email Monitor | Haiku 4.5 | Simple email classification task |
| Evening Summary | Haiku 4.5 | Summarization is straightforward |
| Analysis Agent | Haiku 4.5 | Log parsing and pattern matching |
| Health Monitor | Haiku 4.5 | Simple health check evaluation |

## Troubleshooting

### Agent errors with "No active WhatsApp Web listener"
```bash
pnpm openclaw channels login --channel whatsapp --account default
```
Then scan the QR code with WhatsApp on your phone.

### Gateway times out on CLI commands
When agents are running, CLI commands can timeout. Read `~/.openclaw/cron/jobs.json` directly instead of using `pnpm openclaw cron list`.

### Stale `runningAtMs` markers cause agents to deadlock
Agents get stuck when a previous run didn't clean up its running state. Fix:
```bash
# Clean all running states in jobs.json
python3 -c "
import json
with open('$HOME/.openclaw/cron/jobs.json', 'r+') as f:
    data = json.load(f)
    for job in data['jobs']:
        job.get('state', {}).pop('runningAtMs', None)
    f.seek(0); json.dump(data, f, indent=2); f.truncate()
"
```
Consider setting up a watchdog script to auto-clean stale markers.

### Form filler doesn't work on a specific site
1. Check if it's Workday/BambooHR — these are auto-skipped
2. Check if the form is in a cross-origin iframe — the filler will return an `iframeUrl`
3. Some sites use non-standard React patterns — check `ats-reference.md` for known edge cases

### Dashboard shows wrong pipeline counts
Pipeline counts are computed from actual `- **Stage:**` lines in `job-tracker.md`. If counts look wrong, check that the stage names match exactly: `Applied`, `Confirmed`, `Phone Screen`, etc.

### OAuth token expired
If using Anthropic's OAuth tokens (OAT), they expire after ~8 hours. Set up a token refresh automation or re-login periodically.

## Contributing

This project is built in the open. Contributions welcome:

- **New ATS support** — add scrapers/fillers for new platforms
- **Better scoring** — improve the job relevance scoring formula
- **New search sources** — add scrapers for more job boards
- **Dashboard features** — charts, analytics, better UX
- **Bug fixes** — especially for ATS form handling edge cases

### How to Contribute

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/new-ats-support`)
3. Make your changes
4. Test with your own OpenClaw setup
5. Submit a PR with a clear description

### Known Issues / Improvement Ideas

- [ ] Lever API scraper (JSON endpoint, no browser needed)
- [ ] Ashby GraphQL API scraper
- [ ] Dynamic search scheduling (adjust frequency based on job yield)
- [ ] Follow-up agent (auto-send check-in emails 5-7 days post-application)
- [ ] A/B test application strategies (generic vs. tailored essays)
- [ ] Token cost tracking in dashboard
- [ ] Multi-user support (separate profiles/workspaces)
- [ ] Docker container for easy deployment

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [OpenClaw](https://github.com/nichochar/openclaw) — the AI agent platform that makes this possible
- [Claude](https://claude.ai) by Anthropic — the AI models powering the agents
- [Brave Search API](https://brave.com/search/api/) — web search for job discovery and connection search

---

**Built by [@agi-2026](https://github.com/agi-2026) while racing an H-1B deadline. If this helps your job search, star the repo and share it.**
