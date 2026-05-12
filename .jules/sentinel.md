## 2026-02-12 - [SSL/TLS and SSRF Remediation]
**Vulnerability:** Multiple Python utility scripts explicitly disabled SSL certificate verification and lacked URL protocol validation, exposing the system to MITM attacks and SSRF via local file disclosure (e.g., `file://`).
**Learning:** Hardcoded insecure SSL contexts (`ssl.CERT_NONE`) were likely used to bypass local environment issues but remained in production-ready scripts. Weak protocol checks like `url.startswith("http")` were insufficient to prevent SSRF.
**Prevention:** Always use `ssl.create_default_context()` without insecure overrides. Implement strict `^https?://` protocol validation for all external URL processing.
