# Sentinel's Journal - Critical Security Learnings

## 2026-05-24 - [SSRF and MITM Remediation]
**Vulnerability:** Multiple utility scripts (preflight-check.py, batch-preflight.py, clean-queue.py, validate-queue-urls.py) explicitly disabled SSL certificate verification (ssl.CERT_NONE) and lacked protocol validation for URLs, leading to MITM and SSRF/LFD risks.
**Learning:** Explicitly disabling SSL is a common but dangerous pattern used to bypass local environment issues, and missing protocol checks allows attackers to use 'file://' schemes to read local files.
**Prevention:** Always use default secure SSL contexts and strictly validate URL protocols to 'http' or 'https' using regex.
