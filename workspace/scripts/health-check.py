#!/usr/bin/env python3
"""
Health check script for the job search agent system.
Reads jobs.json directly (no CLI timeout issues).
Returns structured health report.

Usage:
  python3 scripts/health-check.py              # Full health report
  python3 scripts/health-check.py --alert      # Only if something needs attention
  python3 scripts/health-check.py --json        # JSON output

Used by: Health Monitor cron job (runs every 30 min)
"""
import sys
import os
import json
from datetime import datetime, timezone
from queue_utils import filter_jobs, read_queue_sections

OPENCLAW_DIR = os.path.expanduser('~/.openclaw')
JOBS_JSON = os.path.join(OPENCLAW_DIR, 'cron', 'jobs.json')
WORKSPACE = os.path.join(OPENCLAW_DIR, 'workspace')
QUEUE_PATH = os.path.join(WORKSPACE, 'job-queue.md')
TRACKER_PATH = os.path.join(WORKSPACE, 'job-tracker.md')
ORCH_CYCLE_LOG = os.path.join(WORKSPACE, 'logs', 'orchestrator-cycles.jsonl')
SUBAGENT_GUARD_LOG = os.path.join(WORKSPACE, 'logs', 'subagent-guardrails.jsonl')
LOCK_PATH = os.path.join(WORKSPACE, '.queue.lock')
NO_AUTO_COMPANIES = {'openai', 'databricks', 'pinterest', 'deepmind', 'google deepmind'}

H1B_DEADLINE_MS = int(datetime(2026, 3, 15, tzinfo=timezone.utc).timestamp() * 1000)

def get_agent_health():
    """Check all agents for errors, stale runs, stuck states."""
    with open(JOBS_JSON, 'r') as f:
        data = json.load(f)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    alerts = []
    agents = []

    for job in data.get('jobs', []):
        state = job.get('state', {})
        name = job.get('name', 'Unknown')
        enabled = job.get('enabled', True)
        last_status = state.get('lastStatus', '')
        consecutive_errors = state.get('consecutiveErrors', 0)
        last_run_ms = state.get('lastRunAtMs', 0)
        running_ms = state.get('runningAtMs', 0)
        last_duration_ms = state.get('lastDurationMs', 0)

        agent_info = {
            'name': name,
            'enabled': enabled,
            'status': last_status,
            'consecutive_errors': consecutive_errors,
            'last_run_ago_min': round((now_ms - last_run_ms) / 60000) if last_run_ms else None,
            'last_duration_sec': round(last_duration_ms / 1000) if last_duration_ms else None,
            'is_running': bool(running_ms and (now_ms - running_ms) < 1800000),
        }
        agents.append(agent_info)

        # Alert conditions
        if consecutive_errors >= 3:
            alerts.append(f"CRITICAL: {name} has {consecutive_errors} consecutive errors")
        elif consecutive_errors >= 1:
            alerts.append(f"WARNING: {name} has {consecutive_errors} error(s)")

        if last_run_ms and (now_ms - last_run_ms) > 3600000 and enabled:  # >1h since last run
            hours_ago = round((now_ms - last_run_ms) / 3600000, 1)
            alerts.append(f"WARNING: {name} hasn't run in {hours_ago}h")

        if running_ms and (now_ms - running_ms) > 1800000:  # stuck >30 min
            alerts.append(f"WARNING: {name} appears stuck (running for >{round((now_ms - running_ms)/60000)}m)")

        if last_duration_ms and last_duration_ms > 600000 and name != 'Application Orchestrator':  # >10 min for non-orchestrator
            alerts.append(f"INFO: {name} took {round(last_duration_ms/1000)}s last run (slow)")

    return agents, alerts

def get_queue_health():
    """Check queue for issues."""
    alerts = []
    try:
        sections, stats = read_queue_sections(QUEUE_PATH, LOCK_PATH, no_auto_companies=NO_AUTO_COMPANIES)
        pending_count = len(sections.get('pending', []))
        in_progress_jobs = len(sections.get('in_progress', []))
        actionable = filter_jobs(sections.get('pending', []), actionable_only=True)
        by_ats = {
            'ashby': len(filter_jobs(sections.get('pending', []), actionable_only=True, ats_filter='ashby')),
            'greenhouse': len(filter_jobs(sections.get('pending', []), actionable_only=True, ats_filter='greenhouse')),
            'lever': len(filter_jobs(sections.get('pending', []), actionable_only=True, ats_filter='lever')),
            'other': len(filter_jobs(sections.get('pending', []), actionable_only=True, ats_filter='other')),
        }

        if pending_count == 0:
            alerts.append("INFO: Job queue is empty — search agent may need attention")
        elif pending_count > 100:
            alerts.append(f"WARNING: Queue has {pending_count} pending jobs — may need compaction")
        if len(actionable) > 250:
            alerts.append(f"WARNING: Actionable backlog high ({len(actionable)} jobs)")
        if in_progress_jobs:
            alerts.append(f"WARNING: {in_progress_jobs} jobs stuck IN PROGRESS")

        return {
            'pending': stats.get('pending', pending_count),
            'in_progress': stats.get('in_progress', in_progress_jobs),
            'actionable': len(actionable),
            'by_ats': by_ats,
        }, alerts
    except Exception as e:
        return {'error': str(e)}, [f"ERROR: Cannot read queue: {e}"]

