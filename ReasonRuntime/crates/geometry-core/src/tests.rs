use super::*;
use reasonscript_vision_runtime::spatial::VisualObject;
fn object(id: &str, x: f64) -> VisualObject {
    VisualObject {
        object_id: id.into(),
        object_type: Some("shape".into()),
        candidate_types: vec![],
        bounding_box: Some([x, 0.0, 10.0, 10.0]),
        centroid: Some([x + 5.0, 5.0]),
        contour: vec![],
        keypoints: BTreeMap::new(),
        attributes: BTreeMap::new(),
        confidence: Some(1.0),
        uncertainty: None,
        source: "frame".into(),
        provenance: vec![format!("image:{id}")],
    }
}
fn obs() -> VisualObservation {
    VisualObservation {
        schema_version: VISUAL_PROFILE.into(),
        source_id: "frame".into(),
        coordinate_system: CoordinateSystem::default(),
        objects: vec![object("b", 30.0), object("a", 0.0)],
        observed_relations: vec![],
        unknowns: vec![],
        conflicts: vec![],
        provenance: vec!["image".into()],
    }
}
fn prim(kind: &str, parameters: Value) -> Primitive {
    Primitive {
        geometry_id: format!("p:{kind}"),
        geometry_type: kind.into(),
        coordinate_system: "image-pixel".into(),
        parameters,
        provenance: vec!["test".into()],
    }
}
#[test]
fn foundation_and_canonical() {
    let a = from_visual(&obs()).unwrap();
    let mut reversed = obs();
    reversed.objects.reverse();
    assert_eq!(
        digest(&a).unwrap(),
        digest(&from_visual(&reversed).unwrap()).unwrap()
    );
    for (kind, params) in [
        ("Circle", json!({"center":[0,0],"radius":1})),
        ("Triangle", json!({"vertices":[[0,0],[1,0],[0,1]]})),
        ("Transform", json!({"matrix":[1,0,0,1,0,0]})),
    ] {
        assert!(validate_primitive(&prim(kind, params), &a.coordinate_systems).is_ok())
    }
    assert!(Tolerance {
        pixel: -1.0,
        ..Tolerance::default()
    }
    .validate()
    .is_err())
}
#[test]
fn operations() {
    let a = prim("Point", json!({"xy":[0,0]}));
    let b = prim("Point", json!({"xy":[3,4]}));
    let tol = Tolerance::default();
    assert_eq!(
        operate("distance", &a, Some(&b), None, &tol).unwrap().value,
        json!(5.0)
    );
    assert_eq!(
        operate("distance", &a, None, None, &tol).unwrap().status,
        "UNKNOWN"
    );
    let x = prim("Point", json!({"xy":[3,0]}));
    let y = prim("Point", json!({"xy":[0,4]}));
    assert!(
        (operate("angle", &x, Some(&a), Some(&y), &tol)
            .unwrap()
            .value
            .as_f64()
            .unwrap()
            - std::f64::consts::FRAC_PI_2)
            .abs()
            < 1e-12
    );
    let l = prim("Segment", json!({"start":[0,0],"end":[2,2]}));
    let m = prim("Segment", json!({"start":[0,2],"end":[2,0]}));
    assert_eq!(
        operate("intersect", &l, Some(&m), None, &tol)
            .unwrap()
            .value,
        json!([1.0, 1.0])
    );
    assert_eq!(
        operate("perpendicular", &l, Some(&m), None, &tol)
            .unwrap()
            .value,
        json!(true)
    )
}
#[test]
fn boxes_and_transforms() {
    let a = prim("BoundingBox", json!({"xywh":[0,0,10,10]}));
    let b = prim("BoundingBox", json!({"xywh":[2,2,2,2]}));
    let t = Tolerance {
        pixel: 0.0,
        ..Tolerance::default()
    };
    assert_eq!(
        operate("contains", &a, Some(&b), None, &t).unwrap().value,
        json!(true)
    );
    assert_eq!(
        operate("overlap", &a, Some(&b), None, &t).unwrap().value,
        json!(true)
    );
    let edge = prim("BoundingBox", json!({"xywh":[10,0,2,2]}));
    assert_eq!(
        operate("touches", &a, Some(&edge), None, &t).unwrap().value,
        json!(true)
    );
    assert_eq!(
        translate(&b, 3.0, 4.0).unwrap().parameters["xywh"],
        json!([5.0, 6.0, 2.0, 2.0])
    );
    let p = prim("Point", json!({"xy":[1,0]}));
    assert_eq!(
        scale(&p, 2.0, 3.0).unwrap().parameters["xy"],
        json!([2.0, 0.0])
    );
    assert!(
        (rotate(&p, std::f64::consts::FRAC_PI_2).unwrap().parameters["xy"][1]
            .as_f64()
            .unwrap()
            - 1.0)
            .abs()
            < 1e-12
    )
}
#[test]
fn relations_mirp_and_ru() {
    let mut state = from_visual(&obs()).unwrap();
    derive_relations(&mut state, &Tolerance::default(), 100.0).unwrap();
    assert!(state
        .relations
        .iter()
        .any(|r| r.subject == "a" && r.predicate == "LEFT_OF" && r.object == "b"));
    assert_eq!(
        mirp_projection(&state)["schema"],
        "mra-mirp-graph-fragment/0.1"
    );
    let (r, t) = execute_ru(
        &state,
        "DistanceRU",
        &["a:centroid".into(), "b:centroid".into()],
        &Tolerance::default(),
    )
    .unwrap();
    assert_eq!(r.value, json!(30.0));
    assert_eq!(t.operations[0]["ruo"], "distance")
}
#[test]
fn unknown_conflict_and_merge() {
    let mut input = obs();
    input.objects[0].centroid = None;
    let state = from_visual(&input).unwrap();
    assert!(!state.unknowns.is_empty());
    let (r, _) = execute_ru(
        &state,
        "DistanceRU",
        &["a:centroid".into(), "b:centroid".into()],
        &Tolerance::default(),
    )
    .unwrap();
    assert_eq!(r.status, "UNKNOWN");
    let mut other = obs();
    other.objects[0].object_id = "a".into();
    let conflicted = from_visual(&other).unwrap();
    assert!(!conflicted.conflicts.is_empty());
    let (r, _) = execute_ru(
        &conflicted,
        "DistanceRU",
        &["a:centroid".into(), "b:centroid".into()],
        &Tolerance::default(),
    )
    .unwrap();
    assert_eq!(r.status, "CONFLICT");
    let a = from_visual(&obs()).unwrap();
    let mut changed = obs();
    changed.objects[0].centroid = Some([99.0, 0.0]);
    let b = from_visual(&changed).unwrap();
    let expected = merge(&[a.clone(), b.clone()]).unwrap();
    for _ in 0..3 {
        let reversed = merge(&[b.clone(), a.clone()]).unwrap();
        assert_eq!(expected.primitives, reversed.primitives);
        assert_eq!(expected.conflicts, reversed.conflicts)
    }
}

