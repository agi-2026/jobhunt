## 2026-07-16 - SSRF and TLS Verification Bypass in Job URL Preflight Checks

**Vulnerability:**
The dashboard's `/api/add-job` endpoint and CLI queue check utilities (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) lacked host and IP safety checks when fetching job URLs, allowing Server-Side Request Forgery (SSRF) against internal endpoints (e.g. `127.0.0.1`, `localhost`, AWS metadata `169.254.169.254`, and private networks). Additionally, multiple utility scripts disabled TLS certificate verification using `ssl.CERT_NONE` and `check_hostname = False`, opening Man-In-The-Middle (MITM) risks.

**Learning:**
Helper scripts designed for scraping or quick API checks often bypass TLS verification to avoid local certificate issues, and accept arbitrary URLs without resolving destination IPs. In an HTTP-triggered server environment like the dashboard, passing unvalidated URLs to sub-processes or web clients converts internal endpoints into SSRF attack targets.

**Prevention:**
Centralize URL safety checking in a shared utility (`queue_utils.py`'s `is_safe_url`) that validates protocol schemes (`http`/`https`), resolves DNS hostnames via `socket.getaddrinfo`, and validates resolved IP addresses against loopback, private (RFC 1918), and link-local ranges using standard `ipaddress` modules. Always use default secure SSL contexts (`ssl.create_default_context()`).
