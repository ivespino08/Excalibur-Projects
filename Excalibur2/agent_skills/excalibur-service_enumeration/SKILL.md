---
name: excalibur-service_enumeration
description: Detailed service enumeration workflow. Runs nmap with version detection and default scripts, then uses whatweb for web technology fingerprinting on any discovered HTTP/HTTPS services, and enum4linux for any discovered SMB services. Use right after a port scan (or masscan/nmap fallback) has found open ports and before deciding on an exploitation path -- version and technology fingerprinting should happen automatically on any newly discovered service.
---

# Service Enumeration

*These steps can be run independently and their results merged -- later steps don't strictly require earlier ones to succeed, but running them in order is still a reasonable default.*

## Steps

1. **nmap** -- Network exploration and security auditing tool.
   - Inputs: `target` → `target`, `ports` → `ports`
   - See `references/tools.md` for nmap's full flag reference.

2. **whatweb** -- Web technology fingerprinting tool.
   - Inputs: `target` → `http_url`
   - *Only proceed with this step if:* nmap detected HTTP or HTTPS service
   - See `references/tools.md` for whatweb's full flag reference.

3. **enum4linux** -- Tool for enumerating information from Windows and Samba systems.
   - Inputs: `target` → `target`
   - *Only proceed with this step if:* nmap detected SMB service (port 139 or 445)
   - See `references/tools.md` for enum4linux's full flag reference.

## Fallback

If nmap script scan fails, retry with -sV only. If whatweb fails, try nikto as an alternative.

