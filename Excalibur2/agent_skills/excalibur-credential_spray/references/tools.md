# Tool Reference

Tools used by the `excalibur-credential_spray` skill.

# kerbrute
Category: credential_attacks
Description: Tool for brute-forcing and enumerating valid Active Directory accounts through Kerberos pre-authentication. Faster and stealthier than traditional brute-force methods as it does not generate Windows logon events.
Timeout: 600s

## Parameters
  - mode [string, REQUIRED]: Kerbrute mode
  - domain [string, REQUIRED]: Target Active Directory domain
  - dc [string, optional]: Domain Controller IP address
  - users_file [string, optional]: File containing list of usernames
  - password [string, optional]: Password for password spraying
  - passwords_file [string, optional]: File containing list of passwords
  - threads [string, optional] (default: 10): Number of concurrent threads
  - output_file [string, optional]: Path to save results
  - extra_flags [string, optional]: Additional kerbrute flags

## Output Fields
  - valid_users [list[str]]: Discovered valid usernames
  - valid_credentials [list[dict]]: Discovered valid username/password pairs
  - raw_output [string]: Full kerbrute output

## Preconditions
  - [port_open] Kerberos service (port 88) must be accessible on DC

## Postconditions
  - [reveals_data] Enumerates valid AD accounts via Kerberos
  - [gains_access] Discovers valid credentials through spraying/brute-force

## Command Template
  kerbrute {mode} --dc {dc} -d {domain} {users_file} --password '{password}' --passwords {passwords_file} -t {threads} -o {output_file} {extra_flags}

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

# hydra
Category: credential_attacks
Description: Fast and flexible online password brute-forcing tool. Supports over 50 protocols including SSH, FTP, HTTP, SMB, RDP, MySQL, MSSQL, and more. Performs dictionary attacks against remote authentication services.
Timeout: 1800s

## Parameters
  - target [string, REQUIRED]: Target IP address or hostname
  - service [string, REQUIRED]: Target service protocol
  - username [string, optional]: Single username or -L for file
  - username_file [string, optional]: File containing list of usernames
  - password [string, optional]: Single password or -P for file
  - password_file [string, optional] (default: /usr/share/wordlists/rockyou.txt): File containing list of passwords
  - port [string, optional]: Target port (overrides default for service)
  - threads [string, optional] (default: 16): Number of parallel connections
  - http_path [string, optional]: HTTP form path and parameters for http-post-form
  - extra_flags [string, optional]: Additional hydra flags

## Output Fields
  - valid_credentials [list[dict]]: Discovered valid username/password combinations
  - raw_output [string]: Full hydra output

## Preconditions
  - [port_open] Target service must be accessible

## Postconditions
  - [reveals_data] Discovers valid credentials through brute-force
  - [gains_access] Valid credentials enable authentication to services

## Command Template
  hydra -l {username} -L {username_file} -p {password} -P {password_file} -s {port} -t {threads} {extra_flags} {target} {service} {http_path}

