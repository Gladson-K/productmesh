import json
import subprocess
from pathlib import Path

from productmesh.audit import audit
from productmesh.manifest import Manifest, load_manifest

ROOT = Path(__file__).resolve().parents[1]


def iot_data():
    data = json.loads((ROOT / "examples/iot-edge-monitor/product.json").read_text(encoding="utf-8"))
    for key in ("firmware", "lab", "hil", "benchmarks", "observability"):
        data.pop(key, None)
    return data


def iot_manifest():
    return load_manifest(ROOT / "examples/iot-edge-monitor/product.json")


def edge_manifest():
    return load_manifest(ROOT / "examples/edge-ai-deployment/product.json")


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target


def write_manifest(path, data):
    return write_json(path, data)


def audit_data(data, base_dir):
    return audit(Manifest(data, base_dir=base_dir))


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def init_git_repo(path):
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "ProductMesh Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-qm", "initial")
    return repo


def code_list(result):
    return [issue["code"] for issue in result["issues"]]


def find_issue(result, code):
    for issue in result["issues"]:
        if issue["code"] == code:
            return issue
    return None
