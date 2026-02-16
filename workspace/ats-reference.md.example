# ATS Reference Guide — Edge Cases & Platform-Specific Instructions

## Greenhouse (Anthropic, Scale AI, Cresta, Snorkel AI, etc.)

### Email Verification (ALWAYS required after submit)
1. Fill form completely and click Submit
2. Take snapshot. If "verification code" or "security code" text appears:
3. Wait 10 seconds for email
4. Fetch code: `gog gmail search 'from:greenhouse subject:security code' --account YOUR_EMAIL@gmail.com --json`
5. Read latest thread: `gog gmail read <thread_id> --account YOUR_EMAIL@gmail.com` — extract 8-char code
6. Enter code in the 8 individual textboxes (type first char, rest auto-advance)
7. Click Submit again
8. Verify "Thank you for applying" confirmation
9. If no email in 30s, retry search once. If still nothing, WhatsApp user → SKIPPED

### Greenhouse Upload
- Uses button-based uploads ("Attach" button). The actual `input[type=file]` may be hidden.
- Use `ref` pointing to the "Attach" button, NOT `element: "input[type=file]"`.
- **ALWAYS set timeoutMs: 60000** (default 20s causes timeouts)

### Greenhouse Combobox Dropdowns
- Auto-filter as you type. Type "Yes", wait for option, press Enter.

## Ashby (OpenAI, Perplexity, Cohere, Harvey, etc.)

### Toggle Buttons (Yes/No)
- form-filler.js handles these with `simulateRealClick()` (full pointer event chain)
- If script reports `method: 'ashby-toggle-click'`: take snapshot to verify selection
- If toggles appear unselected despite being reported as filled:
  - Use browser `click` action with button's aria-ref (Playwright, not JS)
  - Take another snapshot to verify
- Agreement/consent checkbox: verify visually

### General
- No CAPTCHA, direct apply, clean forms
- Watch for application limit warnings
- No email verification needed

## Lever
- Direct submit, no verification
- Simple form with resume upload
- No CAPTCHA typically

## Gem.com
- May redirect to company ATS
- Sometimes has CAPTCHA on submit
- Direct submit otherwise

## Workday
- HARDEST — multi-page, account creation required, often CAPTCHA
- **SKIP** — prefer companies on Ashby/Greenhouse/Lever

## BambooHR, iCIMS, Taleo
- Complex, often require account creation
- Mark as SKIPPED if too complex

## Iframe Redirect (Company Career Pages)
If form-filler.js returns `iframeDetected: true` with `iframeUrl`:
- Form is inside cross-origin iframe (e.g., databricks.com embeds boards.greenhouse.io)
- Script CANNOT fill cross-origin iframes
- Navigate to `iframeUrl` directly, then re-run filler
- Example: `www.databricks.com/company/careers/...` → `boards.greenhouse.io/databricks/jobs/...`

## File Upload — USE THE UPLOAD ACTION
**NEVER click the upload button with a regular click** (opens OS dialog, causes issues).

First ensure resume is copied:
```
exec: cp ~/.openclaw/workspace/resume/YOUR_RESUME.pdf /tmp/openclaw/uploads/
```

Then use dedicated upload action:
```
action: "upload"
paths: ["/tmp/openclaw/uploads/YOUR_RESUME.pdf"]
inputRef: "<aria-ref of the file input>"  # PREFERRED
timeoutMs: 60000                          # REQUIRED — default 20s too short
```

Alternative with CSS selector:
```
action: "upload"
paths: ["/tmp/openclaw/uploads/YOUR_RESUME.pdf"]
element: "input[type=file]"
timeoutMs: 60000
```

Or with button ref:
```
action: "upload"
paths: ["/tmp/openclaw/uploads/YOUR_RESUME.pdf"]
ref: "<aria-ref of upload button>"
timeoutMs: 60000
```

### Finding the upload element
1. After form-filler.js runs, check `fileUploadSelectors` in result
2. If file already uploaded (reported "file already uploaded: YOUR_RESUME.pdf"), SKIP upload
3. Take snapshot, look for "Resume", "CV", "Upload", or `input[type=file]`
4. Use `inputRef` (preferred) or `ref` from snapshot
