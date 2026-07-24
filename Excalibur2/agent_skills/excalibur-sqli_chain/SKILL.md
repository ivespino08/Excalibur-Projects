---
name: excalibur-sqli_chain
description: End-to-end SQL injection exploitation workflow. Begins with nuclei template scanning for SQLi indicators, then uses sqlmap for automated detection and exploitation, and finally extracts database contents and credentials. Use whenever a web application has forms, query parameters, or API endpoints that take user input into what could be a database query -- check for SQL injection proactively rather than waiting for it to be named.
---

# Sqli Chain

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **nuclei** -- Fast, template-based vulnerability scanner.
   - Inputs: `target` → `url`, `tags` → `tags`
   - See `references/tools.md` for nuclei's full flag reference.

2. **sqlmap** -- Automatic SQL injection detection and exploitation tool.
   - Inputs: `url` → `injectable_url`, `data` → `post_data`, `cookie` → `cookie`
   - *Only proceed with this step if:* nuclei detected potential SQL injection indicators
   - See `references/tools.md` for sqlmap's full flag reference.

3. **sqlmap** -- Automatic SQL injection detection and exploitation tool.
   - Inputs: `url` → `injectable_url`, `dump` → `dump`
   - *Only proceed with this step if:* sqlmap confirmed SQL injection vulnerability
   - See `references/tools.md` for sqlmap's full flag reference.

## Fallback

If nuclei misses the injection, run sqlmap directly with --level=3 and --risk=2. If sqlmap fails, attempt manual injection with wfuzz using common SQLi payloads.

