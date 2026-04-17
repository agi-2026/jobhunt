## 2026-02-14 - [SSRF and MITM Remediation in Preflight Scripts]
**Vulnerability:** Multiple Python utility scripts used `ssl.CERT_NONE` and lacked protocol validation, enabling MITM attacks and SSRF via `file://` or other schemes. Hardcoded user paths also reduced portability.
**Learning:** Legacy scripts often disable SSL verification to "just make it work" during development, creating a recurring vulnerability pattern in internal tools.
**Prevention:** Enforce default secure SSL contexts and strict `^https?://` protocol validation for all scripts performing network requests. Use `os.path.expanduser` for workspace paths.
