## 2025-05-14 - [Vulnerability Pattern: Explicitly Disabling SSL Verification]
**Vulnerability:** Multiple Python utility scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) explicitly disabled SSL certificate verification by setting `verify_mode = ssl.CERT_NONE`.
**Learning:** This pattern was likely used to bypass local environment issues or to simplify development, but it exposes the application to MITM attacks when fetching job data or interacting with ATS APIs.
**Prevention:** Always use default secure contexts (`ssl.create_default_context()`) for network requests. If local certificates are an issue, they should be managed via the OS or environment, not by compromising the application's security posture in code.

## 2025-05-14 - [SSRF Risk in URL Validation Scripts]
**Vulnerability:** URL validation scripts were susceptible to SSRF because they didn't strictly validate the protocol scheme, allowing `file://` or other internal schemes to be processed by `urllib.request`.
**Learning:** Even simple "preflight" checks can be exploited if they interact with user-controlled URLs without strict validation.
**Prevention:** Enforce strict `https?://` protocol validation using regex before initiating any network request.
