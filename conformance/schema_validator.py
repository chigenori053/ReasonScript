"""Small Draft 2020-12 validator for the keywords used by this repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from conformance.framework import ConformanceError, load_json


class SchemaValidator:
    def __init__(self, schema_root: Path):
        self.schema_root = schema_root
        self._cache: dict[Path, dict[str, Any]] = {}

    def validate_file(self, instance: Any, schema_name: str) -> None:
        path = self.schema_root / schema_name
        self._validate(instance, self._load(path), path, "$")

    def _load(self, path: Path) -> dict[str, Any]:
        path = path.resolve()
        if path not in self._cache:
            self._cache[path] = load_json(path)
        return self._cache[path]

    def _validate(self, value: Any, schema: Any, source: Path, location: str) -> None:
        if schema is True:
            return
        if schema is False:
            raise ConformanceError(f"{location}: schema rejected value")
        if "$ref" in schema:
            target_schema, target_source = self._resolve(schema["$ref"], source)
            self._validate(value, target_schema, target_source, location)
            return
        if "oneOf" in schema:
            matches = 0
            for option in schema["oneOf"]:
                try:
                    self._validate(value, option, source, location)
                    matches += 1
                except ConformanceError:
                    pass
            if matches != 1:
                raise ConformanceError(f"{location}: expected exactly one schema match")
        if "const" in schema and value != schema["const"]:
            raise ConformanceError(f"{location}: expected {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            raise ConformanceError(f"{location}: value is not in enum")
        if "type" in schema and not self._matches_type(value, schema["type"]):
            raise ConformanceError(f"{location}: invalid type")
        if isinstance(value, dict):
            required = schema.get("required", [])
            for name in required:
                if name not in value:
                    raise ConformanceError(f"{location}: missing {name}")
            properties = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                extras = value.keys() - properties.keys()
                if extras:
                    raise ConformanceError(f"{location}: unknown field {sorted(extras)[0]}")
            for name, item in value.items():
                if name in properties:
                    self._validate(item, properties[name], source, f"{location}.{name}")
                elif isinstance(schema.get("additionalProperties"), dict):
                    self._validate(
                        item, schema["additionalProperties"], source, f"{location}.{name}"
                    )
        if isinstance(value, list) and "items" in schema:
            for index, item in enumerate(value):
                self._validate(item, schema["items"], source, f"{location}[{index}]")
        if isinstance(value, str) and len(value) < schema.get("minLength", 0):
            raise ConformanceError(f"{location}: string is too short")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise ConformanceError(f"{location}: below minimum")
            if "maximum" in schema and value > schema["maximum"]:
                raise ConformanceError(f"{location}: above maximum")

    def _resolve(self, reference: str, source: Path) -> tuple[Any, Path]:
        filename, _, fragment = reference.partition("#")
        target_source = (source.parent / filename).resolve() if filename else source
        target: Any = self._load(target_source)
        if fragment:
            for part in fragment.lstrip("/").split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        return target, target_source

    @staticmethod
    def _matches_type(value: Any, expected: str | list[str]) -> bool:
        names = [expected] if isinstance(expected, str) else expected
        checks = {
            "null": value is None,
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        }
        return any(checks.get(name, False) for name in names)
