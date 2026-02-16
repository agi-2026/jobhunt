# ATS Platform Notes — Application Agent Reference

## Greenhouse (Anthropic, Scale AI, Cresta, Snorkel AI, Netflix, etc.)
- **Form type:** React custom components — NOT native HTML inputs
- **Dropdowns:** `[role="combobox"]` — must use Playwright click + type + Enter, JS can't fill these
- **File upload:** Button-based ("Attach") — use `ref` to the Attach button, NOT `element: "input[type=file]"`
- **Email verification:** YES — 8-character code sent to email after clicking Submit
  - Fetch via: `gog gmail search 'from:greenhouse subject:security code' --account YOUR_EMAIL@gmail.com --json`
  - Read via: `gog gmail read <thread_id> --account YOUR_EMAIL@gmail.com` — use LAST message's code
  - Code format: 8 alphanumeric characters (e.g., "ClhVHj0p")
  - Entry: 8 individual textboxes — type first char in first box, rest auto-advance
- **CAPTCHA:** reCAPTCHA may appear — usually invisible/auto-pass. If visible, WhatsApp user.
- **Phone field:** Separate country code dropdown + phone number. Use "(555) 555-5555" for phone only.

## Ashby (OpenAI, Perplexity, Cohere, Notion, etc.)
- **Form type:** React custom components
- **Dropdowns:** Custom combobox — Playwright click + type + Enter
- **Toggle buttons:** Yes/No buttons with `aria-pressed` — form-filler.js handles via simulateRealClick()
  - ⚠️ React state may not persist from JS click — verify visually with snapshot
  - Fallback: use Playwright `click` action on the button ref
- **File upload:** Standard — works with `element: "input[type=file]"` or button ref
- **Email verification:** NO — direct submit
- **CAPTCHA:** None typically
- **Application limits:** OpenAI has 5 per 180 days — SKIP (apply manually)

## Lever (various startups)
- **Form type:** Standard HTML forms — simpler than Greenhouse/Ashby
- **Dropdowns:** Native `<select>` elements — JS can fill directly
- **File upload:** Standard input[type=file]
- **Email verification:** NO
- **CAPTCHA:** None typically

## Gem.com (Luma AI, etc.)
- **Form type:** Mixed — sometimes redirects to company ATS
- **Email verification:** NO
- **CAPTCHA:** Sometimes on submit

## Workday (enterprise companies)
- **SKIP** — multi-page, requires account creation, often has CAPTCHA
- **Too complex for automation** — mark as SKIPPED, apply manually

## SmartRecruiters, BambooHR, iCIMS, Taleo
- **SKIP** — complex, account creation required
- Mark as SKIPPED if encountered
