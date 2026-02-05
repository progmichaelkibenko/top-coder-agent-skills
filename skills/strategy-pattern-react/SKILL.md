---
name: strategy-pattern-react
description: Explains and implements the Strategy pattern in React apps. Use when the user mentions strategy pattern, interchangeable algorithms, sort/export/validation strategies in the UI, or replacing conditionals with swappable behavior in components.
---

# Strategy Pattern (React)

**Why:** Strategy lets you define a family of algorithms, put each in a separate module or object, and make them interchangeable so the component or hook that uses them stays stable while behavior is swapped at runtime ([Refactoring.Guru](https://refactoring.guru/design-patterns/strategy)).

**Hard constraints:** The consumer (component or hook) must depend only on a strategy type/interface, not concrete implementations. Use composition (strategy passed as prop or from state); avoid inheritance and avoid large switch/if chains in components. Keep strategies pure and testable outside React.

---

## When to use

- Different variants of the same behavior (e.g. sort order, export format, validation rules, date formatting) and the user can switch at runtime (dropdown, toggle, route).
- A component is bloated with conditionals (e.g. `if (view === 'card') return <CardView />; else if (view === 'table') ...`); extract each variant into a strategy or strategy component.
- You need to add new behaviors without changing the consuming component (Open/Closed).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Context** | The hook or component that holds the current strategy and delegates work to it (e.g. `useSortedList(items, sortStrategy)` or a component that calls `strategy.format(data)`). |
| **Strategy (type/interface)** | Contract for all strategies (e.g. `compare(a, b): number` or `format(data): Blob`). |
| **Concrete strategies** | Plain objects or functions that implement the contract; no React in the strategy itself. |
| **Client** | The component that selects the strategy (e.g. from user input) and passes it to the context (hook or child component). |

Context does not know concrete strategy types—only the interface.

---

## Code contrast

### ❌ ANTI-PATTERN: Big component with conditionals

```tsx
// One component; every new sort option forces edits here.
function UserList({ users }: { users: User[] }) {
  const [sortBy, setSortBy] = useState<'name' | 'email' | 'date'>('name');
  const sorted = useMemo(() => {
    if (sortBy === 'name') return [...users].sort((a, b) => a.name.localeCompare(b.name));
    if (sortBy === 'email') return [...users].sort((a, b) => a.email.localeCompare(b.email));
    if (sortBy === 'date') return [...users].sort((a, b) => new Date(a.joined).getTime() - new Date(b.joined).getTime());
    return users;
  }, [users, sortBy]);
  return (/* ... */);
}
```

Problems: component owns all sort logic; adding a sort option means editing this file and the type union; sort logic is hard to test in isolation.

### ✅ TOP-CODER PATTERN: Strategy type + concrete strategies + hook + presentational component

**Strategy type** (contract):

```ts
// strategies/sortStrategy.ts
export type SortStrategy<T> = {
  id: string;
  label: string;
  compare(a: T, b: T): number;
};
```

**Concrete strategies** (pure, no React):

```ts
// strategies/sortByName.ts
import type { SortStrategy } from './sortStrategy';
import type { User } from '../types';

export const sortByName: SortStrategy<User> = {
  id: 'name',
  label: 'Name',
  compare(a, b) {
    return a.name.localeCompare(b.name);
  },
};

// strategies/sortByEmail.ts
export const sortByEmail: SortStrategy<User> = {
  id: 'email',
  label: 'Email',
  compare(a, b) {
    return a.email.localeCompare(b.email);
  },
};

// strategies/sortByDate.ts
export const sortByDate: SortStrategy<User> = {
  id: 'date',
  label: 'Joined',
  compare(a, b) {
    return new Date(a.joined).getTime() - new Date(b.joined).getTime();
  },
};
```

**Context** (custom hook — depends only on the interface):

```ts
// hooks/useSortedList.ts
import { useMemo } from 'react';
import type { SortStrategy } from '../strategies/sortStrategy';

export function useSortedList<T>(items: T[], strategy: SortStrategy<T>): T[] {
  return useMemo(
    () => [...items].sort(strategy.compare),
    [items, strategy]
  );
}
```

**Client** (component selects strategy and uses the hook):

```tsx
// components/UserList.tsx
import { useState, useCallback } from 'react';
import { useSortedList } from '../hooks/useSortedList';
import { sortByName, sortByEmail, sortByDate } from '../strategies';
import type { User } from '../types';
import type { SortStrategy } from '../strategies/sortStrategy';

const SORT_OPTIONS = [sortByName, sortByEmail, sortByDate] as const;

const getStrategyById = (id: string): SortStrategy<User> =>
  SORT_OPTIONS.find((s) => s.id === id) ?? SORT_OPTIONS[0];

export function UserList({ users }: { users: User[] }) {
  const [strategy, setStrategy] = useState<SortStrategy<User>>(SORT_OPTIONS[0]);
  const sorted = useSortedList(users, strategy);

  const handleSortChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setStrategy(getStrategyById(e.target.value));
  }, []);

  return (
    <section aria-labelledby="sort-heading">
      <h2 id="sort-heading">Users</h2>
      <label htmlFor="sort-by">Sort by</label>
      <select
        id="sort-by"
        value={strategy.id}
        onChange={handleSortChange}
        aria-label="Sort by"
      >
        {SORT_OPTIONS.map((s) => (
          <option key={s.id} value={s.id}>{s.label}</option>
        ))}
      </select>
      <ul>
        {sorted.map((user) => (
          <li key={user.id}>{user.name} — {user.email}</li>
        ))}
      </ul>
    </section>
  );
}
```

Benefits: new sort = new strategy object + add to `SORT_OPTIONS`; `UserList` and `useSortedList` stay unchanged; each strategy is a pure object, easy to unit test.

---

## Optional: strategy as a function type

When the strategy is a single function, use a function type instead of an object:

```ts
// strategies/exportStrategy.ts
export type ExportStrategy<T> = (data: T[]) => Blob;

export const exportAsCsv: ExportStrategy<User> = (data) => {
  const header = ['Name', 'Email'].join(',');
  const rows = data.map((u) => [u.name, u.email].join(','));
  return new Blob([header, ...rows].join('\n'), { type: 'text/csv' });
};

export const exportAsJson: ExportStrategy<User> = (data) => {
  return new Blob([JSON.stringify(data)], { type: 'application/json' });
};
```

A hook or component accepts `ExportStrategy<User>` and calls it on export; the client passes `exportAsCsv` or `exportAsJson` (e.g. from a button group or dropdown).

---

## Notes (Strategy in React)

- **Pass the strategy, not a type name** — The consumer receives the strategy object or function as a prop or from state; it does not branch on `strategyType === 'name'` etc. The client selects the concrete strategy and passes it in.
- **Stable strategy identity** — Define strategy objects at module scope (e.g. `SORT_OPTIONS`) so the same reference is used across renders. That keeps `useMemo` / `useEffect` dependencies correct. Do not create strategy objects inline in render (e.g. `strategy={{ id: 'x', compare: ... }}`).
- **React Context** — Use React Context for the strategy only when many components need the same strategy (e.g. theme, locale). Otherwise pass the strategy by props or local state.
- **Testing** — Strategies are plain objects or functions; unit test them without React. Test the hook with a strategy mock; test the component with React Testing Library.
- **No overkill** — If you have one or two fixed behaviors that rarely change, a simple conditional or single implementation may be enough.

---

## Reference

- [Strategy pattern — Refactoring.Guru](https://refactoring.guru/design-patterns/strategy): intent, problem/solution, structure, applicability, pros/cons.
