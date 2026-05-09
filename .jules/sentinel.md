# Sentinel Journal

## 2026-02-12 - SSRF and MITM Vulnerabilities in URL Utility Scripts
**Vulnerability:** Several Python utility scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) were found to have two significant security flaws:
1. **SSRF/Local File Disclosure:** Using `urllib.request.urlopen` without protocol validation allowed the `file://` scheme, potentially exposing sensitive local files (e.g., `/etc/passwd`).
2. **MITM (Man-in-the-Middle):** Explicitly disabling SSL certificate verification (`ssl.CERT_NONE`) made all network requests vulnerable to interception and modification.

**Learning:** This pattern was likely introduced during development to bypass local certificate issues or speed up development, but it was left in production-ready scripts. `urllib`'s default behavior of accepting any scheme is a common pitfall.

**Prevention:** Always use `ssl.create_default_context()` without overriding `verify_mode` unless absolutely necessary (and then only for specific, trusted internal hosts). Always validate URL protocols using a strict regex (e.g., `^https?://`) before passing them to `urlopen`.
