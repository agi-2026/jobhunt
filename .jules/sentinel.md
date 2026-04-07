## 2026-04-07 - [SSRF and MITM via insecure preflight check]
**Vulnerability:** The `preflight-check.py` script was vulnerable to SSRF/LFI and MITM attacks. It lacked protocol validation (allowing `file://` URLs) and explicitly disabled SSL certificate verification.
**Learning:** Insecure defaults in internal utility scripts can expose the system to significant risks, especially when they handle user-provided URLs. Disabling SSL verification is a common but dangerous anti-pattern.
**Prevention:** Always validate protocols for outgoing requests to only allow `http` and `https`. Never disable SSL verification in production-ready scripts; use the default secure context provided by the `ssl` module.
