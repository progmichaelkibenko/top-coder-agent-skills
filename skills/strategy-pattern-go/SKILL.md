---
name: strategy-pattern-go
description: Explains and implements the Strategy pattern in Go backends. Use when the user mentions strategy pattern, interchangeable algorithms, payment/routing/validation strategies, or replacing conditionals with swappable behavior.
---

# Strategy Pattern (Go Backend)

**Why:** Strategy lets you define a family of algorithms, put each in a separate type, and make them interchangeable so the context stays stable while behavior is swapped at runtime ([Refactoring.Guru](https://refactoring.guru/design-patterns/strategy)).

**Hard constraints:** Context must depend only on a strategy interface, not concrete implementations. Use composition (context holds an interface value); avoid embedding or inheritance for variant behavior. Keep each strategy in its own type/package when it has real logic.

---

## When to use

- Different variants of the same algorithm (e.g. payment methods, route builders, serializers) and you want to switch at runtime.
- A handler or service is bloated with conditionals (e.g. `switch method { case "stripe": ... case "paypal": ... }`); extract each branch into a type that satisfies an interface.
- You need to isolate algorithm details from the rest of the backend logic (Open/Closed: add strategies without changing context).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Context** | Holds a field of strategy interface type; delegates the varying work to it; exposes a setter (or constructor) so clients can inject/replace the strategy. |
| **Strategy (interface)** | Contract for all strategies (e.g. single method like `Execute(ctx, data)` or `BuildRoute(origin, dest)`). |
| **Concrete strategies** | Types that implement the interface; each encapsulates one variant of the algorithm. |
| **Client** | Chooses a concrete strategy and passes it to the context (e.g. from request params, config, or a registry). |

Context does not know concrete strategy types—only the interface.

---

## Code contrast

### ❌ ANTI-PATTERN: Bloated handler with switch

```go
// One struct; every new payment method forces edits here.
type PaymentService struct{}

func (s *PaymentService) ProcessPayment(ctx context.Context, amount float64, method string, details map[string]any) (PaymentResult, error) {
    switch method {
    case "stripe":
        return s.stripeCharge(ctx, amount, details)
    case "paypal":
        return s.paypalCharge(ctx, amount, details)
    case "bank":
        return s.bankTransfer(ctx, amount, details)
    default:
        return PaymentResult{}, fmt.Errorf("unknown method: %s", method)
    }
}

func (s *PaymentService) stripeCharge(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error) { ... }
func (s *PaymentService) paypalCharge(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error) { ... }
func (s *PaymentService) bankTransfer(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error) { ... }
```

Problems: context grows with every variant; touching one branch risks breaking others; hard to test in isolation; violates Open/Closed.

### ✅ TOP-CODER PATTERN: Strategy interface + concrete types + context

**Strategy interface** (contract):

```go
// strategy/payment.go
package strategy

import "context"

type PaymentResult struct {
    ID string
}

type PaymentStrategy interface {
    Execute(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error)
}
```

**Concrete strategies** (one variant per type):

```go
// strategy/stripe.go
package strategy

import "context"

type StripeStrategy struct {
    Client *stripe.Client
}

func (s *StripeStrategy) Execute(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error) {
    intent, err := s.Client.CreatePaymentIntent(ctx, amount, details)
    if err != nil {
        return PaymentResult{}, err
    }
    return PaymentResult{ID: intent.ID}, nil
}

// strategy/paypal.go
type PaypalStrategy struct {
    Client *paypal.Client
}

func (s *PaypalStrategy) Execute(ctx context.Context, amount float64, details map[string]any) (PaymentResult, error) {
    order, err := s.Client.CreateOrder(ctx, amount, details)
    if err != nil {
        return PaymentResult{}, err
    }
    return PaymentResult{ID: order.ID}, nil
}
```

**Context** (depends only on the interface):

```go
// payment/context.go
package payment

import (
    "context"
    "yourmodule/strategy"
)

type Context struct {
    strategy strategy.PaymentStrategy
}

func NewContext(s strategy.PaymentStrategy) *Context {
    return &Context{strategy: s}
}

func (c *Context) SetStrategy(s strategy.PaymentStrategy) {
    c.strategy = s
}

func (c *Context) ProcessPayment(ctx context.Context, amount float64, details map[string]any) (strategy.PaymentResult, error) {
    return c.strategy.Execute(ctx, amount, details)
}
```

**Client** (e.g. HTTP handler) selects strategy and calls context:

```go
// handler/payment.go
var strategies = map[string]strategy.PaymentStrategy{
    "stripe": &strategy.StripeStrategy{Client: stripeClient},
    "paypal": &strategy.PaypalStrategy{Client: paypalClient},
}

func (h *Handler) Pay(w http.ResponseWriter, r *http.Request) {
    method := r.URL.Query().Get("method")
    if method == "" {
        method = "stripe"
    }
    s, ok := strategies[method]
    if !ok {
        s = strategies["stripe"]
    }
    payCtx := payment.NewContext(s)
    result, err := payCtx.ProcessPayment(r.Context(), amount, details)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    json.NewEncoder(w).Encode(result)
}
```

Benefits: add new payment methods by adding a type that implements the interface and registering it; context and other strategies stay unchanged; each strategy is easy to unit test.

---

## Go backend notes

- **Interfaces:** Define the strategy interface in the same package as the context (or a shared package). Prefer small interfaces (e.g. one method); concrete types in other packages implement them without importing the context.
- **Accept interfaces, return structs:** Context accepts `PaymentStrategy` (interface); handlers pass concrete `*StripeStrategy`, etc. Return concrete structs from constructors.
- **Context:** Pass `context.Context` as the first argument in strategy methods for cancellation, timeouts, and request-scoped values.
- **Packages:** One file or package per strategy when logic is non-trivial (e.g. `strategy/stripe.go`); keep the interface in a small shared file (e.g. `strategy/payment.go`).
- **Testing:** Inject a mock that implements the interface into the context; no need for the real Stripe/Paypal clients in unit tests.
- **No overkill:** If you only have one or two fixed algorithms and they rarely change, a simple switch or function field may be enough; avoid extra types for the sake of it.

---

## Reference

- [Strategy pattern — Refactoring.Guru](https://refactoring.guru/design-patterns/strategy): intent, problem/solution, structure, applicability, pros/cons, relations with State/Command/Template Method.
