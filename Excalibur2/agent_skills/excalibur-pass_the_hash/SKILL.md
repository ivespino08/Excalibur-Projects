---
name: excalibur-pass_the_hash
description: Pass-the-hash lateral movement workflow. Extracts NTLM hashes using impacket secretsdump, then uses CrackMapExec to validate the hashes against multiple targets and identify admin access, and finally establishes a shell via evil-winrm or psexec. Use as soon as an NTLM hash or set of hashes has been recovered (e.g. via secretsdump) in a Windows/AD environment -- don't wait to be asked to "pass the hash" specifically; this is the standard next move after any hash dump.
---

# Pass The Hash

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **impacket** -- Collection of Python classes and scripts for working with network protocols.
   - Inputs: `script` → `script`, `target` → `target`, `domain` → `domain`, `username` → `username`, `password` → `password`
   - See `references/tools.md` for impacket's full flag reference.

2. **crackmapexec** -- Swiss army knife for pentesting networks.
   - Inputs: `protocol` → `protocol`, `target` → `target_range`, `username` → `username`, `hash` → `ntlm_hash`, `domain` → `domain`
   - *Only proceed with this step if:* secretsdump extracted NTLM hashes
   - See `references/tools.md` for crackmapexec's full flag reference.

3. **evil_winrm** -- WinRM shell for Windows remote management.
   - Inputs: `host` → `target_host`, `username` → `username`, `hash` → `ntlm_hash`
   - *Only proceed with this step if:* CrackMapExec confirmed admin access on a target
   - See `references/tools.md` for evil_winrm's full flag reference.

## Fallback

If evil-winrm fails, try impacket psexec, wmiexec, or smbexec with the hash. If secretsdump fails due to insufficient privileges, try mimikatz sekurlsa::logonpasswords from an elevated context.

