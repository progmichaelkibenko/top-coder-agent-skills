---
name: pipeline-pattern-nodejs
description: Implements the Pipeline design pattern in Node.js for data transformation. Use when the user mentions pipeline pattern, or when you need a fixed sequence of stages that each transform data and pass to the next—ETL, parsing, data processing, or any linear transformation flow that runs to completion.
---

# Pipeline (Node.js)

**Why:** Pipeline runs data through a fixed sequence of stages. Each stage receives input, transforms it, and passes the result to the next. All stages run in order; there is no conditional “skip” or early exit (barring errors). You avoid one big function and keep each transformation in its own stage.

**Hard constraints:** Stages share a single interface (e.g. `process(data)` returning transformed data). A pipeline composes stages in a fixed order and runs them one after another. Flow is linear—no branching or handler-driven termination.

---

## When to use

- **Data transformation:** Parse → normalize → enrich → serialize, where every step must run.
- **ETL / data processing:** Ingest, transform, load; or parse log lines, extract fields, aggregate.
- **Raw JSON sanitization:** Transform/sanitize JSON with one stage per field (or concern) to remove; build the pipeline conditionally from the request (e.g. add removal stages by response type or `includeX` flags).
- **Parsing pipelines:** Raw input → tokenize → parse → build AST → emit.
- You need a fixed, mandatory sequence (unlike Chain of Responsibility, where handlers can short-circuit).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Stage (interface)** | Declares `process(data)` (or `process(input) => output`). Each stage receives data, returns transformed data. |
| **Concrete stages** | Implement the interface; one transformation per stage. No “pass or stop” decision—always pass result to next. |
| **Pipeline** | Holds an ordered list of stages; runs them in sequence, passing each stage’s output as the next stage’s input. |
| **Client** | Builds the pipeline (e.g. `new Pipeline([parse, normalize, enrich, serialize])`) and runs it with initial input. |

Data flows in one direction; each stage’s output is the next stage’s input. The pipeline runs to completion (or fails at a stage).

---

## Real example: access-log ETL pipeline

A pipeline that **justifies** the pattern: raw access log text → parse → filter → enrich → normalize → aggregate → serialize. Each stage has real logic; combining them in one function would be hard to test and extend.

**Pipeline payload shape (evolves per stage):**
- Input: `{ raw: string }` (log file content).
- After Parse: `{ records: Array<{ ip, method, path, status, timestamp, ... }> }`.
- After Filter/Enrich/Normalize: same `records` array, refined.
- After Aggregate: `{ summary: { byEndpoint, totalRequests, errorCount, errorRate } }`.
- After Serialize: string (JSON report).

### ❌ ANTI-PATTERN: One big function

```javascript
// One function: parsing, filtering, enrichment, aggregation, and output all mixed.
function processAccessLogs(raw) {
  const lines = raw.trim().split('\n');
  const records = [];
  for (const line of lines) {
    const m = line.match(/^(\S+) \S+ \S+ \[([^\]]+)\] "(\w+) ([^"]+)" (\d+)/);
    if (!m) continue;
    const [, ip, time, method, path, status] = m;
    if (Number(status) < 400) continue;  // filter
    const geo = lookupGeo(ip);             // enrich
    records.push({ ip, method, path, status: Number(status), timestamp: time, country: geo?.country });
  }
  const byPath = {};
  for (const r of records) {
    const key = (r.path.split('/')[1] || 'root');
    byPath[key] = (byPath[key] || 0) + 1;
  }
  return JSON.stringify({ byEndpoint: byPath, total: records.length });
}
```

Problems: parse/filter/enrich/aggregate/serialize are tangled; can’t unit-test parsing or aggregation alone; adding a stage (e.g. normalize timestamps) forces edits here; reuse is impossible.

### ✅ TOP-CODER PATTERN: One stage per concern, pipeline runs all

**Pipeline runner and stage contract:**

