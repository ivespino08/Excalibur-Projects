# Tool Reference

Tools used by the `excalibur-linux_enum` skill.

# linpeas
Category: privilege_escalation
Description: Linux Privilege Escalation Awesome Script. Enumerates system information, processes, cron jobs, SUID/SGID binaries, writable files, capabilities, kernel exploits, and other privilege escalation vectors on Linux/Unix systems.
Timeout: 600s

## Parameters
  - intensity [string, optional] (default: normal): Scan intensity level
  - checks [string, optional]: Specific check categories to run (e.g., 'SysI,Devs,AvaSof,ProCronSrworworworworv')
  - password [string, optional]: Current user password for sudo checks
  - network [boolean, optional] (default: true): Include network enumeration checks
  - output_file [string, optional]: Path to save output
  - extra_flags [string, optional]: Additional linpeas flags

## Output Fields
  - suid_binaries [list[str]]: SUID/SGID binaries found
  - writable_paths [list[str]]: Writable paths in sensitive locations
  - cron_jobs [list[dict]]: Discovered cron jobs and scheduled tasks
  - kernel_exploits [list[str]]: Potential kernel exploit suggestions
  - credentials_found [list[dict]]: Passwords and credentials found in files
  - raw_output [string]: Full linpeas output

## Preconditions
  - [os_type] Must have shell access on a Linux/Unix system

## Postconditions
  - [reveals_data] Identifies privilege escalation vectors on Linux

## Command Template
  curl -fsSL https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | bash -s -- -a {extra_flags} 2>&1 | tee {output_file}

# pspy
Category: privilege_escalation
Description: Unprivileged Linux process snooping tool. Monitors running processes, cron jobs, and commands executed by other users without requiring root privileges. Uses inotify to detect process creation events.
Timeout: 300s

## Parameters
  - print_commands [boolean, optional] (default: true): Print commands run by processes
  - print_file_events [boolean, optional] (default: true): Print file system events
  - directories [string, optional] (default: /tmp,/var,/home,/usr,/opt): Directories to watch (comma-separated)
  - color [boolean, optional] (default: true): Enable colored output
  - extra_flags [string, optional]: Additional pspy flags

## Output Fields
  - processes [list[dict]]: Observed process executions with user and command
  - cron_commands [list[dict]]: Detected cron job executions
  - raw_output [string]: Full pspy output

## Preconditions
  - [os_type] Must have shell access on a Linux system

## Postconditions
  - [reveals_data] Reveals processes, cron jobs, and commands by other users

## Command Template
  ./pspy64 -p -f -d {directories} {extra_flags}

