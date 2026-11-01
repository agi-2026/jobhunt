# Sentinel Journal

## 2026-03-11 - SSRF and Local File Disclosure in URL Preflight Validation
**Vulnerability:** `workspace/scripts/preflight-check.py` used `urllib.request.urlopen` with SSL verification disabled (`check_hostname = False`, `CERT_NONE`) and did not restrict the scheme or validate resolved IP addresses. Non-http schemes such as `file:///etc/passwd` returned `ALIVE OK` and read local files, and loopback / metadata / private IPs could be probed directly by arbitrary job inputs.
**Learning:** In autonomous job-seeking agents with URL submission endpoints or crawlers, preflight check scripts receive user and external input that can reach internal services or expose local files unless URLs are strictly parsed and resolved IPs are checked against loopback, private, and link-local ranges before network requests are dispatched.
**Prevention:** Implement centralized URL validation (`is_safe_url` in `queue_utils.py`) enforcing `http`/`https` only, resolving hostnames to all IP addresses, and blocking loopback, link-local (metadata), RFC 1918 private, and reserved ranges with standard SSL verification enabled.
