---
name: strategy-pattern-nodejs
description: Implements the Strategy pattern in Node.js backends. Run when the user mentions strategy pattern, or when you see or need a switch on type/method, multiple behaviors under the same contract, or interchangeable algorithms—apply this skill proactively without the user naming it.
---

# Strategy Pattern (Node.js Backend)

**Why:** Strategy lets you define a family of algorithms, put each in a separate class, and make them interchangeable so the context stays stable while behavior is swapped at runtime ([Refactoring.Guru](https://refactoring.guru/design-patterns/strategy)).

**Hard constraints:** Context must depend only on a strategy interface, not concrete implementations. Use composition (context holds a strategy reference); avoid inheritance for variant behavior. Keep each strategy in its own class/file when it has real logic.

---

## When to use

- Different variants of the same algorithm (e.g. payment methods, route builders, serializers) and you want to switch at runtime.
- A class is bloated with conditionals (e.g. `if (type === 'card') ... else if (type === 'paypal') ...`); extract each branch into a strategy.
- You need to isolate algorithm details from the rest of the backend logic (Open/Closed: add strategies without changing context).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Context** | Holds a reference to one strategy; delegates the varying work to it; exposes a setter (or constructor) so clients can inject/replace the strategy. |
| **Strategy (interface)** | Common contract for all strategies (e.g. single method like `execute(data)` or `buildRoute(origin, dest)`). |
| **Concrete strategies** | Implement the interface; each encapsulates one variant of the algorithm. |
| **Client** | Chooses a concrete strategy and passes it to the context (e.g. from request params, config, or factory). |

Context does not know concrete strategy types—only the interface.

---

## Code contrast

### ❌ ANTI-PATTERN: Bloated handler with conditionals

```javascript
// One big class; every new payment method forces edits here.
class PaymentService {
  processPayment(amount, method, details) {
    if (method === 'stripe') {
      return this.stripeCharge(amount, details);
    }
    if (method === 'paypal') {
      return this.paypalCharge(amount, details);
    }
    if (method === 'bank') {
      return this.bankTransfer(amount, details);
    }
    throw new Error('Unknown method');
  }
  stripeCharge(amount, details) { /* ... */ }
  paypalCharge(amount, details) { /* ... */ }
  bankTransfer(amount, details) { /* ... */ }
}
```

Problems: context grows with every variant; touching one method risks breaking others; hard to test in isolation; violates Open/Closed.

### ✅ TOP-CODER PATTERN: Strategy interface + concrete strategies + context

**Strategy interface** (contract):

```javascript
// strategies/payment-strategy.js (or .ts)
/** @typedef { (amount: number, details: object) => Promise<{ id: string }> } PaymentStrategy */
// In TypeScript: interface PaymentStrategy { execute(amount: number, details: object): Promise<{ id: string }>; }
```

**Concrete strategies** (one variant per class):

```javascript
// strategies/stripe-strategy.js
class StripeStrategy {
  async execute(amount, details) {
    const paymentIntent = await stripe.paymentIntents.create({ amount, ...details });
    return { id: paymentIntent.id };
  }
}

// strategies/paypal-strategy.js
class PaypalStrategy {
  async execute(amount, details) {
    const order = await paypal.orders.create({ amount, ...details });
    return { id: order.id };
  }
}
```

**Context** (depends only on the interface):

```javascript
// services/payment-context.js
class PaymentContext {
  /** @param {PaymentStrategy} strategy */
  constructor(strategy) {
    this.strategy = strategy;
  }
  setStrategy(strategy) {
    this.strategy = strategy;
  }
  async processPayment(amount, details) {
    return this.strategy.execute(amount, details);
  }
}
```

**Client** (e.g. Express route) selects strategy and calls context:

```javascript
// routes/payments.js
const strategies = { stripe: new StripeStrategy(), paypal: new PaypalStrategy() };
const context = new PaymentContext(strategies.stripe);

app.post('/pay', async (req, res) => {
  const strategy = strategies[req.body.method] || strategies.stripe;
  context.setStrategy(strategy);
  const result = await context.processPayment(req.body.amount, req.body.details);
  res.json(result);
});
```

Benefits: add new payment methods by adding a new strategy class and registering it; context and other strategies stay unchanged; each strategy is easy to unit test.

---

## Node.js backend notes

- **DI:** Prefer injecting the strategy (or a strategy factory) into the context so tests can pass mocks.
- **Async:** Strategy methods are often async (e.g. `execute()` returns a Promise); context just awaits and returns.
- **Files:** One file per concrete strategy when the logic is non-trivial (e.g. `strategies/stripe-strategy.js`); keep the interface in a shared file or type definition.
- **No overkill:** If you only have one or two fixed algorithms and they rarely change, a simple conditional or single implementation may be enough; avoid extra classes for the sake of it.

---

## Reference

- [Strategy pattern — Refactoring.Guru](https://refactoring.guru/design-patterns/strategy): intent, problem/solution, structure, applicability, pros/cons, relations with State/Command/Template Method.
