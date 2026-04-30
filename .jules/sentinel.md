## 2025-05-15 - [SSRF and MITM via Insecure Scripting Patterns]
**Vulnerability:** Explicitly disabling SSL certificate verification (ssl.CERT_NONE) and missing protocol validation in URL utility scripts.
**Learning:** A recurring pattern of "shortcuts" in utility scripts (like preflight checks) bypasses standard security controls. Disabling SSL verification and failing to validate protocols (allowing file://) creates critical SSRF and MITM risks.
**Prevention:** Always use 'ssl.create_default_context()' without overrides for network requests. Strictly validate all user-supplied URLs against a regex (e.g., '^https?://') before processing.
