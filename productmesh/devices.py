from .manifest import as_list


def _board_matches(target, board):
    if not target or not board:
        return True
    target_tokens = set(str(target).lower().replace("_", "-").split("-"))
    board_tokens = set(str(board).lower().replace("_", "-").split("-"))
    if target_tokens & board_tokens:
        return True
    target_text = str(target).lower()
    board_text = str(board).lower()
    return target_text in board_text or board_text in target_text


def _resource_issues(device, add):
    constraints = device.get("constraints") or {}
    specs = device.get("specs") or {}
    mapping = (
        ("min_flash_mb", "flash_mb", "flash"),
        ("min_ram_kb", "ram_kb", "RAM"),
        ("min_clock_mhz", "clock_mhz", "clock"),
    )
    for constraint_key, spec_key, label in mapping:
        required = constraints.get(constraint_key)
        if required is None:
            continue
        actual = specs.get(spec_key)
        if actual is None:
            add("DEVICE_SPEC_MISSING", "medium", device.get("id"), f"Device does not declare {spec_key} for {constraint_key}.")
        elif actual < required:
            add(
                "DEVICE_RESOURCE_SHORTFALL",
                "high",
                device.get("id"),
                f"Device {label} {actual} is below required {required}.",
                required=required,
                actual=actual,
            )


def audit_devices(manifest, maps, add):
    devices = as_list(manifest.get("devices"))
    seen = set()
    for index, device in enumerate(devices):
        where = device.get("id") or f"device[{index}]" if isinstance(device, dict) else f"device[{index}]"
        if not isinstance(device, dict):
            add("DEVICE_INVALID", "high", where, "Device entry must be an object.")
            continue
        if not device.get("id"):
            add("DEVICE_ID_MISSING", "high", where, "Device has no id.")
        if device.get("id") in seen:
            add("DEVICE_DUPLICATE_ID", "high", where, f"Device id is duplicated: {device.get('id')}.")
        seen.add(device.get("id"))
        firmware = device.get("firmware")
        if not firmware:
            add("DEVICE_FIRMWARE_MISSING", "high", where, "Device does not declare firmware.")
        elif firmware not in maps["components"]:
            add("DEVICE_FIRMWARE_MISSING", "high", where, f"Firmware component {firmware} does not exist.")
        else:
            component = maps["components"][firmware]
            if not _board_matches(component.get("target"), device.get("board")):
                add(
                    "DEVICE_BOARD_MISMATCH",
                    "medium",
                    where,
                    f"Device board {device.get('board')} does not match firmware target {component.get('target')}.",
                    board=device.get("board"),
                    target=component.get("target"),
                )
        environment_id = device.get("environment")
        environment = maps["environments"].get(environment_id) if environment_id else None
        if environment_id and not environment:
            add("DEVICE_ENVIRONMENT_MISSING", "high", where, f"Environment {environment_id} does not exist.")
        voltage = device.get("logic_voltage")
        if not voltage:
            add("DEVICE_VOLTAGE_MISSING", "high", where, "Device does not declare logic_voltage.")
        elif environment and environment.get("logic_voltage") and environment["logic_voltage"] != voltage:
            add(
                "DEVICE_ENV_VOLTAGE_MISMATCH",
                "critical",
                where,
                f"Device requires {voltage} but environment {environment_id} declares {environment['logic_voltage']}.",
                expected=voltage,
                actual=environment["logic_voltage"],
            )
        declared_interfaces = device.get("interfaces")
        if declared_interfaces is None and firmware in maps["components"]:
            declared_interfaces = maps["components"][firmware].get("interfaces", [])
        for interface_id in declared_interfaces or []:
            interface = maps["interfaces"].get(interface_id)
            if not interface:
                add("DEVICE_INTERFACE_MISSING", "high", where, f"Interface {interface_id} does not exist.")
                continue
            if voltage and interface.get("voltage") and interface["voltage"] != voltage:
                add(
                    "DEVICE_VOLTAGE_MISMATCH",
                    "critical",
                    where,
                    f"Interface {interface_id} requires {interface['voltage']} but device declares {voltage}.",
                    expected=interface["voltage"],
                    actual=voltage,
                )
            if firmware in maps["components"]:
                supported = maps["components"][firmware].get("interfaces", [])
                if interface_id not in supported:
                    add(
                        "DEVICE_INTERFACE_UNSUPPORTED",
                        "high",
                        where,
                        f"Firmware {firmware} does not declare interface {interface_id}.",
                    )
        _resource_issues(device, add)
    return devices


def device_matrix(manifest):
    rows = []
    components = {item.get("id"): item for item in as_list(manifest.get("components")) if isinstance(item, dict)}
    for device in as_list(manifest.get("devices")):
        if not isinstance(device, dict):
            continue
        firmware = components.get(device.get("firmware"), {})
        rows.append(
            {
                "id": device.get("id"),
                "name": device.get("name", device.get("id")),
                "board": device.get("board"),
                "firmware": device.get("firmware"),
                "firmware_target": firmware.get("target"),
                "environment": device.get("environment"),
                "logic_voltage": device.get("logic_voltage"),
                "interfaces": device.get("interfaces") or firmware.get("interfaces", []),
            }
        )
    return rows
