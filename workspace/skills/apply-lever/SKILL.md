---
name: apply-lever
description: Lever ATS application agent. Simple native forms, resume upload, direct submit. Ref staleness mitigation.
---

# Apply Lever — Application Skill

## STATUS: DISABLED (2026-02-17)
All Lever forms now include invisible hCaptcha verification. Headless Chrome cannot solve hCaptcha. The orchestrator no longer dispatches Lever subagents. Lever jobs remain in the queue for Howard to apply manually.

## Browser Profile
Always use `profile="lever"` for ALL browser actions (snapshot, navigate, act, upload).

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats lever --top 10
```
Pick highest-score PENDING job. Read just that job's entry from `job-queue.md` to get URL.

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

### Phase 1: Navigate
- `browser navigate <url> profile="lever"`
- Wait 3s. Take snapshot.
- Handle cookie consent popups.
- If 404 / expired: skip, remove from queue.

### Phase 2: Fill Form
Copy resume first:
```
exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
```
Read `skills/apply-lever/scripts/form-filler.js` and run via `browser act kind=evaluate script="..." timeoutMs=30000 profile="lever"`.
Parse the returned JSON.

**Lever uses native HTML forms** — no React comboboxes, no toggle buttons. The form-filler handles everything via JS. No Playwright interaction needed for dropdowns (native `<select>` elements).

### Phase 2.5: Playwright Re-fill (if needed)
If `playwrightFields[]` is non-empty, re-type those fields using Playwright:
```
browser act kind=type ref="<ref or selector>" text="<value>" profile="lever"
```
**Location field** is the most common — JS setNativeValue doesn't trigger Lever's autocomplete, so the value doesn't persist. Playwright `type` sends real keyboard events that activate the autocomplete.

### Phase 3: Resume Upload
**CRITICAL: All form fields MUST be filled BEFORE uploading resume.** Lever's form validation checks all fields when upload triggers. If fields (especially LinkedIn) are empty at upload time, the upload validation fails silently.

Wait 1-2 seconds after Phase 2/2.5 completes, then upload:
Use `inputElement` from `fileUploadSelectors` (returned by form-filler.js) for a precise selector:
```
browser act kind=upload paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] element="<inputElement from fileUploadSelectors>" timeoutMs=60000 profile="lever"
```
If `inputElement` is not available, fallback to `element="input[type=file]"`.

**After upload, ALWAYS run verify-upload.js** to re-dispatch React events:
```
browser act kind=evaluate script="<contents of scripts/verify-upload.js>" timeoutMs=10000 profile="lever"
```
Check the returned JSON: if `verified: false` or errors mention validation, take a snapshot and retry upload.

### Phase 4: Custom Questions
If `customQuestions[]` is non-empty:
- Read `SOUL.md` for voice/tone
- For "Additional Info" textarea on high-score jobs (280+): write 2-3 sentence cover letter mentioning company fit
- For other jobs: brief relevant note or "See resume"
- Run `skills/apply-lever/scripts/fill-custom-answers.js` via evaluate

### Phase 5: Submit
- Take fresh snapshot. Verify all required fields filled.
- Click submit button using `submitButtonRef`.
- Lever is **direct submit** — NO email verification needed, NO CAPTCHA typically.
- Take post-submit snapshot. Verify confirmation.

### Phase 6: Post-Submit
```
exec: python3 scripts/mark-applied.py "<url>" "<Company>" "<Title>"
```
Append to `job-tracker.md`:
```markdown
### Company — Title
- **Stage:** Applied
- **Date Applied:** YYYY-MM-DD
- **Source:** Lever
- **Link:** <url>
- **Notes:** [brief]
- **Follow-up Due:** YYYY-MM-DD (5 days from now)
```

**LOOP:** Pick next Lever job. Continue until timeout (max 5 per cycle).

### Phase 7: Session Memory
Before timeout, append 3-line summary to `memory/session-YYYY-MM-DD.md`.

## Ref Staleness Mitigation (CRITICAL for Lever)
Lever forms can cause browser refs to go stale on large pages. Strategy:
1. Run form-filler.js FIRST — it fills 80%+ of fields via JS in one evaluate call
2. Only use Playwright for resume upload and submit click
3. If ANY Playwright action fails with "stale element" or "element not found":
   - Take a fresh snapshot to get new refs
   - Retry the action with the new ref
4. Limit to 3 retries per action. If still failing: SKIP with reason.
5. If page has been open >60s, take a fresh snapshot before each Playwright action.

## Lever-Specific Notes
- Simplest ATS: usually name, email, phone, resume, LinkedIn, optional additional info
- No CAPTCHA, no email verification, direct submit
- Native HTML `<select>` dropdowns — all filled by JS (no Playwright needed for dropdowns)
- Fastest target: 2-4 minutes per application when working correctly
- Main failure mode is ref staleness, not form complexity

## Browser Safety Rules
- **SVG className bug:** In evaluate scripts, NEVER use `el.className.substring()` or `el.className.includes()`. SVG elements return `SVGAnimatedString` (not a string). Use `el.getAttribute('class') || ''` instead.
- **Narrow selectors:** Never use broad selectors like `button, [class*=code]`. Always scope to a specific section.

## Skip Rules
- CAPTCHA (rare on Lever): SKIP + WhatsApp Howard
- 3 failed retries: SKIP with reason
- Non-US locations: SKIP (verify location before applying)
- Check `skip-companies.json` — companies listed there must be SKIPPED
