## 2026-03-01 - Global SSL/TLS Bypass and SSRF Risk in Preflight Utility

**Vulnerability:**
`workspace/scripts/preflight-check.py` disabled SSL certificate verification globally via `ssl.CERT_NONE` and `check_hostname = False`, and processed arbitrary target URLs without scheme/IP destination safety checks.

**Learning:**
Utility scripts checking external job board postings attempted to prevent SSL errors on misconfigured hosts by disabling certificate validation, introducing MITM risks and Server-Side Request Forgery (SSRF) risks against internal/link-local endpoints.

**Prevention:**
Centralize outbound URL validation with `is_safe_url` in `queue_utils.py` to resolve and check target IPs against loopback/private/link-local ranges, and strictly enforce standard TLS validation using Python's default SSL contexts.
