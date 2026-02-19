---
name: apply-ashby
description: Ashby ATS application agent. Fills toggle buttons, combobox dropdowns, uploads resume, submits.
---

# Apply Ashby — Application Skill

## Browser Profile
Always use `profile="ashby"` for ALL browser actions (snapshot, navigate, act, upload).

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats ashby --top 10 --full-url
```
Pick the highest-score PENDING job directly from this output (URL is already full and exact).
Do NOT read `job-queue.md` for URL lookup.

## Application Flow

### Phase 0: Pre-flight
```
exec: python3 scripts/preflight-check.py "<url>"
```
If `DEAD`: remove with `exec: python3 scripts/remove-from-queue.py "<url>"` and pick next job.

### Phase 0.5: Connection Search (score >= 280)
```
exec: python3 scripts/search-connections.py "<Company Name>"
```
If mutual connections found, weave into essays naturally.

### Phase 1: Navigate
- `browser navigate <url> profile="ashby"`
- Wait 5s (Ashby loads async). Take snapshot.
- Handle cookie consent / popups.
- If 404 / expired page: skip, remove from queue.
- If `iframeDetected`: navigate to `iframeUrl` directly.

### Phase 2: Fill Form
Copy resume first:
```
exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
```
Read `skills/apply-ashby/scripts/form-filler.js` and run via `browser act kind=evaluate script="..." timeoutMs=30000 profile="ashby"`.
Parse the returned JSON.

### Phase 3: Combobox Dropdowns (Playwright)
For each entry in `comboboxFields[]`:
1. Click the combobox using its `ariaRef` or `selector`
2. Type the `targetValue` text
3. Wait 500ms for the dropdown filter
4. Press Enter to select
5. Take snapshot to verify

### Phase 4: Toggle Button Verification (CRITICAL)
form-filler.js fills toggles with `simulateRealClick()` (full pointer event chain: pointerdown → mousedown → pointerup → mouseup → click → focus). However, **JS clicks may only set CSS active class without updating React internal state**.

For EACH filled field with `method: "ashby-toggle-click"`:
1. Take snapshot and verify the button shows correct visual state (selected/highlighted)
2. If the toggle appears WRONG or unselected:
   - Use **Playwright `click`** on the button's aria-ref: `browser act kind=click ref="<ref>" profile="ashby"`
   - Playwright clicks go through the browser's real event pipeline and reliably update React state
   - Take another snapshot to confirm
3. Common toggles to verify: work authorization (Yes), visa sponsorship (Yes), gender/race (Decline)

**Why Playwright clicks work but JS doesn't always:** Ashby toggle buttons use React synthetic events. JS `dispatchEvent()` creates native DOM events that bypass React's event delegation. Playwright clicks trigger events at the browser level, which React captures via its root event listener.

### Phase 5: Resume Upload
Use the upload action with ref from `fileUploadSelectors`:
```
browser act kind=upload paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] inputRef="<ref>" timeoutMs=60000 profile="ashby"
```
If `fileUploadFound: false` or "file already uploaded" in skipped: skip this step.

### Phase 6: Custom Questions
If `customQuestions[]` is non-empty:
- Read `SOUL.md` for voice/tone
- For essays (200+ words): use `sessions_spawn` with Opus to write tailored response
- For short answers: fill inline from context
- Run `skills/apply-ashby/scripts/fill-custom-answers.js` via evaluate to inject answers

### Phase 7: Submit
- Take fresh snapshot. Verify all required fields are filled.
- Click submit button using `submitButtonRef`.
- Ashby is direct submit — NO email verification needed.
- Take post-submit snapshot. Verify "application submitted" or similar confirmation.
- If CAPTCHA appears: WhatsApp Howard, mark SKIPPED.

### Phase 8: Post-Submit
```
exec: python3 scripts/mark-applied.py "<url>" "<Company>" "<Title>"
```
Append to `job-tracker.md`:
```markdown
### Company — Title
- **Stage:** Applied
- **Date Applied:** YYYY-MM-DD
- **Source:** Ashby
- **Link:** <url>
- **Notes:** [brief]
- **Follow-up Due:** YYYY-MM-DD (5 days from now)
```

**LOOP:** Pick next Ashby job. Continue until timeout (max 5 per cycle).

### Phase 9: Session Memory
Before timeout, append 3-line summary to `memory/session-YYYY-MM-DD.md`:
```
## Apply Ashby — HH:MM CT
- Attempted: N, Completed: N, Skipped: N
- Companies: [list]
```

## Ashby-Specific Notes
- Toggle buttons use full pointer event chain (pointerdown/mousedown/pointerup/mouseup/click/focus)
- `/application` URL loads async — wait 5s before checking for 404
- Application limits are **PER-EMPLOYER**. Only **Sesame AI** is blocked (90-day limit reached). All other Ashby companies are fine.
- No CAPTCHA, no email verification — clean direct forms
- Typical form: name, email, phone, resume, LinkedIn, 2-3 yes/no toggles, 0-2 essay questions

## Browser Safety Rules
- **SVG className bug:** In evaluate scripts, NEVER use `el.className.substring()` or `el.className.includes()`. SVG elements return `SVGAnimatedString` (not a string). Use `el.getAttribute('class') || ''` instead.
- **Narrow selectors:** Never use broad selectors like `button, [class*=code]` — Ashby forms have hundreds of buttons. Always scope selectors to a specific section (e.g. `document.querySelector('.captcha-container button')`).
- **Stale refs:** After any page change, navigation, or long delay, take a fresh snapshot before clicking elements. Old ref IDs (e.g. "e9", "e18") become invalid.

## Skip Rules
- Sesame AI: per-employer limit reached → SKIP
- OpenAI: NO-AUTO (already filtered by `--actionable`)
- CAPTCHA: SKIP + WhatsApp Howard
- 3 failed retries on same job: SKIP with reason
- Check `skip-companies.json` — companies listed there must be SKIPPED
