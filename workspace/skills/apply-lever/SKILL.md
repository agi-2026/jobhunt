---
name: apply-lever
description: Lever ATS application agent. Simple native forms, resume upload, direct submit. Ref staleness mitigation.
---

# Apply Lever — Application Skill

## Browser Profile
Always use `profile="lever"` for ALL browser actions (snapshot, navigate, act, upload).
Never pass `targetId` in browser actions. Ignore `targetId` values returned by browser tools.
Browser tool schema reminder (CRITICAL):
- JS execution must use `action="act"` with nested `request.kind="evaluate"`.
- For ALL `action="act"` calls, put click/type/evaluate params inside `request={...}`.
- File upload uses `action="upload"` with top-level `paths` and `element|ref|inputRef` (not `request.kind="upload"`).
- `action="evaluate"` is invalid and will fail.
- Top-level `kind/ref/text/paths` with `action="act"` can fail with `request required`.
- Canonical evaluate call shape: `{"action":"act","profile":"lever","request":{"kind":"evaluate","fn":"<full_js_source>","timeoutMs":30000}}`

## Metadata-First Retrieval (CRITICAL)
Before reading large files:
- `exec: python3 scripts/context-manifest.py list --profile apply-lever --limit 20`
- `exec: python3 scripts/tool-menu.py --profile lever --json`
- Use `exec: python3 scripts/context-manifest.py read <entry_id> --section "<heading>" --max-lines 180` for targeted reads.
- In apply runs, use only `exec` + `browser` + `process` tools. Do not use `read`/`write`/`edit` tools.
- Avoid direct full-file reads unless manifest access fails.

## Single-Job Guardrail (CRITICAL)
- Work exactly **ONE URL per subagent run**.
- After selecting the top queued Lever URL, do not open any other job URL in this run.
- Stay on that job until one terminal outcome: `SUBMITTED`, `SKIPPED`, or `DEFERRED`.
- If terminal outcome is reached, stop the run and unlock.
- Do not start a second application in the same subagent run.

## Runtime Budget (CRITICAL)
- Target completion time: 4-8 minutes per job.
- If no terminal outcome after 8 minutes, set terminal outcome `DEFERRED` and STOP this run.
- On browser infrastructure errors (`Can't reach the OpenClaw browser control service`, `browser connection lost`, `target closed`, `service unavailable`), stop retrying immediately, set terminal outcome `DEFERRED`, and STOP this run.
- Never spend more than 90 seconds retrying infrastructure failures.
- Snapshot budget: max 3 full snapshots per run. Avoid repeated full snapshots unless required for submit/captcha troubleshooting.

