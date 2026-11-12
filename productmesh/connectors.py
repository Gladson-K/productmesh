from .manifest import as_list, load_data


class Connector:
    name = "base"
    kind = "metadata"
    description = "Base connector stub"

    def normalize(self, data):
        raise NotImplementedError

    def describe(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "network": False,
            "status": "stub",
        }


class GitHubConnector(Connector):
    name = "github"
    kind = "repository"
    description = "Normalize GitHub repository and pull-request metadata from a local JSON export"

    def normalize(self, data):
        data = data or {}
        repo = data.get("repository") or data.get("repo") or {}
        repositories = []
        if repo:
            repositories.append(
                {
                    "id": repo.get("full_name") or repo.get("name"),
                    "remote": repo.get("html_url") or repo.get("clone_url"),
                    "ref": repo.get("default_branch"),
                    "commit": (data.get("head") or {}).get("sha") or repo.get("pushed_at"),
                }
            )
        pull_requests = []
        for item in as_list(data.get("pull_requests") or data.get("pulls")):
            if not isinstance(item, dict):
                continue
            head = item.get("head") or {}
            base = item.get("base") or {}
            pull_requests.append(
                {
                    "id": item.get("number") or item.get("id"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "head": head.get("sha") or head.get("ref"),
                    "base": base.get("ref"),
                    "url": item.get("html_url"),
                }
            )
        return {"connector": self.name, "repositories": repositories, "pull_requests": pull_requests}


class GitLabConnector(Connector):
    name = "gitlab"
    kind = "repository"
    description = "Normalize GitLab project and merge-request metadata from a local JSON export"

    def normalize(self, data):
        data = data or {}
        project = data.get("project") or data.get("repository") or {}
        repositories = []
        if project:
            repositories.append(
                {
                    "id": project.get("path_with_namespace") or project.get("name"),
                    "remote": project.get("web_url") or project.get("http_url_to_repo"),
                    "ref": project.get("default_branch"),
                    "commit": project.get("last_activity_at"),
                }
            )
        merge_requests = []
        for item in as_list(data.get("merge_requests") or data.get("mrs")):
            if not isinstance(item, dict):
                continue
            merge_requests.append(
                {
                    "id": item.get("iid") or item.get("id"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "head": item.get("sha"),
                    "base": item.get("target_branch"),
                    "url": item.get("web_url"),
                }
            )
        return {"connector": self.name, "repositories": repositories, "merge_requests": merge_requests}


class JiraConnector(Connector):
    name = "jira"
    kind = "requirements"
    description = "Normalize Jira issue metadata into requirement entries"

    def normalize(self, data):
        data = data or {}
        requirements = []
        for item in as_list(data.get("issues")):
            if not isinstance(item, dict):
                continue
            fields = item.get("fields") or {}
            priority = fields.get("priority") or {}
            status = fields.get("status") or {}
            requirements.append(
                {
                    "id": item.get("key") or item.get("id"),
                    "statement": fields.get("summary") or fields.get("description"),
                    "criticality": str(priority.get("name") or "medium").lower(),
                    "status": status.get("name"),
                    "source": "jira",
                }
            )
        return {"connector": self.name, "requirements": requirements}


class AzureDevOpsConnector(Connector):
    name = "azure"
    kind = "requirements"
    description = "Normalize Azure DevOps work-item metadata into requirement entries"

    def normalize(self, data):
        data = data or {}
        requirements = []
        for item in as_list(data.get("workItems") or data.get("work_items")):
            if not isinstance(item, dict):
                continue
            fields = item.get("fields") or {}
            requirements.append(
                {
                    "id": str(item.get("id")),
                    "statement": fields.get("System.Title") or fields.get("System.Description"),
                    "criticality": str(fields.get("Microsoft.VSTS.Common.Priority") or "medium").lower(),
                    "status": fields.get("System.State"),
                    "source": "azure",
                }
            )
        return {"connector": self.name, "requirements": requirements}


CONNECTORS = {
    connector.name: connector
    for connector in (GitHubConnector(), GitLabConnector(), JiraConnector(), AzureDevOpsConnector())
}


def list_connectors():
    return [connector.describe() for connector in CONNECTORS.values()]


def get_connector(name):
    key = str(name).lower()
    if key == "azure_devops":
        key = "azure"
    connector = CONNECTORS.get(key)
    if connector is None:
        raise ValueError(f"Unknown connector: {name}")
    return connector


def inspect_connector(name, path):
    connector = get_connector(name)
    result = connector.normalize(load_data(path))
    result["status"] = "stub"
    result["network"] = False
    return result


def import_fragment(name, path):
    connector = get_connector(name)
    normalized = connector.normalize(load_data(path))
    fragment = {"source": name, "connector_status": "stub"}
    if normalized.get("repositories"):
        fragment["repositories"] = normalized["repositories"]
    if normalized.get("requirements"):
        fragment["requirements"] = normalized["requirements"]
    if normalized.get("pull_requests"):
        fragment["pull_requests"] = normalized["pull_requests"]
    if normalized.get("merge_requests"):
        fragment["merge_requests"] = normalized["merge_requests"]
    return fragment
