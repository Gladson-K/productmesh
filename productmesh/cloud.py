from datetime import datetime, timezone
from pathlib import Path

from .manifest import load_data

ROLES = {
    "viewer": ["read"],
    "auditor": ["read", "audit"],
    "approver": ["read", "audit", "approve"],
    "admin": ["read", "audit", "approve", "manage"],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def new_store(name, owner="owner"):
    return {
        "schema_version": "1.0",
        "workspace": {"id": name.lower().replace(" ", "-"), "name": name},
        "members": {owner: "admin"},
        "approvals": [],
        "history": [],
    }


def load_store(path):
    data = load_data(path)
    if not isinstance(data, dict):
        raise TypeError("Cloud workspace store must be an object.")
    data.setdefault("members", {})
    data.setdefault("approvals", [])
    data.setdefault("history", [])
    return data


def save_store(path, store):
    import json

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return target


def can(role, action):
    return action in ROLES.get(str(role).lower(), [])


def add_member(store, user, role):
    role = str(role).lower()
    if role not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    store["members"][user] = role
    record_event(store, "system", "member.added", user, {"role": role})
    return store


def record_event(store, actor, action, target=None, detail=None):
    event = {"timestamp": _now(), "actor": actor, "action": action, "target": target}
    if detail:
        event["detail"] = detail
    store.setdefault("history", []).append(event)
    return event


def request_approval(store, product, actor, note=None):
    approval = {"product": product, "requested_by": actor, "requested_at": _now(), "status": "pending"}
    if note:
        approval["note"] = note
    store.setdefault("approvals", []).append(approval)
    record_event(store, actor, "approval.requested", product)
    return approval


def approve(store, product, actor, role=None, note=None):
    role = role or store.get("members", {}).get(actor)
    if not can(role, "approve"):
        raise PermissionError(f"{actor} cannot approve with role {role}")
    approval = None
    for item in store.get("approvals", []):
        if item.get("product") == product and item.get("status") == "pending":
            approval = item
            break
    if approval is None:
        approval = request_approval(store, product, actor, note)
    approval["status"] = "approved"
    approval["approved_by"] = actor
    approval["approved_at"] = _now()
    if note:
        approval["note"] = note
    record_event(store, actor, "approval.approved", product)
    return approval


def status(store):
    approvals = store.get("approvals", [])
    return {
        "workspace": store.get("workspace"),
        "members": len(store.get("members", {})),
        "roles": store.get("members", {}),
        "approvals": {
            "pending": sum(1 for item in approvals if item.get("status") == "pending"),
            "approved": sum(1 for item in approvals if item.get("status") == "approved"),
        },
        "history": len(store.get("history", [])),
        "status": "stub",
    }
