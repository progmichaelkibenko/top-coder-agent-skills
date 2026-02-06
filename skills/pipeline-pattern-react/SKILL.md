---
name: pipeline-pattern-react
description: Implements the Pipeline design pattern in React for data transformation. Use when the user mentions pipeline pattern, or when you need a fixed sequence of stages that each transform data and pass to the next—ETL-style processing in the UI, parsing, formatting pipelines, or any linear transformation flow that runs to completion.
---

# Pipeline (React)

**Why:** Pipeline runs data through a fixed sequence of stages. Each stage receives input, transforms it, and passes the result to the next. All stages run in order; there is no conditional “skip” or early exit (barring errors). You avoid one big transform function and keep each step in its own function or module.

**Hard constraints:** Stages share a single contract (e.g. `(data: T) => T`). A pipeline is an ordered list of stages run in sequence. Flow is linear—no branching or handler-driven termination.

---

## When to use

- **Data transformation in the UI:** Raw API response → normalize → map to view model → format for display (or export).
- **Formatting/export pipelines:** Data → filter → sort → format (CSV/JSON) → blob/download.
- **Raw JSON sanitization:** Transform API/state JSON with one stage per field to remove; build the pipeline conditionally from request/context (e.g. add removal stages by resource type or `includeX` flags).
- **Parsing or normalization:** User input or file content → parse → validate shape → normalize.
- You need a fixed, mandatory sequence (unlike Chain of Responsibility, where handlers can short-circuit).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Stage (type)** | Contract: `(data: T) => T` (or `(data: T) => T \| Promise<T>` for async). Pure function that takes data and returns transformed data. |
| **Concrete stages** | Pure functions; one transformation per function. No “pass or stop”—always return result for next. |
| **Pipeline** | Ordered list of stages; runner reduces over them: `stages.reduce((data, stage) => stage(data), input)`. |
| **Client** | Builds the pipeline (array of stages) and runs it with initial input (e.g. in a hook or on button click). |

Data flows in one direction; each stage’s output is the next stage’s input. The pipeline runs to completion.

---

## Real example: analytics export pipeline (client-side)

A pipeline that **justifies** the pattern: raw event list from state → validate shape → filter by date range → enrich with labels/categories → aggregate by event type (counts, totals) → format for CSV/JSON download. Each stage has real logic; one big function would be hard to test and extend.

**Pipeline payload:** Input `{ events: Event[] }` (e.g. from context or state). After Validate: same + `validEvents`. After Filter: reduced list. After Enrich: events with `label`, `category`. After Aggregate: `{ events, summary: { byType, totalCount, byDay } }`. After Format: string (CSV or JSON) ready for download.

### ❌ ANTI-PATTERN: One big function

```ts
// Validation, filtering, enrichment, aggregation, and formatting all in one.
function exportAnalytics(events: unknown[], from: Date, to: Date): string {
  const valid = events.filter((e: any) => e?.id && e?.type && e?.timestamp);
  const inRange = valid.filter((e: any) => {
    const t = new Date(e.timestamp).getTime();
    return t >= from.getTime() && t <= to.getTime();
  });
  const enriched = inRange.map(e => ({ ...e, label: getLabel(e.type), category: getCategory(e.type) }));
  const byType: Record<string, number> = {};
  enriched.forEach((e: any) => { byType[e.type] = (byType[e.type] || 0) + 1; });
  return JSON.stringify({ events: enriched, summary: { byType, total: enriched.length } });
}
```

Problems: validate/filter/enrich/aggregate/format are tangled; can’t unit-test aggregation or formatting alone; adding a stage (e.g. sort by timestamp) forces edits everywhere.

### ✅ TOP-CODER PATTERN: One stage per concern, pipeline runs all

**Pipeline runner and stage type:**

```ts
// pipeline/runPipeline.ts
export type Stage<T> = (data: T) => T;

export function runPipeline<T>(stages: Stage<T>[], input: T): T {
  return stages.reduce((data, stage) => stage(data), input);
}
```

**ValidateStage** — ensure events have required fields, coerce types:

```ts
// pipeline/stages/validate.ts
type PipelineInput = { events: unknown[] };
export const validate: Stage<PipelineInput> = (data) => {
  const validEvents = (data.events || []).filter(
    (e: any) => e != null && typeof e.id !== 'undefined' && e.type && e.timestamp
  ).map((e: any) => ({
    id: String(e.id),
    type: String(e.type),
    timestamp: new Date(e.timestamp).toISOString(),
    payload: e.payload ?? {},
  }));
  return { ...data, validEvents };
};
```

**FilterStage** — by date range (configurable via closure or options object in payload):

```ts
// pipeline/stages/filterByDate.ts
type WithValid = PipelineInput & { validEvents: Array<{ timestamp: string }> };
export function filterByDate(from: Date, to: Date): Stage<WithValid> {
  return (data) => {
    const fromMs = from.getTime();
    const toMs = to.getTime();
    const filtered = (data.validEvents || []).filter((e) => {
      const t = new Date(e.timestamp).getTime();
      return t >= fromMs && t <= toMs;
    });
    return { ...data, filteredEvents: filtered };
  };
}
```

**EnrichStage** — add label and category from event type (lookup):

