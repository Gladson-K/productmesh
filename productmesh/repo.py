import os
import re
import subprocess
from pathlib import Path

from .issues import make_issue
from .manifest import as_list, resolve_path

REMOTE_PATTERNS = (
    (re.compile(r"^git@([^:]+):(.+?)(?:\.git)?$"), lambda m: f"{m.group(1)}/{m.group(2)}"),
    (re.compile(r"^ssh://[^@]+@([^/]+)/(.+?)(?:\.git)?$"), lambda m: f"{m.group(1)}/{m.group(2)}"),
    (re.compile(r"^https?://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?$"), lambda m: f"{m.group(1)}/{m.group(2)}"),
)


def _run(args, timeout=20, env=None):
    environment = os.environ.copy()
    environment.setdefault("GIT_TERMINAL_PROMPT", "0")
    environment.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes -o ConnectTimeout=10")
    if env:
        environment.update(env)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=environment, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _git(path, *args, timeout=20):
    return _run(["git", "-C", str(path), *args], timeout=timeout)


def normalize_remote(value):
    if not value:
        return ""
    value = str(value).strip().rstrip("/")
    for pattern, transform in REMOTE_PATTERNS:
        match = pattern.match(value)
        if match:
            value = transform(match)
            break
    value = value.lower().rstrip(".git").strip("/")
    return value


def _local_remote(path):
    code, stdout, _ = _git(path, "remote", "get-url", "origin")
    return stdout if code == 0 else ""


def _tags_at_head(path):
    code, stdout, _ = _git(path, "tag", "--points-at", "HEAD")
    return stdout.splitlines() if code == 0 and stdout else []


def _submodule_state(path):
    code, stdout, _ = _git(path, "submodule", "status", "--recursive")
    if code != 0 or not stdout:
        return []
    modules = []
    for line in stdout.splitlines():
        status = line[0] if line else " "
        parts = line[1:].strip().split()
        modules.append(
            {
                "path": parts[1] if len(parts) > 1 else "",
                "commit": parts[0] if parts else "",
                "status": "dirty" if status in ("+", "U") else "clean",
            }
        )
    return modules


