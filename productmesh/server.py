import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import __version__
from .audit import audit_file
from .workspace import audit_workspace, load_workspace_or_discover, workspace_products

ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX = Path(__file__).resolve().parent / "web" / "index.html"
EXAMPLES = Path(os.environ.get("PRODUCTMESH_EXAMPLES", ROOT / "examples"))
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

FALLBACK_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>ProductMesh</title></head>
<body><h1>ProductMesh</h1><p>The dashboard asset is missing. Use the CLI: <code>productmesh workspace audit</code>.</p></body></html>"""


def _workspace():
    if EXAMPLES.is_dir():
        return load_workspace_or_discover(EXAMPLES)
    return load_workspace_or_discover(Path.cwd())


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, indent=2).encode("utf-8"), "application/json")

    def _html(self, status, body):
        self._send(status, body.encode("utf-8"), "text/html; charset=utf-8")

    def _error(self, status, message):
        self._json(status, {"error": message})

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            if WEB_INDEX.is_file():
                self._send(200, WEB_INDEX.read_bytes(), "text/html; charset=utf-8")
            else:
                self._html(200, FALLBACK_HTML)
            return
        if path == "/healthz":
            self._json(200, {"status": "ok", "version": __version__})
            return
        if path == "/api/version":
            self._json(200, {"name": "ProductMesh", "version": __version__})
            return
        if path == "/api/examples":
            examples = sorted(item.parent.name for item in EXAMPLES.glob("*/product.json"))
            self._json(200, {"examples": examples})
            return
        if path.startswith("/api/audit/"):
            name = path.rsplit("/", 1)[-1]
            if not SAFE_NAME.match(name) or name in (".", ".."):
                self._error(400, "invalid product name")
                return
            manifest = EXAMPLES / name / "product.json"
            if not manifest.is_file():
                self._error(404, "product not found")
                return
            try:
                self._json(200, audit_file(manifest))
            except Exception as exc:
                self._error(400, str(exc))
            return
        if path == "/api/workspace":
            try:
                self._json(200, audit_workspace(_workspace()))
            except Exception as exc:
                self._error(400, str(exc))
            return
        if path == "/api/products":
            try:
                workspace = _workspace()
                products = workspace_products(workspace)
                for product in products:
                    product.pop("path", None)
                self._json(200, {"workspace": workspace.get("workspace"), "products": products})
            except Exception as exc:
                self._error(400, str(exc))
            return
        if path == "/api/devices":
            try:
                result = audit_workspace(_workspace())
                self._json(200, {"devices": result.get("devices", []), "summary": result.get("summary")})
            except Exception as exc:
                self._error(400, str(exc))
            return
        self._error(404, "not found")

    def log_message(self, *args):
        if os.environ.get("PRODUCTMESH_LOG"):
            super().log_message(*args)


def main(host=None, port=None):
    host = host or os.environ.get("PRODUCTMESH_HOST", "127.0.0.1")
    port = port if port is not None else int(os.environ.get("PRODUCTMESH_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), Handler)
    actual_port = server.server_address[1]
    print(f"ProductMesh {__version__}: http://{host}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
