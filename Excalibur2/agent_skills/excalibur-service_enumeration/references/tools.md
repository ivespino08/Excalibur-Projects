# Tool Reference

Tools used by the `excalibur-service_enumeration` skill.

# nmap
Category: reconnaissance
Description: Network exploration and security auditing tool. Discovers hosts, open ports, running services, OS versions, and potential vulnerabilities using various scan techniques.
Timeout: 600s

## Parameters
  - target [string, REQUIRED]: Target IP, hostname, CIDR range, or IP range to scan
  - ports [string, optional]: Port specification (e.g., '80,443', '1-1000', '-' for all)
  - scan_type [string, optional] (default: -sV): Scan type flags
  - scripts [string, optional]: NSE scripts to run (e.g., 'vuln', 'default,safe')
  - timing [string, optional] (default: -T4): Timing template
  - output_file [string, optional]: Path to save output (uses -oN for normal output)
  - extra_flags [string, optional]: Additional nmap flags

## Output Fields
  - open_ports [list[int]]: List of discovered open ports
  - services [list[dict]]: Service details per port (name, version, protocol)
  - os_detection [string]: Detected operating system information
  - raw_output [string]: Full nmap text output

## Preconditions
  - [host_reachable] Target host must be reachable on the network

## Postconditions
  - [discovers_services] Discovers open ports and running services on the target
  - [reveals_data] May reveal OS version and software versions

## Command Template
  nmap {scan_type} {timing} -p {ports} --script={scripts} -oN {output_file} {extra_flags} {target}

# whatweb
Category: reconnaissance
Description: Web technology fingerprinting tool. Identifies content management systems, web frameworks, server software, JavaScript libraries, and other technologies used by a website.
Timeout: 120s

## Parameters
  - target [string, REQUIRED]: Target URL or hostname
  - aggression [string, optional] (default: 1): Aggression level (1=stealthy, 3=aggressive, 4=heavy)
  - verbose [boolean, optional] (default: true): Enable verbose output
  - extra_flags [string, optional]: Additional whatweb flags

## Output Fields
  - technologies [list[dict]]: Detected technologies with versions
  - raw_output [string]: Full whatweb output

## Preconditions
  - [service_running] Target web server must be accessible

## Postconditions
  - [reveals_data] Identifies web technologies, frameworks, and server software

## Command Template
  whatweb -a {aggression} -v {extra_flags} {target}

# enum4linux
Category: reconnaissance
Description: Tool for enumerating information from Windows and Samba systems. Extracts user lists, share information, group membership, password policies, and other data via SMB/NetBIOS.
Timeout: 300s

## Parameters
  - target [string, REQUIRED]: Target IP address
  - username [string, optional]: Username for authenticated enumeration
  - password [string, optional]: Password for authenticated enumeration
  - enum_all [boolean, optional] (default: true): Run all enumeration options
  - extra_flags [string, optional]: Additional enum4linux flags

## Output Fields
  - users [list[str]]: Discovered user accounts
  - shares [list[dict]]: SMB shares with access information
  - groups [list[str]]: Discovered groups
  - password_policy [dict]: Password policy details
  - raw_output [string]: Full enum4linux output

## Preconditions
  - [port_open] SMB service (port 445 or 139) must be open on target

## Postconditions
  - [reveals_data] Enumerates users, shares, groups from SMB/NetBIOS

## Command Template
  enum4linux -a -u {username} -p {password} {extra_flags} {target}