#[test]
fn executable_rus_and_coordinate_boundary() {
    let mut state = from_visual(&obs()).unwrap();
    derive_relations(&mut state, &Tolerance::default(), 100.0).unwrap();
    let steps = vec![
        ReasonStep {
            ru: "DistanceRU".into(),
            arguments: vec!["a:centroid".into(), "b:centroid".into()],
        },
        ReasonStep {
            ru: "SpatialRelationRU".into(),
            arguments: vec!["a".into(), "b".into()],
        },
        ReasonStep {
            ru: "TransformRU".into(),
            arguments: vec!["a:centroid".into(), "[1,0,0,1,3,4]".into()],
        },
    ];
    let (results, trace) = execute_rus(&state, &steps, &Tolerance::default()).unwrap();
    assert_eq!(results.len(), 3);
    assert_eq!(trace.operations.len(), 3);
    assert_eq!(results[0].value, json!(30.0));
    assert_eq!(results[2].value["parameters"]["xy"], json!([8.0, 9.0]));
    let mut bad = obs();
    bad.coordinate_system.y_direction = "UP".into();
    assert!(from_visual(&bad).is_err());
}

#[test]
fn transforms_preserve_primitive_meaning() {
    let vector = prim("Vector", json!({"xy":[1,2]}));
    assert_eq!(
        translate(&vector, 10.0, 20.0).unwrap().parameters["xy"],
        json!([1.0, 2.0])
    );
    let rectangle = prim("Rectangle", json!({"xywh":[0,0,2,1]}));
    let rotated = rotate(&rectangle, std::f64::consts::FRAC_PI_2).unwrap();
    assert_eq!(rotated.geometry_type, "Polygon");
    assert_eq!(rotated.parameters["vertices"].as_array().unwrap().len(), 4);
    let circle = prim("Circle", json!({"center":[1,2],"radius":3}));
    assert_eq!(
        scale(&circle, 2.0, 2.0).unwrap().parameters["radius"],
        json!(6.0)
    );
    assert!(scale(&circle, 2.0, 3.0).is_err());
    let arc = prim(
        "Arc",
        json!({"center":[1,2],"radius":3,"start_angle":0.0,"end_angle":1.0}),
    );
    assert!(validate_primitive(&arc, &[CoordinateSystem::default()]).is_ok());
    assert!(validate_primitive(
        &prim("Arc", json!({"center":[1,2],"radius":3})),
        &[CoordinateSystem::default()]
    )
    .is_err());
}

