## 2026-03-30 - Global SSL Bypass and Scheme Non-Validation in URL Utilities

**Vulnerability:**
Multiple batch and preflight URL validation scripts (`preflight-check.py`, `batch-preflight.py`, `clean-queue.py`, `validate-queue-urls.py`) disabled SSL/TLS certificate verification using `ssl.CERT_NONE` and `check_hostname = False`. Additionally, queue URL checking scripts lacked scheme/IP safety checks, enabling SSRF (Server-Side Request Forgery) attacks against loopback services and local cloud metadata endpoints (e.g. `169.254.169.254`).

**Learning:**
Utility scripts in automated agent pipelines often copy insecure `ssl` overrides to bypass self-signed certificate errors or rate limits, opening up Man-In-The-Middle (MITM) risks and unvalidated URL execution vectors.

**Prevention:**
Enforce default SSL context verification (`ssl.create_default_context()`) across all scripts. Centralize URL safety logic into `queue_utils.is_safe_url` to restrict schemes to `http`/`https` and block loopback, private RFC 1918, link-local, and multicast IP ranges prior to any network request.
