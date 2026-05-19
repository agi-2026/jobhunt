## 2026-02-27 - Insecure SSL Context and SSRF in Utility Scripts
**Vulnerability:** Multiple utility scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) explicitly disabled SSL certificate verification (`ssl.CERT_NONE`) and lacked protocol validation for URLs, leading to MITM and SSRF risks.
**Learning:** SSL verification was likely disabled to avoid local environment issues, but it compromised security. The absence of protocol validation allowed potentially dangerous schemes like `file://` to be processed.
**Prevention:** Use default secure SSL contexts. Implement strict regex-based protocol validation (`^https?://`) for all external URLs.
