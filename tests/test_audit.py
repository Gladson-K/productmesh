from pathlib import Path

from productmesh.audit import audit, load_manifest

ROOT=Path(__file__).resolve().parents[1]
def test_iot_passes():assert audit(load_manifest(ROOT/"examples/iot-edge-monitor/product.json"))["release_ready"]
def test_voltage_mismatch_blocks():
 d=load_manifest(ROOT/"examples/iot-edge-monitor/product.json");d["environments"][0]["logic_voltage"]="5V";r=audit(d);assert any(x["code"]=="VOLTAGE_MISMATCH" and x["severity"]=="critical" for x in r["issues"])
def test_missing_test_blocks():
 d=load_manifest(ROOT/"examples/iot-edge-monitor/product.json");d["requirements"][0]["verified_by"]=["NOPE"];assert any(x["code"]=="TEST_REFERENCE_MISSING" for x in audit(d)["issues"])
def test_null_collections_do_not_crash():
 d=load_manifest(ROOT/"examples/iot-edge-monitor/product.json");d["tests"]=None;d["requirements"]=None;r=audit(d);assert isinstance(r["issues"],list)
def test_single_device_object_is_supported():
 d=load_manifest(ROOT/"examples/iot-edge-monitor/product.json");d["devices"]=d["devices"][0];r=audit(d);assert r["summary"]["devices"]==1
