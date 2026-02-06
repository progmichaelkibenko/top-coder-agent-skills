---
name: chain-of-responsibility-go
description: Implements the Chain of Responsibility pattern in Go. Use when the user mentions chain of responsibility, CoR, or when you need to chain handlers that each process and pass to the next—validation pipelines, processing steps, transformation chains, or any sequential pipeline.
---

# Chain of Responsibility (Go)

**Why:** Chain of Responsibility lets you pass a request (or context) along a chain of handlers. Each handler decides whether to process it and pass to the next, or short-circuit. You avoid one big function with all steps and keep each step in its own type ([Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility)).

**Hard constraints:** Handlers share a single interface (e.g. `Handle(ctx, request)`). Each handler holds a reference to the next; the client composes the chain. A handler either processes and passes, or passes without processing.

---

## When to use

- **Validation:** Multi-rule validation (required → format → range) where you want to add or reorder rules without editing a single validator.
- **Any sequential pipeline:** Processing steps, transformation chains, or multi-step checks where order matters and each step can process and pass (or stop).
- You want to decouple the sender from concrete handlers and add or reorder steps without changing existing code (Single Responsibility; Open/Closed).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Handler (interface)** | Declares `Handle(ctx, request)` (and optionally a setter for next). All concrete handlers implement this. |
| **Base handler (optional)** | Struct that holds `Next`; default `Handle()` forwards to `Next` if non-nil. Reduces boilerplate. |
| **Concrete handlers** | Implement `Handle()`. Process the request (e.g. add errors, transform, check); call `h.Next.Handle(ctx, request)` or return. |
| **Client** | Builds the chain (e.g. `a.SetNext(b); b.SetNext(c)`) and invokes the first handler with the initial request. |

A request/context struct is passed through the chain; handlers read it, optionally mutate it, and pass it along (e.g. for validation: `Value`, `FieldName`, `Errors`).

---

## Code contrast (validation example)

Validation is a common use; the same structure applies to any chain. Below: validation.

### ❌ ANTI-PATTERN: One function with all rules

```go
// One function; every new rule forces edits.
func ValidateOrderInput(data *OrderInput) []ValidationError {
    var errs []ValidationError
    if data.Email == "" {
        errs = append(errs, ValidationError{Field: "email", Message: "email is required"})
    } else if !emailRegex.MatchString(data.Email) {
        errs = append(errs, ValidationError{Field: "email", Message: "invalid email"})
    }
    if data.Amount <= 0 || data.Amount > 10000 {
        errs = append(errs, ValidationError{Field: "amount", Message: "amount must be 1-10000"})
    }
    return errs
}
```

Problems: order and logic are hardcoded; adding/removing a rule touches this function; rules are hard to test in isolation; violates Open/Closed.

### ✅ TOP-CODER PATTERN: Validator interface + base + concrete validators + client-built chain

**Validator interface and context:**

```go
// chain/validator.go
package chain

type ValidationError struct {
    Field   string
    Message string
}

type Context struct {
    Value     any
    FieldName string
    Errors    *[]ValidationError
}

type Validator interface {
    Validate(ctx *Context)
    SetNext(Validator)
}

type BaseValidator struct {
    Next Validator
}

func (b *BaseValidator) SetNext(v Validator) {
    b.Next = v
}

func (b *BaseValidator) Validate(ctx *Context) {
    if b.Next != nil {
        b.Next.Validate(ctx)
    }
}
```

**Concrete validators** (embed base, override Validate):

```go
// chain/required.go
type RequiredValidator struct {
    chain.BaseValidator
}

func (v *RequiredValidator) Validate(ctx *chain.Context) {
    if ctx.Value == nil || strings.TrimSpace(fmt.Sprint(ctx.Value)) == "" {
        *ctx.Errors = append(*ctx.Errors, chain.ValidationError{
            Field: ctx.FieldName, Message: ctx.FieldName + " is required",
        })
    }
    v.BaseValidator.Validate(ctx)
}

// chain/email_format.go
var emailRegex = regexp.MustCompile(`^[^@]+@[^@]+\.\w+$`)

type EmailFormatValidator struct {
    chain.BaseValidator
}

func (v *EmailFormatValidator) Validate(ctx *chain.Context) {
    if ctx.Value != nil && ctx.Value != "" && !emailRegex.MatchString(fmt.Sprint(ctx.Value)) {
        *ctx.Errors = append(*ctx.Errors, chain.ValidationError{
            Field: ctx.FieldName, Message: "invalid email format",
        })
    }
    v.BaseValidator.Validate(ctx)
}

// chain/range.go
type RangeValidator struct {
    Min, Max float64
    chain.BaseValidator
}

func (v *RangeValidator) Validate(ctx *chain.Context) {
    n, ok := toFloat(ctx.Value)
    if ctx.Value != nil && (!ok || n < v.Min || n > v.Max) {
        *ctx.Errors = append(*ctx.Errors, chain.ValidationError{
            Field: ctx.FieldName, Message: fmt.Sprintf("must be between %v and %v", v.Min, v.Max),
        })
    }
    v.BaseValidator.Validate(ctx)
}
```

**Client** builds one chain per field and runs it:

```go
// service/order.go
emailChain := &chain.RequiredValidator{}
emailChain.SetNext(&chain.EmailFormatValidator{})

amountChain := &chain.RequiredValidator{}
amountChain.SetNext(&chain.RangeValidator{Min: 1, Max: 10000})

func (s *Service) ValidateOrderInput(data *OrderInput) []chain.ValidationError {
    var errs []chain.ValidationError
    ctx := &chain.Context{Errors: &errs}
    ctx.Value, ctx.FieldName = data.Email, "email"
    emailChain.Validate(ctx)
    ctx.Value, ctx.FieldName = data.Amount, "amount"
    amountChain.Validate(ctx)
    return errs
}
```

Benefits: add or reorder validators by wiring the chain; each validator is a single type, easy to unit test.

---

## Go notes

- **Context struct:** Use a shared `Context` with a pointer to `Errors` so all validators append to the same slice. For fail-fast, validators can skip calling `v.BaseValidator.Validate(ctx)` when they add an error.
- **Accept interfaces, return structs:** The client depends on the `Validator` interface; concrete types implement it.
- **Packages:** One file per validator when logic is non-trivial (e.g. `chain/required.go`); keep the interface and base in `chain/validator.go`.
- **No overkill:** For one or two fixed steps, a simple function may be enough; use CoR when you have many steps or dynamic composition.
- **General chains:** Same pattern works for non-validation pipelines (e.g. data transformation, enrichment, multi-step processing)—use a request struct that fits the domain and handlers that process and pass.

---

## Reference

- [Chain of Responsibility — Refactoring.Guru](https://refactoring.guru/design-patterns/chain-of-responsibility): intent, problem/solution, structure, applicability, pros/cons, relations with Command/Decorator/Composite.
