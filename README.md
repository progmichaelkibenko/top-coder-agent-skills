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
- **Go** — Same ideas in Go (interfaces, structs, composition, context, testing, etc.).
- **React** — Same ideas in React (functional components, hooks, composition, TypeScript, testing, etc.).

Where a concept differs by language or ecosystem, the skill calls it out and gives language-specific guidance.

## Installing skills (skills CLI)

You can install skills from this repo using the [skills CLI](https://github.com/vercel-labs/skills). It works with Cursor, Claude Code, Windsurf, and other [supported agents](https://github.com/vercel-labs/skills#supported-agents).

Use **`npx skills add`** (not the deprecated `add-skill` package). Other commands: `skills list`, `skills update`, `skills remove`.

```bash
npx skills add progmichaelkibenko/top-coder-agent-skills
pnpx skills add progmichaelkibenko/top-coder-agent-skills
```

Skills follow the [Agent Skills specification](https://agentskills.io/specification) (SKILL.md with YAML frontmatter: `name`, `description`, optional `license`, `metadata`, etc.). Discover more at [skills.sh](https://skills.sh).

### Skills in this repo

| Skill | Description |
|-------|-------------|
| **meta-skill** | General skill for adding *any* agent skill to *any* repo. Asks discovery questions (purpose, location, triggers, domain knowledge, output format), then generates a valid SKILL.md. Use when creating a new skill elsewhere or when the user asks how to author a skill. |
| **top-coder-meta-skill** | Adds skills *to this repo only* (design patterns, architecture, SOLID, clean code). Produces Top-Coder–style SKILL.md with code contrasts and authoring best practices. Use when adding a new skill to top-coder-agent-skills. |
| **strategy-pattern-nodejs** | Explains and implements the Strategy pattern in Node.js backends. Use when the user mentions strategy pattern, interchangeable algorithms, payment/routing/validation strategies, or replacing conditionals with swappable behavior. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/strategy). |
| **strategy-pattern-python** | Explains and implements the Strategy pattern in Python backends. Use when the user mentions strategy pattern, interchangeable algorithms, payment/routing/validation strategies, or replacing conditionals with swappable behavior. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/strategy). |
| **strategy-pattern-go** | Explains and implements the Strategy pattern in Go backends. Use when the user mentions strategy pattern, interchangeable algorithms, payment/routing/validation strategies, or replacing conditionals with swappable behavior. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/strategy). |
| **strategy-pattern-react** | Explains and implements the Strategy pattern in React apps. Use when the user mentions strategy pattern, interchangeable algorithms, sort/export/validation strategies in the UI, or replacing conditionals with swappable behavior in components. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/strategy). |
| **chain-of-responsibility-nodejs** | Implements the Chain of Responsibility pattern in Node.js. Use when you need to chain handlers that each process and pass to the next—validation pipelines, processing steps, transformation chains, or any sequential pipeline. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility). |
| **chain-of-responsibility-go** | Implements the Chain of Responsibility pattern in Go. Use when you need to chain handlers that each process and pass to the next—validation pipelines, processing steps, transformation chains, or any sequential pipeline. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility). |
| **chain-of-responsibility-python** | Implements the Chain of Responsibility pattern in Python. Use when you need to chain handlers that each process and pass to the next—validation pipelines, processing steps, transformation chains, or any sequential pipeline. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility). |
| **chain-of-responsibility-react** | Implements the Chain of Responsibility pattern in React. Use when you need to chain handlers that each process and pass to the next—validation pipelines, contextual help, event handling, or any sequential pipeline. Source: [Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility). |
| **pipeline-pattern-nodejs** | Implements the Pipeline pattern in Node.js for data transformation. Use for fixed-sequence stages (parse → normalize → enrich → serialize)—ETL, parsing, data processing. Differs from CoR: runs to completion, no early exit. |
| **pipeline-pattern-go** | Implements the Pipeline pattern in Go for data transformation. Use for fixed-sequence stages (parse → normalize → enrich → serialize)—ETL, parsing, data processing. Differs from CoR: runs to completion, no early exit. |
| **pipeline-pattern-python** | Implements the Pipeline pattern in Python for data transformation. Use for fixed-sequence stages (parse → normalize → enrich → serialize)—ETL, parsing, data processing. Differs from CoR: runs to completion, no early exit. |
| **pipeline-pattern-react** | Implements the Pipeline pattern in React for data transformation. Use for fixed-sequence stages in the UI—formatting, export, parsing. Differs from CoR: runs to completion, no early exit. |

## How to use these skills (manual)

- **Personal use:** Copy skill directories into `~/.cursor/skills/` so they’re available in all your projects.
- **Team use:** Add this repo as a submodule or copy skills into `.cursor/skills/` in your project so everyone gets the same coding standards.

Each skill lives in its own directory under `skills/<skill-name>/` with a `SKILL.md` (and optional `scripts/`, `references/`, or `assets/`). The agent uses the skill’s **description** and **instructions** to decide when to apply it and how to behave.

## Contributing

Contributions are welcome: new skills, improvements to existing ones, or more Python/Node/Go/React examples. Keep skills **concise**, **actionable**, and aligned with the topics above (design patterns, architecture, SOLID, clean code).

## License

See [LICENSE](LICENSE).
