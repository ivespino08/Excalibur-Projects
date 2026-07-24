---
name: excalibur-network_pivot
description: Network pivoting workflow for reaching internal networks through a compromised host. Sets up a chisel reverse SOCKS proxy through the compromised host, configures proxychains, then performs an nmap scan of the internal network through the tunnel. Use whenever a host has been compromised and there's an internal network segment behind it that isn't directly reachable -- this is the standard way to reach a second subnet/domain, so consider it any time lateral movement or multi-host/multi-domain engagements come up (e.g. GOAD-style environments).
---

# Network Pivot

*Run these steps in order -- each step depends on the previous one succeeding (or its condition being met).*

## Steps

1. **chisel** -- Fast TCP/UDP tunnel transported over HTTP and secured via SSH.
   - Inputs: `mode` → `mode`, `host` → `pivot_host`, `port` → `listen_port`, `tunnel_spec` → `tunnel_spec`
   - See `references/tools.md` for chisel's full flag reference.

2. **proxychains** -- Forces TCP connections made by any application to go through proxy servers like SOCKS4/5 or HTTP proxies.
   - Inputs: `command` → `scan_command`, `config_file` → `proxychains_config`
   - *Only proceed with this step if:* chisel tunnel established successfully
   - See `references/tools.md` for proxychains's full flag reference.

3. **nmap** -- Network exploration and security auditing tool.
   - Inputs: `target` → `internal_range`, `ports` → `ports`
   - *Only proceed with this step if:* proxychains configured and working through tunnel
   - See `references/tools.md` for nmap's full flag reference.

## Fallback

If chisel is unavailable, try SSH dynamic port forwarding (ssh -D 1080 user@pivot) or socat for simple port forwards. If proxychains fails, configure the SOCKS proxy in nmap directly.

