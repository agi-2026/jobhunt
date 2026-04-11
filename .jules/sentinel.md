## 2026-04-11 - [SSL Verification & SSRF Mitigation]
**Vulnerability:** Core network request scripts (`preflight-check.py`, `batch-preflight.py`) explicitly disabled SSL certificate verification (`ssl.CERT_NONE`) and lacked URL protocol validation.
**Learning:** Developers often disable SSL verification to bypass local development hurdles, but this leaves the application vulnerable to MITM attacks in production. Additionally, accepting arbitrary URLs without protocol validation can lead to SSRF or local file disclosure.
**Prevention:** Use `ssl.create_default_context()` without overrides and strictly validate URL protocols to `http://` or `https://` at the entry point of any network-requesting function.
