from helpers import audit_data, find_issue, git, init_git_repo, iot_data

from productmesh.repo import inspect_local, inspect_remote, normalize_remote


def test_inspect_local_clean_repository(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    info = inspect_local(repo)
    assert info["is_repo"] is True
    assert info["dirty"] is False
    assert info["commit"]
    assert info["branch"] in ("main", "master")


def test_repository_audit_clean(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    data = iot_data()
    data["repositories"] = [
        {"id": "REPO-CORE", "path": str(repo), "ref": "HEAD", "required_clean": True}
    ]
    result = audit_data(data, tmp_path)
    assert result["release_ready"] is True
    assert result["summary"]["repositories"] == 1


def test_repository_dirty_blocks(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    (repo / "dirty.txt").write_text("change\n")
    data = iot_data()
    data["repositories"] = [{"id": "REPO-CORE", "path": str(repo), "required_clean": True}]
    result = audit_data(data, tmp_path)
    issue = find_issue(result, "REPO_DIRTY")
    assert issue is not None
    assert issue["severity"] == "high"
    assert result["release_ready"] is False


def test_repository_commit_mismatch(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    data = iot_data()
    data["repositories"] = [{"id": "REPO-CORE", "path": str(repo), "commit": "deadbeef"}]
    result = audit_data(data, tmp_path)
    assert "REPO_COMMIT_MISMATCH" in [issue["code"] for issue in result["issues"]]


def test_repository_ref_mismatch(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    git(repo, "checkout", "-qb", "feature")
    (repo / "feature.txt").write_text("feature\n")
    git(repo, "add", "feature.txt")
    git(repo, "commit", "-qm", "feature")
    current = git(repo, "branch", "--show-current")
    other = "main" if current != "main" else "master"
    data = iot_data()
    data["repositories"] = [{"id": "REPO-CORE", "path": str(repo), "ref": other}]
    result = audit_data(data, tmp_path)
    assert "REPO_REF_MISMATCH" in [issue["code"] for issue in result["issues"]]


def test_repository_not_git(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    data = iot_data()
    data["repositories"] = [{"id": "REPO-CORE", "path": str(plain)}]
    result = audit_data(data, tmp_path)
    assert "REPO_NOT_GIT" in [issue["code"] for issue in result["issues"]]


def test_remote_inspection_with_local_path(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    info = inspect_remote(str(repo))
    assert info["kind"] == "remote"
    assert info["resolved_commit"]
    assert "refs/heads/" in " ".join(info["refs"].keys())


def test_normalize_remote():
    assert normalize_remote("git@github.com:org/repo.git") == "github.com/org/repo"
    assert normalize_remote("https://github.com/org/repo.git") == "github.com/org/repo"
    assert normalize_remote("ssh://git@github.com/org/repo.git") == "github.com/org/repo"
def test_optional_dirty_repository_does_not_block(tmp_path):
    repo = init_git_repo(tmp_path / "repo")
    (repo / "dirty.txt").write_text("change\n")
    data = iot_data()
    data["repositories"] = [{"id": "REPO-CORE", "path": str(repo), "required_clean": True, "optional": True}]
    result = audit_data(data, tmp_path)
    issue = find_issue(result, "REPO_DIRTY")
    assert issue["severity"] == "info"
    assert result["release_ready"] is True
