# Tool Reference

Tools used by the `excalibur-file_inclusion` skill.

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

# wfuzz
Category: web_exploitation
Description: Web application bruteforcer/fuzzer. Replaces FUZZ keyword in URLs, headers, POST data, and cookies with wordlist payloads. Supports multiple injection points and recursive fuzzing.
Timeout: 600s

## Parameters
  - url [string, REQUIRED]: Target URL with FUZZ keyword for injection point
  - wordlist [string, REQUIRED] (default: /usr/share/wordlists/dirb/common.txt): Path to wordlist file
  - data [string, optional]: POST data (e.g., 'user=FUZZ&pass=FUZZ')
  - cookie [string, optional]: Cookie string
  - header [string, optional]: Custom header (e.g., 'Authorization: Bearer FUZZ')
  - hide_code [string, optional]: Hide responses with these HTTP codes (e.g., '404,500')
  - show_code [string, optional]: Show only responses with these HTTP codes
  - hide_chars [string, optional]: Hide responses with this character count
  - threads [string, optional] (default: 20): Number of concurrent threads
  - extra_flags [string, optional]: Additional wfuzz flags

## Output Fields
  - results [list[dict]]: Fuzzing results with response details
  - raw_output [string]: Full wfuzz output

## Preconditions
  - [service_running] Target web application must be accessible

## Postconditions
  - [discovers_services] Discovers valid endpoints, parameters, or credentials

## Command Template
  wfuzz -z file,{wordlist} -u {url} -d '{data}' -b '{cookie}' -H '{header}' --hc {hide_code} --sc {show_code} --hh {hide_chars} -t {threads} {extra_flags}

# commix
Category: web_exploitation
Description: Automated tool for detecting and exploiting command injection vulnerabilities. Supports result-based, blind (time-based), and file-based injection techniques across multiple OS types.
Timeout: 600s

## Parameters
  - url [string, REQUIRED]: Target URL with injectable parameter
  - data [string, optional]: POST data with injectable parameter
  - cookie [string, optional]: HTTP cookie header value
  - level [string, optional] (default: 1): Level of tests to perform (1-3)
  - technique [string, optional]: Injection techniques (c=classic, e=eval, t=time, f=file)
  - os [string, optional]: Target operating system
  - batch [boolean, optional] (default: true): Non-interactive mode
  - extra_flags [string, optional]: Additional commix flags

## Output Fields
  - vulnerable [boolean]: Whether command injection was detected
  - injection_type [string]: Type of injection detected
  - raw_output [string]: Full commix output

## Preconditions
  - [service_running] Target web application must be accessible

## Postconditions
  - [gains_access] Detects and exploits OS command injection vulnerabilities

## Command Template
  commix --url='{url}' --data='{data}' --cookie='{cookie}' --level={level} --technique={technique} --os={os} --batch {extra_flags}