def get_pipeline_health():
    """Check application pipeline for anomalies."""
    alerts = []
    try:
        with open(TRACKER_PATH, 'r') as f:
            content = f.read()

        import re
        stages = {}
        for m in re.finditer(r'- \*\*Stage:\*\*\s*(.*)', content):
            stage = m.group(1).strip()
            if "|" in stage:
                continue
            stages[stage] = stages.get(stage, 0) + 1

        total_applied = sum(v for k, v in stages.items() if k != 'Discovered')
        phone_screens = stages.get('Phone Screen', 0)
        interviews = stages.get('Technical Interview', 0)

        if total_applied > 50 and phone_screens == 0 and interviews == 0:
            alerts.append(f"CONCERN: {total_applied} applications but 0 phone screens/interviews — review application quality")

        return stages, alerts
    except Exception as e:
        return {'error': str(e)}, [f"ERROR: Cannot read tracker: {e}"]

def _model_provider(model):
    if not isinstance(model, str) or "/" not in model:
        return ""
    return model.split("/", 1)[0].strip().lower()


def _extract_secret(cred):
    if not isinstance(cred, dict):
        return "", ""
    for key in ("key", "apiKey", "token", "access"):
        value = cred.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), key
    return "", ""


def _find_provider_profile(profiles_map, provider):
    exact = f"{provider}:default"
    if exact in profiles_map and isinstance(profiles_map[exact], dict):
        return exact, profiles_map[exact]
    for name, cred in profiles_map.items():
        if not isinstance(cred, dict):
            continue
        if name.startswith(f"{provider}:") or str(cred.get("provider", "")).lower() == provider:
            return name, cred
    return "", {}


def _required_provider_jobs(jobs):
    import re

    provider_to_jobs = {}
    for job in jobs:
        if not job.get("enabled", True):
            continue
        name = str(job.get("name") or "Unknown")
        payload = job.get("payload", {})
        providers = set()

        model_provider = _model_provider(payload.get("model", ""))
        if model_provider:
            providers.add(model_provider)

        msg = payload.get("message", "")
        if isinstance(msg, str):
            for match in re.finditer(r"-\s*model:\s*([^\s]+)", msg):
                p = _model_provider(match.group(1))
                if p:
                    providers.add(p)

        for p in providers:
            provider_to_jobs.setdefault(p, set()).add(name)

    return {p: sorted(names) for p, names in provider_to_jobs.items()}


def _provider_recent_ok(jobs, required_job_names, now_ms, window_ms=6 * 3600 * 1000):
    if not required_job_names:
        return False
    required_set = set(required_job_names)
    for job in jobs:
        if str(job.get("name") or "") not in required_set:
            continue
        state = job.get("state", {})
        last_status = str(state.get("lastStatus") or "").lower()
        last_run_ms = int(state.get("lastRunAtMs") or 0)
        if last_status == "ok" and last_run_ms > 0 and (now_ms - last_run_ms) <= window_ms:
            return True
    return False


