# Sentinel Security Journal

## 2026-03-10 - Server-Side Request Forgery (SSRF) and Insecure SSL Context
**Vulnerability:** User-controlled URLs provided to `add_job` endpoint and `preflight-check.py` could target internal services (loopback, private subnets, AWS IMDS metadata at `169.254.169.254`, or arbitrary local ports). Additionally, `preflight-check.py` bypassed SSL TLS verification using `ssl.CERT_NONE`.
**Learning:** Utility scripts making HTTP requests on user-provided or scraped job URLs need shared URL validation logic resolving hostnames via `socket.getaddrinfo` to prevent IP address/DNS rebinding bypasses.
**Prevention:** Consolidate `is_safe_url` in `workspace/scripts/queue_utils.py` to validate URL schemes (`http`/`https`) and verify resolved IP addresses against loopback, private, link-local, multicast, and reserved ranges before executing outbound network requests. Ensure default standard SSL contexts (`ssl.create_default_context()`) are preserved.
