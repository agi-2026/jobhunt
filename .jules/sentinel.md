## 2025-05-11 - Widespread Insecure SSL Configuration
**Vulnerability:** Explicitly disabling SSL certificate verification (`ssl.CERT_NONE`) and hostname checking across multiple utility scripts.
**Learning:** This pattern was likely used to bypass local environment or certificate issues during development, but it left the application vulnerable to MITM attacks for all network-requesting utilities.
**Prevention:** Always use default secure SSL contexts (`ssl.create_default_context()`) and handle certificate issues at the environment/infrastructure level rather than in code.

## 2025-05-11 - Lack of Protocol Validation (SSRF)
**Vulnerability:** Utility scripts using `urllib.request` did not validate URL protocols, allowing schemes like `file://` to be used.
**Learning:** Even simple URL-checking utilities can be vectors for SSRF or local file disclosure if protocols aren't strictly limited to `http` and `https`.
**Prevention:** Implement strict protocol validation using regex (e.g., `^https?://`) for any user-provided or scraped URLs before processing them with network libraries.
