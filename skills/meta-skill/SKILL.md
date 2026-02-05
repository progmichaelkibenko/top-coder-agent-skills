---
name: meta-skill
description: Guides creating and adding agent skills for any repo or purpose. Use when the user wants to create a new skill, add a skill to a repo, write a SKILL.md, or asks how to author or structure an agent skill.
---

# Meta-Skill: Add a Skill (Any Repo / Any Purpose)

Use this skill to create a new agent skill for **any** repository or use case. You gather requirements by asking the right questions, then produce a valid `SKILL.md` (and optional supporting files) that follows the [Agent Skills specification](https://agentskills.io/specification).

## When to use this skill

- User says: "Create a skill for…", "Add a skill that…", "Write a SKILL.md for…"
- User wants to add a skill to a repo (this one or any other)
- User asks how to structure or author an agent skill

**Not for:** Adding skills *only* to top-coder-agent-skills with design-pattern/architecture focus → use **top-coder-meta-skill** instead.

---

## Phase 1: Discovery — Ask These Questions

Before writing the skill, gather (or infer from context):

1. **Purpose and scope**  
   *"What specific task or workflow should this skill help with?"*  
   One clear purpose per skill.

2. **Target location**  
   *"Where should the skill live?"*  
   - Personal: `~/.cursor/skills/<name>/` (or equivalent for other agents)  
   - Project: `.cursor/skills/<name>/` in a specific repo  
   - Another repo: e.g. `skills/<name>/` in that repo

3. **Trigger scenarios**  
   *"When should the agent automatically apply this skill?"*  
   Get concrete phrases or situations (e.g. "when reviewing PRs", "when user says 'deploy my app'").

4. **Key domain knowledge**  
   *"What must the agent know that it might not already know?"*  
   Tools, conventions, formats, domain terms.

5. **Output format preferences**  
   *"Any required templates, formats, or styles?"*  
   e.g. commit message format, report structure, file naming.

6. **Existing patterns**  
   *"Any existing skills or docs to match?"*  
   Repo conventions, similar skills to align with.

**How to ask:** If the user hasn’t provided enough detail, ask these questions conversationally (or use structured prompts). If context already answers some, infer and confirm briefly. Skip only when the answer is obvious.

---

## Phase 2: Design

1. **Name:** Kebab-case, 1–64 chars, lowercase letters and hyphens. No leading/trailing or consecutive hyphens. Must match the skill directory name.  
   - ✅ `code-review`, `deploy-vercel`, `pdf-extract`  
   - ❌ `helper`, `MySkill`, `do-stuff`

2. **Description:** Third person. Include **WHAT** (what the skill does) and **WHEN** (when to activate). Trigger-heavy.  
   - ✅ "Reviews code for security and style per team standards. Use when the user asks for a code review or says 'review this PR'."  
   - ❌ "Helps with code" or "You can use this to review."

3. **Outline:** Main sections and any supporting files (`references/`, `scripts/`, `assets/`).

---

## Phase 3: Authoring Rules

When writing the generated skill:

- **Concise:** No filler. Assume a capable agent; only add context it needs.
- **SKILL.md under 500 lines.** Long content → `references/` or `examples.md`, linked one level deep from SKILL.md.
- **Paths:** Forward slashes only (e.g. `scripts/helper.py`).
- **One default approach;** avoid "you can use A, or B, or C" unless an escape hatch is needed.
- **Consistent terminology** (one term per concept).
- **No time-sensitive rules** (e.g. "before date X"); use a "Deprecated / legacy" section if needed.

### Required frontmatter

```yaml
---
name: <kebab-case-name>
description: <Third-person WHAT. Use when [WHEN/triggers].>
---
```

Optional: `license`, `compatibility`, `metadata`, `allowed-tools` (per spec).

---

## Phase 4: Implementation

1. Create the skill directory (e.g. `skills/<name>/` or the path agreed in Phase 1).
2. Write `SKILL.md` with frontmatter and body (instructions, steps, examples as needed).
3. Add `references/`, `scripts/`, or `assets/` only if needed; link from SKILL.md.
4. Ensure valid Markdown and YAML; name and description within spec limits.

---

## Phase 5: Verify

- [ ] Description is third person, specific, and includes trigger scenarios.
- [ ] Name is kebab-case and matches directory.
- [ ] SKILL.md is under 500 lines; references are one level deep.
- [ ] No Windows-style paths; terminology consistent.
- [ ] Output is ready to save and (if applicable) to install via `npx skills add` or manual copy.

---
*General Meta-Skill — for adding any agent skill, any repo*
