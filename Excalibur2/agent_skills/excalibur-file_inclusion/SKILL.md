---
name: excalibur-file_inclusion
description: File inclusion exploitation workflow. Uses ffuf to discover file inclusion parameters via LFI/RFI wordlists, then confirms the vulnerability with targeted wfuzz payloads, and finally attempts command execution through log poisoning or PHP wrappers. Use whenever a URL parameter looks like it might reference a file path, template, or page name (e.g. ?page=, ?file=, ?template=) -- check for LFI/RFI proactively, since this pattern is easy to miss if not actively looked for.
---

# File Inclusion

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **ffuf** -- Fast web fuzzer written in Go.
   - Inputs: `url` → `fuzz_url`, `wordlist` → `lfi_wordlist`
   - See `references/tools.md` for ffuf's full flag reference.

2. **wfuzz** -- Web application bruteforcer/fuzzer.
   - Inputs: `url` → `url`, `wordlist` → `lfi_payloads`
   - *Only proceed with this step if:* ffuf discovered parameter accepting file paths
   - See `references/tools.md` for wfuzz's full flag reference.

3. **commix** -- Automated tool for detecting and exploiting command injection vulnerabilities.
   - Inputs: `url` → `url`, `data` → `injectable_param`
   - *Only proceed with this step if:* LFI confirmed and log poisoning or wrapper exploitation viable
   - See `references/tools.md` for commix's full flag reference.

## Fallback

If automated LFI detection fails, manually test common paths like /etc/passwd with different traversal depths and encoding variations. Try PHP wrappers (php://filter, expect://) as well.

