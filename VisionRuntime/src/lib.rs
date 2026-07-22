//! Safe-Rust VisionObservation to ReasonUnitObject construction runtime.
//!
//! Model execution is deliberately behind `VisionBackend`. The canonical MVP
//! consumes explicit model observations and never fabricates recognition data.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

pub const PROFILE: &str = "reasonscript-vision-runtime/0.1";
pub const OBSERVATION_PROFILE: &str = "reasonscript-vision-observation/0.1";
pub const TENSOR_PROFILE: &str = "ruo.tensor/1.0";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ImageSource {
    pub image_digest: String,
    pub frame_id: String,
    pub frame_time: f64,
    #[serde(default)]
    pub artifact_ref: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ModelProvenance {
    pub model_id: String,
    pub model_digest: String,
    pub backend: String,
    pub preprocessing_profile: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Detection {
    pub detection_id: String,
    pub track_id: String,
    pub class_label: String,
    pub class_index: u32,
    pub confidence: f32,
    pub bounding_box: [f32; 4],
    pub image_center: [f32; 2],
    #[serde(default)]
    pub embedding: Option<Vec<f32>>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct InputTensor {
    pub shape: Vec<usize>,
    pub values: Vec<f32>,
    #[serde(default = "default_layout")]
    pub layout: String,
}

fn default_layout() -> String {
    "NCHW".to_owned()
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct VisionObservation {
    pub schema_version: String,
    pub observation_id: String,
    pub session_id: String,
    pub source: ImageSource,
    pub model: ModelProvenance,
    pub detections: Vec<Detection>,
    #[serde(default)]
    pub input_tensor: Option<InputTensor>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct VisionModelManifest {
    pub schema_version: String,
    pub model_id: String,
    pub model_digest: String,
    pub backend: String,
    pub preprocessing_profile: String,
    #[serde(default)]
    pub observation_path: Option<String>,
}

/// Boundary implemented by a Burn/ONNX or other Rust inference adapter.
pub trait VisionBackend {
    fn backend_id(&self) -> &str;
    fn infer(&self, image: &[u8], source: ImageSource) -> Result<VisionObservation, VisionError>;
}

/// Dispatch an image through the backend declared by a model manifest.
///
/// v0.1 includes an explicit `observation-json-test` conformance backend. It
/// verifies the real image bytes and imports an authored observation; it never
/// synthesizes detections. Production model engines implement `VisionBackend`.
pub fn infer_from_manifest(
    manifest_path: &Path,
    image_path: &Path,
) -> Result<VisionObservation, VisionError> {
    let manifest: VisionModelManifest =
        serde_json::from_slice(&fs::read(manifest_path).map_err(io_error)?).map_err(json_error)?;
    if manifest.schema_version != "reasonscript-vision-model/0.1"
        || manifest.model_id.trim().is_empty()
        || !digest_like(&manifest.model_digest)
        || manifest.preprocessing_profile.trim().is_empty()
    {
        return Err(VisionError::new(
            "VIS-MOD-001",
            "model",
            "invalid Vision model manifest",
        ));
    }
    if manifest.backend != "observation-json-test" {
        return Err(VisionError::new(
            "VIS-RUN-001",
            "backend",
            format!("Vision backend is not installed: {}", manifest.backend),
        ));
    }
    let relative = manifest.observation_path.as_deref().ok_or_else(|| {
        VisionError::new(
            "VIS-MOD-002",
            "model",
            "test backend requires observation_path",
        )
    })?;
    let observation_path = safe_relative_to(
        manifest_path.parent().unwrap_or_else(|| Path::new(".")),
        relative,
    )?;
    let observation: VisionObservation =
        serde_json::from_slice(&fs::read(observation_path).map_err(io_error)?)
            .map_err(json_error)?;
    validate_observation(&observation)?;
    let image_digest = sha_prefixed(&fs::read(image_path).map_err(io_error)?);
    if observation.source.image_digest != image_digest
        || observation.model.model_id != manifest.model_id
        || observation.model.model_digest != manifest.model_digest
        || observation.model.preprocessing_profile != manifest.preprocessing_profile
        || observation.model.backend != manifest.backend
    {
        return Err(VisionError::new(
            "VIS-RUN-002",
            "provenance",
            "model, image, or preprocessing provenance mismatch",
        ));
    }
    Ok(observation)
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VisionError {
    pub code: String,
    pub stage: String,
    pub message: String,
}

impl VisionError {
    fn new(code: &str, stage: &str, message: impl Into<String>) -> Self {
        Self {
            code: code.to_owned(),
            stage: stage.to_owned(),
            message: message.into(),
        }
    }
}

impl std::fmt::Display for VisionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for VisionError {}

#[derive(Clone, Debug)]
pub struct VisionBundle {
    pub object: Value,
    pub resources: BTreeMap<String, Vec<u8>>,
}

pub fn validate_observation(observation: &VisionObservation) -> Result<(), VisionError> {
    if observation.schema_version != OBSERVATION_PROFILE {
        return Err(VisionError::new(
            "VIS-OBS-001",
            "observation",
            "unsupported observation schema",
        ));
    }
    for (name, value) in [
        ("observation_id", observation.observation_id.as_str()),
        ("session_id", observation.session_id.as_str()),
        ("frame_id", observation.source.frame_id.as_str()),
        ("model_id", observation.model.model_id.as_str()),
    ] {
        if value.trim().is_empty() {
            return Err(VisionError::new(
                "VIS-OBS-002",
                "identity",
                format!("{name} must not be empty"),
            ));
        }
    }
    if !digest_like(&observation.source.image_digest)
        || !digest_like(&observation.model.model_digest)
    {
        return Err(VisionError::new(
            "VIS-OBS-003",
            "provenance",
            "image and model digests must use sha256:<64 hex>",
        ));
    }
    if !observation.source.frame_time.is_finite() {
        return Err(VisionError::new(
            "VIS-OBS-004",
            "numeric",
            "frame time must be finite",
        ));
    }
    let mut ids = BTreeSet::new();
    for detection in &observation.detections {
        if detection.detection_id.is_empty()
            || detection.track_id.is_empty()
            || detection.class_label.is_empty()
        {
            return Err(VisionError::new(
                "VIS-DET-001",
                "detection",
                "detection, track, and class identities are required",
            ));
        }
        if !ids.insert(detection.detection_id.as_str()) {
            return Err(VisionError::new(
                "VIS-DET-002",
                "identity",
                "duplicate detection identity",
            ));
        }
        if !(0.0..=1.0).contains(&detection.confidence) || !detection.confidence.is_finite() {
            return Err(VisionError::new(
                "VIS-DET-003",
                "confidence",
                "confidence must be finite and in [0,1]",
            ));
        }
        if detection
            .bounding_box
            .iter()
            .chain(detection.image_center.iter())
            .any(|v| !v.is_finite())
        {
            return Err(VisionError::new(
                "VIS-DET-004",
                "numeric",
                "detection coordinates must be finite",
            ));
        }
        if detection.bounding_box[2] < 0.0 || detection.bounding_box[3] < 0.0 {
            return Err(VisionError::new(
                "VIS-DET-005",
                "geometry",
                "bounding-box width and height must be non-negative",
            ));
        }
        if detection
            .embedding
            .as_ref()
            .is_some_and(|values| values.iter().any(|v| !v.is_finite()))
        {
            return Err(VisionError::new(
                "VIS-DET-006",
                "embedding",
                "embedding values must be finite",
            ));
        }
    }
    if let Some(input) = &observation.input_tensor {
        let count = checked_product(&input.shape)?;
        if count != input.values.len() || input.values.iter().any(|value| !value.is_finite()) {
            return Err(VisionError::new(
                "VIS-TEN-001",
                "tensor",
                "input tensor shape/value count mismatch or non-finite value",
            ));
        }
    }
    let embedding_sizes: BTreeSet<usize> = observation
        .detections
        .iter()
        .filter_map(|d| d.embedding.as_ref().map(Vec::len))
        .collect();
    if embedding_sizes.len() > 1
        || (!embedding_sizes.is_empty()
            && observation.detections.iter().any(|d| d.embedding.is_none()))
    {
        return Err(VisionError::new(
            "VIS-TEN-002",
            "embedding",
            "embeddings must be present for every detection with one common width",
        ));
    }
    Ok(())
}

pub fn build_ruo(observation: &VisionObservation) -> Result<VisionBundle, VisionError> {
    validate_observation(observation)?;
    let session_key = stable_key(&observation.session_id);
    let object_id = format!("ruo:object:vision-session:{session_key}");
    let revision_id = "ruo:revision:0";
    let root_id = format!("ruo:unit:vision-session:{session_key}");
    let frame_key = stable_key(&observation.source.frame_id);
    let frame_id = format!("ruo:unit:vision-frame:{frame_key}");
    let base = |entity_kind: &str| {
        json!({
            "entity_kind": entity_kind,
            "schema_version": "1.0",
            "created_revision": revision_id,
            "last_modified_revision": revision_id,
            "lifecycle_state": "active",
            "extensions": {}
        })
    };

    let mut detections = observation.detections.clone();
    detections.sort_by(|a, b| {
        let a_id = format!("ruo:unit:vision-track:{}", stable_key(&a.track_id));
        let b_id = format!("ruo:unit:vision-track:{}", stable_key(&b.track_id));
        a_id.cmp(&b_id).then(a.detection_id.cmp(&b.detection_id))
    });
    let unit_ids: Vec<String> = detections
        .iter()
        .map(|d| format!("ruo:unit:vision-track:{}", stable_key(&d.track_id)))
        .collect();
    if unit_ids.iter().collect::<BTreeSet<_>>().len() != unit_ids.len() {
        return Err(VisionError::new(
            "VIS-DET-007",
            "identity",
            "multiple detections resolve to the same track in one observation",
        ));
    }

    let mut units = Vec::new();
    units.push(merge(
        base("composite_reasonunit"),
        json!({
            "entity_id": root_id, "owner_object_id": object_id,
            "unit_kind": "composite", "children": [frame_id]
        }),
    ));
    units.push(merge(
        base("composite_reasonunit"),
        json!({
            "entity_id": frame_id, "owner_object_id": object_id,
            "unit_kind": "composite", "children": unit_ids
        }),
    ));
    for unit_id in &unit_ids {
        units.push(merge(
            base("atomic_reasonunit"),
            json!({
                "entity_id": unit_id, "owner_object_id": object_id,
                "unit_kind": "atomic", "children": []
            }),
        ));
    }

    let evidence_ids: Vec<String> = detections
        .iter()
        .map(|d| {
            format!(
                "ruo:evidence:vision:{}",
                stable_key(&format!(
                    "{}:{}",
                    observation.observation_id, d.detection_id
                ))
            )
        })
        .collect();
    let evidence_registry: Vec<Value> = detections
        .iter()
        .zip(&evidence_ids)
        .map(|(d, evidence_id)| {
            merge(
                base("evidence"),
                json!({
                    "evidence_id": evidence_id,
                    "provenance": {
                        "observation_id": observation.observation_id,
                        "image_digest": observation.source.image_digest,
                        "model_id": observation.model.model_id,
                        "model_digest": observation.model.model_digest,
                        "backend": observation.model.backend,
                        "preprocessing_profile": observation.model.preprocessing_profile,
                        "detection_id": d.detection_id
                    },
                    "confidence": d.confidence,
                    "confidence_contract": "closed_interval_0_1",
                    "observation_or_inference": "observation",
                    "invalidated_by_revision": null
                }),
            )
        })
        .collect();

    let states: Vec<Value> = detections.iter().zip(&unit_ids).zip(&evidence_ids).map(|((d, unit_id), evidence_id)| merge(base("state"), json!({
        "state_id": format!("ruo:state:vision:{}", stable_key(&format!("{}:{}", observation.observation_id, d.detection_id))),
        "owner_id": unit_id,
        "state_class": "unit_local",
        "value": {
            "class_label": d.class_label,
            "class_index": d.class_index,
            "confidence": d.confidence,
            "bounding_box_xywh": d.bounding_box,
            "image_center_xy": d.image_center,
            "frame_time": observation.source.frame_time,
            "knowledge_status": "observed"
        },
        "source_revision": revision_id,
        "source_revisions": {},
        "validity": "current",
        "evidence_refs": [evidence_id],
        "dependency_refs": [],
        "lifecycle_eligibility": ["active"]
    }))).collect();

    let relations: Vec<Value> = unit_ids.iter().zip(&evidence_ids).map(|(unit_id, evidence_id)| merge(base("relation"), json!({
        "relation_id": format!("ruo:relation:observed:{}", stable_key(&format!("{}:{}", frame_id, unit_id))),
        "relation_type": "reasonscript.vision:observed_in/1",
        "relation_class": "internal",
        "source_id": frame_id,
        "target_id": unit_id,
        "directionality": "directed",
        "multiplicity": "one-to-many",
        "endpoint_resolution": "resolved",
        "evidence_refs": [evidence_id]
    }))).collect();

    let mut resources = BTreeMap::new();
    let mut payloads = Vec::new();
    let mut external_resources = Vec::new();
    payloads.push(merge(base("payload"), json!({
        "payload_id": format!("ruo:payload:image:{}", observation.source.image_digest.trim_start_matches("sha256:") ),
        "owner_id": frame_id,
        "profile_id": "ruo.payload.binary-ref/1",
        "value_presence": "external",
        "value_ref": {
            "media_type": "image/*",
            "artifact_ref": observation.source.artifact_ref,
            "sha256": observation.source.image_digest
        },
        "evidence_refs": []
    })));

    let detection_values: Vec<f32> = detections
        .iter()
        .flat_map(|d| {
            [
                d.bounding_box[0],
                d.bounding_box[1],
                d.bounding_box[2],
                d.bounding_box[3],
                d.confidence,
                d.class_index as f32,
            ]
        })
        .collect();
    add_tensor(
        &mut payloads,
        &mut resources,
        &mut external_resources,
        &base,
        &frame_id,
        "detections",
        vec![detections.len(), 6],
        detection_values,
        Some(unit_ids.clone()),
        Some(vec![
            "x",
            "y",
            "width",
            "height",
            "confidence",
            "class_index",
        ]),
        revision_id,
        &evidence_ids,
    )?;

    if let Some(input) = &observation.input_tensor {
        add_tensor(
            &mut payloads,
            &mut resources,
            &mut external_resources,
            &base,
            &frame_id,
            "input",
            input.shape.clone(),
            input.values.clone(),
            None,
            None,
            revision_id,
            &[],
        )?;
    }
    if let Some(width) = detections
        .first()
        .and_then(|d| d.embedding.as_ref().map(Vec::len))
    {
        let values = detections
            .iter()
            .flat_map(|d| d.embedding.clone().unwrap_or_default())
            .collect();
        add_tensor(
            &mut payloads,
            &mut resources,
            &mut external_resources,
            &base,
            &frame_id,
            "embeddings",
            vec![detections.len(), width],
            values,
            Some(unit_ids.clone()),
            None,
            revision_id,
            &evidence_ids,
        )?;
    }

    let object = json!({
        "model_version": "reasonscript-reasonunit-object/1.0",
        "object_identity": merge(base("reasonunit_object"), json!({"entity_id": object_id})),
        "object_type": "reasonscript.vision:observation-session/1",
        "lifecycle_state": "active",
        "current_revision": revision_id,
        "revisions": [{"revision_id": revision_id, "transaction_id": "ruo:transaction:vision-initial", "source_revision": null, "changed_entities": []}],
        "root_units": [root_id],
        "units": units,
        "payloads": payloads,
        "states": states,
        "relations": relations,
        "constraints": [],
        "evidence_registry": evidence_registry,
        "dependency_graph": [],
        "extension_registry": [{
            "namespace": "reasonscript.vision", "authority": PROFILE, "version": "0.1",
            "entity_kinds": ["payload", "state", "relation", "evidence"],
            "canonical_ordering": "stable_identity", "compatibility": "retain", "opaque_retention": true
        }],
        "projection_descriptors": [],
        "partial_loading": {"is_partial": false, "entity_status": {}, "unattached_retained_entities": []},
        "external_resources": external_resources,
        "dependency_cycle_policy": null,
        "extensions": {"reasonscript.vision": {"critical": false, "observation_profile": OBSERVATION_PROFILE, "observation_id": observation.observation_id}}
    });
    Ok(VisionBundle { object, resources })
}

pub fn write_bundle(bundle: &VisionBundle, output: &Path) -> Result<(), VisionError> {
    fs::create_dir_all(output.join("resources")).map_err(io_error)?;
    let object_path = output.join("vision_object.json");
    let object_bytes = serde_json::to_vec_pretty(&bundle.object).map_err(json_error)?;
    fs::write(&object_path, [object_bytes, b"\n".to_vec()].concat()).map_err(io_error)?;
    for (locator, bytes) in &bundle.resources {
        let path = output.join(locator);
        if path.parent().is_some() {
            fs::create_dir_all(path.parent().unwrap()).map_err(io_error)?;
        }
        fs::write(path, bytes).map_err(io_error)?;
    }
    let manifest = json!({
        "schema_version": "reasonscript-vision-runtime-artifacts/0.1",
        "profile": PROFILE,
        "object": "vision_object.json",
        "object_sha256": sha_prefixed(&fs::read(object_path).map_err(io_error)?),
        "resources": bundle.resources.iter().map(|(path, bytes)| json!({"path": path, "sha256": sha_prefixed(bytes), "byte_size": bytes.len()})).collect::<Vec<_>>()
    });
    fs::write(
        output.join("vision_manifest.json"),
        [
            serde_json::to_vec_pretty(&manifest).map_err(json_error)?,
            b"\n".to_vec(),
        ]
        .concat(),
    )
    .map_err(io_error)?;
    Ok(())
}

fn add_tensor(
    payloads: &mut Vec<Value>,
    resources: &mut BTreeMap<String, Vec<u8>>,
    external_resources: &mut Vec<Value>,
    base: &impl Fn(&str) -> Value,
    owner_id: &str,
    role: &str,
    shape: Vec<usize>,
    values: Vec<f32>,
    axis0_ids: Option<Vec<String>>,
    axis1_labels: Option<Vec<&str>>,
    revision_id: &str,
    evidence_refs: &[String],
) -> Result<(), VisionError> {
    if checked_product(&shape)? != values.len() {
        return Err(VisionError::new(
            "VIS-TEN-003",
            "tensor",
            "generated tensor shape mismatch",
        ));
    }
    let payload_id = format!("ruo:payload:tensor:vision:{role}:{}", stable_key(owner_id));
    let resource_id = format!("ruo:resource:vision:{role}:{}", stable_key(owner_id));
    let locator = format!("resources/{role}.ruot");
    let bytes = encode_f32(&values)?;
    let mut axes: Vec<Value> = shape
        .iter()
        .enumerate()
        .map(|(ordinal, size)| {
            json!({
                "ordinal": ordinal, "size": size, "ordering": "ordered",
                "duplicate_policy": "forbidden", "partial_loading_status": "complete"
            })
        })
        .collect();
    if let Some(ids) = axis0_ids {
        axes[0]["identity_mapping"] = json!({
            "mapping_version": "1", "ordered_ids": ids, "uniqueness": "unique",
            "source_object_revision": revision_id, "partial": false
        });
    }
    if let Some(labels) = axis1_labels {
        axes[1]["extensions"] = json!({"reasonscript.vision:column_labels": labels});
    }
    let validity = json!({"status": "complete", "states": vec!["valid"; values.len()]});
    let storage = json!({
        "layout": "row_major", "byte_order": "little", "contiguous": true, "offset_bytes": 0,
        "resource_id": resource_id, "locator": locator,
        "media_type": "application/vnd.reasonscript.ruo-tensor", "byte_size": bytes.len(),
        "sha256": sha_prefixed(&bytes), "chunks": []
    });
    let mut body = json!({
        "payload_id": payload_id, "tensor_profile": TENSOR_PROFILE, "dtype": "float32",
        "rank": shape.len(), "shape": shape, "element_count": values.len(),
        "representation": "dense_resource", "axes": axes, "value_presence": "present",
        "validity": validity, "storage": storage, "logical_digest": "",
        "evidence_refs": evidence_refs, "extensions": {"reasonscript.vision": {"critical": false, "role": role}}
    });
    body["logical_digest"] = Value::String(tensor_logical_digest(&body, &values));
    payloads.push(merge(
        base("payload"),
        json!({
            "payload_id": payload_id, "owner_id": owner_id, "profile_id": "ruo.payload.tensor/1",
            "value_presence": "present", "value": body, "evidence_refs": evidence_refs
        }),
    ));
    external_resources.push(json!({
        "resource_id": resource_id, "owner_payload_id": payload_id,
        "content_sha256": sha_prefixed(&bytes).trim_start_matches("sha256:"),
        "byte_size": bytes.len(), "media_type": "application/vnd.reasonscript.ruo-tensor",
        "payload_profile": "ruo.payload.tensor/1", "profile_version": "1",
        "logical_role": format!("reasonscript.vision:{role}"), "locator_policy": "relative-resource-root",
        "locator": locator, "availability_status": "available", "critical": true,
        "representation": "dense_resource", "dtype": "float32", "shape_digest": sha_prefixed(serde_json::to_string(&shape).unwrap_or_default().as_bytes()),
        "chunks": [], "evidence_refs": evidence_refs, "provenance_refs": evidence_refs
    }));
    resources.insert(locator, bytes);
    Ok(())
}

fn tensor_logical_digest(body: &Value, values: &[f32]) -> String {
    let axes = body["axes"].clone();
    let normalized = json!({
        "tensor_profile": body["tensor_profile"], "dtype": body["dtype"], "rank": body["rank"],
        "shape": body["shape"], "axes": axes,
        "values_hex": values.iter().map(|value| normalized_f32(*value).to_le_bytes().iter().map(|b| format!("{b:02x}")).collect::<String>()).collect::<Vec<_>>(),
        "validity": body["validity"], "unit": Value::Null, "reference_frame": Value::Null,
        "explicit_zero_policy": "forbidden", "critical_extensions": {}
    });
    sha_prefixed(
        serde_json::to_string(&normalized)
            .expect("canonical JSON")
            .as_bytes(),
    )
}

fn encode_f32(values: &[f32]) -> Result<Vec<u8>, VisionError> {
    let mut bytes = Vec::with_capacity(values.len() * 4);
    for value in values {
        if !value.is_finite() {
            return Err(VisionError::new(
                "VIS-TEN-004",
                "tensor",
                "non-finite tensor value",
            ));
        }
        bytes.extend_from_slice(&normalized_f32(*value).to_le_bytes());
    }
    Ok(bytes)
}

fn normalized_f32(value: f32) -> f32 {
    if value == 0.0 {
        0.0
    } else {
        value
    }
}

fn checked_product(shape: &[usize]) -> Result<usize, VisionError> {
    shape.iter().try_fold(1usize, |count, size| {
        count
            .checked_mul(*size)
            .ok_or_else(|| VisionError::new("VIS-TEN-005", "tensor", "tensor shape overflow"))
    })
}

fn digest_like(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64
        && hex
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn safe_relative_to(root: &Path, relative: &str) -> Result<std::path::PathBuf, VisionError> {
    let path = Path::new(relative);
    if path.is_absolute()
        || relative.contains('\\')
        || path.components().any(|component| {
            matches!(
                component,
                std::path::Component::ParentDir
                    | std::path::Component::RootDir
                    | std::path::Component::Prefix(_)
            )
        })
    {
        return Err(VisionError::new(
            "VIS-SEC-001",
            "path",
            "unsafe model-relative path",
        ));
    }
    Ok(root.join(path))
}

fn stable_key(value: &str) -> String {
    hex_digest(value.as_bytes())[..24].to_owned()
}
fn hex_digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn sha_prefixed(bytes: &[u8]) -> String {
    format!("sha256:{}", hex_digest(bytes))
}

fn merge(mut left: Value, right: Value) -> Value {
    if let (Some(left), Some(right)) = (left.as_object_mut(), right.as_object()) {
        for (key, value) in right {
            left.insert(key.clone(), value.clone());
        }
    }
    left
}

fn io_error(error: std::io::Error) -> VisionError {
    VisionError::new("VIS-IO-001", "io", error.to_string())
}
fn json_error(error: serde_json::Error) -> VisionError {
    VisionError::new("VIS-JSON-001", "json", error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn observation() -> VisionObservation {
        serde_json::from_value(json!({
            "schema_version": OBSERVATION_PROFILE,
            "observation_id": "obs:frame:42", "session_id": "solar-session-alpha",
            "source": {"image_digest": format!("sha256:{}", "a".repeat(64)), "frame_id": "frame-42", "frame_time": 42.0, "artifact_ref": "frames/42.png"},
            "model": {"model_id": "solar-detector", "model_digest": format!("sha256:{}", "b".repeat(64)), "backend": "burn", "preprocessing_profile": "solar-vision-input/1"},
            "detections": [{"detection_id":"det:earth:42", "track_id":"earth-01", "class_label":"earth", "class_index":3, "confidence":0.982, "bounding_box":[412.0,218.0,42.0,42.0], "image_center":[433.0,239.0], "embedding":[0.1,0.2]}]
        })).unwrap()
    }

    #[test]
    fn builds_semantic_and_tensor_views() {
        let bundle = build_ruo(&observation()).unwrap();
        assert_eq!(
            bundle.object["payloads"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|p| p["profile_id"] == "ruo.payload.tensor/1")
                .count(),
            2
        );
        assert_eq!(bundle.resources["resources/detections.ruot"].len(), 24);
        let mapping =
            &bundle.object["payloads"][1]["value"]["axes"][0]["identity_mapping"]["ordered_ids"][0];
        assert!(mapping
            .as_str()
            .unwrap()
            .starts_with("ruo:unit:vision-track:"));
    }

    #[test]
    fn rejects_invalid_confidence() {
        let mut value = observation();
        value.detections[0].confidence = 1.1;
        assert_eq!(
            validate_observation(&value).unwrap_err().code,
            "VIS-DET-003"
        );
    }

    #[test]
    fn stable_output_is_independent_of_detection_order() {
        let mut first = observation();
        let mut second = first.detections[0].clone();
        second.detection_id = "det:mars:42".into();
        second.track_id = "mars-01".into();
        second.class_label = "mars".into();
        second.class_index = 4;
        first.detections.push(second);
        let mut reversed = first.clone();
        reversed.detections.reverse();
        assert_eq!(
            build_ruo(&first).unwrap().object,
            build_ruo(&reversed).unwrap().object
        );
    }

    #[test]
    fn rejects_uninstalled_model_backend() {
        let directory =
            std::env::temp_dir().join(format!("vision-model-{}", stable_key("unsupported")));
        fs::create_dir_all(&directory).unwrap();
        let manifest = json!({
            "schema_version":"reasonscript-vision-model/0.1", "model_id":"m",
            "model_digest":format!("sha256:{}", "c".repeat(64)), "backend":"burn",
            "preprocessing_profile":"p/1"
        });
        fs::write(
            directory.join("model.json"),
            serde_json::to_vec(&manifest).unwrap(),
        )
        .unwrap();
        fs::write(directory.join("image.bin"), b"image").unwrap();
        assert_eq!(
            infer_from_manifest(&directory.join("model.json"), &directory.join("image.bin"))
                .unwrap_err()
                .code,
            "VIS-RUN-001"
        );
    }
}
