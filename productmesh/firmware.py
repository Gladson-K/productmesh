import glob
import os
import re
from pathlib import Path

from .manifest import as_list, resolve_path, sha256_file

VERSION_PATTERN = re.compile(rb"(?:v|version[ =:]*)?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
MAGIC = (
    (b"\x7fELF", "elf"),
    (b"\x1f\x8b", "gzip"),
    (b"PK\x03\x04", "zip"),
    (b"\xe9", "esp-image"),
    (b"UF2\n", "uf2"),
)

SERIAL_PATTERNS = (
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
    "/dev/cu.*",
    "/dev/serial/by-id/*",
)


def _format(data):
    for magic, name in MAGIC:
        if data.startswith(magic):
            return name
    return "binary"


def fingerprint(path):
    target = Path(path)
    data = target.read_bytes()
    versions = sorted({match.decode("ascii", "ignore") for match in VERSION_PATTERN.findall(data[: 1024 * 1024])})
    return {
        "path": str(target),
        "size": len(data),
        "sha256": sha256_file(target),
        "format": _format(data),
        "versions": versions,
    }


def discover_devices(roots=None):
    paths = []
    for pattern in roots or SERIAL_PATTERNS:
        paths.extend(path for path in sorted(glob.glob(pattern)) if Path(path).exists())
    devices = []
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        devices.append(
            {
                "path": path,
                "name": Path(path).name,
                "kind": "serial",
                "available": os.access(path, os.R_OK),
                "status": "stub",
            }
        )
    return devices


def audit_firmware(manifest, maps, add, base_dir):
    results = []
    for index, spec in enumerate(as_list(manifest.get("firmware"))):
        if isinstance(spec, str):
            spec = {"path": spec}
        elif not isinstance(spec, dict):
            add("FIRMWARE_INVALID", "high", f"firmware[{index}]", "Firmware entry must be a path or object.")
            continue
        where = spec.get("id") or f"firmware[{index}]"
        component = spec.get("component")
        if component and component not in maps["components"]:
            add("FIRMWARE_COMPONENT_MISSING", "high", where, f"Firmware references unknown component {component}.")
        path_value = spec.get("path")
        if not path_value:
            add("FIRMWARE_MISSING", "high", where, "Firmware entry has no path.")
            continue
        path = resolve_path(base_dir, path_value)
        if not path.is_file():
            add("FIRMWARE_MISSING", "high", where, f"Firmware artifact is missing: {path_value}")
            continue
        try:
            info = fingerprint(path)
        except OSError as exc:
            add("FIRMWARE_INVALID", "high", where, f"Cannot read firmware artifact: {exc}")
            continue
        expected_hash = spec.get("sha256")
        if expected_hash and expected_hash != info["sha256"]:
            add(
                "FIRMWARE_HASH_MISMATCH",
                "high",
                where,
                "Firmware artifact hash does not match the declared hash.",
                expected=expected_hash,
                actual=info["sha256"],
            )
        expected_version = spec.get("version")
        if expected_version and info["versions"] and expected_version not in info["versions"]:
            add(
                "FIRMWARE_VERSION_MISMATCH",
                "high",
                where,
                f"Firmware declares {expected_version} but the artifact contains {info['versions']}.",
                expected=expected_version,
                actual=info["versions"],
            )
        results.append(
            {
                "id": where,
                "path": path_value,
                "component": component,
                "size": info["size"],
                "sha256": info["sha256"],
                "format": info["format"],
                "versions": info["versions"],
            }
        )
    return results