def get_auth_health():
    """Check active runtime auth for providers currently used by jobs (Anthropic/OpenRouter)."""
    alerts = []
    auth_profiles_path = os.path.join(OPENCLAW_DIR, 'agents', 'main', 'agent', 'auth-profiles.json')
    provider_env_keys = {
        "anthropic": ("ANTHROPIC_API_KEY",),
        "openrouter": ("OPENROUTER_API_KEY",),
    }

    try:
        with open(auth_profiles_path, 'r') as f:
            auth_data = json.load(f)
        with open(JOBS_JSON, 'r') as f:
            jobs_data = json.load(f)
    except Exception as e:
        alerts.append(f"WARNING: Cannot read auth/job config: {e}")
        return {'status': 'unknown'}, alerts

    profiles_map = auth_data.get("profiles", {})
    jobs = jobs_data.get("jobs", [])
    provider_jobs = _required_provider_jobs(jobs)
    required = sorted(p for p in provider_jobs.keys() if p in ("google", "openrouter"))
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    providers = {}

    for provider in required:
        profile_name, cred = _find_provider_profile(profiles_map, provider)
        token, token_field = _extract_secret(cred)
        source = ""
        if token and profile_name:
            source = f"profile:{profile_name}:{token_field}"

        if not token:
            for env_name in provider_env_keys.get(provider, ()):
                env_value = (os.environ.get(env_name) or "").strip()
                if env_value:
                    token = env_value
                    source = f"env:{env_name}"
                    break

        cred_type = str(cred.get("type") or "")
        status = "valid"
        expires_in_min = None

        if token and cred_type == "oauth":
            expires = int(cred.get("expires") or 0)
            if expires > 0:
                expires_in_min = (expires - now_ms) / 60000
                if expires_in_min <= 0:
                    status = "near_expiry"
                    alerts.append(f"WARNING: {provider} OAuth token expired in profile {profile_name}")
                elif expires_in_min < 10:
                    status = "near_expiry"
                    alerts.append(f"WARNING: {provider} OAuth token expires in {expires_in_min:.0f} min")
        elif not token:
            if _provider_recent_ok(jobs, provider_jobs.get(provider, []), now_ms):
                status = "inferred_valid"
                source = "runtime:last_success"
            else:
                status = "missing"
                if provider == "openrouter":
                    alerts.append(
                        "CRITICAL: Missing OpenRouter credential. Configure openrouter:default key or OPENROUTER_API_KEY."
                    )
                else:
                    alerts.append(
                        "WARNING: Google credential not found in auth-profiles/env. Verify gateway provider auth."
                    )

        providers[provider] = {
            "status": status,
            "profile": profile_name or "",
            "source": source or "none",
            "type": cred_type or "unknown",
            "required_by_jobs": provider_jobs.get(provider, []),
        }
        if expires_in_min is not None:
            providers[provider]["expires_in_min"] = round(expires_in_min, 1)

    if not required:
        return {
            "status": "not_required",
            "required_providers": [],
            "providers": {},
        }, alerts

    provider_statuses = [v.get("status", "unknown") for v in providers.values()]
    if any(s == "missing" for s in provider_statuses):
        overall = "missing"
    elif any(s in {"near_expiry", "unknown"} for s in provider_statuses):
        overall = "degraded"
    else:
        overall = "valid"

    return {
        "status": overall,
        "required_providers": required,
        "providers": providers,
    }, alerts


