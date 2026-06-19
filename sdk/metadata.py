"""SDK metadata generation — emits sdk_usage into build metadata."""

from __future__ import annotations

from typing import Any


def extract_sdk_usage(reason_ir: dict[str, Any]) -> list[str]:
    """Scan a Reason IR dict for sdk_usage hints and return them."""
    meta = reason_ir.get("metadata") or {}
    return list(meta.get("sdk_usage") or [])


def inject_sdk_usage(
    metadata: dict[str, Any], sdk_modules: list[str]
) -> dict[str, Any]:
    """Return a copy of metadata with sdk_usage field added/updated."""
    result = dict(metadata)
    existing = list(result.get("sdk_usage") or [])
    merged = existing + [m for m in sdk_modules if m not in existing]
    result["sdk_usage"] = merged
    return result


def build_sdk_metadata(sdk_modules: list[str]) -> dict[str, Any]:
    """Build a standalone SDK metadata dict."""
    return {"sdk_usage": list(sdk_modules)}
