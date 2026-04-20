## 2026-02-12 - [SSL/SSRF Mitigation]
**Vulnerability:** Multiple scripts explicitly disabled SSL certificate verification and lacked protocol validation for URLs, leading to MITM and SSRF risks.
**Learning:** A recurring pattern of using `ssl.CERT_NONE` was found in utility scripts to bypass certificate errors, likely for speed or to avoid configuration issues. This was often coupled with loose URL validation.
**Prevention:** Enforce default secure SSL contexts and implement strict protocol whitelisting (`^https?://`) in all scripts performing network requests.