```javascript
// pipeline/Pipeline.js
class Pipeline {
  constructor(stages) {
    this.stages = stages;
  }
  run(input) {
    return this.stages.reduce((data, stage) => stage.process(data), input);
  }
}
```

**ParseStage** — split lines, parse format (e.g. Apache combined or JSONL), skip malformed:

```javascript
// pipeline/stages/ParseStage.js
const COMBINED_LOG = /^(\S+) \S+ \S+ \[([^\]]+)\] "(\w+) ([^"]+)" (\d+)/;
class ParseStage {
  process(data) {
    const lines = (data.raw || '').trim().split(/\r?\n/).filter(Boolean);
    const records = [];
    for (const line of lines) {
      const m = line.match(COMBINED_LOG);
      if (m) {
        records.push({ ip: m[1], timestamp: m[2], method: m[3], path: m[4], status: parseInt(m[5], 10) });
      }
      // else: try JSON.parse for JSONL, or skip
    }
    return { ...data, records };
  }
}
```

**FilterStage** — e.g. only errors, or only certain paths (configurable):

```javascript
// pipeline/stages/FilterStage.js
class FilterStage {
  constructor(options = {}) {
    this.minStatus = options.minStatus ?? 400;
    this.pathPrefix = options.pathPrefix ?? null;
  }
  process(data) {
    let records = data.records || [];
    records = records.filter(r => r.status >= this.minStatus);
    if (this.pathPrefix) records = records.filter(r => r.path.startsWith(this.pathPrefix));
    return { ...data, records };
  }
}
```

**EnrichStage** — add geo from IP, derive endpoint group:

```javascript
// pipeline/stages/EnrichStage.js
class EnrichStage {
  constructor(geoLookup = (ip) => ({})) {
    this.geoLookup = geoLookup;
  }
  process(data) {
    const records = (data.records || []).map(r => ({
      ...r,
      country: this.geoLookup(r.ip)?.country ?? null,
      endpointGroup: (r.path.split('/').filter(Boolean)[0]) || 'root',
    }));
    return { ...data, records };
  }
}
```

**NormalizeStage** — consistent types and field names:

```javascript
// pipeline/stages/NormalizeStage.js
class NormalizeStage {
  process(data) {
    const records = (data.records || []).map(r => ({
      ip: String(r.ip),
      method: (r.method || 'GET').toUpperCase(),
      path: String(r.path),
      status: Number(r.status) || 0,
      timestamp: r.timestamp || null,
      country: r.country ?? null,
      endpoint_group: r.endpointGroup ?? 'root',
    }));
    return { ...data, records };
  }
}
```

**AggregateStage** — group by endpoint, compute counts and error rate:

```javascript
// pipeline/stages/AggregateStage.js
class AggregateStage {
  process(data) {
    const records = data.records || [];
    const byEndpoint = {};
    let errorCount = 0;
    for (const r of records) {
      const key = r.endpoint_group ?? 'root';
      byEndpoint[key] = (byEndpoint[key] || 0) + 1;
      if (r.status >= 400) errorCount++;
    }
    const totalRequests = records.length;
    return {
      ...data,
      summary: {
        byEndpoint,
        totalRequests,
        errorCount,
        errorRate: totalRequests ? (errorCount / totalRequests) : 0,
      },
    };
  }
}
```

**SerializeStage** — format final output:

```javascript
// pipeline/stages/SerializeStage.js
class SerializeStage {
  process(data) {
    return JSON.stringify(data.summary ?? data, null, 2);
  }
}
```

**Client** wires the pipeline and runs it:

```javascript
// services/accessLogPipeline.js
const pipeline = new Pipeline([
  new ParseStage(),
  new FilterStage({ minStatus: 400 }),
  new EnrichStage(lookupGeoByIP),
  new NormalizeStage(),
  new AggregateStage(),
  new SerializeStage(),
]);
const report = pipeline.run({ raw: logFileContent });
```

Benefits: parse/filter/enrich/normalize/aggregate/serialize are separate and testable; you can add stages (e.g. dedupe, rate-limit detection) or swap implementations without touching others; the fixed order and “run to completion” semantics match the Pipeline pattern.

