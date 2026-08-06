"""Multi-waypoint mission helpers: normalize and stitch A* segments."""

from __future__ import annotations

from typing import Any


def normalize_waypoints(raw: Any) -> list[dict[str, Any]]:
    """Parse waypoints from API / console input.

    Visit order = input order: first point is highest priority, then 2, 3, …
    """
    if not isinstance(raw, list) or not raw:
        raise ValueError("waypoints_required")
    out: list[dict[str, Any]] = []
    n = len(raw)
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"waypoint_{i}_not_object")
        try:
            x = float(item["x"])
            y = float(item["y"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"waypoint_{i}_bad_xy") from exc
        # Display priority: first point highest; ordering is always by list index.
        priority = n - i
        wp: dict[str, Any] = {
            "x": x,
            "y": y,
            "priority": priority,
            "order": i,
            "seq": i,
            "id": str(item.get("id") or f"wp{i + 1}"),
            "label": str(item.get("label") or item.get("id") or f"{i + 1}"),
        }
        out.append(wp)
    return out


def mission_public(waypoints: list[dict[str, Any]], index: int, status: str) -> dict[str, Any]:
    remaining = [dict(w) for w in waypoints[index:]]
    done = [dict(w) for w in waypoints[:index]]
    current = dict(waypoints[index]) if 0 <= index < len(waypoints) else None
    return {
        "ok": True,
        "status": status,
        "index": index,
        "total": len(waypoints),
        "current": current,
        "done": done,
        "remaining": remaining,
        "waypoints": [dict(w) for w in waypoints],
    }
