import json
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


def append_event(path, event):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": _now(), **event}
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def load_history(path):
    target = Path(path)
    if not target.is_file():
        return []
    events = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def summarize_history(events):
    actions = {}
    actors = {}
    for event in events:
        action = event.get("action", "unknown")
        actor = event.get("actor", "unknown")
        actions[action] = actions.get(action, 0) + 1
        actors[actor] = actors.get(actor, 0) + 1
    return {
        "events": len(events),
        "actions": dict(sorted(actions.items())),
        "actors": dict(sorted(actors.items())),
        "status": "stub",
    }
