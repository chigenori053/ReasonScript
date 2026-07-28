//! Deterministic semantic-scene projection runtime for ReasonScript.
//!
//! The runtime owns canonical scene construction, validation, scene patches,
//! replayable snapshots, artifact emission, and the SVG reference adapter. It
//! intentionally does not own GPU rendering or visual inference policy.

use reasonscript_vision_runtime::{validate_observation, VisionObservation};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

pub const PROFILE: &str = "reasonscript-semantic-visualization-runtime/0.1";
pub const INPUT_PROFILE: &str = "reasonscript-semantic-visualization-input/0.1";
pub const SCENE_PROFILE: &str = "reasonscript-semantic-visualization-ir/0.1";

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct Diagnostic {
    pub code: String,
    pub severity: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VisualizationError {
    pub diagnostic: Diagnostic,
}

impl VisualizationError {
    pub fn new(code: &str, message: impl Into<String>, location: impl Into<String>) -> Self {
        Self {
            diagnostic: Diagnostic {
                code: code.into(),
                severity: "error".into(),
                message: message.into(),
                location: Some(location.into()),
            },
        }
    }
}

impl std::fmt::Display for VisualizationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.diagnostic.code, self.diagnostic.message)
    }
}
impl std::error::Error for VisualizationError {}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SceneInput {
    pub schema_version: String,
    pub scene_id: String,
    pub source_ref: String,
    #[serde(default = "default_width")]
    pub width: f64,
    #[serde(default = "default_height")]
    pub height: f64,
    #[serde(default)]
    pub objects: Vec<InputObject>,
    #[serde(default)]
    pub relations: Vec<InputRelation>,
}
fn default_width() -> f64 {
    960.0
}
fn default_height() -> f64 {
    540.0
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct InputObject {
    pub object_id: String,
    pub label: String,
    pub bounding_box: [f64; 4],
    #[serde(default = "observed")]
    pub epistemic_state: String,
    #[serde(default = "one")]
    pub confidence: f64,
    #[serde(default)]
    pub evidence_refs: Vec<String>,
    #[serde(default = "geometry_layer")]
    pub layer: String,
}
fn observed() -> String {
    "observed".into()
}
fn one() -> f64 {
    1.0
}
fn geometry_layer() -> String {
    "geometry".into()
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct InputRelation {
    pub relation_id: String,
    pub source_object_id: String,
    pub target_object_id: String,
    pub relation_kind: String,
    #[serde(default = "one")]
    pub confidence: f64,
    #[serde(default)]
    pub evidence_refs: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VisualizationScene {
    pub schema_version: String,
    pub scene_id: String,
    pub revision: u64,
    pub source: SourceDescriptor,
    pub viewport: Viewport,
    pub coordinate_system: CoordinateSystem,
    pub layers: Vec<VisualizationLayer>,
    pub objects: Vec<VisualizationObject>,
    pub relations: Vec<VisualizationRelation>,
    pub camera: VisualizationCamera,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct SourceDescriptor {
    pub source_profile: String,
    pub source_ref: String,
    pub source_digest: String,
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct Viewport {
    pub width: f64,
    pub height: f64,
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct CoordinateSystem {
    pub handedness: String,
    pub up_axis: String,
    pub units: String,
    pub origin: [f64; 3],
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VisualizationLayer {
    pub layer_id: String,
    pub role: String,
    pub order: u32,
    pub visible: bool,
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VisualizationCamera {
    pub camera_id: String,
    pub projection: String,
    pub viewport: Viewport,
    pub selected: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VisualizationObject {
    pub object_id: String,
    pub source_ref: String,
    pub label: String,
    pub layer_id: String,
    pub geometry: BoundingBox2,
    pub epistemic_state: String,
    pub validity_state: String,
    pub interaction_state: String,
    pub confidence: f64,
    pub evidence_refs: Vec<String>,
    pub revision: u64,
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct BoundingBox2 {
    pub primitive: String,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VisualizationRelation {
    pub relation_id: String,
    pub source_object_id: String,
    pub target_object_id: String,
    pub relation_kind: String,
    pub confidence: f64,
    pub evidence_refs: Vec<String>,
    pub revision: u64,
}

pub fn project_input(input: &SceneInput) -> Result<VisualizationScene, VisualizationError> {
    if input.schema_version != INPUT_PROFILE {
        return Err(VisualizationError::new(
            "SVR-SRC-001",
            "unsupported semantic visualization input schema",
            "schema_version",
        ));
    }
    if input.scene_id.trim().is_empty() || input.source_ref.trim().is_empty() {
        return Err(VisualizationError::new(
            "SVR-ID-001",
            "scene_id and source_ref are required",
            "scene",
        ));
    }
    let mut objects: Vec<_> = input
        .objects
        .iter()
        .map(|object| VisualizationObject {
            object_id: object.object_id.clone(),
            source_ref: format!("{}/{}", input.source_ref, object.object_id),
            label: object.label.clone(),
            layer_id: object.layer.clone(),
            geometry: BoundingBox2 {
                primitive: "bounding_box_2d".into(),
                x: object.bounding_box[0],
                y: object.bounding_box[1],
                width: object.bounding_box[2],
                height: object.bounding_box[3],
            },
            epistemic_state: object.epistemic_state.clone(),
            validity_state: "valid".into(),
            interaction_state: "normal".into(),
            confidence: object.confidence,
            evidence_refs: sorted(object.evidence_refs.clone()),
            revision: 0,
        })
        .collect();
    objects.sort_by(|a, b| a.object_id.cmp(&b.object_id));
    let mut relations: Vec<_> = input
        .relations
        .iter()
        .map(|relation| VisualizationRelation {
            relation_id: relation.relation_id.clone(),
            source_object_id: relation.source_object_id.clone(),
            target_object_id: relation.target_object_id.clone(),
            relation_kind: relation.relation_kind.clone(),
            confidence: relation.confidence,
            evidence_refs: sorted(relation.evidence_refs.clone()),
            revision: 0,
        })
        .collect();
    relations.sort_by(|a, b| a.relation_id.cmp(&b.relation_id));
    let mut layers = standard_layers();
    for object in &objects {
        if !layers.iter().any(|layer| layer.layer_id == object.layer_id) {
            layers.push(VisualizationLayer {
                layer_id: object.layer_id.clone(),
                role: object.layer_id.clone(),
                order: 1000,
                visible: true,
            });
        }
    }
    layers.sort_by(|a, b| (a.order, &a.layer_id).cmp(&(b.order, &b.layer_id)));
    let scene = VisualizationScene {
        schema_version: SCENE_PROFILE.into(),
        scene_id: input.scene_id.clone(),
        revision: 0,
        source: SourceDescriptor {
            source_profile: INPUT_PROFILE.into(),
            source_ref: input.source_ref.clone(),
            source_digest: checksum(input)?,
        },
        viewport: Viewport {
            width: input.width,
            height: input.height,
        },
        coordinate_system: CoordinateSystem {
            handedness: "right".into(),
            up_axis: "y".into(),
            units: "pixel".into(),
            origin: [0.0, 0.0, 0.0],
        },
        layers,
        objects,
        relations,
        camera: VisualizationCamera {
            camera_id: "camera:orthographic:default".into(),
            projection: "orthographic".into(),
            viewport: Viewport {
                width: input.width,
                height: input.height,
            },
            selected: true,
        },
    };
    validate_scene(&scene).map(|_| scene)
}

pub fn project_vision(
    observation: &VisionObservation,
) -> Result<VisualizationScene, VisualizationError> {
    validate_observation(observation)
        .map_err(|error| VisualizationError::new(&error.code, error.message, error.stage))?;
    let input = SceneInput {
        schema_version: INPUT_PROFILE.into(),
        scene_id: format!("scene:vision:{}", observation.observation_id),
        source_ref: format!("vision:observation:{}", observation.observation_id),
        width: 1.0,
        height: 1.0,
        objects: observation
            .detections
            .iter()
            .map(|detection| InputObject {
                object_id: format!("object:vision:{}", detection.detection_id),
                label: detection.class_label.clone(),
                bounding_box: detection.bounding_box.map(f64::from),
                epistemic_state: "observed".into(),
                confidence: f64::from(detection.confidence),
                evidence_refs: vec![format!("evidence:vision:{}", detection.detection_id)],
                layer: "geometry".into(),
            })
            .collect(),
        relations: observation
            .detections
            .iter()
            .map(|detection| InputRelation {
                relation_id: format!("relation:frame-to-track:{}", detection.detection_id),
                source_object_id: format!("object:vision:{}", detection.detection_id),
                target_object_id: format!("object:vision:{}", detection.detection_id),
                relation_kind: format!("track:{}", detection.track_id),
                confidence: f64::from(detection.confidence),
                evidence_refs: vec![format!("evidence:vision:{}", detection.detection_id)],
            })
            .collect(),
    };
    let mut scene = project_input(&input)?;
    scene.source = SourceDescriptor {
        source_profile: "reasonscript-vision-observation/0.1".into(),
        source_ref: format!("vision:observation:{}", observation.observation_id),
        source_digest: checksum(observation)?,
    };
    Ok(scene)
}

fn standard_layers() -> Vec<VisualizationLayer> {
    [
        "geometry",
        "topology",
        "semantics",
        "relations",
        "evidence",
        "confidence",
        "inference",
        "diagnostics",
        "state_transition",
        "annotation",
    ]
    .iter()
    .enumerate()
    .map(|(order, role)| VisualizationLayer {
        layer_id: (*role).into(),
        role: (*role).into(),
        order: order as u32,
        visible: true,
    })
    .collect()
}

pub fn validate_scene(scene: &VisualizationScene) -> Result<(), VisualizationError> {
    if scene.schema_version != SCENE_PROFILE || scene.scene_id.trim().is_empty() {
        return Err(VisualizationError::new(
            "SVR-SRC-001",
            "invalid scene identity or schema",
            "scene",
        ));
    }
    finite_positive(scene.viewport.width, "viewport.width")?;
    finite_positive(scene.viewport.height, "viewport.height")?;
    let layer_ids: BTreeSet<_> = scene
        .layers
        .iter()
        .map(|layer| layer.layer_id.as_str())
        .collect();
    if layer_ids.len() != scene.layers.len() {
        return Err(VisualizationError::new(
            "SVR-ID-001",
            "duplicate layer id",
            "layers",
        ));
    }
    let object_ids: BTreeSet<_> = scene
        .objects
        .iter()
        .map(|object| object.object_id.as_str())
        .collect();
    if object_ids.len() != scene.objects.len() {
        return Err(VisualizationError::new(
            "SVR-ID-001",
            "duplicate object id",
            "objects",
        ));
    }
    for object in &scene.objects {
        if object.object_id.is_empty()
            || object.label.is_empty()
            || !layer_ids.contains(object.layer_id.as_str())
        {
            return Err(VisualizationError::new(
                "SVR-REF-001",
                "object identity, label, or layer reference is invalid",
                &object.object_id,
            ));
        }
        for value in [
            object.geometry.x,
            object.geometry.y,
            object.geometry.width,
            object.geometry.height,
        ] {
            if !value.is_finite() {
                return Err(VisualizationError::new(
                    "SVR-NUM-001",
                    "geometry values must be finite",
                    &object.object_id,
                ));
            }
        }
        if object.geometry.width < 0.0 || object.geometry.height < 0.0 {
            return Err(VisualizationError::new(
                "SVR-GEO-001",
                "bounding box size must not be negative",
                &object.object_id,
            ));
        }
        unit_interval(object.confidence, &object.object_id)?;
        if !matches!(
            object.epistemic_state.as_str(),
            "observed" | "inferred" | "predicted" | "unknown" | "conflicted"
        ) {
            return Err(VisualizationError::new(
                "SVR-SCN-001",
                "unsupported epistemic state",
                &object.object_id,
            ));
        }
    }
    let relation_ids: BTreeSet<_> = scene
        .relations
        .iter()
        .map(|relation| relation.relation_id.as_str())
        .collect();
    if relation_ids.len() != scene.relations.len() {
        return Err(VisualizationError::new(
            "SVR-ID-001",
            "duplicate relation id",
            "relations",
        ));
    }
    for relation in &scene.relations {
        if !object_ids.contains(relation.source_object_id.as_str())
            || !object_ids.contains(relation.target_object_id.as_str())
        {
            return Err(VisualizationError::new(
                "SVR-REF-001",
                "relation target does not exist",
                &relation.relation_id,
            ));
        }
        unit_interval(relation.confidence, &relation.relation_id)?;
    }
    Ok(())
}
fn finite_positive(value: f64, location: &str) -> Result<(), VisualizationError> {
    if !value.is_finite() || value <= 0.0 {
        Err(VisualizationError::new(
            "SVR-NUM-001",
            "value must be finite and positive",
            location,
        ))
    } else {
        Ok(())
    }
}
fn unit_interval(value: f64, location: &str) -> Result<(), VisualizationError> {
    if !value.is_finite() || !(0.0..=1.0).contains(&value) {
        Err(VisualizationError::new(
            "SVR-NUM-001",
            "confidence must be finite and in [0,1]",
            location,
        ))
    } else {
        Ok(())
    }
}
fn sorted(mut values: Vec<String>) -> Vec<String> {
    values.sort();
    values.dedup();
    values
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
#[serde(tag = "operation", rename_all = "snake_case")]
pub enum PatchOperation {
    AddObject {
        object: VisualizationObject,
    },
    UpdateObject {
        object_id: String,
        expected_revision: u64,
        object: VisualizationObject,
    },
    RemoveObject {
        object_id: String,
        expected_revision: u64,
    },
    AddRelation {
        relation: VisualizationRelation,
    },
    RemoveRelation {
        relation_id: String,
        expected_revision: u64,
    },
}
#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct ScenePatch {
    pub patch_id: String,
    pub scene_id: String,
    pub base_revision: u64,
    pub operations: Vec<PatchOperation>,
}
#[derive(Clone, Debug)]
pub struct PreparedPatch {
    pub patch: ScenePatch,
    pub proposed: VisualizationScene,
}
#[derive(Clone, Debug)]
pub struct SceneKernel {
    current: VisualizationScene,
    snapshots: BTreeMap<u64, VisualizationScene>,
}

impl SceneKernel {
    pub fn new(scene: VisualizationScene) -> Result<Self, VisualizationError> {
        validate_scene(&scene)?;
        let mut snapshots = BTreeMap::new();
        snapshots.insert(scene.revision, scene.clone());
        Ok(Self {
            current: scene,
            snapshots,
        })
    }
    pub fn current(&self) -> &VisualizationScene {
        &self.current
    }
    pub fn prepare(&self, patch: ScenePatch) -> Result<PreparedPatch, VisualizationError> {
        if patch.scene_id != self.current.scene_id || patch.base_revision != self.current.revision {
            return Err(VisualizationError::new(
                "SVR-TXN-001",
                "patch base scene or revision mismatch",
                "patch",
            ));
        }
        let proposed = apply_patch(&self.current, &patch)?;
        Ok(PreparedPatch { patch, proposed })
    }
    pub fn commit(
        &mut self,
        prepared: PreparedPatch,
    ) -> Result<&VisualizationScene, VisualizationError> {
        if prepared.patch.base_revision != self.current.revision {
            return Err(VisualizationError::new(
                "SVR-TXN-001",
                "scene changed after patch preparation",
                "patch",
            ));
        }
        validate_scene(&prepared.proposed)?;
        self.current = prepared.proposed;
        self.snapshots
            .insert(self.current.revision, self.current.clone());
        Ok(&self.current)
    }
    pub fn snapshot(&self, revision: u64) -> Option<&VisualizationScene> {
        self.snapshots.get(&revision)
    }
    pub fn rollback(&mut self, revision: u64) -> Result<&VisualizationScene, VisualizationError> {
        let prior = self.snapshots.get(&revision).cloned().ok_or_else(|| {
            VisualizationError::new("SVR-TXN-001", "snapshot does not exist", "revision")
        })?;
        let mut restored = prior;
        restored.revision = self.current.revision + 1;
        self.current = restored;
        self.snapshots
            .insert(self.current.revision, self.current.clone());
        Ok(&self.current)
    }
}

pub fn apply_patch(
    scene: &VisualizationScene,
    patch: &ScenePatch,
) -> Result<VisualizationScene, VisualizationError> {
    if patch.patch_id.trim().is_empty() || patch.operations.len() > 10_000 {
        return Err(VisualizationError::new(
            "SVR-RES-001",
            "invalid patch identity or operation budget",
            "patch",
        ));
    }
    let mut next = scene.clone();
    for operation in &patch.operations {
        match operation {
            PatchOperation::AddObject { object } => {
                if next
                    .objects
                    .iter()
                    .any(|item| item.object_id == object.object_id)
                {
                    return Err(VisualizationError::new(
                        "SVR-ID-001",
                        "object already exists",
                        &object.object_id,
                    ));
                }
                next.objects.push(object.clone());
            }
            PatchOperation::UpdateObject {
                object_id,
                expected_revision,
                object,
            } => {
                let target = next
                    .objects
                    .iter_mut()
                    .find(|item| item.object_id == *object_id)
                    .ok_or_else(|| {
                        VisualizationError::new("SVR-REF-001", "object does not exist", object_id)
                    })?;
                if target.revision != *expected_revision || object.object_id != *object_id {
                    return Err(VisualizationError::new(
                        "SVR-PAT-001",
                        "object revision or identity mismatch",
                        object_id,
                    ));
                }
                let mut replacement = object.clone();
                replacement.revision += 1;
                *target = replacement;
            }
            PatchOperation::RemoveObject {
                object_id,
                expected_revision,
            } => {
                let target = next
                    .objects
                    .iter()
                    .find(|item| item.object_id == *object_id)
                    .ok_or_else(|| {
                        VisualizationError::new("SVR-REF-001", "object does not exist", object_id)
                    })?;
                if target.revision != *expected_revision
                    || next.relations.iter().any(|relation| {
                        relation.source_object_id == *object_id
                            || relation.target_object_id == *object_id
                    })
                {
                    return Err(VisualizationError::new(
                        "SVR-PAT-001",
                        "object revision mismatch or relations still reference object",
                        object_id,
                    ));
                }
                next.objects.retain(|item| item.object_id != *object_id);
            }
            PatchOperation::AddRelation { relation } => {
                if next
                    .relations
                    .iter()
                    .any(|item| item.relation_id == relation.relation_id)
                {
                    return Err(VisualizationError::new(
                        "SVR-ID-001",
                        "relation already exists",
                        &relation.relation_id,
                    ));
                }
                next.relations.push(relation.clone());
            }
            PatchOperation::RemoveRelation {
                relation_id,
                expected_revision,
            } => {
                let target = next
                    .relations
                    .iter()
                    .find(|item| item.relation_id == *relation_id)
                    .ok_or_else(|| {
                        VisualizationError::new(
                            "SVR-REF-001",
                            "relation does not exist",
                            relation_id,
                        )
                    })?;
                if target.revision != *expected_revision {
                    return Err(VisualizationError::new(
                        "SVR-PAT-001",
                        "relation revision mismatch",
                        relation_id,
                    ));
                }
                next.relations
                    .retain(|item| item.relation_id != *relation_id);
            }
        }
    }
    next.objects.sort_by(|a, b| a.object_id.cmp(&b.object_id));
    next.relations
        .sort_by(|a, b| a.relation_id.cmp(&b.relation_id));
    next.revision += 1;
    Ok(next)
}

pub fn diff(
    before: &VisualizationScene,
    after: &VisualizationScene,
) -> Result<ScenePatch, VisualizationError> {
    if before.scene_id != after.scene_id {
        return Err(VisualizationError::new(
            "SVR-PAT-001",
            "cannot diff different scenes",
            "scene_id",
        ));
    }
    let old: BTreeMap<_, _> = before
        .objects
        .iter()
        .map(|object| (object.object_id.clone(), object))
        .collect();
    let new: BTreeMap<_, _> = after
        .objects
        .iter()
        .map(|object| (object.object_id.clone(), object))
        .collect();
    let mut operations = Vec::new();
    for (id, object) in &new {
        match old.get(id) {
            None => operations.push(PatchOperation::AddObject {
                object: (*object).clone(),
            }),
            Some(previous) if *previous != *object => {
                operations.push(PatchOperation::UpdateObject {
                    object_id: id.clone(),
                    expected_revision: previous.revision,
                    object: (*object).clone(),
                })
            }
            _ => {}
        }
    }
    for (id, object) in &old {
        if !new.contains_key(id) {
            operations.push(PatchOperation::RemoveObject {
                object_id: id.clone(),
                expected_revision: object.revision,
            });
        }
    }
    Ok(ScenePatch {
        patch_id: stable_id(
            "patch",
            &json!({"before": before.revision, "after": after.revision, "operations": operations}),
        ),
        scene_id: before.scene_id.clone(),
        base_revision: before.revision,
        operations,
    })
}

pub fn render_svg(scene: &VisualizationScene) -> Result<String, VisualizationError> {
    validate_scene(scene)?;
    let mut svg = format!("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{}\" height=\"{}\" viewBox=\"0 0 {} {}\">\n", number(scene.viewport.width), number(scene.viewport.height), number(scene.viewport.width), number(scene.viewport.height));
    svg.push_str("<g id=\"geometry\">\n");
    for object in &scene.objects {
        let style = style_for(&object.epistemic_state);
        let box2 = &object.geometry;
        svg.push_str(&format!("<rect data-evidence=\"{}\" data-source-ref=\"{}\" fill=\"none\" height=\"{}\" id=\"{}\" stroke=\"{}\" stroke-dasharray=\"{}\" stroke-width=\"2\" width=\"{}\" x=\"{}\" y=\"{}\"/>\n", escape(&object.evidence_refs.join(",")), escape(&object.source_ref), number(box2.height), escape(&object.object_id), style.0, style.1, number(box2.width), number(box2.x), number(box2.y)));
        svg.push_str(&format!("<text data-object-id=\"{}\" fill=\"{}\" font-family=\"sans-serif\" font-size=\"12\" x=\"{}\" y=\"{}\">{} ({})</text>\n", escape(&object.object_id), style.0, number(box2.x), number(box2.y - 4.0), escape(&object.label), number(object.confidence)));
    }
    svg.push_str("</g>\n<g id=\"relations\">\n");
    let by_id: BTreeMap<_, _> = scene
        .objects
        .iter()
        .map(|object| (object.object_id.as_str(), object))
        .collect();
    for relation in &scene.relations {
        let source = by_id[relation.source_object_id.as_str()];
        let target = by_id[relation.target_object_id.as_str()];
        let (sx, sy) = center(&source.geometry);
        let (tx, ty) = center(&target.geometry);
        svg.push_str(&format!("<line data-relation-kind=\"{}\" id=\"{}\" stroke=\"#555555\" stroke-width=\"1\" x1=\"{}\" x2=\"{}\" y1=\"{}\" y2=\"{}\"/>\n", escape(&relation.relation_kind), escape(&relation.relation_id), number(sx), number(tx), number(sy), number(ty)));
    }
    svg.push_str("</g>\n</svg>\n");
    Ok(svg)
}
fn style_for(state: &str) -> (&'static str, &'static str) {
    match state {
        "inferred" => ("#2563eb", "6 3"),
        "unknown" => ("#6b7280", "2 4"),
        "conflicted" => ("#dc2626", "4 2"),
        "predicted" => ("#7c3aed", "4 2"),
        _ => ("#15803d", "none"),
    }
}
fn center(box2: &BoundingBox2) -> (f64, f64) {
    (box2.x + box2.width / 2.0, box2.y + box2.height / 2.0)
}
fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
fn number(value: f64) -> String {
    let value = if value == 0.0 { 0.0 } else { value };
    format!("{value:.6}")
        .trim_end_matches('0')
        .trim_end_matches('.')
        .to_owned()
}

pub fn write_artifacts(
    output: &Path,
    source: &Value,
    scene: &VisualizationScene,
) -> Result<Value, VisualizationError> {
    validate_scene(scene)?;
    fs::create_dir_all(output).map_err(|error| {
        VisualizationError::new(
            "SVR-ART-001",
            error.to_string(),
            output.display().to_string(),
        )
    })?;
    let documents: BTreeMap<String, Value> = BTreeMap::from([
        ("visualization_source.json".into(), source.clone()),
        (
            "visualization_scene.json".into(),
            serde_json::to_value(scene).unwrap(),
        ),
        (
            "visualization_render_plan.json".into(),
            json!({"schema_version":"reasonscript-semantic-visualization-render-plan/0.1","scene_id":scene.scene_id,"steps":["validate_source","project_scene","validate_scene","canonicalize","render_svg","emit_artifacts"]}),
        ),
        (
            "visualization_evidence.json".into(),
            json!({"schema_version":"reasonscript-semantic-visualization-evidence/0.1","scene_id":scene.scene_id,"objects":scene.objects.iter().map(|object| json!({"object_id":object.object_id,"evidence_refs":object.evidence_refs,"confidence":object.confidence})).collect::<Vec<_>>() }),
        ),
        (
            "visualization_trace.json".into(),
            json!({"schema_version":"reasonscript-semantic-visualization-trace/0.1","scene_id":scene.scene_id,"events":[{"ordinal":0,"operation":"project","revision":scene.revision},{"ordinal":1,"operation":"validate","revision":scene.revision}]}),
        ),
        (
            "visualization_validation.json".into(),
            json!({"schema_version":"reasonscript-semantic-visualization-validation/0.1","status":"pass","diagnostics":[]}),
        ),
        (
            "visualization_run_summary.json".into(),
            json!({"schema_version":"reasonscript-semantic-visualization-run-summary/0.1","status":"pass","scene_id":scene.scene_id,"object_count":scene.objects.len(),"relation_count":scene.relations.len(),"revision":scene.revision}),
        ),
    ]);
    let mut entries = Vec::new();
    for (name, value) in &documents {
        let payload = pretty_json(value)?;
        fs::write(output.join(name), &payload)
            .map_err(|error| VisualizationError::new("SVR-ART-001", error.to_string(), name))?;
        entries.push(json!({"path":name,"media_type":"application/json","required":true,"bytes":payload.len(),"sha256":digest_bytes(payload.as_bytes())}));
    }
    let svg = render_svg(scene)?;
    fs::write(output.join("scene.svg"), &svg)
        .map_err(|error| VisualizationError::new("SVR-ART-001", error.to_string(), "scene.svg"))?;
    entries.push(json!({"path":"scene.svg","media_type":"image/svg+xml","required":true,"bytes":svg.len(),"sha256":digest_bytes(svg.as_bytes())}));
    let manifest = json!({"schema_version":"reasonscript-semantic-visualization-manifest/0.1","profile":PROFILE,"scene_id":scene.scene_id,"artifacts":entries});
    let manifest_payload = pretty_json(&manifest)?;
    fs::write(
        output.join("visualization_manifest.json"),
        &manifest_payload,
    )
    .map_err(|error| {
        VisualizationError::new(
            "SVR-ART-001",
            error.to_string(),
            "visualization_manifest.json",
        )
    })?;
    Ok(manifest)
}

pub fn canonical_json<T: Serialize>(value: &T) -> Result<String, VisualizationError> {
    serde_json::to_value(value)
        .map_err(|error| VisualizationError::new("SVR-DET-001", error.to_string(), "serialization"))
        .and_then(|value| pretty_json(&value))
}
fn pretty_json(value: &Value) -> Result<String, VisualizationError> {
    serde_json::to_string_pretty(&canonical_value(value))
        .map(|text| text + "\n")
        .map_err(|error| VisualizationError::new("SVR-DET-001", error.to_string(), "serialization"))
}
fn canonical_value(value: &Value) -> Value {
    match value {
        Value::Object(object) => {
            let mut out = serde_json::Map::new();
            for (key, value) in object {
                out.insert(key.clone(), canonical_value(value));
            }
            Value::Object(out)
        }
        Value::Array(items) => Value::Array(items.iter().map(canonical_value).collect()),
        _ => value.clone(),
    }
}
fn checksum<T: Serialize>(value: &T) -> Result<String, VisualizationError> {
    Ok(digest_bytes(canonical_json(value)?.as_bytes()))
}
fn digest_bytes(bytes: &[u8]) -> String {
    format!("sha256:{:x}", Sha256::digest(bytes))
}
fn stable_id(prefix: &str, value: &Value) -> String {
    format!(
        "{prefix}:{}",
        &digest_bytes(pretty_json(value).unwrap().as_bytes())[7..23]
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    fn input() -> SceneInput {
        SceneInput {
            schema_version: INPUT_PROFILE.into(),
            scene_id: "scene:test".into(),
            source_ref: "fixture:test".into(),
            width: 100.0,
            height: 80.0,
            objects: vec![InputObject {
                object_id: "torso".into(),
                label: "Torso".into(),
                bounding_box: [20.0, 10.0, 30.0, 40.0],
                epistemic_state: "observed".into(),
                confidence: 0.9,
                evidence_refs: vec!["e1".into()],
                layer: "geometry".into(),
            }],
            relations: vec![],
        }
    }
    #[test]
    fn projection_and_svg_are_deterministic() {
        let scene = project_input(&input()).unwrap();
        assert_eq!(
            canonical_json(&scene).unwrap(),
            canonical_json(&project_input(&input()).unwrap()).unwrap()
        );
        assert!(render_svg(&scene).unwrap().contains("Torso"));
    }
    #[test]
    fn invalid_geometry_is_rejected() {
        let mut value = input();
        value.objects[0].bounding_box[2] = -1.0;
        assert_eq!(
            project_input(&value).unwrap_err().diagnostic.code,
            "SVR-GEO-001"
        );
    }
    #[test]
    fn transaction_is_atomic_and_replayable() {
        let scene = project_input(&input()).unwrap();
        let mut kernel = SceneKernel::new(scene).unwrap();
        let mut changed = kernel.current().objects[0].clone();
        changed.label = "Changed".into();
        let patch = ScenePatch {
            patch_id: "patch:test".into(),
            scene_id: "scene:test".into(),
            base_revision: 0,
            operations: vec![PatchOperation::UpdateObject {
                object_id: "torso".into(),
                expected_revision: 0,
                object: changed,
            }],
        };
        kernel.commit(kernel.prepare(patch).unwrap()).unwrap();
        assert_eq!(kernel.current().revision, 1);
        kernel.rollback(0).unwrap();
        assert_eq!(kernel.current().revision, 2);
        assert_eq!(kernel.current().objects[0].label, "Torso");
    }
}
