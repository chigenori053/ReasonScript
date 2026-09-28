//! Deterministic 2D geometry over explicit visual observations.
use reasonscript_vision_runtime::spatial::{
    CoordinateSystem, VisualObservation, PROFILE as VISUAL_PROFILE,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};

pub const PROFILE: &str = "reasonscript-geometry-state/1.0";
const KINDS: &[&str] = &[
    "Point",
    "Vector",
    "Line",
    "Segment",
    "Ray",
    "BoundingBox",
    "Circle",
    "Arc",
    "Triangle",
    "Rectangle",
    "Polygon",
    "Transform",
];

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Tolerance {
    pub absolute: f64,
    pub relative: f64,
    pub angular: f64,
    pub pixel: f64,
}
impl Default for Tolerance {
    fn default() -> Self {
        Self {
            absolute: 1e-9,
            relative: 1e-9,
            angular: 1e-9,
            pixel: 1.0,
        }
    }
}
impl Tolerance {
    pub fn validate(&self) -> Result<(), String> {
        if [self.absolute, self.relative, self.angular, self.pixel]
            .iter()
            .all(|v| v.is_finite() && *v >= 0.0)
        {
            Ok(())
        } else {
            Err("GEO-TOL-001: tolerance must be finite and nonnegative".into())
        }
    }
    fn eq(&self, a: f64, b: f64) -> bool {
        (a - b).abs() <= self.absolute.max(self.relative * a.abs().max(b.abs()))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Primitive {
    pub geometry_id: String,
    pub geometry_type: String,
    pub coordinate_system: String,
    pub parameters: Value,
    pub provenance: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Relation {
    pub subject: String,
    pub predicate: String,
    pub object: String,
    pub provenance: Vec<String>,
    pub rule: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GeometryState {
    pub schema_version: String,
    pub state_id: String,
    pub coordinate_systems: Vec<CoordinateSystem>,
    pub primitives: Vec<Primitive>,
    pub relations: Vec<Relation>,
    pub unknowns: Vec<Value>,
    pub conflicts: Vec<Value>,
    pub provenance: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct GeometryResult {
    pub status: String,
    pub value: Value,
    pub provenance: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ReasonTrace {
    pub task_id: String,
    pub runtime: String,
    pub worker_id: String,
    pub input_hash: String,
    pub operations: Vec<Value>,
    pub output_hash: String,
    pub provenance: Vec<String>,
    pub status: String,
}

fn canonical<T: Serialize + ?Sized>(value: &T) -> Result<String, String> {
    serde_json::to_string(value).map_err(|e| e.to_string())
}
pub fn digest<T: Serialize + ?Sized>(value: &T) -> Result<String, String> {
    Ok(format!(
        "sha256:{:x}",
        Sha256::digest(canonical(value)?.as_bytes())
    ))
}
fn sorted_unique(values: &mut Vec<String>) {
    values.sort();
    values.dedup();
}
fn finite(values: &[f64]) -> bool {
    values.iter().all(|v| v.is_finite())
}
fn point(v: &Value) -> Option<[f64; 2]> {
    let a = v.as_array()?;
    if a.len() != 2 {
        return None;
    }
    let p = [a[0].as_f64()?, a[1].as_f64()?];
    finite(&p).then_some(p)
}
fn bbox(v: &Value) -> Option<[f64; 4]> {
    let a = v.as_array()?;
    if a.len() != 4 {
        return None;
    }
    let b = [
        a[0].as_f64()?,
        a[1].as_f64()?,
        a[2].as_f64()?,
        a[3].as_f64()?,
    ];
    (finite(&b) && b[2] >= 0.0 && b[3] >= 0.0).then_some(b)
}
fn pv(p: &Primitive) -> Option<[f64; 2]> {
    point(&p.parameters["xy"])
}
fn bv(p: &Primitive) -> Option<[f64; 4]> {
    bbox(&p.parameters["xywh"])
}
fn circle(p: &Primitive) -> Option<([f64; 2], f64)> {
    if p.geometry_type != "Circle" {
        return None;
    }
    Some((
        point(&p.parameters["center"])?,
        p.parameters["radius"].as_f64()?,
    ))
}
fn endpoints(p: &Primitive) -> Option<([f64; 2], [f64; 2])> {
    Some((point(&p.parameters["start"])?, point(&p.parameters["end"])?))
}
fn center(p: &Primitive) -> Option<[f64; 2]> {
    pv(p)
        .or_else(|| bv(p).map(|b| [b[0] + b[2] / 2.0, b[1] + b[3] / 2.0]))
        .or_else(|| circle(p).map(|c| c.0))
        .or_else(|| {
            (p.geometry_type == "Arc")
                .then(|| point(&p.parameters["center"]))
                .flatten()
        })
}
fn cross(a: [f64; 2], b: [f64; 2]) -> f64 {
    a[0] * b[1] - a[1] * b[0]
}
fn sub(a: [f64; 2], b: [f64; 2]) -> [f64; 2] {
    [a[0] - b[0], a[1] - b[1]]
}
fn dot(a: [f64; 2], b: [f64; 2]) -> f64 {
    a[0] * b[0] + a[1] * b[1]
}
fn norm(a: [f64; 2]) -> f64 {
    dot(a, a).sqrt()
}

pub fn validate_primitive(p: &Primitive, systems: &[CoordinateSystem]) -> Result<(), String> {
    if p.geometry_id.is_empty()
        || p.provenance.is_empty()
        || !systems.iter().any(|s| s.id == p.coordinate_system)
    {
        return Err("GEO-IR-001: missing identity, provenance, or coordinate system".into());
    }
    if !KINDS.contains(&p.geometry_type.as_str()) {
        return Err("GEO-IR-002: unsupported primitive".into());
    }
    let valid = match p.geometry_type.as_str() {
        "Point" | "Vector" => pv(p).is_some(),
        "BoundingBox" | "Rectangle" => bv(p).is_some(),
        "Line" | "Segment" | "Ray" => endpoints(p).is_some(),
        "Circle" | "Arc" => {
            point(&p.parameters["center"]).is_some()
                && p.parameters["radius"]
                    .as_f64()
                    .is_some_and(|r| r.is_finite() && r >= 0.0)
                && (p.geometry_type != "Arc"
                    || (p.parameters["start_angle"]
                        .as_f64()
                        .is_some_and(f64::is_finite)
                        && p.parameters["end_angle"]
                            .as_f64()
                            .is_some_and(f64::is_finite)))
        }
        "Triangle" | "Polygon" => p.parameters["vertices"].as_array().is_some_and(|a| {
            a.len() >= 3
                && (p.geometry_type != "Triangle" || a.len() == 3)
                && a.iter().all(|v| point(v).is_some())
        }),
        "Transform" => p.parameters["matrix"].as_array().is_some_and(|a| {
            a.len() == 6 && a.iter().all(|v| v.as_f64().is_some_and(f64::is_finite))
        }),
        _ => false,
    };
    if valid {
        Ok(())
    } else {
        Err("GEO-IR-003: invalid primitive parameters".into())
    }
}

pub fn canonicalize(state: &mut GeometryState) -> Result<(), String> {
    if state.schema_version != PROFILE {
        return Err("GEO-IR-004: unsupported state version".into());
    }
    state.coordinate_systems.sort_by(|a, b| a.id.cmp(&b.id));
    state
        .primitives
        .sort_by(|a, b| a.geometry_id.cmp(&b.geometry_id));
    state.relations.sort_by(|a, b| {
        (&a.subject, &a.predicate, &a.object, &a.rule).cmp(&(
            &b.subject,
            &b.predicate,
            &b.object,
            &b.rule,
        ))
    });
    let mut merged_relations: Vec<Relation> = Vec::new();
    for relation in state.relations.drain(..) {
        if let Some(last) = merged_relations.last_mut() {
            if last.subject == relation.subject
                && last.predicate == relation.predicate
                && last.object == relation.object
                && last.rule == relation.rule
            {
                last.provenance.extend(relation.provenance);
                continue;
            }
        }
        merged_relations.push(relation);
    }
    state.relations = merged_relations;
    for p in &mut state.primitives {
        sorted_unique(&mut p.provenance);
    }
    for r in &mut state.relations {
        sorted_unique(&mut r.provenance);
    }
    sorted_unique(&mut state.provenance);
    state
        .unknowns
        .sort_by_key(|v| canonical(v).unwrap_or_default());
    state.unknowns.dedup();
    for conflict in &mut state.conflicts {
        if let Some(candidates) = conflict.get_mut("candidates").and_then(Value::as_array_mut) {
            candidates.sort_by_key(|v| canonical(v).unwrap_or_default());
            candidates.dedup();
        }
    }
    state
        .conflicts
        .sort_by_key(|v| canonical(v).unwrap_or_default());
    state.conflicts.dedup();
    if state.coordinate_systems.iter().any(|s| {
        s.id.is_empty()
            || s.origin != "TOP_LEFT"
            || s.x_direction != "RIGHT"
            || s.y_direction != "DOWN"
            || s.unit != "PIXEL"
    }) || state
        .coordinate_systems
        .windows(2)
        .any(|w| w[0].id == w[1].id)
    {
        return Err("GEO-IR-005: unsupported coordinate system".into());
    }
    let mut unique = BTreeMap::<String, Primitive>::new();
    for p in state.primitives.drain(..) {
        validate_primitive(&p, &state.coordinate_systems)?;
        if let Some(existing) = unique.get_mut(&p.geometry_id) {
            if existing.geometry_type == p.geometry_type
                && existing.coordinate_system == p.coordinate_system
                && existing.parameters == p.parameters
            {
                existing.provenance.extend(p.provenance);
            } else {
                state.conflicts.push(json!({"geometry_id":p.geometry_id,"candidates":[existing,p],"status":"CONFLICT"}));
            }
        } else {
            unique.insert(p.geometry_id.clone(), p);
        }
    }
    let conflicted: BTreeSet<_> = state
        .conflicts
        .iter()
        .filter_map(|v| v["geometry_id"].as_str().map(str::to_owned))
        .collect();
    state.primitives = unique
        .into_values()
        .filter(|p| !conflicted.contains(&p.geometry_id))
        .collect();
    for p in &mut state.primitives {
        sorted_unique(&mut p.provenance);
    }
    for conflict in &mut state.conflicts {
        if let Some(candidates) = conflict.get_mut("candidates").and_then(Value::as_array_mut) {
            candidates.sort_by_key(|v| canonical(v).unwrap_or_default());
            candidates.dedup();
        }
    }
    state
        .conflicts
        .sort_by_key(|v| canonical(v).unwrap_or_default());
    state.conflicts.dedup();
    Ok(())
}

pub fn from_visual(observation: &VisualObservation) -> Result<GeometryState, String> {
    if observation.schema_version != VISUAL_PROFILE
        || observation.source_id.is_empty()
        || observation.coordinate_system.id.is_empty()
    {
        return Err("GEO-VIS-001: invalid visual observation".into());
    }
    let mut state = GeometryState {
        schema_version: PROFILE.into(),
        state_id: format!("geometry:{}", observation.source_id),
        coordinate_systems: vec![observation.coordinate_system.clone()],
        primitives: vec![],
        relations: vec![],
        unknowns: observation.unknowns.clone(),
        conflicts: observation.conflicts.clone(),
        provenance: observation.provenance.clone(),
    };
    for object in &observation.objects {
        if object.object_id.is_empty() || object.provenance.is_empty() {
            return Err("GEO-VIS-002: object identity and provenance required".into());
        }
        let mut provenance = object.provenance.clone();
        provenance.push(format!("visual-object:{}", object.object_id));
        sorted_unique(&mut provenance);
        if let Some(b) = object.bounding_box {
            if !finite(&b) || b[2] < 0.0 || b[3] < 0.0 {
                return Err("GEO-VIS-003: invalid bounding box".into());
            }
            state.primitives.push(Primitive {
                geometry_id: format!("{}:bbox", object.object_id),
                geometry_type: "BoundingBox".into(),
                coordinate_system: observation.coordinate_system.id.clone(),
                parameters: json!({"xywh":b}),
                provenance: provenance.clone(),
            });
        }
        if let Some(c) = object.centroid {
            if !finite(&c) {
                return Err("GEO-VIS-003: invalid centroid".into());
            }
            state.primitives.push(Primitive {
                geometry_id: format!("{}:centroid", object.object_id),
                geometry_type: "Point".into(),
                coordinate_system: observation.coordinate_system.id.clone(),
                parameters: json!({"xy":c}),
                provenance: provenance.clone(),
            });
        }
        if object.centroid.is_none() || object.bounding_box.is_none() {
            state.unknowns.push(json!({"object_id":object.object_id,"field":if object.centroid.is_none(){"centroid"}else{"bounding_box"},"provenance":provenance}));
        }
    }
    canonicalize(&mut state)?;
    Ok(state)
}

pub fn merge(states: &[GeometryState]) -> Result<GeometryState, String> {
    if states.is_empty() {
        return Err("GEO-MERGE-001: no states".into());
    }
    if states.len() == 1 {
        let mut state = states[0].clone();
        canonicalize(&mut state)?;
        return Ok(state);
    }
    let mut result = GeometryState {
        schema_version: PROFILE.into(),
        state_id: "geometry:merged".into(),
        coordinate_systems: vec![],
        primitives: vec![],
        relations: vec![],
        unknowns: vec![],
        conflicts: vec![],
        provenance: vec![],
    };
    let mut systems = BTreeMap::new();
    let mut primitives: BTreeMap<String, Primitive> = BTreeMap::new();
    for state in states {
        let mut checked = state.clone();
        canonicalize(&mut checked)?;
        for cs in &checked.coordinate_systems {
            if let Some(old) = systems.insert(cs.id.clone(), cs.clone()) {
                if old != *cs {
                    return Err("GEO-MERGE-002: coordinate system conflict".into());
                }
            }
        }
        for p in &checked.primitives {
            if let Some(old) = primitives.get(&p.geometry_id) {
                if old.geometry_type != p.geometry_type
                    || old.coordinate_system != p.coordinate_system
                    || old.parameters != p.parameters
                {
                    result.conflicts.push(json!({"geometry_id":p.geometry_id,"candidates":[old,p],"status":"CONFLICT"}));
                } else {
                    let item = primitives.get_mut(&p.geometry_id).unwrap();
                    item.provenance.extend(p.provenance.clone());
                }
            } else {
                primitives.insert(p.geometry_id.clone(), p.clone());
            }
        }
        result.relations.extend(checked.relations);
        result.unknowns.extend(checked.unknowns);
        result.conflicts.extend(checked.conflicts);
        result.provenance.extend(checked.provenance);
    }
    let conflicted: BTreeSet<_> = result
        .conflicts
        .iter()
        .filter_map(|v| v["geometry_id"].as_str().map(str::to_owned))
        .collect();
    result.primitives = primitives
        .into_values()
        .filter(|p| !conflicted.contains(&p.geometry_id))
        .collect();
    result.coordinate_systems = systems.into_values().collect();
    canonicalize(&mut result)?;
    Ok(result)
}

fn result(value: Option<Value>, provenance: Vec<String>) -> GeometryResult {
    match value {
        Some(value) => GeometryResult {
            status: "KNOWN".into(),
            value,
            provenance,
        },
        None => GeometryResult {
            status: "UNKNOWN".into(),
            value: Value::Null,
            provenance,
        },
    }
}
fn compatible(a: &Primitive, b: &Primitive) -> bool {
    a.coordinate_system == b.coordinate_system
}
pub fn operate(
    name: &str,
    a: &Primitive,
    b: Option<&Primitive>,
    c: Option<&Primitive>,
    tol: &Tolerance,
) -> Result<GeometryResult, String> {
    tol.validate()?;
    let provenance = {
        let mut p = a.provenance.clone();
        if let Some(b) = b {
            p.extend(b.provenance.clone())
        }
        if let Some(c) = c {
            p.extend(c.provenance.clone())
        }
        sorted_unique(&mut p);
        p
    };
    if b.is_some_and(|b| !compatible(a, b)) || c.is_some_and(|c| !compatible(a, c)) {
        return Err("GEO-CS-001: coordinate systems differ; transform explicitly".into());
    }
    let v = match name {
        "distance" => b.and_then(|b| Some(json!(norm(sub(center(a)?, center(b)?))))),
        "angle" => b.zip(c).and_then(|(b, c)| {
            let u = sub(center(a)?, center(b)?);
            let v = sub(center(c)?, center(b)?);
            (norm(u) > tol.absolute && norm(v) > tol.absolute)
                .then(|| json!(cross(u, v).atan2(dot(u, v)).abs()))
        }),
        "contains" => b.and_then(|b| {
            if let Some((o, r)) = circle(a) {
                return Some(json!(if let Some((q, s)) = circle(b) {
                    norm(sub(o, q)) + s <= r + tol.absolute
                } else {
                    norm(sub(o, center(b)?)) <= r + tol.absolute
                }));
            }
            let x = bv(a)?;
            if let Some(y) = bv(b) {
                Some(json!(
                    y[0] >= x[0] - tol.pixel
                        && y[1] >= x[1] - tol.pixel
                        && y[0] + y[2] <= x[0] + x[2] + tol.pixel
                        && y[1] + y[3] <= x[1] + x[3] + tol.pixel
                ))
            } else {
                let q = center(b)?;
                Some(json!(
                    q[0] >= x[0] - tol.pixel
                        && q[0] <= x[0] + x[2] + tol.pixel
                        && q[1] >= x[1] - tol.pixel
                        && q[1] <= x[1] + x[3] + tol.pixel
                ))
            }
        }),
        "overlap" | "touches" => b.and_then(|b| {
            if let (Some((x, r)), Some((y, s))) = (circle(a), circle(b)) {
                let d = norm(sub(x, y));
                return Some(json!(if name == "overlap" {
                    d < r + s - tol.absolute
                } else {
                    (d - (r + s)).abs() <= tol.absolute || (d - (r - s).abs()).abs() <= tol.absolute
                }));
            }
            let x = bv(a)?;
            let y = bv(b)?;
            let dx = (x[0] + x[2]).min(y[0] + y[2]) - x[0].max(y[0]);
            let dy = (x[1] + x[3]).min(y[1] + y[3]) - x[1].max(y[1]);
            Some(json!(if name == "overlap" {
                dx > tol.pixel && dy > tol.pixel
            } else {
                dx >= -tol.pixel
                    && dy >= -tol.pixel
                    && (dx.abs() <= tol.pixel || dy.abs() <= tol.pixel)
            }))
        }),
        "parallel" | "perpendicular" => b.and_then(|b| {
            let (a0, a1) = endpoints(a)?;
            let (b0, b1) = endpoints(b)?;
            let u = sub(a1, a0);
            let v = sub(b1, b0);
            let denom = norm(u) * norm(v);
            (denom > tol.absolute).then(|| {
                json!(if name == "parallel" {
                    cross(u, v).abs() <= tol.angular * denom
                } else {
                    dot(u, v).abs() <= tol.angular * denom
                })
            })
        }),
        "intersect" => b.and_then(|b| {
            if let (Some((x, r)), Some((y, s))) = (circle(a), circle(b)) {
                let d = norm(sub(y, x));
                if d <= tol.absolute {
                    return if tol.eq(r, s) {
                        None
                    } else {
                        Some(Value::Null)
                    };
                }
                if d > r + s + tol.absolute || d < (r - s).abs() - tol.absolute {
                    return Some(Value::Null);
                }
                let along = (r * r - s * s + d * d) / (2.0 * d);
                let height = (r * r - along * along).max(0.0).sqrt();
                let unit = [(y[0] - x[0]) / d, (y[1] - x[1]) / d];
                let base = [x[0] + along * unit[0], x[1] + along * unit[1]];
                if height <= tol.absolute {
                    return Some(json!(base));
                }
                let mut points = [
                    [base[0] - height * unit[1], base[1] + height * unit[0]],
                    [base[0] + height * unit[1], base[1] - height * unit[0]],
                ];
                points.sort_by(|a, b| a[0].total_cmp(&b[0]).then(a[1].total_cmp(&b[1])));
                return Some(json!({"points":points}));
            }
            let (p, p1) = endpoints(a)?;
            let (q, q1) = endpoints(b)?;
            let r = sub(p1, p);
            let s = sub(q1, q);
            if norm(r) <= tol.absolute || norm(s) <= tol.absolute {
                return None;
            }
            let den = cross(r, s);
            if den.abs() <= tol.angular * norm(r) * norm(s) {
                if cross(sub(q, p), r).abs() > tol.absolute * norm(r) {
                    return Some(Value::Null);
                }
                if a.geometry_type == "Segment" && b.geometry_type == "Segment" {
                    let t0 = dot(sub(q, p), r) / dot(r, r);
                    let t1 = dot(sub(q1, p), r) / dot(r, r);
                    let low = t0.min(t1).max(0.0);
                    let high = t0.max(t1).min(1.0);
                    if high < low - tol.absolute {
                        return Some(Value::Null);
                    }
                    let start = [p[0] + low * r[0], p[1] + low * r[1]];
                    if (high - low).abs() <= tol.absolute {
                        return Some(json!(start));
                    }
                    let end = [p[0] + high * r[0], p[1] + high * r[1]];
                    return Some(json!({"segment":[start,end]}));
                }
                return None;
            }
            let t = cross(sub(q, p), s) / den;
            let u = cross(sub(q, p), r) / den;
            let in_range = |kind: &str, v: f64| match kind {
                "Segment" => v >= -tol.absolute && v <= 1.0 + tol.absolute,
                "Ray" => v >= -tol.absolute,
                _ => true,
            };
            Some(
                if in_range(&a.geometry_type, t) && in_range(&b.geometry_type, u) {
                    json!([p[0] + t * r[0], p[1] + t * r[1]])
                } else {
                    Value::Null
                },
            )
        }),
        _ => return Err("GEO-OP-001: unknown operation".into()),
    };
    Ok(result(v, provenance))
}

pub fn transform(p: &Primitive, m: [f64; 6]) -> Result<Primitive, String> {
    if !finite(&m) {
        return Err("GEO-TRF-001: nonfinite transform".into());
    }
    let apply = |p: [f64; 2]| {
        [
            m[0] * p[0] + m[2] * p[1] + m[4],
            m[1] * p[0] + m[3] * p[1] + m[5],
        ]
    };
    let mut out = p.clone();
    out.geometry_id = format!("{}:transform:{}", p.geometry_id, &digest(&m)?[7..23]);
    out.parameters = match p.geometry_type.as_str() {
        "Point" => json!({"xy":apply(pv(p).ok_or("GEO-TRF-002: invalid point")?)}),
        "Vector" => {
            let v = pv(p).ok_or("GEO-TRF-002: invalid vector")?;
            json!({"xy":[m[0]*v[0]+m[2]*v[1],m[1]*v[0]+m[3]*v[1]]})
        }
        "Line" | "Segment" | "Ray" => {
            let (a, b) = endpoints(p).ok_or("GEO-TRF-002: invalid line")?;
            json!({"start":apply(a),"end":apply(b)})
        }
        "BoundingBox" | "Rectangle" => {
            let b = bv(p).ok_or("GEO-TRF-002: invalid box")?;
            let corners = [
                [b[0], b[1]],
                [b[0] + b[2], b[1]],
                [b[0] + b[2], b[1] + b[3]],
                [b[0], b[1] + b[3]],
            ]
            .map(apply);
            if p.geometry_type == "Rectangle" && (m[1].abs() > 1e-9 || m[2].abs() > 1e-9) {
                out.geometry_type = "Polygon".into();
                json!({"vertices":corners})
            } else {
                let xmin = corners.iter().map(|p| p[0]).fold(f64::INFINITY, f64::min);
                let xmax = corners
                    .iter()
                    .map(|p| p[0])
                    .fold(f64::NEG_INFINITY, f64::max);
                let ymin = corners.iter().map(|p| p[1]).fold(f64::INFINITY, f64::min);
                let ymax = corners
                    .iter()
                    .map(|p| p[1])
                    .fold(f64::NEG_INFINITY, f64::max);
                json!({"xywh":[xmin,ymin,xmax-xmin,ymax-ymin]})
            }
        }
        "Triangle" | "Polygon" => {
            let vertices = p.parameters["vertices"]
                .as_array()
                .ok_or("GEO-TRF-002: invalid polygon")?;
            let points: Vec<_> = vertices
                .iter()
                .map(|v| point(v).map(apply).ok_or("GEO-TRF-002: invalid vertex"))
                .collect::<Result<_, _>>()?;
            json!({"vertices":points})
        }
        "Circle" | "Arc" => {
            let u = [m[0], m[1]];
            let v = [m[2], m[3]];
            let sx = norm(u);
            let sy = norm(v);
            if (sx - sy).abs() > 1e-9 * sx.max(sy).max(1.0) || dot(u, v).abs() > 1e-9 * sx * sy {
                return Err("GEO-TRF-004: circle transform requires a similarity".into());
            }
            let center =
                apply(point(&p.parameters["center"]).ok_or("GEO-TRF-002: invalid circle")?);
            let radius = p.parameters["radius"]
                .as_f64()
                .ok_or("GEO-TRF-002: invalid circle")?
                * sx;
            if p.geometry_type == "Arc" {
                let transform_angle = |angle: f64| {
                    (m[1] * angle.cos() + m[3] * angle.sin())
                        .atan2(m[0] * angle.cos() + m[2] * angle.sin())
                };
                let start = p.parameters["start_angle"]
                    .as_f64()
                    .ok_or("GEO-TRF-002: invalid arc")?;
                let end = p.parameters["end_angle"]
                    .as_f64()
                    .ok_or("GEO-TRF-002: invalid arc")?;
                json!({"center":center,"radius":radius,"start_angle":transform_angle(start),"end_angle":transform_angle(end)})
            } else {
                json!({"center":center,"radius":radius})
            }
        }
        _ => return Err("GEO-TRF-003: transform unsupported for primitive".into()),
    };
    out.provenance.push(format!("transform:{}", digest(&m)?));
    sorted_unique(&mut out.provenance);
    Ok(out)
}
pub fn translate(p: &Primitive, dx: f64, dy: f64) -> Result<Primitive, String> {
    transform(p, [1.0, 0.0, 0.0, 1.0, dx, dy])
}
pub fn rotate(p: &Primitive, radians: f64) -> Result<Primitive, String> {
    let (c, s) = (radians.cos(), radians.sin());
    transform(p, [c, s, -s, c, 0.0, 0.0])
}
pub fn scale(p: &Primitive, sx: f64, sy: f64) -> Result<Primitive, String> {
    transform(p, [sx, 0.0, 0.0, sy, 0.0, 0.0])
}

pub fn derive_relations(
    state: &mut GeometryState,
    tol: &Tolerance,
    near_distance: f64,
) -> Result<(), String> {
    tol.validate()?;
    if !near_distance.is_finite() || near_distance < 0.0 {
        return Err("GEO-REL-001: invalid near threshold".into());
    }
    let mut objects: BTreeMap<String, (Option<&Primitive>, Option<&Primitive>)> = BTreeMap::new();
    for p in &state.primitives {
        if let Some(id) = p.geometry_id.strip_suffix(":bbox") {
            objects.entry(id.into()).or_default().0 = Some(p)
        } else if let Some(id) = p.geometry_id.strip_suffix(":centroid") {
            objects.entry(id.into()).or_default().1 = Some(p)
        }
    }
    let ids: Vec<_> = objects.keys().cloned().collect();
    for a in &ids {
        for b in &ids {
            if a == b {
                continue;
            }
            let (ab, ap) = objects[a];
            let (bb, bp) = objects[b];
            let (Some(ap), Some(bp)) = (ap, bp) else {
                state
                    .unknowns
                    .push(json!({"subject":a,"object":b,"operation":"spatial_relations"}));
                continue;
            };
            if !compatible(ap, bp) {
                continue;
            }
            let (x, y) = (pv(ap).unwrap(), pv(bp).unwrap());
            let mut prov = ap.provenance.clone();
            prov.extend(bp.provenance.clone());
            sorted_unique(&mut prov);
            let mut add = |predicate: &str, rule: &str| {
                state.relations.push(Relation {
                    subject: a.clone(),
                    predicate: predicate.into(),
                    object: b.clone(),
                    provenance: prov.clone(),
                    rule: rule.into(),
                })
            };
            if x[0] < y[0] - tol.pixel {
                add("LEFT_OF", "centroid_x_less")
            }
            if x[0] > y[0] + tol.pixel {
                add("RIGHT_OF", "centroid_x_greater")
            }
            if x[1] < y[1] - tol.pixel {
                add("ABOVE", "image_y_less")
            }
            if x[1] > y[1] + tol.pixel {
                add("BELOW", "image_y_greater")
            }
            if tol.eq(x[0], y[0]) || (x[0] - y[0]).abs() <= tol.pixel {
                add("ALIGNED_VERTICAL", "centroid_x_tolerance")
            }
            if tol.eq(x[1], y[1]) || (x[1] - y[1]).abs() <= tol.pixel {
                add("ALIGNED_HORIZONTAL", "centroid_y_tolerance")
            }
            if norm(sub(x, y)) <= near_distance + tol.pixel {
                add("NEAR", "distance_threshold")
            } else {
                add("FAR", "distance_threshold")
            }
            if let (Some(ab), Some(bb)) = (ab, bb) {
                let (u, v) = (bv(ab).unwrap(), bv(bb).unwrap());
                let inside = u[0] >= v[0] - tol.pixel
                    && u[1] >= v[1] - tol.pixel
                    && u[0] + u[2] <= v[0] + v[2] + tol.pixel
                    && u[1] + u[3] <= v[1] + v[3] + tol.pixel;
                let contains = v[0] >= u[0] - tol.pixel
                    && v[1] >= u[1] - tol.pixel
                    && v[0] + v[2] <= u[0] + u[2] + tol.pixel
                    && v[1] + v[3] <= u[1] + u[3] + tol.pixel;
                if inside {
                    add("INSIDE", "bbox_containment")
                }
                if contains {
                    add("CONTAINS", "bbox_containment")
                }
                let dx = (u[0] + u[2]).min(v[0] + v[2]) - u[0].max(v[0]);
                let dy = (u[1] + u[3]).min(v[1] + v[3]) - u[1].max(v[1]);
                if dx > tol.pixel && dy > tol.pixel {
                    add("OVERLAPS", "bbox_overlap");
                    add("INTERSECTS", "bbox_overlap")
                } else if dx >= -tol.pixel
                    && dy >= -tol.pixel
                    && (dx.abs() <= tol.pixel || dy.abs() <= tol.pixel)
                {
                    add("TOUCHES", "bbox_boundary");
                    add("INTERSECTS", "bbox_boundary")
                }
            }
        }
    }
    canonicalize(state)
}

pub fn mirp_projection(state: &GeometryState) -> Value {
    let provenance = |source: &[String]| json!({"origin":"inference","producer":"reason-geometry","source_ref":source.first().cloned().unwrap_or_else(||state.state_id.clone()),"created_at":"1970-01-01T00:00:00Z","source_chain":source});
    let mut ids = BTreeSet::new();
    for p in &state.primitives {
        if let Some((id, _)) = p.geometry_id.rsplit_once(':') {
            ids.insert(id.to_owned());
        }
    }
    for r in &state.relations {
        ids.insert(r.subject.clone());
        ids.insert(r.object.clone());
    }
    let units:Vec<_>=ids.iter().map(|id|{
        let primitives:Vec<_>=state.primitives.iter().filter(|p|p.geometry_id.starts_with(&format!("{id}:"))).map(|p|json!({"geometry_id":p.geometry_id,"geometry_type":p.geometry_type,"coordinate_system":p.coordinate_system,"parameters":p.parameters,"provenance":p.provenance})).collect();
        let mut chain=state.provenance.clone();for p in &state.primitives {if p.geometry_id.starts_with(&format!("{id}:")){chain.extend(p.provenance.clone())}}sorted_unique(&mut chain);
        json!({"unit_id":format!("ruo:unit:geometry:{id}"),"unit_type":"geometry-object","state":{"status":"ready"},"payload":{"object_id":id,"primitives":primitives},"evidence_refs":[],"lifecycle":"active","provenance":provenance(&chain),"metadata":{}})
    }).collect();
    let mut relations:Vec<Value>=state.relations.iter().map(|r|{
        let key=digest(&(r.subject.as_str(),r.predicate.as_str(),r.object.as_str(),r.rule.as_str())).unwrap_or_default();
        json!({"relation_id":format!("ruo:relation:geometry:{}",&key[7..23]),"source":{"entity_kind":"unit","entity_id":format!("ruo:unit:geometry:{}",r.subject)},"target":{"entity_kind":"unit","entity_id":format!("ruo:unit:geometry:{}",r.object)},"relation_type":format!("domain:geometry:{}",r.predicate.to_ascii_lowercase()),"direction":"directed","evidence_refs":[],"validation_state":"validated","lifecycle":"active","provenance":provenance(&r.provenance),"metadata":{"rule":r.rule}})
    }).collect();
    relations.sort_by(|a, b| a["relation_id"].as_str().cmp(&b["relation_id"].as_str()));
    let graph = json!({"graph_id":format!("ruo:graph:{}",state.state_id),"units":units,"relations":relations,"root_refs":[],"lifecycle":"active","provenance":provenance(&state.provenance),"metadata":{"unknowns":state.unknowns,"conflicts":state.conflicts,"coordinate_systems":state.coordinate_systems}});
    let mut fragment = json!({"schema":"mra-mirp-graph-fragment/0.1","fragment_kind":"graph_fragment","graph":graph});
    fragment["fragment_hash"] = json!(digest(&fragment).unwrap_or_default());
    fragment
}

pub fn execute_ru(
    state: &GeometryState,
    ru: &str,
    arguments: &[String],
    tol: &Tolerance,
) -> Result<(GeometryResult, ReasonTrace), String> {
    let input_hash = digest(state)?;
    if ru == "SpatialRelationRU" {
        let subject = arguments.first().ok_or("GEO-RU-003: subject missing")?;
        let object = arguments.get(1).ok_or("GEO-RU-003: object missing")?;
        let matches: Vec<_> = state
            .relations
            .iter()
            .filter(|r| &r.subject == subject && &r.object == object)
            .collect();
        let mut provenance: Vec<_> = matches.iter().flat_map(|r| r.provenance.clone()).collect();
        sorted_unique(&mut provenance);
        let output = GeometryResult {
            status: if matches.is_empty() {
                "UNKNOWN"
            } else {
                "KNOWN"
            }
            .into(),
            value: json!(matches),
            provenance,
        };
        let trace = ReasonTrace {
            task_id: format!("ru:{ru}"),
            runtime: "GEOMETRY".into(),
            worker_id: "local".into(),
            input_hash,
            operations: vec![
                json!({"ru":ru,"rus":[ru],"ruo":"lookup_relations","arguments":arguments}),
            ],
            output_hash: digest(&output)?,
            provenance: output.provenance.clone(),
            status: output.status.clone(),
        };
        return Ok((output, trace));
    }
    if ru == "TransformRU" {
        let id = arguments.first().ok_or("GEO-RU-003: primitive missing")?;
        let matrix: [f64; 6] =
            serde_json::from_str(arguments.get(1).ok_or("GEO-RU-003: matrix missing")?)
                .map_err(|e| format!("GEO-RU-003: {e}"))?;
        let primitive = state
            .primitives
            .iter()
            .find(|p| &p.geometry_id == id)
            .ok_or("GEO-RU-001: primitive missing")?;
        let transformed = transform(primitive, matrix)?;
        let output = GeometryResult {
            status: "KNOWN".into(),
            value: json!(transformed),
            provenance: transformed.provenance.clone(),
        };
        let trace = ReasonTrace {
            task_id: format!("ru:{ru}"),
            runtime: "GEOMETRY".into(),
            worker_id: "local".into(),
            input_hash,
            operations: vec![json!({"ru":ru,"rus":[ru],"ruo":"transform","arguments":arguments})],
            output_hash: digest(&output)?,
            provenance: output.provenance.clone(),
            status: output.status.clone(),
        };
        return Ok((output, trace));
    }
    let a = state
        .primitives
        .iter()
        .find(|p| Some(&p.geometry_id) == arguments.first());
    if a.is_none()
        || (arguments.len() > 1
            && !state
                .primitives
                .iter()
                .any(|p| p.geometry_id == arguments[1]))
    {
        let conflict = arguments
            .iter()
            .any(|id| state.conflicts.iter().any(|v| v["geometry_id"] == *id));
        let status = if conflict { "CONFLICT" } else { "UNKNOWN" };
        let output = GeometryResult {
            status: status.into(),
            value: Value::Null,
            provenance: state.provenance.clone(),
        };
        let trace = ReasonTrace {
            task_id: format!("ru:{}", ru),
            runtime: "GEOMETRY".into(),
            worker_id: "local".into(),
            input_hash,
            operations: vec![
                json!({"ru":ru,"rus":[ru],"ruo":"resolve_input","arguments":arguments,"output_status":status}),
            ],
            output_hash: digest(&output)?,
            provenance: output.provenance.clone(),
            status: status.into(),
        };
        return Ok((output, trace));
    }
    let a = a.unwrap();
    let b = arguments
        .get(1)
        .and_then(|id| state.primitives.iter().find(|p| &p.geometry_id == id));
    let c = arguments
        .get(2)
        .and_then(|id| state.primitives.iter().find(|p| &p.geometry_id == id));
    let op = match ru {
        "DistanceRU" => "distance",
        "IntersectionRU" => "intersect",
        "ContainmentRU" => "contains",
        "OverlapRU" => "overlap",
        "AngleRU" => "angle",
        _ => return Err("GEO-RU-002: unknown RU".into()),
    };
    let output = operate(op, a, b, c, tol)?;
    let trace = ReasonTrace {
        task_id: format!("ru:{}", ru),
        runtime: "GEOMETRY".into(),
        worker_id: "local".into(),
        input_hash,
        operations: vec![
            json!({"ru":ru,"rus":[ru],"ruo":op,"arguments":arguments,"output_status":output.status}),
        ],
        output_hash: digest(&output)?,
        provenance: output.provenance.clone(),
        status: output.status.clone(),
    };
    Ok((output, trace))
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ReasonStep {
    pub ru: String,
    pub arguments: Vec<String>,
}

pub fn execute_rus(
    state: &GeometryState,
    steps: &[ReasonStep],
    tol: &Tolerance,
) -> Result<(Vec<GeometryResult>, ReasonTrace), String> {
    let input_hash = digest(state)?;
    let mut results = Vec::new();
    let mut operations = Vec::new();
    let mut provenance = Vec::new();
    for step in steps {
        let (result, trace) = execute_ru(state, &step.ru, &step.arguments, tol)?;
        provenance.extend(result.provenance.clone());
        operations.extend(trace.operations);
        results.push(result);
    }
    sorted_unique(&mut provenance);
    let status = if results.iter().any(|r| r.status == "CONFLICT") {
        "CONFLICT"
    } else if results.iter().any(|r| r.status == "UNKNOWN") {
        "UNKNOWN"
    } else {
        "KNOWN"
    };
    let trace = ReasonTrace {
        task_id: format!("rus:{}", digest(steps)?),
        runtime: "GEOMETRY".into(),
        worker_id: "local".into(),
        input_hash,
        operations,
        output_hash: digest(&results)?,
        provenance,
        status: status.into(),
    };
    Ok((results, trace))
}

#[cfg(test)]
mod tests;
