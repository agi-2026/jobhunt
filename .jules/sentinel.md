## 2026-02-17 - Insecure SSL/TLS and SSRF Vulnerabilities in Utility Scripts
**Vulnerability:** Explicit disabling of SSL certificate verification (`verify_mode = ssl.CERT_NONE`) and lack of protocol validation in Python scripts performing network requests.
**Learning:** Development-time bypasses for local certificate issues can easily leak into production scripts, creating MITM risks. Furthermore, using `urllib.request` without strict protocol validation allows for SSRF and local file disclosure via the `file://` scheme.
**Prevention:** Always use default secure contexts for SSL/TLS. Implement strict whitelist-based protocol validation (e.g., `^https?://`) for all user-supplied or externally-sourced URLs before processing.
