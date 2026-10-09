## 2026-03-11 - SSRF and Global TLS Verification Bypass Mitigations

**Vulnerability:** Preflight and queue validation scripts used `ssl.CERT_NONE` and `check_hostname = False` while accepting unvalidated job URLs. This allowed potential Server-Side Request Forgery (SSRF) against internal network interfaces (`localhost`, `127.0.0.1`, `10.x.x.x`, `169.254.169.254`, `file://`) and exposed outbound traffic to MITM eavesdropping.
**Learning:** Legacy utility scripts disabled TLS validation to avoid certificate errors on unusual ATS domains without validating scheme or target IP addresses.
**Prevention:** Enforce shared `is_safe_url` validation resolving hostnames via `socket.getaddrinfo` and checking IP address ranges via `ipaddress` before making outbound HTTP requests, and always use standard SSL context (`ssl.create_default_context()`).
