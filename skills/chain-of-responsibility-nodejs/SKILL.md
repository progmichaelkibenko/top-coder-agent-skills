---
name: chain-of-responsibility-nodejs
description: Implements the Chain of Responsibility pattern in Node.js. Use when the user mentions chain of responsibility, CoR, or when you need to chain handlers that each process and pass to the next—validation pipelines, processing steps, transformation chains, or any sequential pipeline.
---

# Chain of Responsibility (Node.js)

**Why:** Chain of Responsibility lets you pass a request (or context) along a chain of handlers. Each handler decides whether to process it and pass to the next, or short-circuit. You avoid one big function with all steps and keep each step in its own class ([Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility)).

**Hard constraints:** Handlers share a single interface (e.g. `handle(context)`). Each handler holds a reference to the next; the client composes the chain. A handler either processes and passes, or passes without processing.

---

## When to use

- **Validation:** Multi-rule validation (required → format → range) where you want to add or reorder rules without editing a single validator.
- **Any sequential pipeline:** Processing steps, transformation chains, or multi-step checks where order matters and each step can process and pass (or stop).
- You want to decouple the sender from concrete handlers and add or reorder steps without changing existing code (Single Responsibility; Open/Closed).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Handler (interface)** | Declares `handle(context)` (and optionally `setNext(next)`). All concrete handlers implement this. |
| **Base handler (optional)** | Holds `next` reference; default `handle()` forwards to `next` if present. Reduces boilerplate. |
| **Concrete handlers** | Implement `handle()`. Process the context (e.g. add errors, transform, check); call `next.handle(context)` or stop. |
| **Client** | Builds the chain (e.g. `a.setNext(b).setNext(c)`) and invokes the first handler with the initial context. |

A context object is passed through the chain; handlers read it, optionally mutate it, and pass it along (e.g. for validation: `{ value, fieldName, errors }`).

---

## Code contrast (validation example)

Validation is a common use; the same structure applies to any chain (processing, transformation, etc.). Below: validation.

### ❌ ANTI-PATTERN: One big validator with conditionals

```javascript
// One function; every new rule forces edits.
function validateOrderInput(data) {
  const errors = [];
  if (data.email == null || data.email === '') errors.push('Email is required');
  else if (!/^[^@]+@[^@]+$/.test(data.email)) errors.push('Invalid email');
  if (data.amount == null) errors.push('Amount is required');
  else if (typeof data.amount !== 'number' || data.amount <= 0 || data.amount > 10000) errors.push('Amount must be between 1 and 10000');
  return errors;
}
```

Problems: order and logic are hardcoded; adding/removing a rule touches this function; rules are hard to test in isolation; violates Open/Closed.

### ✅ TOP-CODER PATTERN: Validator interface + base handler + concrete validators + client-built chain

**Validator interface and base handler:**

```javascript
// validators/BaseValidator.js
class BaseValidator {
  constructor() {
    this.next = null;
  }
  setNext(validator) {
    this.next = validator;
    return validator;
  }
  validate(context) {
    if (this.next) return this.next.validate(context);
    return context;
  }
}
```

**Validation context** (passed through the chain):

```javascript
// validators/context.js
// { value, fieldName, errors: [] } — handlers read value, push to errors, pass context on
```

**Concrete validators** (each does one check, then passes):

```javascript
// validators/RequiredValidator.js
class RequiredValidator extends BaseValidator {
  validate(context) {
    if (context.value == null || String(context.value).trim() === '') {
      context.errors.push({ field: context.fieldName, message: `${context.fieldName} is required` });
    }
    return super.validate(context);
  }
}

// validators/EmailFormatValidator.js
class EmailFormatValidator extends BaseValidator {
  validate(context) {
    if (context.value && !/^[^@]+@[^@]+\.\w+$/.test(context.value)) {
      context.errors.push({ field: context.fieldName, message: 'Invalid email format' });
    }
    return super.validate(context);
  }
}

// validators/RangeValidator.js
class RangeValidator extends BaseValidator {
  constructor(min, max) {
    super();
    this.min = min;
    this.max = max;
  }
  validate(context) {
    const n = Number(context.value);
    if (context.value != null && (isNaN(n) || n < this.min || n > this.max)) {
      context.errors.push({ field: context.fieldName, message: `Must be between ${this.min} and ${this.max}` });
    }
    return super.validate(context);
  }
}
```

**Client** builds one chain per field and runs it (e.g. in a service or route, after reading body):

```javascript
// services/orderValidation.js
const emailChain = new RequiredValidator();
emailChain.setNext(new EmailFormatValidator());

const amountChain = new RequiredValidator();
amountChain.setNext(new RangeValidator(1, 10000));

function validateOrderInput(data) {
  const errors = [];
  emailChain.validate({ value: data.email, fieldName: 'email', errors });
  amountChain.validate({ value: data.amount, fieldName: 'amount', errors });
  return errors;
}
```

Benefits: add or reorder validators by composing the chain; each validator is a single class, easy to unit test.

---

## Node.js notes

- **Validation context:** Use a shared context object (e.g. `{ value, fieldName, errors }`) so validators can push to the same `errors` array. For fail-fast, have a handler return without calling `next` when it adds an error.
- **Sync vs async:** Validators are usually sync; if a rule needs I/O (e.g. “email not already taken”), that can be an async validator—base and chain would use async/await.
- **Files:** One file per concrete validator when logic is non-trivial (e.g. `validators/EmailFormatValidator.js`); shared base in a common file.
- **No overkill:** For one or two fixed steps, a simple function or a few conditionals may be enough; use CoR when you have many steps or dynamic composition.
- **General chains:** Same pattern works for non-validation pipelines (e.g. data transformation, enrichment, multi-step processing)—use a context that fits the domain and handlers that process and pass.

---

## Reference

- [Chain of Responsibility — Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility): intent, problem/solution, structure, applicability, pros/cons, relations with Command/Decorator/Composite.
