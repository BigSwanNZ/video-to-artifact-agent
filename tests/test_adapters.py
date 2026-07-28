import json
from http import HTTPStatus

from video_to_artifact_agent.adapters.http import (
    build_spec_schema_payload,
    dispatch_http_request,
)
from video_to_artifact_agent.adapters.mcp import (
    TOOL_ANALYZE,
    TOOL_CAPABILITIES,
    TOOL_SCHEMA,
    dispatch_tool,
    tool_manifest,
)
from video_to_artifact_agent.schemas import BuildSpec


def decoded_http_payload(method: str, path: str, body: dict[str, object] | None = None) -> tuple[int, dict[str, object]]:
    raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
    status, _headers, response_body = dispatch_http_request(method, path, raw_body)
    return status, json.loads(response_body.decode("utf-8"))


def test_http_health_capabilities_and_schema_payloads() -> None:
    health_status, health = decoded_http_payload("GET", "/health")
    capabilities_status, capabilities = decoded_http_payload("GET", "/capabilities")
    schema_status, schema = decoded_http_payload("GET", "/schemas/build-spec")

    assert health_status == HTTPStatus.OK
    assert health["status"] == "ok"
    assert capabilities_status == HTTPStatus.OK
    assert capabilities["capabilities"][0]["runtime"] == "unconfigured"
    assert schema_status == HTTPStatus.OK
    assert schema == build_spec_schema_payload()
    assert schema["title"] == "BuildSpec"


def test_http_analyze_creates_valid_build_spec() -> None:
    status, payload = decoded_http_payload(
        "POST",
        "/analyze",
        {
            "source": "https://example.com/training.mp4",
            "artifact_type": "excel",
            "title": "Training model",
            "runtime": "neutral-runtime",
            "model": "neutral-model",
        },
    )

    spec = BuildSpec.model_validate(payload)
    assert status == HTTPStatus.OK
    assert spec.source.url == "https://example.com/training.mp4"
    assert spec.runtime is not None
    assert spec.runtime.runtime == "neutral-runtime"
    assert spec.artifact.artifact_type == "excel"
    assert spec.requirements["adapter"] == "http"


def test_http_analyze_rejects_missing_source() -> None:
    status, payload = decoded_http_payload("POST", "/analyze", {"artifact_type": "web"})

    assert status == HTTPStatus.BAD_REQUEST
    assert "requires source" in payload["message"]


def test_mcp_manifest_exposes_expected_tools() -> None:
    names = {tool["name"] for tool in tool_manifest()["tools"]}

    assert {TOOL_CAPABILITIES, TOOL_SCHEMA, TOOL_ANALYZE}.issubset(names)


def test_mcp_dispatch_capabilities_schema_and_analyze() -> None:
    capabilities = dispatch_tool(TOOL_CAPABILITIES)
    schema = dispatch_tool(TOOL_SCHEMA, {"name": "build-spec"})
    analyze = dispatch_tool(
        TOOL_ANALYZE,
        {
            "source": {"kind": "local_file", "local_path": "/tmp/demo.mp4"},
            "artifact": {
                "artifact_type": "doc",
                "title": "Demo notes",
            },
            "runtime": {
                "runtime": "test-runtime",
                "model": "test-model",
            },
        },
    )

    assert capabilities["ok"] is True
    assert schema["content"][0]["json"]["title"] == "BuildSpec"
    assert analyze["ok"] is True
    spec = BuildSpec.model_validate(analyze["content"][0]["json"])
    assert spec.source.local_path == "/tmp/demo.mp4"
    assert spec.artifact.artifact_type == "doc"
    assert spec.runtime is not None
    assert spec.runtime.model == "test-model"


def test_mcp_dispatch_reports_contract_errors() -> None:
    result = dispatch_tool(TOOL_ANALYZE, {"artifact_type": "excel"})

    assert result["ok"] is False
    assert "requires source" in result["error"]["message"]
