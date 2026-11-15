from .manifest import as_list, load_data, resolve_path


class HILAdapter:
    name = "base"
    available = False
    description = "Base hardware-in-the-loop adapter stub"

    def describe(self):
        return {
            "name": self.name,
            "available": self.available,
            "description": self.description,
            "status": "stub",
        }

    def run(self, plan):
        return {
            "adapter": self.name,
            "status": "stub",
            "available": self.available,
            "plan": plan,
            "results": [],
        }


class MockHILAdapter(HILAdapter):
    name = "mock"
    available = True
    description = "Deterministic adapter for testing HIL plans without hardware"

    def run(self, plan):
        results = []
        for test in as_list(plan.get("tests")):
            if not isinstance(test, dict):
                continue
            results.append(
                {
                    "id": test.get("id"),
                    "name": test.get("name"),
                    "status": test.get("status", "passed"),
                    "duration_ms": test.get("duration_ms", 0),
                }
            )
        return {
            "adapter": self.name,
            "status": "completed",
            "available": True,
            "plan": plan.get("id"),
            "results": results,
        }


class SerialHILAdapter(HILAdapter):
    name = "serial"
    available = False
    description = "Serial hardware adapter placeholder; requires a future device bridge"


ADAPTERS = {
    adapter.name: adapter
    for adapter in (MockHILAdapter(), SerialHILAdapter())
}


def list_adapters():
    return [adapter.describe() for adapter in ADAPTERS.values()]


def get_adapter(name):
    adapter = ADAPTERS.get(str(name).lower())
    if adapter is None:
        raise ValueError(f"Unknown HIL adapter: {name}")
    return adapter


def run_plan(name, plan_path):
    plan = load_data(plan_path)
    if not isinstance(plan, dict):
        raise TypeError("HIL plan must be an object.")
    return get_adapter(name).run(plan)


def audit_hil(manifest, add, base_dir):
    results = []
    for index, spec in enumerate(as_list(manifest.get("hil"))):
        if not isinstance(spec, dict):
            add("HIL_INVALID", "high", f"hil[{index}]", "HIL entry must be an object.")
            continue
        where = spec.get("id") or f"hil[{index}]"
        adapter_name = spec.get("adapter")
        adapter = ADAPTERS.get(str(adapter_name).lower()) if adapter_name else None
        if not adapter:
            add("HIL_ADAPTER_UNKNOWN", "high", where, f"Unknown HIL adapter: {adapter_name}")
            continue
        plan_value = spec.get("plan")
        if not plan_value:
            add("HIL_PLAN_MISSING", "high", where, "HIL entry has no plan path.")
            continue
        plan_path = resolve_path(base_dir, plan_value)
        if not plan_path.is_file():
            add("HIL_PLAN_MISSING", "high", where, f"HIL plan is missing: {plan_value}")
            continue
        if spec.get("required") and not adapter.available:
            add("HIL_ADAPTER_UNAVAILABLE", "high", where, f"HIL adapter {adapter.name} is not available in this stub.")
        results.append({"id": where, "adapter": adapter.name, "plan": plan_value, "available": adapter.available})
    return results
