from .manifest import as_list


def _pin_conflicts(maps, add):
    owners = {}
    for interface in maps["interfaces"].values():
        pins = interface.get("pins") or {}
        if not isinstance(pins, dict):
            continue
        shared = set(as_list(interface.get("shared_pins")))
        for label, pin in pins.items():
            if pin in shared:
                continue
            owners.setdefault(str(pin), []).append((interface.get("id"), label))
    for pin, entries in sorted(owners.items()):
        interface_ids = {entry[0] for entry in entries}
        if len(interface_ids) > 1:
            add(
                "PIN_CONFLICT",
                "high",
                pin,
                f"Pin {pin} is assigned to multiple interfaces: {sorted(interface_ids)}.",
                pin=pin,
                interfaces=sorted(interface_ids),
            )
    return owners


def _bus_conflicts(maps, add):
    owners = {}
    for interface in maps["interfaces"].values():
        bus = interface.get("bus")
        address = interface.get("address") or interface.get("bus_address")
        if not bus or address is None:
            continue
        key = (str(bus), str(address).lower())
        owners.setdefault(key, []).append(interface.get("id"))
    for (bus, address), interface_ids in sorted(owners.items()):
        if len(set(interface_ids)) > 1:
            add(
                "BUS_ADDRESS_CONFLICT",
                "high",
                f"{bus}:{address}",
                f"Bus {bus} address {address} is used by multiple interfaces: {sorted(set(interface_ids))}.",
                bus=bus,
                address=address,
                interfaces=sorted(set(interface_ids)),
            )
    return owners


def _interface_current(maps, device):
    current = 0
    for interface_id in device.get("interfaces") or []:
        interface = maps["interfaces"].get(interface_id)
        if interface and isinstance(interface.get("current_ma"), (int, float)):
            current += interface["current_ma"]
    return current


def _power_budgets(manifest, maps, add):
    checked = 0
    for index, device in enumerate(as_list(manifest.get("devices"))):
        if not isinstance(device, dict):
            continue
        constraints = device.get("constraints") or {}
        specs = device.get("specs") or {}
        budget = constraints.get("max_current_ma", device.get("power_budget_ma"))
        if budget is None:
            continue
        checked += 1
        draw = specs.get("current_ma", device.get("power_draw_ma"))
        if draw is None:
            draw = _interface_current(maps, device)
        where = device.get("id") or f"device[{index}]"
        if not draw:
            add("POWER_BUDGET_MISSING", "medium", where, "Device declares a current budget but no current draw.")
        elif draw > budget:
            add(
                "POWER_BUDGET_EXCEEDED",
                "high",
                where,
                f"Device current draw {draw} mA exceeds budget {budget} mA.",
                budget=budget,
                draw=draw,
            )
    return checked


def audit_electrical(manifest, maps, add):
    pins = _pin_conflicts(maps, add)
    buses = _bus_conflicts(maps, add)
    budgets = _power_budgets(manifest, maps, add)
    return {"pins": len(pins), "buses": len(buses), "power_budgets": budgets}
