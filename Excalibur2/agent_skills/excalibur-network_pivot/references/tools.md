# Tool Reference

Tools used by the `excalibur-network_pivot` skill.

# chisel
Category: network_exploitation
Description: Fast TCP/UDP tunnel transported over HTTP and secured via SSH. Creates port forwards and SOCKS proxies for pivoting through compromised hosts in restricted network environments.
Timeout: 600s

## Parameters
  - mode [string, REQUIRED]: Chisel mode
  - host [string, optional]: Server address to connect to (client mode)
  - port [string, optional] (default: 8000): Listening port (server) or server port (client)
  - tunnel_spec [string, optional]: Tunnel specification (e.g., 'R:8080:127.0.0.1:80' or 'socks')
  - reverse [boolean, optional] (default: false): Allow reverse port forwarding (server mode)
  - extra_flags [string, optional]: Additional chisel flags

## Output Fields
  - tunnel_status [string]: Tunnel establishment status
  - raw_output [string]: Full chisel output

## Postconditions
  - [gains_access] Creates network tunnel for pivoting

## Command Template
  chisel {mode} --port {port} --reverse {extra_flags} {host} {tunnel_spec}

# proxychains
Category: network_exploitation
Description: Forces TCP connections made by any application to go through proxy servers like SOCKS4/5 or HTTP proxies. Essential for pivoting to scan and exploit internal networks through compromised hosts.
Timeout: 600s

## Parameters
  - command [string, REQUIRED]: Command to execute through the proxy chain
  - config_file [string, optional] (default: /etc/proxychains4.conf): Path to proxychains configuration file
  - quiet [boolean, optional] (default: true): Suppress proxychains status messages
  - extra_flags [string, optional]: Additional proxychains flags

## Output Fields
  - command_output [string]: Output from the proxied command
  - raw_output [string]: Full proxychains output

## Preconditions
  - [file_exists] Proxychains configuration must be valid
  - [service_running] At least one proxy in the chain must be accessible

## Postconditions
  - [gains_access] Routes command traffic through configured proxy chain

## Command Template
  proxychains4 -f {config_file} -q {extra_flags} {command}

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