#[test]
fn circle_and_collinear_boundaries() {
    let tolerance = Tolerance {
        absolute: 1e-9,
        pixel: 0.0,
        ..Tolerance::default()
    };
    let a = prim("Circle", json!({"center":[0,0],"radius":5}));
    let b = prim("Circle", json!({"center":[8,0],"radius":5}));
    let c = prim("Circle", json!({"center":[10,0],"radius":5}));
    let point = prim("Point", json!({"xy":[5,0]}));
    assert_eq!(
        operate("contains", &a, Some(&point), None, &tolerance)
            .unwrap()
            .value,
        json!(true)
    );
    assert_eq!(
        operate("overlap", &a, Some(&b), None, &tolerance)
            .unwrap()
            .value,
        json!(true)
    );
    assert_eq!(
        operate("touches", &a, Some(&c), None, &tolerance)
            .unwrap()
            .value,
        json!(true)
    );
    assert_eq!(
        operate("intersect", &a, Some(&c), None, &tolerance)
            .unwrap()
            .value,
        json!([5.0, 0.0])
    );
    assert_eq!(
        operate("intersect", &a, Some(&b), None, &tolerance)
            .unwrap()
            .value["points"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
    let first = prim("Segment", json!({"start":[0,0],"end":[4,0]}));
    let second = prim("Segment", json!({"start":[2,0],"end":[6,0]}));
    assert_eq!(
        operate("intersect", &first, Some(&second), None, &tolerance)
            .unwrap()
            .value,
        json!({"segment":[[2.0,0.0],[4.0,0.0]]})
    );
}

#[test]
fn primitive_catalog_and_invalid_boundaries() {
    let systems = [CoordinateSystem::default()];
    let catalog = [
        ("Point", json!({"xy":[0,0]})),
        ("Vector", json!({"xy":[0,0]})),
        ("Line", json!({"start":[0,0],"end":[1,0]})),
        ("Segment", json!({"start":[0,0],"end":[1,0]})),
        ("Ray", json!({"start":[0,0],"end":[1,0]})),
        ("BoundingBox", json!({"xywh":[0,0,0,0]})),
        ("Circle", json!({"center":[0,0],"radius":0})),
        (
            "Arc",
            json!({"center":[0,0],"radius":1,"start_angle":0,"end_angle":1}),
        ),
        ("Triangle", json!({"vertices":[[0,0],[1,0],[0,1]]})),
        ("Rectangle", json!({"xywh":[0,0,1,1]})),
        ("Polygon", json!({"vertices":[[0,0],[1,0],[0,1],[1,1]]})),
        ("Transform", json!({"matrix":[1,0,0,1,0,0]})),
    ];
    for (kind, parameters) in catalog {
        assert!(
            validate_primitive(&prim(kind, parameters), &systems).is_ok(),
            "{kind}"
        );
    }
    assert!(validate_primitive(
        &prim("Circle", json!({"center":[0,0],"radius":-1})),
        &systems
    )
    .is_err());
    assert!(validate_primitive(&prim("Unknown", json!({})), &systems).is_err());
    assert!(validate_primitive(
        &prim("Polygon", json!({"vertices":[[0,0],[1,0]]})),
        &systems
    )
    .is_err());
}

#[test]
fn operation_negative_and_boundary_cases() {
    let tol = Tolerance {
        pixel: 0.0,
        ..Tolerance::default()
    };
    let point = prim("Point", json!({"xy":[0,0]}));
    assert_eq!(
        operate("distance", &point, Some(&point), None, &tol)
            .unwrap()
            .value,
        json!(0.0)
    );
    assert_eq!(
        operate("angle", &point, Some(&point), Some(&point), &tol)
            .unwrap()
            .status,
        "UNKNOWN"
    );
    let first = prim("Segment", json!({"start":[0,0],"end":[1,0]}));
    let far = prim("Segment", json!({"start":[2,-1],"end":[2,1]}));
    assert!(operate("intersect", &first, Some(&far), None, &tol)
        .unwrap()
        .value
        .is_null());
    let parallel = prim("Segment", json!({"start":[0,1],"end":[1,1]}));
    assert_eq!(
        operate("parallel", &first, Some(&parallel), None, &tol)
            .unwrap()
            .value,
        json!(true)
    );
    assert_eq!(
        operate("perpendicular", &first, Some(&parallel), None, &tol)
            .unwrap()
            .value,
        json!(false)
    );
    let box_ = prim("BoundingBox", json!({"xywh":[0,0,1,1]}));
    let outside = prim("Point", json!({"xy":[2,2]}));
    assert_eq!(
        operate("contains", &box_, Some(&outside), None, &tol)
            .unwrap()
            .value,
        json!(false)
    );
    assert!(operate("no_such_operation", &point, None, None, &tol).is_err());
}

#[test]
fn all_spatial_relation_families() {
    let mut input = obs();
    input.objects = vec![object("a", 0.0), object("b", 20.0)];
    let mut above = object("c", 0.0);
    above.bounding_box = Some([0.0, 20.0, 10.0, 10.0]);
    above.centroid = Some([5.0, 25.0]);
    input.objects.push(above);
    let mut inner = object("d", 2.0);
    inner.bounding_box = Some([2.0, 2.0, 2.0, 2.0]);
    inner.centroid = Some([3.0, 3.0]);
    input.objects.push(inner);
    input.objects.push(object("e", 10.0));
    let mut state = from_visual(&input).unwrap();
    derive_relations(
        &mut state,
        &Tolerance {
            pixel: 0.0,
            ..Tolerance::default()
        },
        10.0,
    )
    .unwrap();
    let predicates: BTreeSet<_> = state
        .relations
        .iter()
        .map(|r| r.predicate.as_str())
        .collect();
    for expected in [
        "LEFT_OF",
        "RIGHT_OF",
        "ABOVE",
        "BELOW",
        "INSIDE",
        "CONTAINS",
        "OVERLAPS",
        "TOUCHES",
        "INTERSECTS",
        "NEAR",
        "FAR",
        "ALIGNED_HORIZONTAL",
        "ALIGNED_VERTICAL",
    ] {
        assert!(predicates.contains(expected), "{expected}");
    }
    assert!(!state
        .relations
        .iter()
        .any(|r| r.subject == "b" && r.object == "a" && r.predicate == "LEFT_OF"));
}

#[test]
fn invalid_ru_and_empty_sequence_boundary() {
    let state = from_visual(&obs()).unwrap();
    assert!(execute_ru(
        &state,
        "UnknownRU",
        &["a:centroid".into()],
        &Tolerance::default()
    )
    .is_err());
    let (results, trace) = execute_rus(&state, &[], &Tolerance::default()).unwrap();
    assert!(results.is_empty() && trace.operations.is_empty());
}
