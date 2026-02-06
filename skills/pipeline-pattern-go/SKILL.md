---
name: pipeline-pattern-go
description: Implements the Pipeline design pattern in Go for data transformation. Use when the user mentions pipeline pattern, or when you need a fixed sequence of stages that each transform data and pass to the next—ETL, parsing, data processing, or any linear transformation flow that runs to completion.
---

# Pipeline (Go)

**Why:** Pipeline runs data through a fixed sequence of stages. Each stage receives input, transforms it, and passes the result to the next. All stages run in order; there is no conditional “skip” or early exit (barring errors). You avoid one big function and keep each transformation in its own type.

**Hard constraints:** Stages share a single interface (e.g. `Process(data) (result, error)`). A pipeline composes stages in a fixed order and runs them one after another. Flow is linear—no branching or handler-driven termination.

---

## When to use

- **Data transformation:** Parse → normalize → enrich → serialize, where every step must run.
- **ETL / data processing:** Ingest, transform, load; or parse log lines, extract fields, aggregate.
- **Raw JSON sanitization:** Transform/sanitize JSON with one stage per field (or concern) to remove; build the pipeline conditionally from the request (e.g. add removal stages by response type or flags).
- **Parsing pipelines:** Raw input → tokenize → parse → build AST → emit.
- You need a fixed, mandatory sequence (unlike Chain of Responsibility, where handlers can short-circuit).

---

## Structure

| Role | Responsibility |
|------|-----------------|
| **Stage (interface)** | Declares `Process(data T) (T, error)` (or similar). Each stage receives data, returns transformed data. |
| **Concrete stages** | Implement the interface; one transformation per type. No “pass or stop” decision—always return result for next. |
| **Pipeline** | Holds an ordered slice of stages; runs them in sequence, passing each stage’s output as the next stage’s input. |
| **Client** | Builds the pipeline (e.g. `Pipeline{Stages: []Stage{Parse{}, Normalize{}, Enrich{}, Serialize{}}}`) and runs it with initial input. |

Data flows in one direction; each stage’s output is the next stage’s input. The pipeline runs to completion (or returns an error from a stage).

---

## Real example: access-log ETL pipeline

A pipeline that **justifies** the pattern: raw access log text → parse → filter → enrich → normalize → aggregate → serialize. Each stage has real logic; one big function would be hard to test and extend.

**Pipeline payload:** Input is `map[string]any` with `"raw"` (string). After Parse, add `"records"` (slice of maps). After Filter/Enrich/Normalize, same slice refined. After Aggregate, add `"summary"` (byEndpoint, totalRequests, errorCount, errorRate). After Serialize, replace with JSON string (or keep summary and serialize in a final stage).

### ❌ ANTI-PATTERN: One big function

```go
// Parsing, filtering, enrichment, aggregation, and output all in one place.
func ProcessAccessLogs(raw string) (string, error) {
    lines := strings.Split(strings.TrimSpace(raw), "\n")
    var records []map[string]any
    for _, line := range lines {
        // parse combined log format, skip malformed...
        if status < 400 {
            continue
        }
        geo := lookupGeo(ip)
        records = append(records, ...)
    }
    byPath := make(map[string]int)
    for _, r := range records { ... }
    return json.Marshal(map[string]any{"byEndpoint": byPath, "total": len(records)})
}
```

Problems: parse/filter/enrich/aggregate/serialize are tangled; can’t test parsing or aggregation alone; adding a stage forces edits everywhere.

### ✅ TOP-CODER PATTERN: One stage per concern, pipeline runs all

**Stage interface and pipeline:**

```go
// pipeline/pipeline.go
package pipeline

type Data = map[string]any

type Stage interface {
    Process(data Data) (Data, error)
}

type Pipeline struct {
    Stages []Stage
}

func (p *Pipeline) Run(input Data) (Data, error) {
    data := input
    var err error
    for _, stage := range p.Stages {
        data, err = stage.Process(data)
        if err != nil {
            return nil, err
        }
    }
    return data, nil
}
```

**ParseStage** — split lines, parse combined log (or JSONL), skip malformed:

```go
// pipeline/parse.go
var combinedLog = regexp.MustCompile(`^(\S+) \S+ \S+ \[([^\]]+)\] "(\w+) ([^"]+)" (\d+)`)

type ParseStage struct{}

func (ParseStage) Process(data Data) (Data, error) {
    raw, _ := data["raw"].(string)
    lines := strings.Split(strings.TrimSpace(raw), "\n")
    var records []Data
    for _, line := range lines {
        m := combinedLog.FindStringSubmatch(line)
        if m == nil {
            continue
        }
        status, _ := strconv.Atoi(m[5])
        records = append(records, Data{
            "ip": m[1], "timestamp": m[2], "method": m[3], "path": m[4], "status": status,
        })
    }
    out := make(Data)
    for k, v := range data {
        out[k] = v
    }
    out["records"] = records
    return out, nil
}
```

**FilterStage** — configurable min status and path prefix:

```go
// pipeline/filter.go
type FilterStage struct {
    MinStatus   int
    PathPrefix  string
}

func (f FilterStage) Process(data Data) (Data, error) {
    recs, _ := data["records"].([]Data)
    var out []Data
    for _, r := range recs {
        status, _ := r["status"].(int)
        if status < f.MinStatus {
            continue
        }
        if f.PathPrefix != "" {
            path, _ := r["path"].(string)
            if !strings.HasPrefix(path, f.PathPrefix) {
                continue
            }
        }
        out = append(out, r)
    }
    res := make(Data)
    for k, v := range data {
        res[k] = v
    }
    res["records"] = out
    return res, nil
}
```

**EnrichStage** — add geo from IP, derive endpoint group:

```go
// pipeline/enrich.go
type EnrichStage struct {
    GeoLookup func(ip string) (country string)
}

