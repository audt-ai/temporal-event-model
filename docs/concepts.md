# Core Concepts

Detailed definitions for the four core concepts in the temporal event model.

---

## Event

An event is a record that something changed at a specific point in time.

### What an event contains

**Required:**
- `id` — Unique identifier. UUIDs work well.
- `entity_id` — What thing changed. Could be a company, a person, a document, whatever.
- `event_type` — What kind of change: `created`, `updated`, `deleted`, `relationship_added`, `relationship_removed`
- `timestamp` — When it happened. ISO 8601, always with timezone (use UTC if in doubt).
- `payload` — The change data. Structure depends on event type.

**Optional:**
- `evidence` — References to supporting material (documents, API responses, etc.)
- `source` — Where this event came from (pipeline name, system identifier)
- `correlation_id` — For grouping related events that should be considered together
- `metadata` — Catch-all for anything else

### What an event doesn't contain

Events don't express:
- Whether the change is good or bad
- How important the change is
- What should be done about it
- Why the change happened
- Who is responsible

These are interpretations. The model doesn't do interpretations.

### Event types

**`created`** — The entity now exists. Payload is the initial state.

**`updated`** — The entity changed. Payload contains the changed fields (partial update, not full replacement).

**`deleted`** — The entity no longer exists. Payload is optional.

**`relationship_added`** — A relationship was established. Payload identifies the other entity, relationship type, and any properties.

**`relationship_removed`** — A relationship ended. Payload identifies which relationship.

That's the complete list. If you think you need another type, consider whether it's really a variant of `updated` with different payload structure.

### Immutability

Events are immutable. Once recorded, they don't change. If you got something wrong, you record a new event that corrects it—you don't edit the old one.

This isn't a technical limitation, it's a design choice. Immutable events make the model trustworthy and reproducible.

---

## Snapshot

A snapshot is the complete state of an entity at a specific point in time.

### How snapshots work

You don't typically store snapshots directly (though you can). You derive them from events:

1. Take all events for an entity up to time T
2. Sort them by timestamp
3. Apply them in order, starting from empty state
4. The result is the snapshot at time T

### The "as of" timestamp

Every snapshot has an `as_of` timestamp that tells you when this snapshot is valid.

- Events with timestamps before or equal to `as_of` are included
- Events with timestamps after `as_of` are not included

This means you can ask "what did this entity look like on March 15th?" and get a deterministic answer.

### Materialized vs reconstructed

**Materialized snapshots** are computed once and stored. Fast to retrieve, but you have to decide in advance which points in time to materialize.

**Reconstructed snapshots** are computed on demand from events. Slower, but works for any point in time without advance planning.

The model treats both identically. From a consumer's perspective, a snapshot is a snapshot.

In practice, you'll probably materialize snapshots at important points (end of day, after significant events) and reconstruct for ad-hoc queries.

### What's in a snapshot

- `entity_id` — Which entity this is
- `as_of` — When this snapshot is valid
- `state` — The complete state (structure depends on entity type)
- `last_event_id` — The most recent event that contributed to this state

The `last_event_id` is useful for debugging and for knowing whether a snapshot is stale.

---

## Diff

A diff shows what changed between two snapshots.

### Structure

A diff has:
- References to the "before" and "after" snapshots
- A list of changes

Each change identifies:
- The field that changed
- The value before
- The value after

### What diffs capture

Diffs capture structural changes at the field level. For each field in the entity:
- If it existed before but not after: removed
- If it exists after but not before: added
- If it exists in both but with different values: changed

Nested objects are diffed recursively. Arrays are compared by position.

### What diffs don't capture

Diffs don't capture:
- Why the change happened
- Whether the change is significant
- What the change means in business terms
- Intent or causality

A status changing from "active" to "inactive" is just a field change in the diff. The diff doesn't know or care that this might be significant.

### Diff formats

The canonical format is field-level (explicit before/after for each changed field). This is the clearest.

You can convert to JSON Patch (RFC 6902) if you need that format for tooling compatibility, but field-level is what we specify.

---

## Timeline

A timeline is an ordered sequence of events for an entity.

### Ordering

Events are ordered by timestamp. Simple enough, except for two complications:

**Concurrent events** — Two events with the exact same timestamp. We use lexicographic ordering of event IDs as a tie-breaker. This is arbitrary but deterministic, which is what matters.

**Out-of-order arrival** — Events might not arrive in chronological order. The timeline handles this by inserting events into the correct position based on timestamp, not arrival time.

### Validation

Timelines validate that events form a valid sequence:
- Can't update an entity that doesn't exist
- Can't delete an entity that doesn't exist
- Can't create an entity that already exists (unless it was deleted)

Invalid event sequences are rejected, not silently ignored.

### What timelines provide

- Deterministic ordering of events
- Consistent tie-breaking for concurrent events
- Validation of event sequences
- A clean interface for deriving snapshots

### What timelines don't provide

- Storage (that's your problem)
- Query capabilities (also your problem)
- Subscription or notification (still your problem)

The timeline is a logical concept for ordering and validation. How you persist and query it is up to you.

---

## Relationships between concepts

```
Events → (apply in order) → Snapshot
Snapshot + Snapshot → (compare) → Diff
Events → (order and validate) → Timeline
Timeline + timestamp → (derive) → Snapshot
```

Events are the source of truth. Everything else is derived.

If you have the events, you can reconstruct any snapshot. If you have two snapshots, you can compute the diff. The timeline is just events with ordering guarantees.

This is intentional. Events are immutable and append-only, which makes them easy to store, replicate, and reason about. Snapshots and diffs are derived views that can be recomputed whenever needed.

