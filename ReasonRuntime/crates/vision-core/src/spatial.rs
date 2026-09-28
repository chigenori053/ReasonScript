//! Versioned spatial projection of authored Vision observations.
use crate::{validate_observation, VisionError, VisionObservation};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

pub const PROFILE: &str = "reasonscript-visual-observation/1.0";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct CoordinateSystem {
    pub id: String,
    pub origin: String,
    pub x_direction: String,
    pub y_direction: String,
    pub unit: String,
}

impl Default for CoordinateSystem {
    fn default() -> Self {
        Self {
            id: "image-pixel".into(),
            origin: "TOP_LEFT".into(),
            x_direction: "RIGHT".into(),
            y_direction: "DOWN".into(),
            unit: "PIXEL".into(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct VisualObject {
    pub object_id: String,
    pub object_type: Option<String>,
    #[serde(default)]
    pub candidate_types: Vec<String>,
    pub bounding_box: Option<[f64; 4]>,
    pub centroid: Option<[f64; 2]>,
    #[serde(default)]
    pub contour: Vec<[f64; 2]>,
    #[serde(default)]
    pub keypoints: BTreeMap<String, [f64; 2]>,
    #[serde(default)]
    pub attributes: BTreeMap<String, Value>,
    pub confidence: Option<f64>,
    pub uncertainty: Option<f64>,
    pub source: String,
    pub provenance: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct VisualObservation {
    pub schema_version: String,
    pub source_id: String,
    pub coordinate_system: CoordinateSystem,
    pub objects: Vec<VisualObject>,
    #[serde(default)]
    pub observed_relations: Vec<Value>,
    #[serde(default)]
    pub unknowns: Vec<Value>,
    #[serde(default)]
    pub conflicts: Vec<Value>,
    pub provenance: Vec<String>,
}

pub fn observe_spatial(input: &VisionObservation) -> Result<VisualObservation, VisionError> {
    validate_observation(input)?;
    let mut objects: Vec<_> = input
        .detections
        .iter()
        .map(|d| VisualObject {
            object_id: d.detection_id.clone(),
            object_type: Some(d.class_label.clone()),
            candidate_types: vec![],
            bounding_box: Some(d.bounding_box.map(f64::from)),
            centroid: Some(d.image_center.map(f64::from)),
            contour: vec![],
            keypoints: BTreeMap::new(),
            attributes: BTreeMap::new(),
            confidence: Some(f64::from(d.confidence)),
            uncertainty: None,
            source: input.source.frame_id.clone(),
            provenance: vec![
                input.source.image_digest.clone(),
                input.model.model_digest.clone(),
                input.observation_id.clone(),
                d.detection_id.clone(),
            ],
        })
        .collect();
    objects.sort_by(|a, b| a.object_id.cmp(&b.object_id));
    Ok(VisualObservation {
        schema_version: PROFILE.into(),
        source_id: input.observation_id.clone(),
        coordinate_system: CoordinateSystem::default(),
        objects,
        observed_relations: vec![],
        unknowns: vec![],
        conflicts: vec![],
        provenance: vec![
            input.source.image_digest.clone(),
            input.model.model_digest.clone(),
            input.observation_id.clone(),
        ],
    })
}
