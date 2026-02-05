---
name: top-coder-meta-skill
description: Generates new skills for the top-coder-agent-skills repo (design patterns, architecture, SOLID, clean code). Use when the user asks to add a skill to this repo, create a design-pattern skill here, or author a SKILL.md for top-coder-agent-skills.
---

# Top-Coder Meta Skill

You are the Lead Architect for the `top-coder-agent-skills` repository. Your job is to transform abstract architectural concepts into high-precision, executable Agent Skills that follow skill-authoring best practices. This skill is **only for adding skills to this repo**.

## 🎯 Objective

Produce a new `SKILL.md` (and optional `references/`) that is modular, token-efficient, and installable via the [Agent Skills spec](https://agentskills.io/specification). Output must be ready to save under `skills/<skill-name>/` in this repository.

## 🏗️ Generation Framework

### 1. Metadata (YAML)

- **name:** Kebab-case, 1–64 chars, lowercase letters and hyphens only. No leading/trailing or consecutive hyphens. Must match the skill directory name.
  - ✅ `repository-pattern`, `dependency-inversion`
  - ❌ `helper`, `utils`, `My-Pattern`
- **description:** Third person only. Include **WHAT** (what the skill does) and **WHEN** (trigger scenarios). Use trigger-heavy phrasing so the agent knows when to activate. For pattern skills (e.g. Strategy), include both explicit triggers (user mentions the pattern) and **situational triggers** (e.g. "when you see a switch on type", "multiple behaviors under the same contract") so the skill runs proactively when the agent identifies the situation, not only when the user names the pattern.
  - ✅ "Implements the Repository pattern for data access abstraction. Use when the user mentions repository, data access layer, or abstracting persistence."
  - ✅ "Implements the Strategy pattern. Run when the user mentions strategy, or when you see/need a switch on type, same contract with different behavior, or interchangeable algorithms—apply proactively without the user naming it."
  - ❌ "Helps with repositories" or "You can use this for repos."

### 2. Core Instruction

- One-sentence "Why."
- Bulleted **Hard Constraints** (e.g. "Must use interfaces," "SKILL.md under 500 lines").

### 3. Code Contrast (required)

- **❌ ANTI-PATTERN:** Naive or spaghetti implementation.
- **✅ TOP-CODER PATTERN:** Correct use of the pattern (Python or Node as appropriate).

### 4. Trigger globs (optional)

Suggest file patterns only when useful for the target agent (e.g. Cursor). Base Agent Skills spec does not define globs; some agents support them.

## 📋 Prompting & Authoring Best Practices

Apply these when writing the generated skill:

- **Concise:** Assume the agent is capable. No filler; every sentence should earn its tokens.
- **SKILL.md size:** Keep under 500 lines. Put long references in `references/` and link from SKILL.md (one level deep).
- **Progressive disclosure:** Essential steps in SKILL.md; detailed examples or APIs in `references/REFERENCE.md` or `examples.md`.
- **Paths:** Use forward slashes only (e.g. `scripts/helper.py`), never Windows-style backslashes.
- **Options:** Prefer one clear default; add an escape hatch only if needed. Avoid "you can use A, or B, or C."
- **Terminology:** Pick one term per concept and use it consistently (e.g. "interface" vs "contract").
- **No time-sensitive rules:** Avoid "before date X use Y." Use a "Deprecated / legacy" section if needed.

## 📋 Execution Steps

1. Identify the core design pattern or principle.
2. Draft `SKILL.md` using the structure above and the authoring best practices.
3. Ensure output is valid Markdown and YAML and ready to save under `skills/<skill-name>/` in this repo.
4. **Update the README:** Add a row for the new skill to the "Skills in this repo" table in the repo root `README.md` (skill name and description).

## 🛑 Quality Gate

- **Modular:** One pattern or principle per skill.
- **Token-efficient:** No fluff; instructions and contrasts only.
- **Installable:** Valid frontmatter (name, description), spec-compliant name and description length.

---
*Top-Coder Meta Skill — for adding skills to top-coder-agent-skills only*
