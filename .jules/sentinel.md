## 2025-05-15 - [SSRF and MITM in Preflight Validator]
**Vulnerability:** The `preflight-check.py` script was vulnerable to SSRF via non-HTTP protocols (e.g., `file://`) and MITM attacks due to disabled SSL certificate verification.
**Learning:** Utility scripts often trade security for "just works" convenience, especially when dealing with various ATS platforms that might have misconfigured SSL.
**Prevention:** Always use default secure SSL contexts and strictly validate URL protocols at the entry point of network-requesting functions.
