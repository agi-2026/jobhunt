#!/usr/bin/env python3
"""Shared queue parsing/filter helpers for JobHunt scripts."""

import fcntl
import ipaddress
import re
import socket
from urllib.parse import urlparse

ATS_PATTERNS = {
    "ashby": ["ashbyhq.com"],
    "greenhouse": ["greenhouse.io", "gh_jid="],
    "lever": ["lever.co"],
}


def read_queue_content(queue_path: str, lock_path: str) -> str:
    """Read queue file under shared lock."""
    with open(lock_path, "w", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_SH)
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                return f.read()
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def parse_queue_sections(content: str, no_auto_companies=None):
    """Parse queue markdown into sectioned jobs + stats."""
    no_auto_companies = set(no_auto_companies or set())
    sections = {"pending": [], "in_progress": [], "completed": [], "skipped": [], "no_auto": []}
    current_section = None
    current_job = None
    stats = {"pending": 0, "in_progress": 0}

    def flush(job, fallback):
        if not job:
            return
        target = job.get("_section", fallback)
        sections.setdefault(target, []).append(job)

    for line in content.split("\n"):
        stripped = line.strip()

        m_stats = re.match(r".*Pending:\s*(\d+)\s*\|\s*In Progress:\s*(\d+)", stripped)
        if m_stats:
            stats["pending"] = int(m_stats.group(1))
            stats["in_progress"] = int(m_stats.group(2))

        if stripped.startswith("## ") and "DO NOT AUTO-APPLY" in stripped:
            flush(current_job, "pending")
            current_job = None
            current_section = "no_auto"
            continue
        if stripped == "## IN PROGRESS":
            flush(current_job, "pending")
            current_job = None
            current_section = "in_progress"
            continue
        if stripped.startswith("## PENDING"):
            flush(current_job, "pending")
            current_job = None
            current_section = "pending"
            continue
        if stripped.startswith("## COMPLETED"):
            flush(current_job, "pending")
            current_job = None
            current_section = "completed"
            continue
        if stripped == "## SKIPPED":
            flush(current_job, "pending")
            current_job = None
            current_section = "skipped"
            continue
        if stripped.startswith("## "):
            flush(current_job, "pending")
            current_job = None
            current_section = None
            continue

        if current_section is None:
            continue

        m_job = re.match(r"^###\s+\[(\d+)\]\s+(.+?)\s*—\s*(.+)$", stripped)
        if m_job:
            flush(current_job, "pending")
            current_job = {
                "_section": "pending" if current_section == "no_auto" else current_section,
                "score": int(m_job.group(1)),
                "company": m_job.group(2).strip(),
                "title": m_job.group(3).strip(),
                "url": "",
                "location": "",
                "salary": "",
                "no_auto": current_section == "no_auto",
            }
            continue

        if not current_job:
            continue

        if stripped.startswith("- **URL:**"):
            current_job["url"] = stripped.split("**URL:**", 1)[1].strip()
        elif stripped.startswith("- **Location:**"):
            current_job["location"] = stripped.split("**Location:**", 1)[1].strip()
        elif stripped.startswith("- **Salary:**"):
            current_job["salary"] = stripped.split("**Salary:**", 1)[1].strip()
        elif (
            "DO NOT AUTO-APPLY" in stripped
            or "OPENAI LIMIT" in stripped
            or "Auto-Apply: NO" in stripped
            or "NO-AUTO" in stripped
        ):
            current_job["no_auto"] = True

    flush(current_job, "pending")

    for section in sections.values():
        for job in section:
            if job.get("company", "").lower() in no_auto_companies:
                job["no_auto"] = True
            job.pop("_section", None)

    if stats["pending"] == 0:
        stats["pending"] = len(sections["pending"])
    if stats["in_progress"] == 0:
        stats["in_progress"] = len(sections["in_progress"])

    return sections, stats


def read_queue_sections(queue_path: str, lock_path: str, no_auto_companies=None):
    content = read_queue_content(queue_path, lock_path)
    return parse_queue_sections(content, no_auto_companies=no_auto_companies)


def filter_jobs(jobs, actionable_only=False, ats_filter=None):
    out = list(jobs)
    if actionable_only:
        out = [j for j in out if not j.get("no_auto")]

    if ats_filter:
        ats_filter = ats_filter.lower()
        patterns = ATS_PATTERNS.get(ats_filter)
        if patterns:
            out = [j for j in out if any(p in j.get("url", "") for p in patterns)]
        elif ats_filter == "other":
            all_known = [p for arr in ATS_PATTERNS.values() for p in arr]
            out = [j for j in out if not any(p in j.get("url", "") for p in all_known)]

    return out


def is_safe_url(url: str) -> tuple[bool, str]:
    """Validate URL to prevent Server-Side Request Forgery (SSRF).

    Checks scheme (http/https only) and resolves hostnames to verify that target IP addresses
    are not loopback, private, link-local, or multicast/reserved.
    Returns (is_safe, reason).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL type"

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL structure: {e}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported scheme '{parsed.scheme}'; only http/https allowed"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in URL"

    hostname_lower = hostname.lower()
    if hostname_lower in ("localhost", "localhost.localdomain") or hostname_lower.endswith(".localhost"):
        return False, "Loopback domain blocked"

    try:
        # Resolve hostname to all associated IP addresses (both IPv4 and IPv6)
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return False, f"Cannot resolve hostname '{hostname}': {e}"
    except Exception as e:
        return False, f"Hostname resolution error: {e}"

    if not addr_info:
        return False, f"No IP address found for hostname '{hostname}'"

    for item in addr_info:
        ip_str = item[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Invalid IP address format: {ip_str}"

        if ip.is_loopback:
            return False, f"Resolved IP {ip_str} is a loopback address"
        if ip.is_link_local:
            return False, f"Resolved IP {ip_str} is a link-local address"
        if ip.is_private:
            return False, f"Resolved IP {ip_str} is a private address"
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False, f"Resolved IP {ip_str} is restricted/reserved"

    return True, "URL is safe"
