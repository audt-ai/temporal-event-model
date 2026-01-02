# Temporal Event Model v0.1 — Architecture

This document describes the design and architecture of the temporal event model. It's meant to be read by engineers who want to understand what we're building and why.

---

## 1. Problem Statement

Most systems treat time as an afterthought. You update a record, and the old value is gone. Maybe there's an audit log somewhere, maybe a trigger writes to a history table, maybe someone remembers to call a logging function. Usually it's inconsistent, implicit, and spread across multiple places.

This causes real problems:

**You lose state.** When a record gets updated, the previous value vanishes unless you explicitly preserved it. And if you did preserve it, it's probably in some audit table that requires specialized queries to make sense of.

**Reconstruction is painful.** Want to know what an entity looked like six months ago? Good luck. You'll be traversing logs, replaying transactions, or querying versioned tables with increasingly baroque SQL.

**Concurrent changes are messy.** When multiple changes happen around the same time, or arrive out of order from different sources, figuring out the actual sequence of events becomes a guessing game.

**History is coupled to storage.** Your change tracking is probably baked into your database schema or scattered across application code. Extracting it, sharing it, or reasoning about it independently is hard.

This repository provides a different approach. We treat time as first-class, not as metadata bolted on afterward.

- Events describe what changed and when
- Snapshots represent state at a point in time
- Diffs show what's different between two states
- Timelines order events and handle the messy parts

The model is deliberately incomplete. It doesn't interpret changes, score them, or decide what to do about them. It just represents them clearly. That's the whole point.

---

## 2. Core Concepts

Four things. That's it.

### Event

An event is a record of something that changed at a specific time. It says what changed, not why it changed or whether it matters.

Every event has:
- A timestamp (when it happened)
- An entity identifier (what thing changed)
- A type (created, updated, deleted, etc.)
- A payload (the actual change data)
- Optional evidence (references to supporting material)

Events are immutable. Once recorded, they don't change. They don't express opinions.

### Snapshot

A snapshot is the complete state of something at a point in time. You get it by applying all the events up to that point.

Think of it like this: if events are the journal entries, a snapshot is the balance sheet on a given date.

Snapshots can be stored (materialized) or computed on demand (reconstructed). The model doesn't care which—they're semantically identical.

### Diff

A diff shows what changed between two snapshots. Field by field, here's what was there before, here's what's there now.

Diffs don't tell you whether the change is good or bad. They don't suggest actions. They don't rank importance. They just show the delta.

### Timeline

A timeline is an ordered sequence of events for an entity. It handles the annoying parts: out-of-order events, concurrent timestamps, validation.

When you need a snapshot, you ask the timeline for it. The timeline guarantees deterministic ordering so you always get the same result.

---

## 3. Data Model

Everything is JSON. We'll publish JSON Schemas, but here's the shape of things.

### Event

```
{
  "id": "evt-abc123",                    // unique identifier
  "entity_id": "company-456",            // what changed
  "event_type": "updated",               // what kind of change
  "timestamp": "2024-03-15T10:30:00Z",   // when
  "payload": {                           // the change data
    "status": "inactive",
    "employee_count": 0
  },
  "evidence": [                          // optional references
    {
      "type": "document",
      "reference": "filing://sec/10k/2024",
      "timestamp": "2024-03-14T00:00:00Z"
    }
  ],
  "source": "data-pipeline-v2",          // optional: where this came from
  "correlation_id": "batch-789",         // optional: for grouping related events
  "metadata": {}                         // optional: whatever else you need
}
```

Required: `id`, `entity_id`, `event_type`, `timestamp`, `payload`

Everything else is optional but often useful.

### Snapshot

```
{
  "entity_id": "company-456",
  "as_of": "2024-03-15T12:00:00Z",
  "state": {
    "name": "Acme Corp",
    "status": "inactive",
    "founded": "2020-01-15",
    "employee_count": 0
  },
  "last_event_id": "evt-abc123"
}
```

The `as_of` timestamp tells you when this snapshot is valid. Events after that time aren't included. Events at exactly that time are included.

### Diff

