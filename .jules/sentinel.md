## 2026-04-14 - [Insecure SSL Contexts & Missing Protocol Validation]
**Vulnerability:** Multiple Python utility scripts (`preflight-check.py`, `batch-preflight.py`, etc.) explicitly disabled SSL certificate verification (`ssl.CERT_NONE`) and lacked protocol validation for user-supplied URLs.
**Learning:** Legacy scripts often disable SSL to avoid local environment issues, but this exposes the system to MITM attacks. Lack of protocol validation allows SSRF (e.g., via `file://`).
**Prevention:** Always use default secure SSL contexts (`ssl.create_default_context()`) and strictly validate URL protocols against `^https?://` before making network requests.
