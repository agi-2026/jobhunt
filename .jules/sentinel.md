## 2025-05-22 - SSL Certificate Verification Disabled
**Vulnerability:** Multiple Python utility scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) explicitly disabled SSL certificate and hostname verification using `ssl.CERT_NONE`.
**Learning:** This pattern was likely used to bypass local certificate issues during development but leaves the application vulnerable to Man-in-the-Middle (MITM) attacks when scraping job boards or calling ATS APIs.
**Prevention:** Always use `ssl.create_default_context()` without overrides for production-ready scripts. If local debugging requires bypassing SSL, it should be done via environment variables or temporary flags, never hardcoded as the default.

## 2025-05-22 - Server-Side Request Forgery (SSRF) via URL Schemes
**Vulnerability:** URL validation in the dashboard and utility scripts was either missing or used weak `startswith("http")` checks, allowing for `file://` or other schemes to be processed.
**Learning:** `urllib.request` supports various protocols by default. Without strict protocol validation, an attacker could read local files or probe internal network services.
**Prevention:** Use strict regex patterns like `^https?://` to validate URLs before passing them to networking libraries. Synchronize this validation between the frontend (JavaScript) and backend (Python).