```
{
  "before": {
    "as_of": "2024-01-01T00:00:00Z",
    "snapshot_ref": "snap-001"
  },
  "after": {
    "as_of": "2024-03-15T12:00:00Z",
    "snapshot_ref": "snap-002"
  },
  "changes": [
    {
      "field": "status",
      "before": "active",
      "after": "inactive"
    },
    {
      "field": "employee_count",
      "before": 50,
      "after": 0
    }
  ]
}
```

We use field-level diffs because they're the clearest. You could convert to JSON Patch (RFC 6902) if you need that format, but field-level is the canonical representation.

### Timeline

A timeline isn't really a data structure you store—it's more of a logical concept. But if you were to serialize one:

```
{
  "entity_id": "company-456",
  "events": ["evt-001", "evt-002", "evt-003"],  // ordered by timestamp
  "ordering_rules": {
    "timestamp_field": "timestamp",
    "tie_breaker": "lexicographic_id"
  }
}
```

---

## 4. Event Semantics

We define five event types. That's enough. If you think you need more, you probably want to put that information in the payload or metadata instead.

### `created`

The entity now exists. Payload contains the initial state.

Can't apply this if the entity already exists.

### `updated`

The entity changed. Payload contains the fields that changed (not the whole state).

Can't apply this if the entity doesn't exist or has been deleted.

### `deleted`

The entity no longer exists. Payload is optional—you might include a reason, but it's not required.

Can't apply this if the entity doesn't exist. After deletion, the only valid next event is `created` (to recreate the entity).

### `relationship_added`

A relationship was established between entities. Payload identifies the target entity, relationship type, and any properties.

This exists because relationships are often first-class things you want to track independently from entity state.

### `relationship_removed`

A relationship ended. Payload identifies which relationship.

---

### Design notes

**Events describe change, not meaning.** An event that changes status from "active" to "inactive" doesn't encode whether that's good, bad, expected, or surprising. It just records the change.

**Clarity over completeness.** We don't try to cover every possible scenario. The model handles the common cases well. Edge cases can use metadata or custom payloads.

**Events are atomic.** One event, one change. If you have a complex change that should be treated as a unit, use multiple events with a shared `correlation_id`, but each event stands on its own.

---

## 5. Snapshot Derivation & Diffing

### Building a snapshot

To get a snapshot at time T:

1. Get all events for the entity with timestamp ≤ T
2. Sort them by timestamp (with tie-breaking for concurrent events)
3. Start with an empty state
4. Apply each event in order
5. Return the final state

Event application rules:
- `created`: Initialize state from payload
- `updated`: Merge payload into state (field-level updates)
- `deleted`: Mark as deleted
- `relationship_added`: Add to relationships list
- `relationship_removed`: Remove from relationships list

### Materialized vs reconstructed

**Materialized snapshots** are computed and stored. Fast to retrieve, but you need to decide which points in time to store.

**Reconstructed snapshots** are computed on demand from events. Slower, but works for any point in time.

The model treats both the same. From a consumer's perspective, a snapshot is a snapshot regardless of how it was produced.

In practice, you'll probably materialize snapshots at regular intervals or at significant events, and reconstruct for ad-hoc queries.

### Computing diffs

To diff two snapshots:

1. Load both snapshots (or reconstruct them)
2. Walk through all fields
3. For each field, compare before and after values
4. Collect changes into a diff structure

Nested objects get diffed recursively. Arrays are compared by position (we don't try to detect moves or reordering—that's interpretation territory).

### Limitations

This is intentionally simple:

- Diffs show structural changes only, not semantic meaning
- We don't capture intermediate states between snapshots
- Array handling is positional, not content-aware
- Schema changes between snapshots require careful handling

These aren't bugs. The model stays simple by not trying to solve everything.

---

## 6. Reference Implementation

The reference implementation is minimal Python. It exists to make the semantics concrete and testable. It's not a framework you should deploy.

### Core functions

**`apply_event(snapshot, event) -> snapshot`**

Takes a snapshot (or None) and an event, returns the new snapshot. Validates that the event can be applied.

**`compute_diff(before, after) -> diff`**

Takes two snapshots, returns a field-level diff.

**`build_timeline(events) -> timeline`**

Takes events in any order, returns them sorted with deterministic tie-breaking.

**`derive_snapshot(timeline, as_of) -> snapshot`**

