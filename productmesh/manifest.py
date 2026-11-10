import hashlib
import json
from pathlib import Path

REQUIRED_FIELDS = ("project", "requirements", "components", "interfaces", "environments", "tests")


class Manifest(dict):
    def __init__(self, data=None, base_dir=None, source_path=None):
        super().__init__(data or {})
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
        self.source_path = Path(source_path).resolve() if source_path else None


class Workspace(dict):
    def __init__(self, data=None, base_dir=None, source_path=None):
        super().__init__(data or {})
        self.base_dir = Path(base_dir).resolve() if base_dir else Path.cwd().resolve()
        self.source_path = Path(source_path).resolve() if source_path else None


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_manifest(path):
    source = Path(path).expanduser().resolve()
    data = load_json(source)
    missing = [key for key in REQUIRED_FIELDS if key not in data]
    if missing:
        raise ValueError(f"Missing top-level field: {missing[0]}")
    return Manifest(data, base_dir=source.parent, source_path=source)


def load_workspace(path):
    source = Path(path).expanduser().resolve()
    data = load_json(source)
    if "workspace" not in data:
        raise ValueError("Missing top-level field: workspace")
    return Workspace(data, base_dir=source.parent, source_path=source)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def base_dir_for(data, fallback=None):
    return Path(getattr(data, "base_dir", fallback or Path.cwd())).resolve()


def resolve_path(base_dir, value):
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path(base_dir) / candidate
    return candidate.resolve()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_fingerprint(path):
    target = Path(path)
    if not target.is_file():
        return None
    return {"path": str(target), "size": target.stat().st_size, "sha256": sha256_file(target)}