def inspect_local(path):
    target = Path(path).resolve()
    if not target.exists():
        return {"kind": "local", "path": str(target), "exists": False, "is_repo": False}
    code, _, _ = _git(target, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return {"kind": "local", "path": str(target), "exists": True, "is_repo": False}
    _, commit, _ = _git(target, "rev-parse", "HEAD")
    _, branch, _ = _git(target, "rev-parse", "--abbrev-ref", "HEAD")
    _, status, _ = _git(target, "status", "--porcelain")
    _, describe, _ = _git(target, "describe", "--tags", "--always", "--dirty")
    _, root, _ = _git(target, "rev-parse", "--show-toplevel")
    dirty_files = [line[3:] for line in status.splitlines() if line.strip()] if status else []
    return {
        "kind": "local",
        "path": str(target),
        "root": root or str(target),
        "exists": True,
        "is_repo": True,
        "commit": commit or None,
        "branch": branch or None,
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
        "describe": describe or None,
        "remote": _local_remote(target),
        "tags": _tags_at_head(target),
        "submodules": _submodule_state(target),
    }


def inspect_remote(remote, ref=None):
    code, stdout, error = _run(["git", "ls-remote", "--symref", remote], timeout=30)
    if code != 0:
        return {"kind": "remote", "remote": remote, "error": error or "git ls-remote failed"}
    refs = {}
    head_ref = None
    for line in stdout.splitlines():
        if line.startswith("ref: "):
            target, name = line[5:].split("\t", 1)
            if name == "HEAD":
                head_ref = target
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            name = parts[1]
            if name == "HEAD" or name.startswith(("refs/heads/", "refs/tags/")):
                refs[name] = parts[0]
    resolved = refs.get("HEAD")
    if ref:
        candidates = (f"refs/heads/{ref}", f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", ref)
        for candidate in candidates:
            if candidate in refs:
                resolved = refs[candidate]
                break
        else:
            for name, sha in refs.items():
                if name.endswith((f"/{ref}", f"/{ref}^{{}}")):
                    resolved = sha
                    break
    return {"kind": "remote", "remote": remote, "refs": refs, "head_ref": head_ref, "resolved_commit": resolved}


def inspect_repository(spec, base_dir):
    if isinstance(spec, str):
        spec = {"path": spec}
    elif isinstance(spec, dict):
        spec = dict(spec)
    else:
        return {"kind": "unknown", "error": "Repository entry must be a path or object.", "spec": {}}
    path_value = spec.get("path")
    remote = spec.get("remote") or spec.get("url")
    info = None
    if path_value:
        path = resolve_path(base_dir, path_value)
        info = inspect_local(path)
        if not info.get("exists") and remote:
            info["remote_inspection"] = inspect_remote(remote, spec.get("ref"))
    elif remote:
        info = inspect_remote(remote, spec.get("ref"))
    else:
        info = {"kind": "unknown", "error": "repository has neither path nor remote"}
    info["spec"] = spec
    if path_value:
        info["declared_path"] = str(resolve_path(base_dir, path_value))
    return info


def _ref_matches(info, spec):
    ref = spec.get("ref")
    if not ref or info.get("kind") != "local" or not info.get("is_repo"):
        return True
    code, stdout, _ = _git(info["path"], "rev-parse", ref)
    return code == 0 and stdout == info.get("commit")


def repository_issues(spec, info, where):
    issues = []
    optional = bool(spec.get("optional"))
    severity = "info" if optional else "high"
    if info.get("kind") == "unknown" or info.get("error"):
        issues.append(
            make_issue("REPO_UNAVAILABLE", severity, where, info.get("error", "Repository cannot be inspected."), repository=where)
        )
        return issues
    if info.get("kind") == "local" and not info.get("exists"):
        issues.append(make_issue("REPO_MISSING", severity, where, f"Repository path does not exist: {info.get('path')}"))
        return issues
    if info.get("kind") == "local" and not info.get("is_repo"):
        issues.append(make_issue("REPO_NOT_GIT", severity, where, f"Path is not a Git repository: {info.get('path')}"))
        return issues
    if info.get("kind") == "local" and not info.get("commit"):
        issues.append(make_issue("REPO_EMPTY", severity, where, "Repository has no commits."))
    required_clean = spec.get("required_clean", True)
    if required_clean and info.get("dirty"):
        files = ", ".join(info.get("dirty_files", [])[:5])
        issues.append(
            make_issue(
                "REPO_DIRTY",
                severity,
                where,
                f"Working tree has {len(info.get('dirty_files', []))} uncommitted change(s): {files}",
                files=info.get("dirty_files", []),
            )
        )
    if info.get("kind") == "local":
        for module in info.get("submodules", []):
            if module.get("status") != "clean":
                issues.append(
                    make_issue("REPO_SUBMODULE_DIRTY", severity, where, f"Submodule is not clean: {module.get('path')}")
                )
        if spec.get("commit") and info.get("commit") and spec["commit"] != info["commit"]:
            issues.append(
                make_issue(
                    "REPO_COMMIT_MISMATCH",
                    severity,
                    where,
                    f"Declared commit {spec['commit']} does not match HEAD {info['commit']}.",
                    expected=spec["commit"],
                    actual=info["commit"],
                )
            )
        if not _ref_matches(info, spec):
            issues.append(
                make_issue(
                    "REPO_REF_MISMATCH",
                    severity,
                    where,
                    f"Declared ref {spec.get('ref')} does not resolve to HEAD {info.get('commit')}.",
                    expected=spec.get("ref"),
                    actual=info.get("commit"),
                )
            )
        if spec.get("remote") and info.get("remote") and normalize_remote(spec["remote"]) != normalize_remote(info["remote"]):
            issues.append(
                make_issue(
                    "REPO_REMOTE_MISMATCH",
                    "medium",
                    where,
                    f"Declared remote {spec['remote']} does not match origin {info['remote']}.",
                    expected=spec["remote"],
                    actual=info["remote"],
                )
            )
    if info.get("kind") == "remote":
        if spec.get("ref") and not info.get("resolved_commit"):
            issues.append(
                make_issue("REPO_REF_NOT_FOUND", severity, where, f"Remote ref not found: {spec.get('ref')}")
            )
        if spec.get("commit") and info.get("resolved_commit") and spec["commit"] != info["resolved_commit"]:
            issues.append(
                make_issue(
                    "REPO_COMMIT_MISMATCH",
                    severity,
                    where,
                    f"Declared commit {spec['commit']} does not match remote {info['resolved_commit']}.",
                    expected=spec["commit"],
                    actual=info["resolved_commit"],
                )
            )
    return issues


def audit_repositories(manifest, maps, add, base_dir):
    specs = []
    if isinstance(manifest.get("repository"), (dict, str)):
        specs.append(("repository", manifest["repository"]))
    for index, repo in enumerate(as_list(manifest.get("repositories"))):
        if isinstance(repo, dict):
            where = repo.get("id") or f"repository[{index}]"
        else:
            where = f"repository[{index}]"
        if not isinstance(repo, (str, dict)):
            add("REPO_UNAVAILABLE", "high", where, "Repository entry must be a path or object.")
            continue
        specs.append((where, repo))
    results = []
    for where, spec in specs:
        info = inspect_repository(spec, base_dir)
        results.append({"id": where, "info": info, "spec": spec if isinstance(spec, dict) else {"path": spec}})
        for issue in repository_issues(info.get("spec", {}), info, where):
            add(issue["code"], issue["severity"], issue["where"], issue["message"], **issue.get("details", {}))
        component = (spec or {}).get("component") if isinstance(spec, dict) else None
        if component and component not in maps["components"]:
            add("REPO_COMPONENT_MISSING", "high", where, f"Repository references unknown component {component}.")
    return results
