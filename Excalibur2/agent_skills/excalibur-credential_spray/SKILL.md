---
name: excalibur-credential_spray
description: Credential spraying workflow across network services. First uses kerbrute to enumerate valid AD usernames via Kerberos, then performs a password spray with CrackMapExec across SMB using common passwords and the discovered user list. Use whenever you have a domain name and Kerberos/SMB access but no confirmed credentials yet -- especially useful as a low-noise alternative to brute-forcing a single account. Watch account lockout policies before spraying.
---

# Credential Spray

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **kerbrute** -- Tool for brute-forcing and enumerating valid Active Directory accounts through Kerberos pre-authentication.
   - Inputs: `mode` → `mode`, `domain` → `domain`, `dc` → `dc_ip`, `users_file` → `users_file`
   - See `references/tools.md` for kerbrute's full flag reference.

2. **crackmapexec** -- Swiss army knife for pentesting networks.
   - Inputs: `protocol` → `protocol`, `target` → `dc_ip`, `username` → `valid_users_file`, `password` → `spray_password`, `domain` → `domain`
   - *Only proceed with this step if:* kerbrute discovered valid usernames
   - See `references/tools.md` for crackmapexec's full flag reference.

3. **hydra** -- Fast and flexible online password brute-forcing tool.
   - Inputs: `target` → `target`, `service` → `service`, `username_file` → `valid_users_file`, `password_file` → `password_file`
   - *Only proceed with this step if:* CrackMapExec spray did not find valid credentials and other services (SSH, RDP, etc.) are available
   - See `references/tools.md` for hydra's full flag reference.

## Fallback

If kerbrute is unavailable, enumerate users via LDAP using ldapdomaindump or enum4linux. Be cautious with password spraying to avoid account lockouts -- respect lockout policies.