```ts
// pipeline/stages/enrich.ts
type WithFiltered = WithValid & { filteredEvents: Array<{ type: string; [k: string]: unknown }> };
export function enrich(getLabel: (t: string) => string, getCategory: (t: string) => string): Stage<WithFiltered> {
  return (data) => {
    const enriched = (data.filteredEvents || []).map((e) => ({
      ...e,
      label: getLabel(e.type),
      category: getCategory(e.type),
    }));
    return { ...data, enrichedEvents: enriched };
  };
}
```

**AggregateStage** — by type and optionally by day:

```ts
// pipeline/stages/aggregate.ts
type WithEnriched = WithFiltered & { enrichedEvents: Array<{ type: string; timestamp: string }> };
export const aggregate: Stage<WithEnriched> = (data) => {
  const events = data.enrichedEvents || [];
  const byType: Record<string, number> = {};
  const byDay: Record<string, number> = {};
  events.forEach((e) => {
    byType[e.type] = (byType[e.type] || 0) + 1;
    const day = e.timestamp.slice(0, 10);
    byDay[day] = (byDay[day] || 0) + 1;
  });
  return {
    ...data,
    summary: { byType, byDay, totalCount: events.length },
  };
};
```

**FormatForExportStage** — build CSV or JSON string for download:

```ts
// pipeline/stages/formatForExport.ts
type WithSummary = WithEnriched & { summary: { byType: Record<string, number>; byDay: Record<string, number>; totalCount: number } };
export function formatForExport(format: 'json' | 'csv'): Stage<WithSummary> {
  return (data) => {
    const events = data.enrichedEvents || [];
    if (format === 'csv') {
      const header = 'id,type,timestamp,label,category\n';
      const rows = events.map((e: any) =>
        [e.id, e.type, e.timestamp, e.label, e.category].map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')
      ).join('\n');
      return { ...data, output: header + rows };
    }
    return { ...data, output: JSON.stringify({ events, summary: data.summary }, null, 2) };
  };
}
```

**Client** (hook) wires the pipeline and runs it:

```tsx
// hooks/useAnalyticsExport.ts
const pipeline = [
  validate,
  filterByDate(dateFrom, dateTo),
  enrich(getEventLabel, getEventCategory),
  aggregate,
  formatForExport('csv'),
];
const result = runPipeline(pipeline, { events: eventsFromState });
downloadAsFile(result.output, 'analytics.csv');
```

Benefits: validate/filter/enrich/aggregate/format are separate and testable; you can add stages (e.g. sort, dedupe) or switch output format without touching others; fixed order and run-to-completion match the Pipeline pattern.

---

## Dynamic composition: raw JSON sanitization

**Transform raw JSON by removing/redacting fields** — **one stage per removal**, and **build the pipeline conditionally from the request** (resource type, `includeX` flags, etc.). Each stage is a pure function; the pipeline array is chosen at runtime.

**Example:** One stage per field (or use a generic `removeField(path)`):

```ts
const removeField = (path: string): Stage<Record<string, unknown>> => (data) => {
  const parts = path.split('.');
  const out = { ...data };
  let cur: any = out;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i];
    if (cur[key] == null) return data;
    cur = cur[key] = { ...cur[key] };
  }
  delete cur[parts[parts.length - 1]];
  return out;
};

function buildSanitizePipeline(options: { isUser?: boolean; isPayment?: boolean; includeAudit?: boolean }) {
  const stages: Stage<Record<string, unknown>>[] = [
    (d) => { const { internalId, ...r } = d; return r; },
    removeField('_rev'),
  ];
  if (options.isUser) {
    stages.push((d) => { const { password, ...r } = d; return r; });
    stages.push(removeField('tokens'));
  } else if (options.isPayment) {
    stages.push(removeField('cardNumber'));
    stages.push(removeField('cvv'));
  }
  if (!options.includeAudit) {
    stages.push((d) => { const { metadata, ...r } = d; const { audit, ...m } = (d.metadata as object) || {}; return { ...r, ...(Object.keys(m).length ? { metadata: m } : {}) }; });
  }
  return stages;
}

const pipeline = buildSanitizePipeline({ isUser: true, includeAudit: false });
const sanitized = runPipeline(pipeline, rawJsonFromApi);
```

Pipeline stays linear; only the **composition** is conditional.

---

## React notes

- **Pure stages:** Keep stages as pure functions (no React, no hooks inside stages) so they are testable and reusable.
- **Stable pipeline:** Define the stage array at module scope or in a constant so it doesn’t change every render.
- **Async:** For async stages, use `(data: T) => Promise<T>` and `async reduce` or a simple loop with `await` in the runner.
- **No overkill:** For two or three fixed steps, a simple composition may be enough; use Pipeline when you have many steps or need to reuse/reorder stages.

---

## Chain of Responsibility vs Pipeline

| Feature | Pipeline | Chain of Responsibility |
|---------|----------|--------------------------|
| **Execution** | Fixed, mandatory sequence | Conditional; handler decides whether to pass to the next |
| **Flow** | Linear, no branching | Allows flexible termination and branching |
| **Termination** | Runs to completion (barring errors) | Can be terminated early by a handler |
| **Use cases** | Data processing, parsing, ETL | Event handling, approval workflows, validation, message filtering |

Use **Pipeline** when every stage must run in a fixed order (e.g. data transformation, export). Use **CoR** when handlers can short-circuit or decide not to pass (e.g. validation, contextual help).

---

## Reference

- Pipeline is a common architectural pattern; related to Unix pipes, ETL pipelines, and functional composition.
