---
name: excalibur-web_discovery
description: Web content and technology discovery workflow. Starts with whatweb to fingerprint technologies, then runs feroxbuster for recursive directory/file discovery, and finally uses ffuf for parameter and vhost fuzzing if initial results warrant it. Use whenever a target exposes an HTTP/HTTPS service -- content and technology discovery should run automatically once a web service is found, not only when the user explicitly asks to "discover content."
---

# Web Discovery

*These steps can be run independently and their results merged -- later steps don't strictly require earlier ones to succeed, but running them in order is still a reasonable default.*

## Steps

1. **whatweb** -- Web technology fingerprinting tool.
   - Inputs: `target` → `url`
   - See `references/tools.md` for whatweb's full flag reference.

2. **feroxbuster** -- Fast, recursive content discovery tool written in Rust.
   - Inputs: `url` → `url`, `wordlist` → `wordlist`, `extensions` → `extensions`
   - See `references/tools.md` for feroxbuster's full flag reference.

3. **ffuf** -- Fast web fuzzer written in Go.
   - Inputs: `url` → `fuzz_url`, `wordlist` → `wordlist`
   - *Only proceed with this step if:* feroxbuster discovered application endpoints
   - See `references/tools.md` for ffuf's full flag reference.

## Fallback

If feroxbuster is unavailable, fall back to gobuster dir mode. If both fail, use ffuf with a common wordlist.

