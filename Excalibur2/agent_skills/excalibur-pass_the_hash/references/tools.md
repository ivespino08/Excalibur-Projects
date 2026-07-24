# Tool Reference

Tools used by the `excalibur-pass_the_hash` skill.

# impacket
Category: credential_attacks
Description: Collection of Python classes and scripts for working with network protocols. Includes tools for credential dumping (secretsdump), remote execution (psexec, wmiexec, smbexec), Kerberos attacks (GetNPUsers, GetUserSPNs), and more.
Timeout: 600s

## Parameters
  - script [string, REQUIRED]: Impacket script to run
  - target [string, REQUIRED]: Target specification (e.g., 'domain/user:pass@target')
  - domain [string, optional]: Active Directory domain name
  - username [string, optional]: Username for authentication
  - password [string, optional]: Password for authentication
  - hash [string, optional]: NTLM hash (LM:NT format) for pass-the-hash
  - dc_ip [string, optional]: Domain Controller IP address
  - output_file [string, optional]: Path to save output
  - extra_flags [string, optional]: Additional script-specific flags

## Output Fields
  - credentials [list[dict]]: Dumped credentials (hashes, tickets, etc.)
  - command_output [string]: Output from remote command execution
  - raw_output [string]: Full impacket script output

## Preconditions
  - [host_reachable] Target must be accessible on the network
  - [tool_installed] Impacket must be installed

## Postconditions
  - [gains_access] Dumps credentials, executes commands, or performs Kerberos attacks
  - [reveals_data] Extracts password hashes and Kerberos tickets

## Command Template
  impacket-{script} {domain}/{username}:{password}@{target} -hashes {hash} -dc-ip {dc_ip} -outputfile {output_file} {extra_flags}

# crackmapexec
Category: network_exploitation
Description: Swiss army knife for pentesting networks. Supports enumeration and exploitation of SMB, WinRM, LDAP, MSSQL, SSH, and other protocols. Automates credential testing, command execution, and lateral movement.
Timeout: 300s

## Parameters
  - protocol [string, REQUIRED]: Protocol to target
  - target [string, REQUIRED]: Target IP, range, or CIDR notation
  - username [string, optional]: Username or file with usernames
  - password [string, optional]: Password or file with passwords
  - hash [string, optional]: NTLM hash for pass-the-hash
  - domain [string, optional]: Active Directory domain name
  - command [string, optional]: Command to execute on target
  - module [string, optional]: CrackMapExec module to run
  - extra_flags [string, optional]: Additional CrackMapExec flags

## Output Fields
  - hosts [list[dict]]: Enumerated hosts with access status
  - credentials_valid [boolean]: Whether provided credentials are valid
  - admin_access [boolean]: Whether admin access was achieved
  - command_output [string]: Output of executed command
  - raw_output [string]: Full CrackMapExec output

## Preconditions
  - [port_open] Target service must be accessible

## Postconditions
  - [gains_access] Tests credentials and executes commands across the network
  - [discovers_services] Enumerates network hosts and services

## Command Template
  crackmapexec {protocol} {target} -u '{username}' -p '{password}' -H '{hash}' -d '{domain}' -x '{command}' -M {module} {extra_flags}

# evil_winrm
Category: network_exploitation
Description: WinRM shell for Windows remote management. Provides an interactive PowerShell session over WinRM with file upload/download, DLL loading, and in-memory script execution.
Timeout: 300s

## Parameters
  - host [string, REQUIRED]: Target Windows host IP or hostname
  - username [string, REQUIRED]: Windows username
  - password [string, optional]: Windows password
  - hash [string, optional]: NTLM hash for pass-the-hash authentication
  - ssl [boolean, optional] (default: false): Use SSL for the WinRM connection
  - scripts_path [string, optional]: Path to PowerShell scripts directory
  - executables_path [string, optional]: Path to executables directory for upload
  - extra_flags [string, optional]: Additional evil-winrm flags

## Output Fields
  - session_established [boolean]: Whether a WinRM session was established
  - raw_output [string]: Full evil-winrm output

## Preconditions
  - [port_open] WinRM service (port 5985/5986) must be open on target

## Postconditions
  - [gains_access] Establishes interactive PowerShell session on target

## Command Template
  evil-winrm -i {host} -u '{username}' -p '{password}' -H '{hash}' -s {scripts_path} -e {executables_path} {extra_flags}

