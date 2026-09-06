## 2026-07-20 - Global SSL Verification Bypass & SSRF/LFD in Preflight Utilities
**Vulnerability:** Preflight and queue validation scripts bypassed TLS certificate verification via `ssl.CERT_NONE` and allowed non-HTTP schemes (`file://`) and loopback/internal IP addresses (`127.0.0.1`, `169.254.169.254`), leading to MITM, LFD, and SSRF risks.
**Learning:** Legacy utility scripts used permissive SSL contexts and raw `urllib.request.urlopen` calls without protocol or IP address validation.
**Prevention:** Always enforce standard SSL context verification and parse hostnames through `is_safe_url` using `socket.getaddrinfo` and `ipaddress` before issuing outbound HTTP requests.
