# Tool Reference

Tools used by the `excalibur-full_port_scan` skill.

# masscan
Category: reconnaissance
Description: High-speed TCP port scanner. Can scan the entire Internet in under 6 minutes. Ideal for quickly identifying open ports on large networks before doing detailed nmap scans.
Timeout: 300s

## Parameters
  - target [string, REQUIRED]: Target IP address or CIDR range
  - ports [string, REQUIRED]: Port specification (e.g., '0-65535', '80,443')
  - rate [string, optional] (default: 1000): Packet transmission rate (packets per second)
  - output_file [string, optional]: Path to save results
  - extra_flags [string, optional]: Additional masscan flags

## Output Fields
  - open_ports [list[int]]: List of discovered open ports
  - raw_output [string]: Full masscan output

## Preconditions
  - [root_access] Requires root/sudo for raw socket access

## Postconditions
  - [discovers_services] Discovers open TCP ports at high speed

## Command Template
  masscan {target} -p{ports} --rate={rate} -oL {output_file} {extra_flags}

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

