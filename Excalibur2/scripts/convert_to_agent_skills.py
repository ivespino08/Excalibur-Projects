"""Convert Excalibur's internal Skill objects into Anthropic Agent Skills.

Lives at scripts/convert_to_agent_skills.py -- run from the repo root with
the project's Poetry environment active (excalibur must be importable):

    poetry run python scripts/convert_to_agent_skills.py agent_skills/

Reads the actual Skill/SkillStep definitions (via SkillEngine, the real
runtime source of truth) and emits one Agent Skills folder per skill:

    <output_dir>/excalibur-<skill-name>/
        SKILL.md
        references/tools.md

SKILL.md's steps are derived directly from each Skill's tool_sequence
(condition + parameter_mapping folded into prose) and fallback_logic, so
these stay in sync with the Python definitions rather than being a
hand-maintained duplicate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from excalibur.tools.registry import ToolRegistry
from excalibur.tools.skill import Skill, SkillEngine, SkillStep
from excalibur.tools.skills.ad_skills import get_ad_skills
from excalibur.tools.skills.pivot_skills import get_pivot_skills
from excalibur.tools.skills.privesc_skills import get_privesc_skills
from excalibur.tools.skills.recon_skills import get_recon_skills
from excalibur.tools.skills.web_skills import get_web_skills

# Hand-written, trigger-optimized descriptions. Skill.description in the
# source is written for a human reading documentation ("X workflow. Does
# Y."); Agent Skills descriptions need to additionally say *when* to use
# the skill and be a little "pushy" about it, per Agent Skills authoring
# guidance, so Claude doesn't under-trigger them mid-engagement.
TRIGGER_HINTS: dict[str, str] = {
    "kerberoasting": (
        "Use whenever the target is a domain-joined Windows/AD environment "
        "and you have at least one set of valid domain credentials -- this "
        "is one of the highest-value early moves in an AD engagement, so "
        "check for it even if not explicitly asked to \"kerberoast.\""
    ),
    "pass_the_hash": (
        "Use as soon as an NTLM hash or set of hashes has been recovered "
        "(e.g. via secretsdump) in a Windows/AD environment -- don't wait "
        "to be asked to \"pass the hash\" specifically; this is the "
        "standard next move after any hash dump."
    ),
    "asrep_roasting": (
        "Use early in any AD engagement, alongside or before kerberoasting "
        "-- AS-REP roasting needs no valid credentials at all (only a "
        "vulnerable account with Kerberos pre-auth disabled), so it's worth "
        "trying even at the very start of enumeration."
    ),
    "network_pivot": (
        "Use whenever a host has been compromised and there's an internal "
        "network segment behind it that isn't directly reachable -- this is "
        "the standard way to reach a second subnet/domain, so consider it "
        "any time lateral movement or multi-host/multi-domain engagements "
        "come up (e.g. GOAD-style environments)."
    ),
    "credential_spray": (
        "Use whenever you have a domain name and Kerberos/SMB access but no "
        "confirmed credentials yet -- especially useful as a low-noise "
        "alternative to brute-forcing a single account. Watch account "
        "lockout policies before spraying."
    ),
    "linux_enum": (
        "Use immediately after gaining any foothold (shell, low-priv user) "
        "on a Linux host -- privilege escalation enumeration should happen "
        "automatically after initial access, not only when explicitly "
        "requested."
    ),
    "windows_enum": (
        "Use immediately after gaining any foothold on a Windows host -- "
        "same rationale as linux_enum: run this automatically after initial "
        "access rather than waiting to be asked."
    ),
    "full_port_scan": (
        "Use at the start of reconnaissance against any new host or "
        "network range where the full port surface isn't known yet. This "
        "is the default first move against a fresh target."
    ),
    "service_enumeration": (
        "Use right after a port scan (or masscan/nmap fallback) has found "
        "open ports and before deciding on an exploitation path -- version "
        "and technology fingerprinting should happen automatically on any "
        "newly discovered service."
    ),
    "web_discovery": (
        "Use whenever a target exposes an HTTP/HTTPS service -- content and "
        "technology discovery should run automatically once a web service "
        "is found, not only when the user explicitly asks to \"discover "
        "content.\""
    ),
    "sqli_chain": (
        "Use whenever a web application has forms, query parameters, or API "
        "endpoints that take user input into what could be a database query "
        "-- check for SQL injection proactively rather than waiting for it "
        "to be named."
    ),
    "auth_bypass": (
        "Use whenever a login form or other authentication gate is in "
        "scope -- try bypass/default-credential/injection angles as a "
        "matter of course before assuming credentials must be brute-forced "
        "or already known."
    ),
    "file_inclusion": (
        "Use whenever a URL parameter looks like it might reference a file "
        "path, template, or page name (e.g. ?page=, ?file=, ?template=) -- "
        "check for LFI/RFI proactively, since this pattern is easy to miss "
        "if not actively looked for."
    ),
}


def format_step(step: SkillStep, index: int, registry: ToolRegistry) -> str:
    """Render one SkillStep as a numbered markdown step."""
    tool = registry.get(step.tool_name)
    tool_desc = tool.interface.description if tool else "(tool not found in registry)"
    # Trim to first sentence for a compact per-step description.
    first_sentence = tool_desc.split(". ")[0].rstrip(".") + "."

    lines = [f"{index}. **{step.tool_name}** -- {first_sentence}"]
    if step.parameter_mapping:
        mapping_str = ", ".join(f"`{k}` \u2192 `{v}`" for k, v in step.parameter_mapping.items())
        lines.append(f"   - Inputs: {mapping_str}")
    if step.condition:
        lines.append(f"   - *Only proceed with this step if:* {step.condition}")
    lines.append(f"   - See `references/tools.md` for {step.tool_name}'s full flag reference.")
    return "\n".join(lines)


def build_skill_md(skill: Skill, registry: ToolRegistry) -> str:
    trigger_hint = TRIGGER_HINTS.get(skill.name, "")
    description = skill.description.strip()
    if trigger_hint:
        description = f"{description} {trigger_hint}"
    # Frontmatter description must be a single unbroken line/paragraph.
    description = " ".join(description.split())

    title = skill.name.replace("_", " ").title()

    steps_md = "\n\n".join(
        format_step(step, i, registry) for i, step in enumerate(skill.tool_sequence, start=1)
    )

    aggregation_note = {
        "sequential": (
            "Run these steps in order -- each step depends on the previous "
            "one succeeding (or its condition being met)."
        ),
        "merge": (
            "These steps can be run independently and their results merged "
            "-- later steps don't strictly require earlier ones to succeed, "
            "but running them in order is still a reasonable default."
        ),
    }.get(skill.result_aggregation, "")

    frontmatter = yaml.safe_dump(
        {"name": f"excalibur-{skill.name}", "description": description},
        default_flow_style=False,
        sort_keys=False,
        width=1_000_000,  # keep description on one line; don't let PyYAML hard-wrap it
    ).strip()

    parts = [
        "---",
        frontmatter,
        "---",
        "",
        f"# {title}",
        "",
    ]
    if aggregation_note:
        parts.append(f"*{aggregation_note}*")
        parts.append("")
    parts.append("## Steps")
    parts.append("")
    parts.append(steps_md)
    parts.append("")
    if skill.fallback_logic:
        parts.append("## Fallback")
        parts.append("")
        parts.append(skill.fallback_logic.strip())
        parts.append("")

    return "\n".join(parts)


def build_tools_reference(skill: Skill, registry: ToolRegistry) -> str:
    seen: set[str] = set()
    sections = ["# Tool Reference", "", f"Tools used by the `excalibur-{skill.name}` skill.", ""]
    for step in skill.tool_sequence:
        if step.tool_name in seen:
            continue
        seen.add(step.tool_name)
        tool = registry.get(step.tool_name)
        if tool is None:
            sections.append(f"## {step.tool_name}\n\n(not found in registry)\n")
            continue
        sections.append(tool.get_documentation())
    return "\n".join(sections)


def main() -> None:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("agent_skills_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = ToolRegistry()
    engine = SkillEngine(registry)
    for factory in (
        get_ad_skills,
        get_pivot_skills,
        get_privesc_skills,
        get_recon_skills,
        get_web_skills,
    ):
        engine.register_skills(factory())

    for name in sorted(engine.list_skills()):
        skill = engine.get_skill(name)
        assert skill is not None
        skill_dir = output_dir / f"excalibur-{name}"
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)

        (skill_dir / "SKILL.md").write_text(build_skill_md(skill, registry) + "\n")
        (refs_dir / "tools.md").write_text(build_tools_reference(skill, registry) + "\n")
        print(f"wrote {skill_dir}")

    print(f"\n{len(engine.list_skills())} skills written to {output_dir}/")


if __name__ == "__main__":
    main()
