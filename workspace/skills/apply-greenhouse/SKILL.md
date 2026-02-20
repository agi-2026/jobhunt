---
name: apply-greenhouse
description: Greenhouse ATS application agent. Handles MyGreenhouse autofill, React-select comboboxes, email verification.
---

# Apply Greenhouse — Application Skill

## Browser Profile
Always use `profile="greenhouse"` for ALL browser actions (snapshot, navigate, act, upload).
Never pass `targetId` in browser actions. Ignore `targetId` values returned by browser tools.
Browser tool schema reminder (CRITICAL):
- JS execution must use `action="act"` with nested `request.kind="evaluate"`.
- For ALL `action="act"` calls, put click/type/evaluate params inside `request={...}`.
- File upload uses `action="upload"` with top-level `paths` and `element|ref|inputRef` (not `request.kind="upload"`).
- `action="evaluate"` is invalid and will fail.
- Top-level `kind/ref/text/paths` with `action="act"` can fail with `request required`.
- Canonical evaluate call shape: `{"action":"act","profile":"greenhouse","request":{"kind":"evaluate","fn":"<full_js_source>","timeoutMs":30000}}`

## Metadata-First Retrieval (CRITICAL)
Before reading large files:
- `exec: python3 scripts/context-manifest.py list --profile apply-greenhouse --limit 20`
- `exec: python3 scripts/tool-menu.py --profile greenhouse --json`
- Use `exec: python3 scripts/context-manifest.py read <entry_id> --section "<heading>" --max-lines 180` for targeted reads.
- In apply runs, use only `exec` + `browser` + `process` tools. Do not use `read`/`write`/`edit` tools.
- Avoid direct full-file reads unless manifest access fails.

## Single-Job Guardrail (CRITICAL)
- Work exactly **ONE URL per subagent run**.
- After selecting the top queued Greenhouse URL, do not open any other job URL in this run.
- Stay on that job until one terminal outcome: `SUBMITTED`, `SKIPPED`, or `DEFERRED`.
- If terminal outcome is reached, stop the run and unlock.
- Do not start a second application in the same subagent run.

