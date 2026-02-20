---
name: apply-ashby
description: Ashby ATS application agent. Fills toggle buttons, combobox dropdowns, uploads resume, submits.
---

# Apply Ashby — Application Skill

## Browser Profile
Always use `profile="ashby"` for ALL browser actions (snapshot, navigate, act, upload).

## Single-Job Guardrail (CRITICAL)
- Work exactly **ONE URL per subagent run**.
- After selecting the top queued Ashby URL, do not open any other job URL in this run.
- Stay on that job until one terminal outcome: `SUBMITTED`, `SKIPPED`, or `DEFERRED`.
- If terminal outcome is reached, stop the run and unlock.
- Do not start a second application in the same subagent run.

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats ashby --top 1 --full-url
```
Pick the highest-score PENDING job directly from this output (URL is already full and exact).
Do NOT read `job-queue.md` for URL lookup.
Do NOT run `queue-summary.py` a second time in the same subagent run.

## Application Flow

### Phase 0: Pre-flight
```
exec: python3 scripts/preflight-check.py "<url>"
```
If `DEAD`: remove with `exec: python3 scripts/remove-from-queue.py "<url>"`, set terminal outcome `SKIPPED`, and STOP this run. Do not pick another URL.

### Phase 0.5: Connection Search (score >= 280)
```
exec: python3 scripts/search-connections.py "<Company Name>"
```
If mutual connections found, record them for manual follow-up notes.

### Phase 1: Navigate
- `browser navigate <url> profile="ashby"`
- Wait 5s (Ashby loads async). Take snapshot.
- Handle cookie consent / popups.
- If 404 / expired page: skip, remove from queue, set terminal outcome `SKIPPED`, and STOP this run.
- If `iframeDetected`: navigate to `iframeUrl` directly.

### Phase 2: Fill Form
Copy resume first:
```
exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
```
Read `skills/apply-ashby/scripts/form-filler.js` and run via `browser act kind=evaluate script="..." timeoutMs=30000 profile="ashby"`.
When running evaluate:
- Paste the **entire file contents** exactly (starts with `(function() {`).
- Do **NOT** run `formFiller()` or any symbol-only snippet.
- If error contains `formFiller is not defined`, re-read the file and re-run once with full file contents.
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
   - Take one more snapshot to confirm
3. Common toggles to verify: work authorization (Yes), visa sponsorship (Yes), gender/race (Decline)
4. Max one verification pass. Do not loop on repeated evaluate checks.
5. Do not use ad-hoc evaluate scripts to infer selected state from `aria-pressed`/`aria-checked` for Ashby yes/no buttons.

**Why Playwright clicks work but JS doesn't always:** Ashby toggle buttons use React synthetic events. JS `dispatchEvent()` creates native DOM events that bypass React's event delegation. Playwright clicks trigger events at the browser level, which React captures via its root event listener.

### Phase 5: Resume Upload
Use the upload action with ref from `fileUploadSelectors`:
```
browser upload paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] inputRef="<ref>" timeoutMs=60000 profile="ashby"
```
If `fileUploadFound: false` or "file already uploaded" in skipped: skip this step.
Never upload by typing a file path into a button/text input. Use the `browser upload` action only.
Never pass a button ref (e.g. `Upload File`) to upload; use the actual file input ref/selector from `fileUploadSelectors`.
If upload action returns `{ "ok": true }`, treat upload as successful for this run.
Do not require `input.files` checks from evaluate scripts; browser security often keeps file state hidden there.
If upload action errors, refresh snapshot and retry upload once, then continue to submit/correction flow.

### Phase 6: Custom Questions
If `customQuestions[]` is non-empty:
- Generate concise, truthful answers from resume/profile context. Do not invent specific facts.
- Build `window.__CUSTOM_ANSWERS__` as an array of `{ selector, value, type }` using entries from `customQuestions[]`.
- Set answers payload:
  `browser act kind=evaluate script="window.__CUSTOM_ANSWERS__ = <JSON_ARRAY>" profile="ashby"`
- Read `skills/apply-ashby/scripts/fill-custom-answers.js` and run it via:
  `browser act kind=evaluate script="..." timeoutMs=30000 profile="ashby"`
- If required custom-question validation still fails after up to 2 correction attempts, set terminal outcome `DEFERRED`.

### Phase 7: Submit
- Take fresh snapshot. Verify all required fields are filled.
- Click submit button using `submitButtonRef`.
- Ashby is direct submit — NO email verification needed.
- Take post-submit snapshot and verify a clear success marker ("application submitted", "thanks for applying", or equivalent).
- If you see validation alert `Your form needs corrections`:
  - Read missing fields list and fix immediately before any other action.
  - For `Name` and `Linkedin`, use Playwright typing (click field ref → select all → type value again), then blur.
  - For `Resume`, run `browser upload`; if it returns `{ "ok": true }`, accept it and continue.
  - Re-submit and snapshot again.
  - Max 2 correction cycles, then `DEFERRED`.
- If CAPTCHA appears: WhatsApp Howard, mark SKIPPED.

### Submission Integrity Rule (CRITICAL)
- Only run `mark-applied.py` after post-submit success is explicitly confirmed by snapshot.
- If success text is not present, do NOT mark applied.
- If submit result is ambiguous after 2 retries/snapshots, mark as `DEFERRED` (not applied) and stop.

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

Do not loop to another job in this run. End after this single job reaches terminal outcome.

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
- On stale-ref errors (`Unknown ref`, `not found`, `not visible`): take fresh snapshot and retry the SAME action once; do not switch jobs/pages.

## Skip Rules
- Sesame AI: per-employer limit reached → SKIP
- OpenAI: NO-AUTO (already filtered by `--actionable`)
- CAPTCHA: SKIP + WhatsApp Howard
- 3 failed retries on same job: SKIP with reason
- Check `skip-companies.json` — companies listed there must be SKIPPED

On SKIP/DEFER for this job, stop the run. Do not open another URL.
