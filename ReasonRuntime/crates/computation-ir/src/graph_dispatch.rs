//! Bounded-walk summary without materializing exponentially many paths.
use crate::value::{StructValue, Value};
use crate::vm::RuntimeError;
use std::{
    cell::RefCell,
    collections::{HashMap, HashSet, VecDeque},
    rc::Rc,
};

type Key = (Rc<str>, Rc<str>, i64, i64, i64, i64, i64);
struct Edge {
    id: Rc<str>,
    source: i64,
    target: i64,
    known: bool,
    active: bool,
    negative: bool,
}
struct Budget {
    used: i64,
    limit: i64,
}
impl Budget {
    fn tick(&mut self) -> Result<(), ()> {
        if self.used >= self.limit {
            return Err(());
        }
        self.used += 1;
        Ok(())
    }
}
fn bad() -> RuntimeError {
    RuntimeError::new("GRAPH-003", "graph.summarize requires typed Unit/EvidenceBinding records, Int entities and integer bounds")
}
fn int(v: &Value) -> Result<i64, RuntimeError> {
    if let Value::Int(x) = v {
        Ok(*x)
    } else {
        Err(bad())
    }
}
fn text(v: &Value) -> Result<Rc<str>, RuntimeError> {
    if let Value::String(x) = v {
        Ok(x.clone())
    } else {
        Err(bad())
    }
}
fn boolean(v: &Value) -> Result<bool, RuntimeError> {
    if let Value::Bool(x) = v {
        Ok(*x)
    } else {
        Err(bad())
    }
}
fn array(v: &Value) -> Result<std::cell::Ref<'_, Vec<Value>>, RuntimeError> {
    if let Value::Array(x) = v {
        Ok(x.borrow())
    } else {
        Err(bad())
    }
}
fn fields(v: &Value) -> Result<std::cell::Ref<'_, HashMap<String, Value>>, RuntimeError> {
    if let Value::Struct(x) = v {
        Ok(x.fields.borrow())
    } else {
        Err(bad())
    }
}
fn get<'a>(f: &'a HashMap<String, Value>, key: &str) -> Result<&'a Value, RuntimeError> {
    f.get(key).ok_or_else(bad)
}
fn key(f: &HashMap<String, Value>, evidence: Rc<str>) -> Result<Key, RuntimeError> {
    Ok((
        evidence,
        text(get(f, "unit_id")?)?,
        int(get(f, "subject")?)?,
        int(get(f, "predicate")?)?,
        int(get(f, "object")?)?,
        int(get(f, "polarity")?)?,
        int(get(f, "revision")?)?,
    ))
}
fn strings(values: impl IntoIterator<Item = Rc<str>>) -> Value {
    Value::Array(Rc::new(RefCell::new(
        values.into_iter().map(Value::String).collect(),
    )))
}
fn result(
    status: &str,
    admitted: bool,
    resource_limit: bool,
    dependencies: Vec<Rc<str>>,
    proof: Vec<Rc<str>>,
    work: i64,
) -> Value {
    Value::Struct(Rc::new(StructValue {
        type_name: "GraphSummary".into(),
        fields: RefCell::new(HashMap::from([
            ("status".into(), Value::String(Rc::from(status))),
            ("admitted".into(), Value::Bool(admitted)),
            ("resource_limit".into(), Value::Bool(resource_limit)),
            ("dependencies".into(), strings(dependencies)),
            ("proof_path".into(), strings(proof)),
            ("work".into(), Value::Int(work)),
        ])),
    }))
}
struct Reach {
    distance: HashMap<i64, usize>,
    parent: HashMap<i64, usize>,
    goal_edge: Option<usize>,
}
fn reach(
    edges: &[Edge],
    adjacency: &HashMap<i64, Vec<usize>>,
    start: i64,
    goal: i64,
    depth: usize,
    reverse: bool,
    known_only: bool,
    budget: &mut Budget,
) -> Result<Reach, ()> {
    let mut r = Reach {
        distance: HashMap::from([(start, 0)]),
        parent: HashMap::new(),
        goal_edge: None,
    };
    let mut queue = VecDeque::from([start]);
    while let Some(node) = queue.pop_front() {
        let d = r.distance[&node];
        if d >= depth {
            continue;
        }
        if let Some(indices) = adjacency.get(&node) {
            for &i in indices {
                budget.tick()?;
                let e = &edges[i];
                if known_only && !e.known {
                    continue;
                }
                let target = if reverse { e.source } else { e.target };
                // A nonempty cycle is a valid witness when start == goal.
                if target == goal && r.goal_edge.is_none() {
                    r.goal_edge = Some(i);
                }
                if let std::collections::hash_map::Entry::Vacant(entry) = r.distance.entry(target) {
                    entry.insert(d + 1);
                    r.parent.insert(target, i);
                    queue.push_back(target);
                }
            }
        }
    }
    Ok(r)
}