## Queue Selection
```
exec: python3 scripts/queue-summary.py --actionable --ats lever --top 10 --full-url
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
- `browser navigate <url> profile="lever"`
- Wait 2-3s.
- Do NOT take a full snapshot immediately after navigate.
- Handle cookie consent popups only if they visibly block interaction.
- If 404 / expired: skip, remove from queue, set terminal outcome `SKIPPED`, and STOP this run.

### Phase 2: Fill Form
Copy resume first:
```
exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
```
Read `skills/apply-lever/scripts/form-filler.js` and run via browser `action="act"` with `request={"kind":"evaluate","fn":"...","timeoutMs":30000}` and `profile="lever"`.
Load canonical JS via manifest immediately before evaluate:
```
exec: python3 scripts/context-manifest.py read lever_form_filler --max-lines 1400 --raw
```
When running evaluate:
- Paste the **entire file contents** exactly (starts with `(function() {`).
- Do **NOT** run `formFiller()` or any symbol-only snippet.
- If error contains `formFiller is not defined`, re-read the file and re-run once with full file contents.
- Run the form-filler evaluate directly after navigation (before first full snapshot) to reduce context and latency.
Parse the returned JSON.

**Lever uses native HTML forms** — no React comboboxes, no toggle buttons. The form-filler handles everything via JS. No Playwright interaction needed for dropdowns (native `<select>` elements).

### Phase 2.5: Playwright Re-fill (if needed)
If `playwrightFields[]` is non-empty, re-type those fields using Playwright:
```
browser action="act" profile="lever" request={"kind":"type","ref":"<ref or selector>","text":"<value>"}
```
**Location field** is the most common — JS setNativeValue doesn't trigger Lever's autocomplete, so the value doesn't persist. Playwright `type` sends real keyboard events that activate the autocomplete.

### Phase 3: Resume Upload
**CRITICAL: All form fields MUST be filled BEFORE uploading resume.** Lever's form validation checks all fields when upload triggers. If fields (especially LinkedIn) are empty at upload time, the upload validation fails silently.

Wait 1-2 seconds after Phase 2/2.5 completes, then upload:
Use `inputElement` from `fileUploadSelectors` (returned by form-filler.js) for a precise selector:
```
browser action="upload" profile="lever" paths=["/tmp/openclaw/uploads/Resume_Howard.pdf"] element="<inputElement from fileUploadSelectors>" timeoutMs=60000
```
If `inputElement` is not available, fallback to `element="input[type=file]"`.

**After upload, ALWAYS run verify-upload.js** to re-dispatch React events:
Load helper only when needed:
`exec: python3 scripts/context-manifest.py read lever_verify_upload --max-lines 220 --raw`
Then run:
```
browser action="act" profile="lever" request={"kind":"evaluate","fn":"<contents of scripts/verify-upload.js>","timeoutMs":10000}
```
Check the returned JSON: if `verified: false` or errors mention validation, take a snapshot and retry upload.

### Phase 4: Custom Questions
If `customQuestions[]` is non-empty:
- Generate concise, truthful answers from resume/profile context. Do not invent specific facts.
- Build `window.__CUSTOM_ANSWERS__` as an array of `{ selector, value, type }` using entries from `customQuestions[]`.
- Set answers payload:
  `browser action="act" profile="lever" request={"kind":"evaluate","fn":"window.__CUSTOM_ANSWERS__ = <JSON_ARRAY>"}`
- Load custom-answer helper only when needed:
  `exec: python3 scripts/context-manifest.py read lever_custom_answers --max-lines 260 --raw`
  then run it via:
  `browser action="act" profile="lever" request={"kind":"evaluate","fn":"...","timeoutMs":30000}`
- If required custom-question validation still fails after up to 2 correction attempts, set terminal outcome `DEFERRED`.

### Phase 5: Submit
- Take fresh snapshot. Verify all required fields filled.
- Click submit button using `submitButtonRef`.
- Take post-submit snapshot.

### Phase 5.5: hCaptcha Challenge (if present)
After clicking submit, hCaptcha may appear as an overlay (image grid or audio challenge).

**Detection:**
If the post-submit snapshot shows a CAPTCHA challenge (image grid, checkbox, or audio prompt), proceed.
Optionally load detector for metadata:
`exec: python3 scripts/context-manifest.py read lever_detect_hcaptcha --max-lines 220 --raw`

**Strategy: Audio-first (Whisper ASR), visual fallback. Max 5 total rounds.**

#### Audio Path — try first (up to 3 rounds):

1. Run the Whisper audio solver. It automatically clicks the audio button, waits for audio to load,
   downloads it, and transcribes via Whisper ASR:
   ```
   exec: python3 scripts/solve-hcaptcha-audio.py
   ```
   - **Exit 0**: stdout contains the answer (e.g. `3 7 2 4 1 5`). Call this `AUDIO_ANSWER`.
   - **Exit 1**: audio path unavailable or transcription empty → skip to Visual Path.

2. Take a fresh snapshot to see the current hCaptcha UI (now showing audio input box + Verify button).

3. Locate the text input box inside the hCaptcha challenge area.
   It is cross-origin, so use coordinate-based click at the center of the input:
   ```
   browser action="act" profile="lever" request={"kind":"click","x":<X>,"y":<Y>}
   ```

4. Type the answer:
   ```
   browser action="act" profile="lever" request={"kind":"type","text":"<AUDIO_ANSWER>"}
   ```

5. Click the Verify button (coordinate-based, bottom of challenge modal):
   ```
   browser action="act" profile="lever" request={"kind":"click","x":<X>,"y":<Y>}
   ```

6. Take a post-verify snapshot:
   - Confirmation page / form gone → **SUCCESS** → proceed to Phase 6.
   - "Please try again" or new challenge → increment audio round, repeat from step 1.
   - After 3 failed audio rounds → switch to Visual Path below.

#### Visual Path — fallback (remaining rounds up to 5 total):

1. Take a snapshot — the hCaptcha modal shows:
   - A prompt at the top (e.g., "Please click each image containing a **motorbus**")
   - A 3x3 or 4x4 grid of images
   - A "Verify" button at the bottom
2. Analyze each grid image carefully. Identify ALL images matching the prompt.
3. Click each matching image using coordinate-based clicking:
   ```
   browser action="act" profile="lever" request={"kind":"click","x":<X>,"y":<Y>}
   ```
   where X,Y are the CENTER coordinates of each matching grid cell. Wait ~200ms between clicks.
4. Click the Verify button.
5. Take a snapshot:
   - Confirmation page → **SUCCESS** → proceed to Phase 6.
   - New round → repeat (counting against the 5-round total limit).
   - "Please try again" → retry the same round.

**If still unsolved after 5 total rounds (audio + visual combined):**
```
exec: python3 scripts/remove-from-queue.py "<url>" --reason "hCaptcha unsolved after 5 rounds"
```
Set terminal outcome `DEFERRED`. Do not open another URL.

**Tips:**
- Audio answer is digits spoken slowly. Whisper transcription is usually exact.
- If Whisper returns letters/words instead of digits, audio path failed — use visual.
- Visual: "motorbus" = bus, "vertical river" = waterfall, "seaplane" = plane on water.
- Select ALL matching images — missing one fails the round.

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

Do not loop to another job in this run. End after this single job reaches terminal outcome.

### Submission Integrity Rule (CRITICAL)
- Only run `mark-applied.py` when submit confirmation is clearly visible.
- If confirmation is missing/ambiguous, do NOT mark applied.
- Set `DEFERRED` and stop this run.

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
- hCaptcha present on many Lever forms since Feb 2026. Audio-first solve (Whisper ASR via solve-hcaptcha-audio.py), visual fallback. Phase 5.5. Max 5 rounds total.
- Native HTML `<select>` dropdowns — all filled by JS (no Playwright needed for dropdowns)
- Fastest target: 2-4 minutes per application when working correctly
- Main failure mode is ref staleness, not form complexity

## Browser Safety Rules
- **SVG className bug:** In evaluate scripts, NEVER use `el.className.substring()` or `el.className.includes()`. SVG elements return `SVGAnimatedString` (not a string). Use `el.getAttribute('class') || ''` instead.
- **Narrow selectors:** Never use broad selectors like `button, [class*=code]`. Always scope to a specific section.

## Skip Rules
- CAPTCHA: Follow Phase 5.5 (audio-first via Whisper, visual fallback). If unsolved after 5 rounds, remove from queue and end the run.
- 3 failed retries: SKIP with reason
- Non-US locations: SKIP (verify location before applying)
- Check `skip-companies.json` — companies listed there must be SKIPPED

On SKIP/DEFER for this job, stop the run. Do not open another URL.
