# Tool Reference

Tools used by the `excalibur-asrep_roasting` skill.

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

# hashcat
Category: credential_attacks
Description: World's fastest and most advanced password recovery utility. Supports over 300 hash types and five attack modes including dictionary, combinator, brute-force, rule-based, and hybrid. GPU-accelerated for maximum performance.
Timeout: 3600s

## Parameters
  - hash_file [string, REQUIRED]: Path to file containing hashes to crack
  - hash_type [string, REQUIRED]: Hash type code (e.g., '0' for MD5, '1000' for NTLM, '13100' for Kerberoasting)
  - attack_mode [string, optional] (default: 0): Attack mode (0=dict, 1=combinator, 3=brute, 6=hybrid, 7=hybrid)
  - wordlist [string, optional] (default: /usr/share/wordlists/rockyou.txt): Path to wordlist (for dictionary/hybrid attacks)
  - rules [string, optional]: Path to rules file for mangling
  - mask [string, optional]: Brute-force mask (e.g., '?u?l?l?l?l?d?d?d')
  - output_file [string, optional]: Path to save cracked passwords
  - force [boolean, optional] (default: false): Force execution even with warnings (CPU-only mode)
  - extra_flags [string, optional]: Additional hashcat flags

## Output Fields
  - cracked [list[dict]]: Cracked hash:password pairs
  - stats [dict]: Cracking statistics (speed, progress, recovered)
  - raw_output [string]: Full hashcat output

## Preconditions
  - [file_exists] Hash file must exist
  - [file_exists] Wordlist must exist (for dictionary-based attacks)

## Postconditions
  - [reveals_data] Recovers plaintext passwords from hashes

## Command Template
  hashcat -m {hash_type} -a {attack_mode} {hash_file} {wordlist} -r {rules} --mask {mask} -o {output_file} --force {extra_flags}

