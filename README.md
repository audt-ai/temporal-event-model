# Temporal Event Model

A primitive for tracking how things change over time.

---
This repository defines a temporal modeling primitive. It provides structured ways to represent:

- **Events**: discrete changes that happened at specific times
- **Snapshots**: complete state at a point in time
- **Diffs**: what changed between two points in time
- **Timelines**: ordered sequences of events

It's a structured alternative to implicit database history or scattered audit logs.
This is not a product, not a workflow engine, not a decision system.

It does not:
- Determine whether changes are important
- Detect anomalies or unusual patterns
- Rank, score, or prioritize anything
- Trigger alerts or downstream actions
- Model intent, causality, or motivation
- Manage workflows or investigations
- Replace your audit or compliance system

The model answers "what changed, and when?" It does not answer "why it matters" or "what should be done about it."

## Use case

Use this model when you need explicit change tracking and want to separate representation from interpretation.

Good fits:
- You need to reconstruct historical state
- You're building systems where temporal relationships matter
- You want a clean primitive to build on, not a framework that makes decisions for you
- You need to share change data across systems with different interpretations

Not a good fit:
- You need alerting, monitoring, or automation out of the box
- You want something that tells you what's important
- You need a complete audit/compliance solution with retention policies and tamper-proofing
- You're looking for a turnkey product

## Quick example

An entity is created, updated, then deleted:

```json
{"event_type": "created", "timestamp": "2024-01-01T00:00:00Z", "payload": {"name": "Acme", "status": "active"}}
{"event_type": "updated", "timestamp": "2024-06-01T00:00:00Z", "payload": {"status": "inactive"}}
{"event_type": "deleted", "timestamp": "2024-12-01T00:00:00Z", "payload": {}}
```

Snapshot as of 2024-03-01:
```json
{"name": "Acme", "status": "active"}
```

Snapshot as of 2024-09-01:
```json
{"name": "Acme", "status": "inactive"}
```

Diff between them:
```json
{"changes": [{"field": "status", "before": "active", "after": "inactive"}]}
```

That's it. Events in, snapshots and diffs out. No interpretation.

## Repository contents

```
docs/               Architecture and concepts
spec/v0.1/          JSON schemas for events, snapshots, diffs, timelines
reference/python/   Minimal reference implementation
examples/           Complete worked examples
```

## Versioning

Schemas are versioned semantically. We're conservative about changes. See [docs/architecture.md](docs/architecture.md) for details.

## Status

v0.1 — Initial release. The model is stable enough to build on, but we expect to learn from real usage.

## License

Apache 2.0

---

Built by [audt](https://github.com/audt-ai)

