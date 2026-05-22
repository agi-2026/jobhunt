## 2025-05-14 - Insecure SSL Contexts in Python Utility Scripts
**Vulnerability:** Explicitly disabling SSL certificate verification (`ssl.CERT_NONE`) and hostname checking in multiple Python scripts using `urllib.request`.
**Learning:** This pattern was consistently used across `preflight-check.py`, `clean-queue.py`, `validate-queue-urls.py`, and `batch-preflight.py`, likely as a workaround for local certificate issues or to simplify development, but it exposes the application to Man-in-the-Middle (MITM) attacks.
**Prevention:** Always use `ssl.create_default_context()` without security-disabling overrides. If local certificates are an issue, they should be added to the system's trust store rather than disabling security in the code.

## 2025-05-14 - SSRF and Local File Disclosure via Protocol-less URLs
**Vulnerability:** Lack of strict URL protocol validation in `preflight-check.py` allowed protocols like `file://` to be processed by `urllib.request.urlopen`.
**Learning:** Even if a script is intended for web URLs, `urllib.request` is a multi-protocol handler. Without explicit `http/https` validation, it can be used for SSRF or to read local files (e.g., `file:///etc/passwd`).
**Prevention:** Implement strict protocol validation using regex (e.g., `^https?://`) before passing user-controlled URLs to any network-requesting library.
