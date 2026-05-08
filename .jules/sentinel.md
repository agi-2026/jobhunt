## 2026-02-17 - Insecure SSL Contexts and SSRF Risk in Utility Scripts
**Vulnerability:** Multiple Python scripts (preflight-check.py, batch-preflight.py, clean-queue.py, validate-queue-urls.py) were explicitly disabling SSL certificate verification (`ssl.CERT_NONE`) and lacked URL protocol validation, exposing the system to MITM attacks and SSRF/local file disclosure (e.g., via `file://`).
**Learning:** Development-time convenience (bypassing SSL errors) often leads to persistent security gaps in production-ready utility scripts. Lack of protocol validation in scripts using `urllib.request` is a common source of SSRF.
**Prevention:** Always use `ssl.create_default_context()` for network requests and strictly validate URL protocols using regex (e.g., `^https?://`) before processing.
