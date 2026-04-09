# Sentinel's Journal - Critical Security Learnings

This journal documents critical security learnings and patterns discovered in the JobHunt codebase.

## 2026-04-09 - [SSL Verification Bypass Pattern]
**Vulnerability:** Multiple scripts explicitly disabled SSL certificate verification and hostname checking (`ssl.CERT_NONE` and `check_hostname = False`).
**Learning:** This was likely done to avoid issues with some websites, but it creates a MITM risk. The application-level override is a dangerous pattern that bypasses OS-level security.
**Prevention:** Always use `ssl.create_default_context()` without overriding `verify_mode` or `check_hostname` unless there is a very specific, well-documented reason to do so.