Takes a timeline and a timestamp, returns the snapshot at that time.

### Characteristics

- Pure functions, no side effects
- Standard library only (no dependencies)
- Clear error messages
- In-memory only (no persistence)
- Optimized for clarity, not performance

The code is documented inline. Read it like executable spec.

---

## 7. Example: Company Lifecycle

A concrete walkthrough. No commentary, just data.

### Events

**Event 1: Company created**
```json
{
  "id": "evt-001",
  "entity_id": "company-123",
  "event_type": "created",
  "timestamp": "2024-01-01T00:00:00Z",
  "payload": {
    "name": "Acme Corp",
    "status": "active",
    "founded": "2024-01-01"
  }
}
```

**Event 2: Company grows**
```json
{
  "id": "evt-002",
  "entity_id": "company-123",
  "event_type": "updated",
  "timestamp": "2024-03-15T10:30:00Z",
  "payload": {
    "status": "expanding",
    "employee_count": 10
  }
}
```

**Event 3: Hires an employee**
```json
{
  "id": "evt-003",
  "entity_id": "company-123",
  "event_type": "relationship_added",
  "timestamp": "2024-03-20T14:00:00Z",
  "payload": {
    "relationship_type": "employs",
    "target_entity": "person-456",
    "properties": {
      "role": "engineer",
      "start_date": "2024-03-20"
    }
  }
}
```

**Event 4: Stabilizes**
```json
{
  "id": "evt-004",
  "entity_id": "company-123",
  "event_type": "updated",
  "timestamp": "2024-06-01T09:00:00Z",
  "payload": {
    "status": "stable",
    "employee_count": 25
  }
}
```

**Event 5: Dissolved**
```json
{
  "id": "evt-005",
  "entity_id": "company-123",
  "event_type": "deleted",
  "timestamp": "2024-12-31T23:59:59Z",
  "payload": {}
}
```

### Snapshots

**As of 2024-02-01 (after creation)**
```json
{
  "entity_id": "company-123",
  "as_of": "2024-02-01T00:00:00Z",
  "state": {
    "name": "Acme Corp",
    "status": "active",
    "founded": "2024-01-01"
  },
  "last_event_id": "evt-001"
}
```

**As of 2024-04-01 (after growth and hiring)**
```json
{
  "entity_id": "company-123",
  "as_of": "2024-04-01T00:00:00Z",
  "state": {
    "name": "Acme Corp",
    "status": "expanding",
    "founded": "2024-01-01",
    "employee_count": 10,
    "relationships": [
      {
        "type": "employs",
        "target": "person-456",
        "role": "engineer",
        "start_date": "2024-03-20"
      }
    ]
  },
  "last_event_id": "evt-003"
}
```

**As of 2024-07-01 (after stabilization)**
```json
{
  "entity_id": "company-123",
  "as_of": "2024-07-01T00:00:00Z",
  "state": {
    "name": "Acme Corp",
    "status": "stable",
    "founded": "2024-01-01",
    "employee_count": 25,
    "relationships": [
      {
        "type": "employs",
        "target": "person-456",
        "role": "engineer",
        "start_date": "2024-03-20"
      }
    ]
  },
  "last_event_id": "evt-004"
}
```

### Diffs

**From 2024-02-01 to 2024-04-01**
```json
{
  "before": {"as_of": "2024-02-01T00:00:00Z"},
  "after": {"as_of": "2024-04-01T00:00:00Z"},
  "changes": [
    {"field": "status", "before": "active", "after": "expanding"},
    {"field": "employee_count", "before": null, "after": 10},
    {"field": "relationships", "before": null, "after": [{"type": "employs", "target": "person-456", "role": "engineer", "start_date": "2024-03-20"}]}
  ]
}
```

**From 2024-04-01 to 2024-07-01**
```json
{
  "before": {"as_of": "2024-04-01T00:00:00Z"},
  "after": {"as_of": "2024-07-01T00:00:00Z"},
  "changes": [
    {"field": "status", "before": "expanding", "after": "stable"},
    {"field": "employee_count", "before": 10, "after": 25}
  ]
}
```

---

## 8. Repository Structure

