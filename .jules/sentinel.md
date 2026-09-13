# Sentinel Security Journal

## 2026-09-13 - Mitigate Global SSL Bypass and SSRF Vulnerabilities in Preflight Verification
**Vulnerability:** `preflight-check.py` disabled SSL hostname and certificate verification (`ssl.CERT_NONE` / `check_hostname = False`) and made unchecked HTTP requests to user-supplied job URLs, enabling Server-Side Request Forgery (SSRF) against internal network services, loopback interfaces (`127.0.0.1`, `[::1]`), and AWS metadata endpoints (`169.254.169.254`).
**Learning:** Utilities fetching external URLs were configured with permissive SSL contexts and lacked hostname IP resolution checks before issuing requests.
**Prevention:** Consolidate URL safety validation in `queue_utils.is_safe_url` using `socket.getaddrinfo` + `ipaddress` properties, restrict protocols to `http` and `https`, and always enforce default SSL certificate verification.
