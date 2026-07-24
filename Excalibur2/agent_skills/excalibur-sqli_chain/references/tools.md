# Tool Reference

Tools used by the `excalibur-sqli_chain` skill.

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

# sqlmap
Category: web_exploitation
Description: Automatic SQL injection detection and exploitation tool. Supports a wide range of database backends and injection techniques including boolean-based blind, time-based blind, error-based, UNION-based, and stacked queries.
Timeout: 900s

## Parameters
  - url [string, REQUIRED]: Target URL with injectable parameter (e.g., 'http://target/page?id=1')
  - data [string, optional]: POST data string (e.g., 'user=admin&pass=test')
  - cookie [string, optional]: HTTP cookie header value
  - level [string, optional] (default: 1): Level of tests to perform (1-5)
  - risk [string, optional] (default: 1): Risk of tests to perform (1-3)
  - technique [string, optional]: SQL injection techniques to use (B/E/U/S/T/Q)
  - dbms [string, optional]: Force specific DBMS backend
  - dump [boolean, optional] (default: false): Dump database table entries
  - dbs [boolean, optional] (default: false): Enumerate databases
  - tables [boolean, optional] (default: false): Enumerate tables in database
  - batch [boolean, optional] (default: true): Non-interactive mode (use defaults)
  - extra_flags [string, optional]: Additional sqlmap flags

## Output Fields
  - injection_points [list[dict]]: Confirmed injection points and techniques
  - databases [list[str]]: Enumerated database names
  - tables [list[str]]: Enumerated table names
  - dumped_data [list[dict]]: Extracted database records
  - raw_output [string]: Full sqlmap output

## Preconditions
  - [service_running] Target web application must be accessible

## Postconditions
  - [gains_access] Detects and exploits SQL injection vulnerabilities
  - [reveals_data] May extract sensitive database contents

## Command Template
  sqlmap -u '{url}' --data='{data}' --cookie='{cookie}' --level={level} --risk={risk} --technique={technique} --dbms={dbms} --batch {extra_flags}

