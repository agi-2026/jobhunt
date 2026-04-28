## 2026-02-14 - Insecure SSL Contexts and Missing Protocol Validation
**Vulnerability:** Utility scripts (preflight-check.py, clean-queue.py, batch-preflight.py, validate-queue-urls.py) were explicitly disabling SSL certificate verification (verify_mode = ssl.CERT_NONE) and lacking strict URL protocol validation. This exposed the application to Man-in-the-Middle (MITM) attacks and Server-Side Request Forgery (SSRF), including local file disclosure via the 'file://' scheme.

**Learning:** SSL verification was likely disabled to bypass local environment issues or self-signed certificate errors during development, a common but dangerous pattern in internal tools. Protocol validation was overlooked, assuming inputs would always be well-formed job board URLs.

**Prevention:** Always use default secure SSL contexts in production-ready scripts. Implement strict regex-based protocol validation (e.g., '^https?://') for any user-provided or external URLs processed by backend scripts to prevent SSRF.
