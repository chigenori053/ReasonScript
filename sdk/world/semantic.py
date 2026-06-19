"""world.semantic - World Model SDK Phase 3 semantic reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .builder import Relation, Scene, World, WorldObject, add_scene, create_object, replace_scene


@dataclass(frozen=True)
class SceneTemplate:
    id: str
    required_objects: tuple[str, ...] = field(default_factory=tuple)
    optional_objects: tuple[str, ...] = field(default_factory=tuple)
    required_relations: tuple[dict[str, str], ...] = field(default_factory=tuple)
    optional_relations: tuple[dict[str, str], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "required_objects": list(self.required_objects),
            "optional_objects": list(self.optional_objects),
            "required_relations": [dict(relation) for relation in self.required_relations],
            "optional_relations": [dict(relation) for relation in self.optional_relations],
        }


@dataclass(frozen=True)
class ReconstructionTrace:
    template: str | None
    inferred_objects: tuple[str, ...] = field(default_factory=tuple)
    inferred_relations: tuple[dict[str, str], ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template": self.template,
            "inferred_objects": list(self.inferred_objects),
            "inferred_relations": [dict(relation) for relation in self.inferred_relations],
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class ReconstructionResult:
    scene: Scene | None = None
    world: World | None = None
    trace: ReconstructionTrace = field(default_factory=lambda: ReconstructionTrace(None))
    template: SceneTemplate | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene": self.scene.to_dict() if self.scene is not None else None,
            "world": self.world.to_dict() if self.world is not None else None,
            "trace": self.trace.to_dict(),
            "template": self.template.to_dict() if self.template is not None else None,
        }


_TEMPLATES: tuple[SceneTemplate, ...] = (
    SceneTemplate(
        id="DiningRoom",
        required_objects=("Table", "Chair"),
        optional_objects=("Lamp",),
        required_relations=({"source": "Chair", "target": "Table", "relation_type": "near"},),
        optional_relations=({"source": "Lamp", "target": "Table", "relation_type": "above"},),
    ),
    SceneTemplate(
        id="Bedroom",
        required_objects=("Bed",),
        optional_objects=("Lamp", "Table"),
        required_relations=(),
        optional_relations=({"source": "Lamp", "target": "Bed", "relation_type": "near"},),
    ),
    SceneTemplate(
        id="Office",
        required_objects=("Desk", "Chair"),
        optional_objects=("Computer",),
        required_relations=({"source": "Chair", "target": "Desk", "relation_type": "near"},),
        optional_relations=({"source": "Computer", "target": "Desk", "relation_type": "above"},),
    ),
    SceneTemplate(
        id="Kitchen",
        required_objects=("Table",),
        optional_objects=("Chair",),
        required_relations=(),
        optional_relations=(),
    ),
    SceneTemplate(
        id="Classroom",
        required_objects=("Desk", "Chair"),
        optional_objects=("Board",),
        required_relations=({"source": "Chair", "target": "Desk", "relation_type": "near"},),
        optional_relations=(),
    ),
)


def create_template(
    template_id: str,
    *,
    required_objects: tuple[str, ...] = (),
    optional_objects: tuple[str, ...] = (),
    required_relations: tuple[dict[str, str], ...] = (),
    optional_relations: tuple[dict[str, str], ...] = (),
) -> SceneTemplate:
    return SceneTemplate(
        id=template_id,
        required_objects=tuple(required_objects),
        optional_objects=tuple(optional_objects),
        required_relations=tuple(dict(relation) for relation in required_relations),
        optional_relations=tuple(dict(relation) for relation in optional_relations),
    )


def register_template(template: SceneTemplate, registry: tuple[SceneTemplate, ...] | None = None) -> tuple[SceneTemplate, ...]:
    current = templates() if registry is None else tuple(registry)
    filtered = tuple(existing for existing in current if existing.id != template.id)
    return tuple(sorted(filtered + (template,), key=lambda t: t.id))


def templates(registry: tuple[SceneTemplate, ...] | None = None) -> tuple[SceneTemplate, ...]:
    return _TEMPLATES if registry is None else tuple(registry)


def validate_template(template: SceneTemplate | dict[str, Any]) -> bool:
    data = template.to_dict() if isinstance(template, SceneTemplate) else template
    if not data.get("id"):
        return False
    for key in ("required_objects", "optional_objects", "required_relations", "optional_relations"):
        if key not in data:
            return False
    return True


def match_template(scene: Scene, registry: tuple[SceneTemplate, ...] | None = None) -> SceneTemplate | None:
    object_kinds = _object_kinds(scene)
    ranked = []
    for index, template in enumerate(templates(registry)):
        required = set(template.required_objects)
        optional = set(template.optional_objects)
        overlap = len(object_kinds & (required | optional))
        missing_required = len(required - object_kinds)
        specificity = len(required) + len(optional) + len(template.required_relations) + len(template.optional_relations)
        score = (overlap * 100) + (specificity * 10) - missing_required
        ranked.append((score, -missing_required, index, template))
    ranked.sort(key=lambda item: (-item[0], item[2]))
    return ranked[0][3] if ranked and ranked[0][0] > 0 else None


def infer_objects(scene: Scene, template: SceneTemplate | None = None) -> tuple[WorldObject, ...]:
    selected = template or match_template(scene)
    if selected is None:
        return ()
    existing = _object_kinds(scene)
    inferred = []
    for kind in selected.required_objects:
        if kind not in existing:
            inferred.append(create_object(_object_id(kind), kind=kind))
    return tuple(inferred)


def infer_relations(scene: Scene, template: SceneTemplate | None = None) -> tuple[Relation, ...]:
    selected = template or match_template(scene)
    if selected is None:
        return ()
    kinds_to_ids = _kind_to_id(scene)
    inferred_objects_by_kind = {obj.kind: obj.id for obj in infer_objects(scene, selected)}
    kinds_to_ids.update(inferred_objects_by_kind)
    existing = {(rel.source, rel.target, rel.relation_type) for rel in scene.relations}
    relations = []
    for relation in selected.required_relations:
        source = kinds_to_ids.get(relation["source"])
        target = kinds_to_ids.get(relation["target"])
        relation_type = relation["relation_type"]
        if source and target and (source, target, relation_type) not in existing:
            relations.append(
                Relation(
                    id=f"inferred-{source}-{relation_type}-{target}",
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    metadata={"inferred": True, "template": selected.id},
                )
            )
    return tuple(sorted(relations, key=lambda rel: rel.id))


def recover_structure(scene: Scene, registry: tuple[SceneTemplate, ...] | None = None) -> ReconstructionResult:
    return reconstruct_scene(scene, registry=registry)


def reconstruct_scene(scene: Scene, registry: tuple[SceneTemplate, ...] | None = None) -> ReconstructionResult:
    selected = match_template(scene, registry)
    inferred_objects = infer_objects(scene, selected)
    next_scene = scene
    for obj in inferred_objects:
        next_scene = Scene(
            id=next_scene.id,
            entities=next_scene.entities,
            objects=next_scene.objects + (obj,),
            relations=next_scene.relations,
            events=next_scene.events,
        )
    inferred_relations = infer_relations(next_scene, selected)
    next_scene = Scene(
        id=next_scene.id,
        entities=next_scene.entities,
        objects=next_scene.objects,
        relations=tuple(sorted(next_scene.relations + inferred_relations, key=lambda rel: rel.id)),
        events=next_scene.events,
    )
    trace = ReconstructionTrace(
        template=selected.id if selected is not None else None,
        inferred_objects=tuple(obj.kind for obj in inferred_objects),
        inferred_relations=tuple(
            {"source": rel.source, "target": rel.target, "relation_type": rel.relation_type}
            for rel in inferred_relations
        ),
        evidence=_build_evidence(selected, inferred_objects, inferred_relations),
    )
    return ReconstructionResult(scene=next_scene, trace=trace, template=selected)


def reconstruct_world(world: World, registry: tuple[SceneTemplate, ...] | None = None) -> ReconstructionResult:
    next_world = world
    traces = []
    selected_template: SceneTemplate | None = None
    for scene in world.scenes:
        result = reconstruct_scene(scene, registry=registry)
        if result.scene is not None:
            next_world = replace_scene(next_world, result.scene)
        traces.append(result.trace)
        selected_template = selected_template or result.template
    trace = _merge_traces(traces)
    return ReconstructionResult(world=next_world, trace=trace, template=selected_template)


def validate_semantic_consistency(scene: Scene, template: SceneTemplate | None = None) -> bool:
    selected = template or match_template(scene)
    if selected is None:
        return True
    object_kinds = _object_kinds(scene)
    if not set(selected.required_objects).issubset(object_kinds):
        return False
    relation_keys = {
        (_kind_for_id(scene, rel.source), _kind_for_id(scene, rel.target), rel.relation_type)
        for rel in scene.relations
    }
    for relation in selected.required_relations:
        key = (relation["source"], relation["target"], relation["relation_type"])
        if key not in relation_keys:
            return False
    return True


def validate_reconstruction(result: ReconstructionResult) -> bool:
    if result.scene is None and result.world is None:
        return False
    if result.trace.template is None:
        return True
    if result.scene is not None:
        return validate_semantic_consistency(result.scene, result.template)
    return all(validate_semantic_consistency(scene) for scene in result.world.scenes)


def reconstruction_trace(result: ReconstructionResult) -> ReconstructionTrace:
    return result.trace


def evidence(result: ReconstructionResult) -> tuple[str, ...]:
    return result.trace.evidence


def matched_template(result: ReconstructionResult) -> str | None:
    return result.trace.template


def inferred_objects(result: ReconstructionResult) -> tuple[str, ...]:
    return result.trace.inferred_objects


def inferred_relations(result: ReconstructionResult) -> tuple[dict[str, str], ...]:
    return result.trace.inferred_relations


def scene_reconstruction_payload(result: ReconstructionResult) -> dict[str, Any]:
    return {
        "trace": result.trace.to_dict(),
        "template": result.template.to_dict() if result.template is not None else None,
    }


def _merge_traces(traces: list[ReconstructionTrace]) -> ReconstructionTrace:
    templates_seen = tuple(trace.template for trace in traces if trace.template is not None)
    return ReconstructionTrace(
        template=templates_seen[0] if templates_seen else None,
        inferred_objects=tuple(item for trace in traces for item in trace.inferred_objects),
        inferred_relations=tuple(item for trace in traces for item in trace.inferred_relations),
        evidence=tuple(item for trace in traces for item in trace.evidence),
    )


def _build_evidence(
    template: SceneTemplate | None,
    inferred_objects: tuple[WorldObject, ...],
    inferred_relations: tuple[Relation, ...],
) -> tuple[str, ...]:
    if template is None:
        return ()
    evidence = [f"{template.id} Template matched"]
    evidence.extend(f"{template.id} requires {obj.kind}; {obj.kind} inferred" for obj in inferred_objects)
    evidence.extend(
        f"{template.id} requires {rel.source} {rel.relation_type} {rel.target}; relation inferred"
        for rel in inferred_relations
    )
    return tuple(evidence)


def _object_kinds(scene: Scene) -> set[str]:
    return {obj.kind for obj in scene.objects}


def _kind_to_id(scene: Scene) -> dict[str, str]:
    return {obj.kind: obj.id for obj in scene.objects}


def _kind_for_id(scene: Scene, item_id: str) -> str:
    for obj in scene.objects:
        if obj.id == item_id:
            return obj.kind
    for entity in scene.entities:
        if entity.id == item_id:
            return entity.kind
    return item_id


def _object_id(kind: str) -> str:
    return f"inferred-{kind.lower()}"
