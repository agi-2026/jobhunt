## 2025-05-22 - [SSRF and Insecure SSL Verification]
**Vulnerability:** Multiple Python utility scripts (preflight-check.py, batch-preflight.py, clean-queue.py, validate-queue-urls.py) were using `ssl.CERT_NONE` and lacked strict URL protocol validation, allowing SSRF (e.g., via `file://` scheme) and MitM attacks.
**Learning:** Explicitly disabling SSL verification (ssl.CERT_NONE) is a dangerous pattern often used to bypass local certificate issues. Combined with `urllib.request.urlopen`, it can lead to local file disclosure if protocols are not strictly validated.
**Prevention:** Always use default secure SSL contexts (`ssl.create_default_context()`) and strictly validate URL protocols using regex (e.g., `^https?://`) before performing network requests.
