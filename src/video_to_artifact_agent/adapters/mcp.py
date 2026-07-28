from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from video_to_artifact_agent.adapters.http import (
    build_spec_schema_payload,
    capabilities_payload,
    create_build_spec,
)
from video_to_artifact_agent.schemas import BuildSpec, RuntimeCapability

JsonObject = dict[str, Any]

TOOL_CAPABILITIES = "video_to_artifact.capabilities"
TOOL_SCHEMA = "video_to_artifact.schema"
TOOL_ANALYZE = "video_to_artifact.analyze"


def tool_manifest() -> JsonObject:
    return {
        "version": 1,
        "tools": [
            {
                "name": TOOL_CAPABILITIES,
                "description": "Return runtime capabilities advertised by this Video-to-Artifact Agent adapter.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": TOOL_SCHEMA,
                "description": "Return JSON schema for a public Video-to-Artifact Agent contract.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": ["build-spec"],
                            "default": "build-spec",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": TOOL_ANALYZE,
                "description": "Create an initial BuildSpec JSON object from a video source and requested artifact.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "oneOf": [
                                {"type": "string"},
                                BuildSpec.model_json_schema()["properties"]["source"],
                            ]
                        },
                        "artifact_type": {
                            "type": "string",
                            "enum": ["excel", "web", "code", "doc", "generic", "unknown"],
                            "default": "unknown",
                        },
                        "title": {"type": "string"},
                        "instructions": {"type": "string"},
                        "runtime": {
                            "oneOf": [
                                {"type": "string"},
                                RuntimeCapability.model_json_schema(),
                            ]
                        },
                        "model": {"type": "string"},
                    },
                    "required": ["source"],
                    "additionalProperties": True,
                },
            },
        ],
    }


def dispatch_tool(
    name: str,
    arguments: JsonObject | None = None,
    capabilities: list[RuntimeCapability] | None = None,
) -> JsonObject:
    args = arguments or {}
    if not isinstance(args, dict):
        return tool_error(name, "Tool arguments must be a JSON object.")

    try:
        if name == TOOL_CAPABILITIES:
            return tool_result(name, capabilities_payload(capabilities))
        if name == TOOL_SCHEMA:
            schema_name = args.get("name", "build-spec")
            if schema_name != "build-spec":
                return tool_error(name, f"Unsupported schema contract: {schema_name}")
            return tool_result(name, build_spec_schema_payload())
        if name == TOOL_ANALYZE:
            spec = create_build_spec(args)
            return tool_result(name, spec.model_dump(mode="json"))
    except ValidationError as exc:
        return tool_error(name, "Tool arguments failed schema validation.", exc.errors())
    except ValueError as exc:
        return tool_error(name, str(exc))

    return tool_error(name, f"Unknown tool: {name}")


def tool_result(name: str, payload: JsonObject) -> JsonObject:
    return {
        "tool": name,
        "ok": True,
        "content": [
            {
                "type": "json",
                "json": payload,
            }
        ],
    }


def tool_error(name: str, message: str, details: Any | None = None) -> JsonObject:
    payload: JsonObject = {
        "tool": name,
        "ok": False,
        "error": {
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload

