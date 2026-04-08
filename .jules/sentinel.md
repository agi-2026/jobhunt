## 2025-05-14 - SSL Verification Disabled and SSRF Protocol Risk
**Vulnerability:** Several utility scripts (preflight-check.py, clean-queue.py, etc.) were disabling SSL certificate verification (ssl.CERT_NONE) and hostname checking. They also lacked protocol validation on user-provided URLs.
**Learning:** These patterns were likely inherited from quick-and-dirty scraping scripts where SSL errors are common. Disabling verification was used as a workaround for "expired" or "misconfigured" certs on job boards, but it opens the app to MITM.
**Prevention:** Always use `ssl.create_default_context()` without overriding verification modes. Strictly validate input URLs to 'http' or 'https' protocol using `startswith(('http://', 'https://'))`.
