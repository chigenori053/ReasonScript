//! Tensor dtypes, matching `frontend/tensor/runtime.py`'s `DTYPE_BYTES` /
//! `_DTYPE_STRUCT` / `_promote` exactly. Data is stored internally as
//! `f64` regardless of declared dtype (the plan's "compat-reference"
//! numeric mode, section 10: "f32 metadataでも内部はbinary64相当で計算する").
//! `Dtype::cast` is where a value actually gets rounded/truncated to its
//! declared dtype's representable range, mirroring `_cast()`.

use crate::error::{Result, TensorCoreError};

/// Phase 9's two numeric execution modes (plan section 10).
/// `CompatReference` is the existing, default, untouched behavior:
/// every dtype computes and stores at full `f64` precision, sequential
/// reduction order, matching the Python reference exactly (needed for
/// the "checkpoint SHA-256一致" bit-exact parity this whole codebase's
/// test suite already depends on). `NativeFast` adds real `f32`
/// rounding at every Tensor creation for `f32`-dtype Tensors (see
/// `Dtype::round_for_mode`) and permits the parallel/reordered-reduction
/// code paths in `ops.rs` -- never used by `CompatReference`, which
/// keeps calling the original sequential functions unconditionally.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum NumericMode {
    #[default]
    CompatReference,
    NativeFast,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Dtype {
    Bool,
    I32,
    I64,
    F32,
    F64,
}

impl Dtype {
    pub fn parse(name: &str) -> Result<Dtype> {
        match name {
            "bool" => Ok(Dtype::Bool),
            "i32" => Ok(Dtype::I32),
            "i64" => Ok(Dtype::I64),
            "f32" => Ok(Dtype::F32),
            "f64" => Ok(Dtype::F64),
            other => Err(TensorCoreError::new(
                "TSF-002",
                format!("unsupported dtype: {other}"),
            )),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Dtype::Bool => "bool",
            Dtype::I32 => "i32",
            Dtype::I64 => "i64",
            Dtype::F32 => "f32",
            Dtype::F64 => "f64",
        }
    }

    pub fn byte_width(self) -> usize {
        match self {
            Dtype::Bool => 1,
            Dtype::I32 => 4,
            Dtype::I64 => 8,
            Dtype::F32 => 4,
            Dtype::F64 => 8,
        }
    }

    fn order(self) -> u8 {
        match self {
            Dtype::Bool => 0,
            Dtype::I32 => 1,
            Dtype::I64 => 2,
            Dtype::F32 => 3,
            Dtype::F64 => 4,
        }
    }

    /// Cast a raw value into this dtype's representable range, matching
    /// `_cast()`: bool -> truthiness, i32/i64 -> truncate toward zero,
    /// f32/f64 -> as-is (f32 rounding happens at `.rstensor` byte
    /// packing / to_array time, not here, consistent with the Python
    /// side keeping compat-reference values as full precision floats
    /// internally).
    pub fn cast(self, value: f64) -> f64 {
        match self {
            Dtype::Bool => {
                if value != 0.0 {
                    1.0
                } else {
                    0.0
                }
            }
            Dtype::I32 | Dtype::I64 => value.trunc(),
            Dtype::F32 | Dtype::F64 => value,
        }
    }

    /// Like `cast`, but in `NumericMode::NativeFast` an `f32`-dtype
    /// value is additionally rounded through a real `f32` round-trip
    /// (`value as f32 as f64`) -- the correctly-rounded `f32` result for
    /// that value, identical to what genuine narrow `f32` storage would
    /// produce, without this crate needing a second, narrower `TensorData`
    /// representation. `CompatReference` behaves exactly like `cast`
    /// (this function is a strict superset, not a behavior change) --
    /// bool/i32/i64 truncation and f64 pass-through are identical in
    /// both modes; only f32 rounding differs.
    pub fn round_for_mode(self, value: f64, mode: NumericMode) -> f64 {
        let casted = self.cast(value);
        if mode == NumericMode::NativeFast && matches!(self, Dtype::F32) {
            casted as f32 as f64
        } else {
            casted
        }
    }
}

pub fn promote(a: Dtype, b: Dtype) -> Dtype {
    if a.order() >= b.order() {
        a
    } else {
        b
    }
}
