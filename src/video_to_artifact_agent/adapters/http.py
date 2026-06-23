from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from video_to_artifact_agent import __version__
from video_to_artifact_agent.schemas import (
    ArtifactRequirement,
    BuildSpec,
    RuntimeCapability,
    SourceInfo,
)
from video_to_artifact_agent.workflow import create_initial_spec, source_info_from_input

JsonObject = dict[str, Any]


def default_capability() -> RuntimeCapability:
    return RuntimeCapability(
        runtime="unconfigured",
        model="unconfigured",
        notes=["HTTP adapter contract is available; no runtime is configured by default."],
    )


def source_info_from_value(value: str | JsonObject) -> SourceInfo:
    if isinstance(value, dict):
        return SourceInfo.model_validate(value)
    return source_info_from_input(value)


def create_build_spec(payload: JsonObject) -> BuildSpec:
    source_value = payload.get("source")
    if not isinstance(source_value, (str, dict)):
        raise ValueError("analyze payload requires source as a string or SourceInfo object")

    runtime_value = payload.get("runtime")
    if isinstance(runtime_value, dict):
        runtime = RuntimeCapability.model_validate(runtime_value)
    else:
        runtime = RuntimeCapability(
            runtime=str(runtime_value or "unconfigured"),
            model=str(payload.get("model") or "unconfigured"),
        )

    artifact_value = payload.get("artifact")
    if isinstance(artifact_value, dict):
        artifact = ArtifactRequirement.model_validate(artifact_value)
    else:
        artifact = ArtifactRequirement(
            artifact_type=payload.get("artifact_type", "unknown"),
            title=payload.get("title"),
            instructions=payload.get("instructions"),
            builder=payload.get("builder"),
        )

    spec = create_initial_spec(
        source_info_from_value(source_value),
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        instructions=artifact.instructions,
        runtime=runtime,
    )
    spec.artifact = artifact
    spec.requirements = {**spec.requirements, "adapter": "http"}
    return spec


def health_payload() -> JsonObject:
    return {
        "status": "ok",
        "service": "video-to-artifact-agent",
        "version": __version__,
    }


def capabilities_payload(capabilities: list[RuntimeCapability] | None = None) -> JsonObject:
    selected = capabilities or [default_capability()]
    return {
        "version": 1,
        "capabilities": [capability.model_dump(mode="json") for capability in selected],
    }


def build_spec_schema_payload() -> JsonObject:
    return BuildSpec.model_json_schema()


def json_response(status: int, payload: JsonObject) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(payload, indent=2).encode("utf-8")
    return (
        status,
        {
            "content-type": "application/json; charset=utf-8",
            "content-length": str(len(body)),
        },
        body,
    )


def error_payload(status: HTTPStatus, message: str, details: Any | None = None) -> JsonObject:
    payload: JsonObject = {
        "error": status.phrase,
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return payload


def dispatch_http_request(
    method: str,
    path: str,
    body: bytes = b"",
    capabilities: list[RuntimeCapability] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    parsed = urlparse(path)
    route = parsed.path.rstrip("/") or "/"
    method = method.upper()

    if method == "GET" and route == "/health":
        return json_response(HTTPStatus.OK, health_payload())
    if method == "GET" and route == "/capabilities":
        return json_response(HTTPStatus.OK, capabilities_payload(capabilities))
    if method == "GET" and route == "/schemas/build-spec":
        return json_response(HTTPStatus.OK, build_spec_schema_payload())
    if method == "POST" and route == "/analyze":
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            spec = create_build_spec(payload)
        except json.JSONDecodeError as exc:
            return json_response(
                HTTPStatus.BAD_REQUEST,
                error_payload(HTTPStatus.BAD_REQUEST, "Invalid JSON request body.", str(exc)),
            )
        except ValidationError as exc:
            return json_response(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                error_payload(HTTPStatus.UNPROCESSABLE_ENTITY, "Request failed schema validation.", exc.errors()),
            )
        except ValueError as exc:
            return json_response(
                HTTPStatus.BAD_REQUEST,
                error_payload(HTTPStatus.BAD_REQUEST, str(exc)),
            )
        return json_response(HTTPStatus.OK, spec.model_dump(mode="json"))

    if route in {"/health", "/capabilities", "/schemas/build-spec", "/analyze"}:
        return json_response(
            HTTPStatus.METHOD_NOT_ALLOWED,
            error_payload(HTTPStatus.METHOD_NOT_ALLOWED, f"{method} is not supported for {route}."),
        )
    return json_response(
        HTTPStatus.NOT_FOUND,
        error_payload(HTTPStatus.NOT_FOUND, f"No HTTP adapter route matches {route}."),
    )


def make_handler(
    capabilities: list[RuntimeCapability] | None = None,
) -> type[BaseHTTPRequestHandler]:
    class VideoToArtifactHandler(BaseHTTPRequestHandler):
        server_version = "VideoToArtifactAgentHTTP/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            self._dispatch()

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            self._dispatch()

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _dispatch(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length) if length else b""
            status, headers, response_body = dispatch_http_request(
                self.command,
                self.path,
                body,
                capabilities=capabilities,
            )
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response_body)

    return VideoToArtifactHandler


def make_server(
    host: str = "127.0.0.1",
    port: int = 0,
    capabilities: list[RuntimeCapability] | None = None,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(capabilities=capabilities))
