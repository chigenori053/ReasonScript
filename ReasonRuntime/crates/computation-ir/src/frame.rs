//! Function-frame variable storage.
//!
//! Every name a function's IR can read or bind (parameters, locals,
//! assignment targets, loop-trace counters, relation-filter and match
//! bindings) gets a fixed slot when the VM is constructed, and the IR node
//! that names it records that slot (`ir::UNRESOLVED_SLOT` until then). A
//! `Frame` stores those names in a `Vec` indexed by slot, so the hot
//! `local`/`assign` paths no longer hash the variable name on every access.
//! Names injected from outside the function body that it never mentions
//! (earlier calculation results, Reason Object and reasoning bindings) live
//! in `extra`, so a frame still exposes exactly the bindings the former
//! name-keyed map held -- traces and Tensor root collection see the same set.

use std::collections::HashMap;
use std::rc::Rc;

use crate::ir::{Expr, Function, Instruction, Pattern, Terminator, UNRESOLVED_SLOT};
use crate::value::Value;

/// Assigns a slot to every name `function` can read or bind and records it
/// on the naming IR nodes. Parameters take the first slots, in order.
pub(crate) fn layout_function(function: &Function) -> SlotLayout {
    let mut layout = SlotLayout::default();
    for parameter in &function.parameters {
        layout.intern(parameter);
    }
    for block in &function.blocks {
        for instruction in &block.instructions {
            match instruction {
                Instruction::Assign {
                    target,
                    expr,
                    target_slot,
                } => {
                    visit_expr(expr, &mut layout);
                    target_slot.set(layout.intern(target));
                }
                Instruction::IndexAssign {
                    collection,
                    index,
                    expr,
                } => {
                    visit_expr(collection, &mut layout);
                    visit_expr(index, &mut layout);
                    visit_expr(expr, &mut layout);
                }
                Instruction::FieldAssign { object, expr, .. } => {
                    visit_expr(object, &mut layout);
                    visit_expr(expr, &mut layout);
                }
                Instruction::Expr { expr } => visit_expr(expr, &mut layout),
                Instruction::TraceLoopStart {
                    counter,
                    counter_slot,
                    ..
                } => counter_slot.set(layout.intern(counter)),
                Instruction::TraceLoopEnd { .. } => {}
            }
        }
        match &block.terminator {
            Terminator::Branch { condition, .. } => visit_expr(condition, &mut layout),
            Terminator::Result { value } | Terminator::Return { value } => {
                visit_expr(value, &mut layout)
            }
            Terminator::Match { subject, arms } => {
                visit_expr(subject, &mut layout);
                for arm in arms {
                    visit_pattern(&arm.pattern, &mut layout);
                    if let Some(guard) = &arm.guard {
                        visit_expr(guard, &mut layout);
                    }
                }
            }
            Terminator::Jump { .. } | Terminator::Trap { .. } => {}
        }
    }
    layout
}

fn visit_pattern(pattern: &Pattern, layout: &mut SlotLayout) {
    match pattern {
        Pattern::Binding { name } => {
            layout.intern(name);
        }
        Pattern::OptionalSome { pattern } => visit_pattern(pattern, layout),
        Pattern::Struct { fields, .. } => {
            for field in fields.values() {
                visit_pattern(field, layout);
            }
        }
        Pattern::Or { alternatives } => {
            for alternative in alternatives {
                visit_pattern(alternative, layout);
            }
        }
        Pattern::Wildcard
        | Pattern::Literal { .. }
        | Pattern::Range { .. }
        | Pattern::EnumValue { .. }
        | Pattern::OptionalNone => {}
    }
}

fn visit_exprs(exprs: &[Expr], layout: &mut SlotLayout) {
    for expr in exprs {
        visit_expr(expr, layout);
    }
}

fn visit_expr(expr: &Expr, layout: &mut SlotLayout) {
    match expr {
        Expr::Local { name, slot, .. } => slot.set(layout.intern(name)),
        Expr::RelationFilter {
            source,
            binding,
            binding_slot,
            predicate,
            ..
        } => {
            visit_expr(source, layout);
            binding_slot.set(layout.intern(binding));
            visit_expr(predicate, layout);
        }
        Expr::Array { elements, .. } => visit_exprs(elements, layout),
        Expr::Struct { fields, .. } => {
            for field in fields.values() {
                visit_expr(field, layout);
            }
        }
        Expr::Unary { operand, .. } => visit_expr(operand, layout),
        Expr::Binary { left, right, .. }
        | Expr::Comparison { left, right, .. }
        | Expr::Logical { left, right, .. }
        | Expr::CallArrayConcat { left, right, .. } => {
            visit_expr(left, layout);
            visit_expr(right, layout);
        }
        Expr::Index {
            collection, index, ..
        } => {
            visit_expr(collection, layout);
            visit_expr(index, layout);
        }
        Expr::Member { object, .. } => visit_expr(object, layout),
        Expr::CallTensor { arguments, .. }
        | Expr::CallVision { arguments, .. }
        | Expr::CallRuo { arguments, .. }
        | Expr::CallOptimizer { arguments, .. }
        | Expr::CallRelation { arguments, .. }
        | Expr::CallSemanticEvent { arguments, .. }
        | Expr::CallReasoning { arguments, .. }
        | Expr::CallString { arguments, .. }
        | Expr::CallFoundation { arguments, .. }
        | Expr::CallConsole { arguments, .. }
        | Expr::CallFunction { arguments, .. } => visit_exprs(arguments, layout),
        Expr::CallArrayBuilder {
            builder, arguments, ..
        } => {
            visit_expr(builder, layout);
            visit_exprs(arguments, layout);
        }
        Expr::CallArrayAppend {
            collection, item, ..
        }
        | Expr::CallArrayPrepend {
            collection, item, ..
        } => {
            visit_expr(collection, layout);
            visit_expr(item, layout);
        }
        Expr::CallCast { argument, .. } => visit_expr(argument, layout),
        Expr::OptionalSome { value, .. } => visit_expr(value, layout),
        Expr::Assert { condition, .. } => visit_expr(condition, layout),
        Expr::AssertEq {
            actual, expected, ..
        } => {
            visit_expr(actual, layout);
            visit_expr(expected, layout);
        }
        Expr::Const { .. }
        | Expr::ArrayBuilder { .. }
        | Expr::EnumValue { .. }
        | Expr::OptionalNone { .. } => {}
    }
}

