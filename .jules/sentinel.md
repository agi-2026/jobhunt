## 2026-02-12 - Insecure SSL Context and SSRF in URL Validation Scripts
**Vulnerability:** Utility scripts (preflight-check.py, batch-preflight.py, clean-queue.py, validate-queue-urls.py) were using `ssl.CERT_NONE` to disable certificate verification and lacked protocol validation on input URLs, allowing SSRF (e.g., reading local files via `file://`).
**Learning:** Developers often disable SSL verification to quickly bypass certificate errors in scrapers, creating MITM risks. Combined with `urllib.request.urlopen`'s support for multiple protocols, this leads to SSRF.
**Prevention:** Always use default secure SSL contexts. Implement strict `^https?://` protocol validation for any URL before passing it to network-requesting functions.
