---
name: apply-greenhouse
description: Greenhouse ATS application agent. Handles MyGreenhouse autofill, React-select comboboxes, email verification.
---

# Apply Greenhouse — Application Skill

## Browser Profile
Always use `profile="greenhouse"` for ALL browser actions (snapshot, navigate, act, upload).

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 10
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
- `browser navigate <url> profile="greenhouse"`
- Wait 5s. Take snapshot.
- Handle cookie/privacy popups.
- If iframe (company career page wrapping `boards.greenhouse.io`): navigate to the direct Greenhouse URL.

### Phase 1.5: MyGreenhouse Autofill
If "Autofill with MyGreenhouse" button is visible:
1. Click it. Wait 5s for autofill to complete.
2. **ALWAYS verify and fix after autofill:**
   - First Name MUST be **"Howard"** (not "Haoyuan") — fix if wrong
   - Disability Status MUST be **"I do not wish to answer"** — fix if wrong
3. Take snapshot to confirm fixes applied.

If no MyGreenhouse button: proceed to Phase 2.

### Phase 2: Fill Form
Copy resume first:
```
exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
```
Read `skills/apply-greenhouse/scripts/form-filler.js` and run via `browser act kind=evaluate script="..." timeoutMs=30000 profile="greenhouse"`.
Parse the returned JSON.

### Phase 3: Combobox Dropdowns (CRITICAL for Greenhouse)
Greenhouse uses React-select combobox components extensively. For EACH entry in `comboboxFields[]`:
1. Click the combobox ref to open the dropdown
2. Type the `targetValue` text
3. Wait 500ms for the filter to populate
4. Press Enter to select the first match
5. Take snapshot to verify selection

**Common Greenhouse comboboxes:**
- Phone country code → type "United States", Enter
- Work authorization → type "Yes", Enter
- Visa sponsorship → type "Yes", Enter
- Gender/Race → type "Decline", Enter
- Disability → type "I do not wish", Enter

### Phase 4: Resume Upload
Greenhouse uses button-based uploads ("Attach" button). The `input[type=file]` may be hidden.
```
browser act kind=upload paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] ref="<attach-button-ref>" timeoutMs=60000 profile="greenhouse"
```
If "file already uploaded" in skipped results: skip upload.
**NEVER click the Attach button with a regular click** — use the upload action.

### Phase 5: Custom Questions
If `customQuestions[]` is non-empty:
- Read `SOUL.md` for voice/tone
- For essays (200+ words): use `sessions_spawn` with Opus
- For short answers: fill inline
- Run `skills/apply-greenhouse/scripts/fill-custom-answers.js` via evaluate

### Phase 6: Submit
- Take fresh snapshot. Verify all required fields are filled (check for red outlines / error messages).
- Click submit button using `submitButtonRef`.
- Take post-submit snapshot.

### Phase 6.5: Email Verification (REQUIRED for Greenhouse)
After submit, if "verification code" or "security code" text appears:
1. Wait 10s for the email to arrive
2. Fetch code:
   ```
   exec: gog gmail search 'from:greenhouse subject:security code' --account cheng.howard1@gmail.com --json
   ```
3. Read the latest thread to extract the **8-character alphanumeric code**
4. Type the first character into the first textbox (the rest auto-advance)
5. Click Submit/Verify
6. Verify "Thank you for applying" confirmation page
7. If no email after 30s: retry search once. Still nothing: WhatsApp Howard, mark SKIPPED.

### Phase 7: Post-Submit
```
exec: python3 scripts/mark-applied.py "<url>" "<Company>" "<Title>"
```
Append to `job-tracker.md`:
```markdown
### Company — Title
- **Stage:** Applied
- **Date Applied:** YYYY-MM-DD
- **Source:** Greenhouse
- **Link:** <url>
- **Notes:** [brief]
- **Follow-up Due:** YYYY-MM-DD (5 days from now)
```

**LOOP:** Pick next Greenhouse job. Continue until timeout (max 5 per cycle).

### Phase 8: Session Memory
Before timeout, append 3-line summary to `memory/session-YYYY-MM-DD.md`.

## Greenhouse-Specific Notes
- MyGreenhouse autofill handles ~80% of standard fields — always try it first
- Combobox dropdowns are the main challenge: React-select components need Playwright click+type+Enter
- Phone field often has a separate country code combobox — set to "United States" first
- Email verification is required after EVERY submit (8-char code via Gmail)
- Forms can have 30-50+ fields (most auto-filled by MyGreenhouse)
- "Remove file" button means resume is already uploaded — skip upload step

## Skip Rules
- Databricks: cross-origin iframe cannot be automated → SKIP
- CAPTCHA: SKIP + WhatsApp Howard
- 3 failed retries: SKIP with reason