func (e EnrichStage) Process(data Data) (Data, error) {
    recs, _ := data["records"].([]Data)
    out := make([]Data, 0, len(recs))
    for _, r := range recs {
        ip, _ := r["ip"].(string)
        path, _ := r["path"].(string)
        parts := strings.Split(strings.Trim(path, "/"), "/")
        group := "root"
        if len(parts) > 0 && parts[0] != "" {
            group = parts[0]
        }
        r2 := make(Data)
        for k, v := range r {
            r2[k] = v
        }
        r2["country"] = e.GeoLookup(ip)
        r2["endpoint_group"] = group
        out = append(out, r2)
    }
    res := make(Data)
    for k, v := range data {
        res[k] = v
    }
    res["records"] = out
    return res, nil
}
```

**NormalizeStage** — consistent types and keys (e.g. snake_case):

```go
// pipeline/normalize.go
type NormalizeStage struct{}

func (NormalizeStage) Process(data Data) (Data, error) {
    recs, _ := data["records"].([]Data)
    out := make([]Data, 0, len(recs))
    for _, r := range recs {
        status, _ := r["status"].(int)
        out = append(out, Data{
            "ip": fmt.Sprint(r["ip"]), "method": strings.ToUpper(fmt.Sprint(r["method"])),
            "path": fmt.Sprint(r["path"]), "status": status,
            "timestamp": r["timestamp"], "country": r["country"],
            "endpoint_group": fmt.Sprint(r["endpoint_group"]),
        })
    }
    res := make(Data)
    for k, v := range data {
        res[k] = v
    }
    res["records"] = out
    return res, nil
}
```

**AggregateStage** — group by endpoint, counts and error rate:

```go
// pipeline/aggregate.go
type AggregateStage struct{}

func (AggregateStage) Process(data Data) (Data, error) {
    recs, _ := data["records"].([]Data)
    byEndpoint := make(map[string]int)
    var errorCount int
    for _, r := range recs {
        group, _ := r["endpoint_group"].(string)
        byEndpoint[group]++
        if status, _ := r["status"].(int); status >= 400 {
            errorCount++
        }
    }
    total := len(recs)
    rate := 0.0
    if total > 0 {
        rate = float64(errorCount) / float64(total)
    }
    res := make(Data)
    for k, v := range data {
        res[k] = v
    }
    res["summary"] = Data{
        "by_endpoint": byEndpoint, "total_requests": total,
        "error_count": errorCount, "error_rate": rate,
    }
    return res, nil
}
```

**SerializeStage** — JSON output:

```go
// pipeline/serialize.go
type SerializeStage struct{}

func (SerializeStage) Process(data Data) (Data, error) {
    summary, _ := data["summary"].(Data)
    if summary == nil {
        summary = data
    }
    b, err := json.MarshalIndent(summary, "", "  ")
    if err != nil {
        return nil, err
    }
    return Data{"output": string(b)}, nil
}
```

**Client** wires and runs:

```go
p := pipeline.Pipeline{
    Stages: []pipeline.Stage{
        pipeline.ParseStage{},
        pipeline.FilterStage{MinStatus: 400},
        pipeline.EnrichStage{GeoLookup: lookupGeoByIP},
        pipeline.NormalizeStage{},
        pipeline.AggregateStage{},
        pipeline.SerializeStage{},
    },
}
result, err := p.Run(pipeline.Data{"raw": logContent})
// result["output"] is JSON string
```

Benefits: each stage is one concern and testable; you can add or reorder stages (e.g. dedupe, rate detection) without touching others; fixed order and run-to-completion match the Pipeline pattern.

---

## Dynamic composition: raw JSON sanitization

**Transform raw JSON by removing/redacting fields** — **one stage per removal**, and **build the pipeline conditionally from the request** (response type, `includeX` flags, etc.). Each stage does one thing; the list of stages is chosen at runtime.

**Example:** Reusable `RemoveFieldStage(path string)` or dedicated stages (`RemoveInternalIdStage`, `RemovePasswordStage`, `RemoveAuditFieldsStage`). Build stages slice from request:

```go
func BuildSanitizePipeline(opts *SanitizeOptions) *Pipeline {
    stages := []Stage{
        RemoveInternalIdStage{},
        RemoveFieldStage{Path: "_rev"},
    }
    if opts.IsUser {
        stages = append(stages, RemovePasswordStage{}, RemoveFieldStage{Path: "tokens"})
    } else if opts.IsPayment {
        stages = append(stages, RemoveFieldStage{Path: "cardNumber"}, RemoveFieldStage{Path: "cvv"})
    }
    if !opts.IncludeAudit {
        stages = append(stages, RemoveAuditFieldsStage{})
    }
    return &Pipeline{Stages: stages}
}

// SanitizeOptions: IsUser, IsPayment, IncludeAudit (booleans)
```

Pipeline stays linear; only the **composition** is conditional.

---

## Go notes

- **Generics:** For strongly typed pipelines, use `type Stage[T any] interface { Process(T) (T, error) }` and `Pipeline[T]` so each stage’s input/output type is explicit.
- **Context:** Pass `context.Context` as the first argument to `Process(ctx context.Context, data T)` if stages need cancellation or timeouts.
- **Error handling:** Pipeline typically stops on first error; return the error from `Run`.
- **No overkill:** For two or three fixed steps, a simple sequence of function calls may be enough; use Pipeline when you have many steps or need to reuse/reorder stages.

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
