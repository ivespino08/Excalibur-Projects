---
name: excalibur-asrep_roasting
description: AS-REP roasting attack workflow. Uses impacket GetNPUsers to identify accounts that do not require Kerberos pre-authentication and extract their AS-REP hashes. Then cracks the hashes with hashcat to obtain plaintext passwords. Use early in any AD engagement, alongside or before kerberoasting -- AS-REP roasting needs no valid credentials at all (only a vulnerable account with Kerberos pre-auth disabled), so it's worth trying even at the very start of enumeration.
---

# Asrep Roasting

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **impacket** -- Collection of Python classes and scripts for working with network protocols.
   - Inputs: `script` → `script`, `domain` → `domain`, `username` → `username`, `password` → `password`, `dc_ip` → `dc_ip`, `target` → `target`
   - See `references/tools.md` for impacket's full flag reference.

2. **hashcat** -- World's fastest and most advanced password recovery utility.
   - Inputs: `hash_file` → `asrep_hash_file`, `hash_type` → `hash_type`, `wordlist` → `wordlist`
   - *Only proceed with this step if:* GetNPUsers retrieved at least one AS-REP hash
   - See `references/tools.md` for hashcat's full flag reference.

## Fallback

If impacket GetNPUsers fails, try kerbrute userenum first to identify valid usernames, then re-run. Alternatively, use Rubeus asreproast from a domain-joined Windows host.

