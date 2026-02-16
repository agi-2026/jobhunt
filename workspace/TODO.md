# Job Search Agent — Improvement Tracker

> Created: 2026-02-15 | Last Updated: 2026-02-15
> Priority: P0 = do now, P1 = do today, P2 = do this week

---

## P0 — Critical Fixes

### 1. Fix Dashboard Pipeline Tracking
- [x] Pipeline counts now computed from actual tracker entries (not manual table)
- [x] Agent status reads from jobs.json directly (no CLI timeout)
- [x] Added stage update form (POST /api/stage)
- [x] H-1B countdown banner with dynamic days
- [x] Proper badge colors for Phone Screen, Interview, Offer stages
- [x] Agent health display (consecutive errors, duration, schedule)

### 2. Fix Email Agent Detection
- [x] Created `update-tracker-stage.py` exec script
- [x] Updated Email Monitor cron prompt with stage update instructions
- [x] Email agent now updates tracker stages (Applied → Phone Screen → Interview)
- [x] Pipeline counts auto-recalculate on stage update

### 3. Context Window Optimization
- [x] Created `queue-summary.py` — compact 1-line-per-job output
- [x] Application Agent uses queue-summary.py instead of reading full queue
- [x] Search Agent starts with `read-memory.py hot` (2KB) instead of reading files
- [x] ATS reference moved to on-demand (read only when filling specific ATS)
- [x] AGENTS.md v3 updated with exec-based context management table

---

## P1 — High Impact Improvements

### 4. Multi-Layer Memory
- [x] Created `read-memory.py` with hot/warm/stats tiers
- [x] **Hot** (~2KB): Pipeline stats, today's activity, critical patterns, active rules
- [x] **Warm** (on-demand): `warm ats`, `warm companies`, `warm failures`, `warm session`
- [x] **Stats**: Pipeline + daily stats from tracker
- [x] All agents start with `exec: python3 scripts/read-memory.py hot`

### 5. Analysis Agent (New Cron Job)
- [x] Created `analyze-logs.py` — parses cron logs for error patterns
- [x] Added Analysis Agent cron job (daily 8:30 PM CT, Haiku 4.5)
- [x] Outputs: `analysis/daily-report-YYYY-MM-DD.md`
- [x] WhatsApp 5-line summary of findings

### 6. Health & Resilience Alerting
- [x] Created `health-check.py` — checks agents, queue, pipeline health
- [x] Added Health Monitor cron job (every 30 min, Haiku 4.5)
- [x] Alerts: 3+ consecutive errors → CRITICAL, 1-2 → WARNING
- [x] Silent when healthy (no unnecessary WhatsApp messages)
- [x] Dashboard shows agent health (errors, duration, schedule)

---

## P2 — Enhancements

### 7. Model Selection Optimization
- [x] Search Agent: Opus → **Sonnet 4.5** (scraping is mechanical)
- [x] Email Monitor: → **Haiku 4.5** (classification task)
- [x] Evening Summary: → **Haiku 4.5** (summarization)
- [x] Analysis Agent: **Haiku 4.5** (log parsing)
- [x] Health Monitor: **Haiku 4.5** (health check)
- [x] Application Agent: **Opus 4.6** (kept — needs judgment for essays)

### 8. LinkedIn Connection Search
- [x] Created `search-connections.py` using Brave API
- [x] Searches for UChicago, Northeastern, Lenovo alumni at target companies
- [x] Application Agent uses for jobs with score >= 280
- [x] Suggested mention text generated automatically

### 9. Dynamic Search Scheduling
- [x] Search Agent reports "YIELD: X new jobs" at end of session
- [x] Infrastructure in place for external schedule adjustment
- [ ] Implement wrapper script to adjust cron frequency based on yield (NEXT)

### 10. Direct API Integrations
- [x] Greenhouse API: `search-greenhouse-api.py` (DONE)
- [x] HN Hiring: `search-hn-hiring.py` (DONE)
- [ ] Lever API: Similar to Greenhouse, JSON endpoint
- [ ] Ashby API: Public GraphQL API for job listings

---

## Remaining Work
- [ ] Lever API scraper (`search-lever-api.py`)
- [ ] Ashby API scraper (`search-ashby-api.py`)
- [ ] Dynamic scheduling wrapper (adjust cron based on YIELD signal)
- [ ] Follow-up agent (check-in emails 5-7 days post-application)
- [ ] A/B test application strategies (generic vs. tailored essays)
- [ ] Token cost tracking dashboard panel

---

## Completed (All Time)
- [x] Dashboard v2 with pipeline tracking, stage updates, health (2026-02-15)
- [x] Multi-layer memory system (2026-02-15)
- [x] Analysis Agent cron job (2026-02-15)
- [x] Health Monitor cron job (2026-02-15)
- [x] Model selection optimization — 6 agents configured (2026-02-15)
- [x] LinkedIn connection search (2026-02-15)
- [x] Email agent stage update fix (2026-02-15)
- [x] Context window optimization (2026-02-15)
- [x] update-tracker-stage.py, queue-summary.py, read-memory.py, search-connections.py (2026-02-15)
- [x] health-check.py, analyze-logs.py (2026-02-15)
- [x] Greenhouse API integration (2026-02-15)
- [x] HN Who is Hiring scraper (2026-02-15)
- [x] API-first search workflow in AGENTS.md (2026-02-15)
- [x] Stale marker watchdog (2026-02-14)
- [x] OAuth token refresh automation (2026-02-14)
- [x] Queue compaction automation (2026-02-14)
- [x] Fast fill protocol (2026-02-14)
- [x] Ashby toggle button handling (2026-02-14)
- [x] Iframe detection/redirect (2026-02-14)
