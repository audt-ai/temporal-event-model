"""
Example: Company Lifecycle

Demonstrates the temporal model using a simple company that gets created,
grows, hires someone, stabilizes, and eventually dissolves.
"""

import json
from datetime import datetime

# Add parent directory to path so we can import temporal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from temporal import (
    apply_event,
    build_timeline,
    derive_snapshot,
    compute_diff,
    validate_timeline
)


# The events that make up our company's history
EVENTS = [
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
    },
    {
        "id": "evt-002",
        "entity_id": "company-123",
        "event_type": "updated",
        "timestamp": "2024-03-15T10:30:00Z",
        "payload": {
            "status": "expanding",
            "employee_count": 10
        }
    },
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
    },
    {
        "id": "evt-004",
        "entity_id": "company-123",
        "event_type": "updated",
        "timestamp": "2024-06-01T09:00:00Z",
        "payload": {
            "status": "stable",
            "employee_count": 25
        }
    },
    {
        "id": "evt-005",
        "entity_id": "company-123",
        "event_type": "deleted",
        "timestamp": "2024-12-31T23:59:59Z",
        "payload": {}
    }
]


def main():
    print("=" * 60)
    print("Temporal Event Model - Company Lifecycle Example")
    print("=" * 60)
    
    # Validate the timeline
    print("\n1. Validating event timeline...")
    errors = validate_timeline(EVENTS)
    if errors:
        print("   Validation errors:")
        for e in errors:
            print(f"   - {e}")
        return
    print("   Timeline is valid.")
    
    # Build ordered timeline
    print("\n2. Building timeline...")
    timeline = build_timeline(EVENTS)
    print(f"   {len(timeline)} events in chronological order")
    
    # Derive snapshots at different points
    timestamps = [
        "2024-02-01T00:00:00Z",  # After creation
        "2024-04-01T00:00:00Z",  # After growth and hiring
        "2024-07-01T00:00:00Z",  # After stabilization
        "2025-01-01T00:00:00Z",  # After deletion
    ]
    
    print("\n3. Deriving snapshots at different points in time...")
    snapshots = {}
    for ts in timestamps:
        snapshot = derive_snapshot(EVENTS, ts)
        snapshots[ts] = snapshot
        print(f"\n   As of {ts}:")
        print(f"   {json.dumps(snapshot, indent=4, default=str)}")
    
    # Compute diffs between consecutive snapshots
    print("\n4. Computing diffs between snapshots...")
    for i in range(len(timestamps) - 1):
        before_ts = timestamps[i]
        after_ts = timestamps[i + 1]
        
        diff = compute_diff(snapshots[before_ts], snapshots[after_ts])
        
        print(f"\n   Diff from {before_ts} to {after_ts}:")
        if diff["changes"]:
            for change in diff["changes"]:
                print(f"   - {change['field']}: {change['before']} -> {change['after']}")
        else:
            print("   No changes")
    
    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    main()

