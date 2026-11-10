import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from productmesh.server import Handler


@pytest.fixture
def base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_health(base_url):
    status, payload = get_json(base_url + "/healthz")
    assert status == 200
    assert payload["status"] == "ok"


def test_examples(base_url):
    status, payload = get_json(base_url + "/api/examples")
    assert status == 200
    assert "iot-edge-monitor" in payload["examples"]


def test_product_audit(base_url):
    status, payload = get_json(base_url + "/api/audit/iot-edge-monitor")
    assert status == 200
    assert payload["release_ready"] is True
    assert payload["summary"]["devices"] == 2


def test_workspace_audit(base_url):
    status, payload = get_json(base_url + "/api/workspace")
    assert status == 200
    assert payload["summary"]["products"] == 3
    assert payload["release_ready"] is True


def test_devices(base_url):
    status, payload = get_json(base_url + "/api/devices")
    assert status == 200
    assert len(payload["devices"]) == 4


def test_unknown_product(base_url):
    with pytest.raises(urllib.error.HTTPError) as error:
        get_json(base_url + "/api/audit/does-not-exist")
    assert error.value.code == 404
