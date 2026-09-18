//! Process-wide allocation counters (P0 runtime metrics `allocation_count`,
//! `allocated_bytes`, `peak_live_bytes`, and the memory budget).
//!
//! The binary opts in with `#[global_allocator] static GLOBAL:
//! CountingAllocator = CountingAllocator;` (see `runtime-cli/src/main.rs`).
//! Without that declaration every counter simply stays `0`, so library
//! tests are unaffected. Counts come straight from the allocator -- they
//! are measurements, not estimates.

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicU64, Ordering::Relaxed};

static COUNT: AtomicU64 = AtomicU64::new(0);
static BYTES: AtomicU64 = AtomicU64::new(0);
static LIVE: AtomicU64 = AtomicU64::new(0);
static PEAK: AtomicU64 = AtomicU64::new(0);

pub struct CountingAllocator;

#[inline]
fn record_alloc(size: usize) {
    COUNT.fetch_add(1, Relaxed);
    BYTES.fetch_add(size as u64, Relaxed);
    let live = LIVE.fetch_add(size as u64, Relaxed) + size as u64;
    PEAK.fetch_max(live, Relaxed);
}

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        record_alloc(layout.size());
        System.alloc(layout)
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        record_alloc(layout.size());
        System.alloc_zeroed(layout)
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        LIVE.fetch_sub(layout.size() as u64, Relaxed);
        System.dealloc(ptr, layout)
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        record_alloc(new_size);
        LIVE.fetch_sub(layout.size() as u64, Relaxed);
        System.realloc(ptr, layout, new_size)
    }
}

/// Point-in-time reading of the counters; `Vm` diffs two of these to report
/// per-run figures.
#[derive(Clone, Copy, Debug, Default)]
pub struct Snapshot {
    pub count: u64,
    pub bytes: u64,
    pub live: u64,
    pub peak: u64,
}

pub fn snapshot() -> Snapshot {
    Snapshot {
        count: COUNT.load(Relaxed),
        bytes: BYTES.load(Relaxed),
        live: LIVE.load(Relaxed),
        peak: PEAK.load(Relaxed),
    }
}

pub fn live_bytes() -> u64 {
    LIVE.load(Relaxed)
}
