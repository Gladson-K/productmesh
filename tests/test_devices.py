from helpers import audit_data, code_list, find_issue, iot_data, iot_manifest


def test_multiple_devices_are_audited():
    result = audit_data(iot_data(), iot_manifest().base_dir)
    assert result["release_ready"] is True
    assert result["summary"]["devices"] == 2
    assert {row["id"] for row in result["devices"]} == {"DEV-ESP32-S3", "DEV-ESP32-C3"}


def test_device_voltage_mismatch_blocks():
    data = iot_data()
    data["devices"][1]["logic_voltage"] = "5V"
    result = audit_data(data, iot_manifest().base_dir)
    issue = find_issue(result, "DEVICE_VOLTAGE_MISMATCH")
    assert issue is not None
    assert issue["severity"] == "critical"
    assert result["release_ready"] is False


def test_device_environment_voltage_mismatch_blocks():
    data = iot_data()
    data["devices"][0]["logic_voltage"] = "1.8V"
    result = audit_data(data, iot_manifest().base_dir)
    assert find_issue(result, "DEVICE_ENV_VOLTAGE_MISMATCH")["severity"] == "critical"


def test_device_missing_firmware():
    data = iot_data()
    data["devices"][0]["firmware"] = "CMP-NOPE"
    result = audit_data(data, iot_manifest().base_dir)
    assert "DEVICE_FIRMWARE_MISSING" in code_list(result)


def test_device_resource_shortfall():
    data = iot_data()
    data["devices"][0]["specs"]["flash_mb"] = 1
    result = audit_data(data, iot_manifest().base_dir)
    issue = find_issue(result, "DEVICE_RESOURCE_SHORTFALL")
    assert issue is not None
    assert issue["details"]["required"] == 8
    assert issue["details"]["actual"] == 1


def test_device_board_mismatch_is_medium():
    data = iot_data()
    data["devices"][0]["board"] = "stm32-nucleo"
    result = audit_data(data, iot_manifest().base_dir)
    issue = find_issue(result, "DEVICE_BOARD_MISMATCH")
    assert issue is not None
    assert issue["severity"] == "medium"


def test_duplicate_device_id():
    data = iot_data()
    data["devices"][1]["id"] = data["devices"][0]["id"]
    result = audit_data(data, iot_manifest().base_dir)
    assert "DEVICE_DUPLICATE_ID" in code_list(result)
