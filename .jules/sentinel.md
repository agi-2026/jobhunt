## 2025-05-15 - [Insecure SSL/TLS defaults in utility scripts]
**Vulnerability:** Multiple Python scripts (preflight-check.py, clean-queue.py, etc.) were explicitly disabling SSL certificate verification (CERT_NONE) and hostname checking.
**Learning:** This was likely done to handle certain job boards with misconfigured SSL or for development convenience, but it exposes the application to MITM attacks when fetching job data or interacting with ATS APIs.
**Prevention:** Always use `ssl.create_default_context()` and do not override its verification properties unless strictly necessary and scoped to a specific, trusted endpoint.

## 2025-05-15 - [SSRF Risk in URL Validation]
**Vulnerability:** URL validation scripts did not enforce strict protocol checks, potentially allowing `file://` or other internal schemes to be processed.
**Learning:** When using `urllib.request` to validate external URLs, it's critical to restrict protocols at the application level before making the request.
**Prevention:** Use a strict regex like `^https?://` to validate all incoming URLs before they are passed to networking libraries.
