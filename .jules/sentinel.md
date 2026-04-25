## 2025-05-14 - Insecure SSL Contexts and SSRF in Preflight Scripts
**Vulnerability:** Multiple Python scripts (preflight-check.py, batch-preflight.py, clean-queue.py, validate-queue-urls.py) were explicitly disabling SSL certificate verification and lacked protocol validation for URLs.
**Learning:** Python's `urllib.request` can be coerced into accessing local files via the `file://` scheme if the protocol is not strictly validated, leading to SSRF/LFD. Furthermore, disabling SSL verification is a common but dangerous pattern in internal utility scripts that exposes them to MITM attacks.
**Prevention:** Always use default secure SSL contexts. Implement strict `https?://` regex validation for any user-provided or scraped URLs before passing them to network request libraries.
