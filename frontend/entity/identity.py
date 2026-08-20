"""Canonical Entity ID generation and parsing (RS-RE-FSM-001 §7.2, §3.3).

Format (design doc §3.3)::

    canonical_entity_id := <u1-prefix> <kind-tag> ":" <path>

    u1-prefix := "ruo:unit:"    (RU / RUS / DERIVE)
               | "ruo:object:"  (RUO)
    kind-tag  := "ru" | "rus" | "ruo" | "derive"
    path      := <namespace> ( "." <owner-identifier> )* "." <identifier>
    namespace := <package> "." <module>   (package present)
               | <module>                 (package absent)

The prefix reuses ``toolchain.reasonunit_object.model.CORE_PREFIXES`` so an
Entity ID is structurally compatible with an RUO-U1 projection (ADR-101):
``ruo:unit:...`` and ``ruo:object:...`` both start with a valid RUO-U1
entity namespace.

No host-specific path, memory address, or timestamp is ever an input to
this module (RS-RE-FSM-001 §7.2 MUST NOT) -- the function signature itself
enforces this: only package/module/owner-path/identifier/kind are accepted.
"""

from __future__ import annotations

import re

from toolchain.reasonunit_object.model import CORE_PREFIXES

from .kinds import EntityKind

_IDENTIFIER = re.compile(r"[A-Za-z_]\w*")

_KIND_TAGS: dict[EntityKind, str] = {
    EntityKind.RU: "ru",
    EntityKind.RUS: "rus",
    EntityKind.RUO: "ruo",
    EntityKind.DERIVE: "derive",
}
_TAG_KINDS: dict[str, EntityKind] = {tag: kind for kind, tag in _KIND_TAGS.items()}


class CanonicalIdError(ValueError):
    """Raised when Canonical Entity ID inputs or a parsed ID are invalid."""


def _validate_identifier(value: str, label: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise CanonicalIdError(f"RE-ID-002 invalid {label}: {value!r}")


def canonical_entity_id(
    *,
    kind: EntityKind,
    module: str,
    identifier: str,
    package: str | None = None,
    owner_path: tuple[str, ...] = (),
) -> str:
    """Build a Canonical Entity ID deterministically from declaration facts.

    ``owner_path`` is the chain of enclosing RUS/RUO identifiers, outermost
    first (empty for a module-level declaration).
    """
    _validate_identifier(module, "module")
    _validate_identifier(identifier, "identifier")
    if package is not None:
        _validate_identifier(package, "package")
    for owner in owner_path:
        _validate_identifier(owner, "owner_path segment")

    prefix = CORE_PREFIXES["object"] if kind is EntityKind.RUO else CORE_PREFIXES["unit"]
    tag = _KIND_TAGS[kind]
    namespace = f"{package}.{module}" if package else module
    segments = ".".join((namespace, *owner_path, identifier))
    return f"{prefix}{tag}:{segments}"


_CANONICAL_ID_PATTERN = re.compile(
    r"^(?P<prefix>ruo:(?:unit|object)):(?P<tag>ru|rus|ruo|derive):(?P<path>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)$"
)


def parse_canonical_entity_id(value: str) -> dict[str, object]:
    """Parse a Canonical Entity ID back into its structural components.

    Returns ``{"kind": EntityKind, "tag": str, "path": tuple[str, ...]}``.
    Raises :class:`CanonicalIdError` if ``value`` is not well-formed, or if
    the prefix/tag combination is inconsistent (an RUO tag must use the
    ``ruo:object:`` prefix; RU/RUS/DERIVE must use ``ruo:unit:``).
    """
    match = _CANONICAL_ID_PATTERN.match(value)
    if not match:
        raise CanonicalIdError(f"RE-ID-002 malformed canonical entity id: {value!r}")
    prefix, tag, path = match.group("prefix"), match.group("tag"), match.group("path")
    kind = _TAG_KINDS[tag]
    expected_prefix = "ruo:object" if kind is EntityKind.RUO else "ruo:unit"
    if prefix != expected_prefix:
        raise CanonicalIdError(
            f"RE-ID-002 kind/prefix mismatch in canonical entity id: {value!r}"
        )
    return {"kind": kind, "tag": tag, "path": tuple(path.split("."))}
