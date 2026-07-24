---
name: excalibur-windows_enum
description: 'Comprehensive Windows privilege escalation enumeration workflow. Runs winpeas for automated enumeration of token privileges, unquoted service paths, AlwaysInstallElevated, stored credentials, and DLL hijacking opportunities. Follows up with Seatbelt for detailed security configuration checks. Use immediately after gaining any foothold on a Windows host -- same rationale as linux_enum: run this automatically after initial access rather than waiting to be asked.'
---

# Windows Enum

*These steps can be run independently and their results merged -- later steps don't strictly require earlier ones to succeed, but running them in order is still a reasonable default.*

## Steps

1. **winpeas** -- Windows Privilege Escalation Awesome Script.
   - Inputs: `mode` → `mode`, `output_file` → `output_file`
   - See `references/tools.md` for winpeas's full flag reference.

2. **seatbelt** -- C# security enumeration tool for Windows hosts.
   - Inputs: `group` → `check_group`
   - *Only proceed with this step if:* winpeas identified interesting token privileges or misconfigured services
   - See `references/tools.md` for seatbelt's full flag reference.

## Fallback

If winpeas cannot be executed, manually check: whoami /priv, wmic service get name,displayname,pathname,startmode, reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer, and cmdkey /list for stored credentials.

