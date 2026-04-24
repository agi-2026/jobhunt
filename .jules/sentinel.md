## 2026-02-12 - [SSL/TLS Security and SSRF Prevention]
**Vulnerability:** Widespread explicit disabling of SSL certificate verification (`ssl.CERT_NONE`) and lack of URL protocol validation in utility scripts.
**Learning:** Utility scripts often trade security for "convenience" to avoid certificate issues, but this exposes the application to MITM attacks. Lack of protocol validation allows SSRF via `file://` or other schemes.
**Prevention:** Always use default secure SSL contexts and strictly validate URL protocols (regex `^https?://`) before making network requests.
