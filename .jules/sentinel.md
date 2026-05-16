## 2025-02-14 - Fix Insecure SSL Verification and SSRF in Preflight Scripts
**Vulnerability:** Multiple Python utility scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) were explicitly disabling SSL certificate verification using `verify_mode = ssl.CERT_NONE`. Additionally, they lacked strict protocol validation, potentially allowing SSRF or local file disclosure (e.g., via `file://`).
**Learning:** This pattern was likely used to bypass certificate issues in development but left the application vulnerable to MITM attacks and SSRF.
**Prevention:** Always use default secure SSL contexts (`ssl.create_default_context()`) and enforce strict URL protocol validation using regex (e.g., `^https?://`) before making network requests.
