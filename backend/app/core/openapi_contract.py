"""OpenAPI 契约规范化与可复现快照。

只修正文档层：运行时成功/错误信封仍由 app.core.envelope 负责。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
ENVELOPE_SCHEMA_NAME = "UnifiedEnvelope"
ENVELOPE_REF = f"#/components/schemas/{ENVELOPE_SCHEMA_NAME}"
SSE_OPERATION_IDS = {
    "dialogue_api_v1_profile_dialogue_post",
    "tutor_chat_api_v1_resource_tutor_chat_post",
    "feynman_api_v1_learning_feynman_post",
    "doc_chat_api_v1_document_chat_post",
}


def _envelope_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": ENVELOPE_REF}}},
    }


def normalize_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    """给全部 HTTP 操作标注统一信封，并对齐实际的 400 校验错误。"""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components[ENVELOPE_SCHEMA_NAME] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "message", "data", "traceId"],
        "properties": {
            "code": {"type": "integer"},
            "message": {"type": "string"},
            "data": {},
            "traceId": {"type": "string"},
        },
    }
    for path_item in schema.get("paths", {}).values():
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            operation["x-zhixue-envelope"] = True
            responses = operation.setdefault("responses", {})
            success = responses.setdefault("200", _envelope_response("Unified success envelope"))
            success_content = success.setdefault("content", {})
            success_content["application/json"] = {"schema": {"$ref": ENVELOPE_REF}}
            if operation.get("operationId") in SSE_OPERATION_IDS:
                success_content["text/event-stream"] = {"schema": {"type": "string"}}
            if "422" in responses:
                responses.pop("422")
                responses["400"] = _envelope_response("Validation error envelope (code=1001)")
            for status, response in responses.items():
                if status.startswith(("4", "5")) and status != "400":
                    response.setdefault("content", {})["application/json"] = {
                        "schema": {"$ref": ENVELOPE_REF}
                    }
    return schema


def install_openapi_contract(app: FastAPI) -> None:
    """安装一次性 OpenAPI 后处理器，不影响实际路由处理函数。"""
    original_openapi = app.openapi

    def contracted_openapi() -> dict[str, Any]:
        if app.openapi_schema is None or not app.openapi_schema.get("x-zhixue-contract"):
            schema = normalize_openapi(original_openapi())
            schema["x-zhixue-contract"] = "openapi-v1"
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi_schema = None
    app.openapi = contracted_openapi  # type: ignore[method-assign]


def _without_documentation_noise(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_documentation_noise(item)
            for key, item in sorted(value.items())
            if key not in {"description", "summary", "externalDocs"}
        }
    if isinstance(value, list):
        return [_without_documentation_noise(item) for item in value]
    return value


def build_openapi_snapshot(schema: dict[str, Any]) -> dict[str, Any]:
    """保留路径、方法、请求/响应 Schema 与组件模型，去除纯文案噪声。"""
    operations: dict[str, Any] = {}
    for path, path_item in sorted(schema.get("paths", {}).items()):
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            key = f"{method.upper()} {path}"
            operations[key] = {
                field: deepcopy(operation[field])
                for field in (
                    "operationId",
                    "tags",
                    "parameters",
                    "requestBody",
                    "responses",
                    "security",
                    "deprecated",
                    "x-zhixue-envelope",
                )
                if field in operation
            }
    schemas = deepcopy(schema.get("components", {}).get("schemas", {}))
    return _without_documentation_noise(
        {
            "snapshotVersion": 1,
            "openapi": schema.get("openapi"),
            "contract": schema.get("x-zhixue-contract"),
            "operationCount": len(operations),
            "schemaCount": len(schemas),
            "operations": operations,
            "schemas": schemas,
        }
    )
