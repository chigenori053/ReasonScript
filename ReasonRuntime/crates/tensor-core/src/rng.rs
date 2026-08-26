//! Deterministic RNG, byte-for-byte matching
//! `frontend/tensor/runtime.py`'s `_random_unit` (SHA-256 counter
//! scheme) and the `random_normal` Box-Muller / `random_permutation`
//! Fisher-Yates formulas built on it.

use sha2::{Digest, Sha256};

use crate::error::{Result, TensorCoreError};

pub fn random_unit(function: &str, seed: i64, stream: i64, counter: u64) -> Result<f64> {
    if seed < 0 || stream < 0 {
        return Err(TensorCoreError::new(
            "RNG-001",
            "seed and stream must be non-negative integers",
        ));
    }
    let message = format!("reasonscript-rng/1\0{function}\0{seed}\0{stream}\0{counter}");
    let digest = Sha256::digest(message.as_bytes());
    let mut bytes = [0u8; 8];
    bytes.copy_from_slice(&digest[..8]);
    let integer = u64::from_le_bytes(bytes) >> 11;
    Ok(integer as f64 / (1u64 << 53) as f64)
}

pub fn uniform(low: f64, high: f64, seed: i64, stream: i64, count: usize) -> Result<Vec<f64>> {
    if high.partial_cmp(&low) != Some(std::cmp::Ordering::Greater) {
        return Err(TensorCoreError::new(
            "RNG-001",
            "invalid random_uniform contract",
        ));
    }
    (0..count)
        .map(|index| {
            random_unit("uniform", seed, stream, index as u64).map(|unit| low + (high - low) * unit)
        })
        .collect()
}

pub fn normal(mean: f64, std: f64, seed: i64, stream: i64, count: usize) -> Result<Vec<f64>> {
    if std < 0.0 {
        return Err(TensorCoreError::new(
            "RNG-001",
            "invalid random_normal contract",
        ));
    }
    let mut result = Vec::with_capacity(count);
    for index in 0..count {
        let u1 = random_unit("normal-a", seed, stream, index as u64)?.max(2f64.powi(-53));
        let u2 = random_unit("normal-b", seed, stream, index as u64)?;
        let z = (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos();
        result.push(mean + std * z);
    }
    Ok(result)
}

pub fn bernoulli(probability: f64, seed: i64, stream: i64, count: usize) -> Result<Vec<f64>> {
    if !(0.0..=1.0).contains(&probability) {
        return Err(TensorCoreError::new(
            "RNG-001",
            "probability must be in [0, 1]",
        ));
    }
    (0..count)
        .map(|index| {
            random_unit("bernoulli", seed, stream, index as u64).map(|unit| {
                if unit < probability {
                    1.0
                } else {
                    0.0
                }
            })
        })
        .collect()
}

pub fn permutation(size: i64, seed: i64, stream: i64) -> Result<Vec<f64>> {
    if size <= 0 {
        return Err(TensorCoreError::new(
            "RNG-001",
            "permutation size must be positive",
        ));
    }
    let size = size as usize;
    let mut values: Vec<i64> = (0..size as i64).collect();
    for index in (1..size).rev() {
        let unit = random_unit("permutation", seed, stream, (size - index) as u64)?;
        let selected = (unit * (index as f64 + 1.0)) as usize;
        values.swap(index, selected);
    }
    Ok(values.into_iter().map(|value| value as f64).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Golden values from `frontend.tensor.runtime._random_unit`:
    ///   _random_unit("uniform", 42, 0, 0) == 0.9294864454185505
    ///   _random_unit("uniform", 42, 0, 1) == 0.9755174574404121
    #[test]
    fn random_unit_matches_python_golden_values() {
        assert_eq!(
            random_unit("uniform", 42, 0, 0).unwrap(),
            0.9294864454185505
        );
        assert_eq!(
            random_unit("uniform", 42, 0, 1).unwrap(),
            0.9755174574404121
        );
    }

    #[test]
    fn negative_seed_or_stream_is_rejected() {
        assert_eq!(
            random_unit("uniform", -1, 0, 0).unwrap_err().code,
            "RNG-001"
        );
        assert_eq!(
            random_unit("uniform", 0, -1, 0).unwrap_err().code,
            "RNG-001"
        );
    }
}