def get_orchestrator_guardrail_health():
    """Check orchestrator cycle guardrail freshness."""
    alerts = []
    latest = None
    try:
        if not os.path.exists(ORCH_CYCLE_LOG):
            alerts.append("WARNING: Orchestrator guardrail log missing (logs/orchestrator-cycles.jsonl)")
            return {"status": "missing"}, alerts

        with open(ORCH_CYCLE_LOG, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    latest = line

        if not latest:
            alerts.append("WARNING: Orchestrator guardrail log is empty")
            return {"status": "empty"}, alerts

        entry = json.loads(latest)
        ts_ms = int(entry.get('timestamp_ms', 0) or 0)
        if ts_ms <= 0:
            alerts.append("WARNING: Orchestrator guardrail latest entry has invalid timestamp")
            return {"status": "invalid"}, alerts

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age_min = (now_ms - ts_ms) / 60000
        # Also compute last-hour health signal for throughput.
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        one_hour_ago_ms = now_ms - 3600000
        cycles_1h = 0
        spawned_1h = 0
        with open(ORCH_CYCLE_LOG, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = int(e.get('timestamp_ms', 0) or 0)
                if ts >= one_hour_ago_ms:
                    cycles_1h += 1
                    spawned_1h += int(e.get('spawned_count', 0) or 0)

        status = {
            "status": "fresh" if age_min <= 10 else "stale",
            "age_min": round(age_min, 1),
            "spawned_count": entry.get('spawned_count', 0),
            "statuses": entry.get('statuses', {}),
            "cycles_1h": cycles_1h,
            "spawned_1h": spawned_1h,
        }
        if age_min > 15:
            alerts.append(f"CRITICAL: Orchestrator guardrail stale ({age_min:.1f} min old)")
        elif age_min > 10:
            alerts.append(f"WARNING: Orchestrator guardrail stale ({age_min:.1f} min old)")
        if cycles_1h >= 6 and spawned_1h == 0:
            alerts.append("WARNING: Orchestrator ran in the last hour but spawned 0 subagents")
        return status, alerts
    except Exception as e:
        alerts.append(f"WARNING: Cannot read orchestrator guardrail log: {e}")
        return {"status": "error"}, alerts


def get_subagent_guardrail_health():
    """Check transcript-derived subagent guardrail violations."""
    alerts = []
    try:
        if not os.path.exists(SUBAGENT_GUARD_LOG):
            return {"status": "missing", "violations_6h": 0, "latest": {}}, alerts

        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        six_hours_ago_ms = now_ms - (6 * 3600 * 1000)
        recent = []
        latest = None
        with open(SUBAGENT_GUARD_LOG, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                latest = entry
                ts_iso = entry.get("timestamp_iso", "")
                try:
                    ts_ms = int(datetime.fromisoformat(ts_iso).timestamp() * 1000)
                except Exception:
                    continue
                if ts_ms >= six_hours_ago_ms:
                    recent.append(entry)

        by_rule = {}
        for entry in recent:
            rule = str(entry.get("rule") or "UNKNOWN")
            by_rule[rule] = by_rule.get(rule, 0) + 1

        forbidden_gateway = by_rule.get("FORBIDDEN_GATEWAY_COMMAND", 0)
        non_canonical = (
            by_rule.get("NON_CANONICAL_FORM_FILLER_PATH", 0)
            + by_rule.get("NON_CANONICAL_FORM_FILLER_SCRIPT", 0)
        )

        if forbidden_gateway > 0:
            alerts.append(
                f"CRITICAL: {forbidden_gateway} forbidden subagent gateway command(s) in last 6h"
            )
        if non_canonical > 0:
            alerts.append(
                f"WARNING: {non_canonical} non-canonical form-filler event(s) in last 6h"
            )

        return {
            "status": "ok" if not recent else "violations",
            "violations_6h": len(recent),
            "by_rule_6h": by_rule,
            "latest": latest or {},
        }, alerts
    except Exception as e:
        alerts.append(f"WARNING: Cannot read subagent guardrail log: {e}")
        return {"status": "error"}, alerts


def main():
    alert_only = '--alert' in sys.argv
    json_mode = '--json' in sys.argv

    agents, agent_alerts = get_agent_health()
    queue, queue_alerts = get_queue_health()
    pipeline, pipeline_alerts = get_pipeline_health()
    auth, auth_alerts = get_auth_health()
    orchestrator_guardrail, orchestrator_alerts = get_orchestrator_guardrail_health()
    subagent_guardrail, subagent_guardrail_alerts = get_subagent_guardrail_health()

    all_alerts = (
        auth_alerts
        + orchestrator_alerts
        + subagent_guardrail_alerts
        + agent_alerts
        + queue_alerts
        + pipeline_alerts
    )

    # H-1B countdown
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    days_left = (H1B_DEADLINE_MS - now_ms) / 86400000
    if days_left < 14:
        all_alerts.insert(0, f"CRITICAL: H-1B deadline in {int(days_left)} days")

    if json_mode:
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'auth': auth,
            'orchestrator_guardrail': orchestrator_guardrail,
            'subagent_guardrail': subagent_guardrail,
            'agents': agents,
            'queue': queue,
            'pipeline': pipeline,
            'alerts': all_alerts,
            'h1b_days_left': int(days_left),
        }, indent=2))
        return

    if alert_only and not all_alerts:
        print("OK — no alerts")
        return

    # Text output
    print(f"=== HEALTH CHECK — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    print(f"H-1B: {int(days_left)} days left\n")

    if all_alerts:
        print("ALERTS:")
        for a in all_alerts:
            print(f"  {a}")
        print()

    auth_status = str(auth.get('status', 'unknown'))
    if auth_status == 'valid':
        auth_icon = "OK"
    elif auth_status in {'degraded', 'near_expiry'}:
        auth_icon = "WARN"
    elif auth_status in {'missing', 'expired'}:
        auth_icon = "CRITICAL"
    else:
        auth_icon = auth_status.upper()
    print(f"AUTH: {auth_icon}")
    for provider, detail in auth.get('providers', {}).items():
        print(f"  - {provider}: {detail.get('status')} ({detail.get('source')})")
    print()
    print(f"ORCHESTRATOR GUARDRAIL: {orchestrator_guardrail}\n")
    print(f"SUBAGENT GUARDRAIL: {subagent_guardrail}\n")

    print("AGENTS:")
    for a in agents:
        status = "RUNNING" if a['is_running'] else a['status'].upper()
        errors = f" ({a['consecutive_errors']} errors)" if a['consecutive_errors'] else ""
        duration = f" [{a['last_duration_sec']}s]" if a['last_duration_sec'] else ""
        ago = f" {a['last_run_ago_min']}m ago" if a['last_run_ago_min'] else ""
        print(f"  {a['name']}: {status}{errors}{duration}{ago}")

    print(f"\nQUEUE: {queue.get('pending', '?')} pending | {queue.get('in_progress', '?')} in_progress")

    print(f"\nPIPELINE: {pipeline}")

if __name__ == '__main__':
    main()
