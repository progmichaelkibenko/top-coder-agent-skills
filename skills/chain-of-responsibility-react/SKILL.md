---
name: chain-of-responsibility-react
description: Implements the Chain of Responsibility pattern in React. Use when the user mentions chain of responsibility, CoR, or when you need to chain handlers that each process and pass to the next—validation pipelines, contextual help, event handling, or any sequential pipeline.
---

# Chain of Responsibility (React)

**Why:** Chain of Responsibility lets you pass a request (or context) along a chain of handlers. Each handler decides whether to process it and pass to the next, or short-circuit. You avoid one big function with all steps and keep each step in its own function or module ([Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility)).

**Hard constraints:** Handlers share a single contract (e.g. `handle(context) => result | pass`). The chain is an ordered list of handlers; the client runs them in sequence. No single component or function with a long if/else for every step.

---

## When to use

- **Validation:** Form or field validation (required → format → max length) where you want to add or reorder rules without editing a central validator.
- **Contextual help:** F1 or help that bubbles from leaf to container (button tooltip → panel → dialog).
- **Any sequential pipeline:** Event handling, transformation chains, or multi-step UI logic where each handler can process and pass (or stop).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Handler (type)** | Contract: e.g. `(context: Context) => void` or return result; context holds whatever the pipeline needs. |
| **Concrete handlers** | Pure functions (or objects with `handle(context)`) that process one step and the chain runner calls the next. |
| **Chain** | Ordered list of handlers; runner iterates and calls each with the same context. |
| **Client** | Builds the chain and runs it with the initial context (e.g. on blur for validation, on F1 for help). |

---

## Code contrast (validation example)

Validation is a common use; the same structure applies to any chain (help, events, etc.). Below: validation.

### ❌ ANTI-PATTERN: One validator with all rules

```tsx
// One place; every new rule forces edits.
function validateEmail(value: string): string[] {
  const errs: string[] = [];
  if (!value?.trim()) errs.push('Email is required');
  else if (!/^[^@]+@[^@]+\.\w+$/.test(value)) errs.push('Invalid email');
  else if (value.length > 255) errs.push('Email too long');
  return errs;
}
```

Problems: adding/removing a rule means editing this function; rules are hard to test in isolation; order is hardcoded.

### ✅ TOP-CODER PATTERN: Validator type + chain runner + one function per rule

**Validation context and chain runner:**

```ts
// validation/chain.ts
export type ValidationContext = {
  value: unknown;
  fieldName: string;
  errors: { field: string; message: string }[];
};

export type Validator = (ctx: ValidationContext) => void;

export function runValidationChain(
  context: ValidationContext,
  validators: Validator[]
): void {
  for (const validate of validators) {
    validate(context);
  }
}
```

**Concrete validators** (pure functions, no React):

```ts
// validation/validators/required.ts
import type { ValidationContext } from '../chain';

export const required: Validator = (ctx) => {
  if (ctx.value == null || String(ctx.value).trim() === '') {
    ctx.errors.push({ field: ctx.fieldName, message: `${ctx.fieldName} is required` });
  }
};

// validation/validators/emailFormat.ts
const EMAIL_RE = /^[^@]+@[^@]+\.\w+$/;
export const emailFormat: Validator = (ctx) => {
  if (ctx.value && !EMAIL_RE.test(String(ctx.value))) {
    ctx.errors.push({ field: ctx.fieldName, message: 'Invalid email format' });
  }
};

// validation/validators/maxLength.ts
export function maxLength(max: number): Validator {
  return (ctx) => {
    if (ctx.value != null && String(ctx.value).length > max) {
      ctx.errors.push({ field: ctx.fieldName, message: `Max ${max} characters` });
    }
  };
}
```

**Client** (component builds chain and runs on blur/submit):

```tsx
// components/EmailField.tsx
import { runValidationChain } from '../validation/chain';
import { required, emailFormat, maxLength } from '../validation/validators';

const EMAIL_VALIDATORS = [required, emailFormat, maxLength(255)];

export function EmailField({ value, onChange, onErrors }: Props) {
  const validate = useCallback(() => {
    const errors: { field: string; message: string }[] = [];
    runValidationChain(
      { value, fieldName: 'email', errors },
      EMAIL_VALIDATORS
    );
    onErrors(errors);
  }, [value, onErrors]);

  return (
    <input
      type="email"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onBlur={validate}
    />
  );
}
```

Benefits: add or reorder validators by changing the array; each validator is a pure function, easy to unit test; same pattern works for any field or form.

---

## Optional: Contextual help chain

For F1/help that bubbles from leaf to container, use the same pattern: handler type `(ctx: HelpContext) => Handled | null`, array of handlers, runner that stops on first non-null. See Refactoring.Guru’s GUI example.

---

## React notes

- **Pure validators:** Keep validation logic in plain functions outside React so they can be tested without the DOM. Components only call the chain runner with the right context.
- **Stable chain:** Define the validator array at module scope or in a constant so it doesn’t change every render.
- **Shared errors:** Pass the same `errors` array through the context so all validators append to it (collect-all). For fail-fast, have the runner stop after the first validator that adds an error.
- **No overkill:** For one or two fixed steps, a small inline function may be enough; use CoR when you have many steps or reusable chains.
- **General chains:** Same pattern works for non-validation (e.g. contextual help, event handling)—use a context that fits the domain and handlers that process and pass.

---

## Reference

- [Chain of Responsibility — Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility): intent, problem/solution, structure, applicability, GUI example (contextual help), relations with Composite/Command/Decorator.