pub fn summarize(args: &[Value]) -> Result<Value, RuntimeError> {
    if args.len() != 7 {
        return Err(RuntimeError::new(
            "GRAPH-002",
            "graph.summarize expects 7 arguments",
        ));
    }
    let units = array(&args[0])?;
    let trusted = array(&args[1])?;
    let entities = array(&args[2])?;
    let start = int(&args[3])?;
    let goal = int(&args[4])?;
    let depth = int(&args[5])?;
    let limit = int(&args[6])?;
    if depth < 1 || limit < 1 || limit > 100_000_000 {
        return Err(RuntimeError::new(
            "GRAPH-004",
            "depth must be positive and work_budget in 1..=100000000",
        ));
    }
    let mut budget = Budget { used: 0, limit };
    let limited = |b: &Budget| result("UNKNOWN", false, true, vec![], vec![], b.used);
    let mut has_start = false;
    let mut has_goal = false;
    for entity in entities.iter() {
        if budget.tick().is_err() {
            return Ok(limited(&budget));
        }
        let id = int(entity)?;
        has_start |= id == start;
        has_goal |= id == goal;
    }
    if !has_start || !has_goal {
        return Ok(result("INVALID", false, false, vec![], vec![], budget.used));
    }
    let mut bindings = HashSet::new();
    for binding in trusted.iter() {
        if budget.tick().is_err() {
            return Ok(limited(&budget));
        }
        let f = fields(binding)?;
        bindings.insert(key(&f, text(get(&f, "evidence_id")?)?)?);
    }
    let mut ids = HashSet::new();
    let mut edges = Vec::with_capacity(units.len().min(limit as usize));
    let mut forward: HashMap<i64, Vec<usize>> = HashMap::new();
    let mut backward: HashMap<i64, Vec<usize>> = HashMap::new();
    for unit in units.iter() {
        if budget.tick().is_err() {
            return Ok(limited(&budget));
        }
        let f = fields(unit)?;
        let id = text(get(&f, "unit_id")?)?;
        if !ids.insert(id.clone()) {
            return Ok(result("INVALID", false, false, vec![], vec![], budget.used));
        }
        let status = text(get(&f, "semantic_status")?)?;
        let revision = int(get(&f, "revision")?)?;
        let provenance = array(get(&f, "provenance")?)?;
        for item in provenance.iter() {
            if budget.tick().is_err() {
                return Ok(limited(&budget));
            }
            text(item)?;
        }
        let mut valid = !boolean(get(&f, "revoked")?)?
            && revision >= 1
            && revision == int(get(&f, "current_revision")?)?
            && !provenance.is_empty()
            && status.as_ref() != "INVALID";
        let evidence = array(get(&f, "evidence")?)?;
        if status.as_ref() == "VERIFIED" {
            valid &= !evidence.is_empty();
        }
        for item in evidence.iter() {
            if budget.tick().is_err() {
                return Ok(limited(&budget));
            }
            let evidence_id = text(item)?;
            if status.as_ref() == "VERIFIED" {
                valid &= bindings.contains(&key(&f, evidence_id)?);
            }
        }
        let negative_evidence = array(get(&f, "negative_evidence")?)?;
        for item in negative_evidence.iter() {
            if budget.tick().is_err() {
                return Ok(limited(&budget));
            }
            text(item)?;
        }
        let contradicted = status.as_ref() == "CONTRADICTED" || !negative_evidence.is_empty();
        let known = valid && !contradicted && status.as_ref() == "VERIFIED";
        let active = valid
            && !contradicted
            && matches!(status.as_ref(), "VERIFIED" | "UNKNOWN" | "HYPOTHESIS");
        let source = int(get(&f, "subject")?)?;
        let target = int(get(&f, "object")?)?;
        let predicate = int(get(&f, "predicate")?)?;
        let polarity = int(get(&f, "polarity")?)?;
        let active = active && predicate == 1 && polarity == 1;
        let negative =
            known && predicate == 1 && polarity == -1 && source == start && target == goal;
        let index = edges.len();
        edges.push(Edge {
            id,
            source,
            target,
            known,
            active,
            negative,
        });
        if active {
            forward.entry(source).or_default().push(index);
            backward.entry(target).or_default().push(index);
        }
    }
    // Three breadth-first searches suffice for exact bounded-walk reachability,
    // a verified witness, and the union of unknown edges on any goal walk.
    let from = match reach(
        &edges,
        &forward,
        start,
        goal,
        depth as usize,
        false,
        false,
        &mut budget,
    ) {
        Ok(x) => x,
        Err(()) => return Ok(limited(&budget)),
    };
    let to = match reach(
        &edges,
        &backward,
        goal,
        start,
        depth as usize,
        true,
        false,
        &mut budget,
    ) {
        Ok(x) => x,
        Err(()) => return Ok(limited(&budget)),
    };
    let verified = match reach(
        &edges,
        &forward,
        start,
        goal,
        depth as usize,
        false,
        true,
        &mut budget,
    ) {
        Ok(x) => x,
        Err(()) => return Ok(limited(&budget)),
    };
    let mut any = false;
    let mut negative = false;
    let mut dependencies = vec![];
    for edge in &edges {
        if budget.tick().is_err() {
            return Ok(limited(&budget));
        }
        negative |= edge.negative;
        if edge.active {
            if let (Some(&a), Some(&b)) = (
                from.distance.get(&edge.source),
                to.distance.get(&edge.target),
            ) {
                if a + 1 + b <= depth as usize {
                    any = true;
                    if !edge.known {
                        dependencies.push(edge.id.clone());
                    }
                }
            }
        }
    }
    let mut proof = vec![];
    if let Some(last) = verified.goal_edge {
        proof.push(edges[last].id.clone());
        let mut node = edges[last].source;
        while node != start {
            if budget.tick().is_err() {
                return Ok(limited(&budget));
            }
            let i = verified.parent[&node];
            proof.push(edges[i].id.clone());
            node = edges[i].source;
        }
        proof.reverse();
    }
    let status = if negative && any {
        "CONTRADICTED"
    } else if !proof.is_empty() {
        "VERIFIED"
    } else if any {
        "HYPOTHESIS"
    } else {
        "UNKNOWN"
    };
    Ok(result(
        status,
        true,
        false,
        dependencies,
        proof,
        budget.used,
    ))
}
