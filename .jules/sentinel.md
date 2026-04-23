## 2026-02-18 - [Insecure SSL/TLS and SSRF Vulnerabilities in Utility Scripts]
**Vulnerability:** Multiple Python utility scripts explicitly disabled SSL certificate verification and lacked protocol validation for URLs.
**Learning:** Legacy scripts often prioritize "it just works" for local testing over security, leading to persistent MITM and SSRF risks if not strictly audited.
**Prevention:** Enforce default secure SSL contexts and strict '^https?://' protocol whitelisting for all network-requesting utility scripts.
