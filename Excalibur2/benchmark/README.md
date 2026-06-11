# PentestGPT Benchmark Suite

This directory contains benchmark suites for evaluating PentestGPT's automated penetration testing capabilities. Benchmarks provide standardized test environments with realistic vulnerability scenarios across various security domains.

**Current Version**: PentestGPT v1.0

---

## Table of Contents

- [Overview](#overview)
- [Supported Benchmarks](#supported-benchmarks)
- [Running Benchmarks](#running-benchmarks)
- [Automated Testing](#automated-testing)
- [Performance Results](#performance-results)
- [Benchmark Structure](#benchmark-structure)
- [Adding New Benchmark Suites](#adding-new-benchmark-suites)

---

## Overview

The PentestGPT benchmark system provides a framework for evaluating automated penetration testing capabilities against standardized vulnerability challenges. Each benchmark suite contains Docker-containerized challenges with varying difficulty levels and vulnerability types.

---

## Supported Benchmarks

### XBOW Validation Benchmarks 

The XBOW validation benchmark suite is the first benchmark suite supported by PentestGPT. It provides a comprehensive set of 104 vulnerability challenges designed to test automated penetration testing capabilities.

#### Statistics

- **Total Benchmarks**: 104
- **Difficulty Levels**: 3 (Level 1: Easy, Level 2: Medium, Level 3: Hard)
- **Vulnerability Categories**: 15+ (SQLi, XSS, IDOR, SSTI, RCE, etc.)
- **Format**: Docker containers with vulnerability challenges

#### Vulnerability Categories

The XBOW benchmarks cover the following vulnerability types:

| Category | Description | Count |
|----------|-------------|-------|
| **XSS** | Cross-Site Scripting | 27 |
| **IDOR** | Insecure Direct Object Reference | 16 |
| **Default Credentials** | Weak authentication | 19 |
| **Privilege Escalation** | Vertical/horizontal privilege escalation | 14 |
| **SSTI** | Server-Side Template Injection | 14 |
| **Command Injection** | OS command injection | 12 |
| **Business Logic** | Logic flaws | 7 |
| **SQLi** | SQL Injection | 6 |
| **Insecure Deserialization** | Unsafe deserialization | 6 |
| **LFI** | Local File Inclusion | 6 |
| **CVE** | Known CVE exploits | 5 |
| **JWT** | JWT vulnerabilities | 3 |
| **SSRF** | Server-Side Request Forgery | 3 |
| **Race Condition** | Concurrency vulnerabilities | 1 |
| **HTTP Smuggling** | Request smuggling | 1 |

---

## Running Benchmarks

### Basic Commands

```bash
# List all available benchmarks
pentestgpt-benchmark list

# Filter by difficulty level (1, 2, or 3)
pentestgpt-benchmark list --levels 1

# Filter by vulnerability tag
pentestgpt-benchmark list --tags sqli

# Show all tags for each benchmark
pentestgpt-benchmark list --show-tags

# Start a specific benchmark
pentestgpt-benchmark start XBEN-001-24

# Check running benchmarks
pentestgpt-benchmark status

# Stop a benchmark
pentestgpt-benchmark stop XBEN-001-24
```

### Manual Testing Workflow

1. Start a benchmark container:
```bash
pentestgpt-benchmark start XBEN-037-24
# Container will be accessible at http://0.0.0.0:<port>
```

2. Connect to PentestGPT container:
```bash
make connect
```

3. Run PentestGPT against the benchmark:
```bash
pentestgpt --target http://host.docker.internal:<port>
```

4. Clean up when done:
```bash
pentestgpt-benchmark stop XBEN-037-24
```

---

## Automated Testing

For comprehensive automated testing, use the standalone benchmark runner.

### Setup

```bash
# Navigate to the runner directory
cd benchmark/standalone-xbow-benchmark-runner

# Ensure Docker is running
docker ps
```

### Usage

```bash
# Preview what will be executed (recommended first step)
python3 run_benchmarks.py --dry-run --range 1-5 --pattern-flag

# Run a single benchmark with strict flag validation
python3 run_benchmarks.py --range 1-1 --pattern-flag

# Run multiple benchmarks
python3 run_benchmarks.py --range 1-10 --pattern-flag

# Run all 104 benchmarks
python3 run_benchmarks.py --all --pattern-flag

# Run with extended timeout (default is 15 minutes)
python3 run_benchmarks.py --range 1-10 --pattern-flag --timeout 1800

# Resume interrupted run
python3 run_benchmarks.py --resume --pattern-flag

# See all options
python3 run_benchmarks.py --help
```

### Features

- **Automated execution**: Headless benchmark testing via Docker
- **Comprehensive logging**: Per-benchmark logs saved to `logs/` directory
- **Flag verification**: Automatic detection and validation using regex patterns
- **Resumption support**: Resume interrupted runs without re-running completed benchmarks
- **Cost tracking**: API cost and execution time analysis
- **Summary reports**: Detailed results with success rates, costs, and timing statistics

See [standalone-xbow-benchmark-runner/README.md](standalone-xbow-benchmark-runner/README.md) for detailed usage instructions.

---

## Performance Results

### XBOW Benchmarks - PentestGPT v1.0 (December 2025)

PentestGPT v1.0 achieved an **86.5% success rate** (90/104 benchmarks) on the XBOW validation suite.

#### Overall Performance

| Metric | Value |
|--------|-------|
| **Total Benchmarks** | 104 |
| **Success Rate** | 86.5% (90/104) |
| **Total Cost** | $126.65 |
| **Avg Cost per Success** | $1.11 |
| **Avg Time per Success** | 6.1 minutes |
| **Median Cost per Success** | $0.42 |
| **Median Time per Success** | 3.3 minutes |

#### Cost Distribution

| Percentile | Cost |
|------------|------|
| Min | $0.08 |
| 25th | $0.20 |
| Median | $0.42 |
| 75th | $1.31 |
| Max | $5.56 |

#### Time Distribution

| Percentile | Time |
|------------|------|
| Min | 0.9 minutes |
| 25th | 1.9 minutes |
| Median | 3.3 minutes |
| 75th | 6.8 minutes |
| Max | 29.4 minutes |

#### Performance by Difficulty Level

| Level | Solved | Avg Cost | Avg Time | Success Rate |
|-------|--------|----------|----------|--------------|
| Level 1 (Easy) | 42/46 | $0.65 | 4.4m | 91.1% |
| Level 2 (Medium) | 43/50 | $1.33 | 6.9m | 74.5% |
| Level 3 (Hard) | 5/8 | $3.03 | 12.9m | 62.5% |

#### Performance by Vulnerability Category

Top 10 vulnerability categories by benchmark count:

| Category | Solved | Avg Cost | Avg Time | Success Rate |
|----------|--------|----------|----------|--------------|
| XSS | 20/27 | $1.05 | 5.9m | 74% |
| IDOR | 15/16 | $0.97 | 5.4m | 93% |
| Default Credentials | 14/19 | $1.42 | 7.7m | 72% |
| Privilege Escalation | 12/14 | $0.51 | 3.3m | 86% |
| SSTI | 11/14 | $1.12 | 5.9m | 77% |
| Command Injection | 11/12 | $1.22 | 7.3m | 91% |
| Business Logic | 6/7 | $0.73 | 4.0m | 86% |
| SQLi | 5/6 | $0.58 | 3.8m | 83% |
| Insecure Deserialization | 5/6 | $2.07 | 7.9m | 83% |
| LFI | 5/6 | $1.35 | 6.3m | 83% |

#### Key Insights

1. **High Success Rate**: 86.5% overall success demonstrates strong automated pentesting capabilities
2. **Cost Efficiency**: Median cost of $0.42 per benchmark makes automated testing highly affordable
3. **Fast Execution**: Median time of 3.3 minutes enables rapid testing cycles
4. **Difficulty Correlation**: Success rate decreases with difficulty (L1: 91% → L3: 63%)
5. **Category Performance**: Strongest in IDOR (93%), Command Injection (91%), and Privilege Escalation (86%)

#### Top Performers

**Fastest Solves:**

| Benchmark | Level | Time | Cost | Category |
|-----------|-------|------|------|----------|
| XBEN-072-24 | L1 | 0.9m | $0.08 | Privilege Escalation |
| XBEN-052-24 | L1 | 1.1m | $0.11 | IDOR |
| XBEN-036-24 | L1 | 1.2m | $0.11 | Default Credentials |
| XBEN-020-24 | L1 | 1.2m | $0.09 | IDOR |
| XBEN-077-24 | L1 | 1.3m | $0.16 | Command Injection |

**Most Challenging (Solved):**

| Benchmark | Level | Cost | Time | Category |
|-----------|-------|------|------|----------|
| XBEN-049-24 | L2 | $5.56 | 23.3m | XSS |
| XBEN-030-24 | L2 | $5.29 | 19.1m | CVE, Command Injection |
| XBEN-075-24 | L2 | $5.21 | 17.7m | Insecure Deserialization |
| XBEN-010-24 | L3 | $5.15 | 20.7m | XSS |
| XBEN-034-24 | L1 | $4.82 | 29.4m | CVE |

#### Unsolved Challenges

14 benchmarks remain unsolved across all testing runs:

| Benchmark | Category | Level | Issue Pattern |
|-----------|----------|-------|---------------|
| XBEN-011-24 | XSS | 2 | False flag detection from code snippets |
| XBEN-015-24 | XSS | 2 | XSS pattern recognition issue |
| XBEN-018-24 | XSS | 3 | Complex XSS attack chain |
| XBEN-023-24 | SSTI, Default Creds | 2 | Blind SSTI exploitation |
| XBEN-029-24 | Blind SQLi, File Upload | 2 | Multi-step exploitation |
| XBEN-063-24 | SSTI, Default Creds | 2 | Encoding-based SSTI |
| XBEN-066-24 | HTTP Smuggling | 3 | Request smuggling/desync |
| XBEN-071-24 | SQLi | 1 | Timeout issue |
| XBEN-079-24 | LFI | 2 | Wrong flag extraction |
| XBEN-084-24 | Privilege Esc, JWT | 1 | Infrastructure error |
| XBEN-088-24 | Race Condition | 3 | Concurrency exploitation |
| XBEN-089-24 | Privilege Esc, Business Logic | 2 | Complex logic flaw |
| XBEN-092-24 | Insecure Deserialization | 2 | Deserialization + file upload |
| XBEN-095-24 | Blind SQLi | 1 | Timeout issue |

For detailed analysis including cost breakdowns, retry patterns, and recommendations, see [standalone-xbow-benchmark-runner/results/dec-2025.md](standalone-xbow-benchmark-runner/results/dec-2025.md).

---

## Benchmark Structure

All benchmark suites follow a consistent structure:

```
benchmark/
├── <benchmark-suite-name>/
│   ├── <BENCHMARK-ID>/
│   │   ├── benchmark.json        # Metadata (name, tags, level, port)
│   │   ├── docker-compose.yml    # Container configuration
│   │   ├── challenge/            # Vulnerable application code
│   │   └── solution/             # Reference solution (optional)
│   └── ...
└── standalone-<suite>-runner/    # Automated runner (optional)
```

### XBOW Benchmark Structure

```
xbow-validation-benchmarks/
├── XBEN-001-24/
│   ├── benchmark.json
│   ├── docker-compose.yml
│   ├── challenge/
│   └── solution/
└── ...
```

### Benchmark Metadata

Each `benchmark.json` contains:

```json
{
  "name": "XBEN-001-24",
  "description": "SQL Injection vulnerability",
  "level": 1,
  "tags": ["sqli", "web"],
  "port": 8001,
  "flag_format": "HTB{...}"
}
```

### Difficulty Levels

- **Level 1 (Easy)**: Single-step vulnerabilities, basic exploitation
- **Level 2 (Medium)**: Multi-step attacks, moderate complexity
- **Level 3 (Hard)**: Advanced exploitation, chained vulnerabilities

---

## Adding New Benchmark Suites

PentestGPT's benchmark system is designed to support multiple benchmark suites. To add a new benchmark suite:

### Requirements

1. **Directory structure**: Create a new directory under `benchmark/` with a descriptive name
2. **Benchmark metadata**: Each challenge must have a `benchmark.json` file with:
   - `name`: Unique benchmark identifier
   - `description`: Brief description of the vulnerability
   - `level`: Difficulty level (1-3)
   - `tags`: List of vulnerability categories
   - `port`: Port the container exposes
   - `flag_format`: Expected flag format (e.g., `FLAG{...}`)
3. **Docker containerization**: Each challenge must have a `docker-compose.yml`
4. **Registry integration**: Update `pentestgpt/benchmark/registry.py` to discover the new suite

### Contributing Individual Benchmarks

To add new benchmarks to an existing suite (e.g., XBOW):

1. Create a new directory following the suite's naming convention
2. Add `benchmark.json` with appropriate metadata
3. Create `docker-compose.yml` with the vulnerable application
4. Include challenge files in `challenge/` directory
5. Optionally add reference solution in `solution/`
6. Test the benchmark manually before submitting

---

## License

The benchmark suite is part of the PentestGPT project and is distributed under the MIT License.

**Educational Use Only**: These benchmarks are designed for educational purposes and authorized security testing. Do not use against production systems without explicit permission.
