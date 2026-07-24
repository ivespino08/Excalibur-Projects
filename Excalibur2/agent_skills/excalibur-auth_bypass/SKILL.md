---
name: excalibur-auth_bypass
description: Authentication bypass workflow. Uses wfuzz to test login forms with common bypass payloads, then nuclei to scan for default credentials and known auth bypasses, and finally commix to test for command injection in auth-adjacent parameters. Use whenever a login form or other authentication gate is in scope -- try bypass/default-credential/injection angles as a matter of course before assuming credentials must be brute-forced or already known.
---

# Auth Bypass

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **wfuzz** -- Web application bruteforcer/fuzzer.
   - Inputs: `url` → `login_url`, `data` → `login_data`, `wordlist` → `bypass_wordlist`
   - See `references/tools.md` for wfuzz's full flag reference.

2. **nuclei** -- Fast, template-based vulnerability scanner.
   - Inputs: `target` → `url`, `tags` → `tags`
   - *Only proceed with this step if:* wfuzz identified interesting response variations
   - See `references/tools.md` for nuclei's full flag reference.

3. **commix** -- Automated tool for detecting and exploiting command injection vulnerabilities.
   - Inputs: `url` → `url`, `data` → `injectable_data`
   - *Only proceed with this step if:* parameters appear injectable based on prior results
   - See `references/tools.md` for commix's full flag reference.

## Fallback

If automated bypass fails, attempt manual testing with known default credentials from SecLists. Also try SQL injection payloads in login fields using sqlmap.

