# Three use cases

## 1. IoT hardware + firmware + cloud

Requirements → board/sensor selection → interfaces → firmware → API/UI → integration test → field release.

Representative failures: 3.3V/5V mismatch, pin-map conflict, stale firmware/API payload, board revision drift, unsupported sensor driver, developer-machine-only build.

V2 example: `examples/iot-edge-monitor/product.json` declares an ESP32 firmware component, an I2C sensor bus, an HTTP/JSON contract and two ESP32 device variants. The audit checks interface voltage against both the environment and each device, plus firmware target and resource constraints.

## 2. Mobile app + backend

UX/API → client/backend → contract tests → store build → rollout.

Representative failures: client pins API v1 while backend publishes v2; required fields/auth claims drift; environment variables or token issuers differ; database migrations break older clients.

V2 example: `examples/mobile-api-contract/product.json` binds a REST interface to OpenAPI v1 and v2 specs. The diff confirms the v2 change is additive and reports the optional fields and new `/health` endpoint as informational. Removing a path, making a field required or changing auth would block the gate.

## 3. Edge AI + accelerator

Train → export → quantize → compile → integrate → benchmark → OTA.

Representative failures: tensor shape/dtype mismatch, unsupported operator/runtime, quantization metadata separated from weights, wrong runtime version, memory/latency constraint violations, performance regression after deployment.

V2 example: `examples/edge-ai-deployment/product.json` declares an ONNX model, expected tensor contract, quantization metadata, CycloneDX SBOM and two devices (Qualcomm QNN and x86 ONNX Runtime). The audit parses the ONNX protobuf directly, checks IR/opset/dtype/shape/hash/quantization consistency and validates the SBOM inventory.

## Using one workspace for several open-source products

`examples/workspace.json` groups all three products. Each product can declare multiple device variants, so a single workspace can track a family of open-source hardware products that share firmware, interfaces or AI artifacts while differing in board, memory, voltage or runtime target.
