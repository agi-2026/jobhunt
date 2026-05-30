## 2026-05-30 - MITM and SSRF in URL Utility Scripts
**Vulnerability:** Multiple Python utility scripts explicitly disabled SSL certificate verification (ssl.CERT_NONE) and lacked protocol validation for user-controlled job URLs.
**Learning:** This was a systemic pattern likely used to simplify development or bypass local environment issues, but it exposed the application to MITM attacks and Local File Disclosure (via file:// protocol).
**Prevention:** Always use default secure SSL contexts and strictly validate URL protocols (e.g., ^https?://) before making network requests in all utility scripts.
