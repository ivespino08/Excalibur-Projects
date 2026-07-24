---
name: excalibur-kerberoasting
description: Kerberoasting attack workflow. Uses impacket GetUserSPNs to enumerate service accounts with SPNs and request TGS tickets, then cracks the extracted Kerberos hashes with hashcat using the rockyou wordlist. Optionally validates cracked credentials with CrackMapExec. Use whenever the target is a domain-joined Windows/AD environment and you have at least one set of valid domain credentials -- this is one of the highest-value early moves in an AD engagement, so check for it even if not explicitly asked to "kerberoast."
---

# Kerberoasting

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **impacket** -- Collection of Python classes and scripts for working with network protocols.
   - Inputs: `script` → `script`, `domain` → `domain`, `username` → `username`, `password` → `password`, `dc_ip` → `dc_ip`, `target` → `target`
   - See `references/tools.md` for impacket's full flag reference.

2. **hashcat** -- World's fastest and most advanced password recovery utility.
   - Inputs: `hash_file` → `tgs_hash_file`, `hash_type` → `hash_type`, `wordlist` → `wordlist`
   - *Only proceed with this step if:* GetUserSPNs retrieved at least one TGS hash
   - See `references/tools.md` for hashcat's full flag reference.

3. **crackmapexec** -- Swiss army knife for pentesting networks.
   - Inputs: `protocol` → `protocol`, `target` → `dc_ip`, `username` → `cracked_user`, `password` → `cracked_pass`, `domain` → `domain`
   - *Only proceed with this step if:* hashcat cracked at least one Kerberos hash
   - See `references/tools.md` for crackmapexec's full flag reference.

## Fallback

If impacket GetUserSPNs fails, try Rubeus kerberoast from a domain-joined Windows host. If hashcat is too slow, fall back to john with the krb5tgs format.

