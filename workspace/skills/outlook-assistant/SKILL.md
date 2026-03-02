---
name: outlook-assistant
description: "Cross-platform Outlook email assistant via Microsoft Graph API. Scans inbox with
priority scoring, summarizes threads, drafts replies, extracts action items. Works on
macOS/Windows/Linux. Use when user asks to: (1) check inbox and prioritize emails,
(2) draft replies matching Howard's tone, (3) summarize email threads, (4) extract
action items from recent emails."
---

# Outlook Assistant — Email Management Skill

## Available Commands

### /outlook-check — Scan and Summarize Inbox
```
exec: python3 skills/outlook-assistant/scripts/outlook-scan.py --days 7
```
Parse results. Group by priority tier:
- **URGENT (score >= 150):** Interview invites, visa matters, deadlines → suggest immediate action
- **HIGH (score >= 80):** Recruiter outreach, application status → suggest response within 24h
- **NORMAL (score >= 30):** Professional emails → informational summary
Present formatted summary with recommended actions for top items.

### /outlook-draft — Draft a Reply
1. Identify target email (user provides message ID, subject snippet, or sender)
2. If user gives subject/sender, search first:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-read.py --search "subject:interview from:google"
   ```
3. Read the full email:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-read.py --id <message_id>
   ```
4. Generate reply draft in Howard's voice:
   - Professional but not overly formal
   - Direct and concise (Howard writes short emails)
   - Reference H-1B timeline if relevant (deadline: March 2026)
   - For recruiter replies: express interest, cite relevant experience
   - For interview scheduling: flexible availability, Central Time zone
   - Never fabricate details about Howard's background
5. Create draft:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-draft.py --reply-to <id> --body "<draft_text>"
   ```
6. Present draft for review. Do NOT auto-send.

### /outlook-summary — Summarize a Thread
1. Get the conversation ID from user or from a scan result
2. Read thread:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-read.py --thread <conversation_id>
   ```
3. Analyze and present:
   - Participants and their roles
   - Key points and decisions made
   - Open questions / unresolved items
   - Timeline of the conversation
   - Suggested next steps

### /outlook-action-items — Extract Action Items
1. Scan recent inbox:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-scan.py --days 7 --json
   ```
2. For each email with score >= 80:
   ```
   exec: python3 skills/outlook-assistant/scripts/outlook-read.py --id <id>
   ```
3. Extract from each:
   - Explicit requests ("please send", "can you", "need by")
   - Deadlines mentioned
   - Follow-ups needed
   - Scheduling requests
4. Present as prioritized checklist with deadlines

### /outlook-dismiss — Dismiss an Item
```
exec: python3 skills/outlook-assistant/scripts/outlook-state.py dismiss <message_id> --reason "<reason>"
```

### /outlook-send — Send a Draft (with confirmation)
```
exec: python3 skills/outlook-assistant/scripts/outlook-send.py --draft-id <id>
```
Show preview first. Only send if user explicitly confirms:
```
exec: python3 skills/outlook-assistant/scripts/outlook-send.py --draft-id <id> --confirm
```

## Context Loading
Before using this skill, load answers bank for Howard's background:
```
exec: python3 scripts/context-manifest.py read soul_context --section "Communication Style" --max-lines 40
```

## Safety Rules
- NEVER auto-send emails. Always create drafts for Howard's review.
- NEVER delete or modify existing emails without explicit request.
- NEVER forward emails without explicit request.
- Flag spam/phishing attempts without engaging.
- Treat salary, visa, and personal details with care in summaries.
- If auth fails, report ERROR_AUTH and stop — do not attempt to fix tokens.