```
temporal-event-model/
├── README.md                 # What this is and isn't
├── LICENSE                   # Apache 2.0
├── docs/
│   ├── architecture.md       # This document
│   └── concepts.md           # Detailed definitions
├── spec/
│   └── v0.1/
│       ├── event.schema.json
│       ├── snapshot.schema.json
│       ├── diff.schema.json
│       └── timeline.schema.json
├── reference/
│   └── python/
│       ├── temporal.py       # Core implementation
│       └── examples/
│           └── company.py    # Runnable example
└── examples/
    └── company-lifecycle/
        ├── events.json
        ├── snapshots.json
        └── diffs.json
```

**Why this structure:**

- `docs/` — Architecture and concepts, separate from README so the README stays focused
- `spec/v0.1/` — Versioned schemas. The version is in the path so we can evolve without breaking things
- `reference/python/` — Minimal implementation for clarity. Python because it's readable
- `examples/` — Data files you can actually use

---

## 9. Non-Goals

This project does not do these things. On purpose.

**Importance or relevance** — All events are recorded equally. We don't distinguish "big" changes from "small" ones.

**Anomaly detection** — We don't identify unusual patterns or outliers. We just record what happened.

**Ranking or scoring** — Events don't have importance scores, risk ratings, or priorities.

**Alerts or triggers** — We don't send notifications or kick off workflows when things change.

**Intent or causality** — Events say what changed, not why. We don't model motivations or cause-and-effect.

**Workflow management** — This isn't a case management system or task tracker.

**Compliance or audit replacement** — We don't provide retention policies, tamper-proofing, or compliance-specific features. You could build those on top, but we don't provide them.

**Why these exclusions?**

The model stays useful by staying simple. If we added interpretation or action-triggering, we'd have to make assumptions about your domain, your priorities, your workflows. Instead, we give you a clean primitive that you can compose with whatever interpretation and action layers make sense for your context.

The model is incomplete by design. That's what makes it reusable.

---

## 10. Relationship to Other Systems

This model is meant to be embedded, consumed, or built upon. It doesn't orchestrate anything.

**Event consumers** can subscribe to events and do whatever they want with them. We don't define how subscription works or guarantee delivery. We just define what an event looks like.

**Snapshot queries** can ask for state at any point in time. We don't define query languages or APIs. We just define what a snapshot looks like.

**Visualization layers** can render timelines, animate state changes, show diffs. We don't provide UI components. We just provide the data structures.

**Decision systems** can reference temporal state when making decisions. We don't encode business logic. We just provide the history.

**Analytics pipelines** can process events for whatever analysis makes sense. We don't do the analysis. We just provide clean input data.

The pattern is always the same: we handle representation, you handle interpretation and action. The boundary is clear and intentional.

---

## 11. Versioning

Schemas use semantic versioning: `MAJOR.MINOR.PATCH`

- **Major**: Breaking changes. Migration required.
- **Minor**: New optional fields or event types. Backward compatible.
- **Patch**: Documentation, clarifications, typos.

**What's a breaking change?**
- Removing a required field
- Changing a field's type
- Removing an event type
- Changing how event application works
- Anything that would invalidate existing data

**Stability policy:**

We're conservative. If we're not sure whether something is breaking, we treat it as breaking. New features are added only when they're clearly necessary and well-understood.

The model favors stability over features. We'd rather be boring and reliable than exciting and unpredictable.

---

## 12. README Positioning

The README should make the following things clear within the first 30 seconds of reading:

**What this is:**
A temporal modeling primitive. Events, snapshots, diffs, timelines. Time as first-class.

**What this isn't:**
Not a product. Not a workflow engine. Not an analysis tool. Not a complete system.

**Who it's for:**
Engineers who need explicit change tracking. People building systems where temporal state matters.

**When to use it:**
When you want to separate "what changed" from "what does it mean." When you need a composable primitive, not a framework.

**When not to use it:**
When you need alerting, scoring, anomaly detection, or workflows. When you need a turnkey solution.

**Tone:**
Calm. Direct. No hype. Written by someone who expects the reader to be skeptical and technically competent.

---

*This document is v0.1. It will evolve, but the core commitments—simplicity, neutrality, incompleteness—are permanent.*

