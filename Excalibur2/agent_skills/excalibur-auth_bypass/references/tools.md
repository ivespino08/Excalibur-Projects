# Tool Reference

Tools used by the `excalibur-auth_bypass` skill.

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

# nuclei
Category: web_exploitation
Description: Fast, template-based vulnerability scanner. Uses a large library of community-maintained templates to detect CVEs, misconfigurations, exposed panels, default credentials, and other security issues.
Timeout: 900s

## Parameters
  - target [string, REQUIRED]: Target URL, IP, or file with list of targets
  - templates [string, optional]: Specific template paths or IDs to use
  - tags [string, optional]: Template tags to filter (e.g., 'cve,rce,sqli')
  - severity [string, optional]: Severity to filter
  - rate_limit [string, optional] (default: 150): Maximum requests per second
  - concurrency [string, optional] (default: 25): Number of concurrent templates to run
  - output_file [string, optional]: Path to save results
  - extra_flags [string, optional]: Additional nuclei flags

## Output Fields
  - findings [list[dict]]: Detected vulnerabilities with severity and details
  - raw_output [string]: Full nuclei output

## Preconditions
  - [service_running] Target must be accessible
  - [file_exists] Nuclei templates must be installed/updated

## Postconditions
  - [reveals_data] Identifies known vulnerabilities and misconfigurations

## Command Template
  nuclei -u {target} -t {templates} -tags {tags} -severity {severity} -rl {rate_limit} -c {concurrency} -o {output_file} {extra_flags}

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

