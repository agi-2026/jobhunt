# JobHunt — Autonomous AI Job Search Agent

An open-source, fully autonomous job search agent that discovers jobs, applies to them in parallel, tracks your pipeline, and keeps you informed — all while you sleep.

Built on [OpenClaw](https://github.com/nichochar/openclaw), powered by Claude.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   JobHunt v5 — Parallel Application Architecture         │
│                                                                          │
│  Search Agent (every 30 min)                                             │
│  ┌──────────────────────────────────────────┐                            │
│  │ API-first: Ashby + Greenhouse + Lever    │                            │
│  │ 172 companies across 3 ATS types         │──▶ job-queue.md            │
│  │ HN Who is Hiring (monthly)               │    (priority sorted)       │
│  └──────────────────────────────────────────┘                            │
│                                                                          │
│  Application Orchestrator (every 5 min)                                  │
│  ┌──────────────────────────────────────────┐                            │
│  │ 1. Batch preflight (remove dead links)   │                            │
│  │ 2. Check locks + queue per ATS type      │                            │
│  │ 3. Spawn parallel subagents ─────────────┼──┐                         │
│  └──────────────────────────────────────────┘  │                         │
│                                                │                         │
│  Subagent Lane (true parallelism)              │                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐            │
│  │ Ashby Agent     │ │ Greenhouse Agent│ │ Lever Agent     │            │
│  │ browser :18801  │ │ browser :18802  │ │ browser :18803  │            │
│  │ up to 3 apps    │ │ up to 3 apps   │ │ up to 3 apps    │            │
│  │ form-filler.js  │ │ form-filler.js │ │ form-filler.js  │            │
│  └────────┬────────┘ └───────┬────────┘ └────────┬────────┘            │
│           └──────────────────┼───────────────────┘                      │
│                              ▼                                           │
│                      job-tracker.md                                      │
│                                                                          │
│  ┌──────────────┐  ┌───────────┐  ┌──────────────┐                      │
│  │Health Monitor│  │ Dashboard │  │   WhatsApp   │                      │
│  │  (30m cycle) │  │   :8765   │  │ notifications│                      │
│  └──────────────┘  └───────────┘  └──────────────┘                      │
└──────────────────────────────────────────────────────────────────────────┘
```

## What It Does

| Agent | Schedule | Model | Job |
|-------|----------|-------|-----|
| **Search Agent** | Every 30 min | Sonnet 4.5 | Discovers jobs via Ashby/Greenhouse/Lever APIs + HN Hiring. Scores, deduplicates, adds to priority queue. |
| **Application Orchestrator** | Every 5 min | Sonnet 4.5 | Checks locks and queues, spawns parallel ATS-specific subagents via `sessions_spawn`. |
| **Ashby Subagent** | On-demand | Sonnet 4.5 | Applies to up to 3 Ashby jobs per cycle. Dedicated browser profile (port 18801). |
| **Greenhouse Subagent** | On-demand | Sonnet 4.5 | Applies to up to 3 Greenhouse jobs per cycle. Handles email verification. Dedicated browser (port 18802). |
| **Lever Subagent** | On-demand | Sonnet 4.5 | Applies to up to 3 Lever jobs per cycle. Dedicated browser (port 18803). |
| **Health Monitor** | Every 30 min | Haiku 4.5 | Checks for stuck agents, consecutive errors, queue issues. WhatsApp alerts only for critical issues. |

**Typical daily output:** 50+ jobs discovered, 15+ applications submitted across 3 ATS types in parallel.

## Key Innovations

### Parallel Application via `sessions_spawn`

OpenClaw's cron lane is serialized — jobs run one at a time. JobHunt works around this with an **orchestrator pattern**: a single cron job spawns up to 3 subagents that run truly in parallel on the subagent lane. Each subagent has its own browser profile and ATS-specific skill set.

**Before (v4):** 3 ATS agents run serially → ~45 min per cycle
**After (v5):** 3 subagents run in parallel → ~15 min per cycle (limited by the slowest)

### API-First Job Discovery

No browser overhead for search. All 172 tracked companies are searched via their native ATS APIs:

| ATS | Companies | Method |
|-----|-----------|--------|
| Ashby | 98 | GraphQL API (`/api/posting-api/postings`) |
| Greenhouse | 59 | JSON API (`/v1/boards/{slug}/jobs`) |
| Lever | 15 | JSON API (`/v0/postings/{slug}`) |

New companies are added by simply editing the Python search scripts — no browser automation needed.

### Deterministic Form Filling

Each ATS type has its own `form-filler.js` that fills 40+ standard fields in ~1 second via browser JS injection. No AI calls needed for standard fields — only custom/essay questions use the model.

### Concurrent Queue Safety

With 3 subagents writing to `job-queue.md` and `dedup-index.md` simultaneously, file-level `fcntl.flock()` advisory locking prevents data corruption. A shared `.queue.lock` file ensures mutual exclusion across all queue-modifying scripts.

## Features

### Intelligent Job Discovery
- **API-first search** — Ashby GraphQL, Greenhouse JSON, Lever JSON APIs (no browser overhead)
- **172 tracked companies** — from top AI labs to VC portfolio startups (a16z, Sequoia)
- **HN Who is Hiring** — monthly scrape via Algolia API
- **Priority scoring** (max ~400) = Recency + Salary + Company Stage + Role Match
- **Deduplication** — URL + company+title matching, maintained atomically by scripts
- **US/remote location filter** — auto-skips non-US jobs during search

### Autonomous Application
- **ATS-specific form fillers** — dedicated `form-filler.js` per platform, fills 40+ fields in ~1s
- **React-aware** — handles Greenhouse dropdowns, Ashby toggle buttons, Lever comboboxes
- **AI essay writer** — reads your SOUL.md persona, writes tailored 200-400 word responses inline
- **Resume upload** — programmatic file upload via `element=` + React event verification
- **Email verification** — auto-fetches Greenhouse verification codes from Gmail
- **Parallel execution** — 3 browser profiles apply simultaneously (up to 9 apps per cycle)

### Smart Context Management
- **Multi-layer memory** — hot (~2KB always loaded), warm (on-demand), cold (archived)
- **Exec-based scripts** — agents call Python scripts instead of reading large files
- **Token-efficient** — ~5K tokens per session instead of ~30K
- **File locking** — `fcntl.flock()` prevents data corruption from parallel writes

### Observability
- **Real-time dashboard** at `localhost:8765` — 5 tabs: Pending Queue, Manual Apply, In Progress, Completed, Skipped
- **WhatsApp notifications** — critical error alerts only (no spam)
- **Session memory** — each agent appends to `memory/session-YYYY-MM-DD.md`
- **Health monitoring** — consecutive error alerts, stuck agent detection

## Supported ATS Platforms

| Platform | API Search | Auto-Fill | Auto-Submit | Notes |
|----------|-----------|-----------|-------------|-------|
| Ashby | Yes (GraphQL) | Yes | Yes | Toggle buttons with full event chain |
| Greenhouse | Yes (JSON) | Yes | Yes | Email verification auto-handled, MyGreenhouse autofill support |
| Lever | Yes (JSON) | Yes | Yes | Playwright fallback for location fields |
| Workday | No | No | No | Multi-page, requires account — manual only |
| Custom ATS | No | No | No | 70+ companies tracked in manual-apply-priority.md |

## Prerequisites

- **[OpenClaw](https://github.com/nichochar/openclaw)** v2026.2+ — the AI agent platform
- **Node.js** 20+ and **pnpm**
- **Python** 3.10+
- **Anthropic API key** (for Claude models)
- **Gmail** account with [gog](https://github.com/nichochar/gog) CLI configured
- **WhatsApp** linked to OpenClaw (for notifications)

## Quick Start

### 1. Install OpenClaw

```bash
git clone https://github.com/nichochar/openclaw.git ~/openclaw
cd ~/openclaw && pnpm install
```

### 2. Clone JobHunt

```bash
git clone https://github.com/agi-2026/jobhunt.git ~/jobhunt
cd ~/jobhunt
```

### 3. Run setup

The setup script creates config files from templates and symlinks the workspace into OpenClaw:

```bash
./setup.sh
```

This will:
- Copy `.example` templates to personal config files (if they don't exist yet)
- Symlink `~/.openclaw/workspace` to your repo's `workspace/` directory
- Symlink `~/.openclaw/cron/jobs.json` to your repo's `cron/jobs.json`
- Create required directories

### 4. Configure your profile

Edit the generated config files with your personal data:

```bash
# Your background, talking points, personality for essays
edit workspace/SOUL.md

# Standard form fields (name, email, phone, education)
edit workspace/form-fields.md

# The form filler engine — update the PROFILE object
edit workspace/scripts/form-filler.js
# Also update ATS-specific form fillers:
edit workspace/skills/apply-ashby/scripts/form-filler.js
edit workspace/skills/apply-greenhouse/scripts/form-filler.js
edit workspace/skills/apply-lever/scripts/form-filler.js

# Agent instructions — set your deadline, preferences, skip rules
edit workspace/AGENTS.md

# Cron jobs — update phone numbers, email, model preferences
edit cron/jobs.json

# API keys
edit .env
```

### 5. Add your resume

```bash
cp /path/to/your/resume.pdf workspace/resume/
```

### 6. Add target companies

Edit the search scripts to add companies to track:

```bash
# Add Ashby companies (98 tracked by default)
edit workspace/scripts/search-ashby-api.py

# Add Greenhouse companies (59 tracked by default)
edit workspace/scripts/search-greenhouse-api.py

# Add Lever companies (15 tracked by default)
edit workspace/scripts/search-lever-api.py
```

Each script has a `COMPANY_INFO` dict — just add a slug and metadata.

### 7. Link WhatsApp and launch

```bash
cd ~/openclaw && pnpm openclaw channels login --channel whatsapp --account default
cd ~/jobhunt && ./start.sh
```

### 8. Verify

```bash
./setup.sh --check
```

Open `http://localhost:8765` to see your dashboard.

## Project Structure

```
jobhunt/
├── README.md
├── setup.sh                               # Interactive setup (creates configs + symlinks)
├── start.sh                               # Launch gateway + dashboard
├── .env.example                           # API key template
├── scripts -> workspace/scripts           # Symlink (subagent exec: commands resolve here)
├── skills -> workspace/skills             # Symlink (subagent SKILL.md reads resolve here)
│
├── dashboard/
│   └── server.py                          # Web dashboard (5-tab: pending, manual, progress, completed, skipped)
│
├── workspace/                             # ← symlinked to ~/.openclaw/workspace/
│   │
│   │  # TEMPLATES (tracked in git — copy to create personal versions)
│   ├── AGENTS.md.example                  # Agent instructions template
│   ├── SOUL.md.example                    # Persona/essay template
│   ├── form-fields.md.example             # Form data template
│   ├── HEARTBEAT.md.example               # Heartbeat check template
│   │
│   │  # CODE (tracked in git)
│   ├── IDENTITY.md                        # Agent persona definition
│   ├── TOOLS.md                           # Environment-specific notes
│   ├── manual-apply-priority.md           # 70+ custom-ATS companies, tiered by priority
│   │
│   ├── scripts/
│   │   │  # Search (API-first, no browser)
│   │   ├── search-ashby-api.py            # Ashby GraphQL API (98 companies)
│   │   ├── search-greenhouse-api.py       # Greenhouse JSON API (59 companies)
│   │   ├── search-lever-api.py            # Lever JSON API (15 companies)
│   │   ├── search-hn-hiring.py            # HN Who is Hiring via Algolia
│   │   ├── detect-ats.py                  # Detect ATS type for new companies
│   │   │
│   │   │  # Queue management
│   │   ├── add-to-queue.py                # Add job to priority queue
│   │   ├── check-dedup.py                 # Dedup check (avoids reading full index)
│   │   ├── mark-applied.py                # Update queue + dedup atomically (with flock)
│   │   ├── remove-from-queue.py           # Remove/skip + dedup (with flock)
│   │   ├── queue-summary.py               # Compact queue view (--ats filter, --actionable)
│   │   ├── compact-queue.py               # Archive old entries, reduce file bloat
│   │   ├── batch-preflight.py             # Bulk dead-link detection via ATS APIs
│   │   ├── preflight-check.py             # Single-URL pre-flight validation
│   │   │
│   │   │  # Application support
│   │   ├── verify-upload.js               # React event fix after resume upload
│   │   ├── greenhouse-verify-code.js      # Greenhouse email verification code filler
│   │   ├── subagent-lock.py               # File-based locking for parallel subagents
│   │   │
│   │   │  # Monitoring
│   │   ├── health-check.py                # System health monitor
│   │   ├── read-memory.py                 # Multi-layer memory reader (hot/warm/stats)
│   │   ├── analyze-logs.py                # Log analysis for improvements
│   │   └── dynamic-scheduler.py           # Auto-adjust cron frequency by yield
│   │
│   └── skills/                            # ATS-specific application skills
│       ├── apply-ashby/
│       │   ├── SKILL.md                   # Ashby-specific application instructions
│       │   └── scripts/form-filler.js     # Ashby form filler (gitignored — personal data)
│       ├── apply-greenhouse/
│       │   ├── SKILL.md                   # Greenhouse-specific instructions (email verification, etc.)
│       │   └── scripts/form-filler.js     # Greenhouse form filler (gitignored)
│       └── apply-lever/
│           ├── SKILL.md                   # Lever-specific instructions
│           └── scripts/form-filler.js     # Lever form filler (gitignored)
│
└── cron/
    ├── jobs.json.example                  # Cron configuration template
    └── jobs.json                          # Your cron config (gitignored, symlinked)
```

### Architecture: OpenClaw as Platform, JobHunt as Agent

```
~/openclaw/                    ← OpenClaw platform (update with git pull)
                                  Provides: gateway, cron, browser, sessions_spawn

~/jobhunt/                     ← JobHunt agent (this repo — source of truth)
  workspace/                      All scripts, templates, skills, and runtime data
  dashboard/                      Dashboard server
  cron/                           Agent schedules
  scripts -> workspace/scripts    Symlink for subagent exec: resolution
  skills -> workspace/skills      Symlink for subagent SKILL.md resolution

~/.openclaw/                   ← OpenClaw runtime (config + symlinks)
  openclaw.json                   Gateway config
  workspace → ~/jobhunt/workspace/    ← SYMLINK
  cron/jobs.json → ~/jobhunt/cron/jobs.json  ← SYMLINK
  browser/                        Chrome profiles (ashby, greenhouse, lever, openclaw)
```

## How It Works

### The Parallel Pipeline

The system runs as a **producer-consumer pipeline with parallel consumers**:

1. **Search Agent (Producer)** runs every 30 minutes:
   - Queries 172 companies across Ashby, Greenhouse, and Lever APIs
   - Scrapes HN Who is Hiring monthly via Algolia
   - Scores each job (0-400) based on recency, salary, company stage, and role match
   - Dedup-checks against existing applications
   - Adds new jobs to `job-queue.md` sorted by score
   - Filters non-US/non-remote jobs automatically (Greenhouse filter)

2. **Application Orchestrator** runs every 5 minutes:
   - Runs `batch-preflight.py --all --remove` to clean dead links
   - For each ATS type (ashby, greenhouse, lever):
     - Checks subagent lock — skips if a previous subagent is still running
     - Checks queue — skips if no actionable jobs for this ATS type
     - Spawns a subagent via `sessions_spawn` with the ATS-specific task

3. **ATS Subagents** (spawned in parallel on the subagent lane):
   - Acquire a file lock for their ATS type
   - Read their ATS-specific SKILL.md for instructions
   - Run `form-filler.js` to fill standard fields in ~1 second
   - Use AI for essay/custom questions (writes inline, no sub-spawning)
   - Upload resume, submit, verify confirmation
   - Mark applied in queue + dedup atomically (with `fcntl.flock()`)
   - Release lock and append to session memory
   - Each processes up to 3 jobs per invocation

4. **Health Monitor** runs every 30 minutes:
   - Checks consecutive errors, stuck agents, queue health
   - WhatsApp alerts only for critical issues

### Scoring Formula

Each job gets a score out of ~400:

```
Score = Recency + Salary + Company + Match

Recency:  100 (today) / 70 (1-3d) / 50 (4-7d) / 30 (1-2w) / 10 (older)
Salary:   100 ($300K+) / 80 ($200-300K) / 60 ($150-200K) / 30 (unlisted) / 0 (<$150K)
Company:  100 (top lab/unicorn) / 90 ($100M+) / 80 (Series B+) / 70 (Series A) / 50 (seed)
Match:    100 (exact title+skills) / 80 (strong) / 60 (partial) / 40 (adjacent)
```

### Race Condition Safety

With 3 subagents running in parallel:

| Concern | Mitigation |
|---------|------------|
| Two subagents apply to same job | ATS-type isolation (each only sees its ATS type) |
| Orchestrator spawns duplicate subagent | File-based lock with 25min auto-expiry |
| Concurrent writes to queue/dedup files | `fcntl.flock()` on shared `.queue.lock` |
| Subagent crashes without unlocking | Lock auto-expires (timeout 15min + 10min buffer) |

### Context Window Optimization

Agents never read large files directly. Instead, they use exec scripts:

| Instead of reading... | Agents call... |
|----------------------|----------------|
| `dedup-index.md` (72KB) | `python3 scripts/check-dedup.py "<url>"` → "NEW" or "DUPLICATE" |
| `job-queue.md` (180KB+) | `python3 scripts/queue-summary.py --ats ashby --top 5` → compact view |
| `job-tracker.md` (114KB) | `python3 scripts/mark-applied.py "<url>" "<company>" "<title>"` |

## Dashboard

The dashboard at `http://localhost:8765` provides 5 tabs:

- **Pending Queue** — Jobs waiting to be applied to, sorted by score
- **Manual Apply** — Companies with application limits or custom ATS (OpenAI, Waymo, etc.)
- **In Progress** — Jobs currently being processed
- **Completed** — Successfully submitted applications
- **Skipped** — Jobs skipped (non-US, expired, already applied)

Plus: pipeline stage counts, agent status from cron state, auto-refresh.

## Customization

### Adding a New Company

1. Detect the ATS type:
```bash
python3 workspace/scripts/detect-ats.py "company.com"
```

2. Add to the appropriate search script:
```python
# In search-ashby-api.py, search-greenhouse-api.py, or search-lever-api.py:
COMPANY_INFO = {
    'company-slug': {'name': 'Company', 'info': 'Description', 'score': 80, 'h1b': 'Likely'},
    ...
}
```

3. Run the search to populate the queue:
```bash
python3 workspace/scripts/search-ashby-api.py --slug company-slug --add
```

### Adding Companies in Bulk

1. Create a text file with career page URLs (one per line)
2. Run ATS detection:
```bash
python3 workspace/scripts/detect-ats.py --file companies.txt
```
3. Add detected companies to the appropriate search scripts
4. Add "not found" companies to `workspace/manual-apply-priority.md`

### Model Selection

| Agent | Recommended Model | Why |
|-------|------------------|-----|
| Application Subagents | Sonnet 4.5 | Good balance of form-filling capability and cost |
| Orchestrator | Sonnet 4.5 | Needs to parse queue output and make spawn decisions |
| Search Agent | Sonnet 4.5 | Mechanical API calls, scoring doesn't need deep reasoning |
| Health Monitor | Haiku 4.5 | Simple health check evaluation |

## Troubleshooting

### Subagent ENOENT errors
Subagents run with CWD at the repo root. They need symlinks to find scripts and skills:
```bash
cd ~/jobhunt
ln -s workspace/scripts scripts
ln -s workspace/skills skills
```

### Gateway doesn't pick up jobs.json changes
The gateway loads cron state into memory at startup. After editing `jobs.json`, restart:
```bash
kill $(pgrep -f openclaw-gateway) && pnpm openclaw gateway --port 18789
```

### "label already in use" errors in gateway logs
A previous subagent session with the same label wasn't cleaned up. This resolves automatically when the subagent lock expires (25 min). To force-clean:
```bash
python3 workspace/scripts/subagent-lock.py unlock ashby
python3 workspace/scripts/subagent-lock.py unlock greenhouse
python3 workspace/scripts/subagent-lock.py unlock lever
```

### Gateway times out on CLI commands
When agents are running, CLI commands can timeout. Read `~/.openclaw/cron/jobs.json` directly.

### Dashboard shows wrong counts
Pipeline counts are computed from `job-tracker.md` stage entries. Queue counts are from `job-queue.md` section headers.

## Contributing

This project is built in the open. Contributions welcome:

- **New ATS support** — add API scrapers + form fillers for new platforms (Workday, BambooHR)
- **Better scoring** — improve the job relevance scoring formula
- **New search sources** — add API integrations for more job boards
- **Dashboard features** — charts, analytics, application success rates
- **Bug fixes** — especially for ATS form handling edge cases

### How to Contribute

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/new-ats-support`)
3. Make your changes
4. Test with your own OpenClaw setup
5. Submit a PR with a clear description

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [OpenClaw](https://github.com/nichochar/openclaw) — the AI agent platform that makes this possible
- [Claude](https://claude.ai) by Anthropic — the AI models powering the agents

---

**Built by [@agi-2026](https://github.com/agi-2026) while racing an H-1B deadline. If this helps your job search, star the repo and share it.**
