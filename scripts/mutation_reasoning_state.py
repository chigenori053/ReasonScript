#!/usr/bin/env python3
"""Mutation gate for the reasoning-state runtime.

Each mutant breaks one contract of the runtime (state, revision, causal
relation, provenance, or hash) and must be caught by the Rust unit tests or the
Python integration tests. Sources are restored byte for byte after every mutant,
and the script fails if any mutant survives, does not apply, or does not compile.

    scripts/mutation_reasoning_state.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "ReasonRuntime"
SRC = RUNTIME / "crates/computation-ir/src"
HOST = RUNTIME / "target/debug/reason-runtime-host"
PYTHON_TESTS = [
    "computation_ir_tests/test_reasoning_state.py",
    "computation_ir_tests/test_native_state_causality.py",
    "computation_ir_tests/test_reason_objects.py",
    "computation_ir_tests/test_causal_relevance.py",
]

# (gate, name, file, original text, mutated text)
MUTATIONS = [
    ("existing", "no-op detection disabled", "reasoning_state.rs",
     "if value.is_some_and(|value| self.fields[index] != *value) {", "if value.is_some() {"),
    ("existing", "stale search_bound", "reasoning_state.rs",
     "(F::SearchBound, V::Int(quotient.isqrt())),", "(F::SearchBound, V::Int(remaining.isqrt())),"),
    ("existing", "double revision increment", "reasoning_state.rs",
     "self.revision += 1;\n        self.metrics.reasoning_state_revision_count += 1;",
     "self.revision += 2;\n        self.metrics.reasoning_state_revision_count += 1;"),
    ("existing", "rejected verification modifies state", "reasoning_state.rs",
     '"CANDIDATE_PREDICATE" if verified => increment(),', '"CANDIDATE_PREDICATE" => increment(),'),
    ("r4", "changed field bit missing", "reasoning_state.rs",
     "changed.0 |= 1 << index;", "changed.0 |= (1 << index) & !ReasonStateField::SearchBound.bit();"),
    ("r4", "wrong source RU", "reason_structure.rs",
     "self.apply_state_effect(RuRef(index as u32), effect, evidence_ref);",
     "self.apply_state_effect(RuRef(index.saturating_sub(1) as u32), effect, evidence_ref);"),
    ("r4", "wrong Evidence index", "reason_structure.rs",
     "evidence_ref = Some(EvidenceRef(self.executable_evidence.len() as u32 - 1));",
     "evidence_ref = Some(EvidenceRef(self.executable_evidence.len().saturating_sub(2) as u32));"),
    ("r4", "missing revision provenance", "state_causality.rs",
     '"state_revision_after": transition.revision_after,', '"state_revision_after": transition.revision_before,'),
    ("r4", "transition hash missing transition", "reasoning_state.rs",
     "for (position, transition) in transitions.iter().enumerate() {",
     "for (position, transition) in transitions.iter().skip(1).enumerate() {"),
    ("r4", "wrong ENABLES transition", "state_causality.rs",
     "transition: self.transitions.len() as u32 - 1,", "transition: 0,"),
    ("r4", "state hash missing goal_status", "reasoning_state.rs",
     "for (position, field) in ReasonStateField::BY_NAME.into_iter().enumerate() {\n"
     "        if position > 0 {\n            buf.push(b',');\n        }\n        buf.push(b'\"');\n"
     "        buf.extend_from_slice(field.name().as_bytes());\n        buf.extend_from_slice(b\"\\\":\");\n"
     "        fields[field.index()].write_json(&mut buf);",
     "for (position, field) in ReasonStateField::BY_NAME.into_iter().filter(|f| *f != ReasonStateField::GoalStatus).enumerate() {\n"
     "        if position > 0 {\n            buf.push(b',');\n        }\n        buf.push(b'\"');\n"
     "        buf.extend_from_slice(field.name().as_bytes());\n        buf.extend_from_slice(b\"\\\":\");\n"
     "        fields[field.index()].write_json(&mut buf);"),
    # RUS / RUO projection
    ("objects", "RUO before/after swapped", "reason_objects.rs",
     "rus_before_ref: rus_id(before),\n            rus_after_ref: rus_id(after),",
     "rus_before_ref: rus_id(after),\n            rus_after_ref: rus_id(before),"),
    ("objects", "RUS parent revision wrong", "reason_objects.rs",
     "parent_revision: Some(revision - 1),", "parent_revision: Some(revision.saturating_sub(2)),"),
    ("objects", "RUO Evidence refs dropped", "reason_objects.rs",
     "            evidence_refs,\n            relation_refs,", "            evidence_refs: Vec::new(),\n            relation_refs,"),
    ("objects", "RUO omits the transition's causal relations", "reason_objects.rs",
     "if let Some(revision) = updated_at[index] {", "if let Some(revision) = updated_at[index].filter(|_| false) {"),
    ("objects", "RUS sequence hash skips a state", "reason_objects.rs",
     "record_hash(states, |buf, state| {", "record_hash(&states[1..], |buf, state| {"),
    ("objects", "RU state binding shifted", "reason_objects.rs",
     "let before = u64::from(unit.state_before);", "let before = u64::from(unit.state_before.saturating_sub(1));"),
    ("objects", "RU begin revision not recorded", "reason_structure.rs",
     "state_before: self.reasoning_state.revision() as u32,", "state_before: 0,"),
    ("objects", "initial source RU not recorded", "reason_structure.rs",
     "self.reasoning_state.set_initial_source_ru(source_ru);", "let _ = source_ru;"),
    ("objects", "transitions not retained for RUS-only mode", "state_causality.rs",
     "if !self.enabled() && !self.retain {", "if !self.enabled() {"),
    ("objects", "retained transitions leak into state causality", "state_causality.rs",
     "let reported: &[RuntimeStateTransition] = if self.enabled() {", "let reported: &[RuntimeStateTransition] = if self.enabled() || self.retain {"),
    # Causal relevance classification and the relevant view
    ("relevance", "CAUSES classified as noise", "causal_relevance.rs",
     '("CAUSES", "CONFIRMED") => {', '("CAUSES", "CONFIRMED") => Edge::Temporal,\n        ("NEVER", "CONFIRMED") => {'),
    ("relevance", "CONFLICT classified as noise", "causal_relevance.rs",
     '(_, "CONFLICT") => Edge::Unresolved(ReasonCode::Conflict),', '(_, "CONFLICT") => Edge::Temporal,'),
    ("relevance", "search exclusion candidate removed", "causal_relevance.rs",
     "bits |= ReasonCode::SearchExclusion.bit();\n                        raise(RelevanceClass::Exclusion, &mut class);",
     "bits |= ReasonCode::SearchExclusion.bit();"),
    ("relevance", "goal root removed", "causal_relevance.rs",
     'roots.push((unit.id.clone(), index as u32, "GOAL_EVALUATION"));', "let _ = index;"),
    ("relevance", "wrong causal edge traversed (forward)", "causal_relevance.rs",
     "let (source, _, edge) = edges[*edge_index as usize];\n            if !edge.traversable() {\n                continue;\n            }\n            let next",
     "let (_, source, edge) = edges[*edge_index as usize];\n            if !edge.traversable() {\n                continue;\n            }\n            let next"),
    ("relevance", "temporal adjacency propagates relevance", "causal_relevance.rs",
     "!matches!(self, Self::Temporal | Self::Unresolved(_))", "!matches!(self, Self::Unresolved(_))"),
    ("relevance", "depth limit ignored", "causal_relevance.rs", "if next > limit {", "if false {"),
    ("relevance", "missing root not fail-open", "causal_relevance.rs", "if roots.is_empty() {", "if false {"),
    ("relevance", "state cause only supporting", "causal_relevance.rs",
     "Self::StateCause | Self::Updates => (Essential, ReasonCode::StateCause),", "Self::StateCause | Self::Updates => (Supporting, ReasonCode::StateCause),"),
    ("relevance", "unresolved never applied", "causal_relevance.rs",
     "if class > RelevanceClass::Unresolved && unresolved {", "if false && class > RelevanceClass::Unresolved && unresolved {"),
    ("relevance", "reason codes missing from the hash", "causal_relevance.rs",
     "crate::reason_objects::push_list(&mut buf, &codes);", "crate::reason_objects::push_list(&mut buf, &Vec::<&str>::new());"),
    ("relevance", "temporal relations kept in the relevant view", "causal_relevance.rs",
     'relation.relation_kind != "TEMPORAL"\n            && !self.dropped', 'true\n            && !self.dropped'),
    ("relevance", "noise never dropped from the relevant view", "causal_relevance.rs",
     "fail_open || classification.keeps_unit(index)", "true"),
    ("relevance", "dropped RU still owns its relations", "reason_objects.rs",
     "if keep.is_some() {\n        for (index, unit) in units.iter().enumerate() {", "if false {\n        for (index, unit) in units.iter().enumerate() {"),
    ("extra", "verification stops reading current_candidate", "state_causality.rs",
     "F::Remaining.bit() | F::SearchBound.bit() | F::CurrentCandidate.bit()", "F::Remaining.bit() | F::SearchBound.bit()"),
]


def sh(command: list[str], cwd: Path = ROOT, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})


def build() -> bool:
    return sh(["cargo", "build", "-p", "reasonscript-computation-runtime-cli"], RUNTIME).returncode == 0


def run_mutant(gate: str, name: str, file: str, old: str, new: str) -> dict:
    path = SRC / file
    original = path.read_bytes()
    text = original.decode("utf-8")
    result = {"gate": gate, "name": name, "file": file}
    if old not in text:
        return {**result, "outcome": "not-applied"}
    try:
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
        if not build():
            return {**result, "outcome": "compile-error"}
        rust = sh(["cargo", "test", "-p", "reasonscript-computation-ir"], RUNTIME).returncode != 0
        python = sh([sys.executable, "-m", "pytest", *PYTHON_TESTS, "-q", "-p", "no:cacheprovider", "-x"],
                    env={"REASONSCRIPT_RUNTIME_HOST": str(HOST)}).returncode != 0
        return {**result, "rust_detected": rust, "python_detected": python,
                "outcome": "detected" if rust or python else "SURVIVED"}
    finally:
        path.write_bytes(original)  # a fresh mtime, so cargo rebuilds the restored source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    parser.add_argument("--gate", action="append", help="run only these gates (repeatable)")
    parser.add_argument("--name", help="run only mutants whose name contains this text")
    args = parser.parse_args()
    mutations = [m for m in MUTATIONS if (not args.gate or m[0] in args.gate) and (not args.name or args.name in m[1])]
    before = {file: (SRC / file).read_bytes() for _, _, file, _, _ in mutations}
    results = [run_mutant(*mutation) for mutation in mutations]
    restored = build() and all((SRC / file).read_bytes() == content for file, content in before.items())
    summary = {
        "mutants": len(results),
        "detected": sum(r["outcome"] == "detected" for r in results),
        "detected_by_rust": sum(bool(r.get("rust_detected")) for r in results),
        "detected_by_python": sum(bool(r.get("python_detected")) for r in results),
        "sources_restored": restored,
        "results": results,
    }
    summary["all_detected"] = summary["detected"] == summary["mutants"] and restored
    for r in results:
        print(f"{r['gate']:9s} {r['name']:46s} {r['outcome']}")
    print(f"{summary['detected']}/{summary['mutants']} detected, sources restored: {restored}")
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["all_detected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
