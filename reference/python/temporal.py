"""
Temporal Event Model - Reference Implementation

This is a minimal implementation to clarify semantics. It's not production code.
No dependencies beyond the standard library. Optimized for clarity, not performance.
"""

from datetime import datetime
from typing import Any, Optional
from copy import deepcopy


# -----------------------------------------------------------------------------
# Event Application
# -----------------------------------------------------------------------------

def apply_event(snapshot: Optional[dict], event: dict) -> dict:
    """
    Apply an event to a snapshot, returning the new snapshot.
    
    Args:
        snapshot: Current snapshot (None if entity doesn't exist yet)
        event: The event to apply
    
    Returns:
        New snapshot with event applied
    
    Raises:
        ValueError: If event cannot be applied to current state
    """
    event_type = event["event_type"]
    entity_id = event["entity_id"]
    payload = event.get("payload", {})
    
    if event_type == "created":
        if snapshot is not None and not snapshot.get("deleted", False):
            raise ValueError(f"Cannot create {entity_id}: already exists")
        return {
            "entity_id": entity_id,
            "as_of": event["timestamp"],
            "state": deepcopy(payload),
            "last_event_id": event["id"],
            "deleted": False
        }
    
    if event_type == "updated":
        if snapshot is None:
            raise ValueError(f"Cannot update {entity_id}: does not exist")
        if snapshot.get("deleted", False):
            raise ValueError(f"Cannot update {entity_id}: has been deleted")
        
        new_state = deepcopy(snapshot["state"])
        for key, value in payload.items():
            new_state[key] = value
        
        return {
            "entity_id": entity_id,
            "as_of": event["timestamp"],
            "state": new_state,
            "last_event_id": event["id"],
            "deleted": False
        }
    
    if event_type == "deleted":
        if snapshot is None:
            raise ValueError(f"Cannot delete {entity_id}: does not exist")
        if snapshot.get("deleted", False):
            raise ValueError(f"Cannot delete {entity_id}: already deleted")
        
        return {
            "entity_id": entity_id,
            "as_of": event["timestamp"],
            "state": {"_deleted_state": deepcopy(snapshot["state"])},
            "last_event_id": event["id"],
            "deleted": True
        }
    
    if event_type == "relationship_added":
        if snapshot is None:
            raise ValueError(f"Cannot add relationship to {entity_id}: does not exist")
        if snapshot.get("deleted", False):
            raise ValueError(f"Cannot add relationship to {entity_id}: has been deleted")
        
        new_state = deepcopy(snapshot["state"])
        if "relationships" not in new_state:
            new_state["relationships"] = []
        
        new_state["relationships"].append({
            "type": payload.get("relationship_type"),
            "target": payload.get("target_entity"),
            **payload.get("properties", {})
        })
        
        return {
            "entity_id": entity_id,
            "as_of": event["timestamp"],
            "state": new_state,
            "last_event_id": event["id"],
            "deleted": False
        }
    
    if event_type == "relationship_removed":
        if snapshot is None:
            raise ValueError(f"Cannot remove relationship from {entity_id}: does not exist")
        if snapshot.get("deleted", False):
            raise ValueError(f"Cannot remove relationship from {entity_id}: has been deleted")
        
        new_state = deepcopy(snapshot["state"])
        relationships = new_state.get("relationships", [])
        
        # Find and remove the relationship
        target = payload.get("target_entity")
        rel_type = payload.get("relationship_type")
        
        new_relationships = [
            r for r in relationships
            if not (r.get("target") == target and r.get("type") == rel_type)
        ]
        
        if len(new_relationships) == len(relationships):
            raise ValueError(f"Relationship not found: {rel_type} -> {target}")
        
        new_state["relationships"] = new_relationships
        
        return {
            "entity_id": entity_id,
            "as_of": event["timestamp"],
            "state": new_state,
            "last_event_id": event["id"],
            "deleted": False
        }
    
    raise ValueError(f"Unknown event type: {event_type}")


# -----------------------------------------------------------------------------
# Diff Computation
# -----------------------------------------------------------------------------

def compute_diff(before: Optional[dict], after: Optional[dict]) -> dict:
    """
    Compute the differences between two snapshots.
    
    Args:
        before: The earlier snapshot (or None)
        after: The later snapshot (or None)
    
    Returns:
        Diff structure with field-level changes
    """
    changes = []
    
    before_state = before["state"] if before else {}
    after_state = after["state"] if after else {}
    
    # Deleted flag
    before_deleted = before.get("deleted", False) if before else False
    after_deleted = after.get("deleted", False) if after else False
    
    if before_deleted != after_deleted:
        changes.append({
            "field": "deleted",
            "before": before_deleted,
            "after": after_deleted
        })
    
    # Collect all keys
    all_keys = set(before_state.keys()) | set(after_state.keys())
    
    for key in sorted(all_keys):
        before_val = before_state.get(key)
        after_val = after_state.get(key)
        
        if before_val != after_val:
            changes.append({
                "field": key,
                "before": before_val,
                "after": after_val
            })
    
    return {
        "before": {
            "as_of": before["as_of"] if before else None,
        },
        "after": {
            "as_of": after["as_of"] if after else None,
        },
        "changes": changes
    }


# -----------------------------------------------------------------------------
# Timeline Operations
# -----------------------------------------------------------------------------

def build_timeline(events: list[dict]) -> list[dict]:
    """
    Build an ordered timeline from a list of events.
    
    Events are sorted by timestamp, with lexicographic event ID as tie-breaker.
    
    Args:
        events: List of events (in any order)
    
    Returns:
        Events sorted in chronological order
    """
    def sort_key(event):
        return (event["timestamp"], event["id"])
    
    return sorted(events, key=sort_key)


def derive_snapshot(events: list[dict], as_of: str) -> Optional[dict]:
    """
    Derive a snapshot by applying events up to a given timestamp.
    
    Args:
        events: List of events (will be sorted internally)
        as_of: ISO 8601 timestamp
    
    Returns:
        Snapshot at the given time, or None if no events apply
    """
    timeline = build_timeline(events)
    
    snapshot = None
    for event in timeline:
        if event["timestamp"] > as_of:
            break
        snapshot = apply_event(snapshot, event)
    
    if snapshot:
        snapshot["as_of"] = as_of
    
    return snapshot


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

def validate_event(event: dict) -> list[str]:
    """
    Validate an event structure.
    
    Args:
        event: Event to validate
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    required = ["id", "entity_id", "event_type", "timestamp", "payload"]
    for field in required:
        if field not in event:
            errors.append(f"Missing required field: {field}")
    
    valid_types = ["created", "updated", "deleted", "relationship_added", "relationship_removed"]
    if event.get("event_type") not in valid_types:
        errors.append(f"Invalid event_type: {event.get('event_type')}")
    
    # Try to parse timestamp
    ts = event.get("timestamp", "")
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"Invalid timestamp format: {ts}")
    
    return errors


def validate_timeline(events: list[dict]) -> list[str]:
    """
    Validate that a sequence of events forms a valid timeline.
    
    Args:
        events: Events to validate (will be sorted internally)
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    timeline = build_timeline(events)
    
    snapshot = None
    for event in timeline:
        try:
            snapshot = apply_event(snapshot, event)
        except ValueError as e:
            errors.append(f"Event {event['id']}: {str(e)}")
    
    return errors