---

## Dynamic composition: raw JSON sanitization

Another real case: **transform raw JSON by removing or redacting fields**, with **one stage per removal** and **conditionally add stages based on the request** (e.g. response type, user role, or `includeX` flags).

**Idea:** Build the pipeline at runtime from the request. Each stage does one thing (remove one field, or one category of fields). Order is fixed once the pipeline is built; composition is dynamic.

**Example — one stage per field to remove, conditional stages by request type:**

```javascript
// pipeline/stages/RemoveFieldStage.js — reusable stage that drops one path
class RemoveFieldStage {
  constructor(path) {
    this.path = path; // e.g. 'internalId', 'metadata.audit', 'password'
  }
  process(data) {
    const out = { ...data };
    const parts = this.path.split('.');
    let cur = out;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts[i];
      if (cur[key] == null) return data;
      cur = cur[key] = { ...cur[key] };
    }
    delete cur[parts[parts.length - 1]];
    return out;
  }
}

// Or dedicated stages per concern (easier to test and name)
class RemoveInternalIdStage {
  process(data) {
    const { internalId, ...rest } = data;
    return rest;
  }
}
class RemovePasswordStage {
  process(data) {
    const { password, ...rest } = data;
    return rest;
  }
}
class RemoveAuditFieldsStage {
  process(data) {
    const { metadata, ...rest } = data;
    const { audit, ...metaRest } = metadata || {};
    return metadata ? { ...rest, metadata: metaRest } : rest;
  }
}
```

**Build pipeline conditionally from request:**

```javascript
// services/sanitizeJson.js
function buildSanitizePipeline(options) {
  const { isUser = false, isPayment = false, includeAudit = true } = options;
  const stages = [
    new RemoveInternalIdStage(),
    new RemoveFieldStage('_rev'),
  ];
  if (isUser) {
    stages.push(new RemovePasswordStage());
    stages.push(new RemoveFieldStage('tokens'));
  } else if (isPayment) {
    stages.push(new RemoveFieldStage('cardNumber'));
    stages.push(new RemoveFieldStage('cvv'));
  }
  if (!includeAudit) {
    stages.push(new RemoveAuditFieldsStage());
  }
  return new Pipeline(stages);
}

const pipeline = buildSanitizePipeline({ isUser: true, includeAudit: false });
const sanitized = pipeline.run(rawJsonFromDb);
```

Benefits: one stage per removal, easy to test; add/remove stages without touching others; only the **list** of stages is conditional, not the flow inside.

---

## Node.js notes

- **Sync vs async:** For async stages, use `async process(data)` and `await` in the pipeline runner (e.g. `for (const stage of this.stages) { data = await stage.process(data); }`).
- **Error handling:** Pipeline typically fails fast: if a stage throws, the pipeline stops. Handle errors in the runner or in individual stages.
- **Files:** One file per stage when logic is non-trivial (e.g. `pipeline/stages/NormalizeStage.js`); pipeline runner in a shared file.
- **No overkill:** For two or three fixed steps, a simple function composition may be enough; use Pipeline when you have many steps or need to reuse/reorder stages.

---

## Chain of Responsibility vs Pipeline

| Feature | Pipeline | Chain of Responsibility |
|---------|----------|--------------------------|
| **Execution** | Fixed, mandatory sequence | Conditional; handler decides whether to pass to the next |
| **Flow** | Linear, no branching | Allows flexible termination and branching |
| **Termination** | Runs to completion (barring errors) | Can be terminated early by a handler |
| **Use cases** | Data processing, parsing, ETL | Event handling, approval workflows, validation, message filtering |

Use **Pipeline** when every stage must run in a fixed order (e.g. data transformation). Use **CoR** when handlers can short-circuit or decide not to pass (e.g. validation, approval chains).

---

## Reference

- Pipeline is a common architectural pattern; related to Unix pipes, middleware chains (with fixed flow), and ETL pipelines.
