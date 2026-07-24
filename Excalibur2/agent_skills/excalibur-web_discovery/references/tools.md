# Tool Reference

Tools used by the `excalibur-web_discovery` skill.

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

# feroxbuster
Category: reconnaissance
Description: Fast, recursive content discovery tool written in Rust. Automatically discovers directories and recursively scans them, making it effective for deep web application enumeration.
Timeout: 900s

## Parameters
  - url [string, REQUIRED]: Target URL to scan
  - wordlist [string, optional] (default: /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt): Path to wordlist file
  - extensions [string, optional]: File extensions to search for (e.g., 'php,html,txt,bak')
  - threads [string, optional] (default: 50): Number of concurrent threads
  - depth [string, optional] (default: 4): Maximum recursion depth
  - filter_status [string, optional]: Status codes to filter out (e.g., '404,500')
  - output_file [string, optional]: Path to save results
  - extra_flags [string, optional]: Additional feroxbuster flags

## Output Fields
  - discovered_paths [list[dict]]: Discovered paths with response details
  - raw_output [string]: Full feroxbuster output

## Preconditions
  - [service_running] Target web server must be accessible

## Postconditions
  - [discovers_services] Recursively discovers web directories and files

## Command Template
  feroxbuster -u {url} -w {wordlist} -x {extensions} -t {threads} -d {depth} -C {filter_status} -o {output_file} {extra_flags}

# ffuf
Category: reconnaissance
Description: Fast web fuzzer written in Go. Supports directory discovery, parameter fuzzing, vhost discovery, and POST data fuzzing with flexible filtering options.
Timeout: 600s

## Parameters
  - url [string, REQUIRED]: Target URL with FUZZ keyword (e.g., 'http://target/FUZZ')
  - wordlist [string, REQUIRED] (default: /usr/share/wordlists/dirb/common.txt): Path to wordlist file
  - method [string, optional] (default: GET): HTTP method to use
  - data [string, optional]: POST data (e.g., 'user=FUZZ&pass=FUZZ')
  - headers [string, optional]: Custom headers (e.g., 'Content-Type: application/json')
  - filter_code [string, optional]: Filter HTTP status codes (e.g., '404,500')
  - match_code [string, optional] (default: 200,204,301,302,307,401,403,405): Match HTTP status codes
  - filter_size [string, optional]: Filter response size
  - threads [string, optional] (default: 40): Number of concurrent threads
  - extra_flags [string, optional]: Additional ffuf flags

## Output Fields
  - results [list[dict]]: Matched results with status, size, and words
  - raw_output [string]: Full ffuf output

## Preconditions
  - [service_running] Target web server must be accessible
  - [file_exists] Wordlist file must exist on disk

## Postconditions
  - [discovers_services] Discovers hidden endpoints, parameters, or vhosts

## Command Template
  ffuf -u {url} -w {wordlist} -X {method} -mc {match_code} -fc {filter_code} -fs {filter_size} -t {threads} -H '{headers}' -d '{data}' {extra_flags}

