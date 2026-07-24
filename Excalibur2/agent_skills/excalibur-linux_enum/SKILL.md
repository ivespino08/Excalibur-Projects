---
name: excalibur-linux_enum
description: Comprehensive Linux privilege escalation enumeration workflow. Runs linpeas for automated enumeration of SUID binaries, cron jobs, writable paths, capabilities, and kernel exploits. Follows up with pspy to monitor processes for cron-triggered commands run by root or other privileged users. Use immediately after gaining any foothold (shell, low-priv user) on a Linux host -- privilege escalation enumeration should happen automatically after initial access, not only when explicitly requested.
---

# Linux Enum

*These steps can be run independently and their results merged -- later steps don't strictly require earlier ones to succeed, but running them in order is still a reasonable default.*

## Steps

1. **linpeas** -- Linux Privilege Escalation Awesome Script.
   - Inputs: `output_file` → `output_file`
   - See `references/tools.md` for linpeas's full flag reference.

2. **pspy** -- Unprivileged Linux process snooping tool.
   - Inputs: `directories` → `watch_dirs`
   - *Only proceed with this step if:* linpeas found potential cron-based escalation vectors or writable script paths
   - See `references/tools.md` for pspy's full flag reference.

## Fallback

If linpeas cannot be uploaded, manually check: find / -perm -4000 2>/dev/null (SUID), cat /etc/crontab, ls -la /etc/cron.*, getcap -r / 2>/dev/null (capabilities), and sudo -l for sudo misconfigurations.

