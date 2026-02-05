# Top Coder Agent Skills

A curated collection of **agent skills** for AI coding assistants (e.g. Cursor, Claude Code). Each skill teaches the agent how to write and review code using design patterns, SOLID principles, clean code, and solid architecture—so generated code is maintainable, testable, and professional.

## What’s in this repo

Skills in this repo focus on **quality code** and **good design**, with guidance and examples for:

- **Design patterns** — When and how to apply creational, structural, and behavioral patterns (Factory, Strategy, Repository, etc.) in real code.
- **Architecture** — Layered apps, ports & adapters, domain-driven design, and how to keep boundaries clear.
- **SOLID principles** — Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion, with concrete do’s and don’ts.
- **Clean code** — Naming, small functions, low coupling, clear error handling, and readability.

Skills are written so an AI agent can **follow** them when generating or refactoring code and when **reviewing** pull requests or existing codebases.

## Languages

Skills and examples are provided for:

- **Python** — Patterns and principles applied in Python (type hints, dataclasses, protocols, dependency injection, etc.).
- **Node.js** — Same ideas in JavaScript/TypeScript (modules, interfaces, DI, testing, etc.).

Where a concept differs by language or ecosystem, the skill calls it out and gives language-specific guidance.

## Installing skills (skills CLI)

You can install skills from this repo using the [skills CLI](https://github.com/vercel-labs/skills). It works with Cursor, Claude Code, Windsurf, and other [supported agents](https://github.com/vercel-labs/skills#supported-agents).

Use **`npx skills add`** (not the deprecated `add-skill` package). Other commands: `skills list`, `skills update`, `skills remove`.

```bash
npx skills add progmichaelkibenko/top-coder-agent-skills
pnpx skills add progmichaelkibenko/top-coder-agent-skills
```

By default, skills install at **project** level (e.g. `.cursor/skills/` for Cursor). Use `-g` for global, `--list` to list skills in a repo, `--skill <name>` to install specific skills.

Skills follow the [Agent Skills specification](https://agentskills.io/specification) (SKILL.md with YAML frontmatter: `name`, `description`, optional `license`, `metadata`, etc.). Discover more at [skills.sh](https://skills.sh).

### Skills in this repo

| Skill | Description |
|-------|-------------|
| **meta-skill** | General skill for adding *any* agent skill to *any* repo. Asks discovery questions (purpose, location, triggers, domain knowledge, output format), then generates a valid SKILL.md. Use when creating a new skill elsewhere or when the user asks how to author a skill. |
| **top-coder-meta-skill** | Adds skills *to this repo only* (design patterns, architecture, SOLID, clean code). Produces Top-Coder–style SKILL.md with code contrasts and authoring best practices. Use when adding a new skill to top-coder-agent-skills. |
| **strategy-pattern-nodejs** | Explains and implements the Strategy pattern in Node.js backends. Use when the user mentions strategy pattern, interchangeable algorithms, payment/routing/validation strategies, or replacing conditionals with swappable behavior. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/strategy). |

## How to use these skills (manual)

- **Personal use:** Copy skill directories into `~/.cursor/skills/` so they’re available in all your projects.
- **Team use:** Add this repo as a submodule or copy skills into `.cursor/skills/` in your project so everyone gets the same coding standards.

Each skill lives in its own directory under `skills/<skill-name>/` with a `SKILL.md` (and optional `scripts/`, `references/`, or `assets/`). The agent uses the skill’s **description** and **instructions** to decide when to apply it and how to behave.

## Contributing

Contributions are welcome: new skills, improvements to existing ones, or more Python/Node examples. Keep skills **concise**, **actionable**, and aligned with the topics above (design patterns, architecture, SOLID, clean code).

## License

See [LICENSE](LICENSE).
