## 2026-03-10 - Global SSL Context Bypass and Unsanitized URL Requests in Utility Scripts
**Vulnerability:** Multiple queue check and preflight scripts disabled SSL verification globally (`ssl.CERT_NONE`, `check_hostname = False`) and fetched user/file-supplied URLs without scheme or host/IP validation, creating SSRF and Man-In-The-Middle risks.
**Learning:** Shared script helpers like `queue_utils.py` are the ideal central place to enforce URL safety (HTTP/HTTPS schemes + resolving IP ranges to block loopback/private/link-local addresses) before any network call.
**Prevention:** Always use standard `ssl.create_default_context()` without disabling verification, and run `is_safe_url()` validation on all incoming URLs before issuing HTTP requests.
