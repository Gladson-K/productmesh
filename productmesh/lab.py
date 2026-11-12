from .manifest import as_list, load_data, resolve_path


def load_inventory(path):
    data = load_data(path)
    if not isinstance(data, dict):
        raise TypeError("Lab inventory must be an object.")
    return data


def list_boards(inventory):
    boards = []
    for board in as_list(inventory.get("boards")):
        if not isinstance(board, dict):
            continue
        boards.append(
            {
                "id": board.get("id"),
                "name": board.get("name", board.get("id")),
                "board": board.get("board"),
                "firmware": board.get("firmware"),
                "serial": board.get("serial"),
                "location": board.get("location"),
                "status": board.get("status", "unknown"),
                "capabilities": board.get("capabilities") or [],
            }
        )
    return boards


def find_board(inventory, value):
    target = str(value).lower()
    for board in list_boards(inventory):
        if str(board.get("id")).lower() == target or str(board.get("board")).lower() == target:
            return board
    return None


def fingerprint_board(board):
    return {
        "id": board.get("id"),
        "board": board.get("board"),
        "firmware": board.get("firmware"),
        "serial": board.get("serial"),
        "location": board.get("location"),
        "status": board.get("status"),
        "capabilities": board.get("capabilities") or [],
        "status_detail": "declared inventory stub",
    }


def audit_lab(manifest, add, base_dir):
    value = manifest.get("lab")
    if not value:
        return {"boards": 0, "matched": 0}
    path_value = value.get("path") if isinstance(value, dict) else value
    if not path_value:
        add("LAB_INVENTORY_MISSING", "high", "lab", "Lab entry has no inventory path.")
        return {"boards": 0, "matched": 0}
    path = resolve_path(base_dir, path_value)
    if not path.is_file():
        add("LAB_INVENTORY_MISSING", "high", "lab", f"Lab inventory is missing: {path_value}")
        return {"boards": 0, "matched": 0}
    try:
        inventory = load_inventory(path)
    except Exception as exc:
        add("LAB_INVENTORY_INVALID", "high", "lab", f"Cannot load lab inventory: {exc}")
        return {"boards": 0, "matched": 0}
    boards = list_boards(inventory)
    matched = 0
    for device in as_list(manifest.get("devices")):
        if not isinstance(device, dict) or not device.get("board"):
            continue
        board = find_board(inventory, device["board"])
        if not board:
            add("LAB_BOARD_MISSING", "medium", device.get("id"), f"Board {device['board']} is not in the lab inventory.")
            continue
        matched += 1
        if board.get("status") not in ("available", "ready"):
            add(
                "LAB_BOARD_UNAVAILABLE",
                "high",
                device.get("id"),
                f"Board {board.get('id')} is marked {board.get('status')} in the lab inventory.",
            )
    return {"boards": len(boards), "matched": matched}