#[derive(Debug, Default)]
pub(crate) struct SlotLayout {
    names: Vec<String>,
    index: HashMap<String, u32>,
}

impl SlotLayout {
    /// Returns `name`'s slot, assigning the next one on first use.
    pub(crate) fn intern(&mut self, name: &str) -> u32 {
        if let Some(&slot) = self.index.get(name) {
            return slot;
        }
        let slot = u32::try_from(self.names.len()).expect("frame slot count fits in u32");
        assert!(
            slot != UNRESOLVED_SLOT,
            "frame slot count exceeds u32 range"
        );
        self.names.push(name.to_owned());
        self.index.insert(name.to_owned(), slot);
        slot
    }

    pub(crate) fn slot_of(&self, name: &str) -> Option<u32> {
        self.index.get(name).copied()
    }
}

#[derive(Clone)]
pub(crate) struct Frame {
    layout: Rc<SlotLayout>,
    slots: Vec<Option<Value>>,
    extra: HashMap<String, Value>,
}

impl Frame {
    pub(crate) fn new(layout: Rc<SlotLayout>) -> Self {
        Frame {
            slots: vec![None; layout.names.len()],
            layout,
            extra: HashMap::new(),
        }
    }

    /// Reads a name through its resolved slot, falling back to a by-name
    /// lookup for a node the layout pass did not annotate.
    pub(crate) fn get_slot(&self, slot: u32, name: &str) -> Option<&Value> {
        match self.slots.get(slot as usize) {
            Some(value) => value.as_ref(),
            None => self.get(name),
        }
    }

    pub(crate) fn get(&self, name: &str) -> Option<&Value> {
        match self.layout.slot_of(name) {
            Some(slot) => self.slots[slot as usize].as_ref(),
            None => self.extra.get(name),
        }
    }

    /// Binds `name` through its resolved slot, returning the previous value.
    pub(crate) fn set_slot(&mut self, slot: u32, name: &str, value: Value) -> Option<Value> {
        match self.slots.get_mut(slot as usize) {
            Some(entry) => entry.replace(value),
            None => self.insert(name, value),
        }
    }

    pub(crate) fn insert(&mut self, name: &str, value: Value) -> Option<Value> {
        match self.layout.slot_of(name) {
            Some(slot) => self.slots[slot as usize].replace(value),
            None => self.extra.insert(name.to_owned(), value),
        }
    }

    pub(crate) fn remove(&mut self, name: &str) -> Option<Value> {
        match self.layout.slot_of(name) {
            Some(slot) => self.slots[slot as usize].take(),
            None => self.extra.remove(name),
        }
    }

    /// Every bound name, in no particular order (callers that need an
    /// order sort, exactly as with the former `HashMap` iteration).
    pub(crate) fn iter(&self) -> impl Iterator<Item = (&str, &Value)> {
        self.layout
            .names
            .iter()
            .zip(&self.slots)
            .filter_map(|(name, value)| value.as_ref().map(|value| (name.as_str(), value)))
            .chain(
                self.extra
                    .iter()
                    .map(|(name, value)| (name.as_str(), value)),
            )
    }

    pub(crate) fn values(&self) -> impl Iterator<Item = &Value> {
        self.iter().map(|(_, value)| value)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slots_and_extra_names_behave_like_one_map() {
        let mut layout = SlotLayout::default();
        let x = layout.intern("x");
        assert_eq!(layout.intern("x"), x);
        let mut frame = Frame::new(Rc::new(layout));

        assert!(frame.get("x").is_none());
        assert!(frame.set_slot(x, "x", Value::Int(1)).is_none());
        assert!(matches!(
            frame.insert("x", Value::Int(2)),
            Some(Value::Int(1))
        ));
        assert!(matches!(frame.get_slot(x, "x"), Some(Value::Int(2))));

        // A name outside the layout is still stored and visible.
        assert!(frame.insert("outer", Value::Bool(true)).is_none());
        assert!(matches!(frame.get("outer"), Some(Value::Bool(true))));
        assert!(matches!(
            frame.get_slot(UNRESOLVED_SLOT, "outer"),
            Some(Value::Bool(true))
        ));
        let mut names: Vec<_> = frame.iter().map(|(name, _)| name).collect();
        names.sort_unstable();
        assert_eq!(names, ["outer", "x"]);

        assert!(matches!(frame.remove("x"), Some(Value::Int(2))));
        assert!(frame.get_slot(x, "x").is_none());
        assert_eq!(frame.values().count(), 1);
    }
}
