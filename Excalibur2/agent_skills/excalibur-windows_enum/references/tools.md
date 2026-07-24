# Tool Reference

Tools used by the `excalibur-windows_enum` skill.

# winpeas
Category: privilege_escalation
Description: Windows Privilege Escalation Awesome Script. Enumerates system info, running processes, services, scheduled tasks, registry keys, unquoted service paths, token privileges, and other Windows privilege escalation vectors.
Timeout: 600s

## Parameters
  - mode [string, optional] (default: all): Check category to run
  - quiet [boolean, optional] (default: false): Quiet mode (less output)
  - wait [boolean, optional] (default: false): Wait for user input between checks
  - output_file [string, optional]: Path to save output
  - extra_flags [string, optional]: Additional winpeas flags

## Output Fields
  - vulnerable_services [list[dict]]: Services with escalation potential
  - unquoted_paths [list[str]]: Unquoted service paths
  - token_privileges [list[str]]: Exploitable token privileges
  - credentials_found [list[dict]]: Discovered stored credentials
  - raw_output [string]: Full winpeas output

## Preconditions
  - [os_type] Must have shell access on a Windows system

## Postconditions
  - [reveals_data] Identifies privilege escalation vectors on Windows

## Command Template
  winPEASx64.exe {mode} {extra_flags} | tee {output_file}

# seatbelt
Category: privilege_escalation
Description: C# security enumeration tool for Windows hosts. Performs numerous safety checks to identify misconfigurations, installed software, credential storage, token privileges, and other security-relevant system settings.
Timeout: 300s

## Parameters
  - group [string, optional] (default: all): Check group to run
  - checks [string, optional]: Specific checks to run (e.g., 'TokenPrivileges,AutoRuns,CredFiles')
  - full [boolean, optional] (default: false): Return complete, unfiltered results
  - output_file [string, optional]: Path to save output file
  - remote_host [string, optional]: Remote host to enumerate (requires admin access)
  - extra_flags [string, optional]: Additional Seatbelt flags

## Output Fields
  - token_privileges [list[str]]: Current token privileges
  - auto_runs [list[dict]]: Auto-run entries (registry, startup, services)
  - credential_files [list[str]]: Paths to credential storage files
  - installed_products [list[dict]]: Installed software products
  - raw_output [string]: Full Seatbelt output

## Preconditions
  - [os_type] Must have shell access on a Windows system

## Postconditions
  - [reveals_data] Enumerates Windows security settings and misconfigurations

## Command Template
  Seatbelt.exe -group={group} -{checks} -outputfile={output_file} -computername={remote_host} {extra_flags}

