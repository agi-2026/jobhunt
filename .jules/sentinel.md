## 2026-03-30 - Mitigating SSL Verification Bypass & SSRF in Preflight Checks
**Vulnerability:** `workspace/scripts/preflight-check.py` previously disabled TLS certificate verification via `ssl.CERT_NONE` and `check_hostname = False`, and lacked scheme/IP validation on incoming target URLs.
**Learning:** Development/utility scripts often suppress SSL checks and allow arbitrary HTTP GET/API calls without hostname resolution validation, opening vectors for MITM and SSRF against internal resources or cloud metadata.
**Prevention:** Consolidate central URL validation (`is_safe_url`) using `socket.getaddrinfo` and `ipaddress` to verify target IPs are non-loopback and public before making HTTP requests, and enforce standard TLS certificate verification.
