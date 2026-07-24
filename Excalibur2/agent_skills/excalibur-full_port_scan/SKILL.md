---
name: excalibur-full_port_scan
description: Comprehensive port discovery workflow. Starts with a fast masscan sweep across all 65535 TCP ports, then performs a detailed nmap service version and script scan on the discovered open ports. Use at the start of reconnaissance against any new host or network range where the full port surface isn't known yet. This is the default first move against a fresh target.
---

# Full Port Scan

*These steps can be run independently and their results merged -- later steps don't strictly require earlier ones to succeed, but running them in order is still a reasonable default.*

## Steps

1. **masscan** -- High-speed TCP port scanner.
   - Inputs: `target` → `target`, `ports` → `ports`
   - See `references/tools.md` for masscan's full flag reference.

2. **nmap** -- Network exploration and security auditing tool.
   - Inputs: `target` → `target`, `ports` → `discovered_ports`
   - *Only proceed with this step if:* masscan found at least one open port
   - See `references/tools.md` for nmap's full flag reference.

## Fallback

If masscan fails (e.g., no root access), fall back to nmap -sS scan across the full port range with -T4 timing.