## Runtime Budget (CRITICAL)
- Target completion time: 5-9 minutes per job (Greenhouse may include email verification).
- If no terminal outcome after 9 minutes, set terminal outcome `DEFERRED` and STOP this run.
- On browser infrastructure errors (`Can't reach the OpenClaw browser control service`, `browser connection lost`, `target closed`, `service unavailable`), stop retrying immediately, set terminal outcome `DEFERRED`, and STOP this run.
- Never spend more than 90 seconds retrying infrastructure failures.
- Snapshot budget: max 4 full snapshots per run (one pre-submit, one post-submit, plus targeted troubleshooting).

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 10 --full-url
```
Pick the highest-score PENDING job directly from this output (URL is already full and exact).
Do NOT read `job-queue.md` for URL lookup.

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

### Phase 1: Navigate
- `browser navigate <url> profile="greenhouse"`
- Wait 3-5s.
- Do NOT take a full snapshot immediately after navigate.
- Handle cookie/privacy popups.
- If page is 404 / expired: remove from queue, set terminal outcome `SKIPPED`, and STOP this run.
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
Read `skills/apply-greenhouse/scripts/form-filler.js` and run via browser `action="act"` with `request={"kind":"evaluate","fn":"...","timeoutMs":30000}` and `profile="greenhouse"`.
Load canonical JS via manifest immediately before evaluate:
```
exec: python3 scripts/context-manifest.py read greenhouse_form_filler --max-lines 1400 --raw
```
When running evaluate:
- Paste the **entire file contents** exactly (starts with `(function() {`).
- Do **NOT** run `formFiller()` or any symbol-only snippet.
- If error contains `formFiller is not defined`, re-read the file and re-run once with full file contents.
Parse the returned JSON.

### Phase 3: Combobox Dropdowns (CRITICAL for Greenhouse)
Greenhouse uses React-select combobox components extensively. For EACH entry in `comboboxFields[]`:
1. Click the combobox ref to open the dropdown
2. Type the `targetValue` text
3. Wait 500ms for the filter to populate
4. **If dropdown shows 0 results**: clear the text, try each value from `alternativeValues[]` until one matches
5. Press Enter to select the first match
6. Take snapshot to verify selection

**Common Greenhouse comboboxes:**
- Phone country code → type "United States", Enter
- Work authorization → type "Yes", Enter
- Visa sponsorship → type "Yes", Enter
- Gender/Race → type "Decline", Enter
- Disability → type "wish to answer", Enter. If 0 results → try "don't wish" → "prefer not" → "decline"

### Phase 4: Resume Upload
Greenhouse uses button-based uploads ("Attach" button) with a hidden `input[type=file]`.

**Preferred method** — use `inputElement` from `fileUploadSelectors` (the hidden file input found by form-filler.js):
```
browser action="upload" profile="greenhouse" paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] element="<inputElement from fileUploadSelectors>" timeoutMs=60000
```
**Fallback** — if `inputElement` is null (no hidden input found), use the button ref:
```
browser action="upload" profile="greenhouse" paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] ref="<attach-button-ref>" timeoutMs=60000
```

**After upload, ALWAYS run verify-upload.js** to re-dispatch React events:
Load helper only when needed:
`exec: python3 scripts/context-manifest.py read greenhouse_verify_upload --max-lines 220 --raw`
Then run:
```
browser action="act" profile="greenhouse" request={"kind":"evaluate","fn":"<contents of scripts/verify-upload.js>","timeoutMs":10000}
```
Check the returned JSON: if `verified: false` or errors mention validation, take a snapshot and retry.

If "file already uploaded" in skipped results: skip upload entirely.
**NEVER click the Attach button with a regular click** — always use the upload action.
Never upload by typing a file path into a button/text input. Use `action="upload"` only.

### Phase 5: Custom Questions
If `customQuestions[]` is non-empty:
- Generate concise, truthful answers from resume/profile context. Do not invent specific facts.
- Build `window.__CUSTOM_ANSWERS__` as an array of `{ selector, value, type }` using entries from `customQuestions[]`.
- Set answers payload:
  `browser action="act" profile="greenhouse" request={"kind":"evaluate","fn":"window.__CUSTOM_ANSWERS__ = <JSON_ARRAY>"}`
- Load custom-answer helper only when needed:
  `exec: python3 scripts/context-manifest.py read greenhouse_custom_answers --max-lines 260 --raw`
  then run it via:
  `browser action="act" profile="greenhouse" request={"kind":"evaluate","fn":"...","timeoutMs":30000}`
- If required custom-question validation still fails after up to 2 correction attempts, set terminal outcome `DEFERRED`.

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
4. **Fill code using atomic script (DO NOT type characters one-by-one):**
   a. Set the code: `browser action="act" profile="greenhouse" request={"kind":"evaluate","fn":"window.__VERIFY_CODE = '<CODE>'"}`
   b. Load helper via `exec: python3 scripts/context-manifest.py read greenhouse_verify_code --max-lines 220 --raw`
      and run via `browser action="act" profile="greenhouse" request={"kind":"evaluate","fn":"..."}`
   c. Parse returned JSON — if `filled: true`, proceed. If `error`, fall back to step 4d.
   d. **Fallback only:** Take snapshot, find the FIRST verification code input box (small single-char inputs near "verification code" text at BOTTOM of page — NOT regular form fields at top), type code character-by-character into those specific inputs.
5. Click Submit/Verify button
6. Verify "Thank you for applying" confirmation page
7. If no email after 30s: retry search once. Still nothing: WhatsApp Howard, mark SKIPPED.

### Submission Integrity Rule (CRITICAL)
- Only run `mark-applied.py` after final success confirmation is visible (for Greenhouse typically "Thank you for applying" after verification).
- If confirmation is absent, do NOT mark applied.
- If ambiguous after retries, set `DEFERRED` and stop.

**CRITICAL:** The verification code boxes are at the BOTTOM of the page near the submit area. Do NOT type into any form fields at the top of the page. The code inputs are small single-character boxes (maxlength=1) grouped together.

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

Do not loop to another job in this run. End after this single job reaches terminal outcome.

### Phase 8: Session Memory
Before timeout, append 3-line summary to `memory/session-YYYY-MM-DD.md`.

## Greenhouse-Specific Notes
- MyGreenhouse autofill handles ~80% of standard fields — always try it first
- Combobox dropdowns are the main challenge: React-select components need Playwright click+type+Enter
- Phone field often has a separate country code combobox — set to "United States" first
- Email verification is required after EVERY submit (8-char code via Gmail)
- Forms can have 30-50+ fields (most auto-filled by MyGreenhouse)
- "Remove file" button means resume is already uploaded — skip upload step

## Browser Safety Rules
- **SVG className bug:** In evaluate scripts, NEVER use `el.className.substring()` or `el.className.includes()`. SVG elements return `SVGAnimatedString` (not a string). Use `el.getAttribute('class') || ''` instead.
- **Narrow selectors for verification code:** When looking for the email verification code input, NEVER use broad selectors like `locator('button, [class*=security], [class*=verify], [class*=code]')` — this matches 200+ elements (country dial code buttons, etc.). Instead, look specifically for:
  - Text containing "verification code" or "security code" on the page
  - Small `input[maxlength="1"]` elements near that text
  - Or use the atomic `greenhouse-verify-code.js` script which handles this correctly
- **Stale refs:** After any page change, navigation, or long delay, take a fresh snapshot before clicking elements. Old ref IDs (e.g. "e9", "e18") become invalid.
- On stale-ref errors (`Unknown ref`, `not found`, `not visible`): take fresh snapshot and retry the SAME action once; do not switch jobs/pages.

## Skip Rules
- Databricks: cross-origin iframe cannot be automated → SKIP
- CAPTCHA: SKIP + WhatsApp Howard
- 3 failed retries: SKIP with reason
- Check `skip-companies.json` — companies listed there must be SKIPPED

On SKIP/DEFER for this job, stop the run. Do not open another URL.
